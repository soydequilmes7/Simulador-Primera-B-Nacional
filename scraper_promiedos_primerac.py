    # -*- coding: utf-8 -*-
"""
scraper_promiedos_primerac.py

Scraper de Promiedos para la Primera C. Calcado de
scraper_promiedos_bmetro.py, con estas diferencias:

  1. LEAGUE_ID = "ffjb" (Primera C en Promiedos).
  2. Escribe fixture_primerac.csv y resultados_primerac.csv.
  3. A diferencia de B Metro (tabla única), Primera C tiene Zona "A" y
     Zona "B" -- pero igual que en fixture.csv/resultados.csv de B
     Nacional, estos CSVs NO llevan columna de zona (la zona de cada
     equipo vive en tabla_primerac.csv). Así que este scraper no
     necesita saber nada de zonas: solo baja fecha por fecha, todos los
     partidos de todas las zonas mezclados, tal como hace Promiedos.

IMPORTANTE (igual que en el de B Metro): hace falta mandar el header
X-Ver; sin él la API devuelve respuestas vacías aunque el status HTTP
sea 200 OK.

Uso:
    python scraper_promiedos_primerac.py

Escribe (o pisa) fixture_primerac.csv y resultados_primerac.csv en
api/datos/ (relativo a este archivo), con las columnas:

    fixture_primerac.csv:    fecha,jornada,equipo_local,equipo_visitante
    resultados_primerac.csv: fecha,jornada,equipo_local,equipo_visitante,goles_local,goles_visitante

También se puede importar y usar programáticamente:

    from scraper_promiedos_primerac import obtener_partidos_jugados_primerac
    partidos = obtener_partidos_jugados_primerac()

NOTA sobre nombres de equipos: como fixture_primerac.csv y
resultados_primerac.csv se arman los dos a partir de la MISMA fuente
(Promiedos), los nombres de equipo_local/equipo_visitante ya salen
consistentes entre sí sin necesitar un mapeo_equipos_primerac.py --
a diferencia del scraper viejo de B Nacional (scraper_promiedos.py),
que sí necesita mapeo_equipos.py porque compara contra un fixture.csv
armado a mano con otros nombres.

Lo que SÍ hay que revisar a mano una sola vez es que los nombres que
tira Promiedos para los 28 equipos de Primera C coincidan con los que
se usen en tabla_primerac.csv (armado aparte, ver
calcular_tabla_primerac.py). Si algún nombre no matchea, este scraper
avisa en "sin_matchear" al correr actualizar_resultados_primerac.py.
"""
import csv
import json
import os
import ssl
import time
import urllib.error
import urllib.request

from mapeo_equipos_primerac import resolver_equipo

try:
    import rutas
except ImportError:
    rutas = None

# Carpeta donde el resto del proyecto guarda los datos (tabla, fixture,
# resultados, data_primerac.json). Usa el mismo módulo `rutas` que el
# resto de los scripts de Primera C (calcular_tabla_primerac.py,
# actualizar_resultados_primerac.py, main_primerac.py) para que todos
# apunten siempre a la misma carpeta, sin importar desde dónde se
# ejecute cada uno. Si por algún motivo `rutas` no está disponible,
# cae a una carpeta "datos" relativa a este archivo como fallback.
if rutas is not None:
    DATOS_DIR = str(rutas.datos_dir())
else:
    DATOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos")

BASE_URL = "https://api.promiedos.com.ar"
LEAGUE_ID = "ffjb"  # Primera C
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

FIXTURE_CSV = os.path.join(DATOS_DIR, "fixture_primerac.csv")
RESULTADOS_CSV = os.path.join(DATOS_DIR, "resultados_primerac.csv")

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
    especial "latest". Incluye TODAS las fechas que Promiedos tenga
    publicadas para esta liga: fase de zonas, interzonales, final por
    el ascenso, reducido, etc. -- se filtran más abajo por nombre."""
    data = _get_json(f"/league/tables_and_fixtures/{LEAGUE_ID}")
    filtros = data["games"]["filters"]
    return [f for f in filtros if f["key"] != "latest"]


def _parsear_partido(g):
    """A diferencia del scraper de B Metro (que solo tiene "Fecha N"),
    Primera C tiene además fechas de Interzonales, Final por el
    ascenso, y el Torneo Reducido -- estas quedan afuera de
    fixture.csv/resultados.csv (que son solo la fase de zonas todos
    contra todos) y se manejan aparte, a mano, cuando llegue el
    momento. Por eso acá solo tomamos "Fecha N"."""
    stage = g.get("stage_round_name")
    if not stage or not stage.lower().startswith("fecha"):
        return None
    try:
        jornada = int(stage.split()[-1])
    except (ValueError, IndexError):
        return None

    equipo_local = resolver_equipo(g["teams"][0]["name"]) or g["teams"][0]["name"]
    equipo_visitante = resolver_equipo(g["teams"][1]["name"]) or g["teams"][1]["name"]
    estado = g.get("status", {})

    goles_local = goles_visitante = None
    tiene_estado_jugado = estado.get("enum") in ESTADOS_JUGADO_ENUM
    if tiene_estado_jugado and "scores" in g and g["scores"][0] is not None and g["scores"][1] is not None:
        goles_local = int(g["scores"][0])
        goles_visitante = int(g["scores"][1])

    # Un partido solo se considera "jugado" si además tiene los goles
    # cargados. Promiedos a veces marca aplazados con el mismo status
    # enum que los finalizados, pero sin scores -- en ese caso lo
    # tratamos como pendiente (va al fixture), no como jugado sin goles.
    jugado = tiene_estado_jugado and goles_local is not None and goles_visitante is not None

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


def obtener_partidos_primerac(verbose=True):
    """Recorre todas las fechas de "Fase de Zonas" y devuelve todos los
    partidos (jugados y pendientes) en una sola lista.

    Promiedos a veces lista el mismo partido dos veces bajo la misma
    fecha (por ejemplo, si hubo alguna corrección o reprogramación
    interna) -- una copia marcada como jugada y otra como pendiente.
    Para evitar que el mismo cruce quede a la vez en
    fixture_primerac.csv y en resultados_primerac.csv, se deduplica
    por (jornada, equipo_local, equipo_visitante), quedándose con la
    versión jugada si hay conflicto."""
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

    partidos_por_clave = {}
    duplicados = []
    for p in partidos:
        clave = (p["jornada"], p["equipo_local"], p["equipo_visitante"])
        anterior = partidos_por_clave.get(clave)
        if anterior is None:
            partidos_por_clave[clave] = p
        elif anterior["jugado"] != p["jugado"]:
            # Conflicto: una copia jugada y otra pendiente. Nos
            # quedamos con la jugada (tiene el resultado real).
            duplicados.append(clave)
            partidos_por_clave[clave] = p if p["jugado"] else anterior
        # Si las dos copias coinciden en "jugado", no importa cuál se
        # use -- se descarta la repetida silenciosamente.

    if duplicados and verbose:
        print(f"  [aviso] {len(duplicados)} partido(s) venían duplicados en la respuesta de "
              f"Promiedos (jugado + pendiente a la vez), se resolvió quedándose con la versión jugada:")
        for jornada, local, visitante in duplicados:
            print(f"    - Fecha {jornada}: {local} vs {visitante}")

    partidos = list(partidos_por_clave.values())
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


def obtener_partidos_jugados_primerac():
    """Igual que obtener_partidos_primerac(), pero solo los jugados, en
    el formato que espera actualizar_resultados_primerac.py."""
    jugados = [p for p in obtener_partidos_primerac(verbose=False) if p["jugado"]]
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
        partidos = obtener_partidos_primerac()
    except urllib.error.URLError as e:
        print(f"ERROR al conectar con Promiedos: {e}")
        return
    except (KeyError, IndexError) as e:
        print(f"La forma del JSON cambió respecto a lo esperado: falta {e}")
        return

    if not partidos:
        print("No se encontró ningún partido de fase de zonas (¿cambió el formato de la respuesta?).")
        return

    n_jugados, n_pendientes = escribir_csvs(partidos)
    jornadas = sorted(set(p["jornada"] for p in partidos))

    print(f"\nListo. {len(partidos)} partidos de fase de zonas encontrados (jornadas {jornadas[0]} a {jornadas[-1]}).")
    print(f"  - Jugados    -> {n_jugados} escritos en {RESULTADOS_CSV}")
    print(f"  - Pendientes -> {n_pendientes} escritos en {FIXTURE_CSV}")
    print("\nOJO: esto pisa fixture_primerac.csv y resultados_primerac.csv enteros.")
    print("Es el modo correcto para el bootstrap inicial (primera vez). Para")
    print("actualizaciones incrementales de ahí en más, usar actualizar_resultados_primerac.py")
    print("en vez de correr este scraper directo.")


if __name__ == "__main__":
    main()
