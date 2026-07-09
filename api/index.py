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

import rutas
import pysim_dispatch
from db.client import DatabaseConfigError, database_schema, database_url
from db.repository import cup_csv_files, league_csv_files
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
]
# El código fuente no cambia mientras el proceso está corriendo, así que se
# lee y cachea una sola vez.
_pysim_source_cache = None

N_SIMULACIONES = 500
N_SIMULACIONES_LPF = 500
# Mismos límites que usaba servidor.py: evitan que un valor mal formado
# o abusivo tumbe la función o la haga correr durante horas.
N_SIMULACIONES_MIN = 50
N_SIMULACIONES_MAX = 5000

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


class SimularCampeonBody(BaseModel):
    equipo: str
    max_intentos: int = MAX_INTENTOS_CAMPEON_DEFAULT


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
    n_sims: int = 100
    aplicar_promocion: bool = True


_lock_season = ReadWriteLock()


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


@app.post("/api/season/play")
def season_play_endpoint(body: SimularTemporadaBody = SimularTemporadaBody()):
    """Corre las 6 competencias (LPF, Nacional, B Metro, Federal A,
    Primera C, Copa Argentina) para una temporada completa, calcula
    clasificados a copas internacionales y (por default) ascensos/
    descensos entre divisiones.

    aplicar_promocion=True calcula los movimientos y los devuelve para
    mostrar, pero NO persiste nada -- el ClubRegistry se arma de cero en
    esta misma request (build_from_current_data()) y vive solo en
    memoria durante la corrida, así que no hay ningún roster real que
    quede mutado. Para generar la temporada siguiente de verdad
    (persistir en Supabase) hace falta un endpoint aparte, todavía no
    construido -- ver PLAN_MODO_TEMPORADA_NACIONAL, Etapa 7."""
    n_sims = max(20, min(500, body.n_sims))

    ocupado = _adquirir_escritura(
        _lock_season,
        "Ya hay una simulación de temporada corriendo. Esperá a que termine.",
    )
    if ocupado:
        return ocupado
    try:
        from season.club_registry import ClubRegistry
        from season.season_engine import SeasonEngine

        registry = ClubRegistry.build_from_current_data()
        engine = SeasonEngine(registry)
        resultado = engine.correr_temporada(n_sims=n_sims, aplicar_promocion=body.aplicar_promocion)

        return {
            "generado": datetime.now().isoformat(timespec="seconds"),
            "n_simulaciones": n_sims,
            "competencias": {
                slug: _serializar_resultado_torneo(r) for slug, r in resultado.resultados.items()
            },
            "clasificacion_copas": resultado.clasificacion,
            "promocion": resultado.promocion,
        }
    except Exception as e:
        return _error_response(e)
    finally:
        _lock_season.release_write()


class GenerarTemporadaBody(BaseModel):
    n_sims: int = 100
    temporada_actual: str
    temporada_siguiente: str


@app.post("/api/season/generate-next")
def season_generate_next_endpoint(body: GenerarTemporadaBody):
    """*** OPERACIÓN QUE ESCRIBE EN SUPABASE DE VERDAD ***

    A diferencia de /api/season/play (shadow, memoria, sin persistir),
    este endpoint corre las 6 competencias, aplica ascensos/descensos
    de verdad y le pide a HistoryManager.persist_season() que:
      - active la temporada `temporada_siguiente` en Supabase para
        LPF/Nacional/BMetro/Primera C (crea la fila si no existe),
      - sortee zonas, ponga standings en cero (o el Apertura simulado
        para LPF) y arme el fixture ida-vuelta de esas 4 divisiones,
      - guarde en Club.history de dónde viene cada club.

    Federal A y Copa Argentina NO quedan cubiertos (ver docstring de
    HistoryManager) -- sus fixtures no son un round-robin simple y
    quedan con los datos de la temporada anterior hasta que se
    implemente su propio generador.

    `temporada_actual`/`temporada_siguiente` son OBLIGATORIOS a
    propósito (ej. "2026"/"2027") -- sin default, para que nadie dispare
    esto sin saber exactamente qué temporada está creando.

    Requiere SUPABASE_DB_URL configurada (HistoryManager() sin repo
    inyectado pega contra la base real vía db.repository.repository()).
    """
    n_sims = max(20, min(500, body.n_sims))

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
        resultado = engine.correr_temporada(
            n_sims=n_sims,
            aplicar_promocion=True,
            generar_temporada_siguiente=True,
            temporada_actual=body.temporada_actual,
            temporada_siguiente=body.temporada_siguiente,
        )

        return {
            "generado": datetime.now().isoformat(timespec="seconds"),
            "n_simulaciones": n_sims,
            "temporada_actual": body.temporada_actual,
            "temporada_siguiente": body.temporada_siguiente,
            "competencias": {
                slug: _serializar_resultado_torneo(r) for slug, r in resultado.resultados.items()
            },
            "clasificacion_copas": resultado.clasificacion,
            "promocion": resultado.promocion,
            "historia": resultado.historia,
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
