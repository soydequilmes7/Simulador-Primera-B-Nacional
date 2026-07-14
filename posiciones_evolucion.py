# -*- coding: utf-8 -*-
"""
posiciones_evolucion.py

Reconstruye la posición de cada equipo DESPUÉS de cada fecha jugada,
para alimentar el gráfico "Evolución de posiciones" del frontend.

No recalcula nada nuevo ni vuelve a simular: recorre los partidos que
YA están cargados en Supabase (matches, status="played", mismos que
usa calcular_tabla*.py para mantener tabla.csv al día) en orden de
jornada, aplicando el mismo criterio de desempate que el resto del
proyecto (puntos desc, diferencia de gol desc, goles a favor desc,
nombre asc), sin mezclar equipos entre zonas.

Uso programático:
    from posiciones_evolucion import calcular_evolucion
    evolucion = calcular_evolucion(partidos_jugados, zona_por_club)
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

CRITERIO_ORDEN = ("puntos", "dg", "gf", "equipo")


def _snapshot_inicial(zona_por_club: dict[str, str]) -> dict[str, dict]:
    """Arranca cada club en cero, en la zona que ya tiene hoy en la tabla."""
    return {
        equipo: {
            "equipo": equipo,
            "zona": zona,
            "puntos": 0,
            "pj": 0,
            "gf": 0,
            "gc": 0,
            "dg": 0,
        }
        for equipo, zona in zona_por_club.items()
    }


def _aplicar_partido(stats: dict[str, dict], partido: dict) -> None:
    """Suma un partido jugado a las stats acumuladas de ambos equipos."""
    local = partido["equipo_local"]
    visitante = partido["equipo_visitante"]
    if local not in stats or visitante not in stats:
        # Equipo sin fila en la tabla actual (p.ej. recién promovido a
        # mitad de temporada): no lo podemos ubicar en una zona, se
        # ignora el partido para la evolución (no rompe el resto).
        return

    gl = int(partido["goles_local"])
    gv = int(partido["goles_visitante"])
    fl, fv = stats[local], stats[visitante]

    fl["pj"] += 1
    fv["pj"] += 1
    fl["gf"] += gl
    fl["gc"] += gv
    fv["gf"] += gv
    fv["gc"] += gl
    fl["dg"] = fl["gf"] - fl["gc"]
    fv["dg"] = fv["gf"] - fv["gc"]

    if gl > gv:
        fl["puntos"] += 3
    elif gl < gv:
        fv["puntos"] += 3
    else:
        fl["puntos"] += 1
        fv["puntos"] += 1


def _posiciones_por_zona(stats: dict[str, dict]) -> dict[str, int]:
    """Ordena cada zona por separado y devuelve {equipo: posición (1-based)}."""
    por_zona: dict[str, list[dict]] = defaultdict(list)
    for fila in stats.values():
        por_zona[fila["zona"]].append(fila)

    posiciones: dict[str, int] = {}
    for filas in por_zona.values():
        filas.sort(key=lambda f: (-f["puntos"], -f["dg"], -f["gf"], f["equipo"]))
        for i, fila in enumerate(filas, start=1):
            posiciones[fila["equipo"]] = i
    return posiciones


def _partido_por_equipo(partidos: list[dict]) -> dict[str, dict]:
    """Para una lista de partidos de UNA fecha, arma {equipo: {rival, local,
    gf, gc}} de cada equipo que jugó esa fecha (lo usa el tooltip del
    frontend para mostrar el resultado del último partido)."""
    resultado: dict[str, dict] = {}
    for p in partidos:
        local = p["equipo_local"]
        visitante = p["equipo_visitante"]
        gl = int(p["goles_local"])
        gv = int(p["goles_visitante"])
        resultado[local] = {"rival": visitante, "local": True, "gf": gl, "gc": gv}
        resultado[visitante] = {"rival": local, "local": False, "gf": gv, "gc": gl}
    return resultado


def calcular_evolucion(
    partidos_jugados: Iterable[dict],
    zona_por_club: dict[str, str],
) -> dict[str, list[dict]]:
    """
    Devuelve, para cada equipo, la lista de snapshots {jornada, posicion,
    puntos, dg, zona, partido} luego de cada fecha en la que se jugó al
    menos un partido. `partido` es {rival, local, gf, gc} si ESE equipo
    jugó esa fecha, o None si no le tocaba (fecha libre/interzonal).
    Las fechas sin ningún partido (suspendidas, todavía no jugadas) no
    generan snapshot.
    """
    partidos_por_jornada: dict[int, list[dict]] = defaultdict(list)
    for p in partidos_jugados:
        jornada = p.get("jornada")
        if jornada is None:
            continue
        partidos_por_jornada[int(jornada)].append(p)

    stats = _snapshot_inicial(zona_por_club)
    evolucion: dict[str, list[dict]] = {equipo: [] for equipo in zona_por_club}

    for jornada in sorted(partidos_por_jornada):
        partidos_de_la_fecha = partidos_por_jornada[jornada]
        for partido in partidos_de_la_fecha:
            _aplicar_partido(stats, partido)

        partido_por_equipo = _partido_por_equipo(partidos_de_la_fecha)
        posiciones = _posiciones_por_zona(stats)
        for equipo, fila in stats.items():
            evolucion[equipo].append({
                "jornada": jornada,
                "posicion": posiciones[equipo],
                "puntos": fila["puntos"],
                "dg": fila["dg"],
                "zona": fila["zona"],
                "partido": partido_por_equipo.get(equipo),
            })


    return evolucion


def tamano_por_zona(zona_por_club: dict[str, str]) -> dict[str, int]:
    """Cantidad de equipos por zona, para que el frontend arme las bandas
    de ascenso/reducido/descenso sin hardcodear la cantidad de equipos."""
    conteo: dict[str, int] = defaultdict(int)
    for zona in zona_por_club.values():
        conteo[zona] += 1
    return dict(conteo)


if __name__ == "__main__":
    print("Este módulo se usa desde api/index.py (endpoint "
          "/api/evolucion-posiciones-nacional); no tiene modo standalone.")
