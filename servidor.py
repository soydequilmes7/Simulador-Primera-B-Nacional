"""
Servidor local para el Simulador Primera Nacional.

Hace tres cosas:
  1. Sirve los archivos de la carpeta public
     igual que "python -m http.server", para que abras la página en el navegador.
  2. Escucha POST /api/simular: cuando apretás el botón "Correr nueva
     simulación" en la web, corre la simulación completa (estadisticas.py +
     main.py), cachea la salida en Supabase y le devuelve el resultado al
     navegador, sin que tengas que volver a la terminal.
  3. Escucha POST /api/actualizar: scrapea los resultados jugados desde Promiedos,
     actualiza Supabase y corre la simulación si hay partidos nuevos.
     Además, cada ACTUALIZAR_CADA_HORAS corre esto solo
     en segundo plano, sin que tengas que apretar nada.

Cómo usarlo:
    (parado en la carpeta "B NACIONAL SIMULADOR", con el venv activado)
    python servidor.py

Después abrís en el navegador:
    http://localhost:8000/template.html

Para frenarlo: Ctrl+C en la terminal.
"""
import json
import threading
import time
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from main import correr_simulacion, simular_hasta_campeon
from main_lpf import correr_simulacion_lpf, simular_hasta_campeon_lpf
from main_primerac import correr_simulacion as correr_simulacion_primerac, simular_hasta_campeon as simular_hasta_campeon_primerac
from actualizar_resultados import actualizar
from actualizar_resultados_lpf import actualizar as actualizar_lpf
from actualizar_resultados_primerac import actualizar as actualizar_primerac
from main_copa import correr_simulacion_copa, simular_hasta_campeon_copa
from actualizar_resultados_copa import actualizar as actualizar_copa
from main_bmetro import correr_simulacion_bmetro, simular_hasta_ascenso_bmetro
from actualizar_resultados_bmetro import actualizar as actualizar_bmetro
from main_federal import correr_simulacion_federal, simular_hasta_ascenso_federal
from actualizar_resultados_federal import actualizar as actualizar_federal
from main_libertadores import correr_simulacion_libertadores
from db.client import DatabaseConfigError
from db.repository import cup_csv_files, league_csv_files, transaction
from posiciones_evolucion import calcular_evolucion, tamano_por_zona
import rutas

# Mismos archivos que sirve api/index.py en /api/pysim-source, para que
# sim-worker.js pueda cargar el simulador local (Pyodide) también en
# desarrollo, no solo en Render.
PYSIM_SOURCE_FILES = [
    "rutas.py",
    "data_access.py",
    "main.py",
    "main_lpf.py",
    "pysim_dispatch.py",
    "modelos/equipo.py",
    "modelos/estadisticas.py",
    "modelos/estadisticas_lpf.py",
    "main_copa.py",
    "modelos/estadisticas_copa.py",
    "main_bmetro.py",
    "modelos/estadisticas_bmetro.py",
    "main_federal.py",
    "modelos/estadisticas_federal.py",
    "modelos/motor_vectorizado.py",
    "fixture_generator.py",
    "main_primerac.py",
    "modelos/estadisticas_primerac.py",
    "main_libertadores.py",
    "modelos/estadisticas_libertadores.py",
    "main_sudamericana.py",
    "modelos/estadisticas_sudamericana.py",
]
_pysim_source_cache = None

PUERTO = 8000
CARPETA_WEB = "public"
N_SIMULACIONES = 500

# Límites para el valor de n_sims que puede pedir la página (evita que un
# valor mal formado o abusivo tumbe el servidor o lo cuelgue por horas).
N_SIMULACIONES_MIN = 50
N_SIMULACIONES_MAX = 5000

# Límites para "simular hasta que un equipo ascienda" (/api/simular-campeon).
# Cada intento es una sola temporada (mucho más liviano que un Monte Carlo
# de 1000 corridas), así que se puede permitir un tope más alto.
MAX_INTENTOS_CAMPEON_DEFAULT = 5000
MAX_INTENTOS_CAMPEON_MIN = 100
MAX_INTENTOS_CAMPEON_MAX = 20000


def _error_http(exc):
    if isinstance(exc, DatabaseConfigError):
        return 503, {"error": str(exc), "config_error": True}
    return 500, {"error": str(exc)}

# Cada cuántas horas se corre la actualización automática sola en segundo
# plano. Poné None para desactivar el auto-update y usar solo el botón manual.
ACTUALIZAR_CADA_HORAS = 6

# Evita que se disparen dos simulaciones/actualizaciones al mismo tiempo
lock_simulacion = threading.Lock()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=CARPETA_WEB, **kwargs)

    def _responder_json(self, status, data):
        cuerpo = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        if self.path == "/api/pysim-source":
            self._manejar_pysim_source()
        elif self.path == "/api/datos-nacional":
            self._manejar_datos_nacional()
        elif self.path == "/api/evolucion-posiciones-nacional":
            self._manejar_evolucion_posiciones_nacional()
        elif self.path == "/api/datos-copa":
            self._manejar_datos_csv(["copa_argentina.csv"])
        elif self.path == "/api/datos-lpf":
            self._manejar_datos_lpf()
        elif self.path == "/api/datos-bmetro":
            self._manejar_datos_csv(["tabla_bmetro.csv", "fixture_bmetro.csv", "resultados_bmetro.csv"])
        elif self.path == "/api/datos-federal":
            self._manejar_datos_csv(["tabla_federal_a.csv", "fixture_federal_a.csv", "resultados_federal_a.csv"])
        elif self.path == "/api/datos-primerac":
            self._manejar_datos_csv(["tabla_primerac.csv", "fixture_primerac.csv", "resultados_primerac.csv"])
        elif self.path == "/api/datos-libertadores":
            self._manejar_datos_locales(["libertadores_cuadro.csv", "libertadores_elo.csv"])
        elif self.path == "/api/datos-sudamericana":
            self._manejar_datos_locales(["sudamericana_cuadro.csv", "sudamericana_elo.csv"])
        else:
            super().do_GET()

    def _manejar_pysim_source(self):
        global _pysim_source_cache
        try:
            if _pysim_source_cache is None:
                archivos = {}
                for nombre_relativo in PYSIM_SOURCE_FILES:
                    ruta = rutas.REPO_DIR / nombre_relativo
                    archivos[nombre_relativo] = ruta.read_text(encoding="utf-8")
                _pysim_source_cache = archivos
            self._responder_json(200, {"files": _pysim_source_cache})
        except Exception as e:
            self._responder_json(*_error_http(e))

    def _manejar_datos_nacional(self):
        try:
            self._responder_json(200, {"files": league_csv_files("nacional")})
        except Exception as e:
            self._responder_json(*_error_http(e))

    def _manejar_evolucion_posiciones_nacional(self):
        """Posición de cada equipo de Primera Nacional después de cada
        fecha ya jugada (ver posiciones_evolucion.calcular_evolucion)."""
        try:
            with transaction() as repo:
                tabla_actual = repo.standing_records("nacional")
                zona_por_club = {fila["equipo"]: fila["zona"] for fila in tabla_actual}
                partidos_jugados = repo.match_records("nacional", "played")
            evolucion = calcular_evolucion(partidos_jugados, zona_por_club)
            self._responder_json(200, {
                "evolucion": evolucion,
                "zonas": tamano_por_zona(zona_por_club),
            })
        except Exception as e:
            self._responder_json(*_error_http(e))

    def _manejar_datos_locales(self, nombres):
        """A diferencia de _manejar_datos_csv (Supabase), Libertadores y
        Sudamericana no pasan por la base: leen directo de datos/*.csv
        (ver cargar_datos_libertadores()/cargar_datos_sudamericana())."""
        try:
            archivos = {nombre: (rutas.datos_dir() / nombre).read_text(encoding="utf-8") for nombre in nombres}
            self._responder_json(200, {"files": archivos})
        except Exception as e:
            self._responder_json(*_error_http(e))

    def _manejar_datos_csv(self, nombres):
        """Handler genérico: devuelve {files: {nombre: contenido}} para la
        lista de CSVs pedida (lo usa /api/datos-copa)."""
        try:
            if nombres == ["copa_argentina.csv"]:
                self._responder_json(200, {"files": cup_csv_files()})
            elif "bmetro" in nombres[0]:
                self._responder_json(200, {"files": league_csv_files("bmetro")})
            elif "federal" in nombres[0]:
                self._responder_json(200, {"files": league_csv_files("federal_a")})
            elif "primerac" in nombres[0]:
                self._responder_json(200, {"files": league_csv_files("primerac")})
            else:
                self._responder_json(500, {"error": f"Dataset no soportado: {nombres}"})
        except Exception as e:
            self._responder_json(*_error_http(e))

    def _manejar_datos_lpf(self):
        try:
            self._responder_json(200, {"files": league_csv_files("lpf")})
        except Exception as e:
            self._responder_json(*_error_http(e))

    def do_POST(self):
        if self.path == "/api/simular":
            self._manejar_simular()
        elif self.path == "/api/actualizar":
            self._manejar_actualizar()
        elif self.path == "/api/simular-campeon":
            self._manejar_simular_campeon()
        elif self.path == "/api/simular-lpf":
            self._manejar_simular_lpf()
        elif self.path == "/api/actualizar-lpf":
            self._manejar_actualizar_lpf()
        elif self.path == "/api/simular-campeon-lpf":
            self._manejar_simular_campeon_lpf()
        elif self.path == "/api/simular-primerac":
            self._manejar_simular_primerac()
        elif self.path == "/api/actualizar-primerac":
            self._manejar_actualizar_primerac()
        elif self.path == "/api/simular-campeon-primerac":
            self._manejar_simular_campeon_primerac()
        elif self.path == "/api/simular-copa":
            self._manejar_simular_copa()
        elif self.path == "/api/actualizar-copa":
            self._manejar_actualizar_copa()
        elif self.path == "/api/simular-campeon-copa":
            self._manejar_simular_campeon_copa()
        elif self.path == "/api/simular-bmetro":
            self._manejar_simular_bmetro()
        elif self.path == "/api/actualizar-bmetro":
            self._manejar_actualizar_bmetro()
        elif self.path == "/api/simular-campeon-bmetro":
            self._manejar_simular_campeon_bmetro()
        elif self.path == "/api/simular-federal":
            self._manejar_simular_federal()
        elif self.path == "/api/actualizar-federal":
            self._manejar_actualizar_federal()
        elif self.path == "/api/simular-campeon-federal":
            self._manejar_simular_campeon_federal()
        elif self.path == "/api/simular-libertadores":
            self._manejar_simular_libertadores()
        else:
            self._responder_json(404, {"error": "Ruta no encontrada"})

    def _leer_n_sims(self):
        """Lee n_sims del body JSON del POST (si lo mandaron) y lo clampea a
        un rango razonable. Si no viene body, viene vacío, o viene mal
        formado, usa N_SIMULACIONES sin romper nada."""
        n_sims = N_SIMULACIONES
        try:
            largo = int(self.headers.get("Content-Length", 0))
            if largo > 0:
                cuerpo = self.rfile.read(largo)
                datos = json.loads(cuerpo)
                n_sims = int(datos.get("n_sims", N_SIMULACIONES))
        except (ValueError, TypeError, json.JSONDecodeError):
            n_sims = N_SIMULACIONES

        return max(N_SIMULACIONES_MIN, min(N_SIMULACIONES_MAX, n_sims))

    def _manejar_simular(self):
        n_sims = self._leer_n_sims()
        if not lock_simulacion.acquire(blocking=False):
            self._responder_json(409, {"error": "Ya hay una simulación corriendo, esperá a que termine"})
            return
        try:
            print(f"\n>>> Corriendo nueva simulación pedida desde la web ({n_sims} corridas)...")
            datos = correr_simulacion(n_sims=n_sims, imprimir=True)
            print(">>> Simulación terminada y data.json actualizado.\n")
            self._responder_json(200, datos)
        except Exception as e:
            print(f">>> ERROR al simular: {e}")
            self._responder_json(*_error_http(e))
        finally:
            lock_simulacion.release()

    def _manejar_actualizar(self):
        n_sims = self._leer_n_sims()
        if not lock_simulacion.acquire(blocking=False):
            self._responder_json(409, {"error": "Ya hay una simulación/actualización corriendo, esperá a que termine"})
            return
        try:
            print(f"\n>>> Actualización pedida desde la web (Promiedos), {n_sims} corridas si hay partidos nuevos...")
            resultado = actualizar(n_sims=n_sims, imprimir=True)
            print(">>> Actualización terminada.\n")
            self._responder_json(200, resultado)
        except Exception as e:
            print(f">>> ERROR al actualizar: {e}")
            self._responder_json(*_error_http(e))
        finally:
            lock_simulacion.release()

    def _manejar_simular_lpf(self):
        """Corre una simulación completa de la LPF (Clausura + playoffs +
        tabla anual + descensos + copas + Trofeo de Campeones) pedida
        desde el selector de liga de la web, con el n_sims del body."""
        n_sims = self._leer_n_sims()
        if not lock_simulacion.acquire(blocking=False):
            self._responder_json(409, {"error": "Ya hay una simulación corriendo, esperá a que termine"})
            return
        try:
            print(f"\n>>> Corriendo nueva simulación de LPF pedida desde la web ({n_sims} corridas)...")
            datos = correr_simulacion_lpf(imprimir=True, n_sims=n_sims)
            print(">>> Simulación de LPF terminada y data_lpf.json actualizado.\n")
            self._responder_json(200, datos)
        except Exception as e:
            print(f">>> ERROR al simular LPF: {e}")
            self._responder_json(*_error_http(e))
        finally:
            lock_simulacion.release()

    def _manejar_actualizar_lpf(self):
        """Scrapea Promiedos (LPF) y, si hay partidos nuevos, actualiza los
        CSV y re-simula con correr_simulacion_lpf."""
        n_sims = self._leer_n_sims()
        if not lock_simulacion.acquire(blocking=False):
            self._responder_json(409, {"error": "Ya hay una simulación/actualización corriendo, esperá a que termine"})
            return
        try:
            print(f"\n>>> Actualización LPF pedida desde la web (Promiedos), {n_sims} corridas si hay partidos nuevos...")
            resultado = actualizar_lpf(n_sims=n_sims, correr_simulacion_fn=correr_simulacion_lpf, imprimir=True)
            print(">>> Actualización LPF terminada.\n")
            self._responder_json(200, resultado)
        except Exception as e:
            print(f">>> ERROR al actualizar LPF: {e}")
            self._responder_json(*_error_http(e))
        finally:
            lock_simulacion.release()

    def _manejar_simular_primerac(self):
        """Corre una simulación completa de Primera C (fase de zonas,
        Final por el 1er Ascenso, Reducido por el 2do y Monte Carlo)
        pedida desde el selector de liga de la web, con el n_sims del
        body."""
        n_sims = self._leer_n_sims()
        if not lock_simulacion.acquire(blocking=False):
            self._responder_json(409, {"error": "Ya hay una simulación corriendo, esperá a que termine"})
            return
        try:
            print(f"\n>>> Corriendo nueva simulación de Primera C pedida desde la web ({n_sims} corridas)...")
            datos = correr_simulacion_primerac(imprimir=True, n_sims=n_sims)
            print(">>> Simulación de Primera C terminada y data_primerac.json actualizado.\n")
            self._responder_json(200, datos)
        except Exception as e:
            print(f">>> ERROR al simular Primera C: {e}")
            self._responder_json(*_error_http(e))
        finally:
            lock_simulacion.release()

    def _manejar_actualizar_primerac(self):
        """Scrapea Promiedos (Primera C) y, si hay partidos nuevos,
        actualiza los CSV y re-simula con correr_simulacion_primerac."""
        n_sims = self._leer_n_sims()
        if not lock_simulacion.acquire(blocking=False):
            self._responder_json(409, {"error": "Ya hay una simulación/actualización corriendo, esperá a que termine"})
            return
        try:
            print(f"\n>>> Actualización Primera C pedida desde la web (Promiedos), {n_sims} corridas si hay partidos nuevos...")
            resultado = actualizar_primerac(n_sims=n_sims, correr_simulacion_fn=correr_simulacion_primerac, imprimir=True)
            print(">>> Actualización Primera C terminada.\n")
            self._responder_json(200, resultado)
        except Exception as e:
            print(f">>> ERROR al actualizar Primera C: {e}")
            self._responder_json(*_error_http(e))
        finally:
            lock_simulacion.release()

    def _manejar_simular_campeon_primerac(self):
        """Corre simular_hasta_campeon_primerac() del equipo pedido desde
        la web (vía ascenso directo o Reducido) y devuelve esa temporada
        completa. No toca data_primerac.json: es una corrida aparte."""
        if not lock_simulacion.acquire(blocking=False):
            self._responder_json(409, {"error": "Ya hay una simulación corriendo, esperá a que termine"})
            return
        try:
            largo = int(self.headers.get("Content-Length", 0))
            cuerpo_raw = self.rfile.read(largo) if largo > 0 else b"{}"
            datos = json.loads(cuerpo_raw) if cuerpo_raw else {}

            equipo_objetivo = str(datos.get("equipo", "")).strip()
            if not equipo_objetivo:
                self._responder_json(400, {"error": "Falta indicar el equipo"})
                return

            try:
                max_intentos = int(datos.get("max_intentos", MAX_INTENTOS_CAMPEON_DEFAULT))
            except (ValueError, TypeError):
                max_intentos = MAX_INTENTOS_CAMPEON_DEFAULT
            max_intentos = max(MAX_INTENTOS_CAMPEON_MIN, min(MAX_INTENTOS_CAMPEON_MAX, max_intentos))

            print(f"\n>>> Simulando hasta el ascenso de {equipo_objetivo} (Primera C) pedido desde la web ({max_intentos} intentos máx)...")
            resultado = simular_hasta_campeon_primerac(equipo_objetivo, max_intentos=max_intentos, imprimir=True)

            if resultado is None:
                print(f">>> No se logró el ascenso de {equipo_objetivo} en {max_intentos} intentos.\n")
                self._responder_json(200, {
                    "logrado": False,
                    "equipo": equipo_objetivo,
                    "max_intentos": max_intentos,
                })
                return

            print(f">>> {equipo_objetivo} ascendió en el intento {resultado['intentos']}.\n")
            self._responder_json(200, {"logrado": True, **resultado})
        except ValueError as e:
            self._responder_json(400, {"error": str(e)})
        except json.JSONDecodeError:
            self._responder_json(400, {"error": "Body inválido"})
        except Exception as e:
            print(f">>> ERROR al simular hasta campeón Primera C: {e}")
            self._responder_json(*_error_http(e))
        finally:
            lock_simulacion.release()

    def _manejar_simular_campeon(self):
        """Corre simular_hasta_campeon() del equipo pedido desde la web y
        devuelve esa temporada completa (tabla, final de ascenso y
        Reducido) en la respuesta. No toca data.json: es una corrida
        aparte, para "ver cómo sería" el ascenso de un equipo puntual."""
        if not lock_simulacion.acquire(blocking=False):
            self._responder_json(409, {"error": "Ya hay una simulación corriendo, esperá a que termine"})
            return
        try:
            largo = int(self.headers.get("Content-Length", 0))
            cuerpo_raw = self.rfile.read(largo) if largo > 0 else b"{}"
            datos = json.loads(cuerpo_raw) if cuerpo_raw else {}

            equipo_objetivo = str(datos.get("equipo", "")).strip()
            if not equipo_objetivo:
                self._responder_json(400, {"error": "Falta indicar el equipo"})
                return

            try:
                max_intentos = int(datos.get("max_intentos", MAX_INTENTOS_CAMPEON_DEFAULT))
            except (ValueError, TypeError):
                max_intentos = MAX_INTENTOS_CAMPEON_DEFAULT
            max_intentos = max(MAX_INTENTOS_CAMPEON_MIN, min(MAX_INTENTOS_CAMPEON_MAX, max_intentos))

            print(f"\n>>> Simulando hasta el ascenso de {equipo_objetivo} pedido desde la web ({max_intentos} intentos máx)...")
            resultado = simular_hasta_campeon(equipo_objetivo, max_intentos=max_intentos, imprimir=True)

            if resultado is None:
                print(f">>> No se logró el ascenso de {equipo_objetivo} en {max_intentos} intentos.\n")
                self._responder_json(200, {
                    "logrado": False,
                    "equipo": equipo_objetivo,
                    "max_intentos": max_intentos,
                })
                return

            print(f">>> {equipo_objetivo} ascendió en el intento {resultado['intentos']}.\n")
            self._responder_json(200, {"logrado": True, **resultado})
        except ValueError as e:
            # simular_hasta_campeon levanta ValueError si el nombre de
            # equipo no existe (con sugerencias si hay coincidencias parciales)
            self._responder_json(400, {"error": str(e)})
        except json.JSONDecodeError:
            self._responder_json(400, {"error": "Body inválido"})
        except Exception as e:
            print(f">>> ERROR al simular hasta campeón: {e}")
            self._responder_json(*_error_http(e))
        finally:
            lock_simulacion.release()

    def _manejar_simular_campeon_lpf(self):
        """Corre simular_hasta_campeon_lpf() del equipo pedido desde la web
        y devuelve esa temporada completa (tablas del Clausura y bracket
        de playoffs) en la respuesta. No toca data_lpf.json."""
        if not lock_simulacion.acquire(blocking=False):
            self._responder_json(409, {"error": "Ya hay una simulación corriendo, esperá a que termine"})
            return
        try:
            largo = int(self.headers.get("Content-Length", 0))
            cuerpo_raw = self.rfile.read(largo) if largo > 0 else b"{}"
            datos = json.loads(cuerpo_raw) if cuerpo_raw else {}

            equipo_objetivo = str(datos.get("equipo", "")).strip()
            if not equipo_objetivo:
                self._responder_json(400, {"error": "Falta indicar el equipo"})
                return

            try:
                max_intentos = int(datos.get("max_intentos", MAX_INTENTOS_CAMPEON_DEFAULT))
            except (ValueError, TypeError):
                max_intentos = MAX_INTENTOS_CAMPEON_DEFAULT
            max_intentos = max(MAX_INTENTOS_CAMPEON_MIN, min(MAX_INTENTOS_CAMPEON_MAX, max_intentos))

            print(f"\n>>> Simulando hasta el título de {equipo_objetivo} (LPF) pedido desde la web ({max_intentos} intentos máx)...")
            resultado = simular_hasta_campeon_lpf(equipo_objetivo, max_intentos=max_intentos, imprimir=True)

            if resultado is None:
                print(f">>> No se logró el título de {equipo_objetivo} en {max_intentos} intentos.\n")
                self._responder_json(200, {
                    "logrado": False,
                    "equipo": equipo_objetivo,
                    "max_intentos": max_intentos,
                })
                return

            print(f">>> {equipo_objetivo} salió campeón en el intento {resultado['intentos']}.\n")
            self._responder_json(200, {"logrado": True, **resultado})
        except ValueError as e:
            self._responder_json(400, {"error": str(e)})
        except json.JSONDecodeError:
            self._responder_json(400, {"error": "Body inválido"})
        except Exception as e:
            print(f">>> ERROR al simular hasta campeón LPF: {e}")
            self._responder_json(*_error_http(e))
        finally:
            lock_simulacion.release()

    def _manejar_simular_copa(self):
        """Simula el cuadro de la Copa Argentina (con Monte Carlo) pedido
        desde la web, con el n_sims del body."""
        n_sims = self._leer_n_sims()
        if not lock_simulacion.acquire(blocking=False):
            self._responder_json(409, {"error": "Ya hay una simulación corriendo, esperá a que termine"})
            return
        try:
            print(f"\n>>> Corriendo simulación de Copa Argentina pedida desde la web ({n_sims} corridas)...")
            datos = correr_simulacion_copa(imprimir=True, n_sims=n_sims)
            print(">>> Simulación de Copa terminada y data_copa.json actualizado.\n")
            self._responder_json(200, datos)
        except Exception as e:
            print(f">>> ERROR al simular Copa: {e}")
            self._responder_json(*_error_http(e))
        finally:
            lock_simulacion.release()

    def _manejar_actualizar_copa(self):
        """Scrapea Promiedos (Copa Argentina) y, si hay cruces nuevos,
        actualiza el cuadro y re-simula."""
        n_sims = self._leer_n_sims()
        if not lock_simulacion.acquire(blocking=False):
            self._responder_json(409, {"error": "Ya hay una simulación corriendo, esperá a que termine"})
            return
        try:
            print(f"\n>>> Actualización de Copa Argentina pedida desde la web (Promiedos)...")
            resultado = actualizar_copa(n_sims=n_sims, correr_simulacion_fn=correr_simulacion_copa, imprimir=True)
            print(">>> Actualización de Copa terminada.\n")
            self._responder_json(200, resultado)
        except Exception as e:
            print(f">>> ERROR al actualizar Copa: {e}")
            self._responder_json(*_error_http(e))
        finally:
            lock_simulacion.release()

    def _manejar_simular_campeon_copa(self):
        """Repite el cuadro hasta que el equipo pedido salga campeón de la
        Copa y devuelve esa corrida completa."""
        if not lock_simulacion.acquire(blocking=False):
            self._responder_json(409, {"error": "Ya hay una simulación corriendo, esperá a que termine"})
            return
        try:
            largo = int(self.headers.get("Content-Length", 0))
            cuerpo_raw = self.rfile.read(largo) if largo > 0 else b"{}"
            datos = json.loads(cuerpo_raw) if cuerpo_raw else {}

            equipo_objetivo = str(datos.get("equipo", "")).strip()
            if not equipo_objetivo:
                self._responder_json(400, {"error": "Falta indicar el equipo"})
                return

            try:
                max_intentos = int(datos.get("max_intentos", MAX_INTENTOS_CAMPEON_DEFAULT))
            except (ValueError, TypeError):
                max_intentos = MAX_INTENTOS_CAMPEON_DEFAULT
            max_intentos = max(MAX_INTENTOS_CAMPEON_MIN, min(MAX_INTENTOS_CAMPEON_MAX, max_intentos))

            print(f"\n>>> Simulando hasta el título de {equipo_objetivo} (Copa Argentina)...")
            resultado = simular_hasta_campeon_copa(equipo_objetivo, max_intentos=max_intentos, imprimir=True)

            if resultado is None:
                self._responder_json(200, {"logrado": False, "equipo": equipo_objetivo, "max_intentos": max_intentos})
                return
            self._responder_json(200, {"logrado": True, **resultado})
        except ValueError as e:
            self._responder_json(400, {"error": str(e)})
        except json.JSONDecodeError:
            self._responder_json(400, {"error": "Body inválido"})
        except Exception as e:
            print(f">>> ERROR al simular hasta campeón Copa: {e}")
            self._responder_json(*_error_http(e))
        finally:
            lock_simulacion.release()

    def _manejar_simular_bmetro(self):
        """Corre la simulación completa de B Metropolitana (temporada
        regular + ascenso directo + Torneo Reducido + Monte Carlo) pedida
        desde la web, con el n_sims del body."""
        n_sims = self._leer_n_sims()
        if not lock_simulacion.acquire(blocking=False):
            self._responder_json(409, {"error": "Ya hay una simulación corriendo, esperá a que termine"})
            return
        try:
            print(f"\n>>> Corriendo nueva simulación de B Metro pedida desde la web ({n_sims} corridas)...")
            datos = correr_simulacion_bmetro(imprimir=True, n_sims=n_sims)
            print(">>> Simulación de B Metro terminada y data_bmetro.json actualizado.\n")
            self._responder_json(200, datos)
        except Exception as e:
            print(f">>> ERROR al simular B Metro: {e}")
            self._responder_json(*_error_http(e))
        finally:
            lock_simulacion.release()

    def _manejar_actualizar_bmetro(self):
        """Scrapea Promiedos (B Metropolitana) y, si hay partidos nuevos,
        actualiza fixture/resultados/tabla y re-simula."""
        n_sims = self._leer_n_sims()
        if not lock_simulacion.acquire(blocking=False):
            self._responder_json(409, {"error": "Ya hay una simulación/actualización corriendo, esperá a que termine"})
            return
        try:
            print(f"\n>>> Actualización de B Metro pedida desde la web (Promiedos), {n_sims} corridas si hay partidos nuevos...")
            resultado = actualizar_bmetro(n_sims=n_sims, correr_simulacion_fn=correr_simulacion_bmetro, imprimir=True)
            print(">>> Actualización de B Metro terminada.\n")
            self._responder_json(200, resultado)
        except Exception as e:
            print(f">>> ERROR al actualizar B Metro: {e}")
            self._responder_json(*_error_http(e))
        finally:
            lock_simulacion.release()

    def _manejar_simular_campeon_bmetro(self):
        """Corre simular_hasta_ascenso_bmetro() del equipo pedido desde la
        web y devuelve esa temporada completa (tabla única y, si le tocó
        vía Reducido, el bracket) en la respuesta."""
        if not lock_simulacion.acquire(blocking=False):
            self._responder_json(409, {"error": "Ya hay una simulación corriendo, esperá a que termine"})
            return
        try:
            largo = int(self.headers.get("Content-Length", 0))
            cuerpo_raw = self.rfile.read(largo) if largo > 0 else b"{}"
            datos = json.loads(cuerpo_raw) if cuerpo_raw else {}

            equipo_objetivo = str(datos.get("equipo", "")).strip()
            if not equipo_objetivo:
                self._responder_json(400, {"error": "Falta indicar el equipo"})
                return

            try:
                max_intentos = int(datos.get("max_intentos", MAX_INTENTOS_CAMPEON_DEFAULT))
            except (ValueError, TypeError):
                max_intentos = MAX_INTENTOS_CAMPEON_DEFAULT
            max_intentos = max(MAX_INTENTOS_CAMPEON_MIN, min(MAX_INTENTOS_CAMPEON_MAX, max_intentos))

            print(f"\n>>> Simulando hasta el ascenso de {equipo_objetivo} (B Metro) pedido desde la web ({max_intentos} intentos máx)...")
            resultado = simular_hasta_ascenso_bmetro(equipo_objetivo, max_intentos=max_intentos, imprimir=True)

            if resultado is None:
                print(f">>> No se logró el ascenso de {equipo_objetivo} en {max_intentos} intentos.\n")
                self._responder_json(200, {
                    "logrado": False,
                    "equipo": equipo_objetivo,
                    "max_intentos": max_intentos,
                })
                return

            print(f">>> {equipo_objetivo} ascendió en el intento {resultado['intentos']}.\n")
            self._responder_json(200, {"logrado": True, **resultado})
        except ValueError as e:
            self._responder_json(400, {"error": str(e)})
        except json.JSONDecodeError:
            self._responder_json(400, {"error": "Body inválido"})
        except Exception as e:
            print(f">>> ERROR al simular hasta ascenso B Metro: {e}")
            self._responder_json(*_error_http(e))
        finally:
            lock_simulacion.release()

    def _manejar_simular_federal(self):
        """Corre el Torneo Federal A completo (5 Fases + Reválida de 6
        Etapas) pedido desde la web, con el n_sims del body."""
        n_sims = self._leer_n_sims()
        if not lock_simulacion.acquire(blocking=False):
            self._responder_json(409, {"error": "Ya hay una simulación corriendo, esperá a que termine"})
            return
        try:
            print(f"\n>>> Corriendo nueva simulación de Federal A pedida desde la web ({n_sims} corridas)...")
            datos = correr_simulacion_federal(imprimir=True, n_sims=n_sims)
            print(">>> Simulación de Federal A terminada y data_federal_a.json actualizado.\n")
            self._responder_json(200, datos)
        except Exception as e:
            print(f">>> ERROR al simular Federal A: {e}")
            self._responder_json(*_error_http(e))
        finally:
            lock_simulacion.release()

    def _manejar_actualizar_federal(self):
        """Scrapea Promiedos (Federal A) y, si hay partidos nuevos,
        actualiza fixture/resultados/tabla y re-simula."""
        n_sims = self._leer_n_sims()
        if not lock_simulacion.acquire(blocking=False):
            self._responder_json(409, {"error": "Ya hay una simulación corriendo, esperá a que termine"})
            return
        try:
            print(f"\n>>> Actualización de Federal A pedida desde la web (Promiedos)...")
            resultado = actualizar_federal(n_sims=n_sims, correr_simulacion_fn=correr_simulacion_federal, imprimir=True)
            print(">>> Actualización de Federal A terminada.\n")
            self._responder_json(200, resultado)
        except Exception as e:
            print(f">>> ERROR al actualizar Federal A: {e}")
            self._responder_json(*_error_http(e))
        finally:
            lock_simulacion.release()

    def _manejar_simular_campeon_federal(self):
        """Corre simular_hasta_ascenso_federal() del equipo pedido desde
        la web (vía directa o Reválida) y devuelve esa corrida completa."""
        if not lock_simulacion.acquire(blocking=False):
            self._responder_json(409, {"error": "Ya hay una simulación corriendo, esperá a que termine"})
            return
        try:
            largo = int(self.headers.get("Content-Length", 0))
            cuerpo_raw = self.rfile.read(largo) if largo > 0 else b"{}"
            datos = json.loads(cuerpo_raw) if cuerpo_raw else {}

            equipo_objetivo = str(datos.get("equipo", "")).strip()
            if not equipo_objetivo:
                self._responder_json(400, {"error": "Falta indicar el equipo"})
                return

            try:
                max_intentos = int(datos.get("max_intentos", MAX_INTENTOS_CAMPEON_DEFAULT))
            except (ValueError, TypeError):
                max_intentos = MAX_INTENTOS_CAMPEON_DEFAULT
            max_intentos = max(MAX_INTENTOS_CAMPEON_MIN, min(MAX_INTENTOS_CAMPEON_MAX, max_intentos))

            print(f"\n>>> Simulando hasta el ascenso de {equipo_objetivo} (Federal A) pedido desde la web ({max_intentos} intentos máx)...")
            resultado = simular_hasta_ascenso_federal(equipo_objetivo, max_intentos=max_intentos, imprimir=True)

            if resultado is None:
                print(f">>> No se logró el ascenso de {equipo_objetivo} en {max_intentos} intentos.\n")
                self._responder_json(200, {"logrado": False, "equipo": equipo_objetivo, "max_intentos": max_intentos})
                return

            intentos = resultado["intentos"]
            print(f">>> {equipo_objetivo} ascendió en el intento {intentos}.")
            self._responder_json(200, {"logrado": True, **resultado})
        except ValueError as e:
            self._responder_json(400, {"error": str(e)})
        except json.JSONDecodeError:
            self._responder_json(400, {"error": "Body inválido"})
        except Exception as e:
            print(f">>> ERROR al simular hasta ascenso Federal A: {e}")
            self._responder_json(*_error_http(e))
        finally:
            lock_simulacion.release()

    def log_message(self, formato, *args):
        print("[servidor]", formato % args)

    def _manejar_simular_libertadores(self):
        """Corre el cuadro completo de la Copa Libertadores (desde Octavos
        de Final) pedido desde la web, con el n_sims del body."""
        n_sims = self._leer_n_sims()
        if not lock_simulacion.acquire(blocking=False):
            self._responder_json(409, {"error": "Ya hay una simulación corriendo, esperá a que termine"})
            return
        try:
            print(f"\n>>> Corriendo nueva simulación de Copa Libertadores pedida desde la web ({n_sims} corridas)...")
            datos = correr_simulacion_libertadores(imprimir=True, n_sims=n_sims)
            print(">>> Simulación de Copa Libertadores terminada y data_libertadores.json actualizado.\n")
            self._responder_json(200, datos)
        except Exception as e:
            print(f">>> ERROR al simular Copa Libertadores: {e}")
            self._responder_json(*_error_http(e))
        finally:
            lock_simulacion.release()


def _hilo_auto_actualizacion():
    """Corre actualizar() sola cada ACTUALIZAR_CADA_HORAS horas, en segundo plano."""
    if not ACTUALIZAR_CADA_HORAS:
        return
    while True:
        time.sleep(ACTUALIZAR_CADA_HORAS * 3600)
        if lock_simulacion.acquire(blocking=False):
            try:
                print("\n>>> [auto] Chequeando resultados nuevos en Promiedos...")
                actualizar(n_sims=N_SIMULACIONES, imprimir=True)
            except Exception:
                print(">>> [auto] ERROR en la actualización automática:")
                traceback.print_exc()
            finally:
                lock_simulacion.release()
        else:
            print(">>> [auto] Se salteó el chequeo automático porque había algo corriendo.")


if __name__ == "__main__":
    servidor = ThreadingHTTPServer(("", PUERTO), Handler)

    if ACTUALIZAR_CADA_HORAS:
        hilo = threading.Thread(target=_hilo_auto_actualizacion, daemon=True)
        hilo.start()

    print("=" * 50)
    print(f"Servidor corriendo en http://localhost:{PUERTO}/template.html")
    if ACTUALIZAR_CADA_HORAS:
        print(f"Auto-actualización activada: cada {ACTUALIZAR_CADA_HORAS} horas revisa Promiedos solo.")
    else:
        print("Auto-actualización desactivada (ACTUALIZAR_CADA_HORAS = None).")
    print("Apretá Ctrl+C para frenarlo.")
    print("=" * 50)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
