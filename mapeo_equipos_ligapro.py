# -*- coding: utf-8 -*-
"""
mapeo_equipos_ligapro.py

Traduce nombres de equipo de LigaPro Serie A (Ecuador) entre:
  - el formato "local" que usan tabla_ligapro.csv / fixture_ligapro.csv /
    resultados_ligapro.csv (y, si corresponde, la tabla `teams` en Supabase)
  - el formato con el que ligapro.ec / Promiedos nombran a cada equipo, que
    suele usar la razón social completa ("Club Sport Emelec", "CSD
    Independiente del Valle", "Liga Deportiva Universitaria de Quito",
    "Sociedad Deportivo Quito"...) o abreviaturas de uso común en la
    cobertura periodística ("Ind. del Valle", "U. Católica", "Guayaquil
    City FC").

Calcado de mapeo_equipos_brasileirao.py -- mismo patrón de normalización +
overrides + fuzzy matching como red de seguridad.

CÓMO EXTENDER ESTE ARCHIVO:
Si aparece un partido "sin matchear" al correr el scraper, agregar el
nombre que trajo la fuente a OVERRIDES del equipo correspondiente.
"""
import re
import unicodedata
from difflib import get_close_matches

# Nombres LOCALES tal cual están en tabla_ligapro.csv / fixture_ligapro.csv
# / resultados_ligapro.csv -- los 16 equipos de la Serie A 2026, según el
# cuadro de participantes confirmado por LigaPro (temporada 2026).
EQUIPOS_LOCALES = [
    "Aucas", "Barcelona", "Delfín", "Deportivo Cuenca", "Emelec",
    "Guayaquil City", "Independiente del Valle", "LDU Quito", "Leones",
    "Libertad", "Macará", "Manta", "Mushuc Runa", "Orense",
    "Técnico Universitario", "Universidad Católica",
]

# Alias / razones sociales completas y abreviaturas de uso habitual en
# medios ecuatorianos (Primicias, Ecuavisa, Studio Fútbol, ESPN, Promiedos).
OVERRIDES = {
    "Aucas": ["sd aucas", "cd aucas", "club social y deportivo aucas"],
    "Barcelona": ["barcelona sc", "barcelona sporting club", "bsc", "idolo"],
    "Delfín": ["delfin sc", "delfin sporting club"],
    "Deportivo Cuenca": ["cd cuenca", "dep cuenca", "club deportivo cuenca"],
    "Emelec": ["club sport emelec", "cs emelec", "bombillo"],
    "Guayaquil City": ["guayaquil city fc", "guayaquil city futbol club"],
    "Independiente del Valle": [
        "csd independiente del valle", "ind del valle", "ind. del valle", "idv",
    ],
    "LDU Quito": [
        "liga deportiva universitaria de quito", "liga de quito", "ldu",
        "l.d.u. quito",
    ],
    "Leones": ["leones fc", "leones del norte", "leones futbol club"],
    "Libertad": ["libertad fc", "club deportivo libertad", "libertad futbol club"],
    "Macará": ["cd macara", "club deportivo macara", "macara"],
    "Manta": ["manta fc", "club deportivo manta"],
    "Mushuc Runa": ["mushuc runa sc", "mushuc runa sporting club"],
    "Orense": ["orense sc", "orense sporting club"],
    "Técnico Universitario": [
        "cd tecnico universitario", "tecnico universitario", "tecnico u",
    ],
    "Universidad Católica": [
        "u catolica", "u. catolica", "universidad catolica del ecuador",
        "catolica",
    ],
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
    candidatos = {normalizar(nombre_local)}
    for alias in OVERRIDES.get(nombre_local, []):
        candidatos.add(normalizar(alias))
    return candidatos


_INDICE = {}
for _local in EQUIPOS_LOCALES:
    for _cand in _candidatos(_local):
        _INDICE[_cand] = _local


def resolver_equipo(nombre_fuente: str, umbral_fuzzy: float = 0.90):
    """Recibe un nombre tal como lo trajo la fuente externa (ligapro.ec,
    Promiedos, etc.) y devuelve el nombre local canónico, o None si no hay
    match confiable."""
    norm = normalizar(nombre_fuente)
    if not norm:
        return None

    if norm in _INDICE:
        return _INDICE[norm]

    cercanos = get_close_matches(norm, _INDICE.keys(), n=1, cutoff=umbral_fuzzy)
    if cercanos:
        return _INDICE[cercanos[0]]

    return None


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        prueba = " ".join(sys.argv[1:])
        print(f"'{prueba}' -> {resolver_equipo(prueba)}")
    else:
        print(f"{len(EQUIPOS_LOCALES)} equipos locales cargados.")
