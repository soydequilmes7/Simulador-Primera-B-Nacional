import json
import datetime

import rutas
from modelos.estadisticas_primerac import Estadisticas


def correr_simulacion(n_sims=1000, imprimir=True, guardar_json=True):
    """Corre toda la simulación de Primera C (fase de zonas, Final por
    el 1er Ascenso, Reducido por el 2do y Monte Carlo) y devuelve el
    diccionario de resultados. Si guardar_json es True (default),
    además lo guarda en public/data_primerac.json. Calcado de
    correr_simulacion() de main.py (B Nacional), con dos llamadas
    distintas por las diferencias reglamentarias:

      - jugar_final_ascenso(tablas) en vez de jugar_final_ascenso(a, b):
        la Final de Primera C es a doble partido y necesita saber los
        puntos de la fase regular para decidir quién es local en la
        vuelta, no solo los nombres de los punteros.
      - El resto (reducido, Monte Carlo, goleadores) tiene la misma
        firma que en B Nacional.
    """

    if imprimir:
        print("=" * 45)
        print("SIMULADOR PRIMERA C")
        print("=" * 45)

    estadisticas_obj = Estadisticas()

    estadisticas_obj.cargar_datos()
    estadisticas_obj.crear_equipos()
    estadisticas_obj.calcular_estadisticas()
    estadisticas_obj.calcular_ratings()
    estadisticas_obj.registrar_partidos_simulados_oficiales = True
    estadisticas_obj.partidos_simulados_oficiales = []

    if imprimir:
        print("\n--- Tabla final simulada (fase de zonas) ---")
    tablas = estadisticas_obj.simular_fase_regular()

    if imprimir:
        for zona, tabla_zona in tablas.items():
            print(f"\nZona {zona} ({len(tabla_zona)} equipos)")
            print(tabla_zona.to_string())

    puntero_a = tablas["A"].iloc[0]["equipo"]
    puntero_b = tablas["B"].iloc[0]["equipo"]

    if imprimir:
        print(f"\n--- Final por el 1er Ascenso: {puntero_a} (A) vs {puntero_b} (B) (doble partido) ---")
    ganador, perdedor, detalle = estadisticas_obj.jugar_final_ascenso(tablas)
    if imprimir:
        print(detalle["detalle"])
        print(f"Campeón del Campeonato de Primera C 2026 y asciende a la Primera B: {ganador}")
        print(f"{perdedor} pasa a semifinales del Torneo Reducido (2do ascenso)")

    if imprimir:
        print("\n--- Torneo Reducido (2do ascenso) ---")
    campeon_reducido, detalle_reducido = estadisticas_obj.jugar_reducido(tablas, perdedor)
    if imprimir:
        print(f"Campeón del Torneo Reducido, asciende a la Primera B: {campeon_reducido}")

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
        print("\nGuardando resultados en data_primerac.json para la web...")

    mc_A = resumen_mc[resumen_mc["zona"] == "A"].drop(columns=["zona"]).to_dict(orient="records")
    mc_B = resumen_mc[resumen_mc["zona"] == "B"].drop(columns=["zona"]).to_dict(orient="records")

    datos_web = {
        "n_simulaciones": n_sims,
        "generado": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "tablas": {
            "A": tablas["A"].to_dict(orient="records"),
            "B": tablas["B"].to_dict(orient="records")
        },
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
            "detalle_marcador": [detalle.get("goles_x", 0), detalle.get("goles_y", 0)] if isinstance(detalle, dict) else [0, 0],
            "texto": detalle.get("detalle", "") if isinstance(detalle, dict) else "",
        },
        "reducido": detalle_reducido,
        "partidos_simulados": estadisticas_obj.partidos_simulados_oficiales,
        "monte_carlo": {
            "A": mc_A,
            "B": mc_B
        },
        "tabla_esperada": {
            "A": tabla_esperada_mc["A"].to_dict(orient="records"),
            "B": tabla_esperada_mc["B"].to_dict(orient="records")
        },
        "goleadores": goleadores_df.head(20).to_dict(orient="records"),
        "rachas": {
            zona: {
                nombre: equipo_obj.ultimos10[-5:]
                for nombre, equipo_obj in estadisticas_obj.equipos.items()
                if equipo_obj.zona == zona
            }
            for zona in ["A", "B"]
        }
    }

    if guardar_json:
        ruta_data_json = rutas.public_dir() / "data_primerac.json"
        try:
            with open(ruta_data_json, "w", encoding="utf-8") as file:
                json.dump(datos_web, file, ensure_ascii=False, indent=4)
            print("¡Archivo data_primerac.json generado con éxito en la carpeta public!")
        except Exception as e:
            print(f"Error al guardar el archivo JSON: {e}")

    return datos_web


def simular_hasta_campeon(equipo_objetivo, max_intentos=5000, imprimir=True):
    """Repite la simulación de la temporada hasta que `equipo_objetivo`
    consiga el ascenso -- ganando la Final directa (1er ascenso) o el
    Torneo Reducido (2do ascenso). Calcado de simular_hasta_campeon()
    de main.py, con la única diferencia de que jugar_final_ascenso()
    recibe `tablas` en vez de los dos nombres de los punteros."""

    if imprimir:
        print("=" * 45)
        print(f"SIMULANDO HASTA QUE ASCIENDA: {equipo_objetivo}")
        print("=" * 45)

    estadisticas_obj = Estadisticas()
    estadisticas_obj.cargar_datos()
    estadisticas_obj.crear_equipos()
    estadisticas_obj.calcular_estadisticas()
    estadisticas_obj.calcular_ratings()

    if equipo_objetivo not in estadisticas_obj.equipos:
        sugerencias = [nombre for nombre in estadisticas_obj.equipos if equipo_objetivo.lower() in nombre.lower()]
        mensaje = f"'{equipo_objetivo}' no es un equipo válido."
        if sugerencias:
            mensaje += f" ¿Quisiste decir: {', '.join(sugerencias)}?"
        raise ValueError(mensaje)

    for intento in range(1, max_intentos + 1):
        if imprimir and intento % 200 == 0:
            print(f"...intento {intento}, todavía no salió campeón")

        tablas = estadisticas_obj.simular_fase_regular()

        equipo_a = tablas["A"].iloc[0]["equipo"]
        equipo_b = tablas["B"].iloc[0]["equipo"]

        ganador_ascenso, perdedor_ascenso, detalle_final = estadisticas_obj.jugar_final_ascenso(tablas)
        campeon_reducido, detalle_reducido = estadisticas_obj.jugar_reducido(tablas, perdedor_ascenso)

        asciende_directo = (ganador_ascenso == equipo_objetivo)
        asciende_por_reducido = (campeon_reducido == equipo_objetivo)

        if asciende_directo or asciende_por_reducido:
            resultado = {
                "equipo": equipo_objetivo,
                "intentos": intento,
                "via": "ascenso_directo" if asciende_directo else "reducido",
                "tablas": {zona: tabla_zona.to_dict(orient="records") for zona, tabla_zona in tablas.items()},
                "final_ascenso": {
                    "equipo_a": equipo_a,
                    "equipo_b": equipo_b,
                    "ganador": ganador_ascenso,
                    "perdedor": perdedor_ascenso,
                    "detalle_marcador": [detalle_final.get("goles_x", 0), detalle_final.get("goles_y", 0)] if isinstance(detalle_final, dict) else [0, 0],
                    "texto": detalle_final.get("detalle", "") if isinstance(detalle_final, dict) else "",
                },
                "reducido": detalle_reducido,
            }

            if imprimir:
                print(f"\n¡{equipo_objetivo} ASCENDIÓ! (tardó {intento} intentos)")
                print(f"Vía: {'ascenso directo (Final)' if asciende_directo else 'Torneo Reducido'}")

            return resultado

    if imprimir:
        print(f"\nNo se logró el ascenso de {equipo_objetivo} en {max_intentos} intentos.")
    return None


def main():
    print("=" * 45)
    print("SIMULADOR PRIMERA C")
    print("=" * 45)
    print("1) Correr una simulación normal (tabla + Monte Carlo)")
    print("2) Simular hasta que un equipo salga campeón (ascienda)")

    opcion = input("\nElegí una opción (1/2): ").strip()

    if opcion == "2":
        equipo_objetivo = input("¿Qué equipo querés que ascienda?: ").strip()
        try:
            simular_hasta_campeon(equipo_objetivo, max_intentos=5000, imprimir=True)
        except ValueError as e:
            print(f"\nError: {e}")
    else:
        correr_simulacion(n_sims=1000, imprimir=True)


if __name__ == "__main__":
    main()
