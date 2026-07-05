# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import io
import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

import pandas as pd
from psycopg.types.json import Jsonb

from db.client import get_connection

MATCH_COLUMNS = ["fecha", "jornada", "equipo_local", "equipo_visitante"]
RESULT_COLUMNS = MATCH_COLUMNS + ["goles_local", "goles_visitante"]
STANDING_COLUMNS = [
    "zona", "posicion", "equipo", "partidos_jugados", "ganados",
    "empatados", "perdidos", "gf", "gc", "dg", "puntos",
]
SCORER_COLUMNS = ["jugador", "equipo", "goles"]
LPF_AVERAGE_COLUMNS = ["equipo", "puntos_historicos", "partidos_historicos"]
CUP_COLUMNS = ["ronda", "llave", "equipo_local", "equipo_visitante", "goles_local", "goles_visitante", "ganador"]


@dataclass(frozen=True)
class CompetitionSpec:
    slug: str
    name: str
    season: str = "2026"


COMPETITIONS = {
    "nacional": CompetitionSpec("nacional", "Primera Nacional"),
    "lpf": CompetitionSpec("lpf", "Liga Profesional"),
    "bmetro": CompetitionSpec("bmetro", "Primera B Metropolitana"),
    "federal_a": CompetitionSpec("federal_a", "Federal A"),
    "copa": CompetitionSpec("copa", "Copa Argentina"),
}

TABLE_FILE_SLUGS = {
    "tabla.csv": "nacional",
    "tablalpf.csv": "lpf",
    "tabla_bmetro.csv": "bmetro",
    "tabla_federal_a.csv": "federal_a",
}


def _records_to_df(records: list[dict], columns: list[str]) -> pd.DataFrame:
    df = pd.DataFrame(records, columns=columns)
    return df


def _empty_df(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def dataframe_to_csv(df: pd.DataFrame, columns: list[str]) -> str:
    out = io.StringIO()
    df.loc[:, columns].to_csv(out, index=False, lineterminator="\n")
    return out.getvalue()


def records_to_csv(records: list[dict], columns: list[str]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows([{c: row.get(c, "") for c in columns} for row in records])
    return out.getvalue()


class SimulatorRepository:
    def __init__(self, conn=None):
        self.conn = conn

    def _execute(self, query: str, params: Iterable[Any] | None = None):
        if self.conn is None:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    return cur.fetchall() if cur.description else []
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall() if cur.description else []

    def _execute_one(self, query: str, params: Iterable[Any] | None = None):
        rows = self._execute(query, params)
        return rows[0] if rows else None

    def season_id(self, competition_slug: str) -> int:
        row = self._execute_one(
            """
            select s.id
            from seasons s
            where s.competition_slug = %s and s.active = true
            order by s.id desc
            limit 1
            """,
            (competition_slug,),
        )
        if row is None:
            raise RuntimeError(f"No hay temporada activa para {competition_slug}")
        return int(row["id"])

    def league_data(self, competition_slug: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        return (
            self.matches_df(competition_slug, "played"),
            self.matches_df(competition_slug, "pending"),
            self.standings_df(competition_slug),
        )

    def matches_df(self, competition_slug: str, status: str) -> pd.DataFrame:
        season_id = self.season_id(competition_slug)
        rows = self._execute(
            """
            select coalesce(m.fecha, '') as fecha, m.jornada,
                   tl.name as equipo_local, tv.name as equipo_visitante,
                   m.goles_local, m.goles_visitante
            from matches m
            join teams tl on tl.id = m.equipo_local_id
            join teams tv on tv.id = m.equipo_visitante_id
            where m.competition_slug = %s and m.season_id = %s and m.status = %s
            order by m.jornada nulls last, m.fecha nulls last, m.id
            """,
            (competition_slug, season_id, status),
        )
        columns = RESULT_COLUMNS if status == "played" else MATCH_COLUMNS
        records = []
        for row in rows:
            item = {c: row.get(c) for c in columns}
            if item.get("fecha") is None:
                item["fecha"] = ""
            records.append(item)
        df = _records_to_df(records, columns)
        for col in ("jornada", "goles_local", "goles_visitante"):
            if col in df.columns and not df.empty:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("int64")
        return df

    def match_records(self, competition_slug: str, status: str) -> list[dict]:
        return self.matches_df(competition_slug, status).to_dict(orient="records")

    def standings_df(self, competition_slug: str) -> pd.DataFrame:
        season_id = self.season_id(competition_slug)
        rows = self._execute(
            """
            select st.zona, st.posicion, t.name as equipo, st.partidos_jugados,
                   st.ganados, st.empatados, st.perdidos, st.gf, st.gc, st.dg, st.puntos
            from standings st
            join teams t on t.id = st.team_id
            where st.competition_slug = %s and st.season_id = %s
            order by st.zona, st.posicion
            """,
            (competition_slug, season_id),
        )
        df = _records_to_df(rows, STANDING_COLUMNS)
        for col in STANDING_COLUMNS:
            if col not in ("zona", "equipo") and not df.empty:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("int64")
        return df

    def standing_records(self, competition_slug: str) -> list[dict]:
        return self.standings_df(competition_slug).to_dict(orient="records")

    def scorer_totals_df(self, competition_slug: str = "nacional") -> pd.DataFrame:
        season_id = self.season_id(competition_slug)
        rows = self._execute(
            """
            select p.name as jugador, t.name as equipo, st.goles
            from scorer_totals st
            join players p on p.id = st.player_id
            join teams t on t.id = st.team_id
            where st.competition_slug = %s and st.season_id = %s
            order by st.goles desc, p.name
            """,
            (competition_slug, season_id),
        )
        df = _records_to_df(rows, SCORER_COLUMNS)
        if not df.empty:
            df["goles"] = pd.to_numeric(df["goles"], errors="coerce").astype("int64")
        return df

    def lpf_average_history_df(self) -> pd.DataFrame:
        season_id = self.season_id("lpf")
        rows = self._execute(
            """
            select t.name as equipo, h.puntos_historicos, h.partidos_historicos
            from lpf_average_history h
            join teams t on t.id = h.team_id
            where h.season_id = %s
            order by t.name
            """,
            (season_id,),
        )
        df = _records_to_df(rows, LPF_AVERAGE_COLUMNS)
        for col in ("puntos_historicos", "partidos_historicos"):
            if not df.empty:
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("int64")
        return df

    def cup_records(self) -> list[dict]:
        season_id = self.season_id("copa")
        rows = self._execute(
            """
            select cm.ronda, cm.llave,
                   coalesce(tl.name, '') as equipo_local,
                   coalesce(tv.name, '') as equipo_visitante,
                   cm.goles_local, cm.goles_visitante,
                   coalesce(tg.name, '') as ganador
            from cup_matches cm
            left join teams tl on tl.id = cm.equipo_local_id
            left join teams tv on tv.id = cm.equipo_visitante_id
            left join teams tg on tg.id = cm.ganador_id
            where cm.competition_slug = 'copa' and cm.season_id = %s
            order by case cm.ronda
                when '32avos' then 1 when '16avos' then 2 when 'octavos' then 3
                when 'cuartos' then 4 when 'semis' then 5 when 'final' then 6
                else 99 end, cm.llave
            """,
            (season_id,),
        )
        records = []
        for row in rows:
            item = {c: row.get(c) for c in CUP_COLUMNS}
            for key in ("goles_local", "goles_visitante"):
                if item[key] is None:
                    item[key] = ""
            records.append(item)
        return records

    def upsert_standings(self, competition_slug: str, filas: list[dict]) -> None:
        season_id = self.season_id(competition_slug)
        for fila in filas:
            team_id = self.ensure_team(fila["equipo"])
            self._execute(
                """
                insert into standings (
                    competition_slug, season_id, zona, posicion, team_id,
                    partidos_jugados, ganados, empatados, perdidos, gf, gc, dg, puntos, updated_at
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                on conflict (competition_slug, season_id, team_id) do update set
                    zona = excluded.zona,
                    posicion = excluded.posicion,
                    partidos_jugados = excluded.partidos_jugados,
                    ganados = excluded.ganados,
                    empatados = excluded.empatados,
                    perdidos = excluded.perdidos,
                    gf = excluded.gf,
                    gc = excluded.gc,
                    dg = excluded.dg,
                    puntos = excluded.puntos,
                    updated_at = now()
                """,
                (
                    competition_slug, season_id, fila["zona"], int(fila["posicion"]), team_id,
                    int(fila["partidos_jugados"]), int(fila["ganados"]), int(fila["empatados"]),
                    int(fila["perdidos"]), int(fila["gf"]), int(fila["gc"]), int(fila["dg"]),
                    int(fila["puntos"]),
                ),
            )

    def replace_matches(self, competition_slug: str, pending: list[dict], played: list[dict]) -> None:
        season_id = self.season_id(competition_slug)
        self._execute(
            "delete from matches where competition_slug = %s and season_id = %s",
            (competition_slug, season_id),
        )
        for row in pending:
            self.upsert_match(competition_slug, row, "pending")
        for row in played:
            self.upsert_match(competition_slug, row, "played")

    def upsert_match(self, competition_slug: str, row: dict, status: str) -> None:
        season_id = self.season_id(competition_slug)
        local_id = self.ensure_team(row["equipo_local"])
        visitante_id = self.ensure_team(row["equipo_visitante"])
        self._execute(
            """
            insert into matches (
                competition_slug, season_id, fecha, jornada, equipo_local_id, equipo_visitante_id,
                goles_local, goles_visitante, status, updated_at
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            on conflict (competition_slug, season_id, jornada, equipo_local_id, equipo_visitante_id)
            do update set
                fecha = excluded.fecha,
                goles_local = excluded.goles_local,
                goles_visitante = excluded.goles_visitante,
                status = excluded.status,
                updated_at = now()
            """,
            (
                competition_slug, season_id, row.get("fecha") or "", int(row.get("jornada") or 0),
                local_id, visitante_id,
                _nullable_int(row.get("goles_local")), _nullable_int(row.get("goles_visitante")), status,
            ),
        )

    def add_scorer_goals(self, cargados: list[dict], competition_slug: str = "nacional") -> int:
        season_id = self.season_id(competition_slug)
        goles_sumados = 0
        for partido in cargados:
            for jugador, goles in partido.get("goleadores_local", {}).items():
                self._add_scorer_goal(season_id, competition_slug, jugador, partido["equipo_local"], int(goles))
                goles_sumados += int(goles)
            for jugador, goles in partido.get("goleadores_visitante", {}).items():
                self._add_scorer_goal(season_id, competition_slug, jugador, partido["equipo_visitante"], int(goles))
                goles_sumados += int(goles)
        return goles_sumados

    def _add_scorer_goal(self, season_id: int, competition_slug: str, jugador: str, equipo: str, goles: int) -> None:
        player_id = self.ensure_player(jugador)
        team_id = self.ensure_team(equipo)
        self._execute(
            """
            insert into scorer_totals (competition_slug, season_id, player_id, team_id, goles, updated_at)
            values (%s, %s, %s, %s, %s, now())
            on conflict (competition_slug, season_id, player_id, team_id)
            do update set goles = scorer_totals.goles + excluded.goles, updated_at = now()
            """,
            (competition_slug, season_id, player_id, team_id, goles),
        )

    def replace_cup_matches(self, rows: list[dict]) -> None:
        season_id = self.season_id("copa")
        self._execute("delete from cup_matches where competition_slug = 'copa' and season_id = %s", (season_id,))
        for row in rows:
            self.upsert_cup_match(row)

    def upsert_cup_match(self, row: dict) -> None:
        season_id = self.season_id("copa")
        local_id = self.ensure_team(row["equipo_local"]) if row.get("equipo_local") else None
        visitante_id = self.ensure_team(row["equipo_visitante"]) if row.get("equipo_visitante") else None
        ganador_id = self.ensure_team(row["ganador"]) if row.get("ganador") else None
        self._execute(
            """
            insert into cup_matches (
                competition_slug, season_id, ronda, llave, equipo_local_id, equipo_visitante_id,
                goles_local, goles_visitante, ganador_id, updated_at
            )
            values ('copa', %s, %s, %s, %s, %s, %s, %s, %s, now())
            on conflict (competition_slug, season_id, ronda, llave) do update set
                equipo_local_id = excluded.equipo_local_id,
                equipo_visitante_id = excluded.equipo_visitante_id,
                goles_local = excluded.goles_local,
                goles_visitante = excluded.goles_visitante,
                ganador_id = excluded.ganador_id,
                updated_at = now()
            """,
            (
                season_id, row["ronda"], int(row["llave"]), local_id, visitante_id,
                _nullable_int(row.get("goles_local")), _nullable_int(row.get("goles_visitante")), ganador_id,
            ),
        )

    def log_update(
        self,
        competition_slug: str,
        cargados: list | None = None,
        sin_matchear: list | None = None,
        simulacion_corrida: bool = False,
        metadata: dict | None = None,
        timestamp: str | None = None,
    ) -> None:
        season_id = self.season_id(competition_slug)
        started_at = datetime.fromisoformat(timestamp) if timestamp else datetime.now()
        self._execute(
            """
            insert into update_runs (
                competition_slug, season_id, started_at, partidos_cargados, sin_matchear,
                simulacion_corrida, metadata
            )
            values (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                competition_slug, season_id, started_at,
                Jsonb(cargados or []), Jsonb(sin_matchear or []), simulacion_corrida, Jsonb(metadata or {}),
            ),
        )

    def save_simulation_output(self, key: str, competition_slug: str, payload: dict, n_simulaciones: int | None = None) -> None:
        season_id = self.season_id(competition_slug)
        self._execute(
            """
            insert into simulation_outputs (key, competition_slug, season_id, n_simulaciones, payload, generated_at)
            values (%s, %s, %s, %s, %s, now())
            on conflict (key) do update set
                competition_slug = excluded.competition_slug,
                season_id = excluded.season_id,
                n_simulaciones = excluded.n_simulaciones,
                payload = excluded.payload,
                generated_at = now()
            """,
            (key, competition_slug, season_id, n_simulaciones, Jsonb(payload)),
        )

    def simulation_output(self, key: str) -> dict | None:
        row = self._execute_one("select payload from simulation_outputs where key = %s", (key,))
        return row["payload"] if row else None

    def ensure_team(self, name: str) -> int:
        row = self._execute_one(
            """
            insert into teams (name) values (%s)
            on conflict (name) do update set name = excluded.name
            returning id
            """,
            (name,),
        )
        return int(row["id"])

    def ensure_player(self, name: str) -> int:
        row = self._execute_one(
            """
            insert into players (name) values (%s)
            on conflict (name) do update set name = excluded.name
            returning id
            """,
            (name,),
        )
        return int(row["id"])


def repository() -> SimulatorRepository:
    return SimulatorRepository()


@contextmanager
def transaction():
    with get_connection() as conn:
        yield SimulatorRepository(conn)


def league_csv_files(competition_slug: str) -> dict[str, str]:
    repo = repository()
    resultados, fixture, tabla = repo.league_data(competition_slug)
    if competition_slug == "nacional":
        goleadores = repo.scorer_totals_df("nacional")
        return {
            "resultados.csv": dataframe_to_csv(resultados, RESULT_COLUMNS),
            "fixture.csv": dataframe_to_csv(fixture, MATCH_COLUMNS),
            "tabla.csv": dataframe_to_csv(tabla, STANDING_COLUMNS),
            "goleadores.csv": dataframe_to_csv(goleadores, SCORER_COLUMNS),
        }
    if competition_slug == "lpf":
        promedios = repo.lpf_average_history_df()
        return {
            "tablalpf.csv": dataframe_to_csv(tabla, STANDING_COLUMNS),
            "fixture_lpf.csv": dataframe_to_csv(fixture, MATCH_COLUMNS),
            "resultados_lpf.csv": dataframe_to_csv(resultados, RESULT_COLUMNS),
            "promedios_lpf.csv": dataframe_to_csv(promedios, LPF_AVERAGE_COLUMNS),
        }
    prefixes = {
        "bmetro": ("tabla_bmetro.csv", "fixture_bmetro.csv", "resultados_bmetro.csv"),
        "federal_a": ("tabla_federal_a.csv", "fixture_federal_a.csv", "resultados_federal_a.csv"),
    }
    tabla_name, fixture_name, resultados_name = prefixes[competition_slug]
    return {
        tabla_name: dataframe_to_csv(tabla, STANDING_COLUMNS),
        fixture_name: dataframe_to_csv(fixture, MATCH_COLUMNS),
        resultados_name: dataframe_to_csv(resultados, RESULT_COLUMNS),
    }


def cup_csv_files() -> dict[str, str]:
    return {"copa_argentina.csv": records_to_csv(repository().cup_records(), CUP_COLUMNS)}


def _nullable_int(value):
    if value is None or value == "":
        return None
    if pd.isna(value):
        return None
    return int(value)
