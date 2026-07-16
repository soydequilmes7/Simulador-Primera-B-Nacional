# -*- coding: utf-8 -*-
"""Diagnostico rapido: recorre los mismos CSV que seed_supabase.py y
avisa si algun fixture/resultados tiene una fila con el nombre de
equipo vacio o faltante (la causa tipica del NotNullViolation en
teams.name). No toca la base de datos -- se corre parado en la raiz
del repo:

    python diagnosticar_csv.py
"""
import csv
from pathlib import Path

DATOS = Path(__file__).resolve().parent / "datos"

ARCHIVOS = [
    "fixture.csv", "resultados.csv",
    "fixture_lpf.csv", "resultados_lpf.csv",
    "fixture_bmetro.csv", "resultados_bmetro.csv",
    "fixture_federal_a.csv", "resultados_federal_a.csv",
    "fixture_primerac.csv", "resultados_primerac.csv",
    "fixture_brasileirao.csv", "resultados_brasileirao.csv",
]

encontrado = False
for nombre in ARCHIVOS:
    path = DATOS / nombre
    if not path.exists():
        print(f"{nombre}: no existe, se salta")
        continue
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):
            for campo in ("equipo_local", "equipo_visitante"):
                valor = row.get(campo)
                if not valor or not valor.strip():
                    print(f"{nombre} linea {i}: '{campo}' vacio -> {row}")
                    encontrado = True

if not encontrado:
    print("No se encontro ninguna fila con equipo vacio en fixture/resultados.")
