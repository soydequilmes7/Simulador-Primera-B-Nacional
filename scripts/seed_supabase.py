#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db.repository import COMPETITIONS, transaction
from mapeo_equipos import OVERRIDES as NACIONAL_ALIASES
from mapeo_equipos_federal import OVERRIDES as FEDERAL_ALIASES
from modelos.estadisticas_lpf import NORMALIZACION_NOMBRES

DATOS = ROOT / "datos"

LEAGUE_FILES = {
    "nacional": {
        "tabla": "tabla.csv",
        "fixture": "fixture.csv",
        "resultados": "resultados.csv",
    },
    "lpf": {
        "tabla": "tablalpf.csv",
        "fixture": "fixture_lpf.csv",
        "resultados": "resultados_lpf.csv",
    },
    "bmetro": {
        "tabla": "tabla_bmetro.csv",
        "fixture": "fixture_bmetro.csv",
        "resultados": "resultados_bmetro.csv",
    },
    "federal_a": {
        "tabla": "tabla_federal_a.csv",
        "fixture": "fixture_federal_a.csv",
        "resultados": "resultados_federal_a.csv",
    },
}


def read_csv(name: str) -> list[dict]:
    path = DATOS / name
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ensure_base(repo):
    print("Sembrando competitions/seasons...", flush=True)
    for spec in COMPETITIONS.values():
        repo._execute(
            """
            insert into competitions (slug, name) values (%s, %s)
            on conflict (slug) do update set name = excluded.name
            """,
            (spec.slug, spec.name),
        )
        repo._execute(
            """
            insert into seasons (competition_slug, name, year, active)
            values (%s, %s, %s, true)
            on conflict (competition_slug, name) do update set
                year = excluded.year,
                active = true
            """,
            (spec.slug, spec.season, int(spec.season)),
        )


def seed_leagues(repo):
    for slug, files in LEAGUE_FILES.items():
        tabla = read_csv(files["tabla"])
        fixture = read_csv(files["fixture"])
        resultados = [row for row in read_csv(files["resultados"]) if row]
        print(
            f"Sembrando {slug}: standings={len(tabla)}, fixture={len(fixture)}, resultados={len(resultados)}",
            flush=True,
        )
        repo.upsert_standings(slug, tabla)
        print(f"  {slug}: standings OK", flush=True)
        seed_matches(repo, slug, fixture, resultados)
        print(f"  {slug}: matches OK", flush=True)


def seed_matches(repo, slug: str, pending: list[dict], played: list[dict]) -> None:
    season_id = repo.season_id(slug)
    repo._execute(
        "delete from matches where competition_slug = %s and season_id = %s",
        (slug, season_id),
    )
    total = len(pending) + len(played)
    done = 0
    for row in pending:
        repo.upsert_match(slug, row, "pending")
        done += 1
        if done % 100 == 0:
            print(f"    {slug}: {done}/{total} partidos", flush=True)
    for row in played:
        repo.upsert_match(slug, row, "played")
        done += 1
        if done % 100 == 0 or done == total:
            print(f"    {slug}: {done}/{total} partidos", flush=True)


def seed_scorers(repo):
    rows = read_csv("goleadores.csv")
    print(f"Sembrando goleadores: {len(rows)} filas", flush=True)
    for i, row in enumerate(rows, start=1):
        player_id = repo.ensure_player(row["jugador"])
        team_id = repo.ensure_team(row["equipo"])
        season_id = repo.season_id("nacional")
        repo._execute(
            """
            insert into scorer_totals (competition_slug, season_id, player_id, team_id, goles, updated_at)
            values ('nacional', %s, %s, %s, %s, now())
            on conflict (competition_slug, season_id, player_id, team_id) do update set
                goles = excluded.goles,
                updated_at = now()
            """,
            (season_id, player_id, team_id, int(row["goles"])),
        )
        if i % 100 == 0 or i == len(rows):
            print(f"  goleadores: {i}/{len(rows)}", flush=True)


def seed_lpf_averages(repo):
    season_id = repo.season_id("lpf")
    rows = read_csv("promedios_lpf.csv")
    print(f"Sembrando promedios LPF: {len(rows)} filas", flush=True)
    for row in rows:
        team_id = repo.ensure_team(row["equipo"])
        repo._execute(
            """
            insert into lpf_average_history (season_id, team_id, puntos_historicos, partidos_historicos)
            values (%s, %s, %s, %s)
            on conflict (season_id, team_id) do update set
                puntos_historicos = excluded.puntos_historicos,
                partidos_historicos = excluded.partidos_historicos
            """,
            (season_id, team_id, int(row["puntos_historicos"]), int(row["partidos_historicos"])),
        )


def seed_copa(repo):
    rows = read_csv("copa_argentina.csv")
    print(f"Sembrando Copa Argentina: {len(rows)} cruces", flush=True)
    for row in rows:
        repo.upsert_cup_match(row)


def seed_aliases(repo):
    print("Sembrando alias de equipos...", flush=True)
    for team, aliases in NACIONAL_ALIASES.items():
        seed_alias_list(repo, "nacional", team, aliases)
    for team, aliases in FEDERAL_ALIASES.items():
        seed_alias_list(repo, "federal_a", team, aliases)
    for alias, canonical in NORMALIZACION_NOMBRES.items():
        seed_alias_list(repo, "lpf", canonical, [alias])


def seed_alias_list(repo, competition_slug: str, team_name: str, aliases: list[str]):
    team_id = repo.ensure_team(team_name)
    for alias in aliases:
        repo._execute(
            """
            insert into team_aliases (team_id, competition_slug, alias, source)
            values (%s, %s, %s, 'seed')
            on conflict (competition_slug, alias) do update set
                team_id = excluded.team_id,
                source = excluded.source
            """,
            (team_id, competition_slug, alias),
        )


def main():
    with transaction() as repo:
        repo._execute("set local lock_timeout = '15s'")
        repo._execute("set local statement_timeout = '120s'")
        ensure_base(repo)
        seed_leagues(repo)
        seed_scorers(repo)
        seed_lpf_averages(repo)
        seed_copa(repo)
        seed_aliases(repo)
    print("Seed Supabase completo.", flush=True)


if __name__ == "__main__":
    main()
