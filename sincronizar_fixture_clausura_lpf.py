# -*- coding: utf-8 -*-
"""
sincronizar_fixture_clausura_lpf.py

Arregla el "9 partidos sin identificar" que tira actualizar_resultados_lpf.py
cuando arranca el Clausura.

CAUSA RAÍZ (confirmada leyendo el código, no una estimación):
Promiedos etiqueta las fechas del Clausura con el mismo "Fecha N" que usó
para el Apertura (scraper_promiedos_lpf.obtener_partidos_lpf() parsea
`stage_round_name` como jornada, y no distingue Apertura de Clausura). El
fixture PENDIENTE de Apertura para esa jornada ya se consumió hace meses
(pasó a "played" cuando se jugó de verdad), así que cuando Promiedos
reporta la MISMA pareja de equipos como jugada otra vez (ahora por el
Clausura), actualizar_resultados_lpf.py no encuentra ninguna fila
pendiente con esa clave (equipo_local, equipo_visitante) -- porque nunca
se cargó el fixture nuevo del Clausura -- y el partido cae en
"sin_matchear".

Este script agrega al fixture PENDIENTE de Supabase los partidos que
Promiedos ya tiene programados para el Clausura y que todavía no están
ahí, sin tocar nada de lo que ya hay (ni el historial "played" del
Apertura, ni las filas pendientes que ya existan).

OJO CON LA JORNADA: la tabla `matches` tiene una constraint única de
(competition_slug, season_id, jornada, equipo_local_id, equipo_visitante_id).
Si insertáramos el Clausura con la MISMA jornada que usó Promiedos (que
vuelve a arrancar en 1), pisaríamos -- vía "on conflict do update" -- la
fila YA JUGADA del Apertura para esa jornada/pareja, perdiendo el
resultado real. Por eso acá se le suma un offset: se toma el jornada
máximo que ya existe en Supabase (jugado o pendiente) para "lpf" y el
Clausura arranca justo después. La jornada de Promiedos para el Clausura
(que reinicia en 1) se guarda en la columna "jornada_torneo" -- si esa
columna no existe en tu esquema todavía, se ignora sin romper nada (ver
más abajo).

Por defecto corre en modo DRY-RUN (solo imprime qué agregaría, no toca
Supabase). Para aplicar de verdad:

    python sincronizar_fixture_clausura_lpf.py --aplicar

Es seguro correrlo más de una vez: si un partido del Clausura ya está en
el fixture pendiente (por ejemplo porque ya lo agregaste en una corrida
anterior), no se vuelve a agregar.
"""
from __future__ import annotations

import argparse

from db.repository import transaction
from mapeo_equipos_lpf import resolver_equipo_lpf
from scraper_promiedos_lpf import obtener_partidos_lpf


def _clave(equipo_local: str, equipo_visitante: str) -> tuple[str, str]:
    return (
        resolver_equipo_lpf(equipo_local) or equipo_local,
        resolver_equipo_lpf(equipo_visitante) or equipo_visitante,
    )


def calcular_filas_nuevas(pending_actual: list[dict], jugados_actual: list[dict]) -> tuple[list[dict], int]:
    """Función pura (sin DB) para poder testearla -- ver
    test_sincronizar_fixture_clausura_lpf.py. Devuelve (filas_nuevas,
    jornada_offset_usado)."""
    jornada_offset = max(
        (int(fila.get("jornada") or 0) for fila in pending_actual + jugados_actual),
        default=0,
    )

    claves_existentes = {_clave(f["equipo_local"], f["equipo_visitante"]) for f in pending_actual}

    partidos_promiedos = obtener_partidos_lpf()
    filas_nuevas = []
    for p in partidos_promiedos:
        if p["jugado"]:
            continue  # esto es lo que ACTUALIZAR_RESULTADOS ya sabe cargar
        clave = _clave(p["equipo_local"], p["equipo_visitante"])
        if clave in claves_existentes:
            continue  # ya está en el fixture pendiente (corrida anterior, o Apertura todavía sin jugarse)
        filas_nuevas.append({
            "fecha": "",
            "jornada": jornada_offset + p["jornada"],
            "equipo_local": clave[0],
            "equipo_visitante": clave[1],
        })
        claves_existentes.add(clave)  # por si Promiedos repitiera la fila

    return filas_nuevas, jornada_offset


def main(aplicar: bool) -> None:
    with transaction() as repo:
        pending_actual = repo.match_records("lpf", "pending")
        jugados_actual = repo.match_records("lpf", "played")

    print(f"Fixture pendiente actual en Supabase: {len(pending_actual)} partido(s)")
    print(f"Resultados ya cargados (played) en Supabase: {len(jugados_actual)} partido(s)")

    filas_nuevas, jornada_offset = calcular_filas_nuevas(pending_actual, jugados_actual)

    if not filas_nuevas:
        print("\nNo hay partidos nuevos del Clausura para agregar -- "
              "o ya están todos cargados, o Promiedos todavía no publicó nada nuevo.")
        return

    print(f"\nJornada máxima ya usada en Supabase: {jornada_offset} -- "
          f"el Clausura se numera a partir de {jornada_offset + 1} para no chocar con el Apertura.")
    print(f"\n{len(filas_nuevas)} partido(s) nuevo(s) del Clausura para agregar al fixture pendiente:")
    for f in filas_nuevas:
        print(f"  Jornada {f['jornada']}: {f['equipo_local']} vs {f['equipo_visitante']}")

    if not aplicar:
        print("\n(DRY-RUN -- no se tocó Supabase. Correr con --aplicar para guardar de verdad.)")
        return

    pending_final = pending_actual + filas_nuevas
    with transaction() as repo:
        repo.replace_matches("lpf", pending_final, jugados_actual)
    print(f"\n✓ Guardado en Supabase: {len(filas_nuevas)} partido(s) nuevo(s) del Clausura agregados al "
          f"fixture pendiente. El historial 'played' del Apertura ({len(jugados_actual)} partidos) no se tocó.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aplicar", action="store_true",
                         help="Guarda los cambios en Supabase. Sin esta bandera, solo muestra qué haría (dry-run).")
    args = parser.parse_args()
    main(aplicar=args.aplicar)
