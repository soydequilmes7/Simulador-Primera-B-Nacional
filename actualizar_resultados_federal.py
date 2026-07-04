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

import csv
import json
import os
from datetime import datetime

try:
    import rutas
    _DATOS_DIR = rutas.datos_dir()
except ImportError:
    _DATOS_DIR = None

from scraper_promiedos_federal import obtener_partidos_jugados_federal
from calcular_tabla_federal import actualizar_tabla_con_partidos

CAMPOS_FIXTURE = ["fecha", "jornada", "equipo_local", "equipo_visitante"]
CAMPOS_RESULTADOS = ["fecha", "jornada", "equipo_local", "equipo_visitante",
                      "goles_local", "goles_visitante"]

NOMBRE_FIXTURE = "fixture_federal_a.csv"
NOMBRE_RESULTADOS = "resultados_federal_a.csv"
NOMBRE_TABLA = "tabla_federal_a.csv"
NOMBRE_LOG = "log_actualizaciones_federal.json"


def _ruta(nombre_archivo: str) -> str:
    if _DATOS_DIR is not None:
        return str(_DATOS_DIR / nombre_archivo)
    return nombre_archivo


def _leer_csv(path: str, campos_esperados: list[str]) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _escribir_csv(path: str, filas: list[dict], campos: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(filas)


def actualizar(n_sims: int = 500, correr_simulacion_fn=None, imprimir: bool = True) -> dict:
    ahora = datetime.now().isoformat(timespec="seconds")

    fixture_csv = _ruta(NOMBRE_FIXTURE)
    resultados_csv = _ruta(NOMBRE_RESULTADOS)
    tabla_csv = _ruta(NOMBRE_TABLA)

    fixture = _leer_csv(fixture_csv, CAMPOS_FIXTURE)
    resultados = _leer_csv(resultados_csv, CAMPOS_RESULTADOS)

    if imprimir:
        print(f"[{ahora}] Scrapeando Promiedos (Federal A)...")

    partidos_jugados = obtener_partidos_jugados_federal()

    if imprimir:
        print(f"  {len(partidos_jugados)} partidos jugados vistos en Promiedos (con zona resuelta)")

    indice_fixture = {}
    for i, fila in enumerate(fixture):
        clave = (fila["equipo_local"], fila["equipo_visitante"])
        indice_fixture[clave] = i

    sin_matchear = []
    cargados = []
    indices_a_borrar = []

    for p in partidos_jugados:
        clave = (p["equipo_local"], p["equipo_visitante"])
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
        else:
            sin_matchear.append(p)

    if not cargados:
        if imprimir:
            print("  No hay partidos nuevos para cargar (todo ya estaba al día).")
        _guardar_log(ahora, cargados, sin_matchear, simulacion_corrida=False)
        return {
            "actualizado": False,
            "cargados": cargados,
            "sin_matchear": sin_matchear,
            "mensaje": "No había partidos nuevos jugados que coincidan con el fixture pendiente.",
        }

    fixture_restante = [f for i, f in enumerate(fixture) if i not in indices_a_borrar]

    _escribir_csv(fixture_csv, fixture_restante, CAMPOS_FIXTURE)
    _escribir_csv(resultados_csv, resultados, CAMPOS_RESULTADOS)
    actualizar_tabla_con_partidos(cargados, tabla_path=tabla_csv, imprimir=imprimir)

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


def _guardar_log(timestamp: str, cargados: list[dict], sin_matchear: list[dict], simulacion_corrida: bool) -> None:
    log_path = _ruta(NOMBRE_LOG)
    historial = []
    if os.path.exists(log_path):
        try:
            with open(log_path, encoding="utf-8") as f:
                historial = json.load(f)
        except (json.JSONDecodeError, OSError):
            historial = []

    historial.append({
        "timestamp": timestamp,
        "partidos_cargados": cargados,
        "sin_matchear": sin_matchear,
        "simulacion_corrida": simulacion_corrida,
    })

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    from main_federal import correr_simulacion_federal
    resultado = actualizar(correr_simulacion_fn=correr_simulacion_federal)
    if resultado["actualizado"]:
        print("\n✓ Actualización completa.")
    else:
        print("\n– Sin cambios.")
