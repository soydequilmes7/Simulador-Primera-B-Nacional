# -*- coding: utf-8 -*-
"""
separar_equipo_compartido.py

Corrige el caso "dos clubes reales distintos, en divisiones distintas,
terminaron compartiendo la misma fila de `teams` porque alguna vez se
sembraron con el mismo alias corto sin desambiguar" -- confirmado con
diff_roster_lpf.py para "Estudiantes" (LPF: Estudiantes de La Plata,
16 partidos jugados reales vs. Nacional: Estudiantes de Caseros,
posición de tabla real en curso) y "Central Córdoba" (LPF: Central
Córdoba SdE vs. Primera C: Central Córdoba de Rosario).

`teams.name` es único a nivel global (ver _ensure_teams_bulk,
db/repository.py) -- cuando dos sembrados distintos usan el mismo
alias corto sin querer, el segundo hace `on conflict (name) do
update` sobre la fila del primero, y desde ahí ambos clubes quedan
compartiendo un solo team_id: standings/matches de AMBAS divisiones
apuntan al mismo id, con datos reales de dos equipos distintos
mezclados bajo una sola identidad.

Este script NO borra nada -- separa: crea una fila NUEVA en `teams`
con el nombre correcto para UNA de las dos competencias en conflicto,
y repunta standings/matches de ESA competencia (y SOLO esa) del
team_id viejo al nuevo. La otra competencia se queda con el team_id
original (podés renombrarlo aparte si hace falta, este script no lo
toca).

Uso:
    # 1) diagnóstico (no escribe nada)
    python separar_equipo_compartido.py --nombre "Estudiantes (Caseros)" --separar lpf --nombre-nuevo "Estudiantes de La Plata"

    # 2) aplicar
    python separar_equipo_compartido.py --nombre "Estudiantes (Caseros)" --separar lpf --nombre-nuevo "Estudiantes de La Plata" --aplicar
"""
from __future__ import annotations

import argparse
import sys

from db.client import get_connection


def _diagnosticar(cur, nombre: str) -> dict:
    cur.execute("select id, name from teams where name = %s", (nombre,))
    equipo = cur.fetchall()
    if not equipo:
        return {"equipo": None}
    team_id = equipo[0]["id"]

    cur.execute(
        """
        select competition_slug, season_id, zona, posicion, partidos_jugados
        from standings where team_id = %s order by competition_slug, season_id
        """,
        (team_id,),
    )
    standings = cur.fetchall()

    cur.execute(
        """
        select competition_slug, season_id, count(*) as partidos,
               sum((equipo_local_id = %s)::int) as como_local,
               sum((equipo_visitante_id = %s)::int) as como_visitante
        from matches
        where equipo_local_id = %s or equipo_visitante_id = %s
        group by competition_slug, season_id
        order by competition_slug, season_id
        """,
        (team_id, team_id, team_id, team_id),
    )
    matches = cur.fetchall()

    return {"equipo": equipo[0], "team_id": team_id, "standings": standings, "matches": matches}


def _imprimir(d: dict, nombre: str) -> None:
    print("=" * 70)
    if d["equipo"] is None:
        print(f'No existe ningún equipo con name = "{nombre}".')
        return
    print(f'team_id={d["team_id"]}  name={nombre!r}')
    print(f"\nStandings (competition_slug, season_id, zona, posicion, partidos_jugados):")
    divisiones_standings = set()
    for f in d["standings"]:
        divisiones_standings.add(f["competition_slug"])
        print(f'  {f["competition_slug"]:12s} season_id={f["season_id"]}  zona={f["zona"]}  '
              f'posicion={f["posicion"]}  partidos_jugados={f["partidos_jugados"]}')

    print(f"\nMatches (competition_slug, season_id, cantidad, como local, como visitante):")
    divisiones_matches = set()
    for f in d["matches"]:
        divisiones_matches.add(f["competition_slug"])
        print(f'  {f["competition_slug"]:12s} season_id={f["season_id"]}  partidos={f["partidos"]}  '
              f'local={f["como_local"]}  visitante={f["como_visitante"]}')

    divisiones = divisiones_standings | divisiones_matches
    print(f"\nEste team_id aparece en {len(divisiones)} división(es): {sorted(divisiones)}")
    if len(divisiones) > 1:
        print("⚠️  Más de una división -- probablemente son DOS clubes reales distintos compartiendo id.")
    print("=" * 70)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nombre", required=True, help='Nombre actual en teams (el compartido), ej. "Estudiantes (Caseros)"')
    parser.add_argument("--separar", required=True, help='competition_slug a separar en un team_id nuevo, ej. "lpf"')
    parser.add_argument("--nombre-nuevo", required=True, help='Nombre correcto para ese competition_slug, ej. "Estudiantes de La Plata"')
    parser.add_argument("--aplicar", action="store_true", help="Aplica la separación (por default solo diagnostica).")
    args = parser.parse_args()

    with get_connection() as conn:
        with conn.cursor() as cur:
            d = _diagnosticar(cur, args.nombre)
            _imprimir(d, args.nombre)

            if d["equipo"] is None:
                return 1

            divisiones_en_uso = {f["competition_slug"] for f in d["standings"]} | {f["competition_slug"] for f in d["matches"]}
            if args.separar not in divisiones_en_uso:
                print(f'\n"{args.separar}" no aparece en standings/matches de este team_id -- nada que separar.')
                return 1
            if len(divisiones_en_uso) < 2:
                print(f'\nSolo aparece en una división ({divisiones_en_uso}) -- no hay nada compartido, no hace falta separar.')
                return 1

            if not args.aplicar:
                print(f'\nSolo diagnóstico. Con --aplicar: usa (creando si hace falta) el team '
                      f'"{args.nombre_nuevo}" y '
                      f'repunta standings/matches de "{args.separar}" (team_id={d["team_id"]}) a ese team nuevo.')
                return 0

            team_id_viejo = d["team_id"]

            cur.execute("select id from teams where name = %s", (args.nombre_nuevo,))
            existente = cur.fetchall()
            if existente:
                team_id_nuevo = existente[0]["id"]
                # Reusar un team_id existente es seguro siempre que ESE id no
                # esté a su vez compartido entre divisiones (si lo estuviera,
                # repuntear ahí solo movería el problema a otro lado). Se
                # revisa acá en vez de asumir -- mismo criterio que
                # _diagnosticar()/_imprimir() de arriba.
                cur.execute(
                    """
                    select distinct competition_slug from (
                        select competition_slug from standings where team_id = %s
                        union
                        select competition_slug from matches
                        where equipo_local_id = %s or equipo_visitante_id = %s
                    ) t
                    """,
                    (team_id_nuevo, team_id_nuevo, team_id_nuevo),
                )
                divisiones_destino = {f["competition_slug"] for f in cur.fetchall()}
                divisiones_destino_sin_la_que_se_separa = divisiones_destino - {args.separar}
                if divisiones_destino_sin_la_que_se_separa:
                    print(
                        f'\n❌ team_id={team_id_nuevo} ("{args.nombre_nuevo}") ya tiene datos en '
                        f'{sorted(divisiones_destino_sin_la_que_se_separa)} -- repuntear "{args.separar}" '
                        f'ahí lo compartiría con MÁS de una división. Revisar a mano, no es un caso '
                        f'seguro para este script.'
                    )
                    return 1
                print(f'\nReusando team_id={team_id_nuevo} ya existente para "{args.nombre_nuevo}" '
                      f'(confirmado: solo tiene datos de "{args.separar}" hasta ahora).')
            else:
                cur.execute(
                    "insert into teams (name) values (%s) returning id",
                    (args.nombre_nuevo,),
                )
                team_id_nuevo = cur.fetchone()["id"]

            cur.execute(
                "update standings set team_id = %s where competition_slug = %s and team_id = %s",
                (team_id_nuevo, args.separar, team_id_viejo),
            )
            filas_standings = cur.rowcount
            cur.execute(
                "update matches set equipo_local_id = %s where competition_slug = %s and equipo_local_id = %s",
                (team_id_nuevo, args.separar, team_id_viejo),
            )
            filas_local = cur.rowcount
            cur.execute(
                "update matches set equipo_visitante_id = %s where competition_slug = %s and equipo_visitante_id = %s",
                (team_id_nuevo, args.separar, team_id_viejo),
            )
            filas_visitante = cur.rowcount

            conn.commit()

            print(f'\n✅ Separado: team_id={team_id_nuevo} "{args.nombre_nuevo}" en uso para "{args.separar}".')
            print(f'   standings repunteados: {filas_standings}')
            print(f'   matches (como local) repunteados: {filas_local}')
            print(f'   matches (como visitante) repunteados: {filas_visitante}')
            print(f'   team_id={team_id_viejo} "{args.nombre}" se queda con el resto de las divisiones.')
            return 0


if __name__ == "__main__":
    sys.exit(main())
