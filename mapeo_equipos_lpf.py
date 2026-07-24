# -*- coding: utf-8 -*-
"""
mapeo_equipos_lpf.py

Traduce nombres de equipos entre:
  - el formato COMPLETO que usás en fixture_lpf.csv / resultados_lpf.csv /
    promedios_lpf.csv, y con el que responde el scraper de Promiedos
    (nombres "canónicos", ej. "Sarmiento Junín", "Argentinos Juniors")
  - el formato CORTO/abreviado que tiene datos/tablalpf.csv (y por lo
    tanto la tabla de standings sembrada en Supabase vía seed_supabase.py),
    ej. "Sarmiento", "Argentinos"

POR QUÉ EXISTE:
A diferencia de Nacional/Federal (donde el "desconocido" es Promiedos),
acá el problema es al revés: fixture_lpf.csv y el scraper YA coinciden
entre sí (por eso el matcheo contra el fixture pendiente nunca falla),
pero datos/tablalpf.csv -- que es lo que se usó para poblar el standings
de Supabase -- tiene nombres abreviados para 17 de los 30 equipos.
Como cada club recién dispara el error la primera vez que juega un
partido nuevo, esto iba a ir apareciendo de a poco, fecha a fecha
(arrancó con Sarmiento Junín / Argentinos Juniors, fecha 1).

Se detectó comparando el set de equipos de tablalpf.csv contra el de
fixture_lpf.csv -- son 17 pares confirmados con los datos reales del
proyecto (no son una estimación como en mapeo_equipos_federal.py).

Cómo se resuelve un nombre:
  1. Se normaliza (minúsculas, sin tildes, sin puntuación) tanto el nombre
     canónico como el nombre corto.
  2. Si hay un OVERRIDE explícito para ese equipo, se usa esa lista de alias.
  3. Si no matchea nada, se usa fuzzy matching (difflib) con un umbral alto.
  4. Si tampoco matchea, se devuelve None y hay que agregar el alias que
     falte a OVERRIDES en vez de adivinar mal.

CÓMO VALIDAR/CORREGIR ESTE ARCHIVO:
Si en el futuro Promiedos (o un fixture nuevo) trae un nombre que no
matchea, correr:
    python mapeo_equipos_lpf.py "Nombre Que Vino"
y si da None, agregarlo a la lista de OVERRIDES del equipo correspondiente.
"""
import re
import unicodedata
from difflib import get_close_matches

# Nombres CANÓNICOS, tal cual están en fixture_lpf.csv / resultados_lpf.csv /
# promedios_lpf.csv (y como los devuelve el scraper de Promiedos).
EQUIPOS_LPF = [
    "Aldosivi", "Argentinos Juniors", "Atlético Tucumán", "Banfield",
    "Barracas Central", "Belgrano", "Boca Juniors", "Central Córdoba SdE",
    "Defensa y Justicia", "Deportivo Riestra", "Estudiantes RC",
    "Estudiantes de La Plata", "Gimnasia La Plata", "Gimnasia de Mendoza",
    "Huracán", "Independiente", "Independiente Rivadavia", "Instituto",
    "Lanús", "Newell's Old Boys", "Platense", "Racing Club", "River Plate",
    "Rosario Central", "San Lorenzo", "Sarmiento Junín", "Talleres de Córdoba",
    "Tigre", "Unión de Santa Fe", "Vélez Sarsfield",
]

# alias = nombres cortos que aparecen en datos/tablalpf.csv (y por lo
# tanto en el standings de Supabase). Confirmados contra los datos reales
# del proyecto, no son una estimación.
OVERRIDES = {
    "Argentinos Juniors": ["argentinos"],
    "Atlético Tucumán": ["atl. tucuman", "atl tucuman"],
    "Barracas Central": ["barracas"],
    "Boca Juniors": ["boca jrs.", "boca jrs"],
    "Defensa y Justicia": ["defensa"],
    "Deportivo Riestra": ["riestra"],
    "Estudiantes de La Plata": ["estudiantes"],
    "Gimnasia La Plata": ["gimnasia"],
    "Gimnasia de Mendoza": ["gimnasia (m)", "gimnasia m"],
    "Independiente Rivadavia": ["independiente riv.", "independiente riv"],
    "Newell's Old Boys": ["newell's", "newells"],
    "Racing Club": ["racing"],
    "River Plate": ["river"],
    "Rosario Central": ["central"],
    "Sarmiento Junín": ["sarmiento"],
    "Talleres de Córdoba": ["talleres"],
    "Unión de Santa Fe": ["union"],
    "Vélez Sarsfield": ["velez"],
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


def _candidatos(nombre_canonico: str):
    """Todas las formas normalizadas contra las que comparar un nombre canónico."""
    candidatos = {normalizar(nombre_canonico)}
    for alias in OVERRIDES.get(nombre_canonico, []):
        candidatos.add(normalizar(alias))
    return candidatos


# Índice: nombre normalizado (canónico o alias) -> nombre canónico
_INDICE = {}
for _canon in EQUIPOS_LPF:
    for _cand in _candidatos(_canon):
        _INDICE[_cand] = _canon


def resolver_equipo_lpf(nombre: str, umbral_fuzzy: float = 0.82):
    """
    Recibe un nombre en CUALQUIER formato conocido (completo tipo fixture,
    o corto tipo tablalpf.csv/standings) y devuelve el nombre canónico
    (el de fixture_lpf.csv), o None si no hay match confiable.
    """
    norm = normalizar(nombre)
    if not norm:
        return None

    # 1) match exacto contra el índice (canónicos + overrides)
    if norm in _INDICE:
        return _INDICE[norm]

    # 2) fuzzy matching como red de seguridad
    cercanos = get_close_matches(norm, _INDICE.keys(), n=1, cutoff=umbral_fuzzy)
    if cercanos:
        return _INDICE[cercanos[0]]

    return None


if __name__ == "__main__":
    # Prueba rápida manual: python mapeo_equipos_lpf.py "Sarmiento"
    import sys
    if len(sys.argv) > 1:
        prueba = " ".join(sys.argv[1:])
        print(f"'{prueba}' -> {resolver_equipo_lpf(prueba)}")
    else:
        print(f"{len(EQUIPOS_LPF)} equipos canónicos cargados.")
