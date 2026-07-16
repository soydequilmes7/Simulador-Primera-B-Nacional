# -*- coding: utf-8 -*-
"""
actualizar_resultados_brasileirao.py

Versión Brasileirão de actualizar_resultados.py, calcada de
actualizar_resultados_bmetro.py con estas diferencias:

  1. Usa scraper_promiedos_brasileirao.py (league id "bbd").
  2. Lee/escribe fixture_brasileirao.csv, resultados_brasileirao.csv y
     tabla_brasileirao.csv.
  3. calcular_tabla_brasileirao.py no tiene zonas (tabla única, 20
     equipos, sin Reducido).
  4. Pasa correr_simulacion_fn=correr_simulacion_brasileirao (de
     main_brasileirao.py) para re-simular después de cargar resultados
     nuevos -- a diferencia de B Metro, acá el motor ya existe desde el
     arranque.

IMPORTANTE -- pendiente de integración con la base: este archivo asume
que "brasileirao" ya está registrado como competition_slug válido en
db/repository.py (dict COMPETITIONS) y que existe la fila
correspondiente en la tabla `seasons` de Supabase. Sin eso,
transaction()/repo.match_records("brasileirao", ...) van a fallar. Ese
registro y la migración SQL quedaron fuera de esta tanda a propósito
(ver conversación) -- se agregan en el siguiente paso.

Uso manual:
    python actualizar_resultados_brasileirao.py

Uso programático:
    from actualizar_resultados_brasileirao import actualizar
    from main_brasileirao import correr_simulacion_brasileirao
    resultado = actualizar(correr_simulacion_fn=correr_simulacion_brasileirao)
"""
from datetime import datetime

from db.repository import transaction

from scraper_promiedos_brasileirao import obtener_partidos_jugados_brasileirao
from calcular_tabla_brasileirao import _aplicar_partido, _reordenar_posiciones

CAMPOS_FIXTURE = ["fecha", "jornada", "equipo_local", "equipo_visitante"]
CAMPOS_RESULTADOS = ["fecha", "jornada", "equipo_local", "equipo_visitante",
                      "goles_local", "goles_visitante"]


def actualizar(n_sims=1000, correr_simulacion_fn=None, imprimir=True):
    ahora = datetime.now().isoformat(timespec="seconds")

    with transaction() as repo:
        fixture = repo.match_records("brasileirao", "pending")
        resultados = repo.match_records("brasileirao", "played")

    if imprimir:
        print(f"[{ahora}] Scrapeando Promiedos (Brasileirão)...")

    partidos_jugados = obtener_partidos_jugados_brasileirao()

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
            # OJO: el fixture local (fila_fixture) es un round-robin
            # GENÉRICO (ver scripts/generar_fixture_brasileirao.py), no
            # el calendario real de la CBF -- su "jornada" no tiene
            # ninguna relación con cuándo se jugó el partido de verdad.
            # Preferimos siempre la jornada/fecha que vino de Promiedos
            # (p["jornada"]/p["fecha_hora"]), y solo caemos al fixture
            # local si por algún motivo el scraper no la trajo (versión
            # vieja del scraper, etc.) para no romper.
            resultado_cargado = {
                "fecha": p.get("fecha_hora") or fila_fixture.get("fecha", ""),
                "jornada": p.get("jornada") if p.get("jornada") is not None else fila_fixture.get("jornada", ""),
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
        repo.replace_matches("brasileirao", fixture_restante, resultados)
        filas = repo.standing_records("brasileirao")
        indice = {f["equipo"]: f for f in filas}
        for p in cargados:
            _aplicar_partido(
                indice, p["equipo_local"], p["equipo_visitante"],
                int(p["goles_local"]), int(p["goles_visitante"]),
            )
        repo.upsert_standings("brasileirao", _reordenar_posiciones(filas))
        elo_actualizados = repo.apply_club_rating_events(
            "brasileirao", elo_cargados, source="real_results",
            metadata={"origen": "actualizar_resultados_brasileirao.py"}
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
        repo.log_update("brasileirao", cargados, sin_matchear, simulacion_corrida, timestamp=timestamp)


if __name__ == "__main__":
    from main_brasileirao import correr_simulacion_brasileirao

    resultado = actualizar(correr_simulacion_fn=correr_simulacion_brasileirao)
    if resultado["actualizado"]:
        print("\n✓ Actualización completa.")
    else:
        print("\n– Sin cambios.")
