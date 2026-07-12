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

Reglamento real simplificado (mismo criterio que Libertadores, ver
season/libertadores_grupos.py): 32 clasificados, 8 zonas de 4, ida y
vuelta. El 1° de cada zona va directo a Octavos; el 2° va a Playoffs
de Octavos contra un 3° de zona de Libertadores (ver ese módulo -- por
eso esta función necesita el resultado YA CORRIDO de Libertadores de
la misma temporada como insumo, no solo QualificationManager).

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
from season.libertadores_grupos import jugar_fase_de_grupos, armar_cuadro_octavos

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
    segundos = [z.tabla[1].equipo for z in zonas_jugadas]  # a Playoffs

    terceros_libertadores = [z["tabla"][2]["equipo"] for z in resultado_libertadores["zonas"]]
    pais_terceros_lib = {z["tabla"][2]["equipo"]: z["tabla"][2]["pais"] for z in resultado_libertadores["zonas"]}
    elo_terceros_lib = {t: resultado_libertadores["elo_por_equipo"][t] for t in terceros_libertadores}
    pais_por_equipo_completo = {**pais_por_equipo, **pais_terceros_lib}
    elo_por_equipo_completo = {**elo_por_equipo, **elo_terceros_lib}

    try:
        cuadro_playoffs = armar_cuadro_octavos(segundos, terceros_libertadores, pais_por_equipo_completo)
        aviso_playoffs = None
    except ValueError:
        # Mismo motivo que el fallback de _armar_octavos_desde_playoffs
        # más abajo: con varios cupos argentinos de cada lado repartidos
        # en 8 zonas, a veces no hay forma de evitar TODOS los cruces de
        # mismo país. No debería tumbar la simulación por eso.
        cuadro_playoffs = [
            {
                "ronda": "playoffs", "llave": i + 1,
                "equipo_ida_local": segundos[i], "equipo_vuelta_local": list(reversed(terceros_libertadores))[i],
                "goles_ida_local": "", "goles_ida_visitante": "",
                "goles_vuelta_local": "", "goles_vuelta_visitante": "",
                "ganador": "",
            }
            for i in range(8)
        ]
        aviso_playoffs = (
            "No se pudo armar Playoffs evitando todos los cruces de mismo país entre "
            "un 2° de zona de Sudamericana y un 3° de zona de Libertadores -- se usó el "
            "orden de ranking simple."
        )
    for fila in cuadro_playoffs:
        fila["ronda"] = "playoffs"

    cuadro_octavos, aviso_octavos = _armar_octavos_desde_playoffs(primeros, cuadro_playoffs, pais_por_equipo_completo)

    motor = EstadisticasSudamericana()
    motor.cuadro_playoffs = cuadro_playoffs
    motor.cuadro = cuadro_octavos
    motor._octavos_vuelta_original = {int(f["llave"]): "" for f in cuadro_octavos}
    motor.crear_equipos_desde_elo(
        {c.equipo for c in clasificacion.equipos} | set(terceros_libertadores),
        elo_por_equipo_completo,
    )
    rondas_detalle, campeon = motor.simular_sudamericana()

    return {
        "avisos": clasificacion.avisos + ([aviso_playoffs] if aviso_playoffs else []) + ([aviso_octavos] if aviso_octavos else []),
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
    }


def _armar_octavos_desde_playoffs(primeros: list[str], cuadro_playoffs: list[dict],
                                   pais_por_equipo: dict[str, str]):
    """Empareja los 8 directos a Octavos (1° de zona de Sudamericana)
    con las 8 llaves de Playoffs, evitando -- cuando se puede -- que el
    directo comparta país con CUALQUIERA de los dos posibles rivales
    de esa llave (todavía no se sabe quién gana el Playoff al momento
    de armar el cuadro).

    A diferencia de armar_cuadro_octavos() (Libertadores, ver
    season/libertadores_grupos.py), acá la restricción es
    frecuentemente IMPOSIBLE de cumplir del todo: con hasta 6 cupos
    argentinos de cada lado repartidos en 8 zonas, es normal que
    Argentina (u otro país con varios cupos) aparezca como país
    prohibido en más llaves de las que hay directos de otros países
    disponibles para taparlas. Por eso, si el backtracking estricto no
    encuentra solución, se cae a un emparejamiento simple por orden de
    ranking (sin la restricción de país) y se devuelve un aviso
    explícito en vez de reventar la simulación -- una llave con cruce
    de mismo país en Octavos es una imperfección de realismo, no un
    error de datos.

    Devuelve (filas_octavos, aviso | None)."""
    if len(primeros) != 8 or len(cuadro_playoffs) != 8:
        raise ValueError(
            f"Se necesitan 8 directos y 8 llaves de playoffs, se recibieron "
            f"{len(primeros)}/{len(cuadro_playoffs)}."
        )

    prohibidos_por_llave = [
        {pais_por_equipo[cruce["equipo_ida_local"]], pais_por_equipo[cruce["equipo_vuelta_local"]]}
        for cruce in cuadro_playoffs
    ]
    preferencia = [sorted(range(8), key=lambda j, i=i: abs(j - i)) for i in range(8)]

    asignacion = _backtracking_octavos_sudamericana(primeros, prohibidos_por_llave, pais_por_equipo, preferencia)
    aviso = None
    if asignacion is None:
        asignacion = primeros
        aviso = (
            "No se pudo armar Octavos evitando todos los cruces de mismo país entre un "
            "directo y los posibles rivales de Playoffs (normal con varios cupos "
            "argentinos repartidos en 8 zonas) -- se usó el orden de ranking simple, "
            "puede haber alguna llave con choque de país."
        )

    return [
        {
            "ronda": "octavos", "llave": i + 1,
            "equipo_ida_local": directo, "equipo_vuelta_local": "",
            "goles_ida_local": "", "goles_ida_visitante": "",
            "goles_vuelta_local": "", "goles_vuelta_visitante": "",
            "ganador": "",
        }
        for i, directo in enumerate(asignacion)
    ], aviso


def _backtracking_octavos_sudamericana(primeros, prohibidos_por_llave, pais_por_equipo, preferencia,
                                        k: int = 0, usados: frozenset = frozenset()):
    if k == len(prohibidos_por_llave):
        return []
    for j in preferencia[k]:
        if j in usados:
            continue
        candidato = primeros[j]
        if pais_por_equipo[candidato] in prohibidos_por_llave[k]:
            continue
        resto = _backtracking_octavos_sudamericana(
            primeros, prohibidos_por_llave, pais_por_equipo, preferencia, k + 1, usados | {j},
        )
        if resto is not None:
            return [candidato] + resto
    return None
