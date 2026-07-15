import json
import datetime

import data_access
import rutas
from modelos import estadisticas
from modelos.estadisticas import Estadisticas


def _ratings_finales_nacional(estadisticas_obj):
    """Ratings finales de cada Equipo de Nacional DESPUÉS de
    calcular_ratings(), en el shape que espera
    ResultadoTorneo.ratings_finales (addendum Etapa 6, punto 3):
    {nombre: {ataque_local, ataque_visitante, defensa_local,
    defensa_visitante}}. Es la fuente real para los clubes que
    ascienden a LPF (vía RatingCarryoverPolicy.rating_para_recien_llegado)."""
    return {
        nombre: {
            "ataque_local": equipo.ataque_local,
            "ataque_visitante": equipo.ataque_visitante,
            "defensa_local": equipo.defensa_local,
            "defensa_visitante": equipo.defensa_visitante,
        }
        for nombre, equipo in estadisticas_obj.equipos.items()
    }


def correr_simulacion(n_sims=1000, imprimir=True, guardar_json=True):
    """Corre toda la simulación (fase regular, final de ascenso, reducido y
    Monte Carlo) y devuelve el diccionario de resultados. Si guardar_json
    es True (default), cachea la salida en Supabase."""

    if imprimir:
        print("=" * 45)
        print("SIMULADOR PRIMERA NACIONAL")
        print("=" * 45)

    estadisticas_obj = Estadisticas()

    estadisticas_obj.cargar_datos()
    estadisticas_obj.crear_equipos()
    estadisticas_obj.calcular_estadisticas()
    estadisticas_obj.calcular_ratings()
    estadisticas_obj.registrar_partidos_simulados_oficiales = True
    estadisticas_obj.partidos_simulados_oficiales = []

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
    # ARMADO DEL JSON PARA LA PÁGINA WEB / API
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
        "ratings_finales": _ratings_finales_nacional(estadisticas_obj),
        "partidos_simulados": estadisticas_obj.partidos_simulados_oficiales,
        "monte_carlo": {
            "A": mc_A,
            "B": mc_B
        },
        # "¿Qué necesita [Equipo]?" -- un objeto por equipo, ya calculado
        # por Estadisticas.monte_carlo() a partir de las simulaciones
        # exitosas (ver modelos/promotion_requirements.py). El frontend
        # solo lo renderiza, no recalcula nada.
        "requisitos_ascenso": estadisticas_obj.requisitos_ascenso,
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

    if guardar_json:
        try:
            data_access.save_simulation_output("nacional", "nacional", datos_web, n_sims)
            print("Resultado de simulación guardado en Supabase.")
        except Exception as e:
            print(f"Error al guardar la simulación en Supabase: {e}")

    return datos_web


def simular_hasta_campeon(equipo_objetivo, max_intentos=5000, imprimir=True):
    """Repite la simulación de la temporada (fase regular + final de ascenso +
    Reducido) hasta que `equipo_objetivo` consiga el ascenso -- ya sea
    ganando la final directa (1° ascenso) o el Reducido (2° ascenso).

    A diferencia de correr_simulacion(), acá NO se corre Monte Carlo en cada
    intento (sería carísimo repetir 1000 simulaciones por cada intento): en
    cada vuelta se simula una sola temporada completa, se revisa si el
    equipo pedido ascendió, y si no, se descarta y se prueba de nuevo con
    los mismos ratings (calculados una sola vez al principio, no hace falta
    recalcularlos en cada intento).

    Devuelve un dict con el detalle de la corrida ganadora (tabla final,
    marcador de la final de ascenso, bracket completo del Reducido y
    cuántos intentos hicieron falta), o None si no se logró en
    max_intentos intentos.
    """

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

        puntero_a = tablas["A"].iloc[0]["equipo"]
        puntero_b = tablas["B"].iloc[0]["equipo"]

        ganador_ascenso, perdedor_ascenso, detalle_final = estadisticas_obj.jugar_final_ascenso(puntero_a, puntero_b)
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
                    "equipo_a": puntero_a,
                    "equipo_b": puntero_b,
                    "ganador": ganador_ascenso,
                    "perdedor": perdedor_ascenso,
                    "detalle_marcador": detalle_final.get("marcador", [0, 0]),
                    "texto": detalle_final.get("texto", ""),
                },
                "reducido": detalle_reducido,
            }

            if imprimir:
                _imprimir_resultado_hasta_campeon(resultado, tablas)

            return resultado

    if imprimir:
        print(f"\nNo se logró el ascenso de {equipo_objetivo} en {max_intentos} intentos.")
    return None


def _imprimir_resultado_hasta_campeon(resultado, tablas):
    equipo_objetivo = resultado["equipo"]

    print(f"\n¡{equipo_objetivo} ASCENDIÓ! (tardó {resultado['intentos']} intentos)")
    print(f"Vía: {'ascenso directo (final)' if resultado['via'] == 'ascenso_directo' else 'Reducido'}")

    print("\n--- Tabla final de esa temporada ---")
    for zona, tabla_zona in tablas.items():
        print(f"\nZona {zona}")
        print(tabla_zona.to_string())

    fa = resultado["final_ascenso"]
    print(f"\n--- Final por el 1° ascenso ---")
    print(fa["texto"])
    print(f"Asciende directo: {fa['ganador']}")
    print(f"{fa['perdedor']} pasa al Reducido")

    print("\n--- Reducido (2° ascenso) ---")
    reducido = resultado["reducido"]

    print("\nPrimera ronda:")
    for partido in reducido["primera_ronda"]:
        print(f"  {partido['local']} {partido['golesLocal']} - {partido['golesVisitante']} {partido['visitante']}  (avanza {partido['avanza']})")

    print("\nCuartos de final:")
    for partido in reducido["cuartos"]:
        print(f"  {partido['local']} {partido['golesLocal']} - {partido['golesVisitante']} {partido['visitante']}  (avanza {partido['avanza']})")

    print("\nSemifinales:")
    for partido in reducido["semis"]:
        print(f"  {partido['local']} {partido['golesLocal']} - {partido['golesVisitante']} {partido['visitante']}  (avanza {partido['avanza']})")

    print("\nFinal del Reducido:")
    print(f"  {reducido['final']['detalle']}")
    print(f"  Campeón del Reducido (2° ascenso): {reducido['final']['campeon']}")


def main():
    print("=" * 45)
    print("SIMULADOR PRIMERA NACIONAL")
    print("=" * 45)
    print("1) Correr una simulación normal (tabla + Monte Carlo)")
    print("2) Simular hasta que un equipo salga campeón (ascienda)")

    opcion = input("\nElegí una opción (1/2): ").strip()

    if opcion == "2":
        equipo_objetivo = input("¿Qué equipo querés que ascienda?: ").strip()
        max_intentos = 5000
        try:
            simular_hasta_campeon(equipo_objetivo, max_intentos=max_intentos, imprimir=True)
        except ValueError as e:
            print(f"\nError: {e}")
    else:
        correr_simulacion(n_sims=1000, imprimir=True)


if __name__ == "__main__":
    main()
