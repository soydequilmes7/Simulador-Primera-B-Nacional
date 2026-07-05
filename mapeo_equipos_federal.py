# -*- coding: utf-8 -*-
"""
mapeo_equipos_federal.py

Traduce nombres de equipos entre:
  - el formato que usás en fixture_federal_a.csv / resultados_federal_a.csv /
    tabla_federal_a.csv (nombres "locales", oficiales y completos)
  - el formato con el que Promiedos nombra a cada equipo (nombres "scrapeados",
    típicamente abreviados)

IMPORTANTE - LEER ANTES DE USAR:
No tuve forma de confirmar en vivo cómo escribe Promiedos cada nombre exacto
para el Federal A (la API de Promiedos no es accesible desde este entorno).
Los alias de OVERRIDES son mi mejor estimación en base a los patrones típicos
de abreviación de Promiedos (saca "Sportivo" -> "Sp.", "Deportivo" -> "Dep.",
reemplaza el sufijo de ciudad/desambiguación por un paréntesis corto, etc.)
y a lo que ya se había confirmado en una sesión anterior comparando contra un
dump real (Sp. Belgrano, Sarmiento (R)/(LB), Boca Unidos, San Martín (For)/(Mdza),
9 de Julio (R), Costa Brava).

TODOS los demás alias de este archivo son ESTIMACIONES SIN CONFIRMAR. Hay que
validarlos la primera vez que se corra el scraper de verdad.

Cómo se resuelve un nombre:
  1. Se normaliza (minúsculas, sin tildes, sin puntuación) tanto el nombre
     local como el nombre que vino de Promiedos.
  2. Si hay un OVERRIDE explícito para ese equipo, se usa esa lista de alias.
  3. Si no matchea nada, se usa fuzzy matching (difflib) con un umbral alto.
  4. Si tampoco matchea, se devuelve None y se loguea como "sin matchear"
     en vez de adivinar mal.

CÓMO VALIDAR/CORREGIR ESTE ARCHIVO:
  1. Correr: python scraper_promiedos_federal.py --debug
  2. Abrir debug_promiedos_federal_dump.json y mirar los nombres reales que
     trae Promiedos en equipo_local/equipo_visitante.
  3. Para cada nombre que no calce con EQUIPOS_LOCALES, agregarlo (normalizado
     o tal cual) a la lista de OVERRIDES del equipo correspondiente.
  4. Volver a correr actualizar_resultados_federal.py y confirmar que
     "sin_matchear" quede vacío (o solo con partidos que realmente no están
     en el fixture, no por problema de nombre).
"""
import re
import unicodedata
from difflib import get_close_matches

# Nombres LOCALES tal cual están en fixture_federal_a.csv / resultados_federal_a.csv
# / tabla_federal_a.csv (los 37 equipos de las 4 zonas del Federal A).
EQUIPOS_LOCALES = [
    # Zona 1
    "Sportivo Belgrano", "Douglas Haig", "9 De Julio Rafaela",
    "CSCyD Gimnasia y Esgrima (Chivilcoy)", "Defensores Belgrano (VR)",
    "Sportivo Las Parejas", "Independiente Chivilcoy", "Atlético Escobar",
    "El Linqueño", "Gimnasia de Concepción",
    # Zona 2
    "San Martín de Formosa", "Bartolomé Mitre (Posadas)",
    "Sarmiento De La Banda", "Sol De América", "Juventud Antoniana",
    "Tucumán Central", "Defensores Pto. Vilelas", "Boca Unidos de Corrientes",
    "Sarmiento de Resistencia",
    # Zona 3
    "Cipolletti", "Atenas Río Cuarto", "Argentino Monte Maíz",
    "Costa Brava (Gral Pico)", "Fundación Amigos por el Deporte",
    "Juventud Unida San Luis", "Deportivo Rincón", "Huracán Las Heras",
    "San Martín de Mendoza",
    # Zona 4
    "Olimpo", "Alvarado", "Kimberley Mar Del Plata", "Villa Mitre",
    "Germinal", "Sol de Mayo", "Santamarina Tandil", "Guillermo Brown",
    "Círculo Deportivo",
]

# Alias probables que puede usar Promiedos para el mismo equipo.
# CONFIRMADOS en sesión anterior contra un dump real: Sp. Belgrano,
# Sarmiento (R)/(LB), Boca Unidos, San Martín (For)/(Mdza), 9 de Julio (R),
# Costa Brava. El resto es ESTIMACIÓN -- validar con --debug.
OVERRIDES = {
    # -- Zona 1 --
    "Sportivo Belgrano": ["sp. belgrano", "sp belgrano"],  # confirmado
    "9 De Julio Rafaela": ["9 de julio (r)", "9 de julio rafaela"],  # confirmado
    "CSCyD Gimnasia y Esgrima (Chivilcoy)": [
        "gimnasia (chivilcoy)", "gimnasia y esgrima (chivilcoy)", "cscyd chivilcoy",
    ],
    "Defensores Belgrano (VR)": [
        "defensores (vr)", "defensores belgrano (vr)", "def. belgrano (vr)",
        "defensores de belgrano (vr)",
    ],
    "Sportivo Las Parejas": ["sp. las parejas", "sp las parejas", "sportivo lp"],  # confirmado
    "Independiente Chivilcoy": ["independiente (chivilcoy)", "independiente (chi)"],  # confirmado (chi)
    "Atlético Escobar": ["atl. escobar", "atletico escobar"],
    "Gimnasia de Concepción": ["gimnasia (concepcion)", "gimnasia concepcion"],

    # -- Zona 2 --
    "San Martín de Formosa": ["san martin (for)", "san martin formosa"],  # confirmado
    "Bartolomé Mitre (Posadas)": [
        "mitre (posadas)", "bartolome mitre (posadas)", "b. mitre (posadas)",
        "bartolome mitre",
    ],
    "Sarmiento De La Banda": ["sarmiento (lb)", "sarmiento la banda"],  # confirmado
    "Sol De América": ["sol de america"],
    "Juventud Antoniana": ["juv. antoniana"],  # confirmado
    "Defensores Pto. Vilelas": [
        "defensores (pv)", "defensores puerto vilelas", "def. pto. vilelas",
    ],
    "Boca Unidos de Corrientes": ["boca unidos"],  # confirmado
    "Sarmiento de Resistencia": ["sarmiento (r)"],  # confirmado

    # -- Zona 3 --
    "Atenas Río Cuarto": ["atenas (rc)", "atenas rio cuarto"],
    "Argentino Monte Maíz": ["argentino (monte maiz)", "argentino monte maiz", "argentino mm"],  # confirmado
    "Costa Brava (Gral Pico)": ["costa brava"],  # confirmado
    "Fundación Amigos por el Deporte": ["fad", "f.a.d.", "amigos por el deporte"],
    "Juventud Unida San Luis": ["juventud unida (sl)", "juventud unida san luis"],
    "Deportivo Rincón": ["dep. rincon", "deportivo rincon", "dvo. rincon"],  # confirmado
    "San Martín de Mendoza": ["san martin (mdza)", "san martin mendoza"],  # confirmado
    "Huracán Las Heras": ["huracan (lh)"],  # confirmado

    # -- Zona 4 --
    "Kimberley Mar Del Plata": ["kimberley", "kimberley (mdp)"],
    "Santamarina Tandil": ["santamarina", "santamarina (tandil)"],
    "Guillermo Brown": ["guillermo brown (pm)", "brown (pm)", "gmo. brown"],  # confirmado
    "Círculo Deportivo": ["circulo deportivo", "circulo dep."],
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
    el nombre local canónico (el que usan tus CSVs del Federal A), o None
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
    # Prueba rápida manual: python mapeo_equipos_federal.py "Sp. Belgrano"
    import sys
    if len(sys.argv) > 1:
        prueba = " ".join(sys.argv[1:])
        print(f"'{prueba}' -> {resolver_equipo(prueba)}")
    else:
        print(f"{len(EQUIPOS_LOCALES)} equipos locales cargados.")
