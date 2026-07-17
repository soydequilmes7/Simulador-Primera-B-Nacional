# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import pandas as pd

import rutas


def usando_pyodide() -> bool:
    return sys.platform == "emscripten"


def _csv_path(nombre: str) -> Path:
    return rutas.datos_dir() / nombre


def league_data(competition_slug: str):
    if usando_pyodide():
        nombres = {
            "nacional": ("resultados.csv", "fixture.csv", "tabla.csv"),
            "lpf": ("resultados_lpf.csv", "fixture_lpf.csv", "tablalpf.csv"),
            "bmetro": ("resultados_bmetro.csv", "fixture_bmetro.csv", "tabla_bmetro.csv"),
            "federal_a": ("resultados_federal_a.csv", "fixture_federal_a.csv", "tabla_federal_a.csv"),
            "primerac": ("resultados_primerac.csv", "fixture_primerac.csv", "tabla_primerac.csv"),
            "ligapro": ("resultados_ligapro.csv", "fixture_ligapro.csv", "tabla_ligapro.csv"),
        }[competition_slug]
        return tuple(pd.read_csv(_csv_path(nombre)) for nombre in nombres)

    from db.repository import bootstrap_league_from_csv, repository

    if competition_slug == "primerac":
        bootstrap_league_from_csv("primerac")
    if competition_slug == "ligapro":
        bootstrap_league_from_csv("ligapro")

    return repository().league_data(competition_slug)


def scorer_totals_df(competition_slug: str = "nacional") -> pd.DataFrame:
    if usando_pyodide():
        path = _csv_path("goleadores.csv")
        return pd.read_csv(path) if path.exists() else pd.DataFrame(columns=["jugador", "equipo", "goles"])

    from db.repository import repository

    return repository().scorer_totals_df(competition_slug)


def club_ratings_by_names(names: list[str]) -> dict[str, dict]:
    if usando_pyodide():
        return {}

    from db.repository import repository

    return repository().club_ratings_by_names(names)


def lpf_average_history_df() -> pd.DataFrame:
    if usando_pyodide():
        return pd.read_csv(_csv_path("promedios_lpf.csv"))

    from db.repository import repository

    return repository().lpf_average_history_df()


def cup_records() -> list[dict]:
    if usando_pyodide():
        with open(_csv_path("copa_argentina.csv"), encoding="utf-8") as f:
            return list(csv.DictReader(f))

    from db.repository import repository

    return repository().cup_records()


def save_simulation_output(key: str, competition_slug: str, payload: dict, n_simulaciones: int | None = None) -> None:
    if usando_pyodide():
        return

    from db.repository import repository

    repository().save_simulation_output(key, competition_slug, payload, n_simulaciones)


def simulation_output(key: str) -> dict | None:
    """Lee el último payload persistido en Supabase para `key` (mismo
    patrón que ya usaban campeon_apertura_lpf()/playoffs_apertura_lpf()
    para sus propias claves). Uso genérico: sirve para que los
    endpoints GET /api/estado-<liga> devuelvan a la página, al cargar,
    el mismo estado que quedó guardado la última vez que se corrió una
    simulación o una actualización -- en vez del snapshot estático
    data*.json, que nunca se reescribe en producción y por eso
    "revierte" al hacer F5 después de actualizar resultados.

    Devuelve None si todavía no hay nada guardado para esa clave (ej.
    deploy nuevo contra una base recién sembrada) o si estamos en
    Pyodide (no hay Supabase desde el navegador) -- el caller debe
    caer al snapshot estático en ese caso, no romper."""
    if usando_pyodide():
        return None

    from db.repository import repository

    return repository().simulation_output(key)


# ---------------------------------------------------------------------
# PLAN_ADDENDUM_ETAPA6_APERTURA_LPF, punto 4: CAMPEON_APERTURA dinámico
# de LPF, persistido con el mismo patrón que save_simulation_output()/
# simulation_output() (tabla simulation_outputs, confirmado real en
# db/repository.py -- ya existía el read, no hubo que inventarlo).
# ---------------------------------------------------------------------
_CLAVE_CAMPEON_APERTURA_LPF = "lpf_campeon_apertura"


def guardar_campeon_apertura_lpf(campeon: str) -> None:
    """Persiste el campeón del Apertura simulado de LPF. En Pyodide no
    hace nada (mismo comportamiento que save_simulation_output(): no
    hay forma de persistir desde el navegador) -- quien llama desde el
    backend (season/history_manager.py) es el único caller esperado."""
    if usando_pyodide():
        return

    from db.repository import repository

    repository().save_simulation_output(_CLAVE_CAMPEON_APERTURA_LPF, "lpf", {"campeon": campeon})


def campeon_apertura_lpf() -> str | None:
    """Lee el campeón del Apertura simulado de LPF, si hay uno
    guardado. Devuelve None si no hay nada (temporada legacy, o
    Pyodide sin el archivo todavía -- ver PENDIENTE más abajo), y el
    caller (estadisticas_lpf.py) cae al CAMPEON_APERTURA="Belgrano"
    hardcodeado -- el flujo 2026 no se toca ni se rompe.

    PENDIENTE (ver PLAN_ADDENDUM_ETAPA6_APERTURA_LPF, "pendientes
    explícitos"): falta el cambio en servidor.py para que el endpoint
    que arma los archivos que lee el Web Worker sirva también
    campeon_apertura_lpf.json, con el mismo patrón que ya existe para
    promedios_lpf.csv. Hasta que eso exista, esta rama de Pyodide
    siempre devuelve None (no hay forma de que el archivo exista en el
    filesystem virtual), y el Web Worker sigue viendo "Belgrano" -- no
    es un bug nuevo, es el mismo comportamiento de hoy."""
    if usando_pyodide():
        path = _csv_path("campeon_apertura_lpf.json")
        if not path.exists():
            return None
        import json
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("campeon")

    from db.repository import repository

    payload = repository().simulation_output(_CLAVE_CAMPEON_APERTURA_LPF)
    return payload.get("campeon") if payload else None


# ---------------------------------------------------------------------
# Bracket REAL de los playoffs del Apertura simulado (mismo patrón que
# CAMPEON_APERTURA arriba). Antes este dato se descartaba adentro de
# EstadisticasLPF.simular_apertura_desde_carryover() (un `_` se comía
# el detalle completo), así que Modo Temporada nunca tenía forma de
# mostrar el cuadro real que definió el campeón del Apertura para las
# temporadas hipotéticas (ronda 2 en adelante) -- BUG REPORTADO: "no
# muestra el bracket del Apertura, solo el del Clausura". No confundir
# con EstadisticasLPF.simular_playoffs_apertura(), que arma un cuadro
# FICTICIO/ilustrativo aparte (ese sigue existiendo, para la ronda 1 /
# temporada real 2026, donde no hay bracket real que guardar).
# ---------------------------------------------------------------------
_CLAVE_PLAYOFFS_APERTURA_LPF = "lpf_playoffs_apertura"


# ---------------------------------------------------------------------
# Etapa 12 (fix "calendario real" de clasificación continental, ver
# season/season_engine.py::correr_temporada(), parámetro
# `plazas_diferidas`): cupos de Copa Libertadores/Copa Sudamericana
# calculados al CIERRE de una temporada, que hay que arrastrar a la
# corrida de la temporada SIGUIENTE (que es la que efectivamente los
# juega). Mismo patrón save_simulation_output()/simulation_output() de
# arriba, clave por temporada de PARTICIPACIÓN (no de clasificación),
# para que /api/season/generate-next (que no encadena estado propio
# entre llamadas, a diferencia de /api/season/play) pueda leer/escribir
# esto entre una corrida y la siguiente sin depender de que el cliente
# se lo mande de vuelta.
# ---------------------------------------------------------------------
def _clave_plazas_diferidas(temporada_participacion: str) -> str:
    return f"plazas_diferidas_continental:{temporada_participacion}"


def guardar_plazas_diferidas_continental(temporada_participacion: str, plazas: dict) -> None:
    """Persiste los cupos de Libertadores/Sudamericana que acaban de
    calcularse al cierre de una temporada, indexados por la temporada
    en la que EFECTIVAMENTE se van a jugar (temporada_participacion =
    temporada_clasificacion + 1). En Pyodide no hace nada, mismo
    criterio que guardar_campeon_apertura_lpf()."""
    if usando_pyodide():
        return

    from db.repository import repository

    repository().save_simulation_output(
        _clave_plazas_diferidas(temporada_participacion), "lpf", plazas,
    )


def plazas_diferidas_continental(temporada_participacion: str) -> dict | None:
    """Lee los cupos diferidos guardados para que los juegue la
    temporada `temporada_participacion`. None si no hay nada guardado
    (ej. la primera temporada de una cadena, sin "temporada anterior"
    de Modo Temporada de la cual arrastrar clasificados) -- el caller
    (SeasonEngine.correr_temporada(plazas_diferidas=...)) debe degradar
    a NO correr Libertadores/Sudamericana en vez de adivinar con los
    clasificados de la temporada equivocada."""
    if usando_pyodide():
        return None

    from db.repository import repository

    return repository().simulation_output(_clave_plazas_diferidas(temporada_participacion))


def guardar_playoffs_apertura_lpf(detalle_playoffs: dict) -> None:
    """Persiste el cuadro REAL de playoffs que definió el campeón del
    Apertura simulado de LPF (octavos/cuartos/semis/final, mismo shape
    que jugar_playoffs()). En Pyodide no hace nada, mismo criterio que
    guardar_campeon_apertura_lpf()."""
    if usando_pyodide():
        return

    from db.repository import repository

    repository().save_simulation_output(_CLAVE_PLAYOFFS_APERTURA_LPF, "lpf", detalle_playoffs)


def playoffs_apertura_lpf() -> dict | None:
    """Lee el cuadro REAL de playoffs del Apertura simulado, si hay
    uno guardado. Devuelve None si no hay nada (temporada legacy, o
    todavía no se corrió ningún avance de temporada que lo haya
    guardado) -- el caller (main_lpf.py) cae de vuelta al cuadro
    FICTICIO de simular_playoffs_apertura(), mismo comportamiento de
    siempre para ese caso."""
    if usando_pyodide():
        path = _csv_path("playoffs_apertura_lpf.json")
        if not path.exists():
            return None
        import json
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    from db.repository import repository

    return repository().simulation_output(_CLAVE_PLAYOFFS_APERTURA_LPF)
