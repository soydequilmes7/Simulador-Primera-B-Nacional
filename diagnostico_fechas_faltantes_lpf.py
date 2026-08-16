# -*- coding: utf-8 -*-
"""
diagnostico_fechas_faltantes_lpf.py

Pablo preguntó de qué fecha son los partidos que le faltan a cada
equipo. El Clausura reusa el MISMO cronograma de rivales que el
Apertura (misma "Fecha N" -> misma pareja de equipos, confirmado leyendo
scraper_promiedos_lpf.py: Promiedos ni siquiera distingue un torneo del
otro en el campo "stage_round_name"). Entonces: para cada equipo,
mirando su cronograma original (datos/fixture_lpf.csv, jornada 1-16) y
viendo contra qué rivales YA hay un resultado cargado en Supabase (sin
importar qué jornada interna le haya tocado a esa fila, post-fix del
offset fijo), se puede inferir qué "Fecha N" del Clausura todavía no
llegó.

Uso:
    python diagnostico_fechas_faltantes_lpf.py
    python diagnostico_fechas_faltantes_lpf.py "Newell's Old Boys" "Deportivo Riestra" "Boca Juniors"
"""
import csv
import sys

from db.repository import transaction
from mapeo_equipos_lpf import resolver_equipo_lpf


def _cronograma_por_equipo():
    """{equipo: {fecha: rival}} a partir del fixture ORIGINAL (antes de
    que se jugara nada), que es el cronograma real de rivales tanto del
    Apertura como del Clausura (mismas parejas, se repiten)."""
    with open("datos/fixture_lpf.csv", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))

    cronograma = {}
    for fila in filas:
        fecha = int(fila["jornada"])
        local, visitante = fila["equipo_local"], fila["equipo_visitante"]
        cronograma.setdefault(local, {})[fecha] = visitante
        cronograma.setdefault(visitante, {})[fecha] = local
    return cronograma


def main(equipos_pedidos):
    cronograma = _cronograma_por_equipo()

    with transaction() as repo:
        jugados = repo.match_records("lpf", "played")

    # Rivales ya enfrentados en el Clausura, por equipo (sin importar
    # la jornada interna de la fila).
    rivales_ya_jugados = {}
    for f in jugados:
        local = resolver_equipo_lpf(f["equipo_local"]) or f["equipo_local"]
        visitante = resolver_equipo_lpf(f["equipo_visitante"]) or f["equipo_visitante"]
        rivales_ya_jugados.setdefault(local, set()).add(visitante)
        rivales_ya_jugados.setdefault(visitante, set()).add(local)

    equipos = equipos_pedidos or sorted(cronograma.keys())

    print("(Ojo: la lista de cada equipo mezcla fechas que YA se jugaron pero se cayeron de la")
    print(" ventana de Promiedos, CON fechas que todavía ni se jugaron en la realidad -- comparar")
    print(" contra Promiedos para saber cuáles de éstas hace falta cargar a mano.)")

    for equipo in equipos:
        if equipo not in cronograma:
            print(f"\n{equipo}: no encontrado en el cronograma (revisá el nombre exacto)")
            continue
        ya_jugados = rivales_ya_jugados.get(equipo, set())
        faltantes = [
            (fecha, rival) for fecha, rival in sorted(cronograma[equipo].items())
            if rival not in ya_jugados
        ]
        if not faltantes:
            print(f"\n{equipo}: sin faltantes detectados (puede que ya esté al día, o que "
                  f"el Clausura todavía no haya llegado a esa fecha realmente).")
            continue
        print(f"\n{equipo}: {len(faltantes)} fecha(s) sin resultado cargado en Supabase:")
        for fecha, rival in faltantes:
            print(f"  Fecha {fecha} vs {rival}")


if __name__ == "__main__":
    main(sys.argv[1:])
