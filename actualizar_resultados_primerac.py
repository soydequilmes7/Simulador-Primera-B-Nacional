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
import csv
import json
import os
from datetime import datetime

try:
    import rutas
    _DATOS_DIR = rutas.datos_dir()
except ImportError:
    _DATOS_DIR = None

from scraper_promiedos_primerac import obtener_partidos_jugados_primerac
from calcular_tabla_primerac import actualizar_tabla_con_partidos

CAMPOS_FIXTURE = ["fecha", "jornada", "equipo_local", "equipo_visitante"]
CAMPOS_RESULTADOS = ["fecha", "jornada", "equipo_local", "equipo_visitante",
                      "goles_local", "goles_visitante"]

NOMBRE_FIXTURE = "fixture_primerac.csv"
NOMBRE_RESULTADOS = "resultados_primerac.csv"
NOMBRE_TABLA = "tabla_primerac.csv"
NOMBRE_LOG = "log_actualizaciones_primerac.json"


def _ruta(nombre_archivo):
    if _DATOS_DIR is not None:
        return str(_DATOS_DIR / nombre_archivo)
    return nombre_archivo


def _leer_csv(path, campos_esperados):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _escribir_csv(path, filas, campos):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(filas)


def actualizar(n_sims=1000, correr_simulacion_fn=None, imprimir=True):
    ahora = datetime.now().isoformat(timespec="seconds")

    fixture_csv = _ruta(NOMBRE_FIXTURE)
    resultados_csv = _ruta(NOMBRE_RESULTADOS)
    tabla_csv = _ruta(NOMBRE_TABLA)

    if not os.path.exists(tabla_csv):
        raise FileNotFoundError(
            f"No existe {tabla_csv} todavía. Antes de correr este script hay que "
            "hacer el bootstrap inicial: correr scraper_promiedos_primerac.py una "
            "vez y después construir_tabla_inicial() de calcular_tabla_primerac.py."
        )

    fixture = _leer_csv(fixture_csv, CAMPOS_FIXTURE)
    resultados = _leer_csv(resultados_csv, CAMPOS_RESULTADOS)

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


def _guardar_log(timestamp, cargados, sin_matchear, simulacion_corrida):
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
    resultado = actualizar()
    if resultado["actualizado"]:
        print("\n✓ Actualización completa.")
    else:
        print("\n– Sin cambios.")
