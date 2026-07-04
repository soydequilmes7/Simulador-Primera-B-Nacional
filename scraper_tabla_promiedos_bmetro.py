# -*- coding: utf-8 -*-
"""
scraper_tabla_promiedos_bmetro.py

Trae la TABLA DE POSICIONES de la Primera B Metropolitana desde Promiedos
y la escribe en tabla_bmetro.csv con el mismo formato que usa el resto
del proyecto.

Endpoint confirmado (sacado del navegador con F12 -> Network):
    https://api.promiedos.com.ar/league/tables_and_fixtures/fahh

Forma real del JSON (confirmada a mano):
    data["tables_groups"][0]["tables"][0]["table"]["rows"] -> lista de filas
    cada fila:
      {
        "num": 1,
        "values": [{"key": "GamePlayed", "value": "22"}, {"key": "Goals", "value": "33:12"}, ...],
        "entity": {"object": {"name": "Excursionistas", ...}},
        "destination_color": "#B7D42A"
      }
    "Goals" viene como "GF:GC" (string), hay que separarlo por ":".

Requiere mandar el header X-Ver (el que usa la propia web); sin él, la
API devuelve {} vacío aunque responda 200 OK.

Uso:
    python scraper_tabla_promiedos_bmetro.py
"""
import csv
import json
import urllib.error
import urllib.request

BASE_URL = "https://api.promiedos.com.ar"
LEAGUE_ID = "fahh"
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
TABLA_CSV = "tabla_bmetro.csv"


def _get_json(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def obtener_tabla_bmetro():
    """Devuelve una lista de dicts ya parseados y ordenados por puntos:
    [{equipo, pj, g, e, p, gf, gc, dg, puntos}, ...]"""
    data = _get_json(ENDPOINT)
    return parsear_tabla(data)


def parsear_tabla(data):
    rows = data["tables_groups"][0]["tables"][0]["table"]["rows"]

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

    filas.sort(key=lambda f: (-f["puntos"], -f["dg"], -f["gf"]))
    return filas


def escribir_csv(filas, path=TABLA_CSV):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["zona", "posicion", "equipo", "partidos_jugados", "ganados",
                          "empatados", "perdidos", "gf", "gc", "dg", "puntos"])
        for i, f in enumerate(filas, start=1):
            writer.writerow(["Unica", i, f["equipo"], f["pj"], f["g"], f["e"],
                              f["p"], f["gf"], f["gc"], f["dg"], f["puntos"]])


def main():
    print(f"Pidiendo {BASE_URL}{ENDPOINT} ...")
    try:
        data = _get_json(ENDPOINT)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} -- {e.read()[:500]}")
        return
    except urllib.error.URLError as e:
        print(f"ERROR de conexión: {e}")
        return

    print(f"\nClaves de primer nivel del JSON: {list(data.keys())}")
    for k in data.keys():
        if k not in ("tables_groups",):
            v = data[k]
            preview = json.dumps(v, ensure_ascii=False)[:800]
            print(f"\n--- data['{k}'] (preview) ---\n{preview}")

    try:
        filas = parsear_tabla(data)
    except (KeyError, IndexError) as e:
        print(f"\nLa forma del JSON cambió respecto a lo esperado: falta {e}")
        return

    escribir_csv(filas)
    print(f"\nListo, {len(filas)} equipos escritos en {TABLA_CSV}.")
    if len(filas) != 22:
        print(f"OJO: se esperaban 22 equipos y se escribieron {len(filas)} -- revisar antes de usar.")

    print("\nTop 3:")
    for f in filas[:3]:
        print(f"  {f['equipo']:<20} {f['puntos']} pts  ({f['pj']} PJ, DG {f['dg']:+d})")


if __name__ == "__main__":
    main()
