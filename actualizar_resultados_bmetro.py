# -*- coding: utf-8 -*-
"""
actualizar_resultados_bmetro.py

Versión B Metropolitana de actualizar_resultados.py, calcada de
actualizar_resultados_lpf.py con estas diferencias:

  1. Usa scraper_promiedos_bmetro.py (league id "fahh").
  2. Lee/escribe fixture_bmetro.csv, resultados_bmetro.csv y
     tabla_bmetro.csv.
  3. calcular_tabla_bmetro.py no tiene zonas (B Metro es tabla única).
  4. NO corre una simulación al final por default -- todavía no hay un
     motor de simulación armado para B Metro (equivalente a
     correr_simulacion_lpf de main_lpf.py). Cuando lo armemos, se pasa
     igual por el parámetro correr_simulacion_fn.

Uso manual:
    python actualizar_resultados_bmetro.py

Uso programático:
    from actualizar_resultados_bmetro import actualizar
    resultado = actualizar()
    # o, cuando exista el simulador de B Metro:
    resultado = actualizar(correr_simulacion_fn=correr_simulacion_bmetro)
"""
from datetime import datetime

from db.repository import transaction

from scraper_promiedos_bmetro import obtener_partidos_jugados_bmetro
from calcular_tabla_bmetro import _aplicar_partido, _reordenar_posiciones

CAMPOS_FIXTURE = ["fecha", "jornada", "equipo_local", "equipo_visitante"]
CAMPOS_RESULTADOS = ["fecha", "jornada", "equipo_local", "equipo_visitante",
                      "goles_local", "goles_visitante"]


def actualizar(n_sims=1000, correr_simulacion_fn=None, imprimir=True):
    ahora = datetime.now().isoformat(timespec="seconds")

    with transaction() as repo:
        fixture = repo.match_records("bmetro", "pending")
        resultados = repo.match_records("bmetro", "played")

    if imprimir:
        print(f"[{ahora}] Scrapeando Promiedos (B Metropolitana)...")

    partidos_jugados = obtener_partidos_jugados_bmetro()

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
    indices_a_borrar = []

    for p in partidos_jugados:
        clave = (p["equipo_local"], p["equipo_visitante"])
        if clave in resultados_ya_cargados:
            continue
        if clave in indice_fixture:
            idx = indice_fixture[clave]
            fila_fixture = fixture[idx]
            resultados.append({
                "fecha": fila_fixture.get("fecha", ""),
                "jornada": fila_fixture.get("jornada", ""),
                "equipo_local": p["equipo_local"],
                "equipo_visitante": p["equipo_visitante"],
                "goles_local": p["goles_local"],
                "goles_visitante": p["goles_visitante"],
            })
            indices_a_borrar.append(idx)
            cargados.append(p)
            resultados_ya_cargados.add(clave)
        else:
            sin_matchear.append(p)

    if not cargados:
        if imprimir:
            print("  No hay partidos nuevos para cargar (todo ya estaba al día).")
        _guardar_log(ahora, cargados, sin_matchear, simulacion_corrida=False)
        # Aunque no haya partidos nuevos, re-simulamos con los datos
        # actuales de Supabase y devolvemos `datos`. El snapshot estático
        # (data_bmetro.json) que sirve la página puede estar más viejo que
        # lo que ya hay cargado en Supabase, así que el frontend usa este
        # `datos` para refrescar tabla/racha en vez de quedarse con el
        # snapshot viejo. Ver correrActualizacionBMetro() en index.html.
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
        repo.replace_matches("bmetro", fixture_restante, resultados)
        filas = repo.standing_records("bmetro")
        indice = {f["equipo"]: f for f in filas}
        for p in cargados:
            _aplicar_partido(
                indice, p["equipo_local"], p["equipo_visitante"],
                int(p["goles_local"]), int(p["goles_visitante"]),
            )
        repo.upsert_standings("bmetro", _reordenar_posiciones(filas))

    datos = None
    simulacion_corrida = False
    if correr_simulacion_fn is not None:
        if imprimir:
            print(f"  Cargados {len(cargados)} partidos nuevos. Re-simulando...")
        datos = correr_simulacion_fn(n_sims=n_sims, imprimir=imprimir, guardar_json=True)
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
        repo.log_update("bmetro", cargados, sin_matchear, simulacion_corrida, timestamp=timestamp)


if __name__ == "__main__":
    resultado = actualizar()
    if resultado["actualizado"]:
        print("\n✓ Actualización completa.")
    else:
        print("\n– Sin cambios.")
