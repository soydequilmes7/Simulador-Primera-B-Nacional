# -*- coding: utf-8 -*-
"""
season/validar_etapa0_local.py

Versión LOCAL de la validación de Etapa 0. A diferencia de
validar_etapa0.py (que pasa por data_access.league_data() -> Supabase),
este script lee los tabla_X.csv directamente desde datos/ con pandas.

No requiere SUPABASE_DB_URL ni conexión a ninguna base. Sirve para
validar la lógica de "un club único por nombre, sin duplicados entre
divisiones" mientras se decide si ClubRegistry en producción va a leer
de CSV, de Supabase, o de ambos.

NOVEDAD (post-hallazgo de Estudiantes / Central Córdoba): el nombre de
un club NO alcanza como identificador único en todo el fútbol argentino
-- hay clubes distintos que comparten nombre (ver datos/club_aliases.csv).
Este script arma, para cada equipo, un club_id único combinando el
nombre con una tabla de alias manual para los casos conocidos de
choque. Los duplicados ahora se detectan por club_id, no por nombre
crudo.

Correrlo desde la raíz del proyecto:

    python -m season.validar_etapa0_local
"""
import csv
import os
import re
import unicodedata

import pandas as pd

# slug interno -> (nombre de división legible, archivo CSV en datos/)
DIVISIONES_LOCAL = {
    "nacional":   ("Primera Nacional",          "datos/tabla.csv"),
    "lpf":        ("Liga Profesional",          "datos/tablalpf.csv"),
    "bmetro":     ("Primera B Metropolitana",   "datos/tabla_bmetro.csv"),
    "federal_a":  ("Federal A",                 "datos/tabla_federal_a.csv"),
    "primerac":   ("Primera C",                 "datos/tabla_primerac.csv"),
}

ALIASES_PATH = "datos/club_aliases.csv"


def slugify(nombre):
    """Convierte un nombre de club en un club_id por defecto (sin acentos, snake_case)."""
    nfkd = unicodedata.normalize("NFKD", nombre)
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    slug = sin_acentos.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
    return slug


def cargar_aliases(path_aliases):
    """
    Lee datos/club_aliases.csv y devuelve un dict:
        (division_slug, nombre_csv) -> (club_id, nombre_display)

    Si el archivo no existe, devuelve un dict vacío (todos los clubes
    usan el club_id por defecto = slugify(nombre)); esto mantiene el
    script funcionando aunque todavía no se haya creado el archivo de
    alias, aunque sin resolver los choques conocidos.
    """
    aliases = {}
    if not os.path.exists(path_aliases):
        return aliases

    with open(path_aliases, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for fila in reader:
            clave = (fila["division"].strip(), fila["nombre_csv"].strip())
            aliases[clave] = (fila["club_id"].strip(), fila["nombre_display"].strip())
    return aliases


def cargar_equipos(path_csv):
    """Lee un tabla_X.csv y devuelve la lista de nombres de equipo, en orden."""
    df = pd.read_csv(path_csv, encoding="utf-8")
    if "equipo" not in df.columns:
        raise ValueError(
            f"{path_csv}: no encontré una columna 'equipo' (columnas: {list(df.columns)})"
        )
    return df["equipo"].tolist()


def resolver_club(division_slug, nombre_csv, aliases):
    """
    Devuelve (club_id, nombre_display) para un equipo, consultando primero
    la tabla de alias manual (para los casos de choque ya conocidos) y
    cayendo al slug por defecto del nombre si no hay alias explícito.
    """
    clave = (division_slug, nombre_csv)
    if clave in aliases:
        return aliases[clave]
    return slugify(nombre_csv), nombre_csv


def main():
    print("=" * 70)
    print("VALIDACIÓN ETAPA 0 (LOCAL, sin Supabase) -- lectura directa de CSV")
    print("Ahora con resolución de nombres ambiguos vía datos/club_aliases.csv")
    print("=" * 70)

    aliases = cargar_aliases(ALIASES_PATH)
    if aliases:
        print(f"\nAlias cargados desde {ALIASES_PATH}: {len(aliases)} entradas")
    else:
        print(
            f"\n⚠️  No encontré {ALIASES_PATH} (o está vacío) -- los choques de "
            "nombre conocidos (Estudiantes, Central Córdoba) NO se van a resolver."
        )

    # slug de división -> lista de (nombre_csv, club_id, nombre_display)
    equipos_por_division = {}
    for slug, (nombre_division, path_csv) in DIVISIONES_LOCAL.items():
        try:
            nombres = cargar_equipos(path_csv)
        except FileNotFoundError:
            print(f"\n❌ No encontré el archivo: {path_csv}")
            return
        except ValueError as e:
            print(f"\n❌ {e}")
            return

        equipos_por_division[slug] = [
            (nombre, *resolver_club(slug, nombre, aliases)) for nombre in nombres
        ]

    # 1) Duplicados entre divisiones: mismo club_id en 2+ tablas
    dueno = {}  # club_id -> (slug de división, nombre_display) de la primera aparición
    duplicados = []
    for slug, (nombre_division, _) in DIVISIONES_LOCAL.items():
        for nombre_csv, club_id, nombre_display in equipos_por_division[slug]:
            if club_id in dueno:
                otro_slug, otro_nombre_display = dueno[club_id]
                otro_div = DIVISIONES_LOCAL[otro_slug][0]
                duplicados.append(
                    (club_id, nombre_display, otro_nombre_display, otro_div, nombre_division)
                )
            else:
                dueno[club_id] = (slug, nombre_display)

    if duplicados:
        print("\n❌ Hay club_id repetidos entre divisiones (choque SIN resolver):")
        for club_id, nombre_a, nombre_b, div_a, div_b in duplicados:
            print(f"   - club_id '{club_id}': '{nombre_b}' en '{div_b}' ya existía como '{nombre_a}' en '{div_a}'")
        print(
            "\nRevisar antes de seguir (ClubRegistry real lanzaría ValueError acá). "
            f"Agregá una fila para este caso en {ALIASES_PATH}."
        )
        return

    # 2) Conteo por división
    total = sum(len(v) for v in equipos_por_division.values())
    print(f"\nTotal de clubes (todas las divisiones): {total}")
    print("\nPor división:")
    for slug, (nombre_division, path_csv) in DIVISIONES_LOCAL.items():
        cantidad = len(equipos_por_division[slug])
        print(f"  {nombre_division:30s} {cantidad:3d} clubes  ({path_csv})")

    # 3) Ejemplo: primeros 3 de cada división, mostrando nombre_display
    #    para que se vea cuándo un club vino resuelto por alias
    print("\nEjemplo (primeros 3 clubes de cada división, nombre_display):")
    for slug, (nombre_division, _) in DIVISIONES_LOCAL.items():
        primeros = [nombre_display for _, _, nombre_display in equipos_por_division[slug][:3]]
        print(f"  {nombre_division}: {primeros}")

    # 4) Mostrar explícitamente los casos que SÍ se resolvieron por alias,
    #    para que quede claro que el mapeo se está usando de verdad
    resueltos = [
        (slug, nombre_csv, nombre_display)
        for slug in equipos_por_division
        for nombre_csv, club_id, nombre_display in equipos_por_division[slug]
        if (slug, nombre_csv) in aliases
    ]
    if resueltos:
        print("\nClubes resueltos vía club_aliases.csv:")
        for slug, nombre_csv, nombre_display in resueltos:
            nombre_division = DIVISIONES_LOCAL[slug][0]
            print(f"  [{nombre_division}] '{nombre_csv}' -> '{nombre_display}'")

    print("\n" + "=" * 70)
    print("Sin duplicados entre divisiones. Los CSV locales + club_aliases.csv")
    print("están listos para representarse como ClubRegistry (una vez que se")
    print("decida si la versión real lee de acá, de Supabase, o de ambos).")
    print("=" * 70)


if __name__ == "__main__":
    main()
