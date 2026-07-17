# -*- coding: utf-8 -*-
import datetime

import data_access
import rutas
from modelos.estadisticas_ligapro import EstadisticasLigaPro

RUTA_JSON_LIGAPRO_DEFAULT = "data_ligapro.json"


def correr_simulacion_ligapro(n_sims=1000, imprimir=True, guardar_json=True):
    """Corre la simulación completa de LigaPro Serie A (Fase Inicial +
    Fase Final con Hexagonal Campeón / Cuadrangular Sudamericana /
    Hexagonal Descenso + Monte Carlo) y devuelve el diccionario de
    resultados."""

    if imprimir:
        print("=" * 45)
        print("SIMULADOR LIGAPRO SERIE A (ECUADOR)")
        print("=" * 45)

    e = EstadisticasLigaPro()
    e.cargar_datos_ligapro()
    e.crear_equipos_ligapro()
    e.calcular_estadisticas()
    e.calcular_ratings()
    e.registrar_partidos_simulados_oficiales = True
    e.partidos_simulados_oficiales = []

    if imprimir:
        print("\n--- Simulando temporada completa (Fase Inicial + Fase Final) ---")
    resultado = e.simular_temporada_ligapro()
    clasif = e.clasificar_zonas_ligapro(resultado)

    if imprimir:
        if resultado["fase_inicial"] is not None:
            print("\n--- Tabla final Fase Inicial ---")
            print(resultado["fase_inicial"].to_string())
        print("\n--- Hexagonal Campeón ---")
        print(resultado["hexagonal_campeon"].to_string())
        print("\n--- Cuadrangular Sudamericana ---")
        print(resultado["cuadrangular_sudamericana"].to_string())
        print("\n--- Hexagonal Descenso ---")
        print(resultado["hexagonal_descenso"].to_string())
        print(f"\nCAMPEÓN: {clasif['campeon']}")
        print(f"VICECAMPEÓN: {clasif['vicecampeon']}")
        print(f"LIBERTADORES: {clasif['libertadores']}")
        print(f"SUDAMERICANA (Hexagonal, 4°-6°): {clasif['sudamericana_hexagonal']}")
        print(f"SUDAMERICANA (Cuadrangular, 1°): {clasif['sudamericana_cuadrangular']}")
        print(f"DESCENSO: {clasif['descenso']}")

    if imprimir:
        print(f"\n--- Monte Carlo ({n_sims} simulaciones) ---")
    resumen_mc, tabla_esperada_mc = e.monte_carlo_ligapro(n_simulaciones=n_sims)
    if imprimir:
        print(resumen_mc.to_string())

    datos_web = {
        "liga": "ligapro",
        "n_simulaciones": n_sims,
        "generado": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "tabla_fase_inicial": (
            resultado["fase_inicial"].to_dict(orient="records")
            if resultado["fase_inicial"] is not None else None
        ),
        "hexagonal_campeon": resultado["hexagonal_campeon"].to_dict(orient="records"),
        "cuadrangular_sudamericana": resultado["cuadrangular_sudamericana"].to_dict(orient="records"),
        "hexagonal_descenso": resultado["hexagonal_descenso"].to_dict(orient="records"),
        "tabla_actual": e.tabla.sort_values(["zona", "posicion"]).to_dict(orient="records"),
        "campeon": clasif["campeon"],
        "vicecampeon": clasif["vicecampeon"],
        "libertadores": clasif["libertadores"],
        "sudamericana_hexagonal": clasif["sudamericana_hexagonal"],
        "sudamericana_cuadrangular": clasif["sudamericana_cuadrangular"],
        "descensos": clasif["descenso"],
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
            data_access.save_simulation_output("ligapro", "ligapro", datos_web, n_sims)
            if imprimir:
                print("\ndata_ligapro.json guardado en Supabase")
        except Exception as ex:
            print(f"Error al guardar data_ligapro.json en Supabase: {ex}")

    return datos_web


def simular_hasta_campeon_ligapro(equipo_objetivo, max_intentos=5000, imprimir=True):
    """Repite la temporada completa (Fase Inicial + Fase Final) hasta que
    `equipo_objetivo` salga campeón (1° del Hexagonal Campeón). Calcado
    de simular_hasta_campeon_brasileirao(), pero acá cada intento resuelve
    las DOS fases -- no hay vectorización posible en este camino porque
    se necesita el detalle partido a partido de una temporada puntual
    para mostrarla (a diferencia de monte_carlo_ligapro(), que solo
    necesita los totales agregados)."""

    if imprimir:
        print("=" * 45)
        print(f"SIMULANDO HASTA QUE SALGA CAMPEÓN: {equipo_objetivo}")
        print("=" * 45)

    e = EstadisticasLigaPro()
    e.cargar_datos_ligapro()
    e.crear_equipos_ligapro()
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

        # Restaurar el estado de arranque antes de cada intento (mismo
        # motivo que en monte_carlo_ligapro: _dividir_en_grupos_fase_final
        # reasigna la zona de los 16 equipos, y hay que devolverla a
        # FaseInicial -- o a la real, si la temporada ya está dividida --
        # antes del intento siguiente).
        for nombre, datos in estado_inicial.items():
            e.equipos[nombre].puntos = datos["puntos"]
            e.equipos[nombre].goles_favor = datos["gf"]
            e.equipos[nombre].goles_contra = datos["gc"]
            e.equipos[nombre].zona = datos["zona"]
        e.fixture = fixture_original.copy()
        e._pares_fixture_cache = None

        resultado = e.simular_temporada_ligapro()
        clasif = e.clasificar_zonas_ligapro(resultado)

        if clasif["campeon"] == equipo_objetivo:
            respuesta = {
                "equipo": equipo_objetivo,
                "intentos": intento,
                "tabla_fase_inicial": (
                    resultado["fase_inicial"].to_dict(orient="records")
                    if resultado["fase_inicial"] is not None else None
                ),
                "hexagonal_campeon": resultado["hexagonal_campeon"].to_dict(orient="records"),
                "cuadrangular_sudamericana": resultado["cuadrangular_sudamericana"].to_dict(orient="records"),
                "hexagonal_descenso": resultado["hexagonal_descenso"].to_dict(orient="records"),
                "vicecampeon": clasif["vicecampeon"],
                "libertadores": clasif["libertadores"],
                "sudamericana_hexagonal": clasif["sudamericana_hexagonal"],
                "sudamericana_cuadrangular": clasif["sudamericana_cuadrangular"],
                "descensos": clasif["descenso"],
            }
            if imprimir:
                print(f"\n¡{equipo_objetivo} SALIÓ CAMPEÓN! (intento {intento})")
            return respuesta

    if imprimir:
        print(f"\nNo se logró el título de {equipo_objetivo} en {max_intentos} intentos.")
    return None


def main():
    print("=" * 45)
    print("SIMULADOR LIGAPRO SERIE A")
    print("=" * 45)
    print("1) Correr una simulación normal (tabla + Monte Carlo)")
    print("2) Simular hasta que un equipo salga campeón")

    opcion = input("\nElegí una opción (1/2): ").strip()

    if opcion == "2":
        equipo_objetivo = input("¿Qué equipo querés que salga campeón?: ").strip()
        try:
            simular_hasta_campeon_ligapro(equipo_objetivo, max_intentos=5000, imprimir=True)
        except ValueError as e:
            print(f"\nError: {e}")
    else:
        correr_simulacion_ligapro(n_sims=1000, imprimir=True)


if __name__ == "__main__":
    main()
