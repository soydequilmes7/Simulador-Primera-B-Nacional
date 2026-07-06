# -*- coding: utf-8 -*-
"""
actualizar_resultados_federal.py

Versión Federal A de actualizar_resultados_bmetro.py, con estas
diferencias:

  1. Usa scraper_promiedos_federal.py (league id "fahi").
  2. calcular_tabla_federal.py SÍ reordena por zona (Federal A tiene 4
     zonas reales; B Metro usa una zona ficticia "Unica").
  3. Si se pasa correr_simulacion_fn, por default es
     main_federal.correr_simulacion_federal.

Uso manual:
    python actualizar_resultados_federal.py

Uso programático:
    from actualizar_resultados_federal import actualizar
    resultado = actualizar()  # sin re-simular
    resultado = actualizar(correr_simulacion_fn=correr_simulacion_federal)
"""
from __future__ import annotations

from datetime import datetime

from db.repository import transaction

from scraper_promiedos_federal import obtener_partidos_jugados_federal
from calcular_tabla_federal import _aplicar_partido, _reordenar_posiciones

CAMPOS_FIXTURE = ["fecha", "jornada", "equipo_local", "equipo_visitante"]
CAMPOS_RESULTADOS = ["fecha", "jornada", "equipo_local", "equipo_visitante",
                      "goles_local", "goles_visitante"]


def _normalizar_jornada(valor) -> str:
    if valor is None or valor == "":
        return ""
    try:
        return str(int(valor))
    except (TypeError, ValueError):
        return str(valor).strip()


def _clave_partido(fila: dict) -> tuple[str, str, str]:
    return (
        _normalizar_jornada(fila.get("jornada")),
        fila["equipo_local"],
        fila["equipo_visitante"],
    )


def _clasificar_partidos_jugados(
    partidos_jugados: list[dict],
    fixture: list[dict],
    resultados: list[dict],
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    indice_fixture = {}
    for i, fila in enumerate(fixture):
        indice_fixture[_clave_partido(fila)] = i

    resultados_ya_cargados = {_clave_partido(fila) for fila in resultados}
    resultados_actualizados = list(resultados)
    sin_matchear = []
    cargados = []
    indices_a_borrar = []

    for p in partidos_jugados:
        clave = _clave_partido(p)
        if clave in resultados_ya_cargados:
            continue
        if clave in indice_fixture:
            idx = indice_fixture[clave]
            fila_fixture = fixture[idx]
            resultados_actualizados.append({
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

    fixture_restante = [f for i, f in enumerate(fixture) if i not in indices_a_borrar]
    return fixture_restante, resultados_actualizados, cargados, sin_matchear


def actualizar(n_sims: int = 500, correr_simulacion_fn=None, imprimir: bool = True) -> dict:
    ahora = datetime.now().isoformat(timespec="seconds")

    with transaction() as repo:
        fixture = repo.match_records("federal_a", "pending")
        resultados = repo.match_records("federal_a", "played")

    if imprimir:
        print(f"[{ahora}] Scrapeando Promiedos (Federal A)...")

    partidos_jugados = obtener_partidos_jugados_federal()

    if imprimir:
        print(f"  {len(partidos_jugados)} partidos jugados vistos en Promiedos (con zona resuelta)")

    fixture_restante, resultados, cargados, sin_matchear = _clasificar_partidos_jugados(
        partidos_jugados, fixture, resultados,
    )

    if not cargados:
        if imprimir:
            print("  No hay partidos nuevos para cargar (todo ya estaba al día).")
        _guardar_log(ahora, cargados, sin_matchear, simulacion_corrida=False)
        # Aunque no haya partidos nuevos, re-simulamos con los datos
        # actuales de Supabase y devolvemos `datos`. El snapshot estático
        # (data_federal_a.json) que sirve la página puede estar más viejo
        # que lo que ya hay cargado en Supabase, así que el frontend usa
        # este `datos` para refrescar tabla/racha en vez de quedarse con el
        # snapshot viejo. Ver correrActualizacionFederal() en index.html.
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

    with transaction() as repo:
        repo.replace_matches("federal_a", fixture_restante, resultados)
        filas = repo.standing_records("federal_a")
        indice = {f["equipo"]: f for f in filas}
        for p in cargados:
            _aplicar_partido(
                indice, p["equipo_local"], p["equipo_visitante"],
                int(p["goles_local"]), int(p["goles_visitante"]),
            )
        repo.upsert_standings("federal_a", _reordenar_posiciones(filas))

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


def _guardar_log(timestamp: str, cargados: list[dict], sin_matchear: list[dict], simulacion_corrida: bool) -> None:
    with transaction() as repo:
        repo.log_update("federal_a", cargados, sin_matchear, simulacion_corrida, timestamp=timestamp)


if __name__ == "__main__":
    from main_federal import correr_simulacion_federal
    resultado = actualizar(correr_simulacion_fn=correr_simulacion_federal)
    if resultado["actualizado"]:
        print("\n✓ Actualización completa.")
    else:
        print("\n– Sin cambios.")
