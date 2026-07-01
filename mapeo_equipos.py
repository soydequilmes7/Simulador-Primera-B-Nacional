# -*- coding: utf-8 -*-
"""
mapeo_equipos.py

Traduce nombres de equipos entre:
  - el formato que usás en fixture.csv / resultados.csv (nombres "locales")
  - el formato con el que Promiedos nombra a cada equipo (nombres "scrapeados")

IMPORTANTE - LEER ANTES DE USAR:
No tuve forma de verificar en vivo cómo escribe Promiedos cada nombre exacto
(su sitio nuevo es una app JS y no pude inspeccionar las respuestas reales
desde este entorno). Los nombres en OVERRIDES de abajo son mi mejor estimación
en base a los nombres habituales de estos clubes, PERO hay que confirmarlos
la primera vez que corras el scraper.

Cómo se resuelve un nombre:
  1. Se normaliza (minúsculas, sin tildes, sin puntuación) tanto el nombre
     local como el nombre que vino de Promiedos.
  2. Si hay un OVERRIDE explícito para ese equipo, se usa esa lista de alias.
  3. Si no matchea nada, se usa fuzzy matching (difflib) con un umbral alto.
  4. Si tampoco matchea, se devuelve None y se loguea como "sin matchear"
     en vez de adivinar mal.

Si algo no matchea, corré el scraper en modo debug (--debug), mirá
debug_promiedos_dump.json y agregá el alias que falte a OVERRIDES.
"""
import re
import unicodedata
from difflib import get_close_matches

# Nombres LOCALES tal cual están en fixture.csv / resultados.csv / tabla.csv
EQUIPOS_LOCALES = [
    "Acassuso", "Agropecuario", "All Boys", "Almagro", "Alte. Brown", "Atlanta",
    "Atlético Rafaela", "Bolivar", "CA Mitre", "Central Norte", "Chacarita",
    "Chaco For Ever", "Chicago", "Colegiales", "Colón", "Defensores",
    "Dep. Madryn", "Estudiantes", "Ferro", "Gimnasia (J)", "Gimnasia y Tiro",
    "Godoy Cruz", "Güemes", "Los Andes", "Maipú", "Midland", "Morón",
    "Patronato", "Quilmes", "Racing (Cba)", "San Martín", "San Martín (T)",
    "San Miguel", "San Telmo", "Temperley", "Tristan Suárez",
]

# alias conocidos / probables que puede usar Promiedos para el mismo equipo.
# ESTO HAY QUE VERIFICARLO - son mi mejor estimación, no un dato confirmado.
OVERRIDES = {
    "Alte. Brown": ["almirante brown"],
    "Atlético Rafaela": ["atletico rafaela", "atletico de rafaela", "rafaela"],
    "CA Mitre": ["mitre santiago del estero", "mitre (sde)", "mitre de santiago"],
    "Central Norte": ["central norte salta", "central norte (salta)"],
    "Chaco For Ever": ["for ever", "chaco for ever"],
    "Dep. Madryn": ["deportivo madryn"],
    "Gimnasia (J)": ["gimnasia y esgrima jujuy", "gimnasia jujuy"],
    "Gimnasia y Tiro": ["gimnasia y tiro salta", "gimnasia y tiro (salta)"],
    "Racing (Cba)": ["racing cordoba", "racing club cordoba", "racing (cordoba)"],
    "San Martín (T)": ["san martin tucuman", "san martin (tucuman)"],
    "San Martín": ["san martin sj", "san martin (sj)", "san martin san juan"],
    "Tristan Suárez": ["tristan suarez"],
}


def normalizar(nombre: str) -> str:
    """minusculas, sin tildes, sin puntuación, espacios simples."""
    if not nombre:
        return ""
    nfkd = unicodedata.normalize("NFKD", nombre)
    sin_tildes = "".join(c for c in nfkd if not unicodedata.combining(c))
    sin_tildes = sin_tildes.lower()
    sin_tildes = re.sub(r"[^a-z0-9()]+", " ", sin_tildes)
    return re.sub(r"\s+", " ", sin_tildes).strip()


def _candidatos(nombre_local: str):
    """Todas las formas normalizadas contra las que comparar un nombre local."""
    candidatos = {normalizar(nombre_local)}
    for alias in OVERRIDES.get(nombre_local, []):
        candidatos.add(normalizar(alias))
    return candidatos


# Índice: nombre normalizado (local o alias) -> nombre local canónico
_INDICE = {}
for _local in EQUIPOS_LOCALES:
    for _cand in _candidatos(_local):
        _INDICE[_cand] = _local


def resolver_equipo(nombre_promiedos: str, umbral_fuzzy: float = 0.82):
    """
    Recibe un nombre tal como lo escupió el scraper de Promiedos y devuelve
    el nombre local canónico (el que usan tus CSVs), o None si no hay
    match confiable.
    """
    norm = normalizar(nombre_promiedos)
    if not norm:
        return None

    # 1) match exacto contra el índice (locales + overrides)
    if norm in _INDICE:
        return _INDICE[norm]

    # 2) fuzzy matching como red de seguridad
    cercanos = get_close_matches(norm, _INDICE.keys(), n=1, cutoff=umbral_fuzzy)
    if cercanos:
        return _INDICE[cercanos[0]]

    return None


if __name__ == "__main__":
    # Prueba rápida manual: python mapeo_equipos.py "Deportivo Madryn"
    import sys
    if len(sys.argv) > 1:
        prueba = " ".join(sys.argv[1:])
        print(f"'{prueba}' -> {resolver_equipo(prueba)}")
    else:
        print(f"{len(EQUIPOS_LOCALES)} equipos locales cargados.")
