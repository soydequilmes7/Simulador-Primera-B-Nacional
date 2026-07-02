import json
from datetime import datetime

import rutas
from modelos.estadisticas_lpf import EstadisticasLPF

RUTA_JSON_LPF = rutas.public_dir() / "data_lpf.json"


def _tabla_a_lista(tabla_df):
    """DataFrame de tabla (posición como índice, columnas equipo/puntos/gf/gc/dg)
    -> lista de dicts en el mismo shape que usa el frontend de Nacional."""
    filas = []
    for _, fila in tabla_df.reset_index(drop=True).iterrows():
        filas.append({
            "equipo": fila["equipo"],
            "puntos": int(fila["puntos"]),
            "gf": int(fila["gf"]),
            "gc": int(fila["gc"]),
            "dg": int(fila["dg"]),
        })
    return filas


def _tabla_promedios_a_lista(tabla_promedios_df):
    """DataFrame de calcular_tabla_promedios() -> lista de dicts para el
    frontend (equipo/puntos/partidos jugados/promedio, ya ordenada de
    mejor a peor)."""
    filas = []
    for _, fila in tabla_promedios_df.reset_index(drop=True).iterrows():
        filas.append({
            "equipo": fila["equipo"],
            "puntos": int(fila["puntos_totales"]),
            "partidos_jugados": int(fila["partidos_totales"]),
            "promedio": round(float(fila["promedio"]), 3),
        })
    return filas


def _apertura_a_zonas(apertura_df):
    """tablalpf.csv (con columna zona y posicion) -> {"A": [...], "B": [...]}
    ya ordenado por posición real del Apertura."""
    zonas = {}
    for zona in ["A", "B"]:
        sub = apertura_df[apertura_df["zona"] == zona].sort_values("posicion")
        zonas[zona] = [
            {
                "equipo": f["equipo"],
                "puntos": int(f["puntos"]),
                "gf": int(f["gf"]),
                "gc": int(f["gc"]),
                "dg": int(f["dg"]),
            }
            for _, f in sub.iterrows()
        ]
    return zonas


def _tabla_actual_clausura(e):
    """Tabla REAL del Clausura a hoy, armada desde resultados_lpf.csv,
    separada por zona: {"A": [...], "B": [...]} con posicion/equipo/puntos/
    gf/gc/dg/partidos_jugados. Si el Clausura no arrancó, viene todo en 0
    ordenado alfabéticamente. La usa el buscador para "Posición actual"."""
    acumulado = {
        fila["equipo"]: {"equipo": fila["equipo"], "zona": fila["zona"],
                          "partidos_jugados": 0, "puntos": 0, "gf": 0, "gc": 0, "dg": 0}
        for _, fila in e.apertura.iterrows()
    }
    for _, p in e.resultados.iterrows():
        local, visitante = p["equipo_local"], p["equipo_visitante"]
        gl, gv = int(p["goles_local"]), int(p["goles_visitante"])
        for nombre, gf, gc in [(local, gl, gv), (visitante, gv, gl)]:
            if nombre not in acumulado:
                continue
            fila = acumulado[nombre]
            fila["partidos_jugados"] += 1
            fila["gf"] += gf
            fila["gc"] += gc
            fila["dg"] = fila["gf"] - fila["gc"]
        if gl > gv:
            acumulado[local]["puntos"] += 3
        elif gv > gl:
            acumulado[visitante]["puntos"] += 3
        else:
            acumulado[local]["puntos"] += 1
            acumulado[visitante]["puntos"] += 1

    tabla_actual = {}
    for zona in ["A", "B"]:
        filas = [f for f in acumulado.values() if f["zona"] == zona]
        filas.sort(key=lambda f: (-f["puntos"], -f["dg"], -f["gf"], f["equipo"]))
        for i, fila in enumerate(filas, start=1):
            fila["posicion"] = i
        tabla_actual[zona] = filas
    return tabla_actual


def _rachas_lpf(e, n_partidos=5):
    """Últimos n partidos reales de cada equipo, por zona, con el mismo
    shape que usa el frontend de Nacional (equipo.ultimos10 ya trae
    gf/gc/puntos/jornada/rival/condicion). Requiere calcular_estadisticas();
    si no hay resultados quedan listas vacías (el frontend lo maneja)."""
    return {
        zona: {
            nombre: equipo.ultimos10[-n_partidos:]
            for nombre, equipo in e.equipos.items()
            if equipo.zona == zona
        }
        for zona in ["A", "B"]
    }


def armar_datos_web_lpf(e, tablas_clausura, campeon_clausura, detalle_playoffs,
                         tabla_anual, tabla_promedios, descensos, copas, trofeo,
                         n_sims, resumen_mc, tabla_esperada_mc):
    """Arma el dict con la forma que espera template.html (sección LPF) y
    que se puede tirar directo a JSON."""
    mc_A = resumen_mc[resumen_mc["zona"] == "A"].drop(columns=["zona"]).to_dict(orient="records")
    mc_B = resumen_mc[resumen_mc["zona"] == "B"].drop(columns=["zona"]).to_dict(orient="records")

    return {
        "liga": "lpf",
        "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "n_simulaciones": n_sims,
        "campeon_apertura": EstadisticasLPF.CAMPEON_APERTURA,
        "apertura": _apertura_a_zonas(e.apertura),
        "tablas_clausura": {
            "A": _tabla_a_lista(tablas_clausura["A"]),
            "B": _tabla_a_lista(tablas_clausura["B"]),
        },
        "playoffs": detalle_playoffs,
        "campeon_clausura": campeon_clausura,
        "tabla_anual": _tabla_a_lista(tabla_anual),
        "tabla_promedios": _tabla_promedios_a_lista(tabla_promedios),
        "tabla_actual": _tabla_actual_clausura(e),
        "rachas": _rachas_lpf(e),
        "descensos": descensos,
        "copas": copas,
        "trofeo": trofeo,
        "monte_carlo": {"A": mc_A, "B": mc_B},
        "tabla_esperada": {
            "A": tabla_esperada_mc["A"].to_dict(orient="records"),
            "B": tabla_esperada_mc["B"].to_dict(orient="records"),
        },
    }


def guardar_json_lpf(datos_web, ruta=None):
    ruta = ruta or RUTA_JSON_LPF
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos_web, f, ensure_ascii=False, indent=2)
    return ruta


def correr_simulacion_lpf(imprimir=True, guardar_json=True, n_sims=300):
    e = EstadisticasLPF()
    e.cargar_datos_lpf()
    e.crear_equipos_lpf()
    if len(e.resultados) > 0:
        # Llena equipo.ultimos10 (rachas del buscador). Con 0 resultados
        # no aporta nada, así que se saltea.
        e.calcular_estadisticas()
    e.calcular_ratings_lpf()

    if imprimir:
        print("\n--- Tabla del Clausura simulada (fase de zonas) ---")
    tablas_clausura = e.simular_clausura()
    if imprimir:
        for zona, tabla_zona in tablas_clausura.items():
            print(f"\nZona {zona}")
            print(tabla_zona.to_string())

    if imprimir:
        print("\n--- Playoffs del Clausura ---")
    campeon_clausura, detalle_playoffs = e.jugar_playoffs(tablas_clausura)
    if imprimir:
        print("\nOctavos:")
        for p in detalle_playoffs["octavos"]:
            print(f"  {p['local']} {p['golesLocal']} - {p['golesVisitante']} {p['visitante']} (avanza {p['avanza']})")
        print("\nCuartos:")
        for p in detalle_playoffs["cuartos"]:
            print(f"  {p['local']} {p['golesLocal']} - {p['golesVisitante']} {p['visitante']} (avanza {p['avanza']})")
        print("\nSemis:")
        for p in detalle_playoffs["semis"]:
            print(f"  {p['local']} {p['golesLocal']} - {p['golesVisitante']} {p['visitante']} (avanza {p['avanza']})")
        print(f"\nFinal: {detalle_playoffs['final']['texto']}")
        print(f"CAMPEÓN DEL CLAUSURA: {campeon_clausura}")

    tabla_anual = e.calcular_tabla_anual(tablas_clausura)
    if imprimir:
        print("\n--- Tabla Anual 2026 (Apertura + Clausura) ---")
        print(tabla_anual.to_string())

    tabla_promedios = e.calcular_tabla_promedios(tabla_anual)
    if imprimir:
        print("\n--- Tabla de promedios ---")
        print(tabla_promedios.to_string())

    descensos = e.calcular_descensos(tabla_anual, tabla_promedios)
    if imprimir:
        print(f"\nDESCIENDEN: {descensos}")

    copas = e.calcular_copas(tabla_anual, campeon_clausura)
    if imprimir:
        print(f"\nLibertadores 2027: {copas['libertadores_2027']}")
        print(f"Sudamericana 2027: {copas['sudamericana_2027']}")

    trofeo = e.calcular_trofeo_campeones(campeon_clausura)
    if imprimir:
        print(f"\n--- Trofeo de Campeones ---")
        print(trofeo)

    if imprimir:
        print(f"\n--- Monte Carlo LPF ({n_sims} simulaciones) ---")
    resumen_mc, tabla_esperada_mc = e.monte_carlo_lpf(n_simulaciones=n_sims)
    if imprimir:
        for zona in sorted(resumen_mc["zona"].unique()):
            print(f"\nZona {zona}")
            print(resumen_mc[resumen_mc["zona"] == zona].drop(columns=["zona"]).to_string())

    datos_web = armar_datos_web_lpf(
        e, tablas_clausura, campeon_clausura, detalle_playoffs,
        tabla_anual, tabla_promedios, descensos, copas, trofeo,
        n_sims, resumen_mc, tabla_esperada_mc,
    )

    if guardar_json:
        ruta = guardar_json_lpf(datos_web)
        if imprimir:
            print(f"\ndata_lpf.json guardado en: {ruta}")

    return datos_web


def simular_hasta_campeon_lpf(equipo_objetivo, max_intentos=5000, imprimir=True):
    """Repite Clausura + playoffs hasta que `equipo_objetivo` salga campeón
    del Clausura. Ratings se calculan una sola vez; cada intento simula una
    temporada. Devuelve dict con la corrida ganadora (tablas del Clausura y
    bracket completo de playoffs) o None si no se logró en max_intentos.
    Levanta ValueError (con sugerencias) si el equipo no existe."""
    e = EstadisticasLPF()
    e.cargar_datos_lpf()
    e.crear_equipos_lpf()
    e.calcular_ratings_lpf()

    if equipo_objetivo not in e.equipos:
        sugerencias = [n for n in e.equipos if equipo_objetivo.lower() in n.lower()]
        mensaje = f"'{equipo_objetivo}' no es un equipo válido."
        if sugerencias:
            mensaje += f" ¿Quisiste decir: {', '.join(sugerencias)}?"
        raise ValueError(mensaje)

    for intento in range(1, max_intentos + 1):
        if imprimir and intento % 200 == 0:
            print(f"...intento {intento}, todavía no salió campeón")

        tablas_clausura = e.simular_clausura()
        campeon, detalle_playoffs = e.jugar_playoffs(tablas_clausura)

        if campeon == equipo_objetivo:
            if imprimir:
                print(f"\n¡{equipo_objetivo} CAMPEÓN DEL CLAUSURA! (intento {intento})")
            return {
                "equipo": equipo_objetivo,
                "intentos": intento,
                "tablas_clausura": {
                    "A": _tabla_a_lista(tablas_clausura["A"]),
                    "B": _tabla_a_lista(tablas_clausura["B"]),
                },
                "playoffs": detalle_playoffs,
            }

    if imprimir:
        print(f"\nNo se logró el título de {equipo_objetivo} en {max_intentos} intentos.")
    return None


if __name__ == "__main__":
    correr_simulacion_lpf()
