# -*- coding: utf-8 -*-
"""
season/sudamericana_temporada.py

Orquesta una temporada completa de Copa Sudamericana dentro de Modo
Temporada, reusando toda la maquinaria ya construida para Libertadores
en vez de duplicarla:

    - LibertadoresManager (ver season/libertadores_manager.py), con
      SUS PROPIAS cuotas (QUOTAS_PAIS_SUDAMERICANA acá abajo, distinta
      de la de Libertadores) sobre el MISMO pool de datos/
      libertadores_pool_internacional.csv.
    - sortear_grupos()/jugar_fase_de_grupos() (ver
      season/libertadores_sorteo.py y season/libertadores_grupos.py),
      sin cambios: son genéricas, no saben ni les importa para qué
      copa se están usando.
    - EstadisticasSudamericana (ver
      modelos/estadisticas_sudamericana.py), que ya sabe resolver
      Playoffs -> Octavos -> Cuartos -> Semis -> Final -- acá solo se
      arma el cuadro que consume, no se toca su lógica interna.

Reglamento real de Playoffs/Octavos (confirmado contra el instructivo
oficial de CONMEBOL, conmebol.com, "Aquí todo sobre el sorteo:
CONMEBOL Libertadores - CONMEBOL Sudamericana", 29/05/2026 -- una
versión anterior de este módulo tenía esto mal, evitaba cruces de
mismo país con backtracking donde el reglamento real NO restringe
nada):

    Playoffs de Octavos: NO es un sorteo, es determinístico por
    desempeño -- "el mejor segundo [de Sudamericana] enfrenta al peor
    tercero [de Libertadores], y así sucesivamente". Sin restricción
    de país (pueden cruzarse dos equipos del mismo país si vienen de
    competencias distintas). Ida en la cancha del tercero de
    Libertadores, vuelta en la del segundo de Sudamericana (el más
    beneficiado, por eso define la serie).

    Octavos de Final: acá sí es un sorteo abierto -- Bolillero 1 son
    los 8 primeros de zona de Sudamericana, Bolillero 2 son los 8
    ganadores de Playoffs. Se sortea sin restricción de país. El
    Bolillero 1 (mejor ranking) define la vuelta como local.

Un mismo club no puede jugar Libertadores Y Sudamericana la misma
temporada: se arma la clasificación de Sudamericana excluyendo del
pool internacional los equipos que ya sacó LibertadoresManager esa
temporada (ver el parámetro `excluir` de
LibertadoresManager.armar_clasificacion()).
"""
from __future__ import annotations

import random

from modelos.estadisticas_sudamericana import EstadisticasSudamericana
from season.libertadores_manager import LibertadoresManager, cargar_pool_internacional
from season.libertadores_sorteo import sortear_grupos
from season.libertadores_grupos import jugar_fase_de_grupos

CUPOS_ARGENTINA_SUDAMERICANA = 6
# Cuotas propias (no las mismas que Libertadores, ver QUOTAS_PAIS en
# season/libertadores_manager.py) sobre el MISMO pool. Suman 26 (+ 6
# de Argentina = 32) -- valor de arranque razonable, no calibrado con
# datos reales de cupos de Sudamericana (mismo criterio que ya se usó
# para los de Libertadores).
QUOTAS_PAIS_SUDAMERICANA: dict[str, int] = {
    "Brasil": 7,
    "Colombia": 3,
    "Ecuador": 3,
    "Peru": 3,
    "Uruguay": 3,
    "Chile": 3,
    "Paraguay": 2,
    "Bolivia": 1,
    "Venezuela": 1,
}
CANTIDAD_TOTAL = CUPOS_ARGENTINA_SUDAMERICANA + sum(QUOTAS_PAIS_SUDAMERICANA.values())  # 32


def simular_temporada_sudamericana(
    clasificados_argentinos: list[str],
    resultado_libertadores: dict,
    elo_argentinos: dict[str, float] | None = None,
    rng: random.Random | None = None,
    pool: list | None = None,
) -> dict:
    """resultado_libertadores: el dict que devuelve season/
    libertadores_grupos.py::simular_temporada_libertadores() de ESTA
    MISMA temporada -- hace falta que haya corrido antes. Se usan sus
    8 terceros de zona (uno por zona, ver resultado_libertadores
    ["zonas"][i]["tabla"][2]) para completar los Playoffs, su Elo
    (resultado_libertadores["elo_por_equipo"]) para simularlos, y su
    lista de equipos_internacionales_usados para no repetir club entre
    las dos copas la misma temporada.

    Devuelve un dict con la misma forma que simular_temporada_
    libertadores() (avisos/zonas/cuadro_playoffs/cuadro_octavos/
    rondas/campeon), JSON-safe."""
    rng = rng or random.Random()
    pool = pool if pool is not None else cargar_pool_internacional()

    manager = LibertadoresManager(
        pool=pool, quotas_pais=QUOTAS_PAIS_SUDAMERICANA, cupos_local=CUPOS_ARGENTINA_SUDAMERICANA,
    )
    excluir = set(resultado_libertadores.get("equipos_internacionales_usados", []))
    clasificacion = manager.armar_clasificacion(
        clasificados_argentinos, elo_argentinos, rng=rng, excluir=excluir,
    )

    zonas_sorteadas = sortear_grupos(clasificacion, rng=rng)
    elo_por_equipo = clasificacion.elo_por_equipo()
    pais_por_equipo = {c.equipo: c.pais for c in clasificacion.equipos}
    zonas_jugadas = jugar_fase_de_grupos(zonas_sorteadas, elo_por_equipo, pais_por_equipo, rng=rng)

    primeros = [z.tabla[0].equipo for z in zonas_jugadas]  # directo a Octavos
    segundos_con_stats = [z.tabla[1] for z in zonas_jugadas]  # a Playoffs

    terceros_con_stats = [
        {"equipo": z["tabla"][2]["equipo"], "puntos": z["tabla"][2]["puntos"],
         "dg": z["tabla"][2]["dg"], "gf": z["tabla"][2]["gf"]}
        for z in resultado_libertadores["zonas"]
    ]
    terceros_libertadores = [t["equipo"] for t in terceros_con_stats]
    elo_terceros_lib = {t: resultado_libertadores["elo_por_equipo"][t] for t in terceros_libertadores}
    elo_por_equipo_completo = {**elo_por_equipo, **elo_terceros_lib}

    cuadro_playoffs = _armar_playoffs_por_ranking(segundos_con_stats, terceros_con_stats)
    cuadro_octavos = _sortear_octavos_pendientes(primeros, cantidad_llaves=8, rng=rng)

    motor = EstadisticasSudamericana()
    motor.cuadro_playoffs = cuadro_playoffs
    motor.cuadro = cuadro_octavos
    motor._octavos_ida_original = {int(f["llave"]): "" for f in cuadro_octavos}
    motor.crear_equipos_desde_elo(
        {c.equipo for c in clasificacion.equipos} | set(terceros_libertadores),
        elo_por_equipo_completo,
    )
    rondas_detalle, campeon = motor.simular_sudamericana()

    return {
        "avisos": clasificacion.avisos,
        "zonas": [
            {
                "letra": z.letra,
                "partidos": z.partidos,
                "tabla": [
                    {
                        "equipo": f.equipo, "pais": f.pais, "puntos": f.puntos, "pj": f.pj,
                        "pg": f.pg, "pe": f.pe, "pp": f.pp, "gf": f.gf, "gc": f.gc, "dg": f.dg,
                    }
                    for f in z.tabla
                ],
            }
            for z in zonas_jugadas
        ],
        "cuadro_playoffs": cuadro_playoffs,
        "cuadro_octavos": cuadro_octavos,
        "rondas": rondas_detalle,
        "campeon": campeon,
        # Elo de los participantes de ESTA Sudamericana (equipos propios +
        # los terceros de zona "prestados" de Libertadores) -- lo necesita
        # season/recopa_sudamericana.py para simular la Recopa contra el
        # campeón de la Libertadores de la misma temporada, mismo criterio
        # que ya expone simular_temporada_libertadores().
        "elo_por_equipo": elo_por_equipo_completo,
    }


def _ordenar_por_desempeno(candidatos: list[dict]) -> list[dict]:
    """Ordena de mejor a peor por (puntos, diferencia de gol, goles a
    favor) -- mismo criterio que ya usa la tabla de zona (ver
    season/libertadores_grupos.py::_ordenar_tabla()), aplicado acá
    para comparar equipos de ZONAS DISTINTAS entre sí. Aproximación
    razonable: CONMEBOL no publica en detalle el criterio exacto para
    rankear "mejor segundo"/"peor tercero" entre grupos."""
    return sorted(candidatos, key=lambda c: (c["puntos"], c["dg"], c["gf"]), reverse=True)


def _armar_playoffs_por_ranking(segundos_con_stats: list, terceros_con_stats: list[dict]) -> list[dict]:
    """Playoffs de Octavos: determinístico por desempeño, NO es un
    sorteo (ver docstring del módulo) -- el mejor segundo de
    Sudamericana enfrenta al peor tercero de Libertadores, bajando
    sucesivamente. Ida en la cancha del tercero de Libertadores
    (menos beneficiado), vuelta en la del segundo de Sudamericana."""
    segundos_ordenados = _ordenar_por_desempeno([
        {"equipo": f.equipo, "puntos": f.puntos, "dg": f.dg, "gf": f.gf} for f in segundos_con_stats
    ])
    terceros_ordenados = _ordenar_por_desempeno(terceros_con_stats)
    peor_a_mejor_terceros = list(reversed(terceros_ordenados))

    return [
        {
            "ronda": "playoffs", "llave": i + 1,
            "equipo_ida_local": peor_a_mejor_terceros[i]["equipo"],
            "equipo_vuelta_local": segundos_ordenados[i]["equipo"],
            "goles_ida_local": "", "goles_ida_visitante": "",
            "goles_vuelta_local": "", "goles_vuelta_visitante": "",
            "ganador": "",
        }
        for i in range(8)
    ]


def _sortear_octavos_pendientes(bombo1: list[str], cantidad_llaves: int,
                                 rng: random.Random | None = None) -> list[dict]:
    """Sorteo abierto de Octavos, SIN restricción de país (ver
    docstring del módulo): asigna al azar cada equipo del Bombo 1 (1°
    de zona de Sudamericana) a una de las 8 llaves de Playoffs -- el
    rival de esa llave todavía no se conoce (se completa recién cuando
    se simulan los Playoffs, ver EstadisticasSudamericana.
    simular_sudamericana()). El Bombo 1 define la vuelta como local; el
    ganador de Playoffs (Bolillero 2) abre la serie de local."""
    if len(bombo1) != cantidad_llaves:
        raise ValueError(f"Se necesitan {cantidad_llaves} equipos en el Bombo 1, se recibieron {len(bombo1)}.")
    rng = rng or random.Random()

    bombo1_sorteado = bombo1[:]
    rng.shuffle(bombo1_sorteado)

    return [
        {
            "ronda": "octavos", "llave": i + 1,
            "equipo_ida_local": "", "equipo_vuelta_local": bombo1_sorteado[i],
            "goles_ida_local": "", "goles_ida_visitante": "",
            "goles_vuelta_local": "", "goles_vuelta_visitante": "",
            "ganador": "",
        }
        for i in range(cantidad_llaves)
    ]
