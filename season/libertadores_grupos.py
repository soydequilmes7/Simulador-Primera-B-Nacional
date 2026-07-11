# -*- coding: utf-8 -*-
"""
season/libertadores_grupos.py

Fase de grupos de Copa Libertadores para Modo Temporada: 8 zonas de 4
equipos, todos contra todos a ida y vuelta (6 fechas por zona), usando
el mismo motor de partido (Poisson + Dixon-Coles) que ya usa
modelos/estadisticas_libertadores.py para octavos -- ver
EstadisticasLibertadores.crear_equipos_desde_elo() y
Estadisticas.simular_partido().

Desempate real de CONMEBOL (Reglamento Libertadores, capítulo
"Fase de Grupos"), aplicado EN ORDEN, sin volver atrás una vez usado
uno (si un criterio ya separó dos equipos, los siguientes no se
vuelven a evaluar entre ellos):

    1. Puntos.
    2. Diferencia de gol en los partidos jugados ENTRE los equipos
       empatados (enfrentamientos directos).
    3. Goles a favor en esos mismos enfrentamientos directos.
    4. Diferencia de gol general (todos los partidos de la zona).
    5. Goles a favor general.
    6. Sorteo -- el reglamento real sigue con tarjetas, pero acá no se
       simulan tarjetas (ver limitación en el docstring de
       simular_partido()), así que el último desempate posible es
       aleatorio, no fabricado.

Salida: para cada zona, tabla ordenada (posición, 1° y 2° clasifican a
octavos, 3° queda marcado para Sudamericana aunque esa integración no
está resuelta todavía -- ver HANDOFF pendiente) + el detalle de los 12
partidos jugados, mismo shape por partido que usa el resto del
proyecto (golesLocal/golesVisitante).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from itertools import permutations

from modelos.estadisticas_libertadores import EstadisticasLibertadores
from season.libertadores_sorteo import sortear_grupos

FECHAS_POR_ZONA = 6
CLASIFICAN_A_OCTAVOS = 2


@dataclass
class FilaTablaZona:
    equipo: str
    pais: str
    puntos: int = 0
    pj: int = 0
    pg: int = 0
    pe: int = 0
    pp: int = 0
    gf: int = 0
    gc: int = 0

    @property
    def dg(self) -> int:
        return self.gf - self.gc


@dataclass
class ZonaJugada:
    letra: str
    partidos: list[dict] = field(default_factory=list)
    tabla: list[FilaTablaZona] = field(default_factory=list)


def _jugar_zona(motor: EstadisticasLibertadores, letra: str, equipos_pais: dict[str, str],
                 rng: random.Random) -> ZonaJugada:
    """Juega las 12 fechas de una zona (4 equipos, todos contra todos
    ida y vuelta) y arma la tabla ya ordenada con los desempates
    reales de CONMEBOL."""
    equipos = list(equipos_pais.keys())
    partidos = []
    filas = {e: FilaTablaZona(equipo=e, pais=equipos_pais[e]) for e in equipos}

    for local, visitante in permutations(equipos, 2):
        gl, gv = motor.simular_partido(local, visitante)
        partidos.append({"local": local, "visitante": visitante, "golesLocal": gl, "golesVisitante": gv})

        fl, fv = filas[local], filas[visitante]
        fl.pj += 1
        fv.pj += 1
        fl.gf += gl
        fl.gc += gv
        fv.gf += gv
        fv.gc += gl
        if gl > gv:
            fl.pg += 1
            fl.puntos += 3
            fv.pp += 1
        elif gl < gv:
            fv.pg += 1
            fv.puntos += 3
            fl.pp += 1
        else:
            fl.pe += 1
            fv.pe += 1
            fl.puntos += 1
            fv.puntos += 1

    tabla = _ordenar_tabla(list(filas.values()), partidos, rng)
    return ZonaJugada(letra=letra, partidos=partidos, tabla=tabla)


def _ordenar_tabla(filas: list[FilaTablaZona], partidos: list[dict], rng: random.Random) -> list[FilaTablaZona]:
    """Aplica el desempate real de CONMEBOL en cascada (ver docstring
    del módulo). Trabaja por grupos de empatados: separa primero por
    puntos, y dentro de cada grupo empatado prueba enfrentamientos
    directos antes de caer a la diferencia de gol general."""
    por_puntos: dict[int, list[FilaTablaZona]] = {}
    for f in filas:
        por_puntos.setdefault(f.puntos, []).append(f)

    resultado: list[FilaTablaZona] = []
    for puntos in sorted(por_puntos, reverse=True):
        grupo = por_puntos[puntos]
        resultado.extend(_desempatar_grupo(grupo, partidos, rng) if len(grupo) > 1 else grupo)
    return resultado


def _desempatar_grupo(grupo: list[FilaTablaZona], partidos: list[dict], rng: random.Random) -> list[FilaTablaZona]:
    nombres_grupo = {f.equipo for f in grupo}
    directos = [p for p in partidos if p["local"] in nombres_grupo and p["visitante"] in nombres_grupo]

    dg_directo: dict[str, int] = {f.equipo: 0 for f in grupo}
    gf_directo: dict[str, int] = {f.equipo: 0 for f in grupo}
    for p in directos:
        dg_directo[p["local"]] += p["golesLocal"] - p["golesVisitante"]
        dg_directo[p["visitante"]] += p["golesVisitante"] - p["golesLocal"]
        gf_directo[p["local"]] += p["golesLocal"]
        gf_directo[p["visitante"]] += p["golesVisitante"]

    desempate = rng.random  # criterio 6: sorteo -- valor distinto por fila, no fabricado
    ruido = {f.equipo: desempate() for f in grupo}

    return sorted(
        grupo,
        key=lambda f: (dg_directo[f.equipo], gf_directo[f.equipo], f.dg, f.gf, ruido[f.equipo]),
        reverse=True,
    )


def jugar_fase_de_grupos(zonas_sorteadas, elo_por_equipo: dict[str, float],
                          pais_por_equipo: dict[str, str],
                          rng: random.Random | None = None) -> list[ZonaJugada]:
    """zonas_sorteadas: lista de ZonaSorteada (ver
    season/libertadores_sorteo.py::sortear_grupos()).
    elo_por_equipo / pais_por_equipo: salen de
    ClasificacionLibertadores (ver season/libertadores_manager.py) --
    se recalcula el Elo relativo POR ZONA (4 equipos, no 32), mismo
    criterio que ya usa el cuadro de octavos con sus 16.

    Devuelve una ZonaJugada por zona, en el mismo orden recibido.
    """
    rng = rng or random.Random()
    resultado = []
    for zona in zonas_sorteadas:
        motor = EstadisticasLibertadores()
        motor.crear_equipos_desde_elo(zona.equipos, elo_por_equipo)
        equipos_pais = {e: pais_por_equipo[e] for e in zona.equipos}
        resultado.append(_jugar_zona(motor, zona.letra, equipos_pais, rng))
    return resultado


def armar_bombos_octavos(zonas_jugadas: list[ZonaJugada]) -> tuple[list[str], list[str]]:
    """De las 8 zonas ya jugadas arma (primeros, segundos): 8 nombres
    cada uno, en el orden real de la posición 1/2 dentro de su propia
    zona (A, B, C, ... H) -- listo para pasarle a armar_cuadro_octavos()
    para construir el cuadro que espera
    EstadisticasLibertadores.simular_libertadores()."""
    primeros = [z.tabla[0].equipo for z in zonas_jugadas]
    segundos = [z.tabla[1].equipo for z in zonas_jugadas]
    return primeros, segundos


def armar_cuadro_octavos(primeros: list[str], segundos: list[str],
                          pais_por_equipo: dict[str, str]) -> list[dict]:
    """Empareja bombo 1 (primeros) contra bombo 2 (segundos), evitando
    que dos equipos del mismo país se crucen. Punto de partida: orden
    inverso (primero[0] vs segundo[7], primero[1] vs segundo[6], ...),
    igual que el criterio real de CONMEBOL. Si esa asignación directa
    tiene algún choque de país, se busca con backtracking la
    asignación válida más parecida posible al orden inverso (un simple
    intercambio hacia adelante no alcanza cuando el choque cae en las
    últimas llaves, sin margen para reacomodar -- ver
    season/validar_libertadores_grupos.py). Devuelve filas con el
    mismo shape que datos/libertadores_cuadro.csv (sin resultados
    todavía), lista para pasarle a EstadisticasLibertadores.cuadro."""
    if len(primeros) != 8 or len(segundos) != 8:
        raise ValueError(f"Se necesitan 8 primeros y 8 segundos, se recibieron {len(primeros)}/{len(segundos)}.")

    orden_inverso = list(reversed(segundos))
    # Para cada primero, candidatos de segundo ordenados por cercanía a
    # su posición "natural" (orden inverso) -- así el backtracking, si
    # tiene margen para elegir, prefiere quedarse lo más cerca posible
    # del criterio real.
    preferencia = [sorted(range(8), key=lambda j, i=i: abs(j - i)) for i in range(8)]

    asignacion = _backtracking_sin_choque_pais(primeros, orden_inverso, pais_por_equipo, preferencia)
    if asignacion is None:
        raise ValueError(
            "No se pudo armar un cuadro de octavos sin cruces de mismo país -- un país "
            "concentra demasiados equipos en los mismos bombos. Revisar QUOTAS_PAIS."
        )

    return [
        {
            "ronda": "octavos", "llave": i + 1,
            "equipo_ida_local": primeros[i], "equipo_vuelta_local": asignacion[i],
            "goles_ida_local": "", "goles_ida_visitante": "",
            "goles_vuelta_local": "", "goles_vuelta_visitante": "",
            "ganador": "",
        }
        for i in range(8)
    ]


def _backtracking_sin_choque_pais(primeros, orden_inverso, pais_por_equipo, preferencia,
                                   i: int = 0, usados: frozenset = frozenset()):
    """Asigna, en orden de primeros[0..7], un segundo distinto para
    cada uno (sin repetir y sin compartir país), probando primero las
    posiciones más cercanas al orden inverso real. Devuelve la lista
    de 8 asignaciones o None si no hay ninguna combinación posible."""
    if i == len(primeros):
        return []
    pais_local = pais_por_equipo[primeros[i]]
    for j in preferencia[i]:
        if j in usados:
            continue
        candidato = orden_inverso[j]
        if pais_por_equipo[candidato] == pais_local:
            continue
        resto = _backtracking_sin_choque_pais(
            primeros, orden_inverso, pais_por_equipo, preferencia, i + 1, usados | {j},
        )
        if resto is not None:
            return [candidato] + resto
    return None


def simular_temporada_libertadores(
    clasificados_argentinos: list[str],
    elo_argentinos: dict[str, float] | None = None,
    rng: random.Random | None = None,
    manager=None,
) -> dict:
    """Orquesta el pipeline completo de una temporada de Libertadores
    en Modo Temporada: cupos+rotación (LibertadoresManager) -> sorteo
    de 8 zonas -> fase de grupos (12 fechas x zona) -> cuadro de
    octavos -> octavos/cuartos/semis/final (motor ya existente de
    modelos/estadisticas_libertadores.py). Pensado para llamarse una
    vez por temporada desde SeasonEngine.correr_temporada() o desde
    api/index.py (ver season/validar_libertadores_grupos.py para el
    detalle de cada paso probado por separado).

    manager: LibertadoresManager inyectable (tests / pool custom). Si
    no se pasa, se instancia uno normal (lee el pool real del CSV).

    Devuelve un dict ya JSON-safe (listo para meter directo en la
    respuesta de un endpoint):
        {
          "avisos": [...],
          "zonas": [{"letra", "tabla": [...], "partidos": [...]}, ...],
          "cuadro_octavos": [...],
          "rondas": {ronda: [detalle_llave, ...]},
          "campeon": str,
        }
    """
    from season.libertadores_manager import LibertadoresManager

    rng = rng or random.Random()
    manager = manager or LibertadoresManager()
    clasificacion = manager.armar_clasificacion(clasificados_argentinos, elo_argentinos, rng=rng)

    zonas_sorteadas = sortear_grupos(clasificacion, rng=rng)
    elo_por_equipo = clasificacion.elo_por_equipo()
    pais_por_equipo = {c.equipo: c.pais for c in clasificacion.equipos}
    zonas_jugadas = jugar_fase_de_grupos(zonas_sorteadas, elo_por_equipo, pais_por_equipo, rng=rng)

    primeros, segundos = armar_bombos_octavos(zonas_jugadas)
    cuadro_octavos = armar_cuadro_octavos(primeros, segundos, pais_por_equipo)

    motor = EstadisticasLibertadores()
    motor.cuadro = cuadro_octavos
    motor.crear_equipos_desde_elo({c.equipo for c in clasificacion.equipos}, elo_por_equipo)
    rondas_detalle, campeon = motor.simular_libertadores()

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
        "cuadro_octavos": cuadro_octavos,
        "rondas": rondas_detalle,
        "campeon": campeon,
    }
