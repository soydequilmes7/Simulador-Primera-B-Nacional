# -*- coding: utf-8 -*-
"""
scraper_promiedos_dimayor.py

Scraper de Promiedos para la Liga BetPlay Dimayor (Colombia), league id
"gca". Confirmado con una corrida real (ver historial del proyecto) que
Promiedos NO distingue Apertura de Clausura por el nombre de la fecha
-- las dos temporadas usan literalmente "Fecha 1".."Fecha 19" como
nombre. Lo que sí las distingue es la "key" de cada fecha:

    "{competition}_{edition}_{stage}_{jornada}"
    ej: "620_130_3_1"  -> stage 3, jornada 1
        "620_130_7_1"  -> stage 7, jornada 1

El número de "stage" cambia de temporada en temporada (esta vez fue 3
para Apertura y 7 para Clausura, con 4/5/6 = Cuartos/Semis/Final de los
playoffs del Apertura) -- por eso NO se hardcodea. En su lugar,
_detectar_stages() prueba la "Fecha 1" de cada stage candidato y usa el
estado de sus partidos: si ya están jugados -> es el Apertura (terminó);
si están programados a futuro -> es el Clausura (esta página empieza
ahí, como pide el reglamento).

Este scraper produce/actualiza 3 archivos en datos/:
  - fixture_dimayor.csv      Clausura, partidos pendientes (motor de simulación)
  - resultados_dimayor.csv   Clausura, partidos ya jugados (motor de simulación)
  - resultados_apertura_dimayor.csv
        Apertura, TODOS los partidos jugados de la fase de todos-contra-
        todos (19 fechas). Se usa para 2 cosas, ninguna pasa por el
        motor de simulación real:
          1) Sección informativa "Tabla Final del Torneo Apertura"
             (calcular_tabla_dimayor.construir_tabla_desde_resultados()).
          2) Calibración de ratings/racha mientras el Clausura tiene 0
             partidos jugados (ver EstadisticasDimayor.cargar_datos_dimayor()).
        NO incluye los playoffs del Apertura (Cuartos/Semis/Final) --
        la "tabla final" que pide el reglamento es la clasificación de
        la fase de todos-contra-todos, no el resultado de una
        eliminación directa.

Uso:
    python scraper_promiedos_dimayor.py

Uso programático:
    from scraper_promiedos_dimayor import obtener_partidos_jugados_dimayor
    partidos = obtener_partidos_jugados_dimayor()
"""
import csv
import json
import os
import ssl
import time
import urllib.error
import urllib.request

try:
    import rutas
except ImportError:
    rutas = None

if rutas is not None:
    DATOS_DIR = str(rutas.datos_dir())
else:
    DATOS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datos")

BASE_URL = "https://api.promiedos.com.ar"
LEAGUE_ID = "gca"  # Liga BetPlay Dimayor (Colombia)
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

FIXTURE_CSV = os.path.join(DATOS_DIR, "fixture_dimayor.csv")
RESULTADOS_CSV = os.path.join(DATOS_DIR, "resultados_dimayor.csv")
RESULTADOS_APERTURA_CSV = os.path.join(DATOS_DIR, "resultados_apertura_dimayor.csv")

ESTADOS_JUGADO_ENUM = {3}
N_FECHAS_FASE_REGULAR = 19


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
    """Lista cruda de TODAS las fechas/etapas que Promiedos tenga
    publicadas bajo este league id -- Apertura, Clausura, playoffs,
    todo mezclado. Cada item es un dict {"name": ..., "key": ...},
    salvo la primera "Fecha 1" de la etapa seleccionada por default en
    la web, que además trae "games" ya adentro."""
    data = _get_json(f"/league/tables_and_fixtures/{LEAGUE_ID}")
    filtros = data["games"]["filters"]
    return [f for f in filtros if f["key"] != "latest"]


def _stage_de_key(key: str):
    """"620_130_3_1" -> stage="3", jornada=1. None si la key no tiene
    el formato esperado (4 segmentos, último numérico)."""
    partes = key.split("_")
    if len(partes) != 4:
        return None, None
    stage, jornada_str = partes[2], partes[3]
    if not jornada_str.lstrip("-").isdigit():
        return None, None
    return stage, int(jornada_str)


def _agrupar_fechas_por_stage(fechas):
    """Agrupa las fechas cuyo nombre es literalmente "Fecha N" (ignora
    "Cuartos de Final", "Semifinales", "Final", "Betplay Final", etc.)
    por su número de stage. Devuelve {stage: {jornada: fecha_dict}}."""
    grupos: dict[str, dict[int, dict]] = {}
    for f in fechas:
        if not f["name"].lower().startswith("fecha"):
            continue
        stage, jornada = _stage_de_key(f["key"])
        if stage is None or jornada < 1:
            continue
        grupos.setdefault(stage, {})[jornada] = f
    return grupos


def _detectar_stages(grupos: dict, verbose=True):
    """De los grupos de "Fecha N" encontrados, determina cuál stage es
    el Apertura (ya jugado) y cuál el Clausura (a futuro, sin jugar
    todavía) probando el estado de los partidos de su "Fecha 1".
    Devuelve (stage_apertura, stage_clausura); cualquiera de los dos
    puede ser None si no se pudo determinar con confianza."""
    candidatos = []  # (stage, n_jugados, n_total)
    for stage, fechas_stage in grupos.items():
        fecha1 = fechas_stage.get(1)
        if not fecha1:
            continue
        resp = _get_json(f"/league/games/{LEAGUE_ID}/{fecha1['key']}")
        juegos = resp.get("games", [])
        if not juegos:
            continue
        n_jugados = sum(1 for g in juegos if g.get("status", {}).get("enum") in ESTADOS_JUGADO_ENUM)
        candidatos.append((stage, n_jugados, len(juegos)))
        time.sleep(PAUSA_ENTRE_PEDIDOS)

    if verbose:
        print("  Stages con fechas de todos-contra-todos encontrados:")
        for stage, n_jugados, n_total in candidatos:
            print(f"    stage={stage}: Fecha 1 tiene {n_jugados}/{n_total} partido(s) jugado(s)")

    jugados_stages = [c for c in candidatos if c[1] == c[2] and c[2] > 0]
    futuros_stages = [c for c in candidatos if c[1] == 0]

    stage_apertura = max(jugados_stages, key=lambda c: int(c[0]))[0] if jugados_stages else None
    stage_clausura = min(futuros_stages, key=lambda c: int(c[0]))[0] if futuros_stages else None

    if verbose:
        print(f"  -> Apertura: stage {stage_apertura!r} | Clausura: stage {stage_clausura!r}")

    return stage_apertura, stage_clausura


def _parsear_partido(g, jornada):
    equipo_local = g["teams"][0]["name"]
    equipo_visitante = g["teams"][1]["name"]
    estado = g.get("status", {})

    goles_local = goles_visitante = None
    tiene_estado_jugado = estado.get("enum") in ESTADOS_JUGADO_ENUM
    if tiene_estado_jugado and "scores" in g and g["scores"][0] is not None and g["scores"][1] is not None:
        goles_local = int(g["scores"][0])
        goles_visitante = int(g["scores"][1])

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


def _obtener_partidos_de_stage(stage: str, fechas_stage: dict, verbose=True):
    """Trae todos los partidos (jugados y pendientes) de las fechas
    1..19 de un stage puntual."""
    partidos = []
    for jornada in range(1, N_FECHAS_FASE_REGULAR + 1):
        fecha = fechas_stage.get(jornada)
        if not fecha:
            if verbose:
                print(f"  [aviso] no se encontró la Fecha {jornada} para el stage {stage}")
            continue
        try:
            resp = _get_json(f"/league/games/{LEAGUE_ID}/{fecha['key']}")
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            if verbose:
                print(f"  Fecha {jornada}: ERROR ({e}), se saltea")
            continue

        juegos = resp.get("games", [])
        if verbose:
            print(f"  Fecha {jornada}: {len(juegos)} partido(s)")
        for g in juegos:
            partidos.append(_parsear_partido(g, jornada))
        time.sleep(PAUSA_ENTRE_PEDIDOS)

    partidos.sort(key=lambda p: (p["jornada"], p["fecha_hora"]))
    return partidos


def obtener_partidos_dimayor(verbose=True):
    """Detecta los stages de Apertura/Clausura y devuelve los partidos
    (jugados y pendientes) del stage de CLAUSURA únicamente -- el que
    alimenta al motor de simulación."""
    fechas = obtener_fechas_disponibles()
    grupos = _agrupar_fechas_por_stage(fechas)
    stage_apertura, stage_clausura = _detectar_stages(grupos, verbose=verbose)

    if stage_clausura is None:
        raise RuntimeError(
            "No se pudo detectar el stage del Torneo Clausura (no hay ningún grupo de "
            "\"Fecha N\" con partidos 100% a futuro todavía). Revisar "
            "obtener_fechas_disponibles() a mano -- puede que Promiedos ya haya arrancado "
            "el Clausura y este scraper necesite ajustarse."
        )

    if verbose:
        print(f"\nTrayendo partidos del Torneo Clausura (stage {stage_clausura})...")
    return _obtener_partidos_de_stage(stage_clausura, grupos[stage_clausura], verbose=verbose)


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


def obtener_partidos_jugados_dimayor():
    """Igual que obtener_partidos_dimayor(), pero solo los jugados, en
    el formato que espera actualizar_resultados_dimayor.py."""
    jugados = [p for p in obtener_partidos_dimayor(verbose=False) if p["jugado"]]
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


# ----------------------------------------------------------------------
# Torneo Apertura: NO se simula. Se guarda en un CSV aparte (no pasa
# por Supabase ni por el motor) para 2 usos: la sección informativa de
# "Tabla Final del Torneo Apertura" y la calibración de ratings/racha
# mientras el Clausura tiene 0 partidos jugados.
# ----------------------------------------------------------------------
def obtener_resultados_apertura_dimayor(verbose=True):
    """Devuelve TODOS los partidos jugados de la fase de
    todos-contra-todos del Torneo Apertura (19 fechas), en el mismo
    formato de fila que resultados_dimayor.csv. No incluye los
    playoffs del Apertura (Cuartos/Semis/Final)."""
    fechas = obtener_fechas_disponibles()
    grupos = _agrupar_fechas_por_stage(fechas)
    stage_apertura, _stage_clausura = _detectar_stages(grupos, verbose=verbose)

    if stage_apertura is None:
        raise RuntimeError(
            "No se pudo detectar el stage del Torneo Apertura (no hay ningún grupo de "
            "\"Fecha N\" con todos los partidos ya jugados)."
        )

    if verbose:
        print(f"\nTrayendo resultados del Torneo Apertura (stage {stage_apertura})...")
    partidos = _obtener_partidos_de_stage(stage_apertura, grupos[stage_apertura], verbose=verbose)
    return [p for p in partidos if p["jugado"]]


def escribir_csv_apertura(partidos_apertura, path=RESULTADOS_APERTURA_CSV):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["fecha", "jornada", "equipo_local", "equipo_visitante", "goles_local", "goles_visitante"])
        for p in partidos_apertura:
            writer.writerow(["", p["jornada"], p["equipo_local"], p["equipo_visitante"], p["goles_local"], p["goles_visitante"]])
    return len(partidos_apertura)


if __name__ == "__main__":
    print(f"Scrapeando Liga BetPlay Dimayor (league id: {LEAGUE_ID})...\n")

    fechas = obtener_fechas_disponibles()
    grupos = _agrupar_fechas_por_stage(fechas)
    stage_apertura, stage_clausura = _detectar_stages(grupos)

    print("\n--- Torneo Apertura (informativo + calibración) ---")
    if stage_apertura is not None:
        partidos_apertura = _obtener_partidos_de_stage(stage_apertura, grupos[stage_apertura])
        jugados_apertura = [p for p in partidos_apertura if p["jugado"]]
        n = escribir_csv_apertura(jugados_apertura)
        print(f"{n} partido(s) del Apertura -> {RESULTADOS_APERTURA_CSV}")
    else:
        print("No se pudo detectar el stage del Apertura -- resultados_apertura_dimayor.csv no se tocó.")

    print("\n--- Torneo Clausura (motor de simulación) ---")
    if stage_clausura is not None:
        partidos_clausura = _obtener_partidos_de_stage(stage_clausura, grupos[stage_clausura])
        n_jugados, n_pendientes = escribir_csvs(partidos_clausura)
        print(f"\n{n_jugados} partido(s) jugados -> {RESULTADOS_CSV}")
        print(f"{n_pendientes} partido(s) pendientes -> {FIXTURE_CSV}")
    else:
        print("No se pudo detectar el stage del Clausura -- fixture_dimayor.csv/resultados_dimayor.csv no se tocaron.")

    equipos_vistos = set()
    for p in (partidos_apertura if stage_apertura is not None else []):
        equipos_vistos.add(p["equipo_local"])
        equipos_vistos.add(p["equipo_visitante"])
    if equipos_vistos:
        print(f"\n{len(equipos_vistos)} equipo(s) únicos vistos en el Apertura:")
        for nombre in sorted(equipos_vistos):
            print(f"  - {nombre}")
