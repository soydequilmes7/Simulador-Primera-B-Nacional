import json
from datetime import datetime
from pathlib import Path

from modelos.estadisticas_lpf import EstadisticasLPF

RUTA_JSON_LPF = Path(__file__).parent / "public" / "data_lpf.json"


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


def armar_datos_web_lpf(e, tablas_clausura, campeon_clausura, detalle_playoffs,
                         tabla_anual, descensos, copas, trofeo,
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

    descensos = e.calcular_descensos(tabla_anual)
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
        tabla_anual, descensos, copas, trofeo,
        n_sims, resumen_mc, tabla_esperada_mc,
    )

    if guardar_json:
        ruta = guardar_json_lpf(datos_web)
        if imprimir:
            print(f"\ndata_lpf.json guardado en: {ruta}")

    return datos_web


if __name__ == "__main__":
    correr_simulacion_lpf()
