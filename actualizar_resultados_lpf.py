# -*- coding: utf-8 -*-
"""
actualizar_resultados_lpf.py

Versión LPF de actualizar_resultados.py. Diferencias a propósito con el
original (Nacional):

  1. Usa scraper_promiedos_lpf.py en vez de scraper_promiedos.py.
  2. Lee/escribe fixture_lpf.csv, resultados_lpf.csv y tabla_lpf.csv
     (no pisa los archivos de Nacional).
  3. NO usa mapeo_equipos.py: los nombres de equipo de Promiedos ya
     coinciden tal cual con los de tabla_lpf.csv, así que no hace falta
     traducir nada.
  4. NO toca goleadores: esta API de Promiedos no expone goleadores
     para la LPF, así que ese paso queda salteado (a diferencia de
     Nacional, que sí lo hace).
  5. NO corre una simulación al final por default. main.py/estadisticas.py
     están armados para el modelo de ascenso/descenso de la Nacional y
     todavía no hay un equivalente para la LPF (2 zonas + fase
     interzonal, sin promedios de descenso todavía definidos acá). Si
     ya tenés (o armamos) un correr_simulacion_lpf(), pasalo por el
     parámetro correr_simulacion_fn y se llama solo cuando haya
     partidos nuevos, igual que en Nacional.

Uso manual:
    python actualizar_resultados_lpf.py

Uso programático (por ejemplo desde servidor.py):
    from actualizar_resultados_lpf import actualizar
    resultado = actualizar()
    # o, cuando exista el simulador de LPF:
    resultado = actualizar(correr_simulacion_fn=correr_simulacion_lpf)
"""
from datetime import datetime

from db.repository import transaction

from scraper_promiedos_lpf import obtener_partidos_jugados_lpf
from calcular_tabla_lpf import _aplicar_partido, _reordenar_posiciones

CAMPOS_FIXTURE = ["fecha", "jornada", "equipo_local", "equipo_visitante"]
CAMPOS_RESULTADOS = ["fecha", "jornada", "equipo_local", "equipo_visitante",
                      "goles_local", "goles_visitante"]


def actualizar(n_sims=1000, correr_simulacion_fn=None, imprimir=True):
    """
    Corre todo el proceso para la LPF. Devuelve un dict con el resultado,
    pensado para poder loguearse o devolverse como JSON desde el
    servidor web (igual que la versión Nacional).

    correr_simulacion_fn: función opcional tipo
        correr_simulacion_fn(n_sims=..., imprimir=..., guardar_json=...)
    Se llama solo si hay partidos nuevos cargados. Si no se pasa nada,
    se saltea el paso de simulación (ver docstring del módulo).
    """
    ahora = datetime.now().isoformat(timespec="seconds")

    with transaction() as repo:
        fixture = repo.match_records("lpf", "pending")
        resultados = repo.match_records("lpf", "played")

    if imprimir:
        print(f"[{ahora}] Scrapeando Promiedos (LPF)...")

    partidos_jugados = obtener_partidos_jugados_lpf()

    if imprimir:
        print(f"  {len(partidos_jugados)} partidos jugados vistos en Promiedos")

    # Como no hace falta traducir nombres, matcheamos directo contra el
    # fixture pendiente por (equipo_local, equipo_visitante).
    indice_fixture = {}
    for i, fila in enumerate(fixture):
        clave = (fila["equipo_local"], fila["equipo_visitante"])
        indice_fixture[clave] = i

    sin_matchear = []
    cargados = []
    elo_cargados = []
    indices_a_borrar = []

    for p in partidos_jugados:
        clave = (p["equipo_local"], p["equipo_visitante"])
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
        else:
            # O ya estaba cargado de una corrida anterior, o el nombre
            # no matchea con fixture_lpf.csv por algún motivo raro.
            sin_matchear.append(p)

    if not cargados:
        if imprimir:
            print("  No hay partidos nuevos para cargar (todo ya estaba al día).")
        _guardar_log(ahora, cargados, sin_matchear, simulacion_corrida=False)
        # Aunque no haya partidos nuevos, re-simulamos con los datos
        # actuales de Supabase y devolvemos `datos`, para que el frontend
        # refresque en vez de quedarse con el snapshot estático viejo.
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
        repo.replace_matches("lpf", fixture_restante, resultados)
        filas = repo.standing_records("lpf")
        indice = {f["equipo"]: f for f in filas}
        for p in cargados:
            _aplicar_partido(
                indice, p["equipo_local"], p["equipo_visitante"],
                int(p["goles_local"]), int(p["goles_visitante"]),
            )
        repo.upsert_standings("lpf", _reordenar_posiciones(filas))
        elo_actualizados = repo.apply_club_rating_events(
            "lpf", elo_cargados, source="real_results", metadata={"origen": "actualizar_resultados_lpf.py"}
        )
        if imprimir:
            print(f"  ELO persistente actualizado con {elo_actualizados} partido(s).")

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
        repo.log_update("lpf", cargados, sin_matchear, simulacion_corrida, timestamp=timestamp)


if __name__ == "__main__":
    resultado = actualizar()
    if resultado["actualizado"]:
        print("\n✓ Actualización completa.")
    else:
        print("\n– Sin cambios.")
