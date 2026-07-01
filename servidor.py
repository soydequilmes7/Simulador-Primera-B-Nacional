"""
Servidor local para el Simulador Primera Nacional.

Hace tres cosas:
  1. Sirve los archivos de la carpeta public (template.html, data.json)
     igual que "python -m http.server", para que abras la página en el navegador.
  2. Escucha POST /api/simular: cuando apretás el botón "Correr nueva
     simulación" en la web, corre la simulación completa (estadisticas.py +
     main.py), regenera public/data.json y le devuelve el resultado al
     navegador, sin que tengas que volver a la terminal.
  3. Escucha POST /api/actualizar: scrapea los resultados jugados desde Promiedos,
     completa fixture.csv -> resultados.csv y corre la simulación si hay
     partidos nuevos. Además, cada ACTUALIZAR_CADA_HORAS corre esto solo
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

from main import correr_simulacion
from actualizar_resultados import actualizar

PUERTO = 8000
CARPETA_WEB = "public"
N_SIMULACIONES = 1000

# Límites para el valor de n_sims que puede pedir la página (evita que un
# valor mal formado o abusivo tumbe el servidor o lo cuelgue por horas).
N_SIMULACIONES_MIN = 50
N_SIMULACIONES_MAX = 5000

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

    def do_POST(self):
        if self.path == "/api/simular":
            self._manejar_simular()
        elif self.path == "/api/actualizar":
            self._manejar_actualizar()
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
            self._responder_json(500, {"error": str(e)})
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
            self._responder_json(500, {"error": str(e)})
        finally:
            lock_simulacion.release()

    def log_message(self, formato, *args):
        print("[servidor]", formato % args)


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
