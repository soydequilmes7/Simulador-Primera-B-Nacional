import json
import datetime
from pathlib import Path

from modelos import estadisticas
from modelos.estadisticas import Estadisticas


def correr_simulacion(n_sims=1000, imprimir=True, guardar_json=True):
    """Corre toda la simulación (fase regular, final de ascenso, reducido y
    Monte Carlo) y devuelve el diccionario de resultados. Si guardar_json es
    True (default), además lo guarda en PAGINAHTLM/data.json. La usan tanto
    main.py (línea de comandos) y servidor.py (botón "Correr nueva
    simulación" de la página web) -- con guardar_json=True, para que la
    página estática quede al día -- como api/index.py (Vercel Function),
    con guardar_json=False: ese filesystem es de solo lectura, así que el
    resultado se devuelve directo en la respuesta HTTP en vez de escribirse
    a disco."""

    if imprimir:
        print("=" * 45)
        print("SIMULADOR PRIMERA NACIONAL")
        print("=" * 45)

    estadisticas_obj = Estadisticas()

    estadisticas_obj.cargar_datos()
    estadisticas_obj.crear_equipos()
    estadisticas_obj.calcular_estadisticas()
    estadisticas_obj.calcular_ratings()

    if imprimir:
        print("\n--- Tabla final simulada (fase regular) ---")
    tablas = estadisticas_obj.simular_fase_regular()

    if imprimir:
        for zona, tabla_zona in tablas.items():
            print(f"\nZona {zona} ({len(tabla_zona)} equipos)")
            print(tabla_zona.to_string())

    puntero_a = tablas["A"].iloc[0]["equipo"]
    puntero_b = tablas["B"].iloc[0]["equipo"]

    if imprimir:
        print(f"\n--- Final por el 1° ascenso: {puntero_a} (A) vs {puntero_b} (B) ---")
    ganador, perdedor, detalle = estadisticas_obj.jugar_final_ascenso(puntero_a, puntero_b)
    if imprimir:
        print(detalle["texto"])
        print(f"Asciende a la Liga Profesional: {ganador}")
        print(f"{perdedor} pasa a semifinales del Reducido (2° ascenso)")

    if imprimir:
        print("\n--- Reducido (2° ascenso) ---")
    campeon_reducido, detalle_reducido = estadisticas_obj.jugar_reducido(tablas, perdedor)
    if imprimir:
        print(detalle_reducido)

    if imprimir:
        print("\n--- Monte Carlo ---")
    resumen_mc, tabla_esperada_mc = estadisticas_obj.monte_carlo(n_simulaciones=n_sims)

    if imprimir:
        for zona in sorted(resumen_mc["zona"].unique()):
            print(f"\nZona {zona}")
            resumen_zona = resumen_mc[resumen_mc["zona"] == zona].drop(columns=["zona"]).reset_index(drop=True)
            resumen_zona.index = resumen_zona.index + 1
            print(resumen_zona.to_string())

        print("\n--- Tabla final esperada (promedio de {} simulaciones) ---".format(n_sims))
        for zona, tabla_zona in tabla_esperada_mc.items():
            print(f"\nZona {zona}")
            print(tabla_zona.to_string())

    if imprimir:
        print("\n--- Goleadores (proyección simple a fin de temporada) ---")
    goleadores_df = estadisticas_obj.calcular_goleadores()
    if imprimir and not goleadores_df.empty:
        print(goleadores_df.head(15).to_string())

    # =================================================================
    # EXPORTACIÓN A JSON PARA LA PÁGINA WEB
    # =================================================================
    if imprimir and guardar_json:
        print("\nGuardando resultados en data.json para la web...")

    mc_A = resumen_mc[resumen_mc["zona"] == "A"].drop(columns=["zona"]).to_dict(orient="records")
    mc_B = resumen_mc[resumen_mc["zona"] == "B"].drop(columns=["zona"]).to_dict(orient="records")

# Preparamos los DataFrames de Monte Carlo separándolos por zona
    mc_A = resumen_mc[resumen_mc["zona"] == "A"].drop(columns=["zona"]).to_dict(orient="records")
    mc_B = resumen_mc[resumen_mc["zona"] == "B"].drop(columns=["zona"]).to_dict(orient="records")

    # Armamos el diccionario blindado (sin pedir claves que no existen)
    datos_web = {
        "n_simulaciones": n_sims,
        "generado": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "tablas": {
            "A": tablas["A"].to_dict(orient="records"),
            "B": tablas["B"].to_dict(orient="records")
        },
        # Tabla real de HOY (datos/tabla.csv), no la simulada a fin de
        # temporada. La usa el buscador de equipos para "Posición actual".
        "tabla_actual": {
            zona: (
                estadisticas_obj.tabla[estadisticas_obj.tabla["zona"] == zona]
                .sort_values("posicion")
                .to_dict(orient="records")
            )
            for zona in ["A", "B"]
        },
        "final_ascenso": {
            "equipo_a": puntero_a,
            "equipo_b": puntero_b,
            "ganador": ganador,
            "perdedor": perdedor,
            # Usamos .get() para que si falta el marcador, ponga [0,0] sin romper nada
            "detalle_marcador": detalle.get("marcador", [0, 0]) if isinstance(detalle, dict) else [0, 0] 
        },
        "reducido": detalle_reducido, 
        "monte_carlo": {
            "A": mc_A,
            "B": mc_B
        },
        "tabla_esperada": {
            "A": tabla_esperada_mc["A"].to_dict(orient="records"),
            "B": tabla_esperada_mc["B"].to_dict(orient="records")
        },
        # Top 20 proyectados. Si todavía no corriste backfill_goleadores.py
        # esto viene vacío (calcular_goleadores() lo maneja sin romper nada).
        "goleadores": goleadores_df.head(20).to_dict(orient="records"),
        # Últimos 5 partidos de cada equipo (para el historial de rachas
        # en la ficha del buscador). equipo.ultimos10 ya viene con
        # gf/gc/puntos/jornada/rival/condicion por partido; acá solo
        # recortamos a los últimos 5 y organizamos por zona.
        "rachas": {
            zona: {
                nombre: equipo.ultimos10[-5:]
                for nombre, equipo in estadisticas_obj.equipos.items()
                if equipo.zona == zona
            }
            for zona in ["A", "B"]
        }
    }

    # Guardar en la carpeta PAGINAHTLM
    if guardar_json:
        ruta_data_json = Path(__file__).resolve().parent / "PAGINAHTLM" / "data.json"
        try:
            with open(ruta_data_json, "w", encoding="utf-8") as file:
                json.dump(datos_web, file, ensure_ascii=False, indent=4)
            print("¡Archivo data.json generado con éxito en la carpeta PAGINAHTLM!")
        except Exception as e:
            print(f"Error al guardar el archivo JSON: {e}")

    return datos_web


def main():
    correr_simulacion(n_sims=1000, imprimir=True)


if __name__ == "__main__":
    main()
