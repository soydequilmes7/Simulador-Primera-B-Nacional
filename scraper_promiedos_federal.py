# -*- coding: utf-8 -*-
"""
scraper_promiedos_federal.py

Scraper de Promiedos para el Torneo Federal A. Calcado de
scraper_promiedos_bmetro.py (mismo endpoint, mismo header X-Ver
obligatorio), con una diferencia importante: el Federal A tiene 4 zonas
en paralelo, y no confiamos en que Promiedos etiquete cada partido con
el mismo nombre de zona que usa el Reglamento ("Zona 1".."Zona 4"). En
vez de parsear ese campo (que puede no existir o venir distinto),
determinamos la zona de cada partido CRUZANDO los nombres de los dos
equipos contra datos/tabla_federal_a.csv (que ya tiene la zona real de
cada uno, sembrada del Reglamento) -- si ambos equipos de un partido
están en la misma zona conocida, ese partido es de esa zona.

Cómo funciona (igual que B Metro):
  1) Pide /league/tables_and_fixtures/{LEAGUE_ID} para sacar la lista de
     fechas disponibles.
  2) Para cada fecha, pide /league/games/{LEAGUE_ID}/{key} y junta los
     partidos de las 4 zonas juntos (se espera que vengan mezclados).
  3) Un partido se considera "jugado" cuando status.enum == 3.

LEAGUE_ID confirmado por búsqueda (promiedos.com.ar/league/federal-a/fahi)
pero sin verificar en vivo la forma exacta del JSON para esta liga en
particular -- si algo no matchea, correr con verbose=True y revisar el
diagnóstico que imprime obtener_partidos_federal() antes de tocar nada.

Uso:
    python scraper_promiedos_federal.py

Escribe (o pisa) fixture_federal_a.csv y resultados_federal_a.csv en
datos/ (relativo a este archivo), con las mismas columnas que el resto
del proyecto.

También se puede importar y usar programáticamente:

    from scraper_promiedos_federal import obtener_partidos_jugados_federal
    partidos = obtener_partidos_jugados_federal()
"""
from __future__ import annotations

import csv
import json
import os
import time
import urllib.error
import urllib.request

DATOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos")
os.makedirs(DATOS_DIR, exist_ok=True)

BASE_URL = "https://api.promiedos.com.ar"
LEAGUE_ID = "fahi"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "es-ES,es;q=0.9,it;q=0.8",
    "Referer": "https://www.promiedos.com.ar/",
    "Origin": "https://www.promiedos.com.ar",
    "X-Ver": "1.11.7.5",  # sin esto la API devuelve respuestas vacías (200 OK igual)
}
TIMEOUT = 20
PAUSA_ENTRE_PEDIDOS = 0.15  # segundos, para no bombardear la API

FIXTURE_CSV = os.path.join(DATOS_DIR, "fixture_federal_a.csv")
RESULTADOS_CSV = os.path.join(DATOS_DIR, "resultados_federal_a.csv")
TABLA_CSV = os.path.join(DATOS_DIR, "tabla_federal_a.csv")

ESTADOS_JUGADO_ENUM = {3}

# Nombres tal cual figuran en el Reglamento pero que Promiedos podría
# escribir distinto -- si el matcheo por plantel falla mucho, revisar
# acá primero (ver _construir_alias() más abajo, que también intenta
# variantes automáticas antes de rendirse).
ALIAS_EQUIPO = {
    "Independiente (Chivilcoy)": "Independiente Chivilcoy",
    "San Martín (Formosa)": "San Martín de Formosa",
    "Gimnasia y Esgrima (CU)": "Gimnasia y Esgrima de Concepción del Uruguay",
    "Defensores de Belgrano (VR)": "Defensores de Belgrano de V. Ramallo",
}


def _get_json(path: str) -> dict:
    req = urllib.request.Request(f"{BASE_URL}{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _cargar_zona_por_equipo() -> dict[str, str]:
    """{equipo: zona} desde tabla_federal_a.csv (fuente de verdad de a
    qué zona pertenece cada club, sembrada del Reglamento)."""
    with open(TABLA_CSV, newline="", encoding="utf-8") as f:
        return {fila["equipo"]: fila["zona"] for fila in csv.DictReader(f)}


def _construir_alias(zona_por_equipo: dict[str, str]) -> dict[str, str]:
    """ALIAS_EQUIPO + variantes automáticas simples (sin tildes, sin
    espacios extra) para tolerar pequeñas diferencias de escritura entre
    Promiedos y el Reglamento sin tener que listarlas todas a mano."""
    alias = dict(ALIAS_EQUIPO)
    for nombre in zona_por_equipo:
        sin_tildes = (nombre.replace("í", "i").replace("é", "e").replace("á", "a")
                      .replace("ó", "o").replace("ú", "u"))
        alias.setdefault(sin_tildes, nombre)
    return alias


def _resolver_equipo(nombre_promiedos: str, zona_por_equipo: dict[str, str], alias: dict[str, str]) -> str:
    """Nombre tal cual lo devuelve Promiedos -> nombre canónico del
    Reglamento, si se puede resolver (si no, devuelve el original tal
    cual, para no perder el partido -- quedará sin zona detectada y se
    reporta al final)."""
    if nombre_promiedos in zona_por_equipo:
        return nombre_promiedos
    return alias.get(nombre_promiedos, nombre_promiedos)


def obtener_fechas_disponibles() -> list[dict]:
    """Lista de dicts {"name": "Fecha N", "key": "..."}, sin el filtro
    especial "latest"."""
    data = _get_json(f"/league/tables_and_fixtures/{LEAGUE_ID}")
    filtros = data["games"]["filters"]
    return [f for f in filtros if f["key"] != "latest"]


def _parsear_partido(g: dict) -> dict | None:
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


def obtener_partidos_federal(verbose: bool = True) -> list[dict]:
    """Recorre todas las fechas disponibles y devuelve los partidos
    (jugados y pendientes) de las 4 zonas juntas, con la zona ya resuelta
    por matcheo de plantel contra tabla_federal_a.csv."""
    zona_por_equipo = _cargar_zona_por_equipo()
    alias = _construir_alias(zona_por_equipo)

    fechas = obtener_fechas_disponibles()
    partidos = []
    sin_zona_detectada = []

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
            if not p:
                continue

            local = _resolver_equipo(p["equipo_local"], zona_por_equipo, alias)
            visitante = _resolver_equipo(p["equipo_visitante"], zona_por_equipo, alias)
            zona_local = zona_por_equipo.get(local)
            zona_visitante = zona_por_equipo.get(visitante)

            if zona_local is None or zona_visitante is None or zona_local != zona_visitante:
                sin_zona_detectada.append((p["equipo_local"], p["equipo_visitante"]))
                continue

            p["equipo_local"], p["equipo_visitante"] = local, visitante
            p["zona"] = zona_local
            partidos.append(p)

        time.sleep(PAUSA_ENTRE_PEDIDOS)

    if sin_zona_detectada and verbose:
        print(f"\n  AVISO: {len(sin_zona_detectada)} partido(s) sin zona detectada "
              "(nombre de equipo no matcheó tabla_federal_a.csv) -- se descartaron:")
        for local, visitante in sin_zona_detectada[:10]:
            print(f"    {local} vs {visitante}")
        print("  Revisar ALIAS_EQUIPO en este archivo si se repite siempre con los mismos nombres.")

    partidos.sort(key=lambda p: (p["zona"], p["jornada"], p["fecha_hora"]))
    return partidos


def escribir_csvs(partidos: list[dict], fixture_path: str = FIXTURE_CSV,
                   resultados_path: str = RESULTADOS_CSV) -> tuple[int, int]:
    jugados = [p for p in partidos if p["jugado"]]
    pendientes = [p for p in partidos if not p["jugado"]]

    with open(fixture_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["fecha", "jornada", "equipo_local", "equipo_visitante"])
        for p in pendientes:
            writer.writerow(["", p["jornada"], p["equipo_local"], p["equipo_visitante"]])

    with open(resultados_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["fecha", "jornada", "equipo_local", "equipo_visitante", "goles_local", "goles_visitante"])
        for p in jugados:
            writer.writerow(["", p["jornada"], p["equipo_local"], p["equipo_visitante"],
                              p["goles_local"], p["goles_visitante"]])

    return len(jugados), len(pendientes)


def obtener_partidos_jugados_federal() -> list[dict]:
    """Igual que obtener_partidos_federal(), pero solo los jugados, en el
    formato que espera actualizar_resultados_federal.py."""
    jugados = [p for p in obtener_partidos_federal(verbose=False) if p["jugado"]]
    return [
        {
            "equipo_local": p["equipo_local"],
            "equipo_visitante": p["equipo_visitante"],
            "goles_local": p["goles_local"],
            "goles_visitante": p["goles_visitante"],
            "zona": p["zona"],
        }
        for p in jugados
    ]


def main() -> None:
    print(f"Pidiendo la lista de fechas de /league/tables_and_fixtures/{LEAGUE_ID} ...")
    try:
        partidos = obtener_partidos_federal()
    except urllib.error.URLError as e:
        print(f"ERROR al conectar con Promiedos: {e}")
        return
    except (KeyError, IndexError) as e:
        print(f"La forma del JSON cambió respecto a lo esperado: falta {e}")
        return

    if not partidos:
        print("No se encontró ningún partido con zona resuelta "
              "(¿cambió el formato de la respuesta, o los nombres no matchean?).")
        return

    n_jugados, n_pendientes = escribir_csvs(partidos)
    jornadas = sorted(set(p["jornada"] for p in partidos))
    zonas = sorted(set(p["zona"] for p in partidos))

    print(f"\nListo. {len(partidos)} partidos encontrados (zonas {zonas}, jornadas {jornadas[0]} a {jornadas[-1]}).")
    print(f"  - Jugados    -> {n_jugados} escritos en {RESULTADOS_CSV}")
    print(f"  - Pendientes -> {n_pendientes} escritos en {FIXTURE_CSV}")


if __name__ == "__main__":
    main()
