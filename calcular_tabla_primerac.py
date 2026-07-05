# -*- coding: utf-8 -*-
"""
calcular_tabla_primerac.py

Versión Primera C de calcular_tabla.py. Mismo enfoque que el original
(con zonas, como B Nacional): mantiene tabla_primerac.csv al día
aplicando SOLO los partidos nuevos de cada actualización de Promiedos,
en vez de recalcular todo desde resultados_primerac.csv.

A diferencia de B Nacional -- que ya arrancaba con un tabla.csv
"canónico" hecho a mano -- acá la tabla hay que armarla por primera vez
a partir de CERO, con el historial completo que trae el scraper. Para
eso está construir_tabla_inicial(), que se usa UNA sola vez (el primer
bootstrap); de ahí en adelante, actualizar_resultados_primerac.py llama
a actualizar_tabla_con_partidos() como de costumbre.

Uso normal (incremental, ya con tabla_primerac.csv existente):
    from calcular_tabla_primerac import actualizar_tabla_con_partidos
    actualizar_tabla_con_partidos(cargados, tabla_path=...)

Uso único (bootstrap inicial, arrancando de cero):
    from calcular_tabla_primerac import construir_tabla_inicial
    construir_tabla_inicial(ZONAS, resultados_path=..., tabla_path=...)
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

# Sorteo de zonas de la Primera C 2026 (AFA / Promiedos, liga "ffjb").
# OJO: verificar que estos nombres coincidan exactamente con los que
# tira el scraper (scraper_promiedos_primerac.py) antes del primer
# bootstrap -- si Promiedos usa una variante distinta (ej. "Berazategui"
# en vez de "A.D. Berazategui"), hay que ajustar acá.
ZONAS_PRIMERA_C = {
    "A": [
        "Centro Español", "Berazategui", "Sacachispas", "Estrella del Sur",
        "Victoriano Arenas", "CA Lugano", "Puerto Nuevo", "Leandro N. Alem",
        "Mercedes", "Juventud Unida SM", "Defensores Cambaceres",
        "Argentino Rosario", "Justo José Urquiza", "Deportivo Paraguayo",
    ],
    "B": [
        "Cañuelas", "Club Luján", "Leones de Rosario FC", "General Lamadrid", "Sportivo Barracas",
        "Yupanqui", "Deportivo Español", "El Porvenir", "Claypole",
        "Central Córdoba", "CA Atlas", "Central Ballester", "Muñiz", "CA Fenix",
    ],
}


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


def construir_tabla_inicial(zonas=None, resultados_path=None, tabla_path=None, imprimir=True):
    """Bootstrap de una sola vez: arma tabla_primerac.csv desde cero
    recorriendo TODO resultados_primerac.csv (todos los partidos
    jugados hasta ahora), en vez de aplicar solo "lo nuevo" como hace
    actualizar_tabla_con_partidos(). Usar esto una única vez, la
    primera vez que se corre el scraper para Primera C; de ahí en
    adelante usar el modo incremental de siempre.

    zonas: dict {"A": [equipos...], "B": [equipos...]}. Por default usa
    ZONAS_PRIMERA_C (el sorteo real de 2026).
    """
    zonas = zonas or ZONAS_PRIMERA_C
    resultados_path = resultados_path or _ruta_default("resultados_primerac.csv")
    tabla_path = tabla_path or _ruta_default("tabla_primerac.csv")

    equipo_a_zona = {equipo: zona for zona, equipos in zonas.items() for equipo in equipos}

    acumulado = {
        equipo: {
            "zona": zona, "equipo": equipo, "partidos_jugados": 0,
            "ganados": 0, "empatados": 0, "perdidos": 0, "gf": 0, "gc": 0,
        }
        for zona, equipos in zonas.items() for equipo in equipos
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
        print(f"  [aviso construir_tabla_inicial] equipo(s) en resultados_primerac.csv "
              f"que no están en ZONAS_PRIMERA_C (revisar nombres): {sorted(equipos_desconocidos)}")

    if partidos_invalidos:
        print(f"  [aviso construir_tabla_inicial] {len(partidos_invalidos)} partido(s) en "
              f"resultados_primerac.csv sin goles cargados (posible walkover/suspendido), "
              f"se salteó del cálculo de la tabla:")
        for p in partidos_invalidos:
            print(f"    - {p['equipo_local']} vs {p['equipo_visitante']} "
                  f"(jornada {p.get('jornada', '?')}, goles: '{p['goles_local']}' - '{p['goles_visitante']}')")

    for fila in acumulado.values():
        fila["puntos"] = fila["ganados"] * 3 + fila["empatados"]
        fila["dg"] = fila["gf"] - fila["gc"]

    filas = list(acumulado.values())
    filas.sort(key=lambda f: (f["zona"], -f["puntos"], -f["dg"], -f["gf"], f["equipo"]))

    zona_actual = None
    contador = 0
    for f_ in filas:
        if f_["zona"] != zona_actual:
            zona_actual = f_["zona"]
            contador = 0
        contador += 1
        f_["posicion"] = contador

    guardar_tabla(filas, tabla_path=tabla_path)

    if imprimir:
        print(f"tabla_primerac.csv armada desde cero con {len(partidos)} partidos "
              f"leídos de {resultados_path}.")

    return filas


def aplicar_partidos(filas_tabla, partidos):
    """Igual que en calcular_tabla.py: aplica `partidos` nuevos sobre
    una copia de filas_tabla y recalcula posiciones por zona."""
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
        print(f"  [aviso calcular_tabla_primerac] equipo(s) sin fila en tabla_primerac.csv, "
              f"no se pudo actualizar su posición: {sorted(equipos_desconocidos)}")

    if partidos_invalidos:
        print(f"  [aviso calcular_tabla_primerac] {len(partidos_invalidos)} partido(s) sin "
              f"goles cargados (posible walkover/suspendido), no se sumaron a la tabla:")
        for p in partidos_invalidos:
            print(f"    - {p['equipo_local']} vs {p['equipo_visitante']}")

    filas = list(indice.values())
    filas.sort(key=lambda f: (f["zona"], -f["puntos"], -f["dg"], -f["gf"], f["equipo"]))

    zona_actual = None
    contador = 0
    for f_ in filas:
        if f_["zona"] != zona_actual:
            zona_actual = f_["zona"]
            contador = 0
        contador += 1
        f_["posicion"] = contador

    return [{c: f_[c] for c in CAMPOS_TABLA} for f_ in filas]


def guardar_tabla(filas, tabla_path=None):
    tabla_path = tabla_path or _ruta_default("tabla_primerac.csv")
    with open(tabla_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS_TABLA)
        writer.writeheader()
        writer.writerows(filas)


def actualizar_tabla_con_partidos(partidos_nuevos, tabla_path=None, imprimir=True):
    """Punto de entrada incremental (uso normal, día a día): lee
    tabla_primerac.csv, le aplica los partidos nuevos y lo vuelve a
    guardar. Si `partidos_nuevos` está vacío, no hace nada."""
    if not partidos_nuevos:
        return None

    tabla_path = tabla_path or _ruta_default("tabla_primerac.csv")

    filas_actuales = _leer_tabla(tabla_path)
    filas_nuevas = aplicar_partidos(filas_actuales, partidos_nuevos)
    guardar_tabla(filas_nuevas, tabla_path=tabla_path)

    if imprimir:
        print(f"  tabla_primerac.csv actualizada con {len(partidos_nuevos)} partido(s) nuevo(s).")

    return filas_nuevas


if __name__ == "__main__":
    print("Este módulo se usa desde actualizar_resultados_primerac.py con los")
    print("partidos nuevos de cada corrida (modo incremental).")
    print()
    print("Para el bootstrap inicial (primera vez, arrancando de cero), correr:")
    print("  from calcular_tabla_primerac import construir_tabla_inicial")
    print("  construir_tabla_inicial()")
    print("...después de haber corrido scraper_promiedos_primerac.py al menos una vez.")
