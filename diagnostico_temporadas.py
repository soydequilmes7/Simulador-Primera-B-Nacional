# -*- coding: utf-8 -*-
"""
diagnostico_temporadas.py

Muestra, para las 6 competencias, todas las temporadas (`seasons`) que
existen y cuál está marcada `active`. Pensado para detectar el patrón
recurrente de "Generar temporada siguiente" a medio camino: una
división avanza de season_id y las demás se quedan atrás, y
ClubRegistry.build_from_current_data() (que arma el roster leyendo LA
TEMPORADA ACTIVA de cada división) termina viendo el mismo club en dos
divisiones a la vez -- el error "Club duplicado entre divisiones".

También muestra, para la temporada activa de cada división, si el
fixture está parejo (todos los equipos con la misma cantidad de
partidos) -- mismo chequeo que ya hace fix_nombre_estudiantes_caseros.py
para LPF, generalizado a las 5 divisiones con fixture propio (Copa
Argentina no tiene "fixture por zona", se excluye).

Uso: python diagnostico_temporadas.py
"""
from __future__ import annotations

from db.client import get_connection

COMPETENCIAS = ["lpf", "nacional", "bmetro", "federal_a", "primerac", "copa"]
COMPETENCIAS_CON_FIXTURE_PAREJO = ["lpf", "nacional", "bmetro", "federal_a", "primerac"]


def _temporadas_por_competencia(cur) -> dict[str, list[dict]]:
    resultado: dict[str, list[dict]] = {}
    for slug in COMPETENCIAS:
        cur.execute(
            "select id, name, active from seasons where competition_slug = %s order by id",
            (slug,),
        )
        resultado[slug] = cur.fetchall()
    return resultado


def _chequear_fixture_parejo(cur, slug: str, season_id: int) -> None:
    cur.execute(
        """
        select t.name as equipo, count(*) as partidos
        from matches m
        join teams t on t.id in (m.equipo_local_id, m.equipo_visitante_id)
        where m.competition_slug = %s and m.season_id = %s
        group by t.name
        order by partidos desc, equipo
        """,
        (slug, season_id),
    )
    filas = cur.fetchall()
    if not filas:
        print(f"      fixture: (sin partidos cargados)")
        return
    conteos = {f["partidos"] for f in filas}
    if len(conteos) == 1:
        print(f"      fixture: OK -- {len(filas)} equipos, {conteos.pop()} partidos c/u")
        return
    maximo, minimo = max(conteos), min(conteos)
    sospechosos = [f["equipo"] for f in filas if f["partidos"] == maximo]
    print(f"      fixture: ⚠️  DESPAREJO -- min={minimo} max={maximo} -- sospechosos: {sospechosos}")


def _buscar_duplicados_entre_divisiones(cur, activas: dict[str, int]) -> None:
    """Mismo chequeo que ClubRegistry.build_from_current_data(), pero
    de solo lectura acá: ¿algún nombre de equipo aparece en standings
    de más de una división, ambas en su temporada activa?"""
    vistos: dict[str, str] = {}
    duplicados = []
    for slug, season_id in activas.items():
        if slug == "copa":
            continue
        cur.execute(
            "select distinct t.name as equipo from standings st join teams t on t.id = st.team_id "
            "where st.competition_slug = %s and st.season_id = %s",
            (slug, season_id),
        )
        for fila in cur.fetchall():
            nombre = fila["equipo"]
            if nombre in vistos and vistos[nombre] != slug:
                duplicados.append((nombre, vistos[nombre], slug))
            else:
                vistos[nombre] = slug

    print("\n" + "=" * 70)
    if not duplicados:
        print("Sin clubes duplicados entre divisiones activas. Todo consistente.")
    else:
        print(f"⚠️  {len(duplicados)} club(es) duplicado(s) entre divisiones activas:")
        for nombre, div_a, div_b in duplicados:
            print(f"  '{nombre}' aparece en '{div_a}' y en '{div_b}' (temporadas activas)")
    print("=" * 70)


def main() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            temporadas = _temporadas_por_competencia(cur)
            activas: dict[str, int] = {}

            for slug in COMPETENCIAS:
                print(f"\n{slug}:")
                for fila in temporadas[slug]:
                    marca = "*" if fila["active"] else " "
                    print(f"  [{marca}] season_id={fila['id']}  name={fila['name']!r}")
                    if fila["active"]:
                        activas[slug] = fila["id"]
                if slug in COMPETENCIAS_CON_FIXTURE_PAREJO and slug in activas:
                    _chequear_fixture_parejo(cur, slug, activas[slug])

            _buscar_duplicados_entre_divisiones(cur, activas)


if __name__ == "__main__":
    main()
