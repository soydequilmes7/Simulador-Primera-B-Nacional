# -*- coding: utf-8 -*-
"""
api/index.py

Backend como Vercel Function (FastAPI/ASGI). Expone la misma
funcionalidad que servidor.py (simular / actualizar) pero pensada para
un filesystem de solo lectura -- ver rutas.py para el detalle de qué
implica eso para /api/actualizar.

Local (con uvicorn instalado):
    uvicorn api.index:app --reload
    -> http://localhost:8000/api/health

Vercel:
    vercel.json enruta /api/* acá (ver "rewrites").
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
from pydantic import BaseModel

from main import correr_simulacion
from actualizar_resultados import actualizar

N_SIMULACIONES = 1000
# Mismos límites que usaba servidor.py: evitan que un valor mal formado
# o abusivo tumbe la función o la haga correr durante horas.
N_SIMULACIONES_MIN = 50
N_SIMULACIONES_MAX = 5000

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


def _clamp_n_sims(n_sims: int) -> int:
    return max(N_SIMULACIONES_MIN, min(N_SIMULACIONES_MAX, n_sims))


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/")
def root():
    return RedirectResponse(url="/index.html")


@app.post("/api/simular")
def simular(body: SimularBody = SimularBody()):
    """Corre la simulación con los datos ya presentes en el deploy y
    devuelve el resultado directo en la respuesta (no se persiste nada:
    ver guardar_json=False)."""
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


@app.post("/api/actualizar")
def actualizar_endpoint(body: SimularBody = SimularBody()):
    """Scrapea Promiedos y, si hay partidos nuevos, actualiza
    tabla/goleadores y re-simula. Ver rutas.py: en Vercel esos cambios
    quedan en /tmp (viven mientras la instancia esté tibia), no se
    escriben de vuelta al deploy."""
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
