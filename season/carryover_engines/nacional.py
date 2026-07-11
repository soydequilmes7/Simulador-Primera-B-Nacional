# -*- coding: utf-8 -*-
"""
season/carryover_engines/nacional.py

Motor season-only para Primera Nacional (Fase 2 de
HANDOFF_carryover_ratings.md).

EL PROBLEMA QUE RESUELVE: cuando Modo Temporada genera la temporada
N+1 de Nacional (HistoryManager._armar_standings_en_cero() -- tabla en
0 partidos, sin ratings), y después alguien la simula llamando a
NacionalAdapter.run() -> main.correr_simulacion() -> cargar_datos() lee
esa tabla en cero -> calcular_ratings() (modelos/estadisticas.py línea
~142) corta temprano porque len(self.resultados)==0 y deja a TODOS los
clubes en el rating default de Equipo.__init__ (1.0/1.0) -- el
campeón, el recién ascendido y el histórico grande arrancan
exactamente igual. Ver sección 3 de HANDOFF_carryover_ratings.md.

QUÉ HACE ESTE MÓDULO: reemplaza el tramo cargar_datos() -> crear_equipos()
-> calcular_estadisticas() -> calcular_ratings() de main.correr_simulacion()
por: armar una tabla en cero + PISAR los ratings con los valores ya
combinados por el caller (memoria EWMA + handicap de Fase 0 para los
que continúan en Nacional, RatingCarryoverPolicy para los ascendidos
de BMetro/Federal A -- ver season/rating_carryover.py). De ahí en
más, usa TAL CUAL (sin reescribir una sola línea) los métodos
heredados de modelos/estadisticas.py: crear_equipos(),
simular_fase_regular(), jugar_final_ascenso(), jugar_reducido().

QUÉ NO HACE (fuera de alcance de la Fase 2, ver HANDOFF): no decide
CUÁNDO usar este motor en vez de main.correr_simulacion() dentro del
flujo real de Modo Temporada -- esa decisión vive en la orquestación
de rondas de api/index.py, que está fuera de "season/" y por lo tanto
fuera del alcance que fijó el usuario para este trabajo. Lo que sí se
agrega es NacionalAdapter.run_desde_carryover() (ver
season/adapters/nacional_adapter.py), listo para que quien orqueste
lo llame en vez de run() cuando corresponda.

RATINGS_FINALES DE ESTA TEMPORADA -- SIMPLIFICACIÓN DOCUMENTADA:
simular_fase_regular() (heredado) devuelve la tabla final AGREGADA
(puntos/gf/gc por zona), no el resultado partido a partido -- no hay
como reconstruir un DataFrame de partidos reales para volver a llamar
a calcular_ratings() heredado. Se deriva un rating final a partir de
esa tabla agregada con el MISMO criterio que ya usa
EstadisticasLPF.ratings_desde_tabla_anual() (fórmula duplicada acá a
propósito, mismo espíritu que esa función ya documenta: "se acepta la
duplicación de estas pocas líneas de fórmula, documentada acá y ahí"
-- ver _ratings_desde_tabla_simulada() más abajo).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from fixture_generator import generar_fixture_ida_vuelta
from modelos.estadisticas import Estadisticas
from season.rating_carryover import RatingCarryoverPolicy, combinar_con_memoria
from season.tournament_adapter import ResultadoTorneo

# Mismo K_REGRESION que el resto del proyecto (modelos/estadisticas.py,
# season/rating_carryover.py, estadisticas_lpf.ratings_desde_tabla_anual).
K_REGRESION = 12


def _extraer_descendidos(tablas: dict) -> list[str]:
    """Últimos 2 de cada zona -- misma regla que
    season/adapters/nacional_adapter.py::_extraer_descendidos() (que
    opera sobre la versión aplanada a dict; acá se trabaja directo
    sobre los DataFrame que devuelve simular_fase_regular())."""
    descendidos: list[str] = []
    for zona in ("A", "B"):
        descendidos.extend(tablas[zona].iloc[-2:]["equipo"].tolist())
    return descendidos


def _ratings_desde_tabla_simulada(tablas: dict, zona_por_club: dict[str, str]) -> dict:
    """Deriva ataque/defensa de cada club desde la tabla final de ESTA
    temporada simulada (puntos/gf/gc agregados por zona) -- ver
    docstring del módulo (misma fórmula que
    EstadisticasLPF.ratings_desde_tabla_anual(), duplicada a
    propósito). Sirve como ratings_finales: la próxima vez que el
    club siga en Nacional, combinar_con_memoria() (Fase 0) lo va a
    mezclar con su historial EWMA."""
    combinada = pd.concat([tablas["A"], tablas["B"]], ignore_index=True)

    tamanios_zona: dict[str, int] = {}
    for zona in zona_por_club.values():
        tamanios_zona[zona] = tamanios_zona.get(zona, 0) + 1
    partidos_jugados = {
        club: 2 * (tamanios_zona[zona] - 1) for club, zona in zona_por_club.items()
    }
    combinada["partidos_jugados"] = combinada["equipo"].map(partidos_jugados)

    promedio_liga_neutral = (
        Estadisticas.PROMEDIO_GF_LOCAL_LIGA + Estadisticas.PROMEDIO_GF_VISITANTE_LIGA
    ) / 2
    factor_local = Estadisticas.PROMEDIO_GF_LOCAL_LIGA / promedio_liga_neutral
    factor_visitante = Estadisticas.PROMEDIO_GF_VISITANTE_LIGA / promedio_liga_neutral

    gf_prom_liga = (combinada["gf"] / combinada["partidos_jugados"]).mean()
    gc_prom_liga = (combinada["gc"] / combinada["partidos_jugados"]).mean()

    resultado = {}
    for _, fila in combinada.iterrows():
        nombre = fila["equipo"]
        n = fila["partidos_jugados"]
        if n == 0:
            continue  # no debería pasar (fixture siempre ida y vuelta), degrada sin romper

        ataque_general = (fila["gf"] / n) / gf_prom_liga
        defensa_general = (fila["gc"] / n) / gc_prom_liga

        resultado[nombre] = {
            "ataque_local": round((n * ataque_general * factor_local + K_REGRESION) / (n + K_REGRESION), 3),
            "ataque_visitante": round((n * ataque_general * factor_visitante + K_REGRESION) / (n + K_REGRESION), 3),
            "defensa_local": round((n * defensa_general * factor_local + K_REGRESION) / (n + K_REGRESION), 3),
            "defensa_visitante": round((n * defensa_general * factor_visitante + K_REGRESION) / (n + K_REGRESION), 3),
        }
    return resultado


def armar_ratings_iniciales(club_registry, resultados_anterior: dict, roster_siguiente: list[str]) -> dict:
    """Arma ratings_iniciales para correr_temporada_desde_carryover(),
    combinando Fase 0 (memoria EWMA + handicap) con RatingCarryoverPolicy
    para los ascendidos -- mismo espíritu que
    HistoryManager._ratings_iniciales_lpf(), adaptado a que Nacional
    recibe ascensos de DOS divisiones (BMetro y Federal A, ver
    season/promotion_manager.py):

      a) clubes que YA jugaban Nacional la temporada anterior: su
         rating final de esa temporada
         (resultados_anterior["nacional"].ratings_finales) combinado
         con memoria EWMA + handicap de Fase 0
         (combinar_con_memoria(), usa Club.history vía club_registry).
         Si el club no está en club_registry (no debería pasar) se
         usa el rating de la temporada anterior sin combinar --
         degrada con gracia.
      b) clubes recién ascendidos: se busca primero en
         resultados_anterior["bmetro"].ratings_finales y, si no está
         ahí, en resultados_anterior["federal_a"].ratings_finales
         (que hoy queda vacío a propósito -- ver ResultadoTorneo --
         así que en la práctica un ascendido de Federal A cae al
         rating GENÉRICO de RatingCarryoverPolicy, degradando con
         gracia en vez de romper, igual que ya pasa con LPF/Nacional
         en HistoryManager).

    club_registry: puede ser None (degrada a "sin memoria" para
        todos, útil para tests que no arman un ClubRegistry completo).
    resultados_anterior: dict[str, ResultadoTorneo] de la temporada
        QUE TERMINA -- se leen las claves "nacional"/"bmetro"/
        "federal_a" si están, ninguna es obligatoria (todas ausentes
        degrada a "todos recién llegados sin historial")."""
    resultado_nacional_anterior = resultados_anterior.get("nacional") if resultados_anterior else None
    ratings_nacional_anterior = (
        resultado_nacional_anterior.ratings_finales if resultado_nacional_anterior is not None else {}
    )
    resultado_bmetro = resultados_anterior.get("bmetro") if resultados_anterior else None
    ratings_bmetro = resultado_bmetro.ratings_finales if resultado_bmetro is not None else {}
    resultado_federal = resultados_anterior.get("federal_a") if resultados_anterior else None
    ratings_federal = resultado_federal.ratings_finales if resultado_federal is not None else {}

    politica = RatingCarryoverPolicy()
    ratings: dict[str, dict] = {}
    for club in roster_siguiente:
        if club in ratings_nacional_anterior:
            rating_crudo = ratings_nacional_anterior[club]
            club_obj = club_registry.get_by_name(club) if club_registry is not None else None
            ratings[club] = (
                combinar_con_memoria(rating_crudo, club_obj, "nacional")
                if club_obj is not None
                else rating_crudo
            )
            continue

        if club in ratings_bmetro:
            ratings[club] = politica.rating_para_recien_llegado(ratings_bmetro[club], "bmetro", "nacional")
            continue

        ratings_origen = ratings_federal.get(club)
        ratings[club] = politica.rating_para_recien_llegado(
            ratings_origen,
            "federal_a" if ratings_origen is not None else None,
            "nacional",
        )
    return ratings


def correr_temporada_desde_carryover(
    roster: list[str],
    zona_por_club: dict[str, str],
    ratings_iniciales: dict[str, dict],
) -> ResultadoTorneo:
    """Corre una temporada COMPLETA de Nacional (fase regular + final
    de 1er ascenso + Reducido) arrancando de una tabla en cero y los
    ratings YA COMBINADOS por el caller. Ver docstring del módulo.

    roster: nombres de los clubes de Nacional para esta temporada
        (después de PromotionManager -- ver
        ClubRegistry.get_by_division("Primera Nacional")).
    zona_por_club: {equipo: "A"|"B"} -- mismo sorteo que usa
        HistoryManager para standings/fixture de esta temporada.
    ratings_iniciales: {equipo: {ataque_local, ataque_visitante,
        defensa_local, defensa_visitante}} -- debe cubrir TODO
        `roster` (fail-fast si falta alguno, mismo criterio que
        EstadisticasLPF.simular_apertura_desde_carryover()).

    Devuelve un ResultadoTorneo (mismo shape que NacionalAdapter.result())
    para poder conectarse donde haga falta sin que Copa Argentina,
    QualificationManager o PromotionManager noten la diferencia."""
    faltantes = [nombre for nombre in roster if nombre not in ratings_iniciales]
    if faltantes:
        raise ValueError(
            f"Faltan ratings iniciales para: {faltantes} -- "
            "ratings_iniciales debe cubrir TODO el roster."
        )

    est = Estadisticas()
    est.tabla = pd.DataFrame([
        {
            "zona": zona_por_club[nombre], "posicion": 1, "equipo": nombre,
            "partidos_jugados": 0, "ganados": 0, "empatados": 0,
            "perdidos": 0, "gf": 0, "gc": 0, "dg": 0, "puntos": 0,
        }
        for nombre in roster
    ])
    est.crear_equipos()  # heredado, sin tocar

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

    tablas = est.simular_fase_regular()  # heredado, sin tocar

    puntero_a = tablas["A"].iloc[0]["equipo"]
    puntero_b = tablas["B"].iloc[0]["equipo"]
    ganador, perdedor, detalle_final = est.jugar_final_ascenso(puntero_a, puntero_b)  # heredado
    campeon_reducido, detalle_reducido = est.jugar_reducido(tablas, perdedor)  # heredado

    datos_crudos = {
        "tablas": {
            "A": tablas["A"].to_dict(orient="records"),
            "B": tablas["B"].to_dict(orient="records"),
        },
        "final_ascenso": {
            "equipo_a": puntero_a, "equipo_b": puntero_b,
            "ganador": ganador, "perdedor": perdedor,
            "detalle_marcador": detalle_final.get("marcador", [0, 0]) if isinstance(detalle_final, dict) else [0, 0],
        },
        "reducido": detalle_reducido,
    }

    return ResultadoTorneo(
        campeon=ganador,
        ascensos=[ganador, campeon_reducido],
        descensos=_extraer_descendidos(tablas),
        clasificados_copa=[],
        datos_crudos=datos_crudos,
        ratings_finales=_ratings_desde_tabla_simulada(tablas, zona_por_club),
    )
