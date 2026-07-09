# -*- coding: utf-8 -*-
"""
rollback_lpf_2027.py

Deshace el "Generar temporada siguiente" que quedó a mitad de camino:
LPF terminó de crear y activar su temporada 2027 (season_id=249), pero
Nacional/B Metro/Primera C nunca llegaron a procesarse y se quedaron en
2026 -- eso es lo que generaba el club duplicado (Ferro/Morón en LPF Y
en Nacional a la vez).

Este script SOLO cambia la columna `active` de la tabla `seasons` para
LPF (desactiva season_id=249 "2027", reactiva season_id=7 "2026"). NO
toca standings ni matches -- esos datos de la 2027 quedan en la base tal
cual (por si hace falta reusarlos), simplemente dejan de ser "la
temporada activa" que lee league_data(). Es la operación mínima para
que las 5 divisiones vuelvan a estar todas en 2026 al mismo tiempo, sin
tocar ningún roster.

Pide confirmación explícita antes de escribir nada.

Uso: python rollback_lpf_2027.py
"""
from db.client import get_connection

SEASON_ID_LPF_2027 = 249
SEASON_ID_LPF_2026 = 7


def main():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select id, name, active from seasons where competition_slug = 'lpf' order by id"
            )
            print("Estado actual de las temporadas de LPF:")
            for fila in cur.fetchall():
                marca = "*" if fila["active"] else " "
                print(f"  [{marca}] season_id={fila['id']} temporada={fila['name']!r}")

            print()
            print(f"Este script va a:")
            print(f"  1) Desactivar season_id={SEASON_ID_LPF_2027} (LPF 2027)")
            print(f"  2) Reactivar season_id={SEASON_ID_LPF_2026} (LPF 2026)")
            print("No toca standings/matches -- solo la columna 'active' de seasons.")
            respuesta = input("\n¿Confirmás? (escribí 'si' para continuar): ").strip().lower()
            if respuesta != "si":
                print("Cancelado, no se tocó nada.")
                return

            cur.execute(
                "update seasons set active = false where id = %s and competition_slug = 'lpf'",
                (SEASON_ID_LPF_2027,),
            )
            cur.execute(
                "update seasons set active = true where id = %s and competition_slug = 'lpf'",
                (SEASON_ID_LPF_2026,),
            )
            conn.commit()

            print()
            cur.execute(
                "select id, name, active from seasons where competition_slug = 'lpf' order by id"
            )
            print("Estado final:")
            for fila in cur.fetchall():
                marca = "*" if fila["active"] else " "
                print(f"  [{marca}] season_id={fila['id']} temporada={fila['name']!r}")


if __name__ == "__main__":
    main()
