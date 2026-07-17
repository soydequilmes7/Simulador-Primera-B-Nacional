# -*- coding: utf-8 -*-
"""
calcular_tabla_ligapro.py

Actualiza datos/tabla_ligapro.csv sumando el resultado de partidos ya
jugados. Calcado de calcular_tabla_brasileirao.py: 3/1/0 puntos, orden
por puntos desc / dg desc / gf desc / nombre.

LIMITACIÓN CONOCIDA (a diferencia de Brasileirão): este archivo sólo
aplica partidos al día a día de la zona en la que ya estén las filas de
tabla_ligapro.csv -- NO hace la transición de Fase Inicial a Fase Final
(no reasigna la columna "zona" de cada equipo a su hexagonal/cuadrangular
correspondiente ni regenera fixture_ligapro.csv con los cruces reales de
la Fase Final). Esa transición, cuando la Fase Inicial real termine sus
30 fechas, hay que hacerla aparte (a mano o con un script nuevo, en la
línea de lo que promotion_manager.py hace para ascensos/descensos AFA)
antes de seguir cargando resultados reales de la Fase Final. Mientras
tanto, EstadisticasLigaPro.simular_temporada_ligapro() sí resuelve esa
transición automáticamente, pero sólo dentro de una corrida de
simulación (no persiste el cambio de zona en el CSV/Supabase).

Uso programático:
    from calcular_tabla_ligapro import actualizar_tabla_con_partidos
    actualizar_tabla_con_partidos(partidos_jugados)
        # lista de dicts con: equipo_local, equipo_visitante,
        # goles_local, goles_visitante
"""
import csv
import os

CAMPOS_TABLA = ["zona", "posicion", "equipo", "partidos_jugados", "ganados",
                "empatados", "perdidos", "gf", "gc", "dg", "puntos"]

TABLA_CSV_DEFAULT = "tabla_ligapro.csv"


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
        raise KeyError(f"Equipo(s) no encontrados en tabla_ligapro.csv: {faltantes}")

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
    # Ordena posiciones DENTRO de cada zona (relevante una vez que la
    # tabla esté dividida en los 3 grupos de Fase Final).
    filas.sort(key=lambda e: (e["zona"], -e["puntos"], -e["dg"], -e["gf"], e["equipo"]))
    contadores_zona = {}
    for equipo in filas:
        zona = equipo["zona"]
        contadores_zona[zona] = contadores_zona.get(zona, 0) + 1
        equipo["posicion"] = contadores_zona[zona]
    return filas


def actualizar_tabla_con_partidos(partidos_jugados, tabla_path=TABLA_CSV_DEFAULT, imprimir=True):
    """partidos_jugados: lista de dicts con equipo_local, equipo_visitante,
    goles_local, goles_visitante."""
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
    print("Este módulo se usa importado desde actualizar_resultados_ligapro.py, "
          "no tiene un modo standalone (no sabe qué partidos aplicar).")
