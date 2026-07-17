# -*- coding: utf-8 -*-
"""Sigue a diagnosticar_duplicado_lpf.py: ya sabemos que zona A tiene 16
equipos (debería tener 15) y que hay dos equipos distintos en posición 1.
Esto lista TODA la zona A ordenada por posición para ver el choque
completo y decidir cuál fila sobra."""
from db.repository import repository


def main():
    repo = repository()
    season_id = repo.season_id("lpf")
    df = repo.standings_df("lpf")

    zona_a = df[df["zona"] == "A"].sort_values(["posicion", "equipo"])
    print(f"Zona A: {len(zona_a)} filas (debería haber 15)\n")
    print(zona_a.to_string(index=False))

    print("\n=== Filas en posición 1 de zona A (el choque) ===")
    print(zona_a[zona_a["posicion"] == 1].to_string(index=False))

    # También el team_id de cada una, por si dos apuntan al mismo club real
    # con nombres levemente distintos (alias sin normalizar).
    print("\n=== team_id + nombre de los equipos en posición 1 de zona A ===")
    rows = repo._execute(
        """
        select t.id, t.name, st.posicion, st.puntos, st.partidos_jugados
        from teams t
        join standings st on st.team_id = t.id
        where st.competition_slug = 'lpf' and st.season_id = %s
          and st.zona = 'A' and st.posicion = 1
        """,
        (season_id,),
    )
    for r in rows:
        print(dict(r))


if __name__ == "__main__":
    main()
