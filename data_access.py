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
