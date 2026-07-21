# -*- coding: utf-8 -*-
"""
api/index.py

Backend FastAPI/ASGI. Expone la misma funcionalidad que servidor.py
(simular / actualizar) y también puede servir el dashboard estático en
Render. La persistencia runtime usa Supabase Postgres.

Local (con uvicorn instalado):
    uvicorn api.index:app --reload
    -> http://localhost:8000/api/health

Render:
    uvicorn api.index:app --host 0.0.0.0 --port $PORT
"""
import sys
import threading
from datetime import datetime
from pathlib import Path

# Este archivo vive en api/; los módulos del simulador (main.py,
# modelos/, actualizar_resultados.py, rutas.py, etc.) están un nivel
# arriba, en la raíz del repo. Los agregamos al sys.path para que los
# imports de abajo funcionen sin importar el directorio desde el que el
# runtime invoque este archivo.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import pandas as pd

import rutas
import data_access
import pysim_dispatch
from db.client import DatabaseConfigError, database_schema, database_url
from db.repository import cup_csv_files, league_csv_files, transaction
from posiciones_evolucion import calcular_evolucion, tamano_por_zona
from main_lpf import correr_simulacion_lpf
from actualizar_resultados import actualizar
from actualizar_resultados_lpf import actualizar as actualizar_lpf
from actualizar_resultados_copa import actualizar as actualizar_copa
from main_copa import correr_simulacion_copa
from actualizar_resultados_bmetro import actualizar as actualizar_bmetro
from main_bmetro import correr_simulacion_bmetro
from actualizar_resultados_federal import actualizar as actualizar_federal
from main_federal import correr_simulacion_federal
from actualizar_resultados_primerac import actualizar as actualizar_primerac
from main_primerac import correr_simulacion as correr_simulacion_primerac
from actualizar_resultados_brasileirao import actualizar as actualizar_brasileirao
from main_brasileirao import correr_simulacion_brasileirao
from actualizar_resultados_ligapro import actualizar as actualizar_ligapro
from main_ligapro import correr_simulacion_ligapro
from actualizar_resultados_dimayor import actualizar as actualizar_dimayor
from main_dimayor import correr_simulacion_dimayor

# Archivos de código fuente que necesita el simulador corriendo en el
# navegador (Pyodide/Web Worker, ver public/js/sim-worker.js). Se sirven
# tal cual están en el repo -- sin duplicar lógica -- vía /api/pysim-source.
PYSIM_SOURCE_FILES = [
    "rutas.py",
    "data_access.py",
    "main.py",
    "main_lpf.py",
    "pysim_dispatch.py",
    "modelos/equipo.py",
    "modelos/estadisticas.py",
    "modelos/promotion_requirements.py",
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
    "main_brasileirao.py",
    "modelos/estadisticas_brasileirao.py",
    "main_ligapro.py",
    "modelos/estadisticas_ligapro.py",
    "main_dimayor.py",
    "modelos/estadisticas_dimayor.py",
    "calcular_tabla_dimayor.py",
    "main_libertadores.py",
    "modelos/estadisticas_libertadores.py",
    "main_sudamericana.py",
    "modelos/estadisticas_sudamericana.py",
]
# El código fuente no cambia mientras el proceso está corriendo, así que se
# lee y cachea una sola vez.
_pysim_source_cache = None

N_SIMULACIONES = 500
N_SIMULACIONES_LPF = 500
# Mismos límites que usaba servidor.py: evitan que un valor mal formado
# o abusivo tumbe la función o la haga correr durante horas.
N_SIMULACIONES_MIN = 50
N_SIMULACIONES_MAX = 10000

# Límites para "simular hasta que un equipo ascienda" (/api/simular-campeon),
# iguales a los que usaba servidor.py.
MAX_INTENTOS_CAMPEON_DEFAULT = 5000
MAX_INTENTOS_CAMPEON_MIN = 100
MAX_INTENTOS_CAMPEON_MAX = 20000

app = FastAPI(title="Simulador Primera Nacional API")


def _error_response(exc: Exception) -> JSONResponse:
    if isinstance(exc, DatabaseConfigError):
        return JSONResponse(
            status_code=503,
            content={
                "error": str(exc),
                "config_error": True,
            },
        )
    return JSONResponse(status_code=500, content={"error": str(exc)})

# Sin credenciales/cookies de por medio; el dashboard puede terminar
# sirviéndose desde otro dominio/proyecto que este mismo, así que se
# permite cualquier origen.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Permite simulaciones concurrentes del mismo torneo y deja las
# actualizaciones como operación exclusiva, porque actualizan archivos
# compartidos en datos/ y public/.
LOCK_WAIT_SECONDS = 25


class ReadWriteLock:
    def __init__(self):
        self._cond = threading.Condition(threading.Lock())
        self._readers = 0
        self._writer = False
        self._writers_waiting = 0

    def acquire_read(self, timeout: float) -> bool:
        end_time = threading.TIMEOUT_MAX if timeout is None else None
        with self._cond:
            if timeout is not None:
                import time
                end_time = time.monotonic() + timeout
            while self._writer or self._writers_waiting:
                if timeout is None:
                    self._cond.wait()
                    continue
                remaining = end_time - time.monotonic()
                if remaining <= 0:
                    return False
                self._cond.wait(remaining)
            self._readers += 1
            return True

    def release_read(self) -> None:
        with self._cond:
            self._readers -= 1
            if self._readers == 0:
                self._cond.notify_all()

    def acquire_write(self, timeout: float) -> bool:
        import time
        end_time = time.monotonic() + timeout
        with self._cond:
            self._writers_waiting += 1
            try:
                while self._writer or self._readers:
                    remaining = end_time - time.monotonic()
                    if remaining <= 0:
                        return False
                    self._cond.wait(remaining)
                self._writer = True
                return True
            finally:
                self._writers_waiting -= 1

    def release_write(self) -> None:
        with self._cond:
            self._writer = False
            self._cond.notify_all()


_lock_nacional = ReadWriteLock()
_lock_lpf = ReadWriteLock()
_lock_copa = ReadWriteLock()
_lock_bmetro = ReadWriteLock()
_lock_federal = ReadWriteLock()
_lock_primerac = ReadWriteLock()
_lock_brasileirao = ReadWriteLock()
_lock_ligapro = ReadWriteLock()
_lock_dimayor = ReadWriteLock()
_lock_libertadores = ReadWriteLock()
_lock_sudamericana = ReadWriteLock()


class SimularBody(BaseModel):
    n_sims: int = N_SIMULACIONES


class SimularLPFBody(BaseModel):
    n_sims: int = N_SIMULACIONES_LPF


class SimularCopaBody(BaseModel):
    n_sims: int = N_SIMULACIONES


class SimularBmetroBody(BaseModel):
    n_sims: int = N_SIMULACIONES


class SimularFederalBody(BaseModel):
    n_sims: int = 500


class SimularPrimeraCBody(BaseModel):
    n_sims: int = 1000


class SimularBrasileiraoBody(BaseModel):
    n_sims: int = 1000


class SimularLigaProBody(BaseModel):
    n_sims: int = 1000


class SimularDimayorBody(BaseModel):
    n_sims: int = 1000


class SimularCampeonBody(BaseModel):
    equipo: str
    max_intentos: int = MAX_INTENTOS_CAMPEON_DEFAULT


class SimularLibertadoresBody(BaseModel):
    n_sims: int = N_SIMULACIONES


class SimularSudamericanaBody(BaseModel):
    n_sims: int = N_SIMULACIONES


def _clamp_n_sims(n_sims: int) -> int:
    return max(N_SIMULACIONES_MIN, min(N_SIMULACIONES_MAX, n_sims))


def _clamp_max_intentos(max_intentos: int) -> int:
    return max(MAX_INTENTOS_CAMPEON_MIN, min(MAX_INTENTOS_CAMPEON_MAX, max_intentos))


def _lock_ocupado(mensaje: str):
    return JSONResponse(
        status_code=409,
        content={
            "error": mensaje,
            "busy": True,
            "retry_after": LOCK_WAIT_SECONDS,
        },
    )


def _adquirir_lectura(lock: ReadWriteLock, mensaje: str):
    if lock.acquire_read(timeout=LOCK_WAIT_SECONDS):
        return None
    return _lock_ocupado(mensaje)


def _adquirir_escritura(lock: ReadWriteLock, mensaje: str):
    if lock.acquire_write(timeout=LOCK_WAIT_SECONDS):
        return None
    return _lock_ocupado(mensaje)


@app.get("/api/health")
def health():
    try:
        database_url()
        return {"ok": True, "storage": "supabase", "schema": database_schema()}
    except Exception as e:
        return _error_response(e)


@app.get("/api/pysim-source")
def pysim_source():
    """Devuelve el código fuente que corre la simulación (rutas.py,
    main.py, main_lpf.py, modelos/*), para que el Web Worker con Pyodide
    lo cargue en su filesystem virtual y lo importe tal cual. Así el
    navegador corre exactamente el mismo código que el backend, sin
    mantener una copia aparte."""
    global _pysim_source_cache
    if _pysim_source_cache is None:
        archivos = {}
        for nombre_relativo in PYSIM_SOURCE_FILES:
            ruta = rutas.REPO_DIR / nombre_relativo
            archivos[nombre_relativo] = ruta.read_text(encoding="utf-8")
        _pysim_source_cache = archivos
    return {"files": _pysim_source_cache}


@app.get("/api/datos-nacional")
def datos_nacional():
    """Devuelve el contenido actual de los CSV de Primera Nacional
    (resultados/fixture/tabla/goleadores), para que el simulador en el
    navegador arranque con los mismos datos que usaría el backend."""
    ocupado = _adquirir_lectura(
        _lock_nacional,
        "Hay una actualización de Primera Nacional en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return {"files": league_csv_files("nacional")}
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_nacional.release_read()


@app.get("/api/evolucion-posiciones-nacional")
def evolucion_posiciones_nacional():
    """Posición de cada equipo de Primera Nacional después de cada fecha
    ya jugada, para el gráfico "Evolución de posiciones" del frontend.
    Reconstruye la serie recorriendo los partidos jugados que ya están
    en Supabase (mismos que usa calcular_tabla.py); no simula nada."""
    ocupado = _adquirir_lectura(
        _lock_nacional,
        "Hay una actualización de Primera Nacional en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        with transaction() as repo:
            tabla_actual = repo.standing_records("nacional")
            zona_por_club = {fila["equipo"]: fila["zona"] for fila in tabla_actual}
            partidos_jugados = repo.match_records("nacional", "played")
        evolucion = calcular_evolucion(partidos_jugados, zona_por_club)
        return {
            "evolucion": evolucion,
            "zonas": tamano_por_zona(zona_por_club),
        }
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_nacional.release_read()


@app.get("/api/evolucion-posiciones-bmetro")
def evolucion_posiciones_bmetro():
    """Igual que /api/evolucion-posiciones-nacional pero para B
    Metropolitana. A diferencia de Nacional, B Metro tiene una sola
    zona ("Unica") -- calcular_evolucion() es agnóstico a eso, así que
    no hace falta ningún cambio en posiciones_evolucion.py."""
    ocupado = _adquirir_lectura(
        _lock_bmetro,
        "Hay una actualización de B Metropolitana en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        with transaction() as repo:
            tabla_actual = repo.standing_records("bmetro")
            zona_por_club = {fila["equipo"]: fila["zona"] for fila in tabla_actual}
            partidos_jugados = repo.match_records("bmetro", "played")
        evolucion = calcular_evolucion(partidos_jugados, zona_por_club)
        return {
            "evolucion": evolucion,
            "zonas": tamano_por_zona(zona_por_club),
        }
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_bmetro.release_read()


@app.get("/api/evolucion-posiciones-primerac")
def evolucion_posiciones_primerac():
    """Igual que /api/evolucion-posiciones-nacional pero para Primera C
    (2 zonas, igual formato que Nacional)."""
    ocupado = _adquirir_lectura(
        _lock_primerac,
        "Hay una actualización de Primera C en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        with transaction() as repo:
            tabla_actual = repo.standing_records("primerac")
            zona_por_club = {fila["equipo"]: fila["zona"] for fila in tabla_actual}
            partidos_jugados = repo.match_records("primerac", "played")
        evolucion = calcular_evolucion(partidos_jugados, zona_por_club)
        return {
            "evolucion": evolucion,
            "zonas": tamano_por_zona(zona_por_club),
        }
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_primerac.release_read()


@app.get("/api/evolucion-posiciones-brasileirao")
def evolucion_posiciones_brasileirao():
    """Igual que /api/evolucion-posiciones-bmetro pero para el
    Brasileirão (una sola zona, 'Unica')."""
    ocupado = _adquirir_lectura(
        _lock_brasileirao,
        "Hay una actualización del Brasileirão en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        with transaction() as repo:
            tabla_actual = repo.standing_records("brasileirao")
            zona_por_club = {fila["equipo"]: fila["zona"] for fila in tabla_actual}
            partidos_jugados = repo.match_records("brasileirao", "played")
        evolucion = calcular_evolucion(partidos_jugados, zona_por_club)
        return {
            "evolucion": evolucion,
            "zonas": tamano_por_zona(zona_por_club),
        }
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_brasileirao.release_read()


@app.get("/api/evolucion-posiciones-ligapro")
def evolucion_posiciones_ligapro():
    """Igual que /api/evolucion-posiciones-brasileirao pero para LigaPro
    Serie A. A diferencia de Brasileirão (una sola zona todo el
    campeonato), acá la zona de cada equipo puede ser "FaseInicial" o,
    una vez resuelta esa fase, alguno de los 3 grupos de Fase Final --
    calcular_evolucion()/tamano_por_zona() ya son genéricos por zona, así
    que no hace falta ningún caso especial."""
    ocupado = _adquirir_lectura(
        _lock_ligapro,
        "Hay una actualización de LigaPro en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        with transaction() as repo:
            tabla_actual = repo.standing_records("ligapro")
            zona_por_club = {fila["equipo"]: fila["zona"] for fila in tabla_actual}
            partidos_jugados = repo.match_records("ligapro", "played")
        evolucion = calcular_evolucion(partidos_jugados, zona_por_club)
        return {
            "evolucion": evolucion,
            "zonas": tamano_por_zona(zona_por_club),
        }
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_ligapro.release_read()


@app.get("/api/evolucion-posiciones-dimayor")
def evolucion_posiciones_dimayor():
    """Igual que /api/evolucion-posiciones-ligapro pero para Liga
    BetPlay Dimayor. La zona de cada equipo es "Clausura" durante la
    fase regular y, una vez resuelta, "Cuadrangular A"/"Cuadrangular B"
    para los 8 clasificados (los otros 12 quedan en "Clausura", ya
    eliminados) -- calcular_evolucion()/tamano_por_zona() son genéricos
    por zona, no hace falta ningún caso especial."""
    ocupado = _adquirir_lectura(
        _lock_dimayor,
        "Hay una actualización de Dimayor en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        with transaction() as repo:
            tabla_actual = repo.standing_records("dimayor")
            zona_por_club = {fila["equipo"]: fila["zona"] for fila in tabla_actual}
            partidos_jugados = repo.match_records("dimayor", "played")
        evolucion = calcular_evolucion(partidos_jugados, zona_por_club)
        return {
            "evolucion": evolucion,
            "zonas": tamano_por_zona(zona_por_club),
        }
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_dimayor.release_read()


@app.get("/api/datos-copa")
def datos_copa():
    """Igual que /api/datos-nacional pero con el cuadro de la Copa
    Argentina (lo único que necesita el simulador de Copa, además de los
    CSV de liga que ya bajan los otros dos endpoints)."""
    ocupado = _adquirir_lectura(
        _lock_copa,
        "Hay una actualización de Copa Argentina en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return {"files": cup_csv_files()}
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_copa.release_read()


@app.get("/api/datos-lpf")
def datos_lpf():
    """Igual que /api/datos-nacional pero con los CSV de la LPF (apertura,
    fixture, resultados, promedios históricos)."""
    ocupado = _adquirir_lectura(
        _lock_lpf,
        "Hay una actualización de Liga Profesional en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return {"files": league_csv_files("lpf")}
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_lpf.release_read()


@app.get("/api/datos-bmetro")
def datos_bmetro():
    """Igual que /api/datos-nacional pero con los CSV de B Metropolitana
    (tabla, fixture, resultados), para que el simulador en el navegador
    (Web Worker con Pyodide) arranque con los mismos datos que usaría el
    backend."""
    ocupado = _adquirir_lectura(
        _lock_bmetro,
        "Hay una actualización de B Metropolitana en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return {"files": league_csv_files("bmetro")}
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_bmetro.release_read()


@app.get("/api/datos-federal")
def datos_federal():
    """Igual que /api/datos-bmetro pero con los CSV del Federal A
    (tabla con las 4 zonas, fixture, resultados)."""
    ocupado = _adquirir_lectura(
        _lock_federal,
        "Hay una actualización de Federal A en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return {"files": league_csv_files("federal_a")}
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_federal.release_read()


@app.get("/api/datos-primerac")
def datos_primerac():
    """Igual que /api/datos-federal pero con los CSV de Primera C
    (tabla con las 2 zonas, fixture, resultados), para que el simulador
    en el navegador (Web Worker con Pyodide) arranque con los mismos
    datos que usaría el backend."""
    ocupado = _adquirir_lectura(
        _lock_primerac,
        "Hay una actualización de Primera C en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return {"files": league_csv_files("primerac")}
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_primerac.release_read()


@app.get("/api/datos-brasileirao")
def datos_brasileirao():
    """Igual que /api/datos-bmetro pero con los CSV del Brasileirão
    Série A (tabla única, sin zonas, fixture, resultados)."""
    ocupado = _adquirir_lectura(
        _lock_brasileirao,
        "Hay una actualización del Brasileirão en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return {"files": league_csv_files("brasileirao")}
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_brasileirao.release_read()


@app.get("/api/datos-ligapro")
def datos_ligapro():
    """Igual que /api/datos-brasileirao pero con los CSV de LigaPro Serie
    A (Ecuador): tabla, fixture y resultados, con la columna "zona"
    reflejando FaseInicial o, si ya se resolvió esa fase, alguno de los
    3 grupos de Fase Final."""
    ocupado = _adquirir_lectura(
        _lock_ligapro,
        "Hay una actualización de LigaPro en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return {"files": league_csv_files("ligapro")}
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_ligapro.release_read()


@app.get("/api/datos-dimayor")
def datos_dimayor():
    """Igual que /api/datos-ligapro pero con los CSV de Liga BetPlay
    Dimayor (Colombia): tabla, fixture y resultados del Torneo
    Clausura, con la columna "zona" reflejando "Clausura" o, una vez
    resuelta esa fase, "Cuadrangular A"/"Cuadrangular B"."""
    ocupado = _adquirir_lectura(
        _lock_dimayor,
        "Hay una actualización de Dimayor en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return {"files": league_csv_files("dimayor")}
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_dimayor.release_read()


def _archivos_datos_locales(nombres: list[str]) -> dict[str, str]:
    """A diferencia de las demás competencias (Supabase, vía
    league_csv_files/cup_csv_files), Libertadores y Sudamericana no
    pasan por la base: cargar_datos_libertadores()/
    cargar_datos_sudamericana() leen directo de datos/*.csv (ver
    modelos/estadisticas_libertadores.py y estadisticas_sudamericana.py).
    Esto lee esos mismos archivos tal cual para mandárselos al Web
    Worker con Pyodide."""
    archivos = {}
    for nombre in nombres:
        ruta = rutas.datos_dir() / nombre
        archivos[nombre] = ruta.read_text(encoding="utf-8")
    return archivos


@app.get("/api/datos-libertadores")
def datos_libertadores():
    """Antes este endpoint no existía: sim-worker.js ya lo pedía (junto
    con el resto de /api/datos-*) para inicializar el simulador local
    en el navegador, así que esa petición devolvía 404 y tumbaba TODO
    el Web Worker (no solo Libertadores) -- ejecutarSimulacion() caía
    siempre al backend para cualquier liga, sin aviso. Devuelve
    libertadores_cuadro.csv y libertadores_elo.csv (ver
    cargar_datos_libertadores())."""
    try:
        return {"files": _archivos_datos_locales(["libertadores_cuadro.csv", "libertadores_elo.csv"])}
    except Exception as e:
        return _error_response(e)


@app.get("/api/datos-sudamericana")
def datos_sudamericana():
    """Igual que /api/datos-libertadores pero con
    sudamericana_cuadro.csv y sudamericana_elo.csv (ver
    cargar_datos_sudamericana())."""
    try:
        return {"files": _archivos_datos_locales(["sudamericana_cuadro.csv", "sudamericana_elo.csv"])}
    except Exception as e:
        return _error_response(e)


def _estado_persistido(key: str):
    """Devuelve el último payload de simulación persistido en Supabase
    para `key` (ver data_access.simulation_output()/
    save_simulation_output()). Esto es lo que corren main.py y afines
    después de cada simulación o de /api/actualizar-*, así que refleja
    el estado real más reciente -- a diferencia de los archivos
    data*.json estáticos en public/, que son un snapshot que solo se
    regenera corriendo esos scripts a mano y nunca se reescribe en un
    deploy de Render/Vercel.

    ANTES: la página, al cargar (F5), solo pedía el data*.json estático.
    Si alguien apretaba "Actualizar desde Promiedos", el scraper y la
    simulación sí quedaban guardados en Supabase (se veía perfecto en
    el momento porque el frontend usaba la respuesta del POST
    directamente), pero al recargar la página volvía a leer el JSON
    viejo -- síntoma: "se pierde la actualización al hacer F5". Este
    endpoint es lo que el frontend debe consultar primero; el
    data*.json estático queda solo como fallback para el caso de un
    deploy nuevo contra una base recién sembrada, sin ninguna
    simulación corrida todavía.

    Devuelve siempre 200 con {"disponible": bool, "datos": ...} en vez
    de 404, para que el frontend distinga "no hay nada guardado
    todavía" (caso legítimo, cae al estático) de un error real de red
    o de servidor."""
    try:
        payload = data_access.simulation_output(key)
        return {"disponible": payload is not None, "datos": payload}
    except Exception as e:
        return _error_response(e)


@app.get("/api/estado-nacional")
def estado_nacional():
    return _estado_persistido("nacional")


@app.get("/api/estado-lpf")
def estado_lpf():
    return _estado_persistido("lpf")


@app.get("/api/estado-bmetro")
def estado_bmetro():
    return _estado_persistido("bmetro")


@app.get("/api/estado-federal")
def estado_federal():
    return _estado_persistido("federal_a")


@app.get("/api/estado-primerac")
def estado_primerac():
    return _estado_persistido("primerac")


@app.get("/api/estado-brasileirao")
def estado_brasileirao():
    return _estado_persistido("brasileirao")


@app.get("/api/estado-ligapro")
def estado_ligapro():
    return _estado_persistido("ligapro")


@app.get("/api/estado-dimayor")
def estado_dimayor():
    return _estado_persistido("dimayor")


@app.get("/api/estado-copa")
def estado_copa():
    return _estado_persistido("copa")


@app.get("/")
def root():
    return RedirectResponse(url="/index.html")


@app.post("/api/simular")
def simular(body: SimularBody = SimularBody()):
    """Corre la simulación con los datos ya presentes y devuelve el
    resultado directo en la respuesta."""
    n_sims = _clamp_n_sims(body.n_sims)

    ocupado = _adquirir_lectura(
        _lock_nacional,
        "Hay una actualización de Primera Nacional en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        datos = pysim_dispatch.simular(n_sims)
        return datos
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_nacional.release_read()


@app.post("/api/simular-campeon")
def simular_campeon(body: SimularCampeonBody):
    """Corre simular_hasta_campeon() del equipo pedido y devuelve esa
    temporada completa (tabla, final de ascenso y Reducido). No toca
    data.json: es una corrida aparte, para "ver cómo sería" el ascenso
    de un equipo puntual."""
    equipo_objetivo = body.equipo.strip()
    if not equipo_objetivo:
        return JSONResponse(status_code=400, content={"error": "Falta indicar el equipo"})

    max_intentos = _clamp_max_intentos(body.max_intentos)

    ocupado = _adquirir_lectura(
        _lock_nacional,
        "Hay una actualización de Primera Nacional en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return pysim_dispatch.simular_campeon(equipo_objetivo, max_intentos)
    except ValueError as e:
        # simular_hasta_campeon levanta ValueError si el nombre de equipo
        # no existe (con sugerencias si hay coincidencias parciales)
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_nacional.release_read()


@app.post("/api/simular-lpf")
def simular_lpf(body: SimularLPFBody = SimularLPFBody()):
    """Corre la simulación completa de la LPF (Clausura + playoffs + tabla
    anual + copas + Trofeo) con el n_sims pedido y devuelve el resultado
    directo en la respuesta."""
    n_sims = _clamp_n_sims(body.n_sims)

    ocupado = _adquirir_lectura(
        _lock_lpf,
        "Hay una actualización de Liga Profesional en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        datos = pysim_dispatch.simular_lpf(n_sims)
        return datos
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_lpf.release_read()


@app.post("/api/actualizar-lpf")
def actualizar_lpf_endpoint(body: SimularLPFBody = SimularLPFBody()):
    """Scrapea Promiedos (LPF) y, si hay partidos nuevos, actualiza los CSV
    y re-simula con correr_simulacion_lpf."""
    n_sims = _clamp_n_sims(body.n_sims)

    ocupado = _adquirir_escritura(
        _lock_lpf,
        "Hay simulaciones o una actualización de Liga Profesional en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        resultado = actualizar_lpf(n_sims=n_sims, correr_simulacion_fn=correr_simulacion_lpf, imprimir=False)
        return resultado
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_lpf.release_write()


@app.post("/api/simular-campeon-lpf")
def simular_campeon_lpf(body: SimularCampeonBody):
    """Corre simular_hasta_campeon_lpf() del equipo pedido y devuelve esa
    temporada completa (tablas del Clausura y bracket de playoffs)."""
    equipo_objetivo = body.equipo.strip()
    if not equipo_objetivo:
        return JSONResponse(status_code=400, content={"error": "Falta indicar el equipo"})

    max_intentos = _clamp_max_intentos(body.max_intentos)

    ocupado = _adquirir_lectura(
        _lock_lpf,
        "Hay una actualización de Liga Profesional en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return pysim_dispatch.simular_campeon_lpf(equipo_objetivo, max_intentos)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_lpf.release_read()


@app.post("/api/simular-copa")
def simular_copa_endpoint(body: SimularCopaBody = SimularCopaBody()):
    """Simula el cuadro de la Copa Argentina (respetando los resultados
    reales) + Monte Carlo de % por ronda, y lo devuelve en la respuesta."""
    n_sims = _clamp_n_sims(body.n_sims)

    ocupado = _adquirir_lectura(
        _lock_copa,
        "Hay una actualización de Copa Argentina en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return pysim_dispatch.simular_copa(n_sims)
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_copa.release_read()


@app.post("/api/actualizar-copa")
def actualizar_copa_endpoint(body: SimularCopaBody = SimularCopaBody()):
    """Scrapea Promiedos (Copa Argentina) y, si hay cruces nuevos, actualiza
    el cuadro y re-simula con correr_simulacion_copa."""
    n_sims = _clamp_n_sims(body.n_sims)

    ocupado = _adquirir_escritura(
        _lock_copa,
        "Hay simulaciones o una actualización de Copa Argentina en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        resultado = actualizar_copa(n_sims=n_sims, correr_simulacion_fn=correr_simulacion_copa, imprimir=False)
        return resultado
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_copa.release_write()


@app.post("/api/simular-campeon-copa")
def simular_campeon_copa_endpoint(body: SimularCampeonBody):
    """Repite el cuadro hasta que el equipo pedido salga campeón de la Copa
    y devuelve esa corrida completa (las 6 rondas del árbol)."""
    equipo_objetivo = body.equipo.strip()
    if not equipo_objetivo:
        return JSONResponse(status_code=400, content={"error": "Falta indicar el equipo"})

    max_intentos = _clamp_max_intentos(body.max_intentos)

    ocupado = _adquirir_lectura(
        _lock_copa,
        "Hay una actualización de Copa Argentina en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return pysim_dispatch.simular_campeon_copa(equipo_objetivo, max_intentos)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_copa.release_read()


@app.post("/api/simular-bmetro")
def simular_bmetro_endpoint(body: SimularBmetroBody = SimularBmetroBody()):
    """Corre la simulación completa de B Metropolitana (temporada regular
    + ascenso directo + Torneo Reducido + Monte Carlo) y devuelve el
    resultado directo en la respuesta."""
    n_sims = _clamp_n_sims(body.n_sims)

    ocupado = _adquirir_lectura(
        _lock_bmetro,
        "Hay una actualización de B Metropolitana en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        datos = pysim_dispatch.simular_bmetro(n_sims)
        return datos
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_bmetro.release_read()


@app.post("/api/simular-campeon-bmetro")
def simular_campeon_bmetro_endpoint(body: SimularCampeonBody):
    """Corre simular_hasta_ascenso_bmetro() del equipo pedido y devuelve
    esa temporada completa: tabla única y, si le tocó vía Reducido, el
    bracket (cuartos/semis/final)."""
    equipo_objetivo = body.equipo.strip()
    if not equipo_objetivo:
        return JSONResponse(status_code=400, content={"error": "Falta indicar el equipo"})

    max_intentos = _clamp_max_intentos(body.max_intentos)

    ocupado = _adquirir_lectura(
        _lock_bmetro,
        "Hay una actualización de B Metropolitana en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return pysim_dispatch.simular_campeon_bmetro(equipo_objetivo, max_intentos)
    except ValueError as e:
        # simular_hasta_ascenso_bmetro levanta ValueError si el nombre de
        # equipo no existe (con sugerencias si hay coincidencias parciales)
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_bmetro.release_read()


@app.post("/api/actualizar-bmetro")
def actualizar_bmetro_endpoint(body: SimularBmetroBody = SimularBmetroBody()):
    """Scrapea Promiedos (B Metropolitana) y, si hay partidos nuevos,
    actualiza fixture/resultados/tabla y re-simula."""
    n_sims = _clamp_n_sims(body.n_sims)

    ocupado = _adquirir_escritura(
        _lock_bmetro,
        "Hay simulaciones o una actualización de B Metropolitana en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        resultado = actualizar_bmetro(n_sims=n_sims, correr_simulacion_fn=correr_simulacion_bmetro, imprimir=False)
        return resultado
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_bmetro.release_write()


@app.post("/api/simular-federal")
def simular_federal_endpoint(body: SimularFederalBody = SimularFederalBody()):
    """Corre el Torneo Federal A completo (5 Fases + Reválida de 6
    Etapas) + Monte Carlo, y devuelve el resultado directo."""
    n_sims = max(50, min(2000, body.n_sims))

    ocupado = _adquirir_lectura(
        _lock_federal,
        "Hay una actualización de Federal A en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        datos = pysim_dispatch.simular_federal(n_sims)
        return datos
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_federal.release_read()


@app.post("/api/actualizar-federal")
def actualizar_federal_endpoint(body: SimularFederalBody = SimularFederalBody()):
    """Scrapea Promiedos (Federal A) y, si hay partidos nuevos, actualiza
    fixture/resultados/tabla y re-simula."""
    n_sims = max(50, min(2000, body.n_sims))

    ocupado = _adquirir_escritura(
        _lock_federal,
        "Hay simulaciones o una actualización de Federal A en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        resultado = actualizar_federal(n_sims=n_sims, correr_simulacion_fn=correr_simulacion_federal, imprimir=False)
        return resultado
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_federal.release_write()


@app.post("/api/simular-campeon-federal")
def simular_campeon_federal_endpoint(body: SimularCampeonBody):
    """Corre simular_hasta_ascenso_federal() del equipo pedido y
    devuelve esa corrida completa (vía directa o Reválida)."""
    equipo_objetivo = body.equipo.strip()
    if not equipo_objetivo:
        return JSONResponse(status_code=400, content={"error": "Falta indicar el equipo"})

    max_intentos = _clamp_max_intentos(body.max_intentos)

    ocupado = _adquirir_lectura(
        _lock_federal,
        "Hay una actualización de Federal A en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return pysim_dispatch.simular_campeon_federal(equipo_objetivo, max_intentos)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_federal.release_read()


@app.post("/api/simular-primerac")
def simular_primerac_endpoint(body: SimularPrimeraCBody = SimularPrimeraCBody()):
    """Corre la simulación completa de Primera C (fase de zonas + Final
    por el 1er ascenso + Torneo Reducido) + Monte Carlo, y devuelve el
    resultado directo."""
    n_sims = _clamp_n_sims(body.n_sims)

    ocupado = _adquirir_lectura(
        _lock_primerac,
        "Hay una actualización de Primera C en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        datos = pysim_dispatch.simular_primerac(n_sims)
        return datos
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_primerac.release_read()


@app.post("/api/simular-brasileirao")
def simular_brasileirao_endpoint(body: SimularBrasileiraoBody = SimularBrasileiraoBody()):
    """Corre la simulación completa del Brasileirão Série A (fase regular
    + clasificación por posición: Libertadores directa/previa,
    Sudamericana, descenso) + Monte Carlo, y devuelve el resultado
    directo. Sin Reducido: acá la tabla final ES la clasificación."""
    n_sims = _clamp_n_sims(body.n_sims)

    ocupado = _adquirir_lectura(
        _lock_brasileirao,
        "Hay una actualización del Brasileirão en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        datos = pysim_dispatch.simular_brasileirao(n_sims)
        return datos
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_brasileirao.release_read()


@app.post("/api/simular-ligapro")
def simular_ligapro_endpoint(body: SimularLigaProBody = SimularLigaProBody()):
    """Corre la simulación completa de LigaPro Serie A: Fase Inicial
    (todos contra todos, 30 fechas) seguida de la Fase Final con split
    automático en Hexagonal Campeón / Cuadrangular Sudamericana /
    Hexagonal Descenso, con arrastre de puntos, + Monte Carlo. Devuelve
    el resultado directo."""
    n_sims = _clamp_n_sims(body.n_sims)

    ocupado = _adquirir_lectura(
        _lock_ligapro,
        "Hay una actualización de LigaPro en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        datos = pysim_dispatch.simular_ligapro(n_sims)
        return datos
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_ligapro.release_read()


@app.post("/api/simular-campeon-ligapro")
def simular_campeon_ligapro_endpoint(body: SimularCampeonBody):
    """Corre simular_hasta_campeon_ligapro() del equipo pedido (Fase
    Inicial + Fase Final completas cada intento, hasta que salga 1° del
    Hexagonal Campeón) y devuelve esa temporada completa."""
    equipo_objetivo = body.equipo.strip()
    if not equipo_objetivo:
        return JSONResponse(status_code=400, content={"error": "Falta indicar el equipo"})

    max_intentos = _clamp_max_intentos(body.max_intentos)

    ocupado = _adquirir_lectura(
        _lock_ligapro,
        "Hay una actualización de LigaPro en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return pysim_dispatch.simular_campeon_ligapro(equipo_objetivo, max_intentos)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_ligapro.release_read()


@app.post("/api/simular-dimayor")
def simular_dimayor_endpoint(body: SimularDimayorBody = SimularDimayorBody()):
    """Corre la simulación completa de Liga BetPlay Dimayor (Colombia):
    Torneo Clausura (todos contra todos, 19 fechas, sin arrastre de
    puntos desde el Apertura -- esa página no simula el Apertura, ya
    terminado) seguido de los Cuadrangulares (Grupo A: 1-4-5-8, Grupo
    B: 2-3-6-7 de la fase regular) y la Final ida y vuelta con
    definición por penales si hace falta, + Monte Carlo. Devuelve el
    resultado directo, incluyendo la tabla final del Torneo Apertura
    como dato informativo (no simulado)."""
    n_sims = _clamp_n_sims(body.n_sims)

    ocupado = _adquirir_lectura(
        _lock_dimayor,
        "Hay una actualización de Dimayor en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        datos = pysim_dispatch.simular_dimayor(n_sims)
        return datos
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_dimayor.release_read()


@app.post("/api/simular-campeon-dimayor")
def simular_campeon_dimayor_endpoint(body: SimularCampeonBody):
    """Corre simular_hasta_campeon_dimayor() del equipo pedido (Clausura
    + Cuadrangulares + Final completos cada intento, hasta que salga
    campeón) y devuelve esa temporada completa."""
    equipo_objetivo = body.equipo.strip()
    if not equipo_objetivo:
        return JSONResponse(status_code=400, content={"error": "Falta indicar el equipo"})

    max_intentos = _clamp_max_intentos(body.max_intentos)

    ocupado = _adquirir_lectura(
        _lock_dimayor,
        "Hay una actualización de Dimayor en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return pysim_dispatch.simular_campeon_dimayor(equipo_objetivo, max_intentos)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_dimayor.release_read()


@app.post("/api/actualizar-primerac")
def actualizar_primerac_endpoint(body: SimularPrimeraCBody = SimularPrimeraCBody()):
    """Scrapea Promiedos (Primera C) y, si hay partidos nuevos, actualiza
    fixture/resultados/tabla y re-simula."""
    n_sims = _clamp_n_sims(body.n_sims)

    ocupado = _adquirir_escritura(
        _lock_primerac,
        "Hay simulaciones o una actualización de Primera C en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        resultado = actualizar_primerac(n_sims=n_sims, correr_simulacion_fn=correr_simulacion_primerac, imprimir=False)
        return resultado
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_primerac.release_write()


@app.post("/api/actualizar-brasileirao")
def actualizar_brasileirao_endpoint(body: SimularBrasileiraoBody = SimularBrasileiraoBody()):
    """Scrapea Promiedos (Brasileirão) y, si hay partidos nuevos,
    actualiza fixture/resultados/tabla y re-simula."""
    n_sims = _clamp_n_sims(body.n_sims)

    ocupado = _adquirir_escritura(
        _lock_brasileirao,
        "Hay simulaciones o una actualización del Brasileirão en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        resultado = actualizar_brasileirao(n_sims=n_sims, correr_simulacion_fn=correr_simulacion_brasileirao, imprimir=False)
        return resultado
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_brasileirao.release_write()


@app.post("/api/actualizar-ligapro")
def actualizar_ligapro_endpoint(body: SimularLigaProBody = SimularLigaProBody()):
    """Scrapea ligapro.ec y, si hay partidos nuevos, actualiza
    fixture/resultados/tabla y re-simula. Ver la limitación documentada
    en actualizar_resultados_ligapro.py sobre la transición Fase Inicial
    -> Fase Final (no se persiste automáticamente en este endpoint)."""
    n_sims = _clamp_n_sims(body.n_sims)

    ocupado = _adquirir_escritura(
        _lock_ligapro,
        "Hay simulaciones o una actualización de LigaPro en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        resultado = actualizar_ligapro(n_sims=n_sims, correr_simulacion_fn=correr_simulacion_ligapro, imprimir=False)
        return resultado
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_ligapro.release_write()


@app.post("/api/actualizar-dimayor")
def actualizar_dimayor_endpoint(body: SimularDimayorBody = SimularDimayorBody()):
    """Scrapea Promiedos (Liga BetPlay, id "gca") y, si hay partidos
    nuevos del Torneo Clausura, actualiza fixture/resultados/tabla y
    re-simula. La tabla final del Torneo Apertura se re-consulta en
    cada simulación (ver main_dimayor.py), no hace falta actualizarla
    acá aparte."""
    n_sims = _clamp_n_sims(body.n_sims)

    ocupado = _adquirir_escritura(
        _lock_dimayor,
        "Hay simulaciones o una actualización de Dimayor en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        resultado = actualizar_dimayor(n_sims=n_sims, correr_simulacion_fn=correr_simulacion_dimayor, imprimir=False)
        return resultado
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_dimayor.release_write()


@app.post("/api/simular-campeon-primerac")
def simular_campeon_primerac_endpoint(body: SimularCampeonBody):
    """Corre simular_hasta_campeon() (Primera C) del equipo pedido y
    devuelve esa corrida completa (vía Final directa o Reducido)."""
    equipo_objetivo = body.equipo.strip()
    if not equipo_objetivo:
        return JSONResponse(status_code=400, content={"error": "Falta indicar el equipo"})

    max_intentos = _clamp_max_intentos(body.max_intentos)

    ocupado = _adquirir_lectura(
        _lock_primerac,
        "Hay una actualización de Primera C en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return pysim_dispatch.simular_campeon_primerac(equipo_objetivo, max_intentos)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_primerac.release_read()


@app.post("/api/simular-campeon-brasileirao")
def simular_campeon_brasileirao_endpoint(body: SimularCampeonBody):
    """Corre simular_hasta_campeon_brasileirao() del equipo pedido y
    devuelve esa temporada completa hasta que el equipo salga campeón."""
    equipo_objetivo = body.equipo.strip()
    if not equipo_objetivo:
        return JSONResponse(status_code=400, content={"error": "Falta indicar el equipo"})

    max_intentos = _clamp_max_intentos(body.max_intentos)

    ocupado = _adquirir_lectura(
        _lock_brasileirao,
        "Hay una actualización del Brasileirão en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return pysim_dispatch.simular_campeon_brasileirao(equipo_objetivo, max_intentos)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_brasileirao.release_read()


@app.post("/api/simular-libertadores")
def simular_libertadores_endpoint(body: SimularLibertadoresBody = SimularLibertadoresBody()):
    """Simula el cuadro de la Copa Libertadores (desde Octavos de Final,
    ida y vuelta salvo la Final a partido único) + Monte Carlo de %
    por ronda, y lo devuelve en la respuesta."""
    n_sims = _clamp_n_sims(body.n_sims)

    ocupado = _adquirir_lectura(
        _lock_libertadores,
        "Hay una actualización de Copa Libertadores en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return pysim_dispatch.simular_libertadores(n_sims)
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_libertadores.release_read()


@app.post("/api/simular-campeon-libertadores")
def simular_campeon_libertadores_endpoint(body: SimularCampeonBody):
    """Corre simular_hasta_campeon_libertadores() del equipo pedido y
    devuelve esa corrida completa del cuadro."""
    equipo_objetivo = body.equipo.strip()
    if not equipo_objetivo:
        return JSONResponse(status_code=400, content={"error": "Falta indicar el equipo"})

    max_intentos = _clamp_max_intentos(body.max_intentos)

    ocupado = _adquirir_lectura(
        _lock_libertadores,
        "Hay una actualización de Copa Libertadores en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return pysim_dispatch.simular_campeon_libertadores(equipo_objetivo, max_intentos)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_libertadores.release_read()


@app.post("/api/simular-sudamericana")
def simular_sudamericana_endpoint(body: SimularSudamericanaBody = SimularSudamericanaBody()):
    """Simula el cuadro de la Copa Sudamericana (Playoffs de Octavos en
    adelante, ida y vuelta salvo la Final a partido único) + Monte
    Carlo de % por ronda, y lo devuelve en la respuesta. Mismo patrón
    que /api/simular-libertadores."""
    n_sims = _clamp_n_sims(body.n_sims)

    ocupado = _adquirir_lectura(
        _lock_sudamericana,
        "Hay una actualización de Copa Sudamericana en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return pysim_dispatch.simular_sudamericana(n_sims)
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_sudamericana.release_read()


@app.post("/api/simular-campeon-sudamericana")
def simular_campeon_sudamericana_endpoint(body: SimularCampeonBody):
    """Corre simular_hasta_campeon_sudamericana() del equipo pedido y
    devuelve esa corrida completa del cuadro."""
    equipo_objetivo = body.equipo.strip()
    if not equipo_objetivo:
        return JSONResponse(status_code=400, content={"error": "Falta indicar el equipo"})

    max_intentos = _clamp_max_intentos(body.max_intentos)

    ocupado = _adquirir_lectura(
        _lock_sudamericana,
        "Hay una actualización de Copa Sudamericana en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        return pysim_dispatch.simular_campeon_sudamericana(equipo_objetivo, max_intentos)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_sudamericana.release_read()


@app.post("/api/actualizar")
def actualizar_endpoint(body: SimularBody = SimularBody()):
    """Scrapea Promiedos y, si hay partidos nuevos, actualiza
    tabla/goleadores y re-simula."""
    n_sims = _clamp_n_sims(body.n_sims)

    ocupado = _adquirir_escritura(
        _lock_nacional,
        "Hay simulaciones o una actualización de Primera Nacional en curso. Esperá unos segundos y probá de nuevo.",
    )
    if ocupado:
        return ocupado
    try:
        resultado = actualizar(n_sims=n_sims, imprimir=False)
        return resultado
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_nacional.release_write()


class SimularTemporadaBody(BaseModel):
    aplicar_promocion: bool = True
    estado_anterior: dict | None = None
    numero_ronda: int = 1
    correr_libertadores: bool = True
    correr_sudamericana: bool = True


_lock_season = ReadWriteLock()
# El campeón/ascensos/descensos de cada liga salen de UNA corrida
# determinista (simular_fase_regular() y afines), no del Monte Carlo --
# confirmado leyendo main.py/main_lpf.py/etc: n_sims solo afecta las
# probabilidades estadísticas, que Modo Temporada ni siquiera muestra.
# Fijo en 1 -- "una simulación por año", no un Monte Carlo de cientos
# de repeticiones que no aporta nada acá y multiplica el tiempo de
# respuesta por 6 ligas sin necesidad.
N_SIMS_TEMPORADA = 1

# Divisiones que HistoryManager sabe generar "temporada siguiente" para
# (ver season/history_manager.py, SLUGS_CUBIERTOS) -- Copa Argentina
# queda afuera (su "fixture" es un sorteo de cuadro, no una liga por
# zonas), así que en el modo "avanzar sin persistir" siempre se relee
# de Supabase real. Federal A YA está cubierta (Primera Fase a 4
# zonas, ver history_manager.py) y por eso entra acá -- antes no
# estaba en esta tupla aunque persist_season() ya la generaba, así que
# el roster/tabla/fixture nuevos se descartaban al armar
# `proximo_estado` y la ronda siguiente volvía a leer los datos reales
# sin tocar de Supabase (síntoma: "los equipos no cambian" ronda tras
# ronda en el frontend).
_SLUGS_AVANZABLES = ("lpf", "nacional", "bmetro", "primerac", "federal_a")

_COLS_RESULTADOS = ["fecha", "jornada", "equipo_local", "equipo_visitante", "goles_local", "goles_visitante"]
_COLS_FIXTURE = ["fecha", "jornada", "equipo_local", "equipo_visitante"]
_COLS_TABLA = ["zona", "posicion", "equipo", "partidos_jugados", "ganados", "empatados", "perdidos", "gf", "gc", "dg", "puntos"]


class _RepoCapturadorEnMemoria:
    """Implementa la misma interfaz que espera HistoryManager
    (ensure_competition_season/upsert_standings/replace_matches) pero
    en vez de escribir en Supabase, guarda lo que le pasarían en un
    dict -- así se puede correr persist_season() (con toda su lógica
    real: sorteo de zonas, Apertura simulado de LPF, etc.) sin tocar la
    base para nada. Lo capturado se devuelve al frontend para que, si
    quiere seguir "avanzando" temporadas, se lo mande de vuelta en la
    próxima request en vez de que el servidor vuelva a leer Supabase."""

    def __init__(self):
        self.capturado: dict[str, dict] = {}

    def ensure_competition_season(self, slug, season=None, deactivate_others=True):
        return -1  # nunca se usa un id real de temporada

    def upsert_standings(self, slug, filas):
        self.capturado.setdefault(slug, {})["tabla"] = filas

    def replace_matches(self, slug, pending=None, played=None):
        self.capturado.setdefault(slug, {})["fixture"] = pending or []
        self.capturado.setdefault(slug, {})["resultados"] = played or []


def _df_resultados(filas: list[dict]) -> "pd.DataFrame":
    df = pd.DataFrame(filas, columns=_COLS_RESULTADOS)
    for col in ("jornada", "goles_local", "goles_visitante"):
        df[col] = df[col].astype("int64")
    return df


def _df_fixture(filas: list[dict]) -> "pd.DataFrame":
    df = pd.DataFrame(filas, columns=_COLS_FIXTURE)
    df["jornada"] = df["jornada"].astype("int64")
    return df


def _df_tabla(filas: list[dict]) -> "pd.DataFrame":
    df = pd.DataFrame(filas, columns=_COLS_TABLA)
    for col in ("posicion", "partidos_jugados", "ganados", "empatados", "perdidos", "gf", "gc", "dg", "puntos"):
        df[col] = df[col].astype("int64")
    df["zona"] = df["zona"].astype(str)
    return df


def _serializar_resultado_torneo(r) -> dict:
    """ResultadoTorneo -> dict JSON-safe. datos_crudos es literalmente
    lo que devuelve main_X.correr_simulacion() (mismo shape que ya
    consume el frontend de cada liga individual -- tablas, monte_carlo,
    etc., ya con tipos nativos de Python). ratings_finales se omite del
    JSON: es un detalle interno para el carryover de la próxima
    temporada, no algo que haga falta mostrar."""
    return {
        "campeon": r.campeon,
        "ascensos": r.ascensos,
        "descensos": r.descensos,
        "clasificados_copa": r.clasificados_copa,
        "datos": r.datos_crudos,
    }


def _correr_temporada_desde_estado(estado_anterior: dict | None, numero_ronda: int, aplicar_promocion: bool,
                                    correr_libertadores: bool = True, correr_sudamericana: bool = True):
    """Corre las 6 competencias, aplica promoción, y arma el
    `proximo_estado` (capturado en memoria, sin persistir) para poder
    seguir "avanzando" temporadas sin volver a tocar Supabase.

    Si estado_anterior es None: arranca de los datos reales
    (ClubRegistry.build_from_current_data() + data_access.league_data()
    normal), y el pool de reposición de Federal A arranca de
    POOL_ASCENSO_REGIONAL (los 10 nombres originales). Si viene con
    datos (de una respuesta anterior de este mismo endpoint):
    reconstruye el registro directo del roster provisto
    (ClubRegistry.agregar_club(), sin tocar Supabase), parchea
    data_access.league_data()/lpf_average_history_df() para que las 5
    divisiones avanzables (ver _SLUGS_AVANZABLES) lean de ahí -- Copa
    Argentina sigue leyendo la base real siempre (no cubierta) -- y
    retoma el pool de Federal A donde quedó (estado_anterior
    ["pool_regional_federal"], ver PromotionManager.aplicar() /
    "pool_regional_restante"), para que los clubes que bajaron por
    Reválida en rondas anteriores sigan disponibles para re-ascender
    más adelante en vez de perderse."""
    from season.club_registry import ClubRegistry
    from season.season_engine import SeasonEngine
    from season.promotion_manager import PromotionManager
    from season.history_manager import HistoryManager
    from season.qualification_manager import QualificationManager
    from season.copa_argentina_manager import CopaArgentinaManager
    from season.copa_argentina_sorteo import sortear_32avos
    from season.tournament_adapter import ResultadoTorneo

    if not estado_anterior:
        registry = ClubRegistry.build_from_current_data()
    else:
        registry = ClubRegistry()
        for nombre, division in estado_anterior["roster"].items():
            registry.agregar_club(nombre, division)
        # Fases 2-5 de HANDOFF_carryover_ratings.md: restaurar
        # Club.history (memoria EWMA multi-temporada, ver
        # season/rating_carryover.py) -- agregar_club() siempre crea
        # el Club con history=[] vacío (ver modelos/club.py), así que
        # sin esto la memoria se perdía en cada request (cada HTTP
        # call reconstruye el registro desde cero, no hay proceso vivo
        # entre rondas). "history_por_club" viaja en estado_anterior/
        # proximo_estado desde la ronda anterior de este mismo
        # endpoint (ver más abajo, donde se arma proximo_estado). Un
        # club sin entrada acá (roster viejo sin este campo, o recién
        # agregado) se queda con history=[] -- degrada con gracia
        # (mismo criterio que "recién llegado sin historial" en toda
        # la Fase 0).
        for nombre, entradas in (estado_anterior.get("history_por_club") or {}).items():
            club = registry.get_by_name(nombre)
            if club is not None:
                club.history = entradas

    datos_por_liga = (estado_anterior or {}).get("datos_por_liga", {})
    original_league_data = data_access.league_data
    original_promedios = data_access.lpf_average_history_df
    original_campeon_apertura = data_access.campeon_apertura_lpf
    original_playoffs_apertura = data_access.playoffs_apertura_lpf

    def _local_league_data(slug):
        if slug in datos_por_liga:
            d = datos_por_liga[slug]
            return (_df_resultados(d.get("resultados", [])), _df_fixture(d.get("fixture", [])), _df_tabla(d.get("tabla", [])))
        return original_league_data(slug)

    def _local_promedios():
        if "lpf" in datos_por_liga and "promedios" in datos_por_liga["lpf"]:
            return pd.DataFrame(datos_por_liga["lpf"]["promedios"])
        return original_promedios()

    def _local_campeon_apertura():
        if "lpf" in datos_por_liga and "campeon_apertura" in datos_por_liga["lpf"]:
            return datos_por_liga["lpf"]["campeon_apertura"]
        return original_campeon_apertura()

    def _local_playoffs_apertura():
        # Cuadro REAL de playoffs que definió el campeón capturado
        # arriba (ver "guardar_playoffs_apertura" más abajo, donde se
        # guarda como "playoffs_apertura_real" para la ronda
        # siguiente). Mismo criterio que _local_campeon_apertura: si
        # esta ronda no tiene un bracket real capturado (ronda 1, la
        # temporada real 2026, donde el Apertura no tuvo playoffs de
        # verdad), cae al comportamiento original (None salvo que se
        # haya persistido en una corrida real fuera de Modo Temporada).
        if "lpf" in datos_por_liga and "playoffs_apertura_real" in datos_por_liga["lpf"]:
            return datos_por_liga["lpf"]["playoffs_apertura_real"]
        return original_playoffs_apertura()

    # Fases 2-5 de HANDOFF_carryover_ratings.md: contexto para que
    # SeasonEngine._correr_competencias() use los motores season-only
    # (nacional/bmetro/federal_a/primerac -- LPF ya resuelve esto solo
    # con el Apertura pre-simulado de HistoryManager, no lo necesita)
    # en vez de main_X.correr_simulacion() para las divisiones que ya
    # tienen standings-en-cero de una ronda anterior de Modo Temporada.
    #
    # zonas_por_liga sale de datos_por_liga[slug]["tabla"] -- son
    # exactamente las filas que armó HistoryManager._armar_standings_
    # en_cero() la ronda pasada (cada fila trae "equipo"/"zona"), o sea
    # el sorteo de zonas YA HECHO que la Primera Fase/fase de zonas de
    # esta ronda tiene que respetar (no se vuelve a sortear acá).
    # BMetro es zona única -- no hace falta el mapeo, solo que la
    # clave "bmetro" esté presente como señal de "hay datos de esta
    # ronda para BMetro" (ver SeasonEngine._correr_competencias()).
    #
    # Si estado_anterior es None (primera ronda de una cadena, o
    # /api/season/generate-next que no pasa por acá) datos_por_liga
    # queda vacío y carryover_context también -- CopaAdapter y el
    # resto siguen 100% el camino normal, cero cambio de
    # comportamiento respecto de antes de esta Fase.
    zonas_por_liga: dict[str, dict] = {}
    for slug in ("nacional", "federal_a", "primerac"):
        tabla = datos_por_liga.get(slug, {}).get("tabla")
        if tabla:
            zonas_por_liga[slug] = {fila["equipo"]: fila["zona"] for fila in tabla}
    if "bmetro" in datos_por_liga and datos_por_liga["bmetro"].get("tabla"):
        zonas_por_liga["bmetro"] = {}

    resultados_anterior_carryover = {
        slug: ResultadoTorneo(campeon=None, ratings_finales=ratings)
        for slug, ratings in (estado_anterior or {}).get("ratings_finales_por_liga", {}).items()
    }
    carryover_context = (
        {"resultados_anterior": resultados_anterior_carryover, "zonas_por_liga": zonas_por_liga}
        if zonas_por_liga else None
    )

    # Monkeypatch acotado a esta request: se restaura pase lo que pase
    # (try/finally), así ninguna otra request concurrente queda leyendo
    # de acá. NO es seguro para uso concurrente real de este endpoint
    # puntual (dos "avanzar" a la vez podrían pisarse el parche) -- para
    # un dashboard de una sola persona explorando escenarios es un
    # trade-off razonable; si hace falta multiusuario en simultáneo para
    # ESTO en particular, hay que sacar el registro/datos de acá y
    # pasarlos por parámetro hasta el fondo de cada main_X.py (cambio
    # más grande, no hecho ahora).
    data_access.league_data = _local_league_data
    data_access.lpf_average_history_df = _local_promedios
    data_access.campeon_apertura_lpf = _local_campeon_apertura
    data_access.playoffs_apertura_lpf = _local_playoffs_apertura
    try:
        engine = SeasonEngine(registry)
        # cuadro_copa_override: el sorteo de 32avos ya armado en la ronda
        # ANTERIOR (ver más abajo, `cuadro_copa_siguiente`), guardado en
        # estado_anterior["cuadro_copa_32avos"]. Sin este parámetro,
        # CopaAdapter volvía a leer SIEMPRE el cuadro real (datos/
        # copa_argentina.csv) sin importar cuántas rondas se avanzaran --
        # este era el bug: la infraestructura del sorteo (season/
        # copa_argentina_sorteo.py) ya existía pero nunca se llamaba desde
        # acá. En None (primera ronda, todavía no hay clasificados
        # propios): CopaAdapter sigue con su comportamiento de siempre
        # (cuadro real).
        resultados = engine._correr_competencias(
            n_sims=N_SIMS_TEMPORADA,
            cuadro_copa_override=(estado_anterior or {}).get("cuadro_copa_32avos"),
            carryover=carryover_context,
        )
    finally:
        data_access.league_data = original_league_data
        data_access.lpf_average_history_df = original_promedios
        data_access.campeon_apertura_lpf = original_campeon_apertura
        data_access.playoffs_apertura_lpf = original_playoffs_apertura

    # Clasificación a copas internacionales (Libertadores/Sudamericana):
    # engine.correr_temporada() la calcula solo vía QualificationManager
    # a partir de resultados["lpf"]/["copa"] (ver season_engine.py), pero
    # acá corremos _correr_competencias() directo (no correr_temporada())
    # para poder inyectar el monkeypatch de datos_por_liga -- así que hay
    # que llamarlo a mano con el mismo criterio, si no esta ronda nunca
    # trae clasificados (el frontend quedaba mostrando siempre "Sin
    # clasificados calculados en esta corrida"). Estos son los cupos que
    # clasifica ESTA ronda -- NO se usan para poblar la Libertadores/
    # Sudamericana de esta misma ronda (ver más abajo, `plazas_
    # diferidas_ronda_anterior`): juegan recién la ronda SIGUIENTE, que
    # es cuando corresponde según el calendario real.
    clasificacion = QualificationManager().calcular(
        resultado_lpf=resultados["lpf"],
        resultado_copa=resultados["copa"],
    )

    # Fix "calendario real" de clasificación continental (ver
    # season/season_engine.py::correr_temporada(), parámetro
    # plazas_diferidas): los clasificados que juegan la Libertadores/
    # Sudamericana de ESTA ronda son los que calculó la ronda ANTERIOR
    # (guardados en estado_anterior["plazas_diferidas_continental"] --
    # mismo patrón que ya usa cuadro_copa_32avos un poco más arriba en
    # esta misma función). None en la ronda 1 (no hay "ronda anterior"
    # de Modo Temporada de la cual arrastrar clasificados) -- en ese
    # caso NO se corre Libertadores/Sudamericana con los clasificados
    # de ESTA ronda (sería el bug original), se deja constancia.
    plazas_diferidas_ronda_anterior = (estado_anterior or {}).get("plazas_diferidas_continental")

    # Etapa 9: Copa Libertadores dentro de Modo Temporada -- mismo
    # criterio que SeasonEngine.correr_temporada(correr_libertadores=...)
    # (ver season_engine.py), corrido a mano acá por la misma razón que
    # clasificacion/clasificacion_copa_argentina arriba: este endpoint
    # llama _correr_competencias() directo, no correr_temporada().
    resultado_libertadores = {}
    if correr_libertadores:
        if plazas_diferidas_ronda_anterior is None:
            resultado_libertadores = {
                "error": (
                    "Todavía no hay clasificados de una ronda anterior de Modo Temporada -- "
                    "la Copa Libertadores se habilita a partir de la ronda siguiente a esta, "
                    "con los clasificados que salgan de acá."
                )
            }
        else:
            from season.libertadores_grupos import simular_temporada_libertadores
            try:
                resultado_libertadores = simular_temporada_libertadores(
                    plazas_diferidas_ronda_anterior.get("libertadores", []),
                )
                resultado_libertadores["ronda_clasificacion"] = plazas_diferidas_ronda_anterior.get("ronda_clasificacion")
            except ValueError as e:
                resultado_libertadores = {"error": str(e)}

    # Etapa 10: Copa Sudamericana -- mismo criterio no-bloqueante, y
    # misma dependencia de correr_libertadores que SeasonEngine.
    # correr_temporada() (ver ese módulo para el porqué: Sudamericana
    # usa los terceros de zona de ESTA MISMA Libertadores).
    resultado_sudamericana = {}
    if correr_sudamericana:
        if not correr_libertadores:
            resultado_sudamericana = {"error": "correr_sudamericana necesita correr_libertadores=True."}
        elif plazas_diferidas_ronda_anterior is None:
            resultado_sudamericana = {
                "error": (
                    "Todavía no hay clasificados de una ronda anterior de Modo Temporada -- "
                    "misma razón que Libertadores arriba."
                )
            }
        elif "error" in resultado_libertadores:
            resultado_sudamericana = {"error": f"Libertadores falló esta temporada: {resultado_libertadores['error']}"}
        else:
            from season.sudamericana_temporada import simular_temporada_sudamericana
            try:
                resultado_sudamericana = simular_temporada_sudamericana(
                    plazas_diferidas_ronda_anterior.get("sudamericana", []), resultado_libertadores,
                )
                resultado_sudamericana["ronda_clasificacion"] = plazas_diferidas_ronda_anterior.get("ronda_clasificacion")
            except ValueError as e:
                resultado_sudamericana = {"error": str(e)}

    # Etapa 11: Recopa Sudamericana (campeón Libertadores vs campeón
    # Sudamericana de ESTA MISMA corrida, partido único a cancha
    # neutral) -- mismo criterio no bloqueante que arriba, corrida a
    # mano por la misma razón (este endpoint no pasa por
    # SeasonEngine.correr_temporada()). None si alguna de las dos copas
    # falló o si algún campeón/Elo no está disponible.
    resultado_recopa = None
    if correr_sudamericana and correr_libertadores and \
            "error" not in resultado_libertadores and "error" not in resultado_sudamericana:
        from season.recopa_sudamericana import simular_recopa
        resultado_recopa = simular_recopa(resultado_libertadores, resultado_sudamericana)

    # Igual criterio que arriba (ver comentario de `clasificacion`):
    # CopaArgentinaManager.calcular() vive en season_engine.correr_
    # temporada(), que acá no llamamos directo -- así que se corre a
    # mano con los mismos `resultados` de esta ronda.
    clasificacion_copa_argentina = CopaArgentinaManager().calcular(resultados)

    # Sorteo de 32avos para la Copa Argentina de la RONDA SIGUIENTE, con
    # los 64 clasificados que se acaban de calcular acá. Se guarda en
    # proximo_estado (más abajo) para que la próxima llamada a este
    # endpoint lo pase como cuadro_copa_override -- así cada ronda de
    # Modo Temporada juega una Copa Argentina nueva con los equipos que
    # clasificaron de verdad, en vez de repetir siempre el cuadro real.
    # Lista vacía si los conteos no cerraron 32+32 (avisos de
    # CopaArgentinaManager): la ronda siguiente cae de vuelta al cuadro
    # real en vez de romper.
    try:
        cuadro_copa_siguiente = sortear_32avos(clasificacion_copa_argentina)
    except ValueError:
        cuadro_copa_siguiente = []

    promocion = {}
    proximo_estado = None
    if aplicar_promocion:
        # pool_regional_federal: estado de PromotionManager._pool_restante
        # de la ronda anterior (ver season/promotion_manager.py,
        # PromotionManager.aplicar() -> resumen["pool_regional_restante"]).
        # PromotionManager no tiene memoria propia entre requests (se
        # instancia una por llamada), así que sin pasarlo acá el pool se
        # resetearía a los 10 nombres originales cada vez y el reciclado
        # de clubes que bajan de Federal A por Reválida no tendría
        # efecto. En None (primera ronda / sin estado_anterior),
        # PromotionManager arranca de POOL_ASCENSO_REGIONAL.
        pool_regional_federal = (estado_anterior or {}).get("pool_regional_federal")
        promocion = PromotionManager(pool_regional=pool_regional_federal).aplicar(
            {slug: resultados[slug] for slug in ("lpf", "nacional", "bmetro", "federal_a", "primerac")},
            registry,
            # Único por ronda -- los clubes de relleno de Federal A
            # ("Ingreso Regional {temporada}-{n}") chocarían entre sí
            # si dos rondas seguidas usaran la misma etiqueta.
            temporada_destino=f"R{numero_ronda + 1}",
        )

        repo_falso = _RepoCapturadorEnMemoria()
        campeon_apertura_capturado = {}
        playoffs_apertura_capturado = {}
        HistoryManager(
            repo=repo_falso,
            guardar_campeon_apertura=lambda campeon: campeon_apertura_capturado.__setitem__("valor", campeon),
            # Cuadro REAL de playoffs que definió ese campeón (mismo
            # patrón que la línea de arriba) -- sin esto, la ronda
            # siguiente no tiene forma de mostrar el bracket del
            # Apertura y main_lpf.py cae siempre al cuadro FICTICIO de
            # simular_playoffs_apertura() (bug real, reportado: "no
            # muestra el bracket del Apertura, solo el del Clausura").
            guardar_playoffs_apertura=lambda detalle: playoffs_apertura_capturado.__setitem__("valor", detalle),
        ).persist_season(
            registry, f"R{numero_ronda}", f"R{numero_ronda + 1}", resultados,
        )
        capturado = {slug: repo_falso.capturado[slug] for slug in _SLUGS_AVANZABLES if slug in repo_falso.capturado}
        if "lpf" in capturado and "valor" in campeon_apertura_capturado:
            # El campeón que HistoryManager acaba de simular para el
            # PRÓXIMO Apertura -- sin esto, la ronda siguiente no
            # encuentra nada en Supabase (nunca se escribió ahí) y
            # estadisticas_lpf.py cae al CAMPEON_APERTURA="Belgrano"
            # hardcodeado de la clase, sin importar quién ganó de
            # verdad en la simulación (bug real, reportado).
            capturado["lpf"]["campeon_apertura"] = campeon_apertura_capturado["valor"]
        if "lpf" in capturado and "valor" in playoffs_apertura_capturado:
            capturado["lpf"]["playoffs_apertura_real"] = playoffs_apertura_capturado["valor"]

        if "lpf" in capturado:
            # promedios_lpf.csv también tiene que "avanzar": los que ya
            # tenían historial lo mantienen, los recién ascendidos entran
            # en 0 (mismo criterio que ya documenta
            # calcular_tabla_promedios() -- "computan desde su ascenso").
            promedios_actuales = _local_promedios()
            roster_lpf_siguiente = [c.name for c in registry.get_by_division("Liga Profesional")]
            conocidos = set(promedios_actuales["equipo"])
            filas_nuevas = [
                {"equipo": eq, "puntos_historicos": 0, "partidos_historicos": 0}
                for eq in roster_lpf_siguiente if eq not in conocidos
            ]
            promedios_siguiente = pd.concat([
                promedios_actuales[promedios_actuales["equipo"].isin(roster_lpf_siguiente)],
                pd.DataFrame(filas_nuevas),
            ], ignore_index=True)
            capturado["lpf"]["promedios"] = promedios_siguiente.to_dict("records")

        proximo_estado = {
            "roster": {c.name: c.division for c in registry.all_clubs()},
            "datos_por_liga": capturado,
            "numero_ronda": numero_ronda + 1,
            "pool_regional_federal": promocion.get("pool_regional_restante", []),
            "cuadro_copa_32avos": cuadro_copa_siguiente,
            # Cupos de Libertadores/Sudamericana recién calculados en
            # ESTA ronda (`clasificacion`, arriba) -- NO se jugaron
            # ahora (ver plazas_diferidas_ronda_anterior más arriba),
            # quedan acá para que la PRÓXIMA llamada a este endpoint
            # los use como plazas_diferidas_ronda_anterior y pueble su
            # propia Libertadores/Sudamericana con ellos (edición del
            # calendario real que les corresponde). Mismo patrón que
            # cuadro_copa_32avos de la línea de arriba.
            "plazas_diferidas_continental": {
                "libertadores": clasificacion.get("libertadores", []),
                "sudamericana": clasificacion.get("sudamericana", []),
                "detalle": clasificacion.get("detalle", {}),
                "avisos": clasificacion.get("avisos", []),
                "ronda_clasificacion": numero_ronda,
            },
            # Fases 2-5 de HANDOFF_carryover_ratings.md -- ver el
            # bloque de arriba donde se restauran ambos al principio
            # de esta misma función. persist_season() (llamado un poco
            # más arriba) ya le agregó la entrada de ESTA ronda a
            # Club.history de cada club del registry -- solo hace
            # falta serializarlo para que sobreviva al viaje ida y
            # vuelta por HTTP (nada de esto se persiste en Supabase en
            # el modo shadow, ver docstring de /api/season/play).
            "history_por_club": {c.name: c.history for c in registry.all_clubs()},
            # ratings_finales de ESTA ronda para las 4 divisiones con
            # motor season-only -- la ronda SIGUIENTE los usa como
            # "resultados_anterior" (tanto para los que continúan vía
            # combinar_con_memoria() como para ascendidos/descendidos
            # cruzados, ej. Nacional necesita el ratings_finales de
            # LPF -- BUG ENCONTRADO Y CORREGIDO ACÁ, reportado por el
            # usuario: "los equipos que descienden de Primera a la B
            # casi por sentado vuelven a descender". La causa real:
            # season/carryover_engines/nacional.py YA revisaba
            # correctamente resultados_anterior["lpf"] (arreglado en
            # una vuelta anterior), pero ACÁ nunca se guardaba "lpf"
            # en ratings_finales_por_liga -- la tupla de abajo tenía
            # ("nacional", "bmetro", "federal_a", "primerac") y se
            # había olvidado "lpf" por completo. El fix de
            # armar_ratings_iniciales() de Nacional era correcto pero
            # nunca le llegaba ningún dato real: resultados_anterior.get("lpf")
            # daba siempre None, y CUALQUIER club recién descendido de
            # LPF caía al rating genérico en cada ronda, sin
            # excepción -- de ahí el patrón "casi por sentado".
            # .get() con default {} por si algún adapter (BMetro/
            # PrimeraC vía su camino NORMAL, si esta ronda no usó
            # carryover para esa división) todavía no lo llena -- ver
            # el docstring corregido de ResultadoTorneo.ratings_finales
            # en season/tournament_adapter.py.
            "ratings_finales_por_liga": {
                slug: resultados[slug].ratings_finales
                for slug in ("lpf", "nacional", "bmetro", "federal_a", "primerac")
                if slug in resultados and resultados[slug].ratings_finales
            },
        }

    return resultados, promocion, proximo_estado, clasificacion, clasificacion_copa_argentina, resultado_libertadores, resultado_sudamericana, resultado_recopa


@app.post("/api/season/play")
def season_play_endpoint(body: SimularTemporadaBody = SimularTemporadaBody()):
    """Corre las 6 competencias (LPF, Nacional, B Metro, Federal A,
    Primera C, Copa Argentina) para una temporada completa, calcula
    clasificados a copas internacionales y (por default) ascensos/
    descensos entre divisiones.

    NUNCA escribe en Supabase (a diferencia de /api/season/generate-next):
      - Sin estado_anterior: lee los datos REALES actuales (una sola
        vez, de solo lectura) y arma un ClubRegistry en memoria.
      - Con estado_anterior (la respuesta de una corrida anterior de
        este mismo endpoint, con aplicar_promocion=True): NO vuelve a
        tocar Supabase para nada -- reconstruye el roster y los
        datos de LPF/Nacional/BMetro/Primera C/Federal A directo de
        lo que vino en el body. Así se puede ir apretando "temporada
        siguiente" las veces que quieras, viendo cómo evolucionan los
        planteles, sin que nada quede persistido hasta que uses el
        otro endpoint a propósito.

    Cada respuesta trae `proximo_estado`: mandalo de vuelta como
    `estado_anterior` (con `numero_ronda` incrementado en 1) en la
    siguiente llamada para encadenar otra temporada.

    LIMITACIÓN CONOCIDA: Copa Argentina siempre lee datos reales (su
    "fixture" es un sorteo de cuadro con invitados de varias
    categorías, no una liga por zonas, HistoryManager no la cubre) --
    sus movimientos se calculan y muestran igual, pero no se
    "arrastran" de una ronda local a la siguiente. Federal A SÍ
    arrastra (Primera Fase a 4 zonas, ver history_manager.py).

    Aparte, sobre muchas rondas seguidas (probado hasta 7 sin
    problema), el reparto geográfico de descensos de Nacional hacia
    B Metro/Federal A puede ir corriendo el tamaño de esos planteles
    con el tiempo -- si en algún momento una ronda tira error de
    validación de cantidad de equipos, es ese caso límite, no un
    timeout ni un dato corrupto.
    """
    ocupado = _adquirir_escritura(
        _lock_season,
        "Ya hay una simulación de temporada corriendo. Esperá a que termine.",
    )
    if ocupado:
        return ocupado
    try:
        resultados, promocion, proximo_estado, clasificacion, clasificacion_copa_argentina, resultado_libertadores, resultado_sudamericana, resultado_recopa = _correr_temporada_desde_estado(
            body.estado_anterior, body.numero_ronda, body.aplicar_promocion, body.correr_libertadores, body.correr_sudamericana,
        )
        return {
            "generado": datetime.now().isoformat(timespec="seconds"),
            "n_simulaciones": N_SIMS_TEMPORADA,
            "numero_ronda": body.numero_ronda,
            "competencias": {slug: _serializar_resultado_torneo(r) for slug, r in resultados.items()},
            # Cupos que clasifican en ESTA ronda -- juegan la Libertadores/
            # Sudamericana de la ronda SIGUIENTE (numero_ronda + 1), no la
            # que se ve en "libertadores"/"sudamericana" acá abajo.
            "clasificacion_copas": clasificacion,
            "clasificacion_copa_argentina": clasificacion_copa_argentina,
            # Copa continental jugada EN esta ronda, poblada con los
            # clasificados de la ronda ANTERIOR (numero_ronda - 1) -- trae
            # {"error": "..."} en la ronda 1, donde todavía no hay
            # clasificados propios de Modo Temporada para arrastrar.
            "libertadores": resultado_libertadores,
            "sudamericana": resultado_sudamericana,
            "recopa": resultado_recopa,
            "promocion": promocion,
            "proximo_estado": proximo_estado,
        }
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_season.release_write()


class GenerarTemporadaBody(BaseModel):
    temporada_actual: str
    temporada_siguiente: str


@app.post("/api/season/generate-next")
def season_generate_next_endpoint(body: GenerarTemporadaBody):
    """*** OPERACIÓN QUE ESCRIBE EN SUPABASE DE VERDAD ***

    A diferencia de /api/season/play (shadow, memoria, sin persistir),
    este endpoint corre las 6 competencias, aplica ascensos/descensos
    de verdad y le pide a HistoryManager.persist_season() que:
      - active la temporada `temporada_siguiente` en Supabase para
        LPF/Nacional/BMetro/Primera C/Federal A (crea la fila si no
        existe),
      - sortee zonas, ponga standings en cero (o el Apertura simulado
        para LPF, o la Primera Fase a 4 zonas para Federal A) y arme
        el fixture ida-vuelta de esas 5 divisiones,
      - guarde en Club.history de dónde viene cada club.

    Copa Argentina NO queda cubierta (ver docstring de HistoryManager)
    -- su fixture es un sorteo de cuadro con invitados de varias
    categorías, no una liga por zonas, y queda con los datos de la
    temporada anterior hasta que se implemente su propio generador.

    `temporada_actual`/`temporada_siguiente` son OBLIGATORIOS a
    propósito (ej. "2026"/"2027") -- sin default, para que nadie dispare
    esto sin saber exactamente qué temporada está creando.

    Requiere SUPABASE_DB_URL configurada (HistoryManager() sin repo
    inyectado pega contra la base real vía db.repository.repository()).
    """
    n_sims = N_SIMS_TEMPORADA

    ocupado = _adquirir_escritura(
        _lock_season,
        "Ya hay una operación de temporada en curso. Esperá a que termine.",
    )
    if ocupado:
        return ocupado
    try:
        from season.club_registry import ClubRegistry
        from season.season_engine import SeasonEngine

        registry = ClubRegistry.build_from_current_data()
        engine = SeasonEngine(registry)

        # Fix "calendario real" de clasificación continental (ver
        # season/season_engine.py::correr_temporada(), parámetro
        # plazas_diferidas): los clasificados a Libertadores/
        # Sudamericana que juegan la temporada `temporada_actual` son
        # los que se calcularon y guardaron al cierre de la temporada
        # ANTERIOR (ver más abajo, guardar_plazas_diferidas_continental
        # con temporada_siguiente=temporada_actual de esa corrida
        # pasada) -- NUNCA los que recién calcule esta misma corrida.
        # None si no hay nada guardado (ej. primera vez que se llama a
        # este endpoint para esta cadena de temporadas): correr_
        # temporada() degrada resultado_libertadores/resultado_
        # sudamericana a {"error": "..."} en vez de usar los cupos de
        # `temporada_actual` (que corresponden a la edición del año
        # SIGUIENTE, no a esta).
        plazas_diferidas = data_access.plazas_diferidas_continental(body.temporada_actual)

        resultado = engine.correr_temporada(
            n_sims=n_sims,
            aplicar_promocion=True,
            generar_temporada_siguiente=True,
            temporada_actual=body.temporada_actual,
            temporada_siguiente=body.temporada_siguiente,
            correr_libertadores=True,
            correr_sudamericana=True,
            correr_recopa=True,
            plazas_diferidas=plazas_diferidas,
        )

        # Los cupos que ACABA de calcular esta corrida (a partir de la
        # LPF/Copa Argentina de `temporada_actual`) no se juegan ahora --
        # se guardan para que la PRÓXIMA llamada a este endpoint (la que
        # reciba temporada_actual=temporada_siguiente de ESTA corrida)
        # los use para poblar su Libertadores/Sudamericana, que es la
        # edición del calendario real que les corresponde.
        data_access.guardar_plazas_diferidas_continental(
            body.temporada_siguiente, resultado.plazas_diferidas_siguiente,
        )

        return {
            "generado": datetime.now().isoformat(timespec="seconds"),
            "n_simulaciones": n_sims,
            "temporada_actual": body.temporada_actual,
            "temporada_siguiente": body.temporada_siguiente,
            "competencias": {
                slug: _serializar_resultado_torneo(r) for slug, r in resultado.resultados.items()
            },
            # Cupos que clasificaron ESTA temporada (temporada_actual) --
            # juegan Libertadores/Sudamericana `temporada_siguiente`, NO
            # esta corrida (ver aviso en "libertadores"/"sudamericana").
            "clasificacion_copas": resultado.clasificacion,
            "clasificacion_copa_argentina": resultado.clasificacion_copa_argentina,
            # Copa continental jugada EN `temporada_actual`, poblada con
            # los clasificados que guardó la corrida ANTERIOR (la de
            # temporada_actual-1) -- error si no había nada guardado.
            "libertadores": resultado.resultado_libertadores,
            "sudamericana": resultado.resultado_sudamericana,
            "recopa": resultado.resultado_recopa,
            "promocion": resultado.promocion,
            "historia": resultado.historia,
            "elo_actualizados": resultado.elo_actualizados,
            "temporada_clasificacion_participa_en": body.temporada_siguiente,
        }
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_season.release_write()



# En Render este mismo proceso sirve el dashboard de public/. En Vercel,
# public/ se sirve como salida estática separada y no forma parte del bundle
# Python, así que el mount solo se instala cuando el directorio existe.
_public_dir = rutas.public_dir()
if _public_dir.exists():
    app.mount("/", StaticFiles(directory=str(_public_dir), html=True), name="public")
