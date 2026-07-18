# -*- coding: utf-8 -*-
"""
fix_standings_dimayor_team_ids.py

Repuntea las 3 filas de `standings` (competition_slug='dimayor') que
quedaron con el team_id VIEJO (de la siembra original mal hecha) hacia
el team_id CORRECTO -- que ya existe en `teams` (probablemente creado
por un reseed anterior del fixture), pero el reset de standings no
alcanzó a corregir.

Después de correr esto, borra las 3 filas huérfanas de `teams` (las
viejas), que ya no las va a referenciar nada.

Uso (una sola vez):
    python fix_standings_dimayor_team_ids.py
"""
from db.client import get_connection

# (team_id viejo, team_id correcto, nombre correcto -- solo para el print)
PARES = [
    (24114, 24118, "Junior FC"),
    (24112, 24119, "Internacional de Bogotá"),
    (24109, 24120, "Fortaleza FC"),
]

with get_connection() as conn:
    with conn.cursor() as cur:
        print("=" * 60)
        print("1) Repuntando standings al team_id correcto")
        print("=" * 60)
        for viejo, correcto, nombre in PARES:
            cur.execute(
                """
                update standings
                set team_id = %s, updated_at = now()
                where competition_slug = 'dimayor' and team_id = %s
                """,
                (correcto, viejo),
            )
            print(f"  {nombre}: {cur.rowcount} fila(s) actualizada(s) ({viejo} -> {correcto})")

        print()
        print("=" * 60)
        print("2) Verificando que no quede nada más apuntando a los team_id viejos")
        print("=" * 60)
        viejos = [p[0] for p in PARES]
        for tabla in ("standings", "club_ratings", "scorer_totals"):
            cur.execute(f"select count(*) as n from {tabla} where team_id = any(%s)", (viejos,))
            n = cur.fetchone()["n"]
            print(f"  {tabla}: {n} fila(s) restante(s) con team_id viejo")

        cur.execute(
            "select count(*) as n from matches where equipo_local_id = any(%s) or equipo_visitante_id = any(%s)",
            (viejos, viejos),
        )
        n_matches = cur.fetchone()["n"]
        print(f"  matches: {n_matches} fila(s) restante(s) con team_id viejo")

        cur.execute("select count(*) as n from standings where team_id = any(%s)", (viejos,))
        n_standings_restantes = cur.fetchone()["n"]

        print()
        print("=" * 60)
        print("3) Borrando las 3 filas huérfanas de `teams` (nombres viejos)")
        print("=" * 60)
        if n_matches or n_standings_restantes:
            print(
                "  SALTEADO: todavía hay filas en otra tabla apuntando a estos "
                "team_id -- no se borra nada para no romper una foreign key. "
                "Revisá el detalle de arriba."
            )
        else:
            cur.execute("delete from teams where id = any(%s)", (viejos,))
            print(f"  Borradas {cur.rowcount} fila(s) de teams.")

print("\nListo. Corré de nuevo: python main_dimayor.py")
