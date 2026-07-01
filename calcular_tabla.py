# -*- coding: utf-8 -*-
"""
calcular_tabla.py

Mantiene datos/tabla.csv al día aplicando SOLO los partidos nuevos que
trae cada actualización de Promiedos, en vez de recalcular toda la
tabla desde el historial completo de resultados.csv.

Por qué así (y no reconstruyendo todo desde resultados.csv): al
comparar, resultados.csv tiene errores en el historial de varios
equipos (partidos con el resultado mal cargado o faltantes), mientras
que tabla.csv es la fuente confiable de los datos reales de hoy. Si
recalculáramos todo desde resultados.csv arrastraríamos esos errores.
En cambio, aplicando solo los partidos NUEVOS (los que
actualizar_resultados.py acaba de bajar de Promiedos en esta corrida)
sobre la tabla.csv que ya está bien, el pasado nunca se toca y la
tabla se mantiene correcta hacia adelante.

Uso:
    from calcular_tabla import actualizar_tabla_con_partidos
    actualizar_tabla_con_partidos(cargados)   # cargados = partidos ya
                                               # traducidos a nombres
                                               # locales, mismo formato
                                               # que usa
                                               # actualizar_resultados.py
"""
import csv
from pathlib import Path

DATOS_DIR = Path(__file__).resolve().parent / "datos"
TABLA_CSV = DATOS_DIR / "tabla.csv"

CAMPOS_TABLA = [
    "zona", "posicion", "equipo", "partidos_jugados", "ganados",
    "empatados", "perdidos", "gf", "gc", "dg", "puntos",
]
CAMPOS_NUMERICOS = [
    "posicion", "partidos_jugados", "ganados", "empatados",
    "perdidos", "gf", "gc", "dg", "puntos",
]


def _leer_tabla():
    with open(TABLA_CSV, newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    for f in filas:
        for campo in CAMPOS_NUMERICOS:
            f[campo] = int(f[campo])
    return filas


def aplicar_partidos(filas_tabla, partidos):
    """
    Devuelve una copia de filas_tabla con los `partidos` nuevos
    aplicados (goles, puntos, PJ, etc.) y las posiciones recalculadas
    dentro de cada zona. No modifica filas_tabla in place.

    `partidos`: lista de dicts con equipo_local, equipo_visitante,
    goles_local, goles_visitante (mismo shape que `cargados` en
    actualizar_resultados.py).
    """
    indice = {f["equipo"]: dict(f) for f in filas_tabla}
    equipos_desconocidos = set()

    for p in partidos:
        local = p["equipo_local"]
        visitante = p["equipo_visitante"]
        if local not in indice or visitante not in indice:
            if local not in indice:
                equipos_desconocidos.add(local)
            if visitante not in indice:
                equipos_desconocidos.add(visitante)
            continue  # no tocamos la tabla si no reconocemos el equipo

        gl = int(p["goles_local"])
        gv = int(p["goles_visitante"])
        fl = indice[local]
        fv = indice[visitante]

        fl["partidos_jugados"] += 1
        fv["partidos_jugados"] += 1
        fl["gf"] += gl
        fl["gc"] += gv
        fv["gf"] += gv
        fv["gc"] += gl

        if gl > gv:
            fl["ganados"] += 1
            fl["puntos"] += 3
            fv["perdidos"] += 1
        elif gl < gv:
            fv["ganados"] += 1
            fv["puntos"] += 3
            fl["perdidos"] += 1
        else:
            fl["empatados"] += 1
            fl["puntos"] += 1
            fv["empatados"] += 1
            fv["puntos"] += 1

        fl["dg"] = fl["gf"] - fl["gc"]
        fv["dg"] = fv["gf"] - fv["gc"]

    if equipos_desconocidos:
        print(f"  [aviso calcular_tabla] equipo(s) sin fila en tabla.csv, "
              f"no se pudo actualizar su posición: {sorted(equipos_desconocidos)}")

    filas = list(indice.values())
    filas.sort(key=lambda f: (f["zona"], -f["puntos"], -f["dg"], -f["gf"], f["equipo"]))

    zona_actual = None
    contador = 0
    for f in filas:
        if f["zona"] != zona_actual:
            zona_actual = f["zona"]
            contador = 0
        contador += 1
        f["posicion"] = contador

    return [{c: f[c] for c in CAMPOS_TABLA} for f in filas]


def guardar_tabla(filas):
    """Escribe datos/tabla.csv con las filas dadas."""
    DATOS_DIR.mkdir(exist_ok=True)
    with open(TABLA_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS_TABLA)
        writer.writeheader()
        writer.writerows(filas)


def actualizar_tabla_con_partidos(partidos_nuevos, imprimir=True):
    """
    Punto de entrada principal: lee tabla.csv, le aplica los partidos
    nuevos y lo vuelve a guardar. Si `partidos_nuevos` está vacío, no
    hace nada (no reescribe el archivo innecesariamente).
    """
    if not partidos_nuevos:
        return None

    filas_actuales = _leer_tabla()
    filas_nuevas = aplicar_partidos(filas_actuales, partidos_nuevos)
    guardar_tabla(filas_nuevas)

    if imprimir:
        print(f"  tabla.csv actualizada con {len(partidos_nuevos)} partido(s) nuevo(s).")

    return filas_nuevas


if __name__ == "__main__":
    print("Este módulo se usa desde actualizar_resultados.py con los partidos "
          "nuevos de cada corrida; no tiene un modo standalone con datos propios.")
