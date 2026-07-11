# -*- coding: utf-8 -*-
"""
season/validar_etapa3.py

Validación de Etapa 3 (RatingCarryoverPolicy). Por diseño, esta etapa
se prueba con datos MOCKEADOS -- sin tocar ClubRegistry real todavía
(ver PLAN_MODO_TEMPORADA_NACIONAL.txt, sección 6, Etapa 3).

La función _manual_carryover() de acá abajo reimplementa la fórmula de
forma INDEPENDIENTE (no importa la lógica interna de
RatingCarryoverPolicy, solo sus constantes públicas) para poder
comparar contra la salida real de la política, mismo espíritu que los
validar_etapa2_*.py que comparan el adaptador contra un mapeo manual.

Correrlo desde la raíz del proyecto:

    python -m season.validar_etapa3
"""
from season.rating_carryover import (
    RatingCarryoverPolicy,
    NIVEL_DIVISION,
    N_CARRYOVER,
    K_REGRESION,
    ATAQUE_GENERICO,
    DEFENSA_GENERICO,
    CAMPOS_RATING,
    N_TEMPORADAS_HANDICAP,
)

# Fase 0 (HANDOFF_carryover_ratings.md): rating_para_recien_llegado()
# aplica el handicap de adaptación de la temporada 1 en destino
# (factor fijo, ver _factor_handicap(0) en rating_carryover.py) --
# esta reimplementación manual se actualiza acá para seguir siendo un
# chequeo independiente real, no una copia del código interno.
#
# ACTUALIZADO (reportado por el usuario: "al que desciende le cuesta
# mucho volver a pelear, en la vida real no pasa así"): el handicap
# ahora es ASIMÉTRICO -- solo se aplica en un ASCENSO real (subir de
# NIVEL_DIVISION), NO en un descenso ni en un movimiento lateral (ver
# _es_ascenso() en rating_carryover.py).
FACTOR_HANDICAP_TEMPORADA_1 = 1 / (N_TEMPORADAS_HANDICAP + 1)


def _manual_carryover(ratings_origen: dict, division_origen: str, division_destino: str) -> dict:
    """Reimplementación independiente de la fórmula, para comparar
    contra RatingCarryoverPolicy sin depender de su código interno."""
    factor = NIVEL_DIVISION[division_origen] / NIVEL_DIVISION[division_destino]
    es_ascenso = NIVEL_DIVISION[division_destino] > NIVEL_DIVISION[division_origen]
    if es_ascenso:
        factor *= FACTOR_HANDICAP_TEMPORADA_1
    resultado = {}
    for campo in CAMPOS_RATING:
        valor_origen = ratings_origen[campo]
        valor_ajustado = 1.0 + (valor_origen - 1.0) * factor
        resultado[campo] = round(
            (N_CARRYOVER * valor_ajustado + K_REGRESION * 1.0) / (N_CARRYOVER + K_REGRESION), 3
        )
    return resultado


def _comparar(nombre_caso: str, esperado: dict, obtenido: dict, tolerancia=1e-9) -> list:
    errores = []
    for campo in CAMPOS_RATING:
        if abs(esperado[campo] - obtenido[campo]) > tolerancia:
            errores.append(
                f"[{nombre_caso}] {campo}: esperado {esperado[campo]}, obtenido {obtenido[campo]}"
            )
    return errores


def main():
    print("=" * 70)
    print("VALIDACIÓN ETAPA 3 -- RatingCarryoverPolicy (datos mockeados)")
    print("=" * 70)

    politica = RatingCarryoverPolicy()
    errores = []

    # ------------------------------------------------------------
    # Caso 1: sin historial en ninguna división -> genérico
    # ------------------------------------------------------------
    print("\n[Caso 1] Club sin historial en ninguna división")
    obtenido = politica.rating_para_recien_llegado(None, None, "primerac")
    esperado = {
        "ataque_local": ATAQUE_GENERICO, "ataque_visitante": ATAQUE_GENERICO,
        "defensa_local": DEFENSA_GENERICO, "defensa_visitante": DEFENSA_GENERICO,
    }
    print(f"  esperado:  {esperado}")
    print(f"  obtenido:  {obtenido}")
    errores += _comparar("sin historial", esperado, obtenido)

    # ------------------------------------------------------------
    # Caso 2: mismo nivel de división (federal_a -> bmetro, ambas
    # NIVEL_DIVISION=0.65 hoy) -> factor=1.0, la única transformación
    # que debería notarse es la regresión hacia el promedio, sin
    # compresión/amplificación por nivel.
    # ------------------------------------------------------------
    print("\n[Caso 2] Mismo nivel de división (federal_a -> bmetro)")
    ratings_origen = {
        "ataque_local": 1.30, "ataque_visitante": 0.85,
        "defensa_local": 1.10, "defensa_visitante": 0.95,
    }
    obtenido = politica.rating_para_recien_llegado(ratings_origen, "federal_a", "bmetro")
    esperado = _manual_carryover(ratings_origen, "federal_a", "bmetro")
    print(f"  ratings_origen: {ratings_origen}")
    print(f"  esperado:  {esperado}")
    print(f"  obtenido:  {obtenido}")
    errores += _comparar("mismo nivel", esperado, obtenido)
    # Chequeo adicional (Fase 0, ACTUALIZADO por la asimetría
    # ascenso/descenso): un movimiento LATERAL (mismo NIVEL_DIVISION)
    # no es un ascenso, así que YA NO lleva handicap -- vuelve a ser
    # la mitad de camino simple entre el valor de origen y 1.0
    # (regresión 50/50, N_CARRYOVER=K_REGRESION=12).
    for campo in CAMPOS_RATING:
        mitad = round((ratings_origen[campo] + 1.0) / 2, 3)
        if abs(obtenido[campo] - mitad) > 1e-9:
            errores.append(
                f"[mismo nivel, chequeo 50/50 sin handicap] {campo}: esperaba {mitad} (mitad de camino), "
                f"dio {obtenido[campo]}"
            )

    # ------------------------------------------------------------
    # Caso 3: ascenso a división más fuerte (nacional -> lpf) ->
    # la distancia al promedio debería COMPRIMIRSE.
    # ------------------------------------------------------------
    print("\n[Caso 3] Ascenso a división más fuerte (nacional -> lpf)")
    ratings_origen = {
        "ataque_local": 1.20, "ataque_visitante": 1.10,
        "defensa_local": 0.90, "defensa_visitante": 0.95,
    }
    obtenido = politica.rating_para_recien_llegado(ratings_origen, "nacional", "lpf")
    esperado = _manual_carryover(ratings_origen, "nacional", "lpf")
    print(f"  ratings_origen: {ratings_origen}")
    print(f"  esperado:  {esperado}")
    print(f"  obtenido:  {obtenido}")
    errores += _comparar("ascenso a división más fuerte", esperado, obtenido)
    if not (abs(obtenido["ataque_local"] - 1.0) < abs(ratings_origen["ataque_local"] - 1.0)):
        errores.append(
            "[ascenso] se esperaba que ataque_local se acercara más a 1.0 que el original "
            "(compresión al subir de nivel), pero no fue así"
        )

    # ------------------------------------------------------------
    # Caso 4: descenso a división más débil (lpf -> nacional) ->
    # la distancia al promedio debería AMPLIFICARSE.
    # ------------------------------------------------------------
    print("\n[Caso 4] Descenso a división más débil (lpf -> nacional)")
    ratings_origen = {
        "ataque_local": 1.20, "ataque_visitante": 1.10,
        "defensa_local": 0.90, "defensa_visitante": 0.95,
    }
    obtenido = politica.rating_para_recien_llegado(ratings_origen, "lpf", "nacional")
    esperado = _manual_carryover(ratings_origen, "lpf", "nacional")
    print(f"  ratings_origen: {ratings_origen}")
    print(f"  esperado:  {esperado}")
    print(f"  obtenido:  {obtenido}")
    errores += _comparar("descenso a división más débil", esperado, obtenido)
    dist_original = abs(ratings_origen["ataque_local"] - 1.0)
    dist_ajustada_pre_regresion = abs(1.0 + (ratings_origen["ataque_local"] - 1.0)
                                       * (NIVEL_DIVISION["lpf"] / NIVEL_DIVISION["nacional"]) - 1.0)
    if not (dist_ajustada_pre_regresion > dist_original):
        errores.append(
            "[descenso] se esperaba que la distancia a 1.0 se amplificara antes de la "
            "regresión (bajar de nivel), pero no fue así"
        )

    # ------------------------------------------------------------
    # Caso 5: errores esperados (claves faltantes / división inválida)
    # ------------------------------------------------------------
    print("\n[Caso 5] Manejo de errores")
    try:
        politica.rating_para_recien_llegado({"ataque_local": 1.0}, "nacional", "lpf")
        errores.append("[errores] esperaba ValueError por claves faltantes en ratings_origen, no se lanzó")
    except ValueError as e:
        print(f"  OK -- claves faltantes levantó ValueError: {e}")

    try:
        politica.rating_para_recien_llegado(
            {c: 1.0 for c in CAMPOS_RATING}, "nacional", "division_inexistente"
        )
        errores.append("[errores] esperaba ValueError por división de destino inválida, no se lanzó")
    except ValueError as e:
        print(f"  OK -- división de destino inválida levantó ValueError: {e}")

    try:
        politica.rating_para_recien_llegado(
            {c: 1.0 for c in CAMPOS_RATING}, "division_inexistente", "lpf"
        )
        errores.append("[errores] esperaba ValueError por división de origen inválida, no se lanzó")
    except ValueError as e:
        print(f"  OK -- división de origen inválida levantó ValueError: {e}")

    print("\n" + "=" * 70)
    if errores:
        print("❌ RatingCarryoverPolicy NO pasó todos los chequeos:")
        for e in errores:
            print(f"   - {e}")
    else:
        print("✅ RatingCarryoverPolicy pasó todos los chequeos con datos mockeados.")
        print("   Recordatorio: NIVEL_DIVISION es una estimación manual (ver docstring de")
        print("   season/rating_carryover.py), no calibrada con datos reales todavía.")
    print("=" * 70)


if __name__ == "__main__":
    main()
