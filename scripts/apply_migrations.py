#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from db.client import database_schema, database_url

MIGRATIONS_DIR = ROOT / "supabase" / "migrations"


def main() -> None:
    schema = database_schema()
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        raise RuntimeError(f"No hay migraciones SQL en {MIGRATIONS_DIR}")

    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("create schema if not exists {}").format(sql.Identifier(schema)))
            cur.execute(sql.SQL("set search_path to {}").format(sql.Identifier(schema)))
            for path in migration_files:
                print(f"Aplicando {path.relative_to(ROOT)}...")
                cur.execute(path.read_text(encoding="utf-8"))
        conn.commit()

    print("Migraciones aplicadas.")


if __name__ == "__main__":
    main()

