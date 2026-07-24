# -*- coding: utf-8 -*-
"""
diagnosticar_lpf.py

Script de UNA VEZ para responder, con datos reales de Supabase y de
Promiedos, por qué esos 3 partidos (Sarmiento Junín-Argentinos Juniors,
Belgrano-Rosario Central, Defensa y Justicia-Aldosivi) caen en
"sin identificar" al actualizar. No toca nada, solo imprime.

Uso (con $env:SUPABASE_DB_URL ya seteada, como en tu terminal):
    python diagnosticar_lpf.py
"""
from db.repository import transaction
from scraper_promiedos_lpf import obtener_partidos_jugados_lpf
from mapeo_equipos_lpf import resolver_equipo_lpf

EQUIPOS_A_REVISAR = {
    "sarmiento junín", "sarmiento junin", "sarmiento",
    "argentinos juniors", "argentinos",
    "belgrano",
    "rosario central", "central",
    "defensa y justicia", "defensa",
    "aldosivi",
}


def _es_relevante(nombre):
    return nombre.strip().lower() in EQUIPOS_A_REVISAR


def main():
    print("=" * 70)
    print("1) ¿Qué devuelve Promiedos AHORA MISMO para estos equipos?")
    print("=" * 70)
    partidos = obtener_partidos_jugados_lpf()
    relevantes = [
        p for p in partidos
        if _es_relevante(p["equipo_local"]) or _es_relevante(p["equipo_visitante"])
    ]
    if not relevantes:
        print("  (Promiedos no devolvió NINGÚN partido jugado de estos 6 equipos)")
    for p in relevantes:
        print(f"  local={p['equipo_local']!r}  "
              f"visitante={p['equipo_visitante']!r}  "
              f"goles={p['goles_local']}-{p['goles_visitante']}  "
              f"resuelve a: ({resolver_equipo_lpf(p['equipo_local'])!r}, "
              f"{resolver_equipo_lpf(p['equipo_visitante'])!r})")

    print()
    print("=" * 70)
    print("2) ¿Están en el FIXTURE PENDIENTE de Supabase (lpf)?")
    print("=" * 70)
    with transaction() as repo:
        pendientes = repo.match_records("lpf", "pending")
        jugados_db = repo.match_records("lpf", "played")
        tabla = repo.standing_records("lpf")

    pendientes_rel = [
        f for f in pendientes
        if _es_relevante(f["equipo_local"]) or _es_relevante(f["equipo_visitante"])
    ]
    if not pendientes_rel:
        print("  (NINGUNA fila pendiente para estos 6 equipos -> ya no hay nada")
        print("   que matchear, sea porque ya se cargaron o porque nunca se")
        print("   sembraron)")
    for f in pendientes_rel:
        print(f"  PENDIENTE: local={f['equipo_local']!r}  visitante={f['equipo_visitante']!r}")

    print()
    print("=" * 70)
    print("3) ¿Ya están en RESULTADOS (jugados) de Supabase (lpf)?")
    print("=" * 70)
    jugados_rel = [
        f for f in jugados_db
        if _es_relevante(f["equipo_local"]) or _es_relevante(f["equipo_visitante"])
    ]
    if not jugados_rel:
        print("  (Ninguno de estos 6 equipos tiene un resultado ya cargado)")
    for f in jugados_rel:
        print(f"  JUGADO: local={f['equipo_local']!r} {f.get('goles_local')}-"
              f"{f.get('goles_visitante')} {f['equipo_visitante']!r}")

    print()
    print("=" * 70)
    print("4) Partidos jugados en la TABLA DE POSICIONES (lpf) para estos equipos")
    print("=" * 70)
    tabla_rel = [f for f in tabla if _es_relevante(f["equipo"])]
    for f in sorted(tabla_rel, key=lambda x: x["equipo"]):
        print(f"  {f['equipo']!r}: partidos_jugados={f['partidos_jugados']}  puntos={f['puntos']}")


if __name__ == "__main__":
    main()
