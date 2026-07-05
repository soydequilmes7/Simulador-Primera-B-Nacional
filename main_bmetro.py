import json
import datetime

import data_access
import rutas
from modelos.estadisticas_bmetro import EstadisticasBMetro

RUTA_JSON_BMETRO_DEFAULT = "data_bmetro.json"


def correr_simulacion_bmetro(n_sims=1000, imprimir=True, guardar_json=True):
    """Corre la simulación completa de B Metropolitana (fase regular +
    ascenso directo + Reducido + Monte Carlo) y devuelve el diccionario de
    resultados. Mismo rol que correr_simulacion() de Nacional (main.py),
    pero para tabla única en vez de 2 zonas."""

    if imprimir:
        print("=" * 45)
        print("SIMULADOR PRIMERA B METROPOLITANA")
        print("=" * 45)

    e = EstadisticasBMetro()
    e.cargar_datos_bmetro()
    e.crear_equipos_bmetro()
    e.calcular_estadisticas()
    e.calcular_ratings()

    if imprimir:
        print("\n--- Tabla final simulada (temporada regular) ---")
    tablas = e.simular_fase_regular()
    tabla_unica = tablas["Unica"]

    if imprimir:
        print(tabla_unica.to_string())

    puntero = e.obtener_puntero(tabla_unica)
    if imprimir:
        print(f"\nASCIENDE DIRECTO: {puntero}")

    if imprimir:
        print("\n--- Torneo Reducido (2° ascenso) ---")
    campeon_reducido, detalle_reducido = e.jugar_reducido_bmetro(tabla_unica)
    if imprimir:
        print("\nCuartos (ida y vuelta):")
        for p in detalle_reducido["cuartos"]:
            print(f"  {p['detalle']} -> avanza {p['campeon']}")
        print("\nSemis (ida y vuelta):")
        for p in detalle_reducido["semis"]:
            print(f"  {p['detalle']} -> avanza {p['campeon']}")
        print(f"\nFinal: {detalle_reducido['final']['detalle']}")
        print(f"CAMPEÓN DEL REDUCIDO (2° ascenso): {campeon_reducido}")

    descendidos = tabla_unica.iloc[-e.DESCENSOS_N:]["equipo"].tolist()
    if imprimir:
        print(f"\nDESCIENDEN (posición en tabla, últimos {e.DESCENSOS_N}): {descendidos}")

    if imprimir:
        print(f"\n--- Monte Carlo ({n_sims} simulaciones) ---")
    resumen_mc, tabla_esperada_mc = e.monte_carlo_bmetro(n_simulaciones=n_sims)
    if imprimir:
        print(resumen_mc.to_string())

    datos_web = {
        "liga": "bmetro",
        "n_simulaciones": n_sims,
        "generado": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "tabla": tabla_unica.to_dict(orient="records"),
        "tabla_actual": (
            e.tabla.sort_values("posicion").to_dict(orient="records")
        ),
        "puntero_ascenso_directo": puntero,
        "reducido": detalle_reducido,
        "campeon_reducido": campeon_reducido,
        "descensos": descendidos,
        "monte_carlo": resumen_mc.to_dict(orient="records"),
        "tabla_esperada": tabla_esperada_mc.to_dict(orient="records"),
        "rachas": {
            nombre: equipo.ultimos10[-5:]
            for nombre, equipo in e.equipos.items()
        },
    }

    if guardar_json:
        try:
            data_access.save_simulation_output("bmetro", "bmetro", datos_web, n_sims)
            if imprimir:
                print("\ndata_bmetro.json guardado en Supabase")
        except Exception as ex:
            print(f"Error al guardar data_bmetro.json en Supabase: {ex}")

    return datos_web


def simular_hasta_ascenso_bmetro(equipo_objetivo, max_intentos=5000, imprimir=True):
    """Repite fase regular + Reducido hasta que `equipo_objetivo` ascienda
    (directo o por Reducido). Calcado de simular_hasta_campeon() de
    Nacional, adaptado a tabla única."""

    if imprimir:
        print("=" * 45)
        print(f"SIMULANDO HASTA QUE ASCIENDA: {equipo_objetivo}")
        print("=" * 45)

    e = EstadisticasBMetro()
    e.cargar_datos_bmetro()
    e.crear_equipos_bmetro()
    e.calcular_estadisticas()
    e.calcular_ratings()

    if equipo_objetivo not in e.equipos:
        sugerencias = [n for n in e.equipos if equipo_objetivo.lower() in n.lower()]
        mensaje = f"'{equipo_objetivo}' no es un equipo válido."
        if sugerencias:
            mensaje += f" ¿Quisiste decir: {', '.join(sugerencias)}?"
        raise ValueError(mensaje)

    for intento in range(1, max_intentos + 1):
        if imprimir and intento % 200 == 0:
            print(f"...intento {intento}, todavía no ascendió")

        tablas = e.simular_fase_regular()
        tabla_unica = tablas["Unica"]
        puntero = e.obtener_puntero(tabla_unica)

        if puntero == equipo_objetivo:
            resultado = {
                "equipo": equipo_objetivo,
                "intentos": intento,
                "via": "ascenso_directo",
                "tabla": tabla_unica.to_dict(orient="records"),
            }
            if imprimir:
                print(f"\n¡{equipo_objetivo} ASCENDIÓ DIRECTO! (intento {intento})")
            return resultado

        campeon_reducido, detalle_reducido = e.jugar_reducido_bmetro(tabla_unica)
        if campeon_reducido == equipo_objetivo:
            resultado = {
                "equipo": equipo_objetivo,
                "intentos": intento,
                "via": "reducido",
                "tabla": tabla_unica.to_dict(orient="records"),
                "reducido": detalle_reducido,
            }
            if imprimir:
                print(f"\n¡{equipo_objetivo} ASCENDIÓ POR EL REDUCIDO! (intento {intento})")
            return resultado

    if imprimir:
        print(f"\nNo se logró el ascenso de {equipo_objetivo} en {max_intentos} intentos.")
    return None


def main():
    print("=" * 45)
    print("SIMULADOR PRIMERA B METROPOLITANA")
    print("=" * 45)
    print("1) Correr una simulación normal (tabla + Monte Carlo)")
    print("2) Simular hasta que un equipo ascienda")

    opcion = input("\nElegí una opción (1/2): ").strip()

    if opcion == "2":
        equipo_objetivo = input("¿Qué equipo querés que ascienda?: ").strip()
        try:
            simular_hasta_ascenso_bmetro(equipo_objetivo, max_intentos=5000, imprimir=True)
        except ValueError as e:
            print(f"\nError: {e}")
    else:
        correr_simulacion_bmetro(n_sims=1000, imprimir=True)


if __name__ == "__main__":
    main()
