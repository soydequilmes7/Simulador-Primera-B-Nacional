# -*- coding: utf-8 -*-
"""
rutas.py

Helpers de rutas del repo.

La persistencia runtime vive en Supabase Postgres. Estos paths se usan
solo para servir assets estáticos, para el script de seed que lee los CSV
commiteados, y para el filesystem virtual de Pyodide en el navegador.
"""
import os
import shutil
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent


def en_vercel() -> bool:
    return bool(os.environ.get("VERCEL"))


def en_render() -> bool:
    return bool(os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID"))


def base_escribible() -> Path:
    return REPO_DIR


def _sembrar_directorio(nombre: str) -> Path:
    base = base_escribible()
    if base == REPO_DIR:
        return REPO_DIR / nombre

    destino = base / nombre
    if not destino.exists():
        origen = REPO_DIR / nombre
        destino.parent.mkdir(parents=True, exist_ok=True)
        if origen.exists():
            shutil.copytree(origen, destino)
        else:
            destino.mkdir(parents=True, exist_ok=True)
    return destino


def datos_dir() -> Path:
    """Carpeta datos/ activa."""
    return _sembrar_directorio("datos")


def public_dir() -> Path:
    """Carpeta public/ activa para estáticos y JSON generados."""
    return _sembrar_directorio("public")


def log_path() -> Path:
    return REPO_DIR / "log_actualizaciones.json"
