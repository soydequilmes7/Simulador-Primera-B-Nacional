# -*- coding: utf-8 -*-
"""
actualizar_resultados_dimayor.py

Versión Dimayor de actualizar_resultados_primerac.py: scrapea
Promiedos, carga los partidos nuevos del Clausura contra el fixture
pendiente, actualiza Supabase y (si se pasa correr_simulacion_fn)
re-simula.

Uso manual:
    python actualizar_resultados_dimayor.py

Uso programático:
    from actualizar_resultados_dimayor import actualizar
    from main_dimayor import correr_simulacion_dimayor
    resultado = actualizar(correr_simulacion_fn=correr_simulacion_dimayor)
"""
from datetime import datetime

from db.repository import bootstrap_league_from_csv, transaction

from scraper_promiedos_dimayor import obtener_partidos_jugados_dimayor
from calcular_tabla_dimayor import aplicar_partidos

CAMPOS_FIXTURE = ["fecha", "jornada", "equipo_local", "equipo_visitante"]
CAMPOS_RESULTADOS = ["fecha", "jornada", "equipo_local", "equipo_visitante",
                      "goles_local", "goles_visitante"]


def actualizar(n_sims=1000, correr_simulacion_fn=None, imprimir=True):
    ahora = datetime.now().isoformat(timespec="seconds")
    bootstrap_league_from_csv("dimayor")

    with transaction() as repo:
        fixture = repo.match_records("dimayor", "pending")
        resultados = repo.match_records("dimayor", "played")

    if imprimir:
        print(f"[{ahora}] Scrapeando Promiedos (Liga BetPlay Dimayor)...")

    partidos_jugados = obtener_partidos_jugados_dimayor()

    if imprimir:
        print(f"  {len(partidos_jugados)} partidos jugados vistos en Promiedos")

    indice_fixture = {}
    for i, fila in enumerate(fixture):
        clave = (fila["equipo_local"], fila["equipo_visitante"])
        indice_fixture[clave] = i
    resultados_ya_cargados = {
        (fila["equipo_local"], fila["equipo_visitante"])
        for fila in resultados
    }

    sin_matchear = []
    cargados = []
    elo_cargados = []
    indices_a_borrar = []

    for p in partidos_jugados:
        clave = (p["equipo_local"], p["equipo_visitante"])
        if clave in resultados_ya_cargados:
            continue
        if clave in indice_fixture:
            idx = indice_fixture[clave]
            fila_fixture = fixture[idx]
            resultado_cargado = {
                "fecha": fila_fixture.get("fecha", ""),
                "jornada": fila_fixture.get("jornada", ""),
                "equipo_local": p["equipo_local"],
                "equipo_visitante": p["equipo_visitante"],
                "goles_local": p["goles_local"],
                "goles_visitante": p["goles_visitante"],
            }
            resultados.append(resultado_cargado)
            indices_a_borrar.append(idx)
            cargados.append(p)
            elo_cargados.append(resultado_cargado)
            resultados_ya_cargados.add(clave)
        else:
            sin_matchear.append(p)

    if not cargados:
        if imprimir:
            print("  No hay partidos nuevos para cargar (todo ya estaba al día).")
        _guardar_log(ahora, cargados, sin_matchear, simulacion_corrida=False)
        datos = None
        if correr_simulacion_fn is not None:
            datos = correr_simulacion_fn(n_sims=n_sims, imprimir=False, guardar_json=False)
        return {
            "actualizado": False,
            "cargados": cargados,
            "sin_matchear": sin_matchear,
            "datos": datos,
            "mensaje": "No había partidos nuevos jugados que coincidan con el fixture pendiente.",
        }

    fixture_restante = [f for i, f in enumerate(fixture) if i not in indices_a_borrar]

    with transaction() as repo:
        repo.replace_matches("dimayor", fixture_restante, resultados)
        tabla_nueva = aplicar_partidos(repo.standing_records("dimayor"), cargados)
        repo.upsert_standings("dimayor", tabla_nueva)
        elo_actualizados = repo.apply_club_rating_events(
            "dimayor", elo_cargados, source="real_results", metadata={"origen": "actualizar_resultados_dimayor.py"}
        )
        if imprimir:
            print(f"  tabla_dimayor.csv actualizada con {len(cargados)} partido(s) nuevo(s).")
            print(f"  ELO persistente actualizado con {elo_actualizados} partido(s).")

    datos = None
    simulacion_corrida = False
    if correr_simulacion_fn is not None:
        if imprimir:
            print(f"  Cargados {len(cargados)} partidos nuevos. Re-simulando...")
        guardar_json = True
        try:
            import rutas as _rutas
            guardar_json = not _rutas.en_vercel()
        except (ImportError, AttributeError):
            pass
        datos = correr_simulacion_fn(n_sims=n_sims, imprimir=imprimir, guardar_json=guardar_json)
        simulacion_corrida = True
    elif imprimir:
        print(f"  Cargados {len(cargados)} partidos nuevos. "
              f"(sin correr_simulacion_fn -> no se corrió ninguna simulación)")

    _guardar_log(ahora, cargados, sin_matchear, simulacion_corrida=simulacion_corrida)

    return {
        "actualizado": True,
        "cargados": cargados,
        "sin_matchear": sin_matchear,
        "datos": datos,
    }


def _guardar_log(timestamp, cargados, sin_matchear, simulacion_corrida):
    with transaction() as repo:
        repo.log_update("dimayor", cargados, sin_matchear, simulacion_corrida, timestamp=timestamp)


if __name__ == "__main__":
    resultado = actualizar()
    if resultado["actualizado"]:
        print("\n✓ Actualización completa.")
    else:
        print("\n– Sin cambios.")
