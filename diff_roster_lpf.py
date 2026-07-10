# -*- coding: utf-8 -*-
"""
diff_roster_lpf.py

Compara el roster de 30 equipos que datos/tablalpf.csv dice que
DEBERÍA tener LPF (el real, ya jugado -- el mismo que usa
estadisticas_lpf._validar_datos_lpf() para exigir "exactamente 30")
contra lo que hoy está persistido en Supabase para la temporada activa
de LPF.

Objetivo: confirmar si "Estudiantes (Caseros)" es un ascenso fantasma
que quedó de una corrida de /api/season/generate-next que nunca se
completó del todo (LPF avanzó, Nacional no -- mismo patrón que
Ferro/Morón, ver rollback_lpf_2027.py), en cuyo caso hay que sacarlo
de LPF (standings + matches), NO tocar Nacional (que tiene la
posición de tabla real, con partidos jugados de verdad).

Uso: python diff_roster_lpf.py
"""
from __future__ import annotations

import pandas as pd

from db.client import get_connection
from modelos.estadisticas_lpf import normalizar


def _roster_real_esperado() -> set[str]:
    df = pd.read_csv("datos/tablalpf.csv", encoding="utf-8")
    return {normalizar(e) for e in df["equipo"]}


def main() -> None:
    esperado = _roster_real_esperado()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select id, active, name from seasons where competition_slug = 'lpf' order by id"
            )
            temporadas = cur.fetchall()
            print("Temporadas de LPF:")
            for fila in temporadas:
                marca = "*" if fila["active"] else " "
                print(f"  [{marca}] season_id={fila['id']}  name={fila['name']!r}")

            season_id_activa = next((f["id"] for f in temporadas if f["active"]), None)
            if season_id_activa is None:
                print("\nNo hay ninguna temporada activa para lpf. Nada para comparar.")
                return

            cur.execute(
                """
                select t.name as equipo, st.zona, st.posicion, st.partidos_jugados
                from standings st join teams t on t.id = st.team_id
                where st.competition_slug = 'lpf' and st.season_id = %s
                order by t.name
                """,
                (season_id_activa,),
            )
            filas = cur.fetchall()
            actual = {f["equipo"] for f in filas}

            print(f"\nRoster real esperado (tablalpf.csv): {len(esperado)} equipos")
            print(f"Roster en Supabase (lpf/season_id={season_id_activa}): {len(actual)} equipos")

            solo_en_db = sorted(actual - esperado)
            solo_en_csv = sorted(esperado - actual)

            print(f"\nEn Supabase pero NO en el roster real esperado ({len(solo_en_db)}):")
            for nombre in solo_en_db:
                fila = next(f for f in filas if f["equipo"] == nombre)
                print(f"  '{nombre}'  zona={fila['zona']}  posicion={fila['posicion']}  "
                      f"partidos_jugados={fila['partidos_jugados']}")

            print(f"\nEn el roster real esperado pero NO en Supabase ({len(solo_en_csv)}):")
            for nombre in solo_en_csv:
                print(f"  '{nombre}'")

            if not solo_en_db and not solo_en_csv:
                print("\n✅ Coincide exacto -- el roster de LPF en Supabase es el real, sin sorpresas.")


if __name__ == "__main__":
    main()
