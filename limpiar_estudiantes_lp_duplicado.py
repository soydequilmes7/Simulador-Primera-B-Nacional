# -*- coding: utf-8 -*-
"""
limpiar_estudiantes_lp_duplicado.py

Borra la fila huérfana de standings que causa el error de ClubRegistry
("Club duplicado entre divisiones: 'Estudiantes de La Plata' aparece
en 'Liga Profesional' y en 'Liga Profesional'").

Confirmado con diagnosticar_estudiantes_lp_duplicado.py:
  - teams.id=19230 name='Estudiantes'          -> 1 fila en standings
    (lpf, season_id=7, zona A, posicion 1, 16 pj, 31 pts), 0 matches.
  - teams.id=2731  name='Estudiantes de La Plata' -> standings +
    matches reales para esa misma temporada (16 partidos jugados).

Son la MISMA fila de standings duplicada -- la de id=19230 quedó de
un seed viejo de tablalpf.csv con el alias corto "Estudiantes", antes
de que existiera el alias que lo resuelve contra el team_id real. No
tiene ningún partido colgando, así que borrarla no pierde nada.

Este script:
  1. Re-valida el estado (mismo chequeo que el diagnóstico) antes de
     escribir nada -- aborta si algo no coincide con lo esperado.
  2. Sin --aplicar: solo diagnostica.
  3. Con --aplicar: borra la fila de standings (team_id=19230,
     competition_slug='lpf', season_id=7). Si después de eso el
     team_id=19230 queda sin NINGUNA referencia en standings, matches,
     scorer_totals, club_ratings ni team_aliases, borra también la
     fila huérfana de teams (prolijidad, no imprescindible).

Uso:
    python limpiar_estudiantes_lp_duplicado.py
    python limpiar_estudiantes_lp_duplicado.py --aplicar
"""
from __future__ import annotations

import argparse

from db.client import get_connection

TEAM_ID_HUERFANO = 19230
NOMBRE_HUERFANO = "Estudiantes"
TEAM_ID_REAL = 2731
NOMBRE_REAL = "Estudiantes de La Plata"
COMPETITION_SLUG = "lpf"
SEASON_ID = 7


def _validar(cur) -> str | None:
    """Devuelve un mensaje de error si el estado real no coincide con
    lo esperado (mejor abortar que borrar a ciegas). None si está
    todo en orden."""
    cur.execute("select id, name from teams where id = %s", (TEAM_ID_HUERFANO,))
    fila = cur.fetchone()
    if fila is None:
        return f"No existe teams.id={TEAM_ID_HUERFANO} -- nada que limpiar."
    if fila["name"] != NOMBRE_HUERFANO:
        return f'teams.id={TEAM_ID_HUERFANO} ahora se llama {fila["name"]!r}, no {NOMBRE_HUERFANO!r} -- revisar a mano.'

    cur.execute(
        "select count(*) as n from matches where equipo_local_id = %s or equipo_visitante_id = %s",
        (TEAM_ID_HUERFANO, TEAM_ID_HUERFANO),
    )
    if cur.fetchone()["n"] != 0:
        return f"teams.id={TEAM_ID_HUERFANO} ahora SÍ tiene partidos en matches -- ya no es un huérfano seguro, revisar a mano."

    cur.execute(
        "select competition_slug, season_id, zona, posicion, partidos_jugados, puntos "
        "from standings where team_id = %s",
        (TEAM_ID_HUERFANO,),
    )
    filas_standings = cur.fetchall()
    if len(filas_standings) != 1:
        return f"teams.id={TEAM_ID_HUERFANO} tiene {len(filas_standings)} fila(s) en standings (se esperaba 1) -- revisar a mano."
    s = filas_standings[0]
    if not (s["competition_slug"] == COMPETITION_SLUG and s["season_id"] == SEASON_ID
            and s["zona"] == "A" and s["posicion"] == 1
            and s["partidos_jugados"] == 16 and s["puntos"] == 31):
        return f"La fila de standings de teams.id={TEAM_ID_HUERFANO} cambió respecto del diagnóstico ({s}) -- revisar a mano."

    cur.execute(
        "select zona, posicion, partidos_jugados, puntos from standings "
        "where team_id = %s and competition_slug = %s and season_id = %s",
        (TEAM_ID_REAL, COMPETITION_SLUG, SEASON_ID),
    )
    fila_real = cur.fetchone()
    if fila_real is None:
        return f"teams.id={TEAM_ID_REAL} ({NOMBRE_REAL!r}) no tiene standings en {COMPETITION_SLUG}/season_id={SEASON_ID} -- ya no coincide con el diagnóstico, revisar a mano."

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aplicar", action="store_true", help="Aplica el borrado (por default solo diagnostica).")
    args = parser.parse_args()

    with get_connection() as conn:
        with conn.cursor() as cur:
            error = _validar(cur)
            if error:
                print(f"❌ {error}")
                return 1

            print(
                f"✅ Confirmado: teams.id={TEAM_ID_HUERFANO} ({NOMBRE_HUERFANO!r}) tiene "
                f"exactamente 1 fila de standings duplicada (lpf/season_id={SEASON_ID}) "
                f"y 0 partidos -- seguro para borrar."
            )

            if not args.aplicar:
                print("\nSolo diagnóstico (no se escribió nada). Correr con --aplicar para borrar.")
                return 0

            cur.execute(
                "delete from standings where team_id = %s and competition_slug = %s and season_id = %s",
                (TEAM_ID_HUERFANO, COMPETITION_SLUG, SEASON_ID),
            )
            print(f"\n✅ Borrada la fila de standings huérfana (team_id={TEAM_ID_HUERFANO}).")

            # Prolijidad: si el team_id huérfano ya no tiene NINGUNA referencia
            # en ningún lado, borramos también la fila de teams.
            referencias = 0
            for consulta in [
                "select count(*) as n from standings where team_id = %s",
                "select count(*) as n from matches where equipo_local_id = %s",
                "select count(*) as n from matches where equipo_visitante_id = %s",
                "select count(*) as n from scorer_totals where team_id = %s",
                "select count(*) as n from club_ratings where team_id = %s",
                "select count(*) as n from team_aliases where team_id = %s",
            ]:
                cur.execute(consulta, (TEAM_ID_HUERFANO,))
                referencias += cur.fetchone()["n"]

            if referencias == 0:
                cur.execute("delete from teams where id = %s", (TEAM_ID_HUERFANO,))
                print(f"✅ teams.id={TEAM_ID_HUERFANO} no tenía más referencias -- fila borrada también.")
            else:
                print(f"ℹ️  teams.id={TEAM_ID_HUERFANO} todavía tiene {referencias} referencia(s) en otras tablas -- se deja la fila de teams como está (no molesta, ya no aparece en standings de lpf).")

            conn.commit()
            print("\nListo. Probá de nuevo 'Simular la temporada completa'.")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
