# -*- coding: utf-8 -*-
"""
diagnosticar_estudiantes_lp_duplicado.py

Diagnostica el duplicado real detectado por ClubRegistry en Liga
Profesional: hay una fila en `teams` llamada "Estudiantes" (id=19230,
confirmado por fix_nombre_estudiantes_caseros.py) con standings en
lpf/season_id=7 pero SIN ningún partido en `matches` -- huele a fila
huérfana dejada por el primer seed de tablalpf.csv (que usa el alias
corto), mientras que el Estudiantes de La Plata real (con todos sus
partidos) vive en otro team_id bajo el nombre completo.

Este script SOLO lee -- no escribe nada. Muestra:
  1. Todas las filas de teams que matcheen "Estudiantes de La Plata"
     (nombre completo).
  2. standings de esa fila en lpf/season_id=7.
  3. matches de esa fila en lpf/season_id=7.
  4. Los mismos dos chequeos para id=19230 ("Estudiantes"), para
     comparar lado a lado.

Uso:
    python diagnosticar_estudiantes_lp_duplicado.py
"""
from __future__ import annotations

from db.client import get_connection

NOMBRES = ["Estudiantes", "Estudiantes de La Plata"]
SEASON_ID_LPF = 7  # confirmado por la corrida anterior


def main() -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select id, name from teams where name = any(%s) order by name",
                (NOMBRES,),
            )
            equipos = cur.fetchall()

            print("=" * 70)
            print("Filas en teams:")
            for e in equipos:
                print(f'  id={e["id"]}  name={e["name"]!r}')

            for e in equipos:
                team_id = e["id"]
                print("\n" + "=" * 70)
                print(f'team_id={team_id}  name={e["name"]!r}')

                cur.execute(
                    """
                    select competition_slug, season_id, zona, posicion,
                           partidos_jugados, puntos
                    from standings
                    where team_id = %s
                    order by competition_slug, season_id
                    """,
                    (team_id,),
                )
                standings = cur.fetchall()
                print(f"  standings ({len(standings)} fila(s)):")
                for s in standings:
                    print(
                        f'    {s["competition_slug"]:12s} season_id={s["season_id"]}  '
                        f'zona={s["zona"]}  posicion={s["posicion"]}  '
                        f'partidos_jugados={s["partidos_jugados"]}  puntos={s["puntos"]}'
                    )

                cur.execute(
                    """
                    select competition_slug, season_id, count(*) as partidos
                    from matches
                    where equipo_local_id = %s or equipo_visitante_id = %s
                    group by competition_slug, season_id
                    order by competition_slug, season_id
                    """,
                    (team_id, team_id),
                )
                matches = cur.fetchall()
                print(f"  matches ({len(matches)} grupo(s) por competencia/temporada):")
                if not matches:
                    print("    (NINGUNO)")
                for m in matches:
                    print(
                        f'    {m["competition_slug"]:12s} season_id={m["season_id"]}  '
                        f'partidos={m["partidos"]}'
                    )

            print("\n" + "=" * 70)
            print(
                "Si 'Estudiantes de La Plata' tiene standings + matches parejos en "
                f"lpf/season_id={SEASON_ID_LPF}, y 'Estudiantes' (id=19230) tiene SOLO "
                "standings y CERO matches -> la fila de 'Estudiantes' es un huérfano "
                "seguro para borrar (no se pierde ningún partido real)."
            )
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
