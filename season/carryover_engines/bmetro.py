# -*- coding: utf-8 -*-
"""
season/carryover_engines/bmetro.py

Motor season-only para B Metropolitana (Fase 3 de
HANDOFF_carryover_ratings.md). Mismo problema y mismo patrón que
season/carryover_engines/nacional.py (leer su docstring primero) --
acá solo se documentan las diferencias reales de B Metro:

  - Zona ÚNICA ("Unica", mismo truco que ya usa
    modelos/estadisticas_bmetro.py para reusar el motor de Nacional
    sin reescribir simular_fase_regular()/_armar_tabla_final()).
  - Sin "final cruzada": el puntero de la tabla asciende directo
    (EstadisticasBMetro.obtener_puntero(), heredado sin tocar).
  - jugar_reducido_bmetro() (heredado sin tocar) en vez de
    jugar_reducido() -- octogonal de posiciones 2..REDUCIDO_N=9, TODAS
    las rondas a ida y vuelta (a diferencia de Nacional).
  - DESCENSOS_N=2: últimos 2 de la tabla única.

ORÍGENES DE ASCENSO A B METRO (confirmado leyendo
season/promotion_manager.py real, sección "3) {bmetro, federal_a} ->
Nacional" NO aplica acá -- son las secciones "2) Nacional ->
{bmetro, federal_a}, por afiliación geográfica" y "4) bmetro <->
primerac"):
  - Descendidos de Nacional (según afiliación geográfica -- algunos
    van a Federal A en vez de acá, ver geografia_clubes.py).
  - Ascendidos de Primera C.
Por eso armar_ratings_iniciales() acá busca en DOS fuentes posibles
(a diferencia de Nacional, que busca en bmetro/federal_a).

RECALIBRADO DE PROMEDIO_GF_LOCAL_LIGA/VISITANTE_LIGA -- DECISIÓN
DOCUMENTADA (punto pendiente del HANDOFF, Fase 3): cargar_datos_bmetro()
recalibra estas constantes con el promedio REAL de goles de B Metro
(~1.06/0.94, división de menos goles que Nacional) a partir de
self.resultados -- pero acá no hay self.resultados (temporada
arrancando en cero, sin partidos reales). cargar_datos_bmetro() ya
documenta que en ese caso ("Sin partidos jugados todavía") se queda
con el default HEREDADO de la clase base (1.35/1.05, calibrado para
Nacional) -- que sería inconsistente para B Metro (demasiados goles
simulados). Achá, en vez de heredar ese default de Nacional, se usa
la aproximación de B Metro que YA está documentada en el comentario
de cargar_datos_bmetro() (líneas ~76-85 de estadisticas_bmetro.py) --
mismo criterio que NIVEL_DIVISION en rating_carryover.py: valor de
arranque razonable, no recalibrado dinámicamente todavía. Una mejora
futura sería encadenar el último recalibrado real de la temporada
anterior a través de ResultadoTorneo -- no se hizo acá para no
agregar un campo nuevo a ese shape sin acuerdo explícito (afectaría
a los otros 5 adaptadores).
"""
from __future__ import annotations

import pandas as pd

from fixture_generator import generar_fixture_ida_vuelta
from modelos.estadisticas_bmetro import EstadisticasBMetro
from season.rating_carryover import RatingCarryoverPolicy, combinar_con_memoria
from season.tournament_adapter import ResultadoTorneo

K_REGRESION = 12

# Ver docstring del módulo -- aproximación documentada en
# modelos/estadisticas_bmetro.py::cargar_datos_bmetro(), no calibrada
# dinámicamente en este motor season-only todavía.
PROMEDIO_GF_LOCAL_LIGA_BMETRO = 1.06
PROMEDIO_GF_VISITANTE_LIGA_BMETRO = 0.94


def armar_ratings_iniciales(club_registry, resultados_anterior: dict, roster_siguiente: list[str]) -> dict:
    """Análogo a carryover_engines.nacional.armar_ratings_iniciales(),
    con los orígenes de ascenso reales de B Metro (ver docstring del
    módulo): continúan en bmetro -> combinar_con_memoria(); si no,
    vienen de un descenso de Nacional o de un ascenso de Primera C."""
    resultado_bmetro_anterior = resultados_anterior.get("bmetro") if resultados_anterior else None
    ratings_bmetro_anterior = (
        resultado_bmetro_anterior.ratings_finales if resultado_bmetro_anterior is not None else {}
    )
    resultado_nacional = resultados_anterior.get("nacional") if resultados_anterior else None
    ratings_nacional = resultado_nacional.ratings_finales if resultado_nacional is not None else {}
    resultado_primerac = resultados_anterior.get("primerac") if resultados_anterior else None
    ratings_primerac = resultado_primerac.ratings_finales if resultado_primerac is not None else {}

    politica = RatingCarryoverPolicy()
    ratings: dict[str, dict] = {}
    for club in roster_siguiente:
        if club in ratings_bmetro_anterior:
            rating_crudo = ratings_bmetro_anterior[club]
            club_obj = club_registry.get_by_name(club) if club_registry is not None else None
            ratings[club] = (
                combinar_con_memoria(rating_crudo, club_obj, "bmetro")
                if club_obj is not None
                else rating_crudo
            )
            continue

        if club in ratings_nacional:
            ratings[club] = politica.rating_para_recien_llegado(
                ratings_nacional[club], "nacional", "bmetro", club_nombre=club,
            )
            continue

        ratings_origen = ratings_primerac.get(club)
        ratings[club] = politica.rating_para_recien_llegado(
            ratings_origen,
            "primerac" if ratings_origen is not None else None,
            "bmetro",
            club_nombre=club,
        )
    return ratings


def _ratings_desde_tabla_simulada(tabla_unica: pd.DataFrame, n_clubes: int) -> dict:
    """Mismo criterio que carryover_engines.nacional._ratings_desde_tabla_simulada(),
    simplificado para una sola zona (todos los clubes juegan el mismo
    ida-y-vuelta entre sí: partidos_jugados = 2*(n_clubes-1) para
    TODOS, no hace falta mapear por zona)."""
    partidos_jugados = 2 * (n_clubes - 1)
    if partidos_jugados == 0:
        return {}

    promedio_liga_neutral = (PROMEDIO_GF_LOCAL_LIGA_BMETRO + PROMEDIO_GF_VISITANTE_LIGA_BMETRO) / 2
    factor_local = PROMEDIO_GF_LOCAL_LIGA_BMETRO / promedio_liga_neutral
    factor_visitante = PROMEDIO_GF_VISITANTE_LIGA_BMETRO / promedio_liga_neutral

    gf_prom_liga = (tabla_unica["gf"] / partidos_jugados).mean()
    gc_prom_liga = (tabla_unica["gc"] / partidos_jugados).mean()

    resultado = {}
    for _, fila in tabla_unica.iterrows():
        nombre = fila["equipo"]
        ataque_general = (fila["gf"] / partidos_jugados) / gf_prom_liga
        defensa_general = (fila["gc"] / partidos_jugados) / gc_prom_liga
        n = partidos_jugados
        resultado[nombre] = {
            "ataque_local": round((n * ataque_general * factor_local + K_REGRESION) / (n + K_REGRESION), 3),
            "ataque_visitante": round((n * ataque_general * factor_visitante + K_REGRESION) / (n + K_REGRESION), 3),
            "defensa_local": round((n * defensa_general * factor_local + K_REGRESION) / (n + K_REGRESION), 3),
            "defensa_visitante": round((n * defensa_general * factor_visitante + K_REGRESION) / (n + K_REGRESION), 3),
        }
    return resultado


def correr_temporada_desde_carryover(roster: list[str], ratings_iniciales: dict[str, dict]) -> ResultadoTorneo:
    """Corre una temporada COMPLETA de B Metro (fase regular + ascenso
    directo + Torneo Reducido) arrancando de una tabla en cero y los
    ratings YA COMBINADOS por el caller. Ver docstring del módulo.

    roster: nombres de los clubes de B Metro para esta temporada
        (después de PromotionManager).
    ratings_iniciales: debe cubrir TODO `roster` (fail-fast, mismo
        criterio que el resto de los motores season-only).

    Devuelve un ResultadoTorneo -- campeon=ascenso directo (mismo
    criterio ya documentado en BMetroAdapter.result()), ascensos=
    [directo, reducido], descensos=últimos DESCENSOS_N.
    """
    faltantes = [nombre for nombre in roster if nombre not in ratings_iniciales]
    if faltantes:
        raise ValueError(
            f"Faltan ratings iniciales para: {faltantes} -- "
            "ratings_iniciales debe cubrir TODO el roster."
        )
    if len(roster) < EstadisticasBMetro.REDUCIDO_N:
        raise ValueError(
            f"B Metro necesita al menos {EstadisticasBMetro.REDUCIDO_N} clubes para el "
            f"Torneo Reducido (octogonal, posiciones 2..{EstadisticasBMetro.REDUCIDO_N}), "
            f"el roster tiene {len(roster)}."
        )

    est = EstadisticasBMetro()
    est.PROMEDIO_GF_LOCAL_LIGA = PROMEDIO_GF_LOCAL_LIGA_BMETRO
    est.PROMEDIO_GF_VISITANTE_LIGA = PROMEDIO_GF_VISITANTE_LIGA_BMETRO

    est.tabla = pd.DataFrame([
        {
            "zona": "Unica", "posicion": 1, "equipo": nombre,
            "partidos_jugados": 0, "ganados": 0, "empatados": 0,
            "perdidos": 0, "gf": 0, "gc": 0, "dg": 0, "puntos": 0,
        }
        for nombre in roster
    ])
    est.crear_equipos_bmetro()  # heredado (delega en crear_equipos()), sin tocar

    for nombre, ratings in ratings_iniciales.items():
        equipo = est.equipos[nombre]
        equipo.ataque_local = ratings["ataque_local"]
        equipo.ataque_visitante = ratings["ataque_visitante"]
        equipo.defensa_local = ratings["defensa_local"]
        equipo.defensa_visitante = ratings["defensa_visitante"]

    est.fixture = pd.DataFrame([
        {"fecha": "", "jornada": p.jornada, "equipo_local": p.equipo_local,
         "equipo_visitante": p.equipo_visitante}
        for p in generar_fixture_ida_vuelta(sorted(roster))
    ])

    tablas = est.simular_fase_regular()  # heredado, sin tocar
    tabla_unica = tablas["Unica"]

    puntero = est.obtener_puntero(tabla_unica)  # heredado, sin tocar
    campeon_reducido, detalle_reducido = est.jugar_reducido_bmetro(tabla_unica)  # heredado, sin tocar
    descensos = tabla_unica.iloc[-EstadisticasBMetro.DESCENSOS_N:]["equipo"].tolist()

    datos_crudos = {
        "tabla": tabla_unica.to_dict(orient="records"),
        "puntero_ascenso_directo": puntero,
        "campeon_reducido": campeon_reducido,
        "reducido": detalle_reducido,
        "descensos": descensos,
    }

    return ResultadoTorneo(
        campeon=puntero,
        ascensos=[puntero, campeon_reducido],
        descensos=descensos,
        clasificados_copa=[],
        datos_crudos=datos_crudos,
        ratings_finales=_ratings_desde_tabla_simulada(tabla_unica, len(roster)),
    )
