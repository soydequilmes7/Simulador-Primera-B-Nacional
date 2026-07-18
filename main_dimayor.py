# -*- coding: utf-8 -*-
import datetime

import data_access
import rutas
from modelos.estadisticas_dimayor import EstadisticasDimayor
from calcular_tabla_dimayor import construir_tabla_apertura

RUTA_JSON_DIMAYOR_DEFAULT = "data_dimayor.json"


def correr_simulacion_dimayor(n_sims=1000, imprimir=True, guardar_json=True):
    """Corre la simulación completa de Liga BetPlay Dimayor (Torneo
    Clausura: fase regular + Cuadrangulares + Final + Monte Carlo) y
    devuelve el diccionario de resultados. La tabla final del Torneo
    Apertura se agrega tal cual (informativa, sin simular)."""

    if imprimir:
        print("=" * 45)
        print("SIMULADOR LIGA BETPLAY DIMAYOR (COLOMBIA) - TORNEO CLAUSURA")
        print("=" * 45)

    e = EstadisticasDimayor()
    e.cargar_datos_dimayor()
    e.crear_equipos_dimayor()
    e.calcular_estadisticas()
    e.calcular_ratings()
    e.registrar_partidos_simulados_oficiales = True
    e.partidos_simulados_oficiales = []

    if imprimir:
        print("\n--- Simulando Torneo Clausura (fase regular + Cuadrangulares + Final) ---")
    resultado = e.simular_temporada_dimayor()

    if imprimir:
        if resultado["fase_regular"] is not None:
            print("\n--- Tabla final fase regular (Clausura) ---")
            print(resultado["fase_regular"].to_string())
        print("\n--- Cuadrangular Grupo A ---")
        print(resultado["grupo_a"].to_string())
        print("\n--- Cuadrangular Grupo B ---")
        print(resultado["grupo_b"].to_string())
        print(f"\n{resultado['detalle_final']['texto']}")
        print(f"\nCAMPEÓN: {resultado['campeon']}")
        print(f"SUBCAMPEÓN: {resultado['subcampeon']}")

    if imprimir:
        print(f"\n--- Monte Carlo ({n_sims} simulaciones) ---")
    resumen_mc, tabla_esperada_mc, matriz_posiciones_mc = e.monte_carlo_dimayor(n_simulaciones=n_sims)
    if imprimir:
        print(resumen_mc.to_string())

    # Tabla final del Torneo Apertura: informativa, no pasa por el
    # motor. Se lee del CSV local que arma scraper_promiedos_dimayor.py
    # (resultados_apertura_dimayor.csv) -- no pega contra la red en
    # cada simulación. Si el archivo no existe/está vacío todavía
    # (nunca se corrió el scraper), devuelve lista vacía y el frontend
    # puede mostrar "no disponible" en esa sección.
    tabla_apertura = construir_tabla_apertura()

    # Tabla de promedios REAL actual (no depende de esta corrida puntual
    # de Monte Carlo): usa la tabla del Clausura tal cual está hoy
    # (e.tabla, antes de simular ningún partido pendiente) para mostrar
    # dónde está parado cada equipo en la lucha por el descenso AHORA
    # MISMO -- la que de verdad importa para "saber el descenso".
    tabla_promedios_actual = e.calcular_tabla_promedios(e.tabla)
    descensos_promedio_actual = e.calcular_descensos_promedio(tabla_promedios_actual)

    datos_web = {
        "liga": "dimayor",
        "torneo": "Clausura",
        "n_simulaciones": n_sims,
        "generado": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "tabla_apertura_final": tabla_apertura,
        "tabla_fase_regular": (
            resultado["fase_regular"].to_dict(orient="records")
            if resultado["fase_regular"] is not None else None
        ),
        "cuadrangular_grupo_a": resultado["grupo_a"].to_dict(orient="records"),
        "cuadrangular_grupo_b": resultado["grupo_b"].to_dict(orient="records"),
        "tabla_actual": e.tabla.sort_values(["zona", "posicion"]).to_dict(orient="records"),
        "campeon": resultado["campeon"],
        "subcampeon": resultado["subcampeon"],
        "detalle_final": resultado["detalle_final"],
        "tabla_promedios_actual": tabla_promedios_actual.to_dict(orient="records"),
        "descensos_promedio_actual": descensos_promedio_actual,
        "tabla_promedios_simulada": (
            resultado["tabla_promedios"].to_dict(orient="records")
            if resultado["tabla_promedios"] is not None else None
        ),
        "descensos_promedio_simulado": resultado["descensos_promedio"],
        "partidos_simulados": e.partidos_simulados_oficiales,
        "monte_carlo": resumen_mc.to_dict(orient="records"),
        "tabla_esperada": tabla_esperada_mc.to_dict(orient="records"),
        "matriz_posiciones": matriz_posiciones_mc.to_dict(orient="records"),
        "rachas": {
            nombre: equipo.ultimos10[-5:]
            for nombre, equipo in e.equipos.items()
        },
    }

    if guardar_json:
        try:
            data_access.save_simulation_output("dimayor", "dimayor", datos_web, n_sims)
            if imprimir:
                print("\ndata_dimayor.json guardado en Supabase")
        except Exception as ex:
            print(f"Error al guardar data_dimayor.json en Supabase: {ex}")

    return datos_web


def simular_hasta_campeon_dimayor(equipo_objetivo, max_intentos=5000, imprimir=True):
    """Repite la temporada del Clausura hasta que `equipo_objetivo`
    salga campeón. Calcado de simular_hasta_campeon_ligapro()."""

    if imprimir:
        print("=" * 45)
        print(f"SIMULANDO HASTA QUE SALGA CAMPEÓN: {equipo_objetivo}")
        print("=" * 45)

    e = EstadisticasDimayor()
    e.cargar_datos_dimayor()
    e.crear_equipos_dimayor()
    e.calcular_estadisticas()
    e.calcular_ratings()

    if equipo_objetivo not in e.equipos:
        sugerencias = [n for n in e.equipos if equipo_objetivo.lower() in n.lower()]
        mensaje = f"'{equipo_objetivo}' no es un equipo válido."
        if sugerencias:
            mensaje += f" ¿Quisiste decir: {', '.join(sugerencias)}?"
        raise ValueError(mensaje)

    estado_inicial = {
        nombre: {"puntos": eq.puntos, "gf": eq.goles_favor, "gc": eq.goles_contra, "zona": eq.zona}
        for nombre, eq in e.equipos.items()
    }
    fixture_original = e.fixture.copy()

    for intento in range(1, max_intentos + 1):
        if imprimir and intento % 200 == 0:
            print(f"...intento {intento}, todavía no salió campeón")

        for nombre, datos in estado_inicial.items():
            e.equipos[nombre].puntos = datos["puntos"]
            e.equipos[nombre].goles_favor = datos["gf"]
            e.equipos[nombre].goles_contra = datos["gc"]
            e.equipos[nombre].zona = datos["zona"]
        e.fixture = fixture_original.copy()
        e._pares_fixture_cache = None

        resultado = e.simular_temporada_dimayor()

        if resultado["campeon"] == equipo_objetivo:
            respuesta = {
                "equipo": equipo_objetivo,
                "intentos": intento,
                "tabla_fase_regular": (
                    resultado["fase_regular"].to_dict(orient="records")
                    if resultado["fase_regular"] is not None else None
                ),
                "cuadrangular_grupo_a": resultado["grupo_a"].to_dict(orient="records"),
                "cuadrangular_grupo_b": resultado["grupo_b"].to_dict(orient="records"),
                "subcampeon": resultado["subcampeon"],
                "detalle_final": resultado["detalle_final"],
            }
            if imprimir:
                print(f"\n¡{equipo_objetivo} SALIÓ CAMPEÓN! (intento {intento})")
            return respuesta

    if imprimir:
        print(f"\nNo se logró el título de {equipo_objetivo} en {max_intentos} intentos.")
    return None


def main():
    print("=" * 45)
    print("SIMULADOR LIGA BETPLAY DIMAYOR")
    print("=" * 45)
    print("1) Correr una simulación normal (tabla + Monte Carlo)")
    print("2) Simular hasta que un equipo salga campeón")

    opcion = input("\nElegí una opción (1/2): ").strip()

    if opcion == "2":
        equipo_objetivo = input("¿Qué equipo querés que salga campeón?: ").strip()
        try:
            simular_hasta_campeon_dimayor(equipo_objetivo, max_intentos=5000, imprimir=True)
        except ValueError as e:
            print(f"\nError: {e}")
    else:
        correr_simulacion_dimayor(n_sims=1000, imprimir=True)


if __name__ == "__main__":
    main()
