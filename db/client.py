# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

_SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class DatabaseConfigError(RuntimeError):
    pass


def database_url() -> str:
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise DatabaseConfigError(
            "Falta SUPABASE_DB_URL. La persistencia usa Supabase Postgres y no tiene fallback a CSV."
        )
    return url


def database_schema() -> str:
    schema = os.environ.get("SUPABASE_SCHEMA", "public")
    if not _SCHEMA_RE.match(schema):
        raise DatabaseConfigError(f"SUPABASE_SCHEMA inválido: {schema!r}")
    return schema


@contextmanager
def get_connection():
    conn = psycopg.connect(database_url(), row_factory=dict_row, prepare_threshold=None)
    try:
        schema = database_schema()
        with conn.cursor() as cur:
            cur.execute(f"set search_path to {schema}")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
