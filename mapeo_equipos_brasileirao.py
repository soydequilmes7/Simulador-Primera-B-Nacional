# -*- coding: utf-8 -*-
"""
mapeo_equipos_brasileirao.py

Traduce nombres de equipo del Brasileirão Série A entre:
  - el formato "local" que usan tabla_brasileirao.csv / fixture_brasileirao.csv /
    resultados_brasileirao.csv (y, si corresponde, la tabla `teams` en Supabase)
  - el formato con el que la API de Promiedos nombra a cada equipo en cada
    respuesta -- que NO es estable en el tiempo. Confirmado con datos reales
    de esta temporada: la misma API devolvió "Vasco da Gama" en el fixture
    generado al inicio del torneo y "Vasco Da Gama" en los resultados
    scrapeados más adelante; lo mismo con "Red Bull Bragantino" vs.
    "Bragantino" (el sponsor a veces se omite).

A diferencia de Primera Nacional (mapeo_equipos.py) o Federal A
(mapeo_equipos_federal.py), este módulo no existía todavía -- por eso el
scraper de Brasileirão (scraper_promiedos_brasileirao.py) guardaba los
nombres tal cual los devolvía Promiedos en cada corrida, sin pasarlos por
ningún canonicalizador. Como `teams.name` en Supabase es único mediante un
INSERT ... ON CONFLICT (name) case-sensitive (ver repository.py,
_ensure_teams_bulk), dos variantes de mayúsculas/minúsculas para el mismo
club no chocan como "ya existe" sino que crean una fila NUEVA -- de ahí el
KeyError al simular: self.equipos se arma con la clave de la tabla
("Vasco da Gama") pero el fixture trae la otra variante ("Vasco Da Gama"),
que no está en el diccionario.

Cómo se resuelve un nombre:
  1. Se normaliza (minúsculas, sin tildes, sin puntuación) tanto el nombre
     local como el nombre que vino de Promiedos. Esto ya resuelve solo las
     diferencias de mayúsculas/minúsculas (p.ej. "Vasco Da Gama" == "vasco
     da gama" == "Vasco da Gama" normalizado).
  2. Si hay un OVERRIDE explícito para ese equipo (nombres realmente
     distintos, no solo de capitalización -- p.ej. con/sin sponsor), se usa
     esa lista de alias.
  3. Si no matchea nada, fuzzy matching (difflib) con un umbral alto como
     red de seguridad.
  4. Si tampoco matchea, se devuelve None y el scraper debe loguearlo como
     "sin matchear" en vez de guardar el nombre crudo sin avisar -- ese
     silencio es justamente lo que permitió que este bug pasara
     desapercibido.

CÓMO EXTENDER ESTE ARCHIVO:
Si aparece un partido "sin matchear", agregar el nombre que trajo Promiedos
a OVERRIDES del equipo correspondiente y volver a correr el scraper.
"""
import re
import unicodedata
from difflib import get_close_matches

# Nombres LOCALES tal cual están en tabla_brasileirao.csv / fixture_brasileirao.csv
# / resultados_brasileirao.csv (los 20 equipos de la temporada 2026).
EQUIPOS_LOCALES = [
    "Athletico Paranaense", "Atlético Mineiro", "Bahia", "Botafogo",
    "Chapecoense", "Corinthians", "Coritiba", "Cruzeiro", "Flamengo",
    "Fluminense", "Grêmio", "Internacional", "Mirassol", "Palmeiras",
    "Red Bull Bragantino", "Remo", "Santos", "São Paulo", "Vasco da Gama",
    "Vitória",
]

# Alias confirmados contra datos reales (fixture y resultados scrapeados de
# Promiedos en esta misma temporada) o muy probables por cómo suele
# abreviar Promiedos a estos clubes. Las diferencias de may/min ("Vasco Da
# Gama") NO hace falta listarlas acá: normalizar() ya las resuelve.
OVERRIDES = {
    "Red Bull Bragantino": ["bragantino"],  # confirmado (resultados_brasileirao.csv)
    "Athletico Paranaense": ["athletico-pr", "athletico pr", "furacao"],
    "Atlético Mineiro": ["atletico-mg", "atletico mg", "atlético-mg", "galo"],
    "Grêmio": ["gremio"],
    "São Paulo": ["sao paulo", "spfc"],
    "Internacional": ["inter"],
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
    Recibe un nombre tal como lo escupió Promiedos y devuelve el nombre
    local canónico (el que usan los CSV/la tabla `teams`), o None si no
    hay match confiable.
    """
    norm = normalizar(nombre_promiedos)
    if not norm:
        return None

    # 1) match exacto contra el índice (locales + overrides). Esto ya
    #    cubre "Vasco Da Gama" -> "Vasco da Gama" solo por normalizar().
    if norm in _INDICE:
        return _INDICE[norm]

    # 2) fuzzy matching como red de seguridad
    cercanos = get_close_matches(norm, _INDICE.keys(), n=1, cutoff=umbral_fuzzy)
    if cercanos:
        return _INDICE[cercanos[0]]

    return None


if __name__ == "__main__":
    # Prueba rápida manual: python mapeo_equipos_brasileirao.py "Vasco Da Gama"
    import sys
    if len(sys.argv) > 1:
        prueba = " ".join(sys.argv[1:])
        print(f"'{prueba}' -> {resolver_equipo(prueba)}")
    else:
        print(f"{len(EQUIPOS_LOCALES)} equipos locales cargados.")
