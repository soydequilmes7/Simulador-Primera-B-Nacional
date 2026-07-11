import json
from datetime import datetime

import data_access
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


def _ratings_finales_lpf(e):
    """Ratings finales de cada Equipo LPF DESPUÉS de calcular_ratings_lpf(),
    en el shape que espera ResultadoTorneo.ratings_finales (addendum
    Etapa 6, punto 3): {nombre: {ataque_local, ataque_visitante,
    defensa_local, defensa_visitante}}. Es la fuente para bootstrapear
    el Apertura simulado de la temporada siguiente (clubes que
    continúan en LPF)."""
    return {
        nombre: {
            "ataque_local": equipo.ataque_local,
            "ataque_visitante": equipo.ataque_visitante,
            "defensa_local": equipo.defensa_local,
            "defensa_visitante": equipo.defensa_visitante,
        }
        for nombre, equipo in e.equipos.items()
    }


def armar_datos_web_lpf(e, tablas_clausura, campeon_clausura, detalle_playoffs,
                         tabla_anual, tabla_promedios, descensos, copas, trofeo,
                         n_sims, resumen_mc, tabla_esperada_mc, detalle_playoffs_apertura=None,
                         playoffs_apertura_es_real=False):
    """Arma el dict con la forma que espera template.html (sección LPF) y
    que se puede tirar directo a JSON."""
    mc_A = resumen_mc[resumen_mc["zona"] == "A"].drop(columns=["zona"]).to_dict(orient="records")
    mc_B = resumen_mc[resumen_mc["zona"] == "B"].drop(columns=["zona"]).to_dict(orient="records")

    return {
        "liga": "lpf",
        "generado": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "n_simulaciones": n_sims,
        # Instancia, no clase: e.CAMPEON_APERTURA puede estar pisado por el
        # campeón dinámico del Apertura (ver cargar_datos_lpf()).
        "campeon_apertura": e.CAMPEON_APERTURA,
        "apertura": _apertura_a_zonas(e.apertura),
        "tablas_clausura": {
            "A": _tabla_a_lista(tablas_clausura["A"]),
            "B": _tabla_a_lista(tablas_clausura["B"]),
        },
        "playoffs": detalle_playoffs,
        # Cuadro del Apertura para Modo Temporada -- ver el comentario
        # largo en correr_simulacion_lpf() (BUG REPORTADO: "no muestra
        # el bracket del Apertura"). "playoffs_apertura_es_real" le
        # dice al frontend si esto es el cuadro REAL que definió a
        # campeon_apertura (ronda 2 en adelante) o el ilustrativo/
        # ficticio de siempre (ronda 1, sin bracket real disponible)
        # -- el frontend solo debe mostrarlo cuando es real, para no
        # repetir la confusión original de dos campeones distintos.
        "playoffs_apertura": detalle_playoffs_apertura,
        "playoffs_apertura_es_real": playoffs_apertura_es_real,
        "campeon_clausura": campeon_clausura,
        "tabla_anual": _tabla_a_lista(tabla_anual),
        "tabla_promedios": _tabla_promedios_a_lista(tabla_promedios),
        "tabla_actual": _tabla_actual_clausura(e),
        "rachas": _rachas_lpf(e),
        "ratings_finales": _ratings_finales_lpf(e),
        "partidos_simulados": getattr(e, "partidos_simulados_oficiales", []),
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
    data_access.save_simulation_output("lpf", "lpf", datos_web, datos_web.get("n_simulaciones"))
    return "simulation_outputs:lpf"


def correr_simulacion_lpf(imprimir=True, guardar_json=True, n_sims=300):
    e = EstadisticasLPF()
    e.cargar_datos_lpf()
    e.crear_equipos_lpf()
    if len(e.resultados) > 0:
        # Llena equipo.ultimos10 (rachas del buscador). Con 0 resultados
        # no aporta nada, así que se saltea.
        e.calcular_estadisticas()
    e.calcular_ratings_lpf()
    e.registrar_partidos_simulados_oficiales = True
    e.partidos_simulados_oficiales = []

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

    # Cuadro de playoffs del Apertura para Modo Temporada. BUG
    # REPORTADO ("no muestra el bracket del Apertura, solo el del
    # Clausura, o capaz al revés"): para temporadas hipotéticas (ronda
    # 2 en adelante) el Apertura SÍ tiene un cuadro real -- es el que
    # definió e.CAMPEON_APERTURA en HistoryManager.persist_season()
    # (ver simular_apertura_desde_carryover()) -- pero antes se tiraba
    # y acá se generaba un segundo cuadro FICTICIO con un ganador
    # random que casi nunca coincidía, así que el frontend lo tenía
    # bloqueado siempre. Ahora, si hay un bracket real capturado para
    # esta ronda (data_access.playoffs_apertura_lpf(), monkeypincheado
    # por api/index.py con el de la ronda que se acaba de simular), se
    # usa ESE -- coincide 100% con e.CAMPEON_APERTURA porque es el
    # mismo cuadro que lo definió. Si no hay nada guardado (ronda 1: la
    # temporada real 2026, cuyo Apertura no tuvo playoffs de verdad),
    # se cae al cuadro ilustrativo/ficticio de siempre, marcado como tal.
    detalle_playoffs_apertura_real = data_access.playoffs_apertura_lpf()
    playoffs_apertura_es_real = detalle_playoffs_apertura_real is not None
    if playoffs_apertura_es_real:
        detalle_playoffs_apertura = detalle_playoffs_apertura_real
        if imprimir:
            print("\n--- Playoffs del Apertura (bracket REAL, definió al campeón) ---")
            print(f"CAMPEÓN DEL APERTURA: {e.CAMPEON_APERTURA}")
    else:
        if imprimir:
            print("\n--- Playoffs del Apertura (SIMULADO, ficticio) ---")
        detalle_playoffs_apertura = e.simular_playoffs_apertura()
        if imprimir:
            print(f"CAMPEÓN SIMULADO DEL APERTURA: {detalle_playoffs_apertura['campeon_apertura_simulado']} "
                  f"(campeón real: {e.CAMPEON_APERTURA})")

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
        detalle_playoffs_apertura=detalle_playoffs_apertura,
        playoffs_apertura_es_real=playoffs_apertura_es_real,
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
