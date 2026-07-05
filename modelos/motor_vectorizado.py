# -*- coding: utf-8 -*-
"""
Prototipo aislado del núcleo vectorizado "por slot", para validarlo
estadísticamente contra el motor no vectorizado ANTES de tocar
estadisticas_federal.py. Reimplementa el mismo modelo matemático que
_simular_fase_regular_vectorizado() / simular_partido() de estadisticas.py
(Poisson + Dixon-Coles + shock Gamma), pero generalizado para que el
equipo que ocupa cada "slot" pueda variar por simulación (gather por
índice en vez de fixture fijo).
"""
import math
import numpy as np

MAX_GOLES = 8
FACTORIALES = np.array([math.factorial(i) for i in range(MAX_GOLES + 1)], dtype=np.float64)
RANGO_GOLES = np.arange(MAX_GOLES + 1)
PROMEDIO_GF_LOCAL_LIGA = 1.35
PROMEDIO_GF_VISITANTE_LIGA = 1.05
K_SHOCK_PARTIDO = 10
RHO = -0.1


def simular_partido_simple(ataque_local, defensa_visitante, ataque_visitante, defensa_local, rng):
    """Réplica de simular_partido() para un solo partido (usado en el
    loop de referencia, no vectorizado)."""
    lambda_local = ataque_local * defensa_visitante * PROMEDIO_GF_LOCAL_LIGA
    lambda_visitante = ataque_visitante * defensa_local * PROMEDIO_GF_VISITANTE_LIGA

    shock_local = rng.gamma(shape=K_SHOCK_PARTIDO, scale=1 / K_SHOCK_PARTIDO)
    shock_visitante = rng.gamma(shape=K_SHOCK_PARTIDO, scale=1 / K_SHOCK_PARTIDO)
    lambda_local *= shock_local
    lambda_visitante *= shock_visitante

    k = RANGO_GOLES
    p_x = (lambda_local ** k) * np.exp(-lambda_local) / FACTORIALES
    p_y = (lambda_visitante ** k) * np.exp(-lambda_visitante) / FACTORIALES
    probs = np.outer(p_x, p_y)
    probs[0, 0] *= 1 - lambda_local * lambda_visitante * RHO
    probs[1, 0] *= 1 + lambda_visitante * RHO
    probs[0, 1] *= 1 + lambda_local * RHO
    probs[1, 1] *= 1 - RHO

    flat = probs.ravel()
    flat = flat / flat.sum()
    idx = rng.choice(flat.size, p=flat)
    return int(idx // (MAX_GOLES + 1)), int(idx % (MAX_GOLES + 1))


def simular_partidos_vectorizado(idx_local, idx_visit, ataque_local_g, defensa_visitante_g,
                                  ataque_visitante_g, defensa_local_g, rng,
                                  max_elems_por_bloque=8_000_000):
    """Núcleo vectorizado genérico: idx_local / idx_visit son arrays
    (M, S) de ÍNDICES GLOBALES de equipo (pueden variar libremente por
    columna/simulación -- esa es la generalización sobre
    _simular_fase_regular_vectorizado, que asume fixture de identidad
    fija). *_g son los arrays de rating por equipo GLOBAL (largo
    n_equipos_global, fijos entre simulaciones).

    Devuelve (puntos_local, puntos_visit, goles_local, goles_visit),
    cada uno (M, S) -- SIN acumular todavía a totales por equipo (eso
    lo hace el caller, porque quién es "local"/"visitante" en cada
    celda depende del armado de cada fase)."""
    M, S = idx_local.shape
    n_marcadores = (MAX_GOLES + 1) ** 2

    lambda_local_base = ataque_local_g[idx_local] * defensa_visitante_g[idx_visit] * PROMEDIO_GF_LOCAL_LIGA
    lambda_visit_base = ataque_visitante_g[idx_visit] * defensa_local_g[idx_local] * PROMEDIO_GF_VISITANTE_LIGA

    goles_local = np.zeros((M, S), dtype=np.int64)
    goles_visit = np.zeros((M, S), dtype=np.int64)

    tanda = max(1, min(S, max_elems_por_bloque // max(1, M * n_marcadores)))
    k = RANGO_GOLES
    fact = FACTORIALES

    for inicio in range(0, S, tanda):
        s = min(tanda, S - inicio)
        sl = slice(inicio, inicio + s)

        shock_local = rng.gamma(shape=K_SHOCK_PARTIDO, scale=1 / K_SHOCK_PARTIDO, size=(M, s))
        shock_visit = rng.gamma(shape=K_SHOCK_PARTIDO, scale=1 / K_SHOCK_PARTIDO, size=(M, s))

        lambda_local = lambda_local_base[:, sl] * shock_local
        lambda_visit = lambda_visit_base[:, sl] * shock_visit

        p_x = (lambda_local[..., None] ** k) * np.exp(-lambda_local)[..., None] / fact
        p_y = (lambda_visit[..., None] ** k) * np.exp(-lambda_visit)[..., None] / fact
        probs = p_x[..., :, None] * p_y[..., None, :]

        probs[..., 0, 0] *= 1 - lambda_local * lambda_visit * RHO
        probs[..., 1, 0] *= 1 + lambda_visit * RHO
        probs[..., 0, 1] *= 1 + lambda_local * RHO
        probs[..., 1, 1] *= 1 - RHO

        flat = probs.reshape(M, s, n_marcadores)
        flat = flat / flat.sum(axis=-1, keepdims=True)
        cumulativo = np.cumsum(flat, axis=-1)
        r = rng.random((M, s, 1))
        idx_marcador = (cumulativo < r).sum(axis=-1)

        goles_local[:, sl] = idx_marcador // (MAX_GOLES + 1)
        goles_visit[:, sl] = idx_marcador % (MAX_GOLES + 1)

    gana_local = goles_local > goles_visit
    gana_visit = goles_local < goles_visit
    empate = ~gana_local & ~gana_visit
    puntos_local = np.where(gana_local, 3, np.where(empate, 1, 0))
    puntos_visit = np.where(gana_visit, 3, np.where(empate, 1, 0))

    return puntos_local, puntos_visit, goles_local, goles_visit
