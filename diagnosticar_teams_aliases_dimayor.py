# -*- coding: utf-8 -*-
"""
diagnosticar_teams_aliases_dimayor.py

Va directo a Supabase (sin pasar por el resolver de nombres) para ver:
  1. Todas las filas de `teams` que coincidan con los 6 nombres en juego
     (los 3 viejos mal sembrados + los 3 correctos).
  2. Todas las filas de `team_aliases` para competition_slug='dimayor'.

Esto muestra si el problema es un alias viejo en `team_aliases` que
sigue resolviendo "Junior FC" (etc.) contra el team_id equivocado, o
si es otra cosa.

Uso:
    python diagnosticar_teams_aliases_dimayor.py
"""
from db.client import get_connection

NOMBRES = [
    "Junior FC", "Junior de Barranquilla",
    "Fortaleza FC", "Fortaleza CEIF",
    "Internacional de Bogotá", "Inter de Bogotá",
]

with get_connection() as conn:
    with conn.cursor() as cur:
        print("=" * 60)
        print("1) Filas en `teams` que coinciden con estos nombres")
        print("=" * 60)
        cur.execute(
            "select id, name from teams where name = any(%s) order by name",
            (NOMBRES,),
        )
        for row in cur.fetchall():
            print(f"  id={row['id']!r}  name={row['name']!r}")

        print()
        print("=" * 60)
        print("2) Filas en `team_aliases` para competition_slug='dimayor'")
        print("=" * 60)
        cur.execute(
            """
            select ta.alias, ta.team_id, t.name as team_name, ta.source
            from team_aliases ta
            join teams t on t.id = ta.team_id
            where ta.competition_slug = 'dimayor'
            order by ta.alias
            """
        )
        filas = cur.fetchall()
        if not filas:
            print("  (ninguna)")
        for row in filas:
            print(
                f"  alias={row['alias']!r}  -> team_id={row['team_id']}  "
                f"team_name={row['team_name']!r}  source={row['source']!r}"
            )

        print()
        print("=" * 60)
        print("3) Standings actuales de dimayor (team_id + name)")
        print("=" * 60)
        cur.execute(
            """
            select st.team_id, t.name, st.zona, st.posicion
            from standings st
            join teams t on t.id = st.team_id
            where st.competition_slug = 'dimayor'
            order by st.posicion
            """
        )
        for row in cur.fetchall():
            print(f"  team_id={row['team_id']}  name={row['name']!r}  zona={row['zona']}  posicion={row['posicion']}")
