# -*- coding: utf-8 -*-
"""
mapeo_equipos_primerac.py

Traduce nombres de equipos entre:
  - el formato que usás en fixture_primerac.csv / resultados_primerac.csv /
    tabla_primerac.csv (nombres "locales", oficiales y completos)
  - el formato con el que Promiedos nombra a cada equipo (nombres "scrapeados",
    a veces abreviados o sin la desambiguación entre paréntesis)

IMPORTANTE - LEER ANTES DE USAR:
Primera C no tenía NINGÚN mapeo de nombres hasta ahora -- por eso
"Central Córdoba" (así, sin desambiguar) venía llegando de Promiedos y
nunca matcheaba contra "Central Córdoba (Rosario)" del fixture: los 19
partidos de ese equipo quedaban siempre en "sin_matchear". Ese alias
ESTÁ CONFIRMADO (viene directo de una actualización real reportada por
Pablo, 20/07/2026). El resto de los alias de este archivo son
ESTIMACIONES SIN CONFIRMAR -- se van completando a medida que aparezcan
en "sin_matchear" (ver instrucciones abajo).

Cómo se resuelve un nombre:
  1. Se normaliza (minúsculas, sin tildes, sin puntuación) tanto el nombre
     local como el nombre que vino de Promiedos.
  2. Si hay un OVERRIDE explícito para ese equipo, se usa esa lista de alias.
  3. Si no matchea nada, se usa fuzzy matching (difflib) con un umbral alto.
  4. Si tampoco matchea, se devuelve None y se loguea como "sin matchear"
     en vez de adivinar mal.

CÓMO VALIDAR/CORREGIR ESTE ARCHIVO:
  Cada vez que "Actualizar Resultados" en la web muestre partidos "sin
  identificar", la lista ya trae el nombre exacto que mandó Promiedos
  para cada equipo (equipo_local/equipo_visitante). Para cada nombre
  que no sea el mismo texto que en EQUIPOS_LOCALES, agregarlo a la
  lista de OVERRIDES del equipo correspondiente y volver a actualizar.
"""
import re
import unicodedata
from difflib import get_close_matches

# Nombres LOCALES tal cual están en fixture_primerac.csv / resultados_primerac.csv
# / tabla_primerac.csv (los 28 equipos de las 2 zonas de Primera C).
EQUIPOS_LOCALES = [
    # Zona A
    "Argentino Rosario", "CA Atlas", "CA Lugano", "Cañuelas",
    "Deportivo Español", "Deportivo Paraguayo", "El Porvenir",
    "General Lamadrid", "Justo José Urquiza", "Leones de Rosario FC",
    "Mercedes", "Muñiz", "Puerto Nuevo", "Sacachispas",
    # Zona B
    "Berazategui", "CA Fenix", "Central Ballester",
    "Central Córdoba (Rosario)", "Centro Español", "Claypole",
    "Club Luján", "Defensores Cambaceres", "Estrella del Sur",
    "Juventud Unida SM", "Leandro N. Alem", "Sportivo Barracas",
    "Victoriano Arenas", "Yupanqui",
]

# Alias que puede usar Promiedos para el mismo equipo.
OVERRIDES = {
    # Confirmado 20/07/2026: Promiedos manda "Central Córdoba" sin la
    # desambiguación -- en el sistema hay más de un "Central Córdoba"
    # (la Primera Nacional/Primera B tiene el de Santiago del Estero),
    # así que acá se guarda como "(Rosario)" para no colisionar.
    "Central Córdoba (Rosario)": ["central cordoba", "central cordoba rosario"],
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


def resolver_equipo(nombre_promiedos: str, umbral_fuzzy: float = 0.90):
    """
    Recibe un nombre tal como lo escupió el scraper de Promiedos y devuelve
    el nombre local canónico (el que usan tus CSVs de Primera C), o None
    si no hay match confiable.
    """
    norm = normalizar(nombre_promiedos)
    if not norm:
        return None

    # 1) match exacto contra el índice (locales + overrides)
    if norm in _INDICE:
        return _INDICE[norm]

    # 2) fuzzy matching como red de seguridad (para lo que no está en OVERRIDES)
    cercanos = get_close_matches(norm, _INDICE.keys(), n=1, cutoff=umbral_fuzzy)
    if cercanos:
        return _INDICE[cercanos[0]]

    return None


if __name__ == "__main__":
    # Prueba rápida manual: python mapeo_equipos_primerac.py "Central Cordoba"
    import sys
    if len(sys.argv) > 1:
        prueba = " ".join(sys.argv[1:])
        print(f"'{prueba}' -> {resolver_equipo(prueba)}")
    else:
        print(f"{len(EQUIPOS_LOCALES)} equipos locales cargados.")
