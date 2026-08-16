# -*- coding: utf-8 -*-
"""
diagnostico_tabla_clausura_lpf.py

Pablo reportó (fecha de este diagnóstico) que "Tabla del Clausura — a
hoy" no coincide con la tabla real de Promiedos (menos PJ/puntos de los
que corresponden para varios equipos).

Sospecha: _tabla_actual_clausura() (main_lpf.py) arranca el acumulado
desde los nombres de e.apertura (tabla congelada del Apertura) y después
recorre e.resultados sumando cada partido -- pero si el nombre de un
equipo en resultados NO coincide EXACTO con el nombre en apertura, la
línea `if nombre not in acumulado: continue` lo descarta en silencio,
sin ningún error ni aviso. Este script imprime exactamente eso: qué
nombres aparecen en resultados pero no en apertura (los partidos que se
están perdiendo) y cuántos partidos afecta.

Uso:
    python diagnostico_tabla_clausura_lpf.py
"""
from modelos.estadisticas_lpf import EstadisticasLPF

e = EstadisticasLPF()
e.cargar_datos_lpf()

nombres_apertura = set(e.apertura["equipo"])
print(f"Equipos en Apertura (tabla congelada): {len(nombres_apertura)}")

nombres_resultados = set(e.resultados["equipo_local"]) | set(e.resultados["equipo_visitante"])
print(f"Equipos distintos mencionados en resultados del Clausura: {len(nombres_resultados)}")

huerfanos = nombres_resultados - nombres_apertura
if not huerfanos:
    print("\nOK: todos los nombres de resultados están en Apertura -- no es un problema de nombres acá.")
else:
    print(f"\n{len(huerfanos)} nombre(s) en resultados que NO están en Apertura "
          f"(esos partidos se están descartando en silencio en _tabla_actual_clausura):")
    for nombre in sorted(huerfanos):
        partidos = e.resultados[
            (e.resultados["equipo_local"] == nombre) | (e.resultados["equipo_visitante"] == nombre)
        ]
        print(f"\n  {nombre!r} -- aparece en {len(partidos)} partido(s):")
        for _, p in partidos.iterrows():
            print(f"    {p['equipo_local']} {p['goles_local']}-{p['goles_visitante']} {p['equipo_visitante']}")
        # Buscamos el nombre más parecido en Apertura, para sugerir el fix.
        from difflib import get_close_matches
        parecidos = get_close_matches(nombre, nombres_apertura, n=3, cutoff=0.6)
        print(f"    Candidatos parecidos en Apertura: {parecidos}")

print("\n--- Conteo de partidos jugados por equipo (resultados), para comparar a mano contra Promiedos ---")
conteo = {}
for _, p in e.resultados.iterrows():
    conteo[p["equipo_local"]] = conteo.get(p["equipo_local"], 0) + 1
    conteo[p["equipo_visitante"]] = conteo.get(p["equipo_visitante"], 0) + 1
for nombre in sorted(conteo, key=lambda n: -conteo[n]):
    print(f"  {nombre}: {conteo[nombre]} partido(s)")
