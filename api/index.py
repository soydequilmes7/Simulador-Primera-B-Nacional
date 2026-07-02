# -*- coding: utf-8 -*-
"""
api/index.py

Backend FastAPI/ASGI. Expone la misma funcionalidad que servidor.py
(simular / actualizar) y también puede servir el dashboard estático en
Render. Ver rutas.py para el manejo de datos persistentes.

Local (con uvicorn instalado):
    uvicorn api.index:app --reload
    -> http://localhost:8000/api/health

Render:
    uvicorn api.index:app --host 0.0.0.0 --port $PORT
"""
import sys
import threading
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
from main import correr_simulacion, simular_hasta_campeon
from main_lpf import correr_simulacion_lpf, simular_hasta_campeon_lpf
from actualizar_resultados import actualizar
from actualizar_resultados_lpf import actualizar as actualizar_lpf

N_SIMULACIONES = 1000
# La simulación de LPF es más pesada por corrida (playoffs + tabla anual +
# descensos dentro del Monte Carlo), por eso el default es más bajo.
N_SIMULACIONES_LPF = 300
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

# Sin credenciales/cookies de por medio; el dashboard puede terminar
# sirviéndose desde otro dominio/proyecto que este mismo, así que se
# permite cualquier origen.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Evita que se pisen dos simulaciones/actualizaciones al mismo tiempo
# DENTRO de una misma instancia tibia. No protege entre instancias
# concurrentes distintas (cada una corre en su propio proceso) -- eso
# ya requeriría coordinación externa (lock en una base de datos, etc.).
_lock_simulacion = threading.Lock()


class SimularBody(BaseModel):
    n_sims: int = N_SIMULACIONES


class SimularLPFBody(BaseModel):
    n_sims: int = N_SIMULACIONES_LPF


class SimularCampeonBody(BaseModel):
    equipo: str
    max_intentos: int = MAX_INTENTOS_CAMPEON_DEFAULT


def _clamp_n_sims(n_sims: int) -> int:
    return max(N_SIMULACIONES_MIN, min(N_SIMULACIONES_MAX, n_sims))


def _clamp_max_intentos(max_intentos: int) -> int:
    return max(MAX_INTENTOS_CAMPEON_MIN, min(MAX_INTENTOS_CAMPEON_MAX, max_intentos))


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/")
def root():
    return RedirectResponse(url="/index.html")


@app.post("/api/simular")
def simular(body: SimularBody = SimularBody()):
    """Corre la simulación con los datos ya presentes y devuelve el
    resultado directo en la respuesta."""
    n_sims = _clamp_n_sims(body.n_sims)

    if not _lock_simulacion.acquire(blocking=False):
        return JSONResponse(
            status_code=409,
            content={"error": "Ya hay una simulación corriendo, esperá a que termine"},
        )
    try:
        datos = correr_simulacion(n_sims=n_sims, imprimir=False, guardar_json=False)
        return datos
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        _lock_simulacion.release()


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

    if not _lock_simulacion.acquire(blocking=False):
        return JSONResponse(
            status_code=409,
            content={"error": "Ya hay una simulación corriendo, esperá a que termine"},
        )
    try:
        resultado = simular_hasta_campeon(equipo_objetivo, max_intentos=max_intentos, imprimir=False)
        if resultado is None:
            return {"logrado": False, "equipo": equipo_objetivo, "max_intentos": max_intentos}
        return {"logrado": True, **resultado}
    except ValueError as e:
        # simular_hasta_campeon levanta ValueError si el nombre de equipo
        # no existe (con sugerencias si hay coincidencias parciales)
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        _lock_simulacion.release()


@app.post("/api/simular-lpf")
def simular_lpf(body: SimularLPFBody = SimularLPFBody()):
    """Corre la simulación completa de la LPF (Clausura + playoffs + tabla
    anual + copas + Trofeo) con el n_sims pedido y devuelve el resultado
    directo en la respuesta."""
    n_sims = _clamp_n_sims(body.n_sims)

    if not _lock_simulacion.acquire(blocking=False):
        return JSONResponse(
            status_code=409,
            content={"error": "Ya hay una simulación corriendo, esperá a que termine"},
        )
    try:
        datos = correr_simulacion_lpf(imprimir=False, guardar_json=False, n_sims=n_sims)
        return datos
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        _lock_simulacion.release()


@app.post("/api/actualizar-lpf")
def actualizar_lpf_endpoint(body: SimularLPFBody = SimularLPFBody()):
    """Scrapea Promiedos (LPF) y, si hay partidos nuevos, actualiza los CSV
    y re-simula con correr_simulacion_lpf."""
    n_sims = _clamp_n_sims(body.n_sims)

    if not _lock_simulacion.acquire(blocking=False):
        return JSONResponse(
            status_code=409,
            content={"error": "Ya hay una simulación/actualización corriendo, esperá a que termine"},
        )
    try:
        resultado = actualizar_lpf(n_sims=n_sims, correr_simulacion_fn=correr_simulacion_lpf, imprimir=False)
        return resultado
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        _lock_simulacion.release()


@app.post("/api/simular-campeon-lpf")
def simular_campeon_lpf(body: SimularCampeonBody):
    """Corre simular_hasta_campeon_lpf() del equipo pedido y devuelve esa
    temporada completa (tablas del Clausura y bracket de playoffs)."""
    equipo_objetivo = body.equipo.strip()
    if not equipo_objetivo:
        return JSONResponse(status_code=400, content={"error": "Falta indicar el equipo"})

    max_intentos = _clamp_max_intentos(body.max_intentos)

    if not _lock_simulacion.acquire(blocking=False):
        return JSONResponse(
            status_code=409,
            content={"error": "Ya hay una simulación corriendo, esperá a que termine"},
        )
    try:
        resultado = simular_hasta_campeon_lpf(equipo_objetivo, max_intentos=max_intentos, imprimir=False)
        if resultado is None:
            return {"logrado": False, "equipo": equipo_objetivo, "max_intentos": max_intentos}
        return {"logrado": True, **resultado}
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        _lock_simulacion.release()


@app.post("/api/actualizar")
def actualizar_endpoint(body: SimularBody = SimularBody()):
    """Scrapea Promiedos y, si hay partidos nuevos, actualiza
    tabla/goleadores y re-simula."""
    n_sims = _clamp_n_sims(body.n_sims)

    if not _lock_simulacion.acquire(blocking=False):
        return JSONResponse(
            status_code=409,
            content={"error": "Ya hay una simulación/actualización corriendo, esperá a que termine"},
        )
    try:
        resultado = actualizar(n_sims=n_sims, imprimir=False)
        return resultado
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        _lock_simulacion.release()


# En Render este mismo proceso sirve el dashboard de public/. En Vercel,
# las rutas estáticas siguen siendo responsabilidad de Vercel y /api/*
# llega a esta app por rewrite.
app.mount("/", StaticFiles(directory=str(rutas.public_dir()), html=True), name="public")
