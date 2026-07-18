# -*- coding: utf-8 -*-
"""
reset_dimayor.py

Borra las filas de "dimayor" en Supabase (standings + matches) para
poder re-sembrarlas desde cero con los CSV corregidos -- necesario
porque la primera corrida de bootstrap_league_from_csv("dimayor") ya
insertó 3 nombres de equipo mal (Junior de Barranquilla, Inter de
Bogotá, Fortaleza CEIF) y bootstrap_league_from_csv() NO vuelve a
sembrar si ya hay filas.

Uso (una sola vez, antes de volver a correr el scraper/main):
    python reset_dimayor.py
"""
from db.client import get_connection

COMPETITION_SLUG = "dimayor"


def main():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from matches where competition_slug = %s", (COMPETITION_SLUG,))
            borrados_matches = cur.rowcount
            cur.execute("delete from standings where competition_slug = %s", (COMPETITION_SLUG,))
            borrados_standings = cur.rowcount

    print(f"Borradas {borrados_matches} fila(s) de matches y {borrados_standings} fila(s) de standings para '{COMPETITION_SLUG}'.")
    print("Ahora corré de nuevo: python scraper_promiedos_dimayor.py  y después  python main_dimayor.py")


if __name__ == "__main__":
    main()
