# -*- coding: utf-8 -*-
"""
scraper_promiedos_federal.py

Trae los PARTIDOS JUGADOS del Torneo Federal A desde la API pública de
Promiedos (api.promiedos.com.ar). Calcado de scraper_promiedos.py (la
Primera Nacional), con las diferencias que ya documentó
scraper_tabla_promiedos_federal.py para esta misma liga:

  - LEAGUE_ID = "fahi" (Federal A).
  - Hace falta el header X-Ver -- sin él, la API devuelve "{}" vacío con
    status 200 (no tira error, así que si no se manda este header parece
    que "no hay partidos" en vez de fallar de forma obvia).
  - A diferencia de la Nacional (LEAGUE_ID "ebj"), donde
    /league/tables_and_fixtures/{id} está bloqueado y hay que generar
    las keys de fecha a mano probando un rango numérico,
    scraper_tabla_promiedos_federal.py ya confirmó que ese endpoint SÍ
    responde para "fahi" (lo usa para bajar las 4 tablas de posiciones).
    Por eso acá el camino "prolijo" (leer games.filters de
    tables_and_fixtures) es el que más chances tiene de andar directo;
    el fallback por rango numérico queda como red de seguridad, con un
    prefijo de key placeholder -- si hace falta usarlo de verdad, correr
    con --debug, mirar debug_promiedos_federal_dump.json y completar
    PREFIJO_FECHA_FALLBACK con la key real de una fecha conocida (mismo
    procedimiento que ya usa scraper_promiedos.py para la Nacional).

Uso:
    from scraper_promiedos_federal import obtener_partidos_jugados_federal
    partidos = obtener_partidos_jugados_federal()
    # [{"jornada": 17, "equipo_local": "Olimpo", "equipo_visitante": "Villa Mitre",
    #   "goles_local": 1, "goles_visitante": 0, "zona": "4",
    #   "goleadores_local": {...}, "goleadores_visitante": {...}}, ...]

Los nombres de equipo pasan por mapeo_equipos_federal.resolver_equipo()
antes de salir de este módulo: si Promiedos los da abreviados (p. ej.
"Sp. Belgrano", "Sarmiento (R)"), se traducen al nombre oficial que usan
tabla_federal_a.csv / fixture_federal_a.csv ("Sportivo Belgrano",
"Sarmiento de Resistencia"). Si un nombre no matchea ni por alias ni por
fuzzy matching, se deja TAL COMO lo dio Promiedos (no se descarta el
partido) -- así actualizar_resultados_federal.py lo va a mostrar en
"sin_matchear" y queda visible para agregar el alias que falte, en vez
de perderse en silencio.

OJO: los alias de mapeo_equipos_federal.py son en su mayoría estimaciones
sin confirmar contra un dump real (ver el docstring de ese archivo). La
primera corrida con --debug es la que valida (o corrige) esto de verdad.

Modo debug (baja todo y lo guarda para inspección manual):
    python scraper_promiedos_federal.py --debug
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

from mapeo_equipos_federal import resolver_equipo

LEAGUE_ID = "fahi"  # Federal A
BASE_URL = "https://api.promiedos.com.ar"

# Mismo set de headers que ya probó scraper_tabla_promiedos_federal.py
# para esta liga -- en particular X-Ver, sin el cual la API devuelve
# "{}" vacío con 200 OK en vez de un error explícito.
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

# Placeholder -- NO confirmado en vivo para el Federal A (a diferencia de
# PREFIJO_FECHA en scraper_promiedos.py, que sí está confirmado para la
# Nacional). Solo se usa si el camino prolijo (tables_and_fixtures) no
# devuelve games.filters. Completar con la key real de una fecha
# conocida después de correr --debug.
PREFIJO_FECHA_FALLBACK = None
MAX_FECHAS = 40
FALLOS_SEGUIDOS_PARA_FRENAR = 3
PAUSA_ENTRE_PEDIDOS = 0.3

DATOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos")
TABLA_CSV = os.path.join(DATOS_DIR, "tabla_federal_a.csv")


def _get_json(path: str) -> dict:
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _cargar_zona_por_equipo() -> dict[str, str]:
    """{equipo: zona} a partir de tabla_federal_a.csv, para poder marcar
    de qué zona es cada partido jugado (informativo -- actualizar() de
    actualizar_resultados_federal.py matchea por nombre de equipo nada
    más, no necesita la zona para funcionar)."""
    if not os.path.exists(TABLA_CSV):
        return {}
    with open(TABLA_CSV, newline="", encoding="utf-8") as f:
        return {fila["equipo"]: fila["zona"] for fila in csv.DictReader(f)}


def _fechas_desde_tables_and_fixtures() -> list[dict]:
    """Camino prolijo: lee games.filters de tables_and_fixtures. A
    diferencia de la Nacional, para "fahi" este endpoint no está
    bloqueado (scraper_tabla_promiedos_federal.py ya lo usa para las
    tablas), así que tiene buenas chances de traer la lista de fechas
    directo. Devuelve [] si viene vacío, para que el llamador caiga al
    fallback sin drama."""
    try:
        data = _get_json(f"/league/tables_and_fixtures/{LEAGUE_ID}")
    except Exception as e:
        print(f"  [aviso] tables_and_fixtures falló ({e}); pruebo el fallback.")
        return []

    filtros = (data or {}).get("games", {}).get("filters", [])
    fechas = [
        {"nombre": f["name"], "key": f["key"]}
        for f in filtros
        if f.get("key") != "latest"
    ]
    return fechas


def _fechas_por_rango(prefijo: str, max_fechas: int = MAX_FECHAS) -> list[dict]:
    """Fallback: genera las keys "{prefijo}{n}" y las prueba una por una
    contra /league/games/{LEAGUE_ID}/{key}. Mismo mecanismo que usa
    scraper_promiedos.py para la Nacional -- pero acá `prefijo` todavía
    no está confirmado en vivo (ver PREFIJO_FECHA_FALLBACK)."""
    fechas = []
    fallos_seguidos = 0
    for n in range(1, max_fechas + 1):
        key = f"{prefijo}{n}"
        try:
            data = _get_json(f"/league/games/{LEAGUE_ID}/{key}")
        except urllib.error.HTTPError as e:
            print(f"  [aviso] fecha {n} ({key}): HTTP {e.code}")
            fallos_seguidos += 1
        except Exception as e:
            print(f"  [aviso] fecha {n} ({key}): {e}")
            fallos_seguidos += 1
        else:
            if not (data or {}).get("games"):
                fallos_seguidos += 1
            else:
                fallos_seguidos = 0
                fechas.append({"nombre": f"Fecha {n}", "key": key})

        if fallos_seguidos >= FALLOS_SEGUIDOS_PARA_FRENAR:
            break
        time.sleep(PAUSA_ENTRE_PEDIDOS)

    return fechas


def obtener_fechas_disponibles() -> list[dict]:
    fechas = _fechas_desde_tables_and_fixtures()
    if fechas:
        return fechas

    if not PREFIJO_FECHA_FALLBACK:
        print("  [aviso] tables_and_fixtures vino vacío y no hay PREFIJO_FECHA_FALLBACK "
              "configurado todavía -- correr con --debug, mirar el dump y completarlo "
              "en scraper_promiedos_federal.py.")
        return []

    print("  [aviso] tables_and_fixtures vino vacío; genero las claves de fecha a mano.")
    return _fechas_por_rango(PREFIJO_FECHA_FALLBACK)


def _extraer_jornada(stage_round_name: str | None) -> int | None:
    m = re.search(r"(\d+)", stage_round_name or "")
    return int(m.group(1)) if m else None


def _goles_por_jugador(equipo_json: dict) -> dict[str, int]:
    conteo: dict[str, int] = {}
    for gol in equipo_json.get("goals", []):
        jugador = gol.get("player_name")
        if not jugador:
            continue
        conteo[jugador] = conteo.get(jugador, 0) + 1
    return conteo


def _partidos_de_fecha(key: str, zona_por_equipo: dict[str, str]) -> list[dict]:
    """Devuelve solo los partidos ya FINALIZADOS de una fecha puntual."""
    data = _get_json(f"/league/games/{LEAGUE_ID}/{key}")
    partidos = []
    for g in data.get("games", []):
        if g.get("status", {}).get("name") != "Finalizado":
            continue
        equipos = g.get("teams", [])
        scores = g.get("scores", [])
        if len(equipos) != 2 or len(scores) != 2:
            continue

        local_promiedos = equipos[0].get("short_name") or equipos[0].get("name")
        visitante_promiedos = equipos[1].get("short_name") or equipos[1].get("name")

        # Traduce al nombre oficial (tabla/fixture) cuando se puede resolver;
        # si no, deja el nombre de Promiedos tal cual para que quede visible
        # en "sin_matchear" en vez de perderse.
        local = resolver_equipo(local_promiedos) or local_promiedos
        visitante = resolver_equipo(visitante_promiedos) or visitante_promiedos

        partidos.append({
            "jornada": _extraer_jornada(g.get("stage_round_name")),
            "equipo_local": local,
            "equipo_visitante": visitante,
            "goles_local": int(scores[0]),
            "goles_visitante": int(scores[1]),
            # Informativo: de qué zona es el partido, resuelta por
            # plantel contra tabla_federal_a.csv (puede venir None si
            # todavía no hay CSV o el nombre no matcheó ninguna zona).
            "zona": zona_por_equipo.get(local) or zona_por_equipo.get(visitante),
            "goleadores_local": _goles_por_jugador(equipos[0]),
            "goleadores_visitante": _goles_por_jugador(equipos[1]),
        })
    return partidos


def obtener_partidos_jugados_federal(fechas: list[str] | None = None) -> list[dict]:
    """Trae todos los partidos jugados del Federal A (todas las fechas
    disponibles, o solo las que se pasen en `fechas` como lista de
    "key"). Nombres de equipo tal como los da Promiedos -- ver
    docstring del módulo sobre mapeo_equipos_federal.py."""
    zona_por_equipo = _cargar_zona_por_equipo()

    if fechas is None:
        fechas = [f["key"] for f in obtener_fechas_disponibles()]

    partidos = []
    for key in fechas:
        try:
            partidos.extend(_partidos_de_fecha(key, zona_por_equipo))
        except Exception as e:
            print(f"  [aviso] no se pudo leer la fecha {key}: {e}")
        time.sleep(PAUSA_ENTRE_PEDIDOS)
    return partidos


def _modo_debug():
    print("Bajando lista de fechas (Federal A)...")
    fechas = obtener_fechas_disponibles()
    print(f"  {len(fechas)} fechas encontradas.")

    if not fechas:
        print("\nNo se encontró ninguna fecha ni por tables_and_fixtures ni por el "
              "fallback. Guardando la respuesta cruda de tables_and_fixtures para "
              "inspección manual...")
        try:
            data = _get_json(f"/league/tables_and_fixtures/{LEAGUE_ID}")
        except Exception as e:
            data = {"error": str(e)}
        with open("debug_promiedos_federal_dump.json", "w", encoding="utf-8") as f:
            json.dump({"tables_and_fixtures_raw": data}, f, ensure_ascii=False, indent=2)
        print("Guardado en debug_promiedos_federal_dump.json -- revisar la forma real "
              "del JSON (games.filters, o de dónde sacar la key de una fecha) y ajustar "
              "este scraper si hace falta.")
        return

    print("Bajando partidos de todas las fechas (puede tardar unos segundos)...")
    partidos = obtener_partidos_jugados_federal([f["key"] for f in fechas])

    with open("debug_promiedos_federal_dump.json", "w", encoding="utf-8") as f:
        json.dump({"fechas": fechas, "partidos_jugados": partidos}, f, ensure_ascii=False, indent=2)

    print(f"\n{len(partidos)} partidos FINALIZADOS encontrados en total.")
    print("Guardado en debug_promiedos_federal_dump.json")
    print("\nÚltimos 10:")
    for p in partidos[-10:]:
        print(f"  Fecha {p['jornada']} (zona {p['zona']}): "
              f"{p['equipo_local']} {p['goles_local']} - {p['goles_visitante']} {p['equipo_visitante']}")


if __name__ == "__main__":
    if "--debug" in sys.argv:
        _modo_debug()
    else:
        partidos = obtener_partidos_jugados_federal()
        print(f"{len(partidos)} partidos jugados encontrados:")
        for p in partidos:
            print(f"  Fecha {p['jornada']} (zona {p['zona']}): "
                  f"{p['equipo_local']} {p['goles_local']} - {p['goles_visitante']} {p['equipo_visitante']}")
