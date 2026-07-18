# -*- coding: utf-8 -*-
"""
calcular_tabla_dimayor.py

Versión Dimayor de calcular_tabla_primerac.py. A diferencia de Primera
C (que tiene 2 zonas, A y B), acá hay una sola zona real durante toda
la fase regular del Clausura: "Clausura" (los cuadrangulares se arman
más adelante, dinámicamente, dentro de modelos/estadisticas_dimayor.py
-- este archivo NO sabe nada de cuadrangulares, sólo de la fase de
todos-contra-todos).

Uso normal (incremental, ya con tabla_dimayor.csv existente):
    from calcular_tabla_dimayor import actualizar_tabla_con_partidos
    actualizar_tabla_con_partidos(cargados, tabla_path=...)

Uso único (bootstrap inicial del Clausura, arrancando de cero):
    from calcular_tabla_dimayor import construir_tabla_inicial
    construir_tabla_inicial()
"""
import csv

try:
    import rutas
except ImportError:
    rutas = None

CAMPOS_TABLA = [
    "zona", "posicion", "equipo", "partidos_jugados", "ganados",
    "empatados", "perdidos", "gf", "gc", "dg", "puntos",
]
CAMPOS_NUMERICOS = [
    "posicion", "partidos_jugados", "ganados", "empatados",
    "perdidos", "gf", "gc", "dg", "puntos",
]

ZONA_CLAUSURA = "Clausura"

# Los 20 equipos de la Liga BetPlay Dimayor (Categoría Primera A) para
# la temporada 2026, según Promiedos (liga "gca"). OJO: verificar que
# estos nombres coincidan EXACTAMENTE con los que tira
# scraper_promiedos_dimayor.py antes del primer bootstrap -- si algún
# nombre no matchea, actualizar_resultados_dimayor.py avisa en
# "sin_matchear".
EQUIPOS_DIMAYOR = [
    "Águilas Doradas", "Alianza FC", "América de Cali", "Atlético Bucaramanga",
    "Atlético Nacional", "Boyacá Chicó", "Cúcuta Deportivo", "Deportes Tolima",
    "Deportivo Cali", "Deportivo Pasto", "Deportivo Pereira", "Fortaleza FC",
    "Independiente Medellín", "Independiente Santa Fe", "Internacional de Bogotá",
    "Jaguares de Córdoba", "Junior FC", "Llaneros FC",
    "Millonarios", "Once Caldas",
]


def _ruta_default(nombre_archivo):
    if rutas is not None:
        return str(rutas.datos_dir() / nombre_archivo)
    return nombre_archivo


def _leer_tabla(tabla_path):
    with open(tabla_path, newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    for f_ in filas:
        for campo in CAMPOS_NUMERICOS:
            f_[campo] = int(f_[campo])
    return filas


def _leer_resultados(resultados_path):
    with open(resultados_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def construir_tabla_inicial(equipos=None, resultados_path=None, tabla_path=None, imprimir=True):
    """Bootstrap de una sola vez: arma tabla_dimayor.csv desde cero
    recorriendo TODO resultados_dimayor.csv (los partidos del Clausura
    ya jugados hasta el momento del primer scrapeo). Usar una única vez,
    la primera vez que se corre el scraper para Dimayor; de ahí en
    adelante usar el modo incremental (actualizar_tabla_con_partidos).

    equipos: lista de 20 nombres. Por default usa EQUIPOS_DIMAYOR.
    """
    equipos = equipos or EQUIPOS_DIMAYOR
    resultados_path = resultados_path or _ruta_default("resultados_dimayor.csv")
    tabla_path = tabla_path or _ruta_default("tabla_dimayor.csv")

    acumulado = {
        equipo: {
            "zona": ZONA_CLAUSURA, "equipo": equipo, "partidos_jugados": 0,
            "ganados": 0, "empatados": 0, "perdidos": 0, "gf": 0, "gc": 0,
        }
        for equipo in equipos
    }

    partidos = _leer_resultados(resultados_path)
    equipos_desconocidos = set()
    partidos_invalidos = []

    for p in partidos:
        local, visitante = p["equipo_local"], p["equipo_visitante"]
        if local not in acumulado or visitante not in acumulado:
            if local not in acumulado:
                equipos_desconocidos.add(local)
            if visitante not in acumulado:
                equipos_desconocidos.add(visitante)
            continue

        if not p["goles_local"] or not p["goles_visitante"]:
            partidos_invalidos.append(p)
            continue

        gl, gv = int(p["goles_local"]), int(p["goles_visitante"])
        fl, fv = acumulado[local], acumulado[visitante]

        fl["partidos_jugados"] += 1
        fv["partidos_jugados"] += 1
        fl["gf"] += gl
        fl["gc"] += gv
        fv["gf"] += gv
        fv["gc"] += gl

        if gl > gv:
            fl["ganados"] += 1
            fv["perdidos"] += 1
        elif gl < gv:
            fv["ganados"] += 1
            fl["perdidos"] += 1
        else:
            fl["empatados"] += 1
            fv["empatados"] += 1

    if equipos_desconocidos:
        print(f"  [aviso construir_tabla_inicial] equipo(s) en resultados_dimayor.csv "
              f"que no están en EQUIPOS_DIMAYOR (revisar nombres): {sorted(equipos_desconocidos)}")

    if partidos_invalidos:
        print(f"  [aviso construir_tabla_inicial] {len(partidos_invalidos)} partido(s) en "
              f"resultados_dimayor.csv sin goles cargados, se salteó del cálculo de la tabla.")

    for fila in acumulado.values():
        fila["puntos"] = fila["ganados"] * 3 + fila["empatados"]
        fila["dg"] = fila["gf"] - fila["gc"]

    filas = list(acumulado.values())
    filas.sort(key=lambda f: (-f["puntos"], -f["dg"], -f["gf"], f["equipo"]))

    for contador, f_ in enumerate(filas, start=1):
        f_["posicion"] = contador

    guardar_tabla(filas, tabla_path=tabla_path)

    if imprimir:
        print(f"tabla_dimayor.csv armada desde cero con {len(partidos)} partidos "
              f"leídos de {resultados_path}.")

    return filas


def aplicar_partidos(filas_tabla, partidos):
    """Igual que calcular_tabla_primerac.aplicar_partidos(), pero sin
    zonas (una sola tabla, todos los equipos)."""
    indice = {f["equipo"]: dict(f) for f in filas_tabla}
    equipos_desconocidos = set()
    partidos_invalidos = []

    for p in partidos:
        local = p["equipo_local"]
        visitante = p["equipo_visitante"]
        if local not in indice or visitante not in indice:
            if local not in indice:
                equipos_desconocidos.add(local)
            if visitante not in indice:
                equipos_desconocidos.add(visitante)
            continue

        if not p["goles_local"] and p["goles_local"] != 0 or not p["goles_visitante"] and p["goles_visitante"] != 0:
            partidos_invalidos.append(p)
            continue

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
        print(f"  [aviso calcular_tabla_dimayor] equipo(s) sin fila en tabla_dimayor.csv, "
              f"no se pudo actualizar su posición: {sorted(equipos_desconocidos)}")

    if partidos_invalidos:
        print(f"  [aviso calcular_tabla_dimayor] {len(partidos_invalidos)} partido(s) sin "
              f"goles cargados, no se sumaron a la tabla.")

    filas = list(indice.values())
    filas.sort(key=lambda f: (-f["puntos"], -f["dg"], -f["gf"], f["equipo"]))

    for contador, f_ in enumerate(filas, start=1):
        f_["posicion"] = contador

    return [{c: f_[c] for c in CAMPOS_TABLA} for f_ in filas]


def guardar_tabla(filas, tabla_path=None):
    tabla_path = tabla_path or _ruta_default("tabla_dimayor.csv")
    with open(tabla_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS_TABLA)
        writer.writeheader()
        writer.writerows(filas)


def actualizar_tabla_con_partidos(partidos_nuevos, tabla_path=None, imprimir=True):
    """Punto de entrada incremental: lee tabla_dimayor.csv, le aplica
    los partidos nuevos y lo vuelve a guardar."""
    if not partidos_nuevos:
        return None

    tabla_path = tabla_path or _ruta_default("tabla_dimayor.csv")

    filas_actuales = _leer_tabla(tabla_path)
    filas_nuevas = aplicar_partidos(filas_actuales, partidos_nuevos)
    guardar_tabla(filas_nuevas, tabla_path=tabla_path)

    if imprimir:
        print(f"  tabla_dimayor.csv actualizada con {len(partidos_nuevos)} partido(s) nuevo(s).")

    return filas_nuevas


def construir_tabla_apertura(resultados_apertura_path=None):
    """Arma la clasificación FINAL del Torneo Apertura (informativa,
    nunca pasa por el motor de simulación) a partir de
    resultados_apertura_dimayor.csv -- el archivo local que escribe
    scraper_promiedos_dimayor.py con los 19 fechas de todos-contra-
    todos del Apertura ya jugado (sin incluir sus playoffs de Cuartos/
    Semis/Final).

    Devuelve una lista de dicts (posicion, equipo, partidos_jugados,
    ganados, empatados, perdidos, gf, gc, dg, puntos) lista para
    mostrar tal cual, o [] si el archivo no existe/está vacío (ej.
    todavía no se corrió el scraper)."""
    resultados_apertura_path = resultados_apertura_path or _ruta_default("resultados_apertura_dimayor.csv")

    try:
        partidos = _leer_resultados(resultados_apertura_path)
    except (FileNotFoundError, OSError):
        return []
    if not partidos:
        return []

    acumulado = {}
    for p in partidos:
        local, visitante = p["equipo_local"], p["equipo_visitante"]
        if p["goles_local"] == "" or p["goles_visitante"] == "":
            continue
        gl, gv = int(p["goles_local"]), int(p["goles_visitante"])

        for nombre in (local, visitante):
            acumulado.setdefault(nombre, {
                "equipo": nombre, "partidos_jugados": 0, "ganados": 0,
                "empatados": 0, "perdidos": 0, "gf": 0, "gc": 0,
            })
        fl, fv = acumulado[local], acumulado[visitante]
        fl["partidos_jugados"] += 1
        fv["partidos_jugados"] += 1
        fl["gf"] += gl
        fl["gc"] += gv
        fv["gf"] += gv
        fv["gc"] += gl
        if gl > gv:
            fl["ganados"] += 1
            fv["perdidos"] += 1
        elif gl < gv:
            fv["ganados"] += 1
            fl["perdidos"] += 1
        else:
            fl["empatados"] += 1
            fv["empatados"] += 1

    for fila in acumulado.values():
        fila["puntos"] = fila["ganados"] * 3 + fila["empatados"]
        fila["dg"] = fila["gf"] - fila["gc"]

    filas = list(acumulado.values())
    filas.sort(key=lambda f: (-f["puntos"], -f["dg"], -f["gf"], f["equipo"]))
    for posicion, f_ in enumerate(filas, start=1):
        f_["posicion"] = posicion

    return filas


if __name__ == "__main__":
    print("Este módulo se usa desde actualizar_resultados_dimayor.py con los")
    print("partidos nuevos de cada corrida (modo incremental).")
    print()
    print("Para el bootstrap inicial (primera vez, arrancando de cero), correr:")
    print("  from calcular_tabla_dimayor import construir_tabla_inicial")
    print("  construir_tabla_inicial()")
    print("...después de haber corrido scraper_promiedos_dimayor.py al menos una vez.")