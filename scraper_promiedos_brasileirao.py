# -*- coding: utf-8 -*-
"""
scraper_promiedos_brasileirao.py

Scraper de Promiedos para el Brasileirao Serie A. Trae el fixture
COMPLETO de la temporada (las 38 fechas de todos contra todos, ida y
vuelta), no solo la fecha actual.

Calcado de scraper_promiedos_bmetro.py, mismo mecanismo:

  1) Pide /league/tables_and_fixtures/{LEAGUE_ID} para sacar la lista de
     fechas disponibles (data["games"]["filters"]: "Fecha 1".."Fecha 38",
     cada una con su "key" interna).
  2) Para cada fecha, pide /league/games/{LEAGUE_ID}/{key} y junta los
     partidos. Fechas que todavía no tienen fixture publicado devuelven
     "games": [] y simplemente se saltean.
  3) Un partido se considera "jugado" cuando status.enum == 3.

IMPORTANTE: hace falta mandar el header X-Ver (el que usa la propia web
de Promiedos); sin él la API devuelve respuestas vacías aunque el
status HTTP sea 200 OK.

LEAGUE_ID = "bbd" (confirmado desde la URL pública:
https://www.promiedos.com.ar/league/brasileirao-serie-a/bbd)

Uso:
    python scraper_promiedos_brasileirao.py

Escribe (o pisa) fixture_brasileirao.csv y resultados_brasileirao.csv en
datos/ (relativo a este archivo, no a la carpeta donde se corra), con
las mismas columnas que el resto del proyecto:

    fixture_brasileirao.csv:    fecha,jornada,equipo_local,equipo_visitante
    resultados_brasileirao.csv: fecha,jornada,equipo_local,equipo_visitante,goles_local,goles_visitante

También se puede importar y usar programáticamente:

    from scraper_promiedos_brasileirao import obtener_partidos_jugados_brasileirao
    partidos = obtener_partidos_jugados_brasileirao()
"""
import csv
import json
import os
import ssl
import time
import urllib.error
import urllib.request

import rutas

# Carpeta donde el resto del proyecto guarda los datos (tabla, fixture,
# resultados, data_brasileirao.json). Se calcula relativa a este archivo
# para que funcione sin importar desde dónde se lo ejecute.
DATOS_DIR = str(rutas.datos_dir())

BASE_URL = "https://api.promiedos.com.ar"
LEAGUE_ID = "bbd"  # Brasileirao Serie A
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "es-ES,es;q=0.9,it;q=0.8",
    "Referer": "https://www.promiedos.com.ar/",
    "Origin": "https://www.promiedos.com.ar",
    "X-Ver": "1.11.7.5",
}
TIMEOUT = 20
PAUSA_ENTRE_PEDIDOS = 0.15  # segundos, para no bombardear la API

FIXTURE_CSV = os.path.join(DATOS_DIR, "fixture_brasileirao.csv")
RESULTADOS_CSV = os.path.join(DATOS_DIR, "resultados_brasileirao.csv")

ESTADOS_JUGADO_ENUM = {3}


def _get_json(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
    except urllib.error.URLError as e:
        if not isinstance(e.reason, ssl.SSLCertVerificationError):
            raise
        context = _ssl_context_fallback()
        resp = urllib.request.urlopen(req, timeout=TIMEOUT, context=context)

    with resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def _ssl_context_fallback():
    try:
        import certifi
    except ImportError:
        return ssl._create_unverified_context()
    return ssl.create_default_context(cafile=certifi.where())


def obtener_fechas_disponibles():
    """Lista de dicts {"name": "Fecha N", "key": "..."}, sin el filtro
    especial "latest"."""
    data = _get_json(f"/league/tables_and_fixtures/{LEAGUE_ID}")
    filtros = data["games"]["filters"]
    return [f for f in filtros if f["key"] != "latest"]


def _parsear_partido(g):
    stage = g.get("stage_round_name")
    if not stage or not stage.lower().startswith("fecha"):
        return None
    try:
        jornada = int(stage.split()[-1])
    except (ValueError, IndexError):
        return None

    equipo_local = g["teams"][0]["name"]
    equipo_visitante = g["teams"][1]["name"]
    estado = g.get("status", {})
    jugado = estado.get("enum") in ESTADOS_JUGADO_ENUM

    goles_local = goles_visitante = None
    if jugado and "scores" in g:
        goles_local = int(g["scores"][0])
        goles_visitante = int(g["scores"][1])

    return {
        "jornada": jornada,
        "equipo_local": equipo_local,
        "equipo_visitante": equipo_visitante,
        "jugado": jugado,
        "goles_local": goles_local,
        "goles_visitante": goles_visitante,
        "estado": estado.get("name", ""),
        "fecha_hora": g.get("start_time", ""),
    }


def obtener_partidos_brasileirao(verbose=True):
    """Recorre las 38 fechas de la temporada regular y devuelve todos los
    partidos (jugados y pendientes) en una sola lista."""
    fechas = obtener_fechas_disponibles()
    partidos = []
    for f in fechas:
        try:
            resp = _get_json(f"/league/games/{LEAGUE_ID}/{f['key']}")
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            if verbose:
                print(f"  {f['name']}: ERROR ({e}), se saltea")
            continue

        juegos = resp.get("games", [])
        if verbose:
            print(f"  {f['name']}: {len(juegos)} partido(s)")
        for g in juegos:
            p = _parsear_partido(g)
            if p:
                partidos.append(p)
        time.sleep(PAUSA_ENTRE_PEDIDOS)

    partidos.sort(key=lambda p: (p["jornada"], p["fecha_hora"]))
    return partidos


def escribir_csvs(partidos, fixture_path=FIXTURE_CSV, resultados_path=RESULTADOS_CSV):
    jugados = [p for p in partidos if p["jugado"]]
    pendientes = [p for p in partidos if not p["jugado"]]
    os.makedirs(os.path.dirname(fixture_path), exist_ok=True)
    os.makedirs(os.path.dirname(resultados_path), exist_ok=True)

    with open(fixture_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["fecha", "jornada", "equipo_local", "equipo_visitante"])
        for p in pendientes:
            writer.writerow(["", p["jornada"], p["equipo_local"], p["equipo_visitante"]])

    with open(resultados_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["fecha", "jornada", "equipo_local", "equipo_visitante", "goles_local", "goles_visitante"])
        for p in jugados:
            writer.writerow(["", p["jornada"], p["equipo_local"], p["equipo_visitante"], p["goles_local"], p["goles_visitante"]])

    return len(jugados), len(pendientes)


def obtener_partidos_jugados_brasileirao():
    """Igual que obtener_partidos_brasileirao(), pero solo los jugados, en
    el formato que espera actualizar_resultados_brasileirao.py. Esta API
    de Promiedos no expone goleadores acá (vienen en un campo aparte
    dentro de cada gol de "teams"), así que esas claves quedan vacías
    por ahora."""
    jugados = [p for p in obtener_partidos_brasileirao(verbose=False) if p["jugado"]]
    return [
        {
            "equipo_local": p["equipo_local"],
            "equipo_visitante": p["equipo_visitante"],
            "goles_local": p["goles_local"],
            "goles_visitante": p["goles_visitante"],
            "goleadores_local": {},
            "goleadores_visitante": {},
        }
        for p in jugados
    ]


def main():
    print(f"Pidiendo la lista de fechas de /league/tables_and_fixtures/{LEAGUE_ID} ...")
    try:
        partidos = obtener_partidos_brasileirao()
    except urllib.error.URLError as e:
        print(f"ERROR al conectar con Promiedos: {e}")
        return
    except (KeyError, IndexError) as e:
        print(f"La forma del JSON cambió respecto a lo esperado: falta {e}")
        return

    if not partidos:
        print("No se encontró ningún partido de fase regular (¿cambió el formato de la respuesta?).")
        return

    n_jugados, n_pendientes = escribir_csvs(partidos)
    jornadas = sorted(set(p["jornada"] for p in partidos))

    print(f"\nListo. {len(partidos)} partidos de liga encontrados (jornadas {jornadas[0]} a {jornadas[-1]}).")
    print(f"  - Jugados    -> {n_jugados} escritos en {RESULTADOS_CSV}")
    print(f"  - Pendientes -> {n_pendientes} escritos en {FIXTURE_CSV}")


if __name__ == "__main__":
    main()
