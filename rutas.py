# -*- coding: utf-8 -*-
"""
rutas.py

Resuelve dónde leer/escribir los archivos de datos según el entorno:

- Local (servidor.py, CLI): lee y escribe directo en la carpeta del repo.
- Render: lee y escribe en SIMULADOR_STATE_DIR (por default /var/data si
  está definida la variable RENDER), pensado para montar ahí un Persistent
  Disk. La primera vez copia datos/ y public/ desde el repo.
- Vercel Functions: mantiene el fallback viejo a /tmp, sembrado con una
  copia de datos/ la primera vez que se necesita.

IMPORTANTE - /tmp en Vercel no es durable. En Render, la persistencia real
depende de que SIMULADOR_STATE_DIR apunte a un Persistent Disk.
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
    configurada = os.environ.get("SIMULADOR_STATE_DIR")
    if configurada:
        return Path(configurada)
    if en_render():
        return Path("/var/data")
    if en_vercel():
        return Path("/tmp")
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
    base = base_escribible()
    if base != REPO_DIR:
        base.mkdir(parents=True, exist_ok=True)
    return base / "log_actualizaciones.json"
