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
resultado real. Por eso acá se le suma un offset FIJO de 16 (ver
APERTURA_TOTAL_JORNADAS más abajo: el Apertura 2026 tuvo exactamente 16
fechas reales) -- Clausura Fecha 1 siempre queda como jornada 17,
Fecha 2 como jornada 18, etc. Antes era un offset DINÁMICO ("la
jornada máxima ya usada en Supabase"), pero eso daba números
impredecibles según qué fixture viejo del Apertura hubiera quedado
pendiente sin jugar nunca -- Pablo se encontró con esto en la
práctica (16/08/2026).

Por defecto corre en modo DRY-RUN (solo imprime qué agregaría, no toca
Supabase). Para aplicar de verdad:

    python sincronizar_fixture_clausura_lpf.py --aplicar

Es seguro correrlo más de una vez: si un partido del Clausura ya está en
el fixture pendiente (por ejemplo porque ya lo agregaste en una corrida
anterior), no se vuelve a agregar.

NOTA: desde que se agregó este script, actualizar_resultados_lpf.py
llama a calcular_filas_nuevas() (la función de acá) automáticamente en
cada corrida -- no hace falta acordarse de correr este archivo a mano
en cada transición de fase. Se deja como está (con su modo --aplicar
manual) por si en algún momento hace falta correr la sincronización
sola, sin tocar resultados, o para inspeccionar en dry-run qué agregaría
antes de que corra solo.
"""
from __future__ import annotations

import argparse

from db.repository import transaction
from mapeo_equipos_lpf import resolver_equipo_lpf
from scraper_promiedos_lpf import obtener_partidos_lpf

# El Apertura 2026 tuvo 16 fechas reales (confirmado: el fixture
# original con el que arrancó el proyecto -- antes de que se jugara un
# solo partido -- va de jornada 1 a 16, datos/fixture_lpf.csv). Es una
# constante FIJA a propósito: antes acá se usaba "la jornada máxima ya
# usada en Supabase" (pending + played), pero eso da un número
# impredecible que depende de basura vieja que haya quedado pendiente
# sin jugar nunca (Pablo se encontró con esto: un partido del Clausura
# quedó con jornada interna "10" en vez de un número prolijo, porque
# consumió una fila pendiente vieja del Apertura que nunca se había
# jugado). Con la constante fija, Clausura Fecha 1 SIEMPRE es jornada
# 17, Fecha 2 SIEMPRE jornada 18, etc. -- predecible y estable, no
# importa qué quede pendiente de antes.
APERTURA_TOTAL_JORNADAS = 16


def _clave(equipo_local: str, equipo_visitante: str) -> tuple[str, str]:
    return (
        resolver_equipo_lpf(equipo_local) or equipo_local,
        resolver_equipo_lpf(equipo_visitante) or equipo_visitante,
    )


def calcular_filas_nuevas(pending_actual: list[dict], jugados_actual: list[dict]) -> tuple[list[dict], int]:
    """Función pura (sin DB) para poder testearla -- ver
    test_sincronizar_fixture_clausura_lpf.py. Devuelve (filas_nuevas,
    jornada_offset_usado).

    BUG DE LA PRIMERA VERSIÓN (reportado por Pablo, 26/07/2026, seguía
    tirando "sin identificar" después de mergear el fix): esta función
    filtraba `if p["jugado"]: continue`, o sea que solo agregaba al
    fixture los partidos que Promiedos TODAVÍA no había jugado. Pero
    para cuando alguien aprieta "Actualizar Resultados", lo más común
    es que el partido del Clausura YA esté jugado en Promiedos -- ese
    filtro lo descartaba antes de siquiera intentar agregarlo, así que
    nunca llegaba a existir la fila de fixture que el matcheo principal
    de actualizar_resultados_lpf.py necesita para encontrarlo.

    Ahora se agregan partidos jugados Y pendientes por igual. Para no
    reintroducir como "nuevo" un partido del Apertura que Promiedos
    todavía muestre en su ventana de "últimos ~100" (y así generar una
    fila de fixture pendiente duplicada, con riesgo de recargar el
    mismo resultado dos veces), se compara el marcador: si ya hay un
    resultado cargado para esa pareja de equipos con el MISMO marcador,
    se asume que es el mismo partido de vuelta apareciendo en la
    ventana de Promiedos (no uno nuevo) y no se agrega. Si el marcador
    es distinto (o la pareja no tiene ningún resultado cargado
    todavía), es un partido genuinamente nuevo -- se agrega.
    """
    jornada_offset = APERTURA_TOTAL_JORNADAS

    claves_pendientes = {_clave(f["equipo_local"], f["equipo_visitante"]) for f in pending_actual}

    marcadores_ya_cargados: dict[tuple[str, str], set[tuple]] = {}
    for f in jugados_actual:
        clave = _clave(f["equipo_local"], f["equipo_visitante"])
        marcadores_ya_cargados.setdefault(clave, set()).add(
            (f.get("goles_local"), f.get("goles_visitante"))
        )

    partidos_promiedos = obtener_partidos_lpf()
    filas_nuevas = []
    for p in partidos_promiedos:
        clave = _clave(p["equipo_local"], p["equipo_visitante"])
        if clave in claves_pendientes:
            continue  # ya está en el fixture pendiente (corrida anterior)
        if p["jugado"]:
            marcador = (p["goles_local"], p["goles_visitante"])
            if marcador in marcadores_ya_cargados.get(clave, set()):
                continue  # mismo partido y mismo resultado ya cargados -- no es uno nuevo
        filas_nuevas.append({
            "fecha": "",
            "jornada": jornada_offset + p["jornada"],
            "equipo_local": clave[0],
            "equipo_visitante": clave[1],
        })
        claves_pendientes.add(clave)  # por si Promiedos repitiera la fila

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
