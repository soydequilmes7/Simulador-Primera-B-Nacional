# -*- coding: utf-8 -*-
"""
diagnosticar_primerac_sin_matchear.py

Diagnóstico puntual para el aviso "partido(s) sin identificar" que tira
"Actualizar Resultados" en Primera C. No modifica nada -- solo imprime,
lado a lado, las 3 fuentes que actualizar_resultados_primerac.py cruza
para decidir si un partido matchea o no:

  1. Lo que Promiedos está devolviendo AHORA para ese cruce (crudo y ya
     pasado por resolver_equipo()).
  2. Lo que hay en el fixture PENDIENTE de Supabase para esos dos equipos
     (en cualquier orden local/visitante).
  3. Lo que ya está en resultados (jugados) de Supabase para esos dos
     equipos.

La causa más probable de un "sin_matchear" con nombres ya limpios
(como "Puerto Nuevo vs CA Fenix", que ya están tal cual en
EQUIPOS_LOCALES de mapeo_equipos_primerac.py, sin necesitar ningún
alias) es que el CRUCE cambió de local/visitante entre lo que se
guardó en el fixture original y lo que Promiedos tiene hoy -- pasa
seguido en el ascenso por reprogramaciones de cancha. La clave que usa
actualizar_resultados_primerac.py es (equipo_local, equipo_visitante)
en ESE orden exacto, así que un partido reprogramado con local/
visitante invertido queda "sin matchear" aunque ambos nombres estén
perfectos.

Uso:
    python diagnosticar_primerac_sin_matchear.py "Puerto Nuevo" "CA Fenix"
"""
from __future__ import annotations

import sys

from db.repository import bootstrap_league_from_csv, transaction
from mapeo_equipos_primerac import resolver_equipo
from scraper_promiedos_primerac import obtener_partidos_primerac


def diagnosticar(equipo_a: str, equipo_b: str) -> None:
    print(f"=== Diagnóstico: {equipo_a} vs {equipo_b} (Primera C) ===\n")

    # 1) Qué dice Promiedos AHORA para cualquier partido entre estos dos.
    print("--- 1) Promiedos (ahora mismo) ---")
    partidos = obtener_partidos_primerac(verbose=False)
    encontrados_promiedos = [
        p for p in partidos
        if {p["equipo_local"], p["equipo_visitante"]} == {equipo_a, equipo_b}
    ]
    if not encontrados_promiedos:
        print(f"  Promiedos NO tiene (todavía) ningún cruce entre '{equipo_a}' y "
              f"'{equipo_b}' con esos nombres YA RESUELTOS por resolver_equipo().")
        print("  Si el nombre real que manda Promiedos es distinto, buscándolo por "
              "nombre parcial:")
        parciales = [
            p for p in partidos
            if equipo_a.lower() in p["equipo_local"].lower() + p["equipo_visitante"].lower()
            or equipo_b.lower() in p["equipo_local"].lower() + p["equipo_visitante"].lower()
        ]
        for p in parciales:
            print(f"    - Fecha {p['jornada']}: {p['equipo_local']} vs {p['equipo_visitante']} "
                  f"(jugado={p['jugado']})")
    else:
        for p in encontrados_promiedos:
            print(f"  Fecha {p['jornada']}: LOCAL={p['equipo_local']!r} "
                  f"VISITANTE={p['equipo_visitante']!r} jugado={p['jugado']} "
                  f"goles={p['goles_local']}-{p['goles_visitante']}")

    # 2) Qué hay en el fixture pendiente de Supabase para estos dos equipos,
    #    en CUALQUIER orden (para detectar swap de local/visitante).
    print("\n--- 2) Fixture PENDIENTE en Supabase ---")
    bootstrap_league_from_csv("primerac")
    with transaction() as repo:
        fixture = repo.match_records("primerac", "pending")
        resultados = repo.match_records("primerac", "played")

    en_fixture = [
        f for f in fixture
        if {f["equipo_local"], f["equipo_visitante"]} == {equipo_a, equipo_b}
    ]
    if not en_fixture:
        print(f"  NINGUNA fila pendiente entre '{equipo_a}' y '{equipo_b}' "
              f"(ni en ese orden ni invertido).")
    for f in en_fixture:
        print(f"  Fecha {f.get('jornada')}: LOCAL={f['equipo_local']!r} "
              f"VISITANTE={f['equipo_visitante']!r}")

    # 3) Qué hay ya cargado en resultados (por si ya se cargó con el
    #    orden/nombre equivocado en una corrida anterior).
    print("\n--- 3) Resultados YA CARGADOS en Supabase ---")
    en_resultados = [
        r for r in resultados
        if {r["equipo_local"], r["equipo_visitante"]} == {equipo_a, equipo_b}
    ]
    if not en_resultados:
        print(f"  NINGÚN resultado cargado todavía entre '{equipo_a}' y '{equipo_b}'.")
    for r in en_resultados:
        print(f"  Fecha {r.get('jornada')}: {r['equipo_local']} {r['goles_local']}-"
              f"{r['goles_visitante']} {r['equipo_visitante']}")

    print("\n--- Diagnóstico ---")
    # Emparejar por jornada (no por índice 0 a ciegas -- bug del primer
    # borrador de este script: comparaba la primera fila de Promiedos
    # contra la primera del fixture aunque fueran jornadas distintas).
    swap_detectado = False
    for f in en_fixture:
        p_misma_jornada = next(
            (p for p in encontrados_promiedos if p["jornada"] == f.get("jornada")), None,
        )
        if p_misma_jornada is None:
            continue
        orden_fixture = (f["equipo_local"], f["equipo_visitante"])
        orden_promiedos = (p_misma_jornada["equipo_local"], p_misma_jornada["equipo_visitante"])
        if orden_fixture != orden_promiedos:
            swap_detectado = True
            print(f"  => Fecha {f.get('jornada')}: local/visitante INVERTIDO. Fixture tenía "
                  f"{orden_fixture[0]!r} de local, Promiedos ahora dice {orden_promiedos[0]!r}.")
            print("     Esto es lo que hace que quede 'sin matchear'.")
    if not swap_detectado and encontrados_promiedos and en_fixture:
        print("  => Mismo orden en las jornadas que se pudieron comparar, raro que haya")
        print("     quedado sin matchear. Puede ser timing -- corré 'Actualizar Resultados' de nuevo.")
    elif encontrados_promiedos and not en_fixture and not en_resultados:
        print("  => Promiedos tiene el partido pero NO hay fila pendiente NI cargada en")
        print("     Supabase para este cruce -- puede ser un partido de una fase que no")
        print("     está en el fixture (interzonal/reducido) o falta en el fixture original.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Uso: python {sys.argv[0]} \"Equipo A\" \"Equipo B\"")
        sys.exit(1)
    diagnosticar(sys.argv[1], sys.argv[2])
