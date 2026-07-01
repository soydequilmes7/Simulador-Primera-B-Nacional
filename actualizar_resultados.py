# -*- coding: utf-8 -*-
"""
actualizar_resultados.py

Orquesta la actualización automática:
  1. Trae los resultados actuales desde la API de Promiedos (scraper_promiedos.py)
  2. Traduce los nombres de equipo al formato local (mapeo_equipos.py)
  3. Busca esos partidos dentro de fixture.csv (los pendientes)
  4. Si los encuentra, los mueve a resultados.csv con sus goles
     y los borra de fixture.csv
  5. Suma los goles de esos partidos a datos/goleadores.csv (acumulado
     histórico de goles por jugador). NOTA: goleadores.csv tiene que
     existir de antes — correr backfill_goleadores.py una sola vez
     antes de la primera actualización, si todavía no lo hiciste.
  6. Si hubo al menos un partido nuevo, corre la simulación
     (correr_simulacion, de main.py) para regenerar data.json
  7. Guarda un log en log_actualizaciones.json con fecha/hora
     y el detalle de qué se cargó

Uso manual:
    python actualizar_resultados.py

Se puede llamar también programáticamente:
    from actualizar_resultados import actualizar
    resultado = actualizar()
"""
import csv
import json
import os
from datetime import datetime
from pathlib import Path

from mapeo_equipos import resolver_equipo
from scraper_promiedos import obtener_partidos_jugados
from calcular_tabla import actualizar_tabla_con_partidos

# Misma carpeta de datos que usa actualizar_datos.py (datos/ al lado de
# este archivo), en vez de rutas relativas al directorio desde donde se
# ejecute el script.
DATOS_DIR = Path(__file__).resolve().parent / "datos"

FIXTURE_CSV = str(DATOS_DIR / "fixture.csv")
RESULTADOS_CSV = str(DATOS_DIR / "resultados.csv")
GOLEADORES_CSV = str(DATOS_DIR / "goleadores.csv")
LOG_PATH = str(Path(__file__).resolve().parent / "log_actualizaciones.json")

CAMPOS_FIXTURE = ["fecha", "jornada", "equipo_local", "equipo_visitante"]
CAMPOS_RESULTADOS = ["fecha", "jornada", "equipo_local", "equipo_visitante",
                      "goles_local", "goles_visitante"]
CAMPOS_GOLEADORES = ["jugador", "equipo", "goles"]


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


def _traducir_partidos(partidos_promiedos):
    """
    Devuelve (partidos_traducidos, sin_matchear).
    partidos_traducidos ya tiene los nombres en formato local.
    """
    traducidos = []
    sin_matchear = []
    for p in partidos_promiedos:
        local = resolver_equipo(p["equipo_local"])
        visitante = resolver_equipo(p["equipo_visitante"])
        if local and visitante:
            traducidos.append({
                "equipo_local": local,
                "equipo_visitante": visitante,
                "goles_local": p["goles_local"],
                "goles_visitante": p["goles_visitante"],
                # Nombres de jugador tal cual, no necesitan traducción de
                # equipo (ya van con el nombre local en la clave de arriba).
                "goleadores_local": p.get("goleadores_local", {}),
                "goleadores_visitante": p.get("goleadores_visitante", {}),
            })
        else:
            sin_matchear.append(p)
    return traducidos, sin_matchear


def _actualizar_goleadores(cargados, imprimir=True):
    """
    Suma los goles de los partidos recién cargados a datos/goleadores.csv
    (acumulado histórico por jugador+equipo). Solo se llama con los
    partidos que efectivamente se cargaron (evita duplicar si se corre
    varias veces sin partidos nuevos).
    """
    goleadores = _leer_csv(GOLEADORES_CSV, CAMPOS_GOLEADORES)
    indice = {(g["jugador"], g["equipo"]): i for i, g in enumerate(goleadores)}

    def _sumar(jugador, equipo, goles):
        clave = (jugador, equipo)
        if clave in indice:
            fila = goleadores[indice[clave]]
            fila["goles"] = int(fila["goles"]) + goles
        else:
            goleadores.append({"jugador": jugador, "equipo": equipo, "goles": goles})
            indice[clave] = len(goleadores) - 1

    goles_sumados = 0
    for p in cargados:
        for jugador, goles in p.get("goleadores_local", {}).items():
            _sumar(jugador, p["equipo_local"], goles)
            goles_sumados += goles
        for jugador, goles in p.get("goleadores_visitante", {}).items():
            _sumar(jugador, p["equipo_visitante"], goles)
            goles_sumados += goles

    _escribir_csv(GOLEADORES_CSV, goleadores, CAMPOS_GOLEADORES)
    if imprimir:
        print(f"  {goles_sumados} goles de jugador sumados a goleadores.csv.")


def actualizar(n_sims=1000, imprimir=True):
    """
    Corre todo el proceso. Devuelve un dict con el resultado, pensado
    para poder loguearse o devolverse como JSON desde el servidor web.
    """
    ahora = datetime.now().isoformat(timespec="seconds")

    fixture = _leer_csv(FIXTURE_CSV, CAMPOS_FIXTURE)
    resultados = _leer_csv(RESULTADOS_CSV, CAMPOS_RESULTADOS)

    if imprimir:
        print(f"[{ahora}] Scrapeando Promiedos...")

    partidos_promiedos = obtener_partidos_jugados()
    traducidos, sin_matchear = _traducir_partidos(partidos_promiedos)

    if imprimir:
        print(f"  {len(partidos_promiedos)} partidos jugados vistos en Promiedos")
        print(f"  {len(traducidos)} matchearon con nombres locales")
        if sin_matchear:
            print(f"  {len(sin_matchear)} NO matchearon (revisar mapeo_equipos.py):")
            for p in sin_matchear:
                print(f"    - {p['equipo_local']} vs {p['equipo_visitante']}")

    # Indexamos el fixture pendiente por (equipo_local, equipo_visitante)
    # jornada no se usa como clave porque puede haber partidos reprogramados
    # que en tu fixture.csv siguen etiquetados con la jornada original.
    indice_fixture = {}
    for i, fila in enumerate(fixture):
        clave = (fila["equipo_local"], fila["equipo_visitante"])
        indice_fixture[clave] = i

    cargados = []
    indices_a_borrar = []

    for p in traducidos:
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

    # Sacamos del fixture los que ya se jugaron
    fixture_restante = [f for i, f in enumerate(fixture) if i not in indices_a_borrar]

    _escribir_csv(FIXTURE_CSV, fixture_restante, CAMPOS_FIXTURE)
    _escribir_csv(RESULTADOS_CSV, resultados, CAMPOS_RESULTADOS)
    _actualizar_goleadores(cargados, imprimir=imprimir)
    actualizar_tabla_con_partidos(cargados, imprimir=imprimir)

    if imprimir:
        print(f"  Cargados {len(cargados)} partidos nuevos. Re-simulando...")

    # Importa aquí para evitar import circular si este módulo se usa antes
    # de que main.py esté disponible en el path
    from main import correr_simulacion
    datos = correr_simulacion(n_sims=n_sims, imprimir=imprimir)

    _guardar_log(ahora, cargados, sin_matchear, simulacion_corrida=True)

    return {
        "actualizado": True,
        "cargados": cargados,
        "sin_matchear": sin_matchear,
        "datos": datos,
    }


def _guardar_log(timestamp, cargados, sin_matchear, simulacion_corrida):
    historial = []
    if os.path.exists(LOG_PATH):
        try:
            with open(LOG_PATH, encoding="utf-8") as f:
                historial = json.load(f)
        except (json.JSONDecodeError, OSError):
            historial = []

    historial.append({
        "timestamp": timestamp,
        "partidos_cargados": cargados,
        "sin_matchear": sin_matchear,
        "simulacion_corrida": simulacion_corrida,
    })

    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    resultado = actualizar()
    if resultado["actualizado"]:
        print("\n✓ Actualización completa.")
    else:
        print("\n– Sin cambios.")
