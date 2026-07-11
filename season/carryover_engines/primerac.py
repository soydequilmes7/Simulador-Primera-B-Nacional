# -*- coding: utf-8 -*-
"""
season/carryover_engines/primerac.py

Motor season-only para Primera C (Fase 4 de
HANDOFF_carryover_ratings.md). Mismo problema y mismo patrón que
season/carryover_engines/nacional.py (leer su docstring primero) --
acá solo se documentan las diferencias reales de Primera C,
confirmadas leyendo modelos/estadisticas_primerac.py COMPLETO antes de
tocar nada (como pedía el HANDOFF):

  - `modelos.estadisticas_primerac.Estadisticas` es una clase
    STANDALONE -- NO hereda de modelos/estadisticas.py. Tiene su
    propia copia de crear_equipos()/simular_fase_regular()/
    simular_partido()/jugar_serie_ida_vuelta()/etc, calcada pero
    duplicada (confirmado, no es la misma clase). Se importa acá con
    alias EstadisticasPrimeraC para no chocar con
    modelos.estadisticas.Estadisticas.
  - jugar_final_ascenso(tablas) -- firma DISTINTA a Nacional
    (jugar_final_ascenso(nombre_a, nombre_b)): acá recibe el dict de
    tablas completo (necesita los puntos de la fase regular para
    decidir quién es local en la vuelta -- Boletín 6825, final a doble
    partido). Devuelve (ganador, perdedor, detalle) iguel que Nacional.
  - jugar_reducido(tablas, perdedor) -- misma firma que Nacional, pero
    formato distinto por dentro (2°-7° de cada zona, TODAS las rondas
    ida y vuelta) -- no importa acá porque se llama tal cual, heredado
    (bueno, en este caso "propio de la clase", no heredado -- pero
    igual sin tocarle una línea).
  - SIN DESCENSOS: Primera C es la categoría más baja modelada: el
    último de cada zona juega un partido por la "suspensión de
    afiliación" contra un rival del Torneo Promocional Amateur, que
    este motor NO simula (ver docstring de
    EstadisticasPrimeraC.monte_carlo()). PrimeraCAdapter.result() ya
    documenta esto con descensos=[] siempre -- se replica el mismo
    criterio acá, no hace falta reconstruir nada.
  - Zonas A/B (2 zonas, mismo formato que Nacional) -- confirmado
    también en season/history_manager.py::DIVISIONES_DOS_ZONAS, que ya
    incluye "primerac".
  - Sin recalibración de PROMEDIO_GF_LOCAL/VISITANTE_LIGA: a
    diferencia de B Metro, estadisticas_primerac.py NUNCA recalibra
    esas constantes (se queda siempre en el default 1.35/1.05,
    confirmado -- no hay ningún cargar_datos_primerac() análogo al de
    B Metro). Este motor tampoco recalibra nada, mismo comportamiento.

ORIGEN DE ASCENSOS A PRIMERA C (confirmado leyendo
season/promotion_manager.py real, sección "4) bmetro <-> primerac"):
SOLO descendidos de B Metro (resultados["bmetro"].descensos ->
primerac). Primera C no recibe de ningún otro lado -- es la única
división con una sola fuente de arrivals, a diferencia de Nacional
(bmetro + federal_a) y BMetro (nacional + primerac).
"""
from __future__ import annotations

import pandas as pd

from fixture_generator import generar_fixture_ida_vuelta
from modelos.estadisticas_primerac import Estadisticas as EstadisticasPrimeraC
from season.rating_carryover import RatingCarryoverPolicy, combinar_con_memoria
from season.tournament_adapter import ResultadoTorneo

K_REGRESION = 12


def armar_ratings_iniciales(club_registry, resultados_anterior: dict, roster_siguiente: list[str]) -> dict:
    """Análogo a carryover_engines.nacional.armar_ratings_iniciales(),
    con la única fuente de ascenso real de Primera C (ver docstring
    del módulo): continúan en primerac -> combinar_con_memoria(); si
    no, vienen de un descenso de B Metro -- si tampoco están ahí
    (o "bmetro" no viene en resultados_anterior), degradan al rating
    GENÉRICO de RatingCarryoverPolicy (recién llegado sin historial)."""
    resultado_primerac_anterior = resultados_anterior.get("primerac") if resultados_anterior else None
    ratings_primerac_anterior = (
        resultado_primerac_anterior.ratings_finales if resultado_primerac_anterior is not None else {}
    )
    resultado_bmetro = resultados_anterior.get("bmetro") if resultados_anterior else None
    ratings_bmetro = resultado_bmetro.ratings_finales if resultado_bmetro is not None else {}

    politica = RatingCarryoverPolicy()
    ratings: dict[str, dict] = {}
    for club in roster_siguiente:
        if club in ratings_primerac_anterior:
            rating_crudo = ratings_primerac_anterior[club]
            club_obj = club_registry.get_by_name(club) if club_registry is not None else None
            ratings[club] = (
                combinar_con_memoria(rating_crudo, club_obj, "primerac")
                if club_obj is not None
                else rating_crudo
            )
            continue

        ratings_origen = ratings_bmetro.get(club)
        ratings[club] = politica.rating_para_recien_llegado(
            ratings_origen,
            "bmetro" if ratings_origen is not None else None,
            "primerac",
            club_nombre=club,
        )
    return ratings


def _ratings_desde_tabla_simulada(tablas: dict, zona_por_club: dict[str, str]) -> dict:
    """Mismo criterio que carryover_engines.nacional._ratings_desde_tabla_simulada()
    (2 zonas A/B) -- duplicado a propósito, mismo espíritu documentado
    ahí y en EstadisticasLPF.ratings_desde_tabla_anual()."""
    combinada = pd.concat([tablas["A"], tablas["B"]], ignore_index=True)

    tamanios_zona: dict[str, int] = {}
    for zona in zona_por_club.values():
        tamanios_zona[zona] = tamanios_zona.get(zona, 0) + 1
    partidos_jugados = {
        club: 2 * (tamanios_zona[zona] - 1) for club, zona in zona_por_club.items()
    }
    combinada["partidos_jugados"] = combinada["equipo"].map(partidos_jugados)

    promedio_liga_neutral = (
        EstadisticasPrimeraC.PROMEDIO_GF_LOCAL_LIGA + EstadisticasPrimeraC.PROMEDIO_GF_VISITANTE_LIGA
    ) / 2
    factor_local = EstadisticasPrimeraC.PROMEDIO_GF_LOCAL_LIGA / promedio_liga_neutral
    factor_visitante = EstadisticasPrimeraC.PROMEDIO_GF_VISITANTE_LIGA / promedio_liga_neutral

    gf_prom_liga = (combinada["gf"] / combinada["partidos_jugados"]).mean()
    gc_prom_liga = (combinada["gc"] / combinada["partidos_jugados"]).mean()

    resultado = {}
    for _, fila in combinada.iterrows():
        nombre = fila["equipo"]
        n = fila["partidos_jugados"]
        if n == 0:
            continue

        ataque_general = (fila["gf"] / n) / gf_prom_liga
        defensa_general = (fila["gc"] / n) / gc_prom_liga

        resultado[nombre] = {
            "ataque_local": round((n * ataque_general * factor_local + K_REGRESION) / (n + K_REGRESION), 3),
            "ataque_visitante": round((n * ataque_general * factor_visitante + K_REGRESION) / (n + K_REGRESION), 3),
            "defensa_local": round((n * defensa_general * factor_local + K_REGRESION) / (n + K_REGRESION), 3),
            "defensa_visitante": round((n * defensa_general * factor_visitante + K_REGRESION) / (n + K_REGRESION), 3),
        }
    return resultado


def correr_temporada_desde_carryover(
    roster: list[str],
    zona_por_club: dict[str, str],
    ratings_iniciales: dict[str, dict],
) -> ResultadoTorneo:
    """Corre una temporada COMPLETA de Primera C (fase de zonas + Final
    por el 1er Ascenso a doble partido + Torneo Reducido) arrancando de
    una tabla en cero y los ratings YA COMBINADOS por el caller. Ver
    docstring del módulo.

    roster / zona_por_club: igual que en Nacional (ver
    carryover_engines.nacional.correr_temporada_desde_carryover()).

    Devuelve un ResultadoTorneo con descensos=[] SIEMPRE (ver docstring
    del módulo -- Primera C no desciende dentro de este sistema)."""
    faltantes = [nombre for nombre in roster if nombre not in ratings_iniciales]
    if faltantes:
        raise ValueError(
            f"Faltan ratings iniciales para: {faltantes} -- "
            "ratings_iniciales debe cubrir TODO el roster."
        )

    est = EstadisticasPrimeraC()
    est.tabla = pd.DataFrame([
        {
            "zona": zona_por_club[nombre], "posicion": 1, "equipo": nombre,
            "partidos_jugados": 0, "ganados": 0, "empatados": 0,
            "perdidos": 0, "gf": 0, "gc": 0, "dg": 0, "puntos": 0,
        }
        for nombre in roster
    ])
    est.crear_equipos()  # propio de la clase (no heredado, pero sin tocar)

    for nombre, ratings in ratings_iniciales.items():
        equipo = est.equipos[nombre]
        equipo.ataque_local = ratings["ataque_local"]
        equipo.ataque_visitante = ratings["ataque_visitante"]
        equipo.defensa_local = ratings["defensa_local"]
        equipo.defensa_visitante = ratings["defensa_visitante"]

    partidos = []
    for zona in sorted(set(zona_por_club.values())):
        clubes_zona = sorted(n for n, z in zona_por_club.items() if z == zona)
        partidos += generar_fixture_ida_vuelta(clubes_zona)
    est.fixture = pd.DataFrame([
        {"fecha": "", "jornada": p.jornada, "equipo_local": p.equipo_local,
         "equipo_visitante": p.equipo_visitante}
        for p in partidos
    ])

    tablas = est.simular_fase_regular()  # sin tocar

    ganador, perdedor, detalle_final = est.jugar_final_ascenso(tablas)  # firma propia de Primera C, sin tocar
    campeon_reducido, detalle_reducido = est.jugar_reducido(tablas, perdedor)  # sin tocar

    datos_crudos = {
        "tablas": {
            "A": tablas["A"].to_dict(orient="records"),
            "B": tablas["B"].to_dict(orient="records"),
        },
        "final_ascenso": {
            "ganador": ganador, "perdedor": perdedor,
            "detalle": detalle_final.get("detalle", ""),
        },
        "reducido": detalle_reducido,
    }

    return ResultadoTorneo(
        campeon=ganador,
        ascensos=[ganador, campeon_reducido],
        descensos=[],  # Primera C no desciende dentro de este sistema -- ver docstring del módulo
        clasificados_copa=[],
        datos_crudos=datos_crudos,
        ratings_finales=_ratings_desde_tabla_simulada(tablas, zona_por_club),
    )
