# -*- coding: utf-8 -*-
"""
scraper_ligapro.py

Trae los resultados jugados de la LigaPro Serie A (Ecuador) directamente
desde el propio sitio oficial (ligapro.ec). Son pedidos HTTP normales
(sin Playwright, sin navegador, sin necesidad de imitar TLS de Chrome).

Cómo se encontró este endpoint: ligapro.ec es un sitio en WordPress
donde la sección "Resultados"/"Calendario" se llena con JavaScript
después de cargar la página. Mirando la pestaña Network del navegador
(F12 → Network → Fetch/XHR) mientras carga esa sección, aparecen dos
pedidos propios del sitio:

  - GET https://ligapro.ec/informacion/results/dataResultados.php
      Solo los partidos ya jugados, más reciente primero. Trae fecha,
      "week" (jornada), equipos (con teamid y logo) y el marcador final.

  - GET https://ligapro.ec/informacion/fixtures/dataPartidos.php
      El fixture COMPLETO de la temporada en una sola llamada: pasados
      Y por jugar, agrupados por semana ("fechaSemana"), con
      "estadoComet" ("Played" / "Fixture") indicando si ya se jugó,
      idPartido, equipos, marcador (o "-" si todavía no se jugó) y
      estadio.

Usamos dataPartidos.php porque trae TODO en un solo pedido (no hay que
andar probando fecha por fecha como con Promiedos o Sofascore), y ya
viene con un campo de estado explícito para filtrar solo lo jugado.

A diferencia de Sofascore, este endpoint no está protegido por
Cloudflare/Akamai ni exige imitar la huella TLS de un navegador: es un
.php propio del sitio que responde directo con JSON. Tampoco hace falta
generar keys de temporada a mano como con Promiedos.

LIMITACIÓN: este endpoint no trae goleadores por jugador (a diferencia
del scraper de Promiedos). Si en algún momento se necesita ese dato,
habría que revisar si existe otro endpoint bajo /informacion/ que dé el
detalle de un partido puntual a partir de su "idPartido" (se puede
buscar de la misma forma: Network tab en la ficha de un partido jugado).

IMPORTANTE: si en algún momento este script deja de traer partidos, lo
más probable es que ligapro.ec haya cambiado la ruta del endpoint (por
ejemplo si renuevan el sitio). Correr con --debug y mirar
debug_ligapro_dump.json para diagnosticar.

Uso:
    from scraper_ligapro import obtener_partidos_jugados
    partidos = obtener_partidos_jugados()
    # [{"jornada": 1, "equipo_local": "Orense SC", "equipo_visitante": "Liga...",
    #   "goles_local": 1, "goles_visitante": 2, "estadio": "...", "fecha": "2026-02-20",
    #   "id_partido": "5d36f1yakrhk9zm2eejddkhec"}, ...]

Modo debug (baja todo y lo guarda para inspección manual):
    python scraper_ligapro.py --debug
"""
import json
import sys
import urllib.request

BASE_URL = "https://ligapro.ec/informacion"
ENDPOINT_PARTIDOS = "/fixtures/dataPartidos.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9",
    "Referer": "https://ligapro.ec/resultados",
}
TIMEOUT = 20


def _get_json(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _es_gol_valido(score):
    """El campo scoreLocal/scoreVisitante viene como '-' en partidos aún no jugados."""
    return isinstance(score, (int, float)) or (isinstance(score, str) and score.strip().lstrip("-").isdigit() and score.strip() != "-")


def obtener_fixture_completo():
    """
    Devuelve el fixture completo tal como lo entrega ligapro.ec: una lista
    de semanas, cada una con su lista de partidos (jugados y por jugar).
    Útil si en algún momento se quiere mostrar también el calendario de
    partidos pendientes, no solo los resultados.
    """
    data = _get_json(ENDPOINT_PARTIDOS)
    return data.get("result", [])


def obtener_partidos_jugados():
    """
    Trae todos los partidos YA JUGADOS de la temporada (filtra por
    estadoComet == "Played"). Un solo pedido HTTP trae todo el fixture,
    así que no hace falta ir fecha por fecha.
    """
    semanas = obtener_fixture_completo()
    partidos = []

    for semana in semanas:
        jornada_raw = semana.get("fechaSemana")
        try:
            jornada = int(jornada_raw)
        except (TypeError, ValueError):
            jornada = jornada_raw

        for p in semana.get("partidos", []):
            if p.get("estadoComet") != "Played":
                continue

            local = p.get("clubLocal", {}) or {}
            visitante = p.get("clubVisitante", {}) or {}
            goles_local = local.get("scoreLocal")
            goles_visitante = visitante.get("scoreVisitante")

            if not (_es_gol_valido(goles_local) and _es_gol_valido(goles_visitante)):
                continue

            partidos.append({
                "jornada": jornada,
                "id_partido": p.get("idPartido"),
                "fecha": p.get("fechaPartido"),
                "hora": p.get("horaPartido"),
                "equipo_local": local.get("razonSocialLocal"),
                "equipo_visitante": visitante.get("razonSocialVisitante"),
                "goles_local": int(goles_local),
                "goles_visitante": int(goles_visitante),
                "estadio": (p.get("estadio") or {}).get("estadio"),
            })

    return partidos


def _modo_debug():
    print("Bajando fixture completo de ligapro.ec...")
    semanas = obtener_fixture_completo()
    print(f"  {len(semanas)} semanas encontradas en el fixture.")

    partidos = obtener_partidos_jugados()

    with open("debug_ligapro_dump.json", "w", encoding="utf-8") as f:
        json.dump({"semanas_crudo": semanas, "partidos_jugados": partidos}, f, ensure_ascii=False, indent=2)

    print(f"\n{len(partidos)} partidos FINALIZADOS encontrados en total.")
    print("Guardado en debug_ligapro_dump.json")
    print("\nÚltimos 10:")
    for p in partidos[-10:]:
        print(f"  Fecha {p['jornada']}: {p['equipo_local']} {p['goles_local']} - {p['goles_visitante']} {p['equipo_visitante']}")


if __name__ == "__main__":
    if "--debug" in sys.argv:
        _modo_debug()
    else:
        partidos = obtener_partidos_jugados()
        print(f"{len(partidos)} partidos jugados encontrados:")
        for p in partidos:
            print(f"  Fecha {p['jornada']}: {p['equipo_local']} {p['goles_local']} - {p['goles_visitante']} {p['equipo_visitante']}")
