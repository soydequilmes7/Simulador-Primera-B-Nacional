# -*- coding: utf-8 -*-
"""
pysim_dispatch.py

Punto único de entrada a las simulaciones "livianas" (no escriben a
disco) de las ligas y copas: correr_simulacion / simular_hasta_campeon
(Nacional), correr_simulacion_lpf / simular_hasta_campeon_lpf (LPF),
correr_simulacion_copa / simular_hasta_campeon_copa (Copa Argentina),
correr_simulacion_bmetro / simular_hasta_ascenso_bmetro (B Metro),
correr_simulacion_federal / simular_hasta_ascenso_federal (Federal A),
correr_simulacion_primerac / simular_hasta_ascenso_primerac (Primera C)
y correr_simulacion_libertadores / simular_hasta_campeon_libertadores
(Copa Libertadores). Arma el mismo dict de respuesta que antes armaba
cada endpoint de api/index.py, para que:

- api/index.py lo use en /api/simular, /api/simular-lpf,
  /api/simular-campeon, /api/simular-campeon-lpf, /api/simular-copa,
  /api/simular-campeon-copa, /api/simular-bmetro,
  /api/simular-campeon-bmetro, /api/simular-libertadores y
  /api/simular-campeon-libertadores.
- El Web Worker con Pyodide (public/js/sim-worker.js) llame exactamente
  las mismas funciones dentro del navegador, sin reimplementar el
  wrapping en JS.

No hace I/O propio: delega todo a main.py / main_lpf.py / main_copa.py /
main_bmetro.py, que ya leen los CSV vía rutas.datos_dir().
"""
import json
import math

from main import correr_simulacion, simular_hasta_campeon
from main_lpf import correr_simulacion_lpf, simular_hasta_campeon_lpf
from main_copa import correr_simulacion_copa, simular_hasta_campeon_copa
from main_bmetro import correr_simulacion_bmetro, simular_hasta_ascenso_bmetro
from main_federal import correr_simulacion_federal, simular_hasta_ascenso_federal
from main_primerac import correr_simulacion as correr_simulacion_primerac, simular_hasta_campeon as simular_hasta_ascenso_primerac
from main_libertadores import correr_simulacion_libertadores, simular_hasta_campeon_libertadores
from main_sudamericana import correr_simulacion_sudamericana, simular_hasta_campeon_sudamericana


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


def simular_copa(n_sims):
    return correr_simulacion_copa(imprimir=False, guardar_json=False, n_sims=n_sims)


def simular_campeon_copa(equipo_objetivo, max_intentos):
    resultado = simular_hasta_campeon_copa(equipo_objetivo, max_intentos=max_intentos, imprimir=False)
    return _envolver_hasta_campeon(resultado, equipo_objetivo, max_intentos)


def simular_campeon_lpf(equipo_objetivo, max_intentos):
    resultado = simular_hasta_campeon_lpf(equipo_objetivo, max_intentos=max_intentos, imprimir=False)
    return _envolver_hasta_campeon(resultado, equipo_objetivo, max_intentos)


def simular_bmetro(n_sims):
    return correr_simulacion_bmetro(n_sims=n_sims, imprimir=False, guardar_json=False)


def simular_campeon_bmetro(equipo_objetivo, max_intentos):
    resultado = simular_hasta_ascenso_bmetro(equipo_objetivo, max_intentos=max_intentos, imprimir=False)
    return _envolver_hasta_campeon(resultado, equipo_objetivo, max_intentos)


def simular_federal(n_sims):
    return correr_simulacion_federal(n_sims=n_sims, imprimir=False, guardar_json=False)


def simular_campeon_federal(equipo_objetivo, max_intentos):
    resultado = simular_hasta_ascenso_federal(equipo_objetivo, max_intentos=max_intentos, imprimir=False)
    return _envolver_hasta_campeon(resultado, equipo_objetivo, max_intentos)


def simular_primerac(n_sims):
    return correr_simulacion_primerac(n_sims=n_sims, imprimir=False, guardar_json=False)


def simular_campeon_primerac(equipo_objetivo, max_intentos):
    resultado = simular_hasta_ascenso_primerac(equipo_objetivo, max_intentos=max_intentos, imprimir=False)
    return _envolver_hasta_campeon(resultado, equipo_objetivo, max_intentos)


def simular_libertadores(n_sims):
    return correr_simulacion_libertadores(imprimir=False, guardar_json=False, n_sims=n_sims)


def simular_campeon_libertadores(equipo_objetivo, max_intentos):
    resultado = simular_hasta_campeon_libertadores(equipo_objetivo, max_intentos=max_intentos, imprimir=False)
    return _envolver_hasta_campeon(resultado, equipo_objetivo, max_intentos)


def simular_sudamericana(n_sims):
    return correr_simulacion_sudamericana(imprimir=False, guardar_json=False, n_sims=n_sims)


def simular_campeon_sudamericana(equipo_objetivo, max_intentos):
    resultado = simular_hasta_campeon_sudamericana(equipo_objetivo, max_intentos=max_intentos, imprimir=False)
    return _envolver_hasta_campeon(resultado, equipo_objetivo, max_intentos)


_TAREAS = {
    "simular": lambda kwargs: simular(kwargs["n_sims"]),
    "simular-lpf": lambda kwargs: simular_lpf(kwargs["n_sims"]),
    "simular-campeon": lambda kwargs: simular_campeon(kwargs["equipo"], kwargs["max_intentos"]),
    "simular-campeon-lpf": lambda kwargs: simular_campeon_lpf(kwargs["equipo"], kwargs["max_intentos"]),
    "simular-copa": lambda kwargs: simular_copa(kwargs["n_sims"]),
    "simular-campeon-copa": lambda kwargs: simular_campeon_copa(kwargs["equipo"], kwargs["max_intentos"]),
    "simular-bmetro": lambda kwargs: simular_bmetro(kwargs["n_sims"]),
    "simular-campeon-bmetro": lambda kwargs: simular_campeon_bmetro(kwargs["equipo"], kwargs["max_intentos"]),
    "simular-federal": lambda kwargs: simular_federal(kwargs["n_sims"]),
    "simular-campeon-federal": lambda kwargs: simular_campeon_federal(kwargs["equipo"], kwargs["max_intentos"]),
    "simular-primerac": lambda kwargs: simular_primerac(kwargs["n_sims"]),
    "simular-campeon-primerac": lambda kwargs: simular_campeon_primerac(kwargs["equipo"], kwargs["max_intentos"]),
    "simular-libertadores": lambda kwargs: simular_libertadores(kwargs["n_sims"]),
    "simular-campeon-libertadores": lambda kwargs: simular_campeon_libertadores(kwargs["equipo"], kwargs["max_intentos"]),
    "simular-sudamericana": lambda kwargs: simular_sudamericana(kwargs["n_sims"]),
    "simular-campeon-sudamericana": lambda kwargs: simular_campeon_sudamericana(kwargs["equipo"], kwargs["max_intentos"]),
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
    return json.dumps(_normalizar_json(resultado), ensure_ascii=False)


def _normalizar_json(valor):
    """Convierte valores no válidos en JSON estándar antes de cruzar a JS.

    Python serializa ``float('nan')`` como ``NaN`` por defecto, pero
    ``JSON.parse`` (usado por el Web Worker) lo rechaza. Las simulaciones
    pueden incluir esos valores en campos aún no definidos, por ejemplo la
    fecha de un partido pendiente. En JSON se representan como ``null``.
    """
    if isinstance(valor, float):
        return valor if math.isfinite(valor) else None
    if isinstance(valor, dict):
        return {clave: _normalizar_json(item) for clave, item in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_normalizar_json(item) for item in valor]
    return valor
