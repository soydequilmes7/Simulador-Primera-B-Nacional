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
import csv
import json
import os
from datetime import datetime

try:
    import rutas
    _DATOS_DIR = rutas.datos_dir()
except ImportError:
    # Si no está rutas.py en el path, se usa la carpeta actual (o se
    # puede pisar con la variable de entorno LPF_DATOS_DIR más abajo).
    _DATOS_DIR = None

from scraper_promiedos_lpf import obtener_partidos_jugados_lpf
from calcular_tabla_lpf import actualizar_tabla_con_partidos

CAMPOS_FIXTURE = ["fecha", "jornada", "equipo_local", "equipo_visitante"]
CAMPOS_RESULTADOS = ["fecha", "jornada", "equipo_local", "equipo_visitante",
                      "goles_local", "goles_visitante"]

NOMBRE_FIXTURE = "fixture_lpf.csv"
NOMBRE_RESULTADOS = "resultados_lpf.csv"
NOMBRE_TABLA = "tabla_lpf.csv"
NOMBRE_LOG = "log_actualizaciones_lpf.json"


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

    fixture_csv = _ruta(NOMBRE_FIXTURE)
    resultados_csv = _ruta(NOMBRE_RESULTADOS)
    tabla_csv = _ruta(NOMBRE_TABLA)

    fixture = _leer_csv(fixture_csv, CAMPOS_FIXTURE)
    resultados = _leer_csv(resultados_csv, CAMPOS_RESULTADOS)

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
            # O ya estaba cargado de una corrida anterior, o el nombre
            # no matchea con fixture_lpf.csv por algún motivo raro.
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
