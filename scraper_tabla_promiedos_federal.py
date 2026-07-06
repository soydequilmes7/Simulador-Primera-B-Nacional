# -*- coding: utf-8 -*-
"""
scraper_tabla_promiedos_federal.py

Trae las 4 TABLAS DE POSICIONES del Torneo Federal A desde Promiedos y
las escribe en tabla_federal_a.csv, mismo formato que usa el resto del
proyecto. Calcado de scraper_tabla_promiedos_bmetro.py, con una
diferencia: acá hay 4 tablas (una por zona) en vez de una sola, y no
confiamos en que Promiedos las nombre "Zona 1".."Zona 4" -- cada tabla
se asigna a la zona real comparando su plantel contra
tabla_federal_a.csv (que ya tiene la zona correcta de cada equipo,
sembrada del Reglamento): la zona con más equipos en común gana.

Forma esperada del JSON (no verificada en vivo para esta liga -- se
asume la misma estructura que ya funciona para B Metro, con
tables_groups[*]["tables"] en vez de un único tables_groups[0]["tables"][0]):
    data["tables_groups"] -> lista de grupos, cada uno con sus "tables"
    cada tabla: {"table": {"rows": [...]}}
    cada fila: igual que B Metro (num, values, entity.object.name)

Requiere el header X-Ver (sin él, la API devuelve {} vacío con 200 OK).

Uso:
    python scraper_tabla_promiedos_federal.py
"""
from __future__ import annotations

import csv
import json
import os
import ssl
import urllib.error
import urllib.request

DATOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos")

BASE_URL = "https://api.promiedos.com.ar"
LEAGUE_ID = "fahi"
ENDPOINT = f"/league/tables_and_fixtures/{LEAGUE_ID}"
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
TABLA_CSV = os.path.join(DATOS_DIR, "tabla_federal_a.csv")


def _get_json(path: str) -> dict:
    req = urllib.request.Request(f"{BASE_URL}{path}", headers=HEADERS)
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
    with open(TABLA_CSV, newline="", encoding="utf-8") as f:
        return {fila["equipo"]: fila["zona"] for fila in csv.DictReader(f)}


def _parsear_filas_tabla(rows: list[dict]) -> list[dict]:
    filas = []
    for row in rows:
        valores = {v["key"]: v["value"] for v in row["values"]}
        nombre = row["entity"]["object"]["name"]

        gf, gc = 0, 0
        goles = valores.get("Goals", "0:0")
        if ":" in goles:
            gf_str, gc_str = goles.split(":", 1)
            gf, gc = int(gf_str), int(gc_str)

        filas.append({
            "equipo": nombre,
            "pj": int(valores.get("GamePlayed", 0)),
            "g": int(valores.get("GamesWon", 0)),
            "e": int(valores.get("GamesEven", 0)),
            "p": int(valores.get("GamesLost", 0)),
            "gf": gf,
            "gc": gc,
            "dg": int(valores.get("Ratio", gf - gc)),
            "puntos": int(valores.get("Points", 0)),
        })
    return filas


def _zona_mas_probable(equipos_tabla: list[str], zona_por_equipo: dict[str, str]) -> str | None:
    """Compara el plantel de una tabla scrapeada contra las 4 zonas
    conocidas y devuelve la que más nombres tiene en común. None si no
    matchea ninguno (tabla de otra categoría, o nombres muy distintos)."""
    conteo: dict[str, int] = {}
    for equipo in equipos_tabla:
        zona = zona_por_equipo.get(equipo)
        if zona:
            conteo[zona] = conteo.get(zona, 0) + 1
    if not conteo:
        return None
    return max(conteo, key=conteo.get)


def obtener_tablas_federal() -> dict[str, list[dict]]:
    """{"1": [...], "2": [...], "3": [...], "4": [...]} -- cada lista ya
    ordenada por puntos/dg/gf, con la zona resuelta por plantel."""
    zona_por_equipo = _cargar_zona_por_equipo()
    data = _get_json(ENDPOINT)

    tablas_por_zona: dict[str, list[dict]] = {}
    sin_matchear = []

    for grupo in data.get("tables_groups", []):
        for tabla in grupo.get("tables", []):
            rows = tabla.get("table", {}).get("rows", [])
            if not rows:
                continue
            filas = _parsear_filas_tabla(rows)
            zona = _zona_mas_probable([f["equipo"] for f in filas], zona_por_equipo)
            if zona is None:
                sin_matchear.append([f["equipo"] for f in filas])
                continue
            filas.sort(key=lambda f: (-f["puntos"], -f["dg"], -f["gf"]))
            tablas_por_zona[zona] = filas

    if sin_matchear:
        print(f"AVISO: {len(sin_matchear)} tabla(s) no matchearon ninguna zona conocida:")
        for equipos in sin_matchear:
            print(f"  {equipos[:3]}...")

    return tablas_por_zona


def escribir_csv(tablas_por_zona: dict[str, list[dict]], path: str = TABLA_CSV) -> int:
    total = 0
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["zona", "posicion", "equipo", "partidos_jugados", "ganados",
                          "empatados", "perdidos", "gf", "gc", "dg", "puntos"])
        for zona in sorted(tablas_por_zona):
            for i, f in enumerate(tablas_por_zona[zona], start=1):
                writer.writerow([zona, i, f["equipo"], f["pj"], f["g"], f["e"],
                                  f["p"], f["gf"], f["gc"], f["dg"], f["puntos"]])
                total += 1
    return total


def main() -> None:
    print(f"Pidiendo {BASE_URL}{ENDPOINT} ...")
    try:
        tablas_por_zona = obtener_tablas_federal()
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} -- {e.read()[:500]}")
        return
    except urllib.error.URLError as e:
        print(f"ERROR de conexión: {e}")
        return
    except (KeyError, IndexError) as e:
        print(f"La forma del JSON cambió respecto a lo esperado: falta {e}")
        return

    if len(tablas_por_zona) != 4:
        print(f"OJO: se esperaban 4 zonas y se resolvieron {len(tablas_por_zona)} "
              f"({sorted(tablas_por_zona)}) -- revisar antes de usar.")
        if not tablas_por_zona:
            return

    total = escribir_csv(tablas_por_zona)
    print(f"\nListo, {total} equipos escritos en {TABLA_CSV}.")

    for zona in sorted(tablas_por_zona):
        print(f"\nZona {zona} (top 3):")
        for f in tablas_por_zona[zona][:3]:
            print(f"  {f['equipo']:<40} {f['puntos']} pts  ({f['pj']} PJ, DG {f['dg']:+d})")


if __name__ == "__main__":
    main()
