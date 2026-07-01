# -*- coding: utf-8 -*-
"""
rutas.py

Resuelve dónde leer/escribir los archivos de datos según el entorno:

- Local (servidor.py, CLI): lee y escribe directo en la carpeta del
  repo, como siempre.
- Vercel Functions: el filesystem del deploy es de solo lectura, así
  que cualquier escritura (fixture.csv, resultados.csv, goleadores.csv,
  tabla.csv, log_actualizaciones.json) se redirige a /tmp, sembrado con
  una copia de datos/ la primera vez que se necesita.

IMPORTANTE - limitación de /tmp en Vercel: no persiste entre cold
starts, no se comparte entre instancias, y se pierde en cada nuevo
deploy. O sea, /api/actualizar funciona de punta a punta (scrapea,
actualiza tabla/goleadores, re-simula) dentro de la misma instancia
tibia, pero no es una base de datos durable. Para que los cambios
sobrevivan hace falta correr actualizar_resultados.py en algún lado con
filesystem persistente (local, o un job de CI que commitee los CSV
actualizados) o migrar estos CSV a una base de datos real.
"""
import os
import shutil
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent


def en_vercel() -> bool:
    return bool(os.environ.get("VERCEL"))


def base_escribible() -> Path:
    return Path("/tmp") if en_vercel() else REPO_DIR


def datos_dir() -> Path:
    """Carpeta datos/ activa: la del repo en local, o una copia en /tmp
    (creada la primera vez que se pide) cuando corre como Vercel Function."""
    destino = base_escribible() / "datos"
    if en_vercel() and not destino.exists():
        shutil.copytree(REPO_DIR / "datos", destino)
    return destino


def log_path() -> Path:
    return base_escribible() / "log_actualizaciones.json"
