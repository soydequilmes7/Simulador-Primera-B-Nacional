# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import io
import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
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
    "primerac": CompetitionSpec("primerac", "Primera C"),
    "copa": CompetitionSpec("copa", "Copa Argentina"),
    "brasileirao": CompetitionSpec("brasileirao", "Brasileirão Série A"),
}

TABLE_FILE_SLUGS = {
    "tabla.csv": "nacional",
    "tablalpf.csv": "lpf",
    "tabla_bmetro.csv": "bmetro",
    "tabla_federal_a.csv": "federal_a",
    "tabla_primerac.csv": "primerac",
    "tabla_brasileirao.csv": "brasileirao",
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

    def ensure_competition_season(
        self,
        competition_slug: str,
        season: str | None = None,
        deactivate_others: bool = True,
    ) -> int:
        """Asegura que exista (y esté activa) la fila de `seasons` para
        `season` (ej. "2027"). Si `season` es None, usa el default de
        COMPETITIONS (comportamiento anterior, compatible con todo el
        código que ya llama ensure_competition_season(slug) sin
        segundo argumento).

        ANTES: `spec.season` estaba hardcodeado a "2026" en COMPETITIONS
        y esta función SIEMPRE hacía upsert contra (competition_slug,
        "2026") -- no había forma de crear una temporada N+1 realmente
        distinta, cualquier llamada pisaba la misma fila. Este es el fix
        de ese problema (Etapa 6 del plan de Modo Temporada Nacional).

        deactivate_others=True (default) desactiva cualquier OTRA fila
        de `seasons` de esa competencia -- así season_id() (que filtra
        `active = true`) resuelve sin ambigüedad a la temporada recién
        creada. Pasar False si por algún motivo se necesita tener más
        de una temporada activa a la vez (no es el caso normal)."""
        spec = COMPETITIONS[competition_slug]
        season_name = season or spec.season
        try:
            year = int(season_name)
        except ValueError:
            year = int(spec.season)  # fallback si season no es puramente numérico

        self._execute(
            """
            insert into competitions (slug, name) values (%s, %s)
            on conflict (slug) do update set name = excluded.name
            """,
            (spec.slug, spec.name),
        )
        if deactivate_others:
            self._execute(
                "update seasons set active = false where competition_slug = %s and name != %s",
                (competition_slug, season_name),
            )
        self._execute(
            """
            insert into seasons (competition_slug, name, year, active)
            values (%s, %s, %s, true)
            on conflict (competition_slug, name) do update set
                year = excluded.year,
                active = true
            """,
            (competition_slug, season_name, year),
        )
        return self.season_id(competition_slug)

    def league_seed_counts(self, competition_slug: str) -> dict[str, int]:
        season_id = self.season_id(competition_slug)
        standings = self._execute_one(
            "select count(*) as n from standings where competition_slug = %s and season_id = %s",
            (competition_slug, season_id),
        )
        matches = self._execute_one(
            "select count(*) as n from matches where competition_slug = %s and season_id = %s",
            (competition_slug, season_id),
        )
        return {"standings": int(standings["n"]), "matches": int(matches["n"])}

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

    def club_ratings_by_names(self, names: list[str]) -> dict[str, dict]:
        nombres_unicos = list(dict.fromkeys(names))
        if not nombres_unicos:
            return {}
        rows = self._execute(
            """
            select t.name, cr.ataque_local, cr.ataque_visitante,
                   cr.defensa_local, cr.defensa_visitante, cr.partidos_computados
            from club_ratings cr
            join teams t on t.id = cr.team_id
            where t.name = any(%s)
            """,
            (nombres_unicos,),
        )
        return {
            row["name"]: {
                "ataque_local": float(row["ataque_local"]),
                "ataque_visitante": float(row["ataque_visitante"]),
                "defensa_local": float(row["defensa_local"]),
                "defensa_visitante": float(row["defensa_visitante"]),
                "partidos_computados": int(row["partidos_computados"]),
            }
            for row in rows
        }

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

    def _ensure_teams_bulk(self, names: list[str]) -> dict[str, int]:
        """Como ensure_team() pero para muchos nombres a la vez -- UN
        solo viaje a la base en vez de uno por equipo. Mismo INSERT ...
        ON CONFLICT ... DO UPDATE de siempre, solo que con varias filas
        de VALUES juntas; RETURNING trae el id tanto de las filas
        insertadas como de las que ya existían (conflicto)."""
        nombres_unicos = list(dict.fromkeys(names))  # dedup preservando orden
        if not nombres_unicos:
            return {}
        placeholders = ", ".join(["(%s)"] * len(nombres_unicos))
        filas = self._execute(
            f"""
            insert into teams (name) values {placeholders}
            on conflict (name) do update set name = excluded.name
            returning id, name
            """,
            nombres_unicos,
        )
        return {fila["name"]: fila["id"] for fila in filas}

    def upsert_standings(self, competition_slug: str, filas: list[dict]) -> None:
        """Antes: 1 round-trip para season_id + 1 para ensure_team +
        1 insert POR FILA (varios cientos en una tabla como Nacional).
        Ahora: 1 round-trip para season_id + 1 para los equipos (batch)
        + 1 insert con todas las filas juntas -- 3 en total, sea cual
        sea el tamaño de la tabla. Mismo comportamiento (mismo upsert
        por competition_slug+season_id+team_id), solo que agrupado."""
        if not filas:
            return
        season_id = self.season_id(competition_slug)
        equipo_id = self._ensure_teams_bulk([fila["equipo"] for fila in filas])

        valores = []
        parametros = []
        for fila in filas:
            valores.append("(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())")
            parametros.extend([
                competition_slug, season_id, fila["zona"], int(fila["posicion"]), equipo_id[fila["equipo"]],
                int(fila["partidos_jugados"]), int(fila["ganados"]), int(fila["empatados"]),
                int(fila["perdidos"]), int(fila["gf"]), int(fila["gc"]), int(fila["dg"]),
                int(fila["puntos"]),
            ])

        self._execute(
            f"""
            insert into standings (
                competition_slug, season_id, zona, posicion, team_id,
                partidos_jugados, ganados, empatados, perdidos, gf, gc, dg, puntos, updated_at
            )
            values {", ".join(valores)}
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
            parametros,
        )

    def replace_matches(self, competition_slug: str, pending: list[dict], played: list[dict]) -> None:
        """Antes: delete + 1 insert POR PARTIDO, cada uno con SUS
        PROPIOS round-trips de season_id + 2x ensure_team (~4 viajes
        por partido -- para una tabla de 400+ partidos, más de 1500
        round-trips a una base en otra región, tiempo de sobra para
        que Render/el navegador corten por timeout). Ahora: 1 round-trip
        para season_id + el delete + 1 para TODOS los equipos (batch,
        local y visitante de pending y played juntos) + 1 insert con
        todos los partidos juntos -- 4 en total sea cual sea la
        cantidad de partidos. Mismo resultado final en la tabla."""
        season_id = self.season_id(competition_slug)
        self._execute(
            "delete from matches where competition_slug = %s and season_id = %s",
            (competition_slug, season_id),
        )

        partidos = [(row, "pending") for row in pending] + [(row, "played") for row in played]
        if not partidos:
            return

        nombres_equipos = []
        for row, _status in partidos:
            nombres_equipos.append(row["equipo_local"])
            nombres_equipos.append(row["equipo_visitante"])
        equipo_id = self._ensure_teams_bulk(nombres_equipos)

        valores = []
        parametros = []
        for row, status in partidos:
            valores.append("(%s, %s, %s, %s, %s, %s, %s, %s, %s, now())")
            parametros.extend([
                competition_slug, season_id, row.get("fecha") or "", int(row.get("jornada") or 0),
                equipo_id[row["equipo_local"]], equipo_id[row["equipo_visitante"]],
                _nullable_int(row.get("goles_local")), _nullable_int(row.get("goles_visitante")), status,
            ])

        self._execute(
            f"""
            insert into matches (
                competition_slug, season_id, fecha, jornada, equipo_local_id, equipo_visitante_id,
                goles_local, goles_visitante, status, updated_at
            )
            values {", ".join(valores)}
            on conflict (competition_slug, season_id, jornada, equipo_local_id, equipo_visitante_id)
            do update set
                fecha = excluded.fecha,
                goles_local = excluded.goles_local,
                goles_visitante = excluded.goles_visitante,
                status = excluded.status,
                updated_at = now()
            """,
            parametros,
        )

    def apply_club_rating_events(
        self,
        competition_slug: str,
        matches: list[dict],
        source: str,
        metadata: dict | None = None,
    ) -> int:
        """Aplica ELO persistente a partidos oficiales, deduplicando por evento.

        No se llama desde simular_partido(): ese método también corre Monte Carlo.
        Los callers deben pasar solo resultados reales o temporadas aceptadas.
        """
        if not matches:
            return 0

        from season.elo_ratings import PROMEDIOS_COMPETITION, actualizar_por_partido, rating_default

        season_id = self.season_id(competition_slug)
        nombres = []
        for match in matches:
            nombres.append(match["equipo_local"])
            nombres.append(match["equipo_visitante"])
        team_id = self._ensure_teams_bulk(nombres)

        team_ids_unicos = list(dict.fromkeys(team_id.values()))
        placeholders = ", ".join(["(%s)"] * len(team_ids_unicos))
        self._execute(
            f"""
            insert into club_ratings (team_id)
            values {placeholders}
            on conflict (team_id) do nothing
            """,
            team_ids_unicos,
        )

        applied = 0
        for index, match in enumerate(matches, start=1):
            local_id = team_id[match["equipo_local"]]
            visitante_id = team_id[match["equipo_visitante"]]
            jornada = _nullable_int(match.get("jornada"))
            event_key = match.get("event_key")
            if not event_key:
                event_key = (
                    f"{competition_slug}:{season_id}:{jornada or 0}:"
                    f"{local_id}:{visitante_id}:{match.get('goles_local')}:{match.get('goles_visitante')}"
                )

            self._execute("select pg_advisory_xact_lock(hashtext(%s))", (f"{source}:{event_key}",))
            existing = self._execute_one(
                """
                select id
                from club_rating_events
                where source = %s and event_key = %s
                """,
                (source, event_key),
            )
            if existing is not None:
                continue

            rating_rows = self._execute(
                """
                select team_id, ataque_local, ataque_visitante,
                       defensa_local, defensa_visitante, partidos_computados
                from club_ratings
                where team_id in (%s, %s)
                for update
                """,
                (local_id, visitante_id),
            )
            ratings = {int(row["team_id"]): dict(row) for row in rating_rows}
            local_rating = ratings.get(local_id, rating_default())
            visitante_rating = ratings.get(visitante_id, rating_default())

            promedio_default = PROMEDIOS_COMPETITION.get(competition_slug, (1.35, 1.05))
            promedio_local = float(match.get("promedio_local") or promedio_default[0])
            promedio_visitante = float(match.get("promedio_visitante") or promedio_default[1])
            update = actualizar_por_partido(
                local_rating,
                visitante_rating,
                int(match["goles_local"]),
                int(match["goles_visitante"]),
                promedio_local,
                promedio_visitante,
            )

            self._upsert_club_rating(local_id, update.local_post)
            self._upsert_club_rating(visitante_id, update.visitante_post)
            self._execute(
                """
                insert into club_rating_events (
                    competition_slug, season_id, event_key, source, jornada,
                    equipo_local_id, equipo_visitante_id, goles_local, goles_visitante,
                    expected_local, expected_visitante,
                    rating_local_pre, rating_visitante_pre,
                    rating_local_post, rating_visitante_post, metadata
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (source, event_key) do nothing
                """,
                (
                    competition_slug, season_id, event_key, source, jornada,
                    local_id, visitante_id, int(match["goles_local"]), int(match["goles_visitante"]),
                    update.expected_local, update.expected_visitante,
                    Jsonb(update.local_pre), Jsonb(update.visitante_pre),
                    Jsonb(update.local_post), Jsonb(update.visitante_post),
                    Jsonb({**(metadata or {}), **(match.get("metadata") or {}), "orden": index}),
                ),
            )
            applied += 1
        return applied

    def _upsert_club_rating(self, team_id: int, rating: dict) -> None:
        self._execute(
            """
            insert into club_ratings (
                team_id, ataque_local, ataque_visitante,
                defensa_local, defensa_visitante, partidos_computados, updated_at
            )
            values (%s, %s, %s, %s, %s, %s, now())
            on conflict (team_id) do update set
                ataque_local = excluded.ataque_local,
                ataque_visitante = excluded.ataque_visitante,
                defensa_local = excluded.defensa_local,
                defensa_visitante = excluded.defensa_visitante,
                partidos_computados = excluded.partidos_computados,
                updated_at = now()
            """,
            (
                team_id,
                float(rating["ataque_local"]),
                float(rating["ataque_visitante"]),
                float(rating["defensa_local"]),
                float(rating["defensa_visitante"]),
                int(rating["partidos_computados"]),
            ),
        )

    def upsert_match(self, competition_slug: str, row: dict, status: str) -> None:
        """Se mantiene para quien necesite cargar UN partido suelto
        (ej. scripts/seed_supabase.py) -- replace_matches() ya NO la
        usa (ver arriba), así que la ruta de temporada completa no pasa
        más por acá."""
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


LEAGUE_FILE_SPECS = {
    "nacional": ("tabla.csv", "fixture.csv", "resultados.csv"),
    "lpf": ("tablalpf.csv", "fixture_lpf.csv", "resultados_lpf.csv"),
    "bmetro": ("tabla_bmetro.csv", "fixture_bmetro.csv", "resultados_bmetro.csv"),
    "federal_a": ("tabla_federal_a.csv", "fixture_federal_a.csv", "resultados_federal_a.csv"),
    "primerac": ("tabla_primerac.csv", "fixture_primerac.csv", "resultados_primerac.csv"),
    "brasileirao": ("tabla_brasileirao.csv", "fixture_brasileirao.csv", "resultados_brasileirao.csv"),
}


def bootstrap_league_from_csv(competition_slug: str) -> bool:
    """Seed a league from bundled CSVs only when its DB rows are absent."""
    tabla_name, fixture_name, resultados_name = LEAGUE_FILE_SPECS[competition_slug]
    datos_dir = Path(__file__).resolve().parent.parent / "datos"

    def read_csv(name: str) -> list[dict]:
        with open(datos_dir / name, newline="", encoding="utf-8") as f:
            return [row for row in csv.DictReader(f) if row]

    with transaction() as repo:
        repo.ensure_competition_season(competition_slug)
        counts = repo.league_seed_counts(competition_slug)
        if counts["standings"] and counts["matches"]:
            return False

        repo.upsert_standings(competition_slug, read_csv(tabla_name))
        repo.replace_matches(
            competition_slug,
            read_csv(fixture_name),
            read_csv(resultados_name),
        )
        return True


def league_csv_files(competition_slug: str) -> dict[str, str]:
    if competition_slug == "primerac":
        bootstrap_league_from_csv("primerac")

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
        "primerac": ("tabla_primerac.csv", "fixture_primerac.csv", "resultados_primerac.csv"),
        "brasileirao": ("tabla_brasileirao.csv", "fixture_brasileirao.csv", "resultados_brasileirao.csv"),
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
