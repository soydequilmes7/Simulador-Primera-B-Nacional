# -*- coding: utf-8 -*-
"""
scripts/generar_fixture_brasileirao.py

Arma datos/fixture_brasileirao.csv desde cero: fixture_brasileirao.csv
llegó vacío (solo el header, sin la temporada real cargada todavía) y
sin fixture no hay nada para que main_brasileirao.py simule -- de ahí
que la tabla apareciera vacía en la página.

Genera un todos-contra-todos de ida y vuelta (38 fechas, 380 partidos)
con fixture_generator.py -- el mismo generador que ya usan Federal A,
LPF y los carryover_engines de Modo Temporada -- a partir de los 20
equipos que ya están en datos/tabla_brasileirao.csv, para no repetir
esa lista a mano y arriesgar que se desincronice.

ADVERTENCIA: este fixture es un calendario "genérico" (round-robin por
el método del círculo), no el fixture oficial real de la CBF. Sirve
para poder simular la temporada ya mismo; cuando actualizar_resultados_
brasileirao.py empiece a scrapear resultados reales de Promiedos, esos
resultados se van a matchear por nombre de equipo (no por fecha), así
que el orden exacto de las fechas de este fixture no afecta la
precisión de la tabla una vez que haya partidos reales cargados.

Uso (una sola vez, parado en la raíz del repo):
    python scripts/generar_fixture_brasileirao.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fixture_generator import generar_fixture_ida_vuelta

DATOS_DIR = Path(__file__).resolve().parent.parent / "datos"
TABLA_CSV = DATOS_DIR / "tabla_brasileirao.csv"
FIXTURE_CSV = DATOS_DIR / "fixture_brasileirao.csv"


def leer_equipos(tabla_csv: Path) -> list[str]:
    with open(tabla_csv, newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    if not filas:
        raise ValueError(f"{tabla_csv} está vacío -- no hay equipos para armar el fixture")
    # Orden por posición, para que el fixture generado sea reproducible
    # (mismo input -> mismo calendario) sin depender del orden del CSV.
    filas.sort(key=lambda f: int(f["posicion"]))
    return [f["equipo"] for f in filas]


def generar(tabla_csv: Path = TABLA_CSV, fixture_csv: Path = FIXTURE_CSV) -> int:
    equipos = leer_equipos(tabla_csv)
    partidos = generar_fixture_ida_vuelta(equipos)

    with open(fixture_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["fecha", "jornada", "equipo_local", "equipo_visitante"])
        for p in partidos:
            writer.writerow(["", p.jornada, p.equipo_local, p.equipo_visitante])

    return len(partidos)


if __name__ == "__main__":
    total = generar()
    n_jornadas = total // 10  # 20 equipos -> 10 partidos por fecha
    print(f"{FIXTURE_CSV.relative_to(FIXTURE_CSV.parent.parent)}: {total} partidos en {n_jornadas} fechas.")
