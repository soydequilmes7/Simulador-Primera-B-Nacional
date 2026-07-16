# -*- coding: utf-8 -*-
import datetime

import data_access
import rutas
from modelos.estadisticas_brasileirao import EstadisticasBrasileirao

RUTA_JSON_BRASILEIRAO_DEFAULT = "data_brasileirao.json"


def correr_simulacion_brasileirao(n_sims=1000, imprimir=True, guardar_json=True):
    """Corre la simulación completa del Brasileirão (fase regular +
    clasificación por posición: Libertadores directa/previa, Sudamericana,
    descenso + Monte Carlo) y devuelve el diccionario de resultados.
    Mismo rol que correr_simulacion_bmetro(), pero sin Reducido -- acá la
    tabla final ES la clasificación, no hay partidos extra."""

    if imprimir:
        print("=" * 45)
        print("SIMULADOR BRASILEIRÃO SÉRIE A")
        print("=" * 45)

    e = EstadisticasBrasileirao()
    e.cargar_datos_brasileirao()
    e.crear_equipos_brasileirao()
    e.calcular_estadisticas()
    e.calcular_ratings()
    e.registrar_partidos_simulados_oficiales = True
    e.partidos_simulados_oficiales = []

    if imprimir:
        print("\n--- Tabla final simulada (temporada regular) ---")
    tablas = e.simular_fase_regular()
    tabla_unica = tablas["Unica"]

    if imprimir:
        print(tabla_unica.to_string())

    campeon = e.obtener_puntero(tabla_unica)
    zonas = e.clasificar_zonas(tabla_unica)

    if imprimir:
        print(f"\nCAMPEÓN: {campeon}")
        print(f"LIBERTADORES (fase de grupos, pos. 1-{e.LIBERTADORES_DIRECTA_N}): "
              f"{zonas['libertadores_directa']}")
        print(f"LIBERTADORES (previa, pos. {e.LIBERTADORES_DIRECTA_N + 1}-{e.LIBERTADORES_PREVIA_N}): "
              f"{zonas['libertadores_previa']}")
        print(f"SUDAMERICANA (pos. {e.LIBERTADORES_PREVIA_N + 1}-{e.SUDAMERICANA_N}): "
              f"{zonas['sudamericana']}")
        print(f"DESCENSO (últimos {e.DESCENSOS_N}): {zonas['descenso']}")

    if imprimir:
        print(f"\n--- Monte Carlo ({n_sims} simulaciones) ---")
    resumen_mc, tabla_esperada_mc = e.monte_carlo_brasileirao(n_simulaciones=n_sims)
    if imprimir:
        print(resumen_mc.to_string())

    datos_web = {
        "liga": "brasileirao",
        "n_simulaciones": n_sims,
        "generado": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "tabla": tabla_unica.to_dict(orient="records"),
        "tabla_actual": (
            e.tabla.sort_values("posicion").to_dict(orient="records")
        ),
        "campeon": campeon,
        "libertadores_directa": zonas["libertadores_directa"],
        "libertadores_previa": zonas["libertadores_previa"],
        "sudamericana": zonas["sudamericana"],
        "descensos": zonas["descenso"],
        "partidos_simulados": e.partidos_simulados_oficiales,
        "monte_carlo": resumen_mc.to_dict(orient="records"),
        "tabla_esperada": tabla_esperada_mc.to_dict(orient="records"),
        "rachas": {
            nombre: equipo.ultimos10[-5:]
            for nombre, equipo in e.equipos.items()
        },
    }

    if guardar_json:
        try:
            data_access.save_simulation_output("brasileirao", "brasileirao", datos_web, n_sims)
            if imprimir:
                print("\ndata_brasileirao.json guardado en Supabase")
        except Exception as ex:
            print(f"Error al guardar data_brasileirao.json en Supabase: {ex}")

    return datos_web


def simular_hasta_campeon_brasileirao(equipo_objetivo, max_intentos=5000, imprimir=True):
    """Repite la fase regular hasta que `equipo_objetivo` salga campeón
    (puntero de la tabla final). Calcado de simular_hasta_ascenso_bmetro(),
    pero sin la parte de Reducido porque acá no existe."""

    if imprimir:
        print("=" * 45)
        print(f"SIMULANDO HASTA QUE SALGA CAMPEÓN: {equipo_objetivo}")
        print("=" * 45)

    e = EstadisticasBrasileirao()
    e.cargar_datos_brasileirao()
    e.crear_equipos_brasileirao()
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
            print(f"...intento {intento}, todavía no salió campeón")

        tablas = e.simular_fase_regular()
        tabla_unica = tablas["Unica"]
        campeon = e.obtener_puntero(tabla_unica)

        if campeon == equipo_objetivo:
            resultado = {
                "equipo": equipo_objetivo,
                "intentos": intento,
                "tabla": tabla_unica.to_dict(orient="records"),
            }
            if imprimir:
                print(f"\n¡{equipo_objetivo} SALIÓ CAMPEÓN! (intento {intento})")
            return resultado

    if imprimir:
        print(f"\nNo se logró el título de {equipo_objetivo} en {max_intentos} intentos.")
    return None


def main():
    print("=" * 45)
    print("SIMULADOR BRASILEIRÃO SÉRIE A")
    print("=" * 45)
    print("1) Correr una simulación normal (tabla + Monte Carlo)")
    print("2) Simular hasta que un equipo salga campeón")

    opcion = input("\nElegí una opción (1/2): ").strip()

    if opcion == "2":
        equipo_objetivo = input("¿Qué equipo querés que salga campeón?: ").strip()
        try:
            simular_hasta_campeon_brasileirao(equipo_objetivo, max_intentos=5000, imprimir=True)
        except ValueError as e:
            print(f"\nError: {e}")
    else:
        correr_simulacion_brasileirao(n_sims=1000, imprimir=True)


if __name__ == "__main__":
    main()
