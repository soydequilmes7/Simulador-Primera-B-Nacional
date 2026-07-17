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


def _muestrear_marginal(lam, rng, k=RANGO_GOLES, fact=FACTORIALES):
    """Muestrea una Poisson truncada a [0, MAX_GOLES] por función de
    distribución acumulada (mismo método que el resto del código: cumsum
    + comparación contra un uniforme). lam puede tener cualquier shape;
    devuelve un array de la misma shape con valores enteros 0..MAX_GOLES."""
    p = (lam[..., None] ** k) * np.exp(-lam)[..., None] / fact
    p /= p.sum(axis=-1, keepdims=True)
    np.cumsum(p, axis=-1, out=p)
    r = rng.random(lam.shape + (1,))
    return (p < r).sum(axis=-1)


def muestrear_marcador_dixon_coles(lambda_local, lambda_visit, rng, max_rondas=30):
    """Muestrea marcadores (goles_local, goles_visit) de la distribución
    EXACTA de Dixon-Coles sin armar el tensor conjunto (M,S,9,9) de 81
    celdas por partido -- baja la memoria de O(n*81) a O(n*9) sampleando
    las marginales de Poisson por separado (independientes) y corrigiendo
    con rejection sampling solo donde la corrección de Dixon-Coles pega:
    las 4 celdas (0,0), (1,0), (0,1) y (1,1).

    La corrección multiplica la celda (x,y) por tau(x,y):
        tau(0,0) = 1 - lambda_local*lambda_visit*RHO
        tau(1,0) = 1 + lambda_visit*RHO
        tau(0,1) = 1 + lambda_local*RHO
        tau(1,1) = 1 - RHO
        tau(x,y) = 1                              en cualquier otra celda

    Muestreando (x,y) de las marginales independientes y aceptando cada
    candidato con probabilidad tau(x,y)/tau_max (tau_max = cota superior
    de tau para ese lambda_local/lambda_visit), lo que queda es EXACTAMENTE
    una muestra de la distribución conjunta corregida -- no es una
    aproximación, es rejection sampling estándar. Con RHO=-0.1 la tasa de
    aceptación ronda 85-95%, así que en promedio hacen falta pocas rondas.

    Optimización sobre la primera versión: en vez de re-sortear TODOS los
    elementos en cada ronda, solo se re-sortean los que todavía no
    aceptaron (arrays de "pendientes" que se van achicando ronda a ronda),
    evitando recalcular tau/marginales para elementos ya resueltos. Si
    después de max_rondas todavía queda algún elemento pendiente (muy
    poco probable dado que tau_max ronda 1.1), se resuelve el resto con
    el método exacto O(81) de siempre -- pero aplicado solo a ese resto
    ínfimo, no a la grilla completa, así que no pesa en la práctica."""
    shape = lambda_local.shape
    n = lambda_local.size
    ll_flat = lambda_local.reshape(-1)
    lv_flat = lambda_visit.reshape(-1)

    goles_local = np.empty(n, dtype=np.int64)
    goles_visit = np.empty(n, dtype=np.int64)

    pendientes = np.arange(n)

    for _ in range(max_rondas):
        if pendientes.size == 0:
            break

        ll_p = ll_flat[pendientes]
        lv_p = lv_flat[pendientes]

        x_p = _muestrear_marginal(ll_p, rng)
        y_p = _muestrear_marginal(lv_p, rng)

        tau = np.ones(pendientes.size, dtype=np.float64)
        m00 = (x_p == 0) & (y_p == 0)
        m10 = (x_p == 1) & (y_p == 0)
        m01 = (x_p == 0) & (y_p == 1)
        m11 = (x_p == 1) & (y_p == 1)
        tau[m00] = 1 - ll_p[m00] * lv_p[m00] * RHO
        tau[m10] = 1 + lv_p[m10] * RHO
        tau[m01] = 1 + ll_p[m01] * RHO
        tau[m11] = 1 - RHO

        # Cota superior de tau para este lambda_local/lambda_visit: el
        # único candidato a superar 1-RHO (constante, celda (1,1)) es la
        # celda (0,0), que crece con lambda_local*lambda_visit. Las
        # celdas (1,0)/(0,1) quedan siempre <=1 con RHO<0, así que no
        # hace falta considerarlas acá.
        tau_max = np.maximum(1 - RHO, 1 - ll_p * lv_p * RHO)

        r = rng.random(pendientes.size)
        aceptado = r < (tau / tau_max)

        idx_aceptado = pendientes[aceptado]
        goles_local[idx_aceptado] = x_p[aceptado]
        goles_visit[idx_aceptado] = y_p[aceptado]

        pendientes = pendientes[~aceptado]

    if pendientes.size > 0:
        # Fallback exacto (tensor de 81 celdas) para el puñado de
        # elementos que no aceptaron en max_rondas rondas -- barato
        # porque pendientes.size es ínfimo comparado con n.
        ll_p = ll_flat[pendientes]
        lv_p = lv_flat[pendientes]
        k = RANGO_GOLES
        p_x = (ll_p[..., None] ** k) * np.exp(-ll_p)[..., None] / FACTORIALES
        p_y = (lv_p[..., None] ** k) * np.exp(-lv_p)[..., None] / FACTORIALES
        probs = p_x[..., :, None] * p_y[..., None, :]
        probs[..., 0, 0] *= 1 - ll_p * lv_p * RHO
        probs[..., 1, 0] *= 1 + lv_p * RHO
        probs[..., 0, 1] *= 1 + ll_p * RHO
        probs[..., 1, 1] *= 1 - RHO

        flat = probs.reshape(pendientes.size, (MAX_GOLES + 1) ** 2)
        flat /= flat.sum(axis=-1, keepdims=True)
        np.cumsum(flat, axis=-1, out=flat)
        r = rng.random((pendientes.size, 1))
        idx_marcador = (flat < r).sum(axis=-1)

        goles_local[pendientes] = idx_marcador // (MAX_GOLES + 1)
        goles_visit[pendientes] = idx_marcador % (MAX_GOLES + 1)

    return goles_local.reshape(shape), goles_visit.reshape(shape)


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

    for inicio in range(0, S, tanda):
        s = min(tanda, S - inicio)
        sl = slice(inicio, inicio + s)

        shock_local = rng.gamma(shape=K_SHOCK_PARTIDO, scale=1 / K_SHOCK_PARTIDO, size=(M, s))
        shock_visit = rng.gamma(shape=K_SHOCK_PARTIDO, scale=1 / K_SHOCK_PARTIDO, size=(M, s))

        lambda_local = lambda_local_base[:, sl] * shock_local
        lambda_visit = lambda_visit_base[:, sl] * shock_visit

        # Muestreo marginal + rejection sampling exacto (ver
        # muestrear_marcador_dixon_coles más arriba): reemplaza el tensor
        # conjunto (M,s,9,9) de 81 celdas por marginales O(9)
        # independientes y una corrección puntual solo en las 4 celdas
        # que Dixon-Coles afecta, bajando el pico de memoria de la tanda
        # ~3.65x a costa de un ~1.7x en tiempo (loop de rejection).
        gl, gv = muestrear_marcador_dixon_coles(lambda_local, lambda_visit, rng)
        goles_local[:, sl] = gl
        goles_visit[:, sl] = gv

    gana_local = goles_local > goles_visit
    gana_visit = goles_local < goles_visit
    empate = ~gana_local & ~gana_visit
    puntos_local = np.where(gana_local, 3, np.where(empate, 1, 0))
    puntos_visit = np.where(gana_visit, 3, np.where(empate, 1, 0))

    return puntos_local, puntos_visit, goles_local, goles_visit
