# -*- coding: utf-8 -*-
"""
calcular_tabla_bmetro.py

Actualiza datos/tabla_bmetro.csv sumando el resultado de partidos ya
jugados. B Metropolitana es una tabla única (todos contra todos, sin
zonas), pero se mantiene la columna "zona" con el valor constante
"Unica" en todas las filas para poder reusar tal cual la clase base
Estadisticas (modelos/estadisticas.py) de Nacional, que agrupa todo
por esa columna -- con una sola zona, se comporta como una tabla
única sin tocar nada del motor genérico.

Reglas de la tabla:
  - 3 puntos por ganar, 1 por empatar, 0 por perder.
  - Orden: puntos desc, diferencia de gol desc, goles a favor desc,
    nombre del equipo (para estabilidad si sigue habiendo empate).

Uso programático:
    from calcular_tabla_bmetro import actualizar_tabla_con_partidos
    actualizar_tabla_con_partidos(partidos_jugados)
        # lista de dicts con: equipo_local, equipo_visitante,
        # goles_local, goles_visitante
"""
import csv
import os

CAMPOS_TABLA = ["zona", "posicion", "equipo", "partidos_jugados", "ganados",
                "empatados", "perdidos", "gf", "gc", "dg", "puntos"]

TABLA_CSV_DEFAULT = "tabla_bmetro.csv"


def _leer_tabla(path):
    with open(path, newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    for fila in filas:
        for campo in ("posicion", "partidos_jugados", "ganados", "empatados",
                      "perdidos", "gf", "gc", "dg", "puntos"):
            fila[campo] = int(fila[campo])
    return filas


def _escribir_tabla(path, filas):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS_TABLA)
        writer.writeheader()
        writer.writerows(filas)


def _aplicar_partido(indice_por_equipo, equipo_local, equipo_visitante, gl, gv):
    local = indice_por_equipo.get(equipo_local)
    visitante = indice_por_equipo.get(equipo_visitante)
    if local is None or visitante is None:
        faltantes = [e for e in (equipo_local, equipo_visitante) if indice_por_equipo.get(e) is None]
        raise KeyError(f"Equipo(s) no encontrados en tabla_bmetro.csv: {faltantes}")

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


def _reordenar_posiciones(filas):
    filas.sort(key=lambda e: (-e["puntos"], -e["dg"], -e["gf"], e["equipo"]))
    for i, equipo in enumerate(filas, start=1):
        equipo["posicion"] = i
    return filas


def actualizar_tabla_con_partidos(partidos_jugados, tabla_path=TABLA_CSV_DEFAULT, imprimir=True):
    """partidos_jugados: lista de dicts con equipo_local, equipo_visitante,
    goles_local, goles_visitante (mismo formato que devuelve
    scraper_promiedos_bmetro.obtener_partidos_jugados_bmetro())."""
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
    print("Este módulo se usa importado desde actualizar_resultados_bmetro.py, "
          "no tiene un modo standalone (no sabe qué partidos aplicar).")
