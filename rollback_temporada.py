# -*- coding: utf-8 -*-
"""
rollback_temporada.py

Versión genérica de rollback_lpf_2027.py (que tenía los season_id
249/7 hardcodeados a mano para un incidente puntual y ya no sirve tal
cual -- este reemplaza esa necesidad de forma reusable).

Deshace un "Generar temporada siguiente" que quedó a mitad de camino:
UNA división avanzó de season_id y activó su temporada nueva, pero el
resto se quedó atrás -- eso es lo que genera "Club duplicado entre
divisiones" en ClubRegistry.build_from_current_data() (el mismo club
aparece "activo" en dos divisiones a la vez).

Este script SOLO cambia la columna `active` de `seasons` para UNA
competencia: desactiva la temporada que avanzó de más, reactiva la
anterior. NO toca standings ni matches -- esos datos de la temporada
que se desactiva quedan en la base tal cual (por si hace falta
revisarlos o reusarlos), simplemente dejan de ser "la temporada
activa" que lee league_data().

Pide confirmación explícita antes de escribir nada.

Uso:
    python diagnostico_temporadas.py                       # para ver los season_id disponibles
    python rollback_temporada.py <slug> <season_id_reactivar>

Ejemplo (el caso real que motivó este script):
    python rollback_temporada.py lpf 6
"""
from __future__ import annotations

import sys

from db.client import get_connection


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 1

    slug = sys.argv[1]
    try:
        season_id_reactivar = int(sys.argv[2])
    except ValueError:
        print(f"season_id inválido: {sys.argv[2]!r} (tiene que ser un entero)")
        return 1

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select id, name, active from seasons where competition_slug = %s order by id",
                (slug,),
            )
            temporadas = cur.fetchall()
            if not temporadas:
                print(f"No hay ninguna temporada para competition_slug={slug!r}.")
                return 1

            print(f"Estado actual de las temporadas de {slug!r}:")
            for fila in temporadas:
                marca = "*" if fila["active"] else " "
                print(f"  [{marca}] season_id={fila['id']}  name={fila['name']!r}")

            if not any(f["id"] == season_id_reactivar for f in temporadas):
                print(f"\nseason_id={season_id_reactivar} no existe para {slug!r}. Nada para hacer.")
                return 1

            activa_actual = next((f for f in temporadas if f["active"]), None)
            if activa_actual is None:
                print(f"\n⚠️  {slug!r} no tiene NINGUNA temporada activa hoy (raro). "
                      f"Se va a activar season_id={season_id_reactivar} igual.")
            elif activa_actual["id"] == season_id_reactivar:
                print(f"\nseason_id={season_id_reactivar} YA es la activa. No hay nada que hacer.")
                return 0

            print(f"\nEste script va a:")
            if activa_actual is not None:
                print(f"  1) Desactivar season_id={activa_actual['id']} ({activa_actual['name']!r})")
            print(f"  2) Reactivar season_id={season_id_reactivar}")
            print("No toca standings/matches -- solo la columna 'active' de seasons.")
            respuesta = input("\n¿Confirmás? (escribí 'si' para continuar): ").strip().lower()
            if respuesta != "si":
                print("Cancelado, no se tocó nada.")
                return 0

            if activa_actual is not None:
                cur.execute(
                    "update seasons set active = false where id = %s and competition_slug = %s",
                    (activa_actual["id"], slug),
                )
            cur.execute(
                "update seasons set active = true where id = %s and competition_slug = %s",
                (season_id_reactivar, slug),
            )
            conn.commit()

            print()
            cur.execute(
                "select id, name, active from seasons where competition_slug = %s order by id",
                (slug,),
            )
            print("Estado final:")
            for fila in cur.fetchall():
                marca = "*" if fila["active"] else " "
                print(f"  [{marca}] season_id={fila['id']}  name={fila['name']!r}")
            return 0


if __name__ == "__main__":
    sys.exit(main())
