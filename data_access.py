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
        }[competition_slug]
        return tuple(pd.read_csv(_csv_path(nombre)) for nombre in nombres)

    from db.repository import bootstrap_league_from_csv, repository

    if competition_slug == "primerac":
        bootstrap_league_from_csv("primerac")

    return repository().league_data(competition_slug)


def scorer_totals_df(competition_slug: str = "nacional") -> pd.DataFrame:
    if usando_pyodide():
        path = _csv_path("goleadores.csv")
        return pd.read_csv(path) if path.exists() else pd.DataFrame(columns=["jugador", "equipo", "goles"])

    from db.repository import repository

    return repository().scorer_totals_df(competition_slug)


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
