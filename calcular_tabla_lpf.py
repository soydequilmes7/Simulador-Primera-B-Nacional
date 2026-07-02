# -*- coding: utf-8 -*-
"""
calcular_tabla_lpf.py

Actualiza datos/tabla_lpf.csv sumando el resultado de partidos ya
jugados. Es el equivalente para LPF de calcular_tabla.py (Nacional),
pero implementado de cero acá porque no tengo el original a la vista
-- si tu calcular_tabla.py hace algo distinto (por ejemplo algún
criterio de desempate particular), decime y lo ajusto para que
matcheen los dos.

Reglas de la tabla (estándar AFA):
  - 3 puntos por ganar, 1 por empatar, 0 por perder.
  - Orden dentro de cada zona: puntos desc, diferencia de gol desc,
    goles a favor desc, nombre del equipo (para que el orden sea
    estable si sigue habiendo empate).
  - No mezcla equipos entre zonas (cada equipo se queda en la zona que
    ya tenía en tabla_lpf.csv; los partidos interzonales, como los de
    Fecha 6, sí sirven para sumar puntos/goles de cada equipo, pero no
    cambian de zona a nadie).

Uso programático:
    from calcular_tabla_lpf import actualizar_tabla_con_partidos
    actualizar_tabla_con_partidos(partidos_jugados)  # lista de dicts
        # cada dict con: equipo_local, equipo_visitante,
        # goles_local, goles_visitante
"""
import csv
import os

CAMPOS_TABLA = ["zona", "posicion", "equipo", "partidos_jugados", "ganados",
                "empatados", "perdidos", "gf", "gc", "dg", "puntos"]

TABLA_CSV_DEFAULT = "tabla_lpf.csv"


def _leer_tabla(path):
    with open(path, newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    # Todo a int menos zona/equipo
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
        raise KeyError(f"Equipo(s) no encontrados en tabla_lpf.csv: {faltantes}")

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
    por_zona = {}
    for fila in filas:
        por_zona.setdefault(fila["zona"], []).append(fila)

    for zona, equipos in por_zona.items():
        equipos.sort(key=lambda e: (-e["puntos"], -e["dg"], -e["gf"], e["equipo"]))
        for i, equipo in enumerate(equipos, start=1):
            equipo["posicion"] = i

    # Reconstruye la lista completa respetando el orden zona A, zona B, ...
    filas_ordenadas = []
    for zona in sorted(por_zona.keys()):
        filas_ordenadas.extend(por_zona[zona])
    return filas_ordenadas


def actualizar_tabla_con_partidos(partidos_jugados, tabla_path=TABLA_CSV_DEFAULT, imprimir=True):
    """partidos_jugados: lista de dicts con equipo_local, equipo_visitante,
    goles_local, goles_visitante (mismo formato que devuelve
    scraper_promiedos_lpf.obtener_partidos_jugados_lpf())."""
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
    print("Este módulo se usa importado desde actualizar_resultados_lpf.py, "
          "no tiene un modo standalone (no sabe qué partidos aplicar).")
