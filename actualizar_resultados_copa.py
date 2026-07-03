# -*- coding: utf-8 -*-
"""
actualizar_resultados_copa.py

Actualiza datos/copa_argentina.csv con los resultados reales de la Copa
Argentina desde la API de Promiedos (LEAGUE_ID "gea", el de
promiedos.com.ar/league/copa-argentina/gea) y opcionalmente re-simula.

Cómo funciona el merge:
  1. Trae TODOS los partidos terminados de /league/games/gea/latest.
  2. Con el cuadro actual arma qué cruces están pendientes o son
     derivables (el ganador de las llaves 2k-1 y 2k juega la llave k de
     la ronda siguiente): si Promiedos tiene un partido terminado entre
     ese par de equipos, se completa la fila (o se agrega si es de una
     ronda que todavía no estaba en el CSV).
  3. En empates intenta leer el ganador por penales de los campos que
     expone la API (nombres tolerantes: penalties/penalty_score/scores
     extendidos). Si no lo encuentra, deja el cruce con goles pero sin
     ganador: el simulador lo resuelve por penales simulados y el log
     lo reporta para completarlo a mano.

Uso manual:      python actualizar_resultados_copa.py
Programático:    from actualizar_resultados_copa import actualizar
                 actualizar(correr_simulacion_fn=correr_simulacion_copa)
"""
import csv
import json
import urllib.request
from datetime import datetime

import rutas
from modelos.estadisticas_copa import RONDAS, LLAVES_POR_RONDA

BASE_URL = "https://api.promiedos.com.ar"
LEAGUE_ID = "gea"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Accept-Language": "es-AR,es;q=0.9",
    "Referer": "https://www.promiedos.com.ar/league/copa-argentina/gea",
    "Origin": "https://www.promiedos.com.ar",
}
TIMEOUT = 20
CAMPOS = ["ronda", "llave", "equipo_local", "equipo_visitante",
          "goles_local", "goles_visitante", "ganador"]

# Promiedos a veces nombra distinto que su propio cuadro; alias mínimos.
NORMALIZACION = {}


def _get_json(path):
    req = urllib.request.Request(f"{BASE_URL}{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def obtener_partidos_copa():
    """Partidos TERMINADOS de la Copa según Promiedos, como lista de dicts
    {local, visitante, goles_local, goles_visitante, ganador|None}."""
    data = _get_json(f"/league/games/{LEAGUE_ID}/latest")
    partidos = []
    for g in data.get("games", []):
        estado = g.get("status", {})
        if estado.get("enum") != 3:  # 3 = terminado (incluye penales/alargue)
            continue
        local = NORMALIZACION.get(g["teams"][0]["name"], g["teams"][0]["name"])
        visitante = NORMALIZACION.get(g["teams"][1]["name"], g["teams"][1]["name"])
        goles_local, goles_visitante = int(g["scores"][0]), int(g["scores"][1])

        ganador = None
        if goles_local != goles_visitante:
            ganador = local if goles_local > goles_visitante else visitante
        else:
            ganador = _ganador_por_penales(g, local, visitante)

        partidos.append({
            "local": local, "visitante": visitante,
            "goles_local": goles_local, "goles_visitante": goles_visitante,
            "ganador": ganador,
        })
    return partidos


def _ganador_por_penales(g, local, visitante):
    """Best-effort: busca el score de penales en las variantes de campo
    que se han visto en esta API. Devuelve None si no aparece."""
    for clave in ("penalties", "penalty_score", "penalty_scores", "pen_scores"):
        valor = g.get(clave)
        if isinstance(valor, (list, tuple)) and len(valor) == 2:
            try:
                p_local, p_visitante = int(valor[0]), int(valor[1])
            except (TypeError, ValueError):
                continue
            if p_local != p_visitante:
                return local if p_local > p_visitante else visitante
    # Algunas respuestas traen scores extendidos: [gl, gv, pl, pv]
    scores = g.get("scores", [])
    if len(scores) >= 4:
        try:
            p_local, p_visitante = int(scores[2]), int(scores[3])
            if p_local != p_visitante:
                return local if p_local > p_visitante else visitante
        except (TypeError, ValueError):
            pass
    if g.get("winner") in (1, 2):
        return local if g["winner"] == 1 else visitante
    return None


def actualizar(n_sims=1000, correr_simulacion_fn=None, imprimir=True):
    """Merge de resultados reales sobre copa_argentina.csv. Devuelve dict
    {actualizado, cargados, sin_ganador, datos} (mismo contrato que los
    actualizadores de Nacional y LPF)."""
    ruta_csv = rutas.datos_dir() / "copa_argentina.csv"
    with open(ruta_csv, encoding="utf-8") as f:
        cuadro = list(csv.DictReader(f))

    if imprimir:
        print("Consultando Promiedos (Copa Argentina)...")
    partidos = obtener_partidos_copa()
    jugados = {frozenset((p["local"], p["visitante"])): p for p in partidos}

    filas = {(c["ronda"], int(c["llave"])): c for c in cuadro}
    cargados, sin_ganador = [], []

    ganadores_previos = {}
    for ronda_i, ronda in enumerate(RONDAS):
        ganadores = {}
        for llave in range(1, LLAVES_POR_RONDA[ronda] + 1):
            fila = filas.get((ronda, llave))

            if fila is None or not fila["equipo_local"]:
                # Cruce derivable del árbol: ganadores de 2k-1 y 2k.
                local = ganadores_previos.get(2 * llave - 1)
                visitante = ganadores_previos.get(2 * llave)
                if not local or not visitante:
                    continue  # todavía no están los dos clasificados
                if fila is None:
                    fila = {"ronda": ronda, "llave": str(llave),
                            "equipo_local": local, "equipo_visitante": visitante,
                            "goles_local": "", "goles_visitante": "", "ganador": ""}
                    filas[(ronda, llave)] = fila
                else:
                    fila["equipo_local"], fila["equipo_visitante"] = local, visitante

            if not fila["ganador"]:
                p = jugados.get(frozenset((fila["equipo_local"], fila["equipo_visitante"])))
                if p:
                    invertido = p["local"] != fila["equipo_local"]
                    fila["goles_local"] = p["goles_visitante"] if invertido else p["goles_local"]
                    fila["goles_visitante"] = p["goles_local"] if invertido else p["goles_visitante"]
                    fila["ganador"] = p["ganador"] or ""
                    cargados.append(f"{ronda}: {fila['equipo_local']} {fila['goles_local']}-"
                                    f"{fila['goles_visitante']} {fila['equipo_visitante']}")
                    if not p["ganador"]:
                        sin_ganador.append(f"{ronda} llave {llave}: empate sin ganador por penales detectable")

            if fila["ganador"]:
                ganadores[llave] = fila["ganador"]
        ganadores_previos = ganadores

    if not cargados:
        if imprimir:
            print("  No hay resultados nuevos de Copa.")
        return {"actualizado": False, "cargados": [], "sin_ganador": sin_ganador,
                "mensaje": "No había cruces nuevos terminados."}

    orden = {r: i for i, r in enumerate(RONDAS)}
    filas_ordenadas = sorted(filas.values(), key=lambda f: (orden[f["ronda"]], int(f["llave"])))
    with open(ruta_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS)
        writer.writeheader()
        writer.writerows(filas_ordenadas)

    if imprimir:
        print(f"  Cargados {len(cargados)} resultado(s) nuevo(s) de Copa.")
        for aviso in sin_ganador:
            print(f"  AVISO: {aviso} — completá 'ganador' a mano en copa_argentina.csv")

    datos = None
    if correr_simulacion_fn is not None:
        guardar_json = True
        try:
            guardar_json = not rutas.en_vercel()
        except AttributeError:
            pass
        datos = correr_simulacion_fn(n_sims=n_sims, imprimir=imprimir, guardar_json=guardar_json)

    _guardar_log(cargados, sin_ganador)
    return {"actualizado": True, "cargados": cargados, "sin_ganador": sin_ganador, "datos": datos}


def _guardar_log(cargados, sin_ganador):
    ruta = rutas.datos_dir() / "log_actualizaciones_copa.json"
    try:
        historial = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else []
    except (json.JSONDecodeError, OSError):
        historial = []
    historial.append({"timestamp": datetime.now().isoformat(timespec="seconds"),
                      "cargados": cargados, "sin_ganador": sin_ganador})
    ruta.write_text(json.dumps(historial[-50:], ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    from main_copa import correr_simulacion_copa
    actualizar(correr_simulacion_fn=correr_simulacion_copa)
