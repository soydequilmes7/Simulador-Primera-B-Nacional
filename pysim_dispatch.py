# -*- coding: utf-8 -*-
"""
pysim_dispatch.py

Punto único de entrada a las 4 simulaciones "livianas" (no escriben a
disco): correr_simulacion, correr_simulacion_lpf, simular_hasta_campeon y
simular_hasta_campeon_lpf. Arma el mismo dict de respuesta que antes
armaba cada endpoint de api/index.py, para que:

- api/index.py lo use en /api/simular, /api/simular-lpf,
  /api/simular-campeon y /api/simular-campeon-lpf.
- El Web Worker con Pyodide (public/js/sim-worker.js) llame exactamente
  las mismas funciones dentro del navegador, sin reimplementar el
  wrapping en JS.

No hace I/O propio: delega todo a main.py / main_lpf.py, que ya leen los
CSV vía rutas.datos_dir().
"""
import json

from main import correr_simulacion, simular_hasta_campeon
from main_lpf import correr_simulacion_lpf, simular_hasta_campeon_lpf


def simular(n_sims):
    return correr_simulacion(n_sims=n_sims, imprimir=False, guardar_json=False)


def simular_lpf(n_sims):
    return correr_simulacion_lpf(imprimir=False, guardar_json=False, n_sims=n_sims)


def _envolver_hasta_campeon(resultado, equipo_objetivo, max_intentos):
    if resultado is None:
        return {"logrado": False, "equipo": equipo_objetivo, "max_intentos": max_intentos}
    return {"logrado": True, **resultado}


def simular_campeon(equipo_objetivo, max_intentos):
    resultado = simular_hasta_campeon(equipo_objetivo, max_intentos=max_intentos, imprimir=False)
    return _envolver_hasta_campeon(resultado, equipo_objetivo, max_intentos)


def simular_campeon_lpf(equipo_objetivo, max_intentos):
    resultado = simular_hasta_campeon_lpf(equipo_objetivo, max_intentos=max_intentos, imprimir=False)
    return _envolver_hasta_campeon(resultado, equipo_objetivo, max_intentos)


_TAREAS = {
    "simular": lambda kwargs: simular(kwargs["n_sims"]),
    "simular-lpf": lambda kwargs: simular_lpf(kwargs["n_sims"]),
    "simular-campeon": lambda kwargs: simular_campeon(kwargs["equipo"], kwargs["max_intentos"]),
    "simular-campeon-lpf": lambda kwargs: simular_campeon_lpf(kwargs["equipo"], kwargs["max_intentos"]),
}


def ejecutar_tarea(tarea, **kwargs):
    """Dispatcha una tarea por nombre y devuelve {"ok": True, "data": ...}
    o {"ok": False, "status": int, "error": str} -- nunca deja escapar la
    excepción. La usa el Web Worker con Pyodide (public/js/sim-worker.js)
    para no tener que parsear tracebacks de Python del lado de JS: los
    ValueError (equipo inexistente) se traducen a status 400, igual que
    hacen los endpoints de api/index.py."""
    fn = _TAREAS.get(tarea)
    if fn is None:
        return {"ok": False, "status": 400, "error": f"Tarea desconocida: {tarea}"}
    try:
        return {"ok": True, "data": fn(kwargs)}
    except ValueError as e:
        return {"ok": False, "status": 400, "error": str(e)}
    except Exception as e:
        return {"ok": False, "status": 500, "error": str(e)}


def ejecutar_tarea_json(tarea, kwargs_json):
    """Igual que ejecutar_tarea, pero recibe/devuelve JSON -- así el
    worker llama esto desde JS pasando strings nomás, sin tener que armar
    un PyProxy con los kwargs."""
    kwargs = json.loads(kwargs_json) if kwargs_json else {}
    resultado = ejecutar_tarea(tarea, **kwargs)
    return json.dumps(resultado, ensure_ascii=False)
