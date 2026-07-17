# -*- coding: utf-8 -*-
"""
scripts/generar_fixture_ligapro.py

Arma datos/fixture_ligapro.csv desde cero: la FASE INICIAL de LigaPro
Serie A es un todos-contra-todos ida y vuelta de 16 equipos (30 fechas,
240 partidos), igual en estructura a Brasileirão -- se reusa el mismo
fixture_generator.generar_fixture_ida_vuelta() por el método del círculo.

ADVERTENCIA (igual que en Brasileirão): este es un calendario GENÉRICO,
no el fixture oficial real de LigaPro. Sirve para poder simular ya
mismo; cuando actualizar_resultados_ligapro.py empiece a scrapear
resultados reales, éstos matchean por nombre de equipo, no por fecha.

Este script SOLO genera el fixture de la FASE INICIAL. El fixture de la
FASE FINAL (Hexagonal Campeón / Cuadrangular Sudamericana / Hexagonal
Descenso) se genera dinámicamente dentro de
EstadisticasLigaPro._generar_fixture_fase_final(), una vez que se conoce
la tabla final de la Fase Inicial (real o simulada) -- no tiene sentido
pre-generarlo acá porque depende de qué equipos clasifican a cada grupo.

Uso (una sola vez, parado en la raíz del repo):
    python scripts/generar_fixture_ligapro.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fixture_generator import generar_fixture_ida_vuelta

DATOS_DIR = Path(__file__).resolve().parent.parent / "datos"
TABLA_CSV = DATOS_DIR / "tabla_ligapro.csv"
FIXTURE_CSV = DATOS_DIR / "fixture_ligapro.csv"


def leer_equipos(tabla_csv: Path) -> list[str]:
    with open(tabla_csv, newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    if not filas:
        raise ValueError(f"{tabla_csv} está vacío -- no hay equipos para armar el fixture")
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
    n_jornadas = total // 8  # 16 equipos -> 8 partidos por fecha
    print(f"{FIXTURE_CSV.relative_to(FIXTURE_CSV.parent.parent)}: {total} partidos en {n_jornadas} fechas.")
