# -*- coding: utf-8 -*-
"""
season/carryover_engines/federal.py

Motor season-only para el Torneo Federal A (Fase 5 de
HANDOFF_carryover_ratings.md). Mismo problema y mismo patrón que
season/carryover_engines/nacional.py (leer su docstring primero) --
acá solo se documentan las diferencias reales de Federal A,
confirmadas leyendo modelos/estadisticas_federal.py y main_federal.py
COMPLETOS antes de tocar nada (como pedía el HANDOFF):

  - `EstadisticasFederal` SÍ HEREDA de modelos/estadisticas.py (a
    diferencia de lo que decía el HANDOFF -- "motor vectorizado sin
    objetos Equipo por partido" es una descripción de la
    ESTIMACIÓN de probabilidades por Monte Carlo
    (simular_temporada_vectorizada(), usada solo para los
    porcentajes), NO de la corrida "oficial" única: main_federal.py
    tiene un modo de corrida ÚNICA, no vectorizada, con objetos
    Equipo reales -- `_correr_torneo_completo()` -- que es
    exactamente lo que este motor necesita y reproduce acá (sin
    importarlo desde main_federal.py, mismo criterio que los otros 4
    motores season-only: se replica la secuencia de llamadas a mano,
    todas a métodos de EstadisticasFederal SIN TOCAR una línea).
  - 5 Fases (Primera: 4 zonas: "1" de 10 clubes + "2"/"3"/"4" de 9
    cada una, ida y vuelta; Segunda: 2 zonas A/B de 9, una rueda;
    Tercera/Cuarta/Quinta: eliminación directa ida y vuelta, la
    Quinta a partido único -> 1er ascenso) EN PARALELO con la
    Reválida (6 Etapas -> 2do ascenso + 4 descensos, que en este
    sistema significan RETIRO del roster, no pasan a otra división
    modelada -- ver PromotionManager._retirar_club()).
  - `calcular_descensos()` (sin tocar) usa una constante hardcodeada
    _PARTIDOS_PRIMERA_FASE_POR_ZONA={10:18, 9:16} para el promedio de
    la Zona A de la Reválida -- ESTO ASUME que la Primera Fase se jugó
    la rueda doble COMPLETA (ida y vuelta) con el reparto real de
    zonas (10/9/9/9). Este motor arma exactamente esa fixture
    (generar_fixture_ida_vuelta por zona, mismo generador que las
    otras 4 divisiones) y confía en que zona_por_club venga con esa
    distribución -- que es justo lo que ya arma
    season/history_manager.py::_sortear_zonas_n(clubes, 4, rng) para
    "federal_a" (el resto de 37/4 se lo lleva la zona "1", que es
    ZONA_DIEZ). Si el roster de Federal A alguna vez deja de tener 37
    clubes (o de tener SIEMPRE los mismos tamaños de zona: 10/9/9/9),
    calcular_descensos() daría promedios mal calculados para la Zona
    A -- riesgo PREEXISTENTE del motor real (no introducido acá),
    coherente con el punto ya anotado en la memoria del proyecto
    ("Nacional y Federal A muestran fixture counts desparejos en
    diagnósticos").
  - RATINGS_FINALES: a diferencia de lo que decía el docstring viejo
    de ResultadoTorneo (ya corregido en la Fase 2/3, ver
    season/tournament_adapter.py), Federal A SÍ tiene objetos Equipo
    reales con ratings -- este motor los expone por primera vez (el
    FederalAdapter normal, vía main_federal.py, nunca lo hizo).

ORIGEN DE ASCENSOS A FEDERAL A (confirmado leyendo
season/promotion_manager.py real, sección "2) Nacional ->
{bmetro, federal_a}, por afiliación geográfica" -- Federal A NO recibe
de ninguna otra división, la sección "5) Federal A pierde 4 por
Reválida" son BAJAS que se reemplazan con clubes de relleno, no
ascensos reales):
  - Descendidos de Nacional (según afiliación geográfica).
  - Clubes de relleno (season/promotion_manager.py::_elegir_club_relleno)
    que reemplazan las bajas de la Reválida -- sin ratings_finales en
    ningún lado (ni siquiera en el pool, ver ese método), degradan al
    rating GENÉRICO -- mismo criterio que cualquier "recién llegado
    sin historial" del resto del sistema.
"""
from __future__ import annotations

import pandas as pd

from fixture_generator import generar_fixture_ida_vuelta
from main_federal import _serie_a_dict
from modelos.estadisticas_federal import EstadisticasFederal
from season.rating_carryover import RatingCarryoverPolicy, combinar_con_memoria
from season.tournament_adapter import ResultadoTorneo

K_REGRESION = 12


def armar_ratings_iniciales(club_registry, resultados_anterior: dict, roster_siguiente: list[str]) -> dict:
    """Análogo a carryover_engines.nacional.armar_ratings_iniciales(),
    con la única fuente de ascenso real de Federal A (ver docstring
    del módulo): continúan en federal_a -> combinar_con_memoria(); si
    no, vienen de un descenso de Nacional -- si tampoco están ahí
    (clubes de relleno de la Reválida, sin historial en ningún lado),
    degradan al rating GENÉRICO de RatingCarryoverPolicy."""
    resultado_federal_anterior = resultados_anterior.get("federal_a") if resultados_anterior else None
    ratings_federal_anterior = (
        resultado_federal_anterior.ratings_finales if resultado_federal_anterior is not None else {}
    )
    resultado_nacional = resultados_anterior.get("nacional") if resultados_anterior else None
    ratings_nacional = resultado_nacional.ratings_finales if resultado_nacional is not None else {}

    politica = RatingCarryoverPolicy()
    ratings: dict[str, dict] = {}
    for club in roster_siguiente:
        if club in ratings_federal_anterior:
            rating_crudo = ratings_federal_anterior[club]
            club_obj = club_registry.get_by_name(club) if club_registry is not None else None
            ratings[club] = (
                combinar_con_memoria(rating_crudo, club_obj, "federal_a")
                if club_obj is not None
                else rating_crudo
            )
            continue

        ratings_origen = ratings_nacional.get(club)
        ratings[club] = politica.rating_para_recien_llegado(
            ratings_origen,
            "nacional" if ratings_origen is not None else None,
            "federal_a",
            club_nombre=club,
        )
    return ratings


def _ratings_desde_tabla_simulada(tablas_primera_fase: dict, zona_por_club: dict[str, str]) -> dict:
    """Mismo criterio que carryover_engines.nacional._ratings_desde_tabla_simulada(),
    generalizado a N zonas (acá 4: "1".."4") -- se deriva de la
    PRIMERA FASE únicamente (el componente de todos-contra-todos, más
    representativo del nivel real del club que las llaves de
    eliminación de las fases siguientes)."""
    combinada = pd.concat(list(tablas_primera_fase.values()), ignore_index=True)

    tamanios_zona: dict[str, int] = {}
    for zona in zona_por_club.values():
        tamanios_zona[zona] = tamanios_zona.get(zona, 0) + 1
    partidos_jugados = {
        club: 2 * (tamanios_zona[zona] - 1) for club, zona in zona_por_club.items()
    }
    combinada["partidos_jugados"] = combinada["equipo"].map(partidos_jugados)

    promedio_liga_neutral = (
        EstadisticasFederal.PROMEDIO_GF_LOCAL_LIGA + EstadisticasFederal.PROMEDIO_GF_VISITANTE_LIGA
    ) / 2
    factor_local = EstadisticasFederal.PROMEDIO_GF_LOCAL_LIGA / promedio_liga_neutral
    factor_visitante = EstadisticasFederal.PROMEDIO_GF_VISITANTE_LIGA / promedio_liga_neutral

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
    """Corre una temporada COMPLETA del Torneo Federal A (5 Fases +
    Reválida de 6 Etapas) arrancando de una Primera Fase en cero y los
    ratings YA COMBINADOS por el caller. Reproduce, método a método y
    SIN TOCAR NINGUNO, la misma secuencia que
    main_federal.py::_correr_torneo_completo() -- ver docstring del
    módulo para por qué no se importa esa función directamente.

    roster: 37 clubes de Federal A (después de PromotionManager,
        incluidos los de relleno de la Reválida).
    zona_por_club: {equipo: "1"|"2"|"3"|"4"} -- zona "1" DEBE tener 10
        clubes y "2"/"3"/"4" 9 cada una (mismo reparto que ya arma
        HistoryManager -- ver docstring del módulo sobre por qué
        calcular_descensos() depende de esto).
    ratings_iniciales: debe cubrir TODO `roster` (fail-fast).

    Devuelve un ResultadoTorneo -- campeon=1er ascenso (camino
    principal, mismo criterio que FederalAdapter.result()),
    ascensos=[1er ascenso, 2do ascenso vía Reválida], descensos=4
    clubes (2 por zona de Reválida, calcular_descensos() sin tocar).
    """
    faltantes = [nombre for nombre in roster if nombre not in ratings_iniciales]
    if faltantes:
        raise ValueError(
            f"Faltan ratings iniciales para: {faltantes} -- "
            "ratings_iniciales debe cubrir TODO el roster."
        )

    est = EstadisticasFederal()
    est.tabla = pd.DataFrame([
        {
            "zona": zona_por_club[nombre], "posicion": 1, "equipo": nombre,
            "partidos_jugados": 0, "ganados": 0, "empatados": 0,
            "perdidos": 0, "gf": 0, "gc": 0, "dg": 0, "puntos": 0,
        }
        for nombre in roster
    ])
    est.crear_equipos_federal()  # = crear_equipos() heredado, sin tocar

    for nombre, ratings in ratings_iniciales.items():
        equipo = est.equipos[nombre]
        equipo.ataque_local = ratings["ataque_local"]
        equipo.ataque_visitante = ratings["ataque_visitante"]
        equipo.defensa_local = ratings["defensa_local"]
        equipo.defensa_visitante = ratings["defensa_visitante"]

    # Snapshots que normalmente arma cargar_datos_federal() (ver su
    # docstring) -- acá la Primera Fase arranca en cero (temporada
    # recién generada, sin partidos reales todavía), a diferencia de
    # la lectura real que parte de tabla_federal_a.csv ya con
    # jornadas jugadas.
    est._zonas_primera_fase = dict(zona_por_club)
    est._puntajes_primera_fase = {nombre: {"puntos": 0, "gf": 0, "gc": 0} for nombre in roster}
    est._totales_primera_fase = {nombre: {"puntos": 0, "gf": 0, "gc": 0} for nombre in roster}

    partidos = []
    for zona in sorted(set(zona_por_club.values())):
        clubes_zona = sorted(n for n, z in zona_por_club.items() if z == zona)
        partidos += generar_fixture_ida_vuelta(clubes_zona)
    est._fixture_primera_fase = pd.DataFrame([
        {"fecha": "", "jornada": p.jornada, "equipo_local": p.equipo_local,
         "equipo_visitante": p.equipo_visitante}
        for p in partidos
    ])

    est.reiniciar_para_nueva_corrida()  # heredado/propio, sin tocar -- deja zonas/fixture/puntajes listos

    # A partir de acá, MISMA secuencia que main_federal.py::_correr_torneo_completo(),
    # todos métodos de EstadisticasFederal sin tocar una línea.
    tablas_pf = est.simular_primera_fase()
    clasif_pf = est.clasificados_primera_fase(tablas_pf)

    est.armar_segunda_fase(clasif_pf)
    tablas_2f = est.simular_segunda_fase()
    clasif_2f = est.clasificados_segunda_fase(tablas_2f)

    resultados_3f = est.jugar_tercera_fase(clasif_2f["tercera_fase"])
    resultados_4f = est.jugar_cuarta_fase(resultados_3f)
    resultado_5f = est.jugar_quinta_fase(resultados_4f)

    est.armar_revalida_primera_etapa(clasif_pf)
    tablas_r1 = est.simular_revalida_primera_etapa()
    descensos = est.calcular_descensos(tablas_pf, tablas_r1, clasif_pf)

    posiciones_r2 = est.armar_revalida_segunda_etapa(
        resultados_3f, tablas_2f, clasif_2f["revalida_segunda_etapa_2f"], tablas_pf, tablas_r1
    )
    resultados_r2 = est.jugar_revalida_segunda_etapa(posiciones_r2)

    posiciones_r3 = est.armar_revalida_tercera_etapa(resultados_r2, resultados_4f, tablas_2f)
    resultados_r3 = est.jugar_revalida_tercera_etapa(posiciones_r3)

    posiciones_r4 = est.armar_revalida_cuarta_etapa(resultados_r3, resultado_5f)
    resultados_r4 = est.jugar_revalida_cuarta_etapa(posiciones_r4)

    resultados_r5 = est.jugar_revalida_quinta_etapa(resultados_r4)
    resultado_r6 = est.jugar_revalida_sexta_etapa(resultados_r5)

    ascenso_1 = resultado_5f.ganador
    ascenso_2 = resultado_r6.ganador

    datos_crudos = {
        "primera_fase": {"tablas": {z: t.to_dict(orient="records") for z, t in tablas_pf.items()}},
        "segunda_fase": {"tablas": {z: t.to_dict(orient="records") for z, t in tablas_2f.items()}},
        "camino_principal": {
            # _serie_a_dict() traduce el shape interno de Federal A
            # (local_ida/ida/vuelta/agregado para las series, marcador
            # para el partido único) al shape que ya esperan
            # matchHTML()/seriesHTML() del frontend -- exactamente lo
            # mismo que hace main_federal.py::_armar_datos_web() para
            # la pestaña normal de Federal A. Antes acá se mandaba
            # resultado.detalle crudo, así que el frontend no
            # encontraba equipo_x/equipo_y/campeon (ni local/visitante/
            # golesLocal/golesVisitante) y terminaba imprimiendo
            # "undefined" en las tarjetas de Tercera/Cuarta Fase y en
            # el marcador de la Final.
            "tercera_fase": {k: _serie_a_dict(v) for k, v in resultados_3f.items()},
            "cuarta_fase": {k: _serie_a_dict(v) for k, v in resultados_4f.items()},
            "quinta_fase_final": _serie_a_dict(resultado_5f),
            "ascenso_1": ascenso_1,
        },
        "revalida": {
            "primera_etapa": {"tablas": {z: t.to_dict(orient="records") for z, t in tablas_r1.items()}},
            "descensos": descensos,
            "ascenso_2": ascenso_2,
        },
    }

    return ResultadoTorneo(
        campeon=ascenso_1,
        ascensos=[ascenso_1, ascenso_2],
        descensos=descensos,
        clasificados_copa=[],
        datos_crudos=datos_crudos,
        ratings_finales=_ratings_desde_tabla_simulada(tablas_pf, zona_por_club),
    )
