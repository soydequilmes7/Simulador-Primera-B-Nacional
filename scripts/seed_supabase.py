#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

import psycopg

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
    "primerac": {
        "tabla": "tabla_primerac.csv",
        "fixture": "fixture_primerac.csv",
        "resultados": "resultados_primerac.csv",
    },
    "brasileirao": {
        "tabla": "tabla_brasileirao.csv",
        "fixture": "fixture_brasileirao.csv",
        "resultados": "resultados_brasileirao.csv",
    },
    "dimayor": {
        "tabla": "tabla_dimayor.csv",
        "fixture": "fixture_dimayor.csv",
        "resultados": "resultados_dimayor.csv",
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


def seed_one_league(repo, slug: str, files: dict) -> None:
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


def _con_reintentos(descripcion: str, intentos: int, fn) -> None:
    """Reintenta `fn()` (una tanda de trabajo dentro de su PROPIA
    transacción/conexión nueva) ante caídas de conexión transitorias
    con Supabase -- 'server closed the connection unexpectedly'/
    'the connection is lost' suelen ser el pooler cortando una sesión
    que viene abierta hace rato, no un error de los datos. Reintentar
    con una conexión NUEVA (transaction() se vuelve a llamar adentro de
    fn) resuelve la gran mayoría. Si se agotan los intentos, se
    relanza el error real para no ocultar un problema de verdad."""
    for intento in range(1, intentos + 1):
        try:
            fn()
            return
        except psycopg.OperationalError as e:
            if intento == intentos:
                raise
            espera = 3 * intento
            print(
                f"  {descripcion}: se cortó la conexión ({e}). "
                f"Reintentando en {espera}s (intento {intento + 1}/{intentos})...",
                flush=True,
            )
            time.sleep(espera)


def _set_timeouts(repo) -> None:
    repo._execute("set local lock_timeout = '15s'")
    repo._execute("set local statement_timeout = '120s'")


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
        team_id = repo.ensure_team(row["equipo"], "nacional")
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
        team_id = repo.ensure_team(row["equipo"], "lpf")
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


def seed_dimayor_averages(repo):
    """Igual que seed_lpf_averages() pero para dimayor_average_history
    (ver migración 003_dimayor_average_history.sql). Valores 2024+2025
    completos en datos/promedios_dimayor.csv -- el 2026 en curso NO se
    siembra acá, se suma en caliente en calcular_tabla_promedios()."""
    season_id = repo.season_id("dimayor")
    rows = read_csv("promedios_dimayor.csv")
    print(f"Sembrando promedios Dimayor: {len(rows)} filas", flush=True)
    for row in rows:
        team_id = repo.ensure_team(row["equipo"], "dimayor")
        repo._execute(
            """
            insert into dimayor_average_history (season_id, team_id, puntos_historicos, partidos_historicos)
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
    team_id = repo.ensure_team(team_name, competition_slug)
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
    def _base():
        with transaction() as repo:
            _set_timeouts(repo)
            ensure_base(repo)

    _con_reintentos("competitions/seasons", 3, _base)
    print("Base (competitions/seasons) OK.", flush=True)

    for slug, files in LEAGUE_FILES.items():
        def _liga(slug=slug, files=files):
            with transaction() as repo:
                _set_timeouts(repo)
                seed_one_league(repo, slug, files)

        _con_reintentos(slug, 3, _liga)

    def _resto():
        with transaction() as repo:
            _set_timeouts(repo)
            seed_scorers(repo)
            seed_lpf_averages(repo)
            seed_dimayor_averages(repo)
            seed_copa(repo)
            seed_aliases(repo)

    _con_reintentos("goleadores/promedios/copa/alias", 3, _resto)
    print("Seed Supabase completo.", flush=True)


if __name__ == "__main__":
    main()
