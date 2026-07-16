# -*- coding: utf-8 -*-
"""
scraper_promiedos_lpf.py

Scraper definitivo de Promiedos para la Liga Profesional Argentina (LPF),
calcado en su forma de uso de scraper_promiedos.py (Nacional), pero
adaptado a lo que en verdad expone la API para "hc":

  - El único endpoint que sirve es /league/games/{LEAGUE_ID}/latest.
    No hay forma de paginar (page/before/offset se ignoran) ni de pedir
    tables_and_fixtures (siempre vacío). Pero no hace falta: esa "ventana"
    de 100 partidos ya trae TODA la fase regular publicada hasta el
    momento (se va a ir extendiendo sola a medida que la AFA anuncie más
    fechas -- simplemente hay que volver a pedir el endpoint más adelante).

  - La respuesta mezcla dos cosas: partidos de la Copa/torneo anterior
    (ya jugados, sin campo "stage_round_name") y partidos de la Liga
    Profesional actual (con "stage_round_name": "Fecha N"). Este scraper
    se queda solo con los segundos.

  - Un partido se considera "jugado" cuando status.enum == 3 (incluye
    variantes como "Finalizado", "Por penales", "En Tiempo Extra"; en
    fase de liga regular debería ser siempre "Finalizado" liso y llano,
    pero se contempla igual por las dudas).

Uso:
    python scraper_promiedos_lpf.py

Escribe (o pisa) fixture_lpf.csv y resultados_lpf.csv en la carpeta
donde se corra (nombres distintos a los de Nacional a propósito, para
no pisar fixture.csv/resultados.csv del otro torneo), con las mismas
columnas que usa el proyecto de Nacional:

    fixture_lpf.csv:    fecha,jornada,equipo_local,equipo_visitante
    resultados_lpf.csv: fecha,jornada,equipo_local,equipo_visitante,goles_local,goles_visitante

("fecha" se deja vacío a propósito, igual que en Nacional -- es una
columna que quedó sin usar en ese proyecto).

También se puede importar y usar programáticamente:

    from scraper_promiedos_lpf import obtener_partidos_lpf
    partidos = obtener_partidos_lpf()  # lista de dicts

Cada dict tiene: jornada (int), equipo_local, equipo_visitante,
jugado (bool), goles_local, goles_visitante (None si no se jugó),
estado (str), fecha_hora (str, tal cual la da Promiedos: "DD-MM-YYYY HH:MM").
"""
import csv
import json
import urllib.error
import urllib.request

BASE_URL = "https://api.promiedos.com.ar"
LEAGUE_ID = "hc"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-AR,es;q=0.9",
    # No hizo diferencia en las pruebas, pero no está de más mandarlos.
    "Referer": "https://www.promiedos.com.ar/league/liga-profesional/hc",
    "Origin": "https://www.promiedos.com.ar",
}
TIMEOUT = 20

FIXTURE_CSV = "fixture_lpf.csv"
RESULTADOS_CSV = "resultados_lpf.csv"

# Estados de partido cuyo enum == 3 se consideran "jugado" (por si
# apareciera algún desempate por penales entre semana, aunque en la
# fase regular de liga no debería pasar).
ESTADOS_JUGADO_ENUM = {3}


def _get_json(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def obtener_partidos_lpf():
    """Trae y parsea los partidos de fase regular de la LPF (Liga
    Profesional). Descarta lo que sea de la Copa/torneo anterior (lo que
    no tiene "stage_round_name")."""
    data = _get_json(f"/league/games/{LEAGUE_ID}/latest")
    partidos = []

    for g in data.get("games", []):
        stage = g.get("stage_round_name")
        if not stage or not stage.lower().startswith("fecha"):
            continue  # partido de otro torneo (ej. Copa de la Liga anterior)

        try:
            jornada = int(stage.split()[-1])
        except (ValueError, IndexError):
            continue

        equipo_local = g["teams"][0]["name"]
        equipo_visitante = g["teams"][1]["name"]
        estado = g.get("status", {})
        tiene_estado_jugado = estado.get("enum") in ESTADOS_JUGADO_ENUM

        goles_local = goles_visitante = None
        scores = g.get("scores") or []
        if (
            tiene_estado_jugado
            and len(scores) == 2
            and scores[0] is not None
            and scores[1] is not None
        ):
            goles_local = int(scores[0])
            goles_visitante = int(scores[1])

        # Un partido solo se considera "jugado" si además tiene los
        # goles cargados. Promiedos a veces marca aplazados/suspendidos
        # con el mismo status enum que los finalizados, pero sin scores
        # -- en ese caso lo tratamos como pendiente (va al fixture), no
        # como jugado sin goles (ver mismo fix en
        # scraper_promiedos_primerac.py).
        jugado = tiene_estado_jugado and goles_local is not None and goles_visitante is not None

        partidos.append({
            "jornada": jornada,
            "equipo_local": equipo_local,
            "equipo_visitante": equipo_visitante,
            "jugado": jugado,
            "goles_local": goles_local,
            "goles_visitante": goles_visitante,
            "estado": estado.get("name", ""),
            "fecha_hora": g.get("start_time", ""),
        })

    # Orden estable por jornada y, dentro de cada jornada, por horario.
    partidos.sort(key=lambda p: (p["jornada"], p["fecha_hora"]))
    return partidos


def escribir_csvs(partidos, fixture_path=FIXTURE_CSV, resultados_path=RESULTADOS_CSV):
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
            writer.writerow(["", p["jornada"], p["equipo_local"], p["equipo_visitante"], p["goles_local"], p["goles_visitante"]])

    return len(jugados), len(pendientes)


def obtener_partidos_jugados_lpf():
    """Igual que obtener_partidos_lpf(), pero se queda solo con los ya
    jugados y devuelve las claves en el formato que espera
    actualizar_resultados_lpf.py (mismo "contrato" que
    scraper_promiedos.obtener_partidos_jugados() en el proyecto de
    Nacional). No hay datos de goleadores en este endpoint de Promiedos,
    así que esas claves quedan siempre vacías."""
    jugados = [p for p in obtener_partidos_lpf() if p["jugado"]]
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
    print(f"Pidiendo /league/games/{LEAGUE_ID}/latest ...")
    try:
        partidos = obtener_partidos_lpf()
    except urllib.error.URLError as e:
        print(f"ERROR al conectar con Promiedos: {e}")
        return

    if not partidos:
        print("No se encontró ningún partido de fase regular (¿cambió el formato de la respuesta?).")
        return

    n_jugados, n_pendientes = escribir_csvs(partidos)
    jornadas = sorted(set(p["jornada"] for p in partidos))

    print(f"\nListo. {len(partidos)} partidos de liga encontrados (jornadas {jornadas[0]} a {jornadas[-1]}).")
    print(f"  - Jugados   -> {resultados_csv_msg(n_jugados)} escritos en {RESULTADOS_CSV}")
    print(f"  - Pendientes -> {n_pendientes} escritos en {FIXTURE_CSV}")


def resultados_csv_msg(n):
    return n


if __name__ == "__main__":
    main()
