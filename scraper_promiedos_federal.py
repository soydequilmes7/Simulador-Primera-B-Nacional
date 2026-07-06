# -*- coding: utf-8 -*-
"""
scraper_promiedos_federal.py

Trae el fixture completo del Torneo Federal A desde la API pública de
Promiedos (api.promiedos.com.ar): partidos jugados y pendientes. Mantiene
el contrato viejo de obtener_partidos_jugados_federal(), pero también puede
regenerar fixture_federal_a.csv y resultados_federal_a.csv.

  - LEAGUE_ID = "fahi" (Federal A).
  - Hace falta el header X-Ver -- sin él, la API devuelve "{}" vacío con
    status 200 (no tira error, así que si no se manda este header parece
    que "no hay partidos" en vez de fallar de forma obvia).
  - El camino principal lee games.filters desde tables_and_fixtures.
  - Si ese endpoint falla o viene vacío, se prueban las keys por rango.
    La temporada 2026 usa "5078_42_1_N" para la Fecha 1..17 y
    "5078_42_2_18" para la Fecha 18, así que el fallback acepta varios
    prefijos y prueba todos los candidatos para cada número de fecha.

Uso:
    python scraper_promiedos_federal.py
    # escribe datos/fixture_federal_a.csv y datos/resultados_federal_a.csv

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
import ssl
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
PREFIJOS_FECHA_FALLBACK = ("5078_42_1_", "5078_42_2_")
MAX_FECHAS = 40
FALLOS_SEGUIDOS_PARA_FRENAR = 3
PAUSA_ENTRE_PEDIDOS = 0.3

DATOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos")
TABLA_CSV = os.path.join(DATOS_DIR, "tabla_federal_a.csv")
FIXTURE_CSV = os.path.join(DATOS_DIR, "fixture_federal_a.csv")
RESULTADOS_CSV = os.path.join(DATOS_DIR, "resultados_federal_a.csv")

ESTADOS_JUGADO_ENUM = {3}


def _get_json(path: str) -> dict:
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
    except urllib.error.URLError as e:
        if not isinstance(e.reason, ssl.SSLCertVerificationError):
            raise
        resp = urllib.request.urlopen(req, timeout=TIMEOUT, context=_ssl_context_fallback())

    with resp:
        return json.loads(resp.read().decode("utf-8"))


def _ssl_context_fallback():
    try:
        import certifi
    except ImportError:
        return ssl._create_unverified_context()
    return ssl.create_default_context(cafile=certifi.where())


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


def _fechas_por_rango(
    prefijos: tuple[str, ...] = PREFIJOS_FECHA_FALLBACK,
    max_fechas: int = MAX_FECHAS,
) -> list[dict]:
    """Fallback: para cada número de fecha prueba varios prefijos posibles.
    Esto cubre el caso real de Federal A 2026, donde la Fecha 18 cambió de
    "5078_42_1_18" a "5078_42_2_18"."""
    fechas = []
    fallos_seguidos = 0
    for n in range(1, max_fechas + 1):
        fecha_encontrada = None
        for prefijo in prefijos:
            key = f"{prefijo}{n}"
            try:
                data = _get_json(f"/league/games/{LEAGUE_ID}/{key}")
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    print(f"  [aviso] fecha {n} ({key}): HTTP {e.code}")
                continue
            except Exception as e:
                print(f"  [aviso] fecha {n} ({key}): {e}")
                continue
            if (data or {}).get("games"):
                fecha_encontrada = {"nombre": f"Fecha {n}", "key": key}
                break

        if fecha_encontrada is None:
            fallos_seguidos += 1
        else:
            fallos_seguidos = 0
            fechas.append(fecha_encontrada)

        if fallos_seguidos >= FALLOS_SEGUIDOS_PARA_FRENAR:
            break
        time.sleep(PAUSA_ENTRE_PEDIDOS)

    return fechas


def obtener_fechas_disponibles() -> list[dict]:
    fechas = _fechas_desde_tables_and_fixtures()
    if fechas:
        return fechas

    if not PREFIJOS_FECHA_FALLBACK:
        print("  [aviso] tables_and_fixtures vino vacío y no hay PREFIJOS_FECHA_FALLBACK "
              "configurado todavía.")
        return []

    print("  [aviso] tables_and_fixtures vino vacío; genero las claves de fecha a mano.")
    return _fechas_por_rango()


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


def _resolver_nombre_equipo(equipo_json: dict) -> str:
    nombre_corto = equipo_json.get("short_name") or ""
    nombre_largo = equipo_json.get("name") or ""
    return (
        resolver_equipo(nombre_corto)
        or resolver_equipo(nombre_largo)
        or nombre_corto
        or nombre_largo
    )


def _parsear_partido(g: dict, zona_por_equipo: dict[str, str]) -> dict | None:
    equipos = g.get("teams", [])
    if len(equipos) != 2:
        return None

    local = _resolver_nombre_equipo(equipos[0])
    visitante = _resolver_nombre_equipo(equipos[1])
    scores = g.get("scores") or []
    tiene_goles = len(scores) == 2 and scores[0] is not None and scores[1] is not None
    estado = g.get("status", {})
    jugado = estado.get("enum") in ESTADOS_JUGADO_ENUM and tiene_goles

    partido = {
        "jornada": _extraer_jornada(g.get("stage_round_name")),
        "equipo_local": local,
        "equipo_visitante": visitante,
        "jugado": jugado,
        "estado": estado.get("name", ""),
        "fecha_hora": g.get("start_time", ""),
        # Informativo: de qué zona es el partido, resuelta por plantel
        # contra tabla_federal_a.csv.
        "zona": zona_por_equipo.get(local) or zona_por_equipo.get(visitante),
        "goleadores_local": _goles_por_jugador(equipos[0]),
        "goleadores_visitante": _goles_por_jugador(equipos[1]),
    }
    if jugado:
        partido["goles_local"] = int(scores[0])
        partido["goles_visitante"] = int(scores[1])
    return partido


def _partidos_de_fecha(key: str, zona_por_equipo: dict[str, str]) -> list[dict]:
    data = _get_json(f"/league/games/{LEAGUE_ID}/{key}")
    partidos = []
    for g in data.get("games", []):
        partido = _parsear_partido(g, zona_por_equipo)
        if partido:
            partidos.append(partido)
    return partidos


def _clave_partido(partido: dict) -> tuple[str, str, str]:
    return (
        str(partido.get("jornada") or ""),
        partido["equipo_local"],
        partido["equipo_visitante"],
    )


def _deduplicar_partidos(partidos: list[dict]) -> list[dict]:
    por_clave = {}
    for partido in partidos:
        clave = _clave_partido(partido)
        anterior = por_clave.get(clave)
        if anterior is None or (partido.get("jugado") and not anterior.get("jugado")):
            por_clave[clave] = partido
    return list(por_clave.values())


def obtener_partidos_federal(fechas: list[str] | None = None) -> list[dict]:
    """Trae todos los partidos publicados del Federal A: jugados y
    pendientes. Los nombres salen normalizados al formato local cuando hay
    alias confiable."""
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
    partidos = _deduplicar_partidos(partidos)
    partidos.sort(key=lambda p: (p.get("jornada") or 999, p.get("fecha_hora") or ""))
    return partidos


def obtener_partidos_jugados_federal(fechas: list[str] | None = None) -> list[dict]:
    """Trae todos los partidos jugados del Federal A (todas las fechas
    disponibles, o solo las que se pasen en `fechas` como lista de
    "key"). Nombres de equipo tal como los da Promiedos -- ver
    docstring del módulo sobre mapeo_equipos_federal.py."""
    return [p for p in obtener_partidos_federal(fechas) if p.get("jugado")]


def escribir_csvs(
    partidos: list[dict],
    fixture_path: str = FIXTURE_CSV,
    resultados_path: str = RESULTADOS_CSV,
) -> tuple[int, int]:
    jugados = [p for p in partidos if p.get("jugado")]
    pendientes = [p for p in partidos if not p.get("jugado")]
    os.makedirs(os.path.dirname(fixture_path), exist_ok=True)
    os.makedirs(os.path.dirname(resultados_path), exist_ok=True)

    with open(fixture_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["fecha", "jornada", "equipo_local", "equipo_visitante"])
        for p in pendientes:
            writer.writerow(["", p["jornada"], p["equipo_local"], p["equipo_visitante"]])

    with open(resultados_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["fecha", "jornada", "equipo_local", "equipo_visitante",
                         "goles_local", "goles_visitante"])
        for p in jugados:
            writer.writerow(["", p["jornada"], p["equipo_local"], p["equipo_visitante"],
                             p["goles_local"], p["goles_visitante"]])

    return len(jugados), len(pendientes)


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
    partidos = obtener_partidos_federal([f["key"] for f in fechas])

    with open("debug_promiedos_federal_dump.json", "w", encoding="utf-8") as f:
        json.dump({"fechas": fechas, "partidos": partidos}, f, ensure_ascii=False, indent=2)

    jugados = [p for p in partidos if p.get("jugado")]
    pendientes = [p for p in partidos if not p.get("jugado")]
    print(f"\n{len(partidos)} partidos encontrados en total.")
    print(f"  Jugados: {len(jugados)}")
    print(f"  Pendientes: {len(pendientes)}")
    print("Guardado en debug_promiedos_federal_dump.json")
    print("\nÚltimos 10:")
    for p in partidos[-10:]:
        if p.get("jugado"):
            marcador = f"{p['goles_local']} - {p['goles_visitante']}"
        else:
            marcador = p.get("estado") or "Pendiente"
        print(f"  Fecha {p['jornada']} (zona {p['zona']}): "
              f"{p['equipo_local']} {marcador} {p['equipo_visitante']}")


if __name__ == "__main__":
    if "--debug" in sys.argv:
        _modo_debug()
    else:
        partidos = obtener_partidos_federal()
        if not partidos:
            print("No se encontró ningún partido de Federal A.")
            sys.exit(1)
        n_jugados, n_pendientes = escribir_csvs(partidos)
        jornadas = sorted({p["jornada"] for p in partidos if p.get("jornada") is not None})
        print(f"\nListo. {len(partidos)} partidos encontrados "
              f"(jornadas {jornadas[0]} a {jornadas[-1]}).")
        print(f"  - Jugados    -> {n_jugados} escritos en {RESULTADOS_CSV}")
        print(f"  - Pendientes -> {n_pendientes} escritos en {FIXTURE_CSV}")
