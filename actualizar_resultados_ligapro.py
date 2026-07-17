# -*- coding: utf-8 -*-
"""
actualizar_resultados_ligapro.py

Versión LigaPro de actualizar_resultados.py, calcada de
actualizar_resultados_brasileirao.py con estas diferencias:

  1. Usa scraper_ligapro.py (endpoint propio de ligapro.ec,
     dataPartidos.php) en vez de Promiedos.
  2. Los nombres que trae ligapro.ec vienen en formato "razón social"
     (p.ej. "Liga Deportiva Universitaria de Quito", "CSD Independiente
     del Valle") -- se normalizan contra los nombres locales de
     tabla_ligapro.csv/fixture_ligapro.csv con
     mapeo_equipos_ligapro.resolver_equipo() ANTES de intentar matchear
     contra el fixture pendiente. Brasileirão no necesita este paso
     porque scraper_promiedos_brasileirao.py ya devuelve nombres
     normalizados.
  3. Lee/escribe fixture_ligapro.csv, resultados_ligapro.csv y
     tabla_ligapro.csv, vía calcular_tabla_ligapro (_aplicar_partido /
     _reordenar_posiciones).
  4. Pasa correr_simulacion_fn=correr_simulacion_ligapro (de
     main_ligapro.py) para re-simular después de cargar resultados
     nuevos.

LIMITACIÓN CONOCIDA (ver también el docstring de calcular_tabla_ligapro.py):
este archivo aplica partidos nuevos dentro de la zona en la que ya estén
las filas de tabla_ligapro.csv en Supabase (normalmente "FaseInicial"
mientras dura esa fase). NO hace la transición de Fase Inicial a Fase
Final -- no reasigna la columna "zona" de cada equipo a su
hexagonal/cuadrangular correspondiente ni regenera fixture_ligapro.csv
con los cruces reales de la Fase Final. Esa transición hay que hacerla
aparte (a mano o con un script nuevo) una vez que la Fase Inicial real
termine sus 30 fechas. Mientras tanto, EstadisticasLigaPro.
simular_temporada_ligapro() sí resuelve esa transición automáticamente,
pero solo dentro de una corrida de simulación (no persiste el cambio de
zona en el CSV/Supabase).

Uso manual:
    python actualizar_resultados_ligapro.py

Uso programático:
    from actualizar_resultados_ligapro import actualizar
    from main_ligapro import correr_simulacion_ligapro
    resultado = actualizar(correr_simulacion_fn=correr_simulacion_ligapro)
"""
from datetime import datetime

from db.repository import transaction

from scraper_ligapro import obtener_partidos_jugados
from mapeo_equipos_ligapro import resolver_equipo
from calcular_tabla_ligapro import _aplicar_partido, _reordenar_posiciones

CAMPOS_FIXTURE = ["fecha", "jornada", "equipo_local", "equipo_visitante"]
CAMPOS_RESULTADOS = ["fecha", "jornada", "equipo_local", "equipo_visitante",
                      "goles_local", "goles_visitante"]


def _normalizar_partidos_scrapeados(partidos_jugados):
    """Traduce equipo_local/equipo_visitante (razón social de ligapro.ec)
    a los nombres locales de tabla_ligapro.csv/fixture_ligapro.csv. Los
    partidos donde no se pudo resolver alguno de los dos equipos se
    devuelven aparte, en vez de descartarlos silenciosamente, para que
    aparezcan en "sin_matchear" y se puedan diagnosticar (agregar el
    alias que falta a mapeo_equipos_ligapro.OVERRIDES)."""
    normalizados = []
    no_resueltos = []
    for p in partidos_jugados:
        local = resolver_equipo(p["equipo_local"])
        visitante = resolver_equipo(p["equipo_visitante"])
        if local is None or visitante is None:
            no_resueltos.append(p)
            continue
        normalizados.append({**p, "equipo_local": local, "equipo_visitante": visitante})
    return normalizados, no_resueltos


def actualizar(n_sims=1000, correr_simulacion_fn=None, imprimir=True):
    ahora = datetime.now().isoformat(timespec="seconds")

    with transaction() as repo:
        fixture = repo.match_records("ligapro", "pending")
        resultados = repo.match_records("ligapro", "played")

    if imprimir:
        print(f"[{ahora}] Scrapeando ligapro.ec (LigaPro Serie A)...")

    partidos_jugados_crudo = obtener_partidos_jugados()
    partidos_jugados, sin_normalizar = _normalizar_partidos_scrapeados(partidos_jugados_crudo)

    if imprimir:
        print(f"  {len(partidos_jugados_crudo)} partidos jugados vistos en ligapro.ec"
              f" ({len(sin_normalizar)} sin poder normalizar nombre de equipo)")
        if sin_normalizar:
            nombres_sin_resolver = set()
            for p in sin_normalizar:
                nombres_sin_resolver.add(p["equipo_local"])
                nombres_sin_resolver.add(p["equipo_visitante"])
            print("  Nombres crudos sin matchear (agregar el que falte a OVERRIDES en mapeo_equipos_ligapro.py):")
            for nombre in sorted(nombres_sin_resolver):
                print(f"    - {nombre!r} -> {resolver_equipo(nombre)}")

    indice_fixture = {}
    for i, fila in enumerate(fixture):
        clave = (fila["equipo_local"], fila["equipo_visitante"])
        indice_fixture[clave] = i
    resultados_ya_cargados = {
        (fila["equipo_local"], fila["equipo_visitante"])
        for fila in resultados
    }

    sin_matchear = list(sin_normalizar)
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
            # Igual que en Brasileirão: el fixture local es un
            # round-robin GENÉRICO (ver scripts/generar_fixture_ligapro.py),
            # no el calendario real de LigaPro -- su "jornada" no tiene
            # relación con cuándo se jugó el partido de verdad. Preferimos
            # siempre la fecha/jornada que vino de ligapro.ec y solo
            # caemos al fixture local si el scraper no la trajo.
            resultado_cargado = {
                "fecha": p.get("fecha") or fila_fixture.get("fecha", ""),
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
        repo.replace_matches("ligapro", fixture_restante, resultados)
        filas = repo.standing_records("ligapro")
        indice = {f["equipo"]: f for f in filas}
        for p in cargados:
            _aplicar_partido(
                indice, p["equipo_local"], p["equipo_visitante"],
                int(p["goles_local"]), int(p["goles_visitante"]),
            )
        repo.upsert_standings("ligapro", _reordenar_posiciones(filas))
        elo_actualizados = repo.apply_club_rating_events(
            "ligapro", elo_cargados, source="real_results",
            metadata={"origen": "actualizar_resultados_ligapro.py"}
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
        repo.log_update("ligapro", cargados, sin_matchear, simulacion_corrida, timestamp=timestamp)


if __name__ == "__main__":
    from main_ligapro import correr_simulacion_ligapro

    resultado = actualizar(correr_simulacion_fn=correr_simulacion_ligapro)
    if resultado["actualizado"]:
        print("\n✓ Actualización completa.")
    else:
        print("\n– Sin cambios.")
