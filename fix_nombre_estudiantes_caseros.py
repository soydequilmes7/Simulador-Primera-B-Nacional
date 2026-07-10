# -*- coding: utf-8 -*-
"""
fix_nombre_estudiantes_caseros.py

Diagnostica y corrige el bug de raíz reportado en Modo Temporada:
en la tabla `teams` de Supabase, Estudiantes de Caseros (Primera
Nacional) está guardado como "Estudiantes" a secas -- el mismo alias
corto que estadisticas_lpf.NORMALIZACION_NOMBRES usa para expandir
"Estudiantes" -> "Estudiantes de La Plata" al cargar LPF. Cuando ese
club asciende a LPF, colisiona con el Estudiantes de La Plata real
(ver PromotionManager._mover_club / ClubRegistry.renombrar_club,
agregado para que esto falle explícito en vez de fusionar los dos
clubes en silencio).

`teams.name` es GLOBAL y único (`on conflict (name) do update` en
_ensure_teams_bulk, db/repository.py) -- no está separado por
competencia. Por eso alcanza con un solo UPDATE: standings y matches
referencian a `teams` por `team_id`, no por nombre, así que renombrar
la fila arregla LPF, Nacional y cualquier otro lado que lo use, todo
junto.

Uso (PowerShell, mismo patrón que el resto del proyecto):
    $env:SUPABASE_DB_URL = "..."; python fix_nombre_estudiantes_caseros.py
    $env:SUPABASE_DB_URL = "..."; python fix_nombre_estudiantes_caseros.py --aplicar

Sin --aplicar: solo diagnostica (no escribe nada). Con --aplicar:
corrige el nombre, PERO SOLO SI el diagnóstico no encontró nada raro
(ver _validar_antes_de_aplicar) -- mejor abortar y avisar que corregir
a ciegas si el estado real no es el esperado.
"""
from __future__ import annotations

import argparse
import sys

from db.client import get_connection

NOMBRE_VIEJO = "Estudiantes"
NOMBRE_NUEVO = "Estudiantes (Caseros)"


def _diagnosticar(cur) -> dict:
    cur.execute("select id, name from teams where name = %s", (NOMBRE_VIEJO,))
    viejo = cur.fetchall()

    cur.execute("select id, name from teams where name = %s", (NOMBRE_NUEVO,))
    nuevo = cur.fetchall()

    equipo_id = viejo[0]["id"] if viejo else None
    apariciones_standings = []
    apariciones_matches = []
    if equipo_id is not None:
        cur.execute(
            """
            select competition_slug, season_id, zona, posicion
            from standings where team_id = %s
            order by competition_slug, season_id
            """,
            (equipo_id,),
        )
        apariciones_standings = cur.fetchall()

        cur.execute(
            """
            select competition_slug, season_id, count(*) as partidos
            from matches
            where equipo_local_id = %s or equipo_visitante_id = %s
            group by competition_slug, season_id
            order by competition_slug, season_id
            """,
            (equipo_id, equipo_id),
        )
        apariciones_matches = cur.fetchall()

    return {
        "viejo": viejo,
        "nuevo": nuevo,
        "standings": apariciones_standings,
        "matches": apariciones_matches,
    }


def _imprimir_diagnostico(d: dict) -> None:
    print("=" * 70)
    print(f'Filas en teams con name = "{NOMBRE_VIEJO}": {len(d["viejo"])}')
    for fila in d["viejo"]:
        print(f'  id={fila["id"]}  name={fila["name"]!r}')

    print(f'\nFilas en teams con name = "{NOMBRE_NUEVO}": {len(d["nuevo"])}')
    for fila in d["nuevo"]:
        print(f'  id={fila["id"]}  name={fila["name"]!r}')

    if d["viejo"]:
        print(f'\nAparece en standings (competition_slug, season_id, zona, posicion):')
        for fila in d["standings"]:
            print(f'  {fila["competition_slug"]:12s} season_id={fila["season_id"]}  '
                  f'zona={fila["zona"]}  posicion={fila["posicion"]}')

        print(f'\nAparece en matches (competition_slug, season_id, cantidad):')
        for fila in d["matches"]:
            print(f'  {fila["competition_slug"]:12s} season_id={fila["season_id"]}  '
                  f'partidos={fila["partidos"]}')
    print("=" * 70)


def _validar_antes_de_aplicar(d: dict) -> str | None:
    """Devuelve un mensaje de error si el estado real no es el
    esperado (mejor abortar el UPDATE que aplicarlo a ciegas).
    None si está todo en orden para aplicar.

    NOTA (revisado tras el primer diagnóstico real): renombrar
    teams.name NO afecta standings/matches -- esas tablas referencian
    por team_id (que no cambia), no por nombre, y no hay ningún UNIQUE
    ni FK sobre el nombre salvo en la propia tabla teams. Por eso este
    validador YA NO bloquea el rename solo porque el equipo tenga
    standings/matches en "lpf" -- eso es un problema de integridad de
    ESA temporada de LPF, separado del nombre, y se reporta aparte
    (ver _diagnosticar_fixture_lpf) en vez de bloquear la corrección
    del nombre, que hace falta de todos modos."""
    if not d["viejo"]:
        return f'No hay ninguna fila en teams con name = "{NOMBRE_VIEJO}" -- nada que corregir.'
    if len(d["viejo"]) > 1:
        return f'Hay {len(d["viejo"])} filas con name = "{NOMBRE_VIEJO}" (se esperaba 1) -- revisar a mano.'
    if d["nuevo"]:
        return (
            f'Ya existe una fila con name = "{NOMBRE_NUEVO}" (id={d["nuevo"][0]["id"]}) -- '
            f'un UPDATE directo violaría la unicidad de teams.name. Hay que fusionar '
            f'team_id a mano en standings/matches antes de renombrar, no es un caso '
            f'seguro para este script.'
        )
    return None


def _diagnosticar_fixture_lpf(cur, season_id: int) -> None:
    """Chequeo aparte (informativo, no bloquea el rename): ¿la
    temporada de LPF con este season_id tiene el fixture parejo
    (todos los equipos con la misma cantidad de partidos) o ya está
    corrupta por la colisión de nombres (algún equipo con el doble)?
    Mismo criterio que _validar_datos_lpf() en estadisticas_lpf.py."""
    cur.execute(
        """
        select t.name as equipo, count(*) as partidos
        from matches m
        join teams t on t.id in (m.equipo_local_id, m.equipo_visitante_id)
        where m.competition_slug = 'lpf' and m.season_id = %s
        group by t.name
        order by partidos desc, equipo
        """,
        (season_id,),
    )
    filas = cur.fetchall()
    print(f"\nFixture de LPF, season_id={season_id} -- partidos por equipo:")
    if not filas:
        print("  (sin partidos cargados todavía para esta temporada -- nada que limpiar)")
        return
    conteos = {f["partidos"] for f in filas}
    if len(conteos) == 1:
        print(f"  OK -- los {len(filas)} equipos tienen {conteos.pop()} partidos cada uno (parejo).")
        return
    maximo = max(conteos)
    minimo = min(conteos)
    sospechosos = [f["equipo"] for f in filas if f["partidos"] == maximo]
    print(f"  ⚠️  DESPAREJO -- min={minimo} max={maximo}. Sospechosos (máximo): {sospechosos}")
    print(f"  Esta temporada de LPF quedó con el fixture corrupto por la colisión de "
          f"nombres -- hay que regenerarla (borrar standings+matches de lpf/season_id="
          f"{season_id} y volver a correr esa promoción/temporada) DESPUÉS de aplicar "
          f"el rename. Avisame el resultado de este chequeo y lo resolvemos.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aplicar", action="store_true", help="Aplica el UPDATE (por default solo diagnostica).")
    args = parser.parse_args()

    with get_connection() as conn:
        with conn.cursor() as cur:
            d = _diagnosticar(cur)
            _imprimir_diagnostico(d)

            season_ids_lpf = sorted({f["season_id"] for f in d["standings"] if f["competition_slug"] == "lpf"})
            for season_id in season_ids_lpf:
                _diagnosticar_fixture_lpf(cur, season_id)

            if not args.aplicar:
                print('\nSolo diagnóstico (no se escribió nada). Correr con --aplicar para corregir.')
                return 0

            error = _validar_antes_de_aplicar(d)
            if error:
                print(f"\n❌ No se aplica el fix: {error}")
                return 1

            cur.execute("update teams set name = %s where name = %s", (NOMBRE_NUEVO, NOMBRE_VIEJO))
            conn.commit()
            print(f'\n✅ Renombrado: "{NOMBRE_VIEJO}" -> "{NOMBRE_NUEVO}" (1 fila en teams).')
            if season_ids_lpf:
                print(
                    f'\nOJO: este equipo tenía standings en lpf/season_id={season_ids_lpf} -- '
                    f'si el chequeo de fixture de arriba dio "DESPAREJO", esa temporada de LPF '
                    f'sigue corrupta (el rename no la arregla retroactivamente, solo evita que '
                    f'la corrupción se repita de acá en adelante). Avisame para limpiarla.'
                )
            return 0


if __name__ == "__main__":
    sys.exit(main())
