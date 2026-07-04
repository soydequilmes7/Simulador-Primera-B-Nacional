# -*- coding: utf-8 -*-
"""
calcular_tabla_federal.py

Actualiza datos/tabla_federal_a.csv sumando el resultado de partidos ya
jugados. Calcado de calcular_tabla_bmetro.py, con una diferencia clave:
el Federal A SÍ tiene 4 zonas reales (a diferencia de B Metro, que usa
una zona ficticia "Unica"), así que las posiciones se reordenan POR
ZONA, no globalmente sobre los 37 clubes.

Reglas de la tabla:
  - 3 puntos por ganar, 1 por empatar, 0 por perder.
  - Orden dentro de cada zona: puntos desc, diferencia de gol desc,
    goles a favor desc, nombre del equipo (para estabilidad si sigue
    habiendo empate) -- mismo criterio que el resto del proyecto.

Uso programático:
    from calcular_tabla_federal import actualizar_tabla_con_partidos
    actualizar_tabla_con_partidos(partidos_jugados)
        # lista de dicts con: equipo_local, equipo_visitante,
        # goles_local, goles_visitante
"""
from __future__ import annotations

import csv
import os

CAMPOS_TABLA = ["zona", "posicion", "equipo", "partidos_jugados", "ganados",
                "empatados", "perdidos", "gf", "gc", "dg", "puntos"]

TABLA_CSV_DEFAULT = "tabla_federal_a.csv"


def _leer_tabla(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    for fila in filas:
        for campo in ("posicion", "partidos_jugados", "ganados", "empatados",
                      "perdidos", "gf", "gc", "dg", "puntos"):
            fila[campo] = int(fila[campo])
    return filas


def _escribir_tabla(path: str, filas: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS_TABLA)
        writer.writeheader()
        writer.writerows(filas)


def _aplicar_partido(indice_por_equipo: dict[str, dict], equipo_local: str,
                      equipo_visitante: str, gl: int, gv: int) -> None:
    local = indice_por_equipo.get(equipo_local)
    visitante = indice_por_equipo.get(equipo_visitante)
    if local is None or visitante is None:
        faltantes = [e for e in (equipo_local, equipo_visitante) if indice_por_equipo.get(e) is None]
        raise KeyError(f"Equipo(s) no encontrados en tabla_federal_a.csv: {faltantes}")

    local["partidos_jugados"] += 1
    visitante["partidos_jugados"] += 1
    local["gf"] += gl
    local["gc"] += gv
    visitante["gf"] += gv
    visitante["gc"] += gl
    local["dg"] = local["gf"] - local["gc"]
    visitante["dg"] = visitante["gf"] - visitante["gc"]

    if gl > gv:
        local["ganados"] += 1
        local["puntos"] += 3
        visitante["perdidos"] += 1
    elif gl < gv:
        visitante["ganados"] += 1
        visitante["puntos"] += 3
        local["perdidos"] += 1
    else:
        local["empatados"] += 1
        visitante["empatados"] += 1
        local["puntos"] += 1
        visitante["puntos"] += 1


def _reordenar_posiciones(filas: list[dict]) -> list[dict]:
    """A diferencia de B Metro (una sola zona "Unica"), acá hay que
    ordenar y numerar cada zona por separado -- si no, la posición 1
    global le tocaría siempre a la misma zona más fuerte, y las otras
    3 zonas nunca tendrían un verdadero 1°."""
    por_zona: dict[str, list[dict]] = {}
    for fila in filas:
        por_zona.setdefault(fila["zona"], []).append(fila)

    resultado = []
    for zona in sorted(por_zona):
        equipos_zona = por_zona[zona]
        equipos_zona.sort(key=lambda e: (-e["puntos"], -e["dg"], -e["gf"], e["equipo"]))
        for i, equipo in enumerate(equipos_zona, start=1):
            equipo["posicion"] = i
        resultado.extend(equipos_zona)
    return resultado


def actualizar_tabla_con_partidos(partidos_jugados: list[dict], tabla_path: str = TABLA_CSV_DEFAULT,
                                   imprimir: bool = True) -> list[dict]:
    """partidos_jugados: lista de dicts con equipo_local, equipo_visitante,
    goles_local, goles_visitante (mismo formato que devuelve
    scraper_promiedos_federal.obtener_partidos_jugados_federal())."""
    if not os.path.exists(tabla_path):
        raise FileNotFoundError(f"No se encontró {tabla_path}")

    filas = _leer_tabla(tabla_path)
    indice = {f["equipo"]: f for f in filas}

    aplicados = 0
    for p in partidos_jugados:
        _aplicar_partido(
            indice,
            p["equipo_local"],
            p["equipo_visitante"],
            int(p["goles_local"]),
            int(p["goles_visitante"]),
        )
        aplicados += 1

    filas = _reordenar_posiciones(filas)
    _escribir_tabla(tabla_path, filas)

    if imprimir:
        print(f"  Tabla actualizada ({aplicados} partidos aplicados) -> {tabla_path}")

    return filas


if __name__ == "__main__":
    print("Este módulo se usa importado desde actualizar_resultados_federal.py, "
          "no tiene un modo standalone (no sabe qué partidos aplicar).")
