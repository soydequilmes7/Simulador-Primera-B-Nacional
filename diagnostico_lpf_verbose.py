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

# Para cada partido sin matchear, buscamos en el fixture pendiente
# original (los 228) cualquier fila que mencione a alguno de los dos
# equipos, para comparar el string EXACTO guardado en Supabase contra
# el que devuelve Promiedos/resolver_equipo_lpf. Si es un problema de
# nombres, acá se va a ver clarito la diferencia.
from mapeo_equipos_lpf import resolver_equipo_lpf

with transaction() as repo2:
    pending_ahora = repo2.match_records("lpf", "pending")

print("\n--- Búsqueda de coincidencias parciales para cada partido sin matchear ---")
for p in r["sin_matchear"]:
    local_raw = p["equipo_local"]
    visit_raw = p["equipo_visitante"]
    local_resuelto = resolver_equipo_lpf(local_raw)
    visit_resuelto = resolver_equipo_lpf(visit_raw)
    print(f"\n{local_raw!r} vs {visit_raw!r}")
    print(f"  resolver_equipo_lpf: {local_resuelto!r} vs {visit_resuelto!r}")
    encontrados = [
        f for f in pending_ahora
        if local_raw.split()[0].lower() in f["equipo_local"].lower() + f["equipo_visitante"].lower()
        or visit_raw.split()[0].lower() in f["equipo_local"].lower() + f["equipo_visitante"].lower()
    ]
    if encontrados:
        for f in encontrados[:3]:
            print(f"  candidato en pending (jornada {f.get('jornada')}): "
                  f"{f['equipo_local']!r} vs {f['equipo_visitante']!r}")
    else:
        print("  (ningún candidato parecido encontrado en pending)")
