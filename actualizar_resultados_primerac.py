# -*- coding: utf-8 -*-
"""
actualizar_resultados_primerac.py

Versión Primera C de actualizar_resultados.py, calcada de
actualizar_resultados_bmetro.py con estas diferencias:

  1. Usa scraper_promiedos_primerac.py (league id "ffjb").
  2. Lee/escribe fixture_primerac.csv, resultados_primerac.csv y
     tabla_primerac.csv.
  3. calcular_tabla_primerac.py SÍ tiene zonas (a diferencia de B
     Metro), igual que B Nacional.
  4. Antes de la primera corrida de este script hace falta que exista
     tabla_primerac.csv -- ver construir_tabla_inicial() en
     calcular_tabla_primerac.py para el bootstrap inicial.

Uso manual:
    python actualizar_resultados_primerac.py

Uso programático:
    from actualizar_resultados_primerac import actualizar
    resultado = actualizar()
    # o, con el motor de simulación ya armado:
    from main_primerac import correr_simulacion as correr_simulacion_primerac
    resultado = actualizar(correr_simulacion_fn=correr_simulacion_primerac)
"""
from datetime import datetime

from db.repository import bootstrap_league_from_csv, transaction

from scraper_promiedos_primerac import obtener_partidos_jugados_primerac
from calcular_tabla_primerac import aplicar_partidos

CAMPOS_FIXTURE = ["fecha", "jornada", "equipo_local", "equipo_visitante"]
CAMPOS_RESULTADOS = ["fecha", "jornada", "equipo_local", "equipo_visitante",
                      "goles_local", "goles_visitante"]

def actualizar(n_sims=1000, correr_simulacion_fn=None, imprimir=True):
    ahora = datetime.now().isoformat(timespec="seconds")
    bootstrap_league_from_csv("primerac")

    with transaction() as repo:
        fixture = repo.match_records("primerac", "pending")
        resultados = repo.match_records("primerac", "played")

    if imprimir:
        print(f"[{ahora}] Scrapeando Promiedos (Primera C)...")

    partidos_jugados = obtener_partidos_jugados_primerac()

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
        # Aunque no haya partidos nuevos, re-simulamos con los datos
        # actuales de Supabase y devolvemos `datos`, para que el frontend
        # refresque en vez de quedarse con el snapshot estático viejo.
        # guardar_json=False: no escribimos a disco (en Vercel es read-only).
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
        repo.replace_matches("primerac", fixture_restante, resultados)
        tabla_nueva = aplicar_partidos(repo.standing_records("primerac"), cargados)
        repo.upsert_standings("primerac", tabla_nueva)
        elo_actualizados = repo.apply_club_rating_events(
            "primerac", elo_cargados, source="real_results", metadata={"origen": "actualizar_resultados_primerac.py"}
        )
        if imprimir:
            print(f"  tabla_primerac.csv actualizada con {len(cargados)} partido(s) nuevo(s).")
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
        repo.log_update("primerac", cargados, sin_matchear, simulacion_corrida, timestamp=timestamp)


if __name__ == "__main__":
    resultado = actualizar()
    if resultado["actualizado"]:
        print("\n✓ Actualización completa.")
    else:
        print("\n– Sin cambios.")
