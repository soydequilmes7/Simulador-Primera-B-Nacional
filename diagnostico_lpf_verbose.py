# -*- coding: utf-8 -*-
"""Diagnóstico puntual: por qué siguen "sin identificar" los partidos de
LPF después del fix de auto-sync. No modifica nada más allá de lo que
actualizar() haría normalmente (si hay resultados nuevos matcheables,
los carga -- es el mismo actualizar() de siempre, solo con más prints).

Uso:
    python diagnostico_lpf_verbose.py
"""
from actualizar_resultados_lpf import actualizar
from sincronizar_fixture_clausura_lpf import calcular_filas_nuevas
from db.repository import transaction

with transaction() as repo:
    pending_actual = repo.match_records("lpf", "pending")
    jugados_actual = repo.match_records("lpf", "played")

print(f"Fixture pendiente en Supabase ANTES: {len(pending_actual)}")
print(f"Resultados jugados en Supabase ANTES: {len(jugados_actual)}")

filas_nuevas, offset = calcular_filas_nuevas(pending_actual, jugados_actual)
print(f"\ncalcular_filas_nuevas() detectó: {len(filas_nuevas)} fila(s) nueva(s) (offset={offset})")
for f in filas_nuevas[:15]:
    print(f"  Jornada {f['jornada']}: {f['equipo_local']} vs {f['equipo_visitante']}")

print("\n--- Corriendo actualizar() completo ---")
r = actualizar(imprimir=True)

print("\n--- RESUMEN ---")
print("cargados:", len(r["cargados"]))
print("sin_matchear:", len(r["sin_matchear"]))
print("fixture_sincronizado:", r.get("fixture_sincronizado"))
for p in r["sin_matchear"][:15]:
    print("  sin matchear:", p["equipo_local"], "vs", p["equipo_visitante"],
          "->", p["goles_local"], p["goles_visitante"])
