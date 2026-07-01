# -*- coding: utf-8 -*-
"""
scraper_promiedos.py

Trae los resultados jugados de la Primera Nacional desde la API pública
de Promiedos (api.promiedos.com.ar). Son pedidos HTTP normales (sin
Playwright, sin navegador).

Confirmado inspeccionando la API real (ver fecha18.json / tabla_fixtures2.json):

  - GET /league/tables_and_fixtures/{LEAGUE_ID}
      Debería traer, entre otras cosas, games.filters: la lista de todas
      las fechas del torneo con su "key" interna
      (ej: {"name": "Fecha 18", "key": "419_46_1_18"}).
      EN LA PRÁCTICA este endpoint nos está devolviendo "{}" vacío con
      status 200 (verificado). Es una protección anti-bot del lado de
      Promiedos que no bloquea con error, directamente "vacía" la
      respuesta cuando el pedido no viene de un navegador real.

  - GET /league/games/{LEAGUE_ID}/{key}
      Este SÍ funciona perfecto con un pedido HTTP común (confirmado con
      fecha18.json, clave "419_46_1_18": trajo los 18 partidos completos).
      Cada partido tiene:
        "teams": [ {"short_name": "...", "goals": [{"player_name": "...", ...}], ...},
                   {"short_name": "...", "goals": [...], ...} ]
        "scores": [golesEquipo1, golesEquipo2]   (solo si ya se jugó)
        "status": {"name": "Finalizado" | "Prog." | ...}
      El campo "goals" de cada equipo trae el detalle de quién convirtió,
      así que de paso sacamos también goles por jugador (ver
      goleadores_local / goleadores_visitante en obtener_partidos_jugados).

Como tables_and_fixtures está bloqueado, no podemos usarlo para conseguir
la lista de "keys" de cada fecha. En cambio, generamos esas keys nosotros:
la que conseguimos ("419_46_1_18") tiene la forma
    {torneo}_{temporada}_{zona}_{número de fecha}
así que probamos "419_46_1_1", "419_46_1_2", ... contra el endpoint que sí
funciona, y frenamos cuando varias seguidas no traen partidos (fin del
torneo, o cambió el formato).

El scraper primero INTENTA el camino "prolijo" (tables_and_fixtures) por si
algún día deja de estar bloqueado, y si no, cae solo al modo de generar las
keys a mano.

IMPORTANTE: si en algún momento esto deja de funcionar (0 partidos siempre,
o un salto raro en los números de fecha), correr con --debug y mirar
debug_promiedos_dump.json. Lo más probable es que haya que actualizar
PREFIJO_FECHA de abajo (cambia de temporada a temporada).

Uso:
    from scraper_promiedos import obtener_partidos_jugados
    partidos = obtener_partidos_jugados()
    # [{"jornada": 18, "equipo_local": "Midland", "equipo_visitante": "Atlanta",
    #   "goles_local": 1, "goles_visitante": 2}, ...]

Modo debug (baja todo y lo guarda para inspección manual):
    python scraper_promiedos.py --debug
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request

LEAGUE_ID = "ebj"  # Primera Nacional
BASE_URL = "https://api.promiedos.com.ar"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-AR,es;q=0.9",
}
TIMEOUT = 15

# Clave confirmada para "Fecha 18": "419_46_1_18". Se arma reemplazando el
# número final. Si Promiedos cambia el torneo/temporada, este prefijo hay
# que actualizarlo (correr --debug y fijarse qué onda).
PREFIJO_FECHA = "419_46_1_"
MAX_FECHAS = 40  # margen amplio; la Nacional suele tener ~35-37 fechas
FALLOS_SEGUIDOS_PARA_FRENAR = 3
PAUSA_ENTRE_PEDIDOS = 0.3  # segundos, para no golpear la API de una


def _get_json(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fechas_desde_tables_and_fixtures():
    """
    Camino "prolijo": intenta leer games.filters de tables_and_fixtures.
    Devuelve [] si el endpoint está vacío/bloqueado (no tira excepción,
    para que el llamador pueda caer al fallback sin drama).
    """
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


def _fechas_por_rango(prefijo=PREFIJO_FECHA, max_fechas=MAX_FECHAS):
    """
    Fallback: genera las keys "{prefijo}{n}" y las prueba una por una contra
    /league/games/{LEAGUE_ID}/{key} (que sabemos que funciona). Frena
    cuando junta varios fallos/vacíos seguidos.
    """
    fechas = []
    fallos_seguidos = 0
    for n in range(1, max_fechas + 1):
        key = f"{prefijo}{n}"
        try:
            data = _get_json(f"/league/games/{LEAGUE_ID}/{key}")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                fallos_seguidos += 1
            else:
                print(f"  [aviso] fecha {n} ({key}): HTTP {e.code}")
                fallos_seguidos += 1
            if fallos_seguidos >= FALLOS_SEGUIDOS_PARA_FRENAR:
                break
            time.sleep(PAUSA_ENTRE_PEDIDOS)
            continue
        except Exception as e:
            print(f"  [aviso] fecha {n} ({key}): {e}")
            fallos_seguidos += 1
            if fallos_seguidos >= FALLOS_SEGUIDOS_PARA_FRENAR:
                break
            time.sleep(PAUSA_ENTRE_PEDIDOS)
            continue

        if not (data or {}).get("games"):
            fallos_seguidos += 1
            if fallos_seguidos >= FALLOS_SEGUIDOS_PARA_FRENAR:
                break
            time.sleep(PAUSA_ENTRE_PEDIDOS)
            continue

        fallos_seguidos = 0
        fechas.append({"nombre": f"Fecha {n}", "key": key})
        time.sleep(PAUSA_ENTRE_PEDIDOS)

    return fechas


def obtener_fechas_disponibles():
    """
    Devuelve la lista de fechas del torneo: [{"nombre": "Fecha 1", "key": "..."}, ...]
    Intenta primero tables_and_fixtures; si viene vacío (bloqueado), genera
    las keys a mano probando el rango de números de fecha.
    """
    fechas = _fechas_desde_tables_and_fixtures()
    if fechas:
        return fechas

    print("  [aviso] tables_and_fixtures vino vacío (bloqueo anti-bot conocido); "
          "genero las claves de fecha a mano.")
    return _fechas_por_rango()


def _extraer_jornada(stage_round_name):
    m = re.search(r"(\d+)", stage_round_name or "")
    return int(m.group(1)) if m else None


def _goles_por_jugador(equipo_json):
    """
    Cuenta los goles de cada jugador dentro de la lista "goals" que trae
    Promiedos para un equipo en un partido puntual.
    Devuelve {"Nombre Jugador": cantidad_de_goles_en_ESE_partido, ...}
    (un jugador puede aparecer con 2+ si convirtió más de uno).
    """
    conteo = {}
    for gol in equipo_json.get("goals", []):
        jugador = gol.get("player_name")
        if not jugador:
            continue
        conteo[jugador] = conteo.get(jugador, 0) + 1
    return conteo


def _partidos_de_fecha(key):
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
        partidos.append({
            "jornada": _extraer_jornada(g.get("stage_round_name")),
            "equipo_local": equipos[0].get("short_name") or equipos[0].get("name"),
            "equipo_visitante": equipos[1].get("short_name") or equipos[1].get("name"),
            "goles_local": int(scores[0]),
            "goles_visitante": int(scores[1]),
            # Goles por jugador de cada equipo en ESTE partido puntual (no
            # acumulado). resolver_equipo() todavía hay que aplicarlo al
            # nombre del equipo, igual que con equipo_local/equipo_visitante.
            "goleadores_local": _goles_por_jugador(equipos[0]),
            "goleadores_visitante": _goles_por_jugador(equipos[1]),
        })
    return partidos


def obtener_partidos_jugados(fechas=None):
    """
    Trae todos los partidos ya jugados del torneo (todas las fechas, o
    solo las que se pasen en `fechas` como lista de "key").
    Devuelve nombres de equipo TAL COMO los da Promiedos (short_name) -
    todavía hay que pasarlos por mapeo_equipos.resolver_equipo().
    """
    if fechas is None:
        fechas = [f["key"] for f in obtener_fechas_disponibles()]

    partidos = []
    for key in fechas:
        try:
            partidos.extend(_partidos_de_fecha(key))
        except Exception as e:
            print(f"  [aviso] no se pudo leer la fecha {key}: {e}")
        time.sleep(PAUSA_ENTRE_PEDIDOS)
    return partidos


def _modo_debug():
    print("Bajando lista de fechas...")
    fechas = obtener_fechas_disponibles()
    print(f"  {len(fechas)} fechas encontradas.")

    print("Bajando partidos de todas las fechas (puede tardar unos segundos)...")
    partidos = obtener_partidos_jugados([f["key"] for f in fechas])

    with open("debug_promiedos_dump.json", "w", encoding="utf-8") as f:
        json.dump({"fechas": fechas, "partidos_jugados": partidos}, f, ensure_ascii=False, indent=2)

    print(f"\n{len(partidos)} partidos FINALIZADOS encontrados en total.")
    print("Guardado en debug_promiedos_dump.json")
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
