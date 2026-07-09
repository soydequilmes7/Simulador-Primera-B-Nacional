# -*- coding: utf-8 -*-
"""
validar_etapa5_local.py

El addendum v15 (otra sesión de Claude) corrió SeasonEngine._correr_
competencias() con los 6 adapters reales pero los 6 main_X.py
STUBEADOS (sin CSV/DB a mano en esa sesión). Acá se corre lo mismo
pero con el motor Y los datos 100% reales del repo, parcheando
data_access para las 5 ligas + Copa (mismo patrón "Opción B" que ya
usa cada validar_etapa2_X_local.py, todos juntos de una vez).

Corrida en modo shadow (aplicar_promocion=False): no muta el
ClubRegistry, solo corre las 6 simulaciones y arma `resultados`.

Uso: python -m season.validar_etapa5_local
"""
from __future__ import annotations

import csv

import pandas as pd

RUTAS = {
    "nacional": ("datos/resultados.csv", "datos/fixture.csv", "datos/tabla.csv"),
    "lpf": ("datos/resultados_lpf.csv", "datos/fixture_lpf.csv", "datos/tablalpf.csv"),
    "bmetro": ("datos/resultados_bmetro.csv", "datos/fixture_bmetro.csv", "datos/tabla_bmetro.csv"),
    "federal_a": ("datos/resultados_federal_a.csv", "datos/fixture_federal_a.csv", "datos/tabla_federal_a.csv"),
    "primerac": ("datos/resultados_primerac.csv", "datos/fixture_primerac.csv", "datos/tabla_primerac.csv"),
}
PROMEDIOS_LPF_CSV = "datos/promedios_lpf.csv"
CUADRO_COPA_CSV = "datos/copa_argentina.csv"


def _league_data_local(competition_slug: str):
    rutas = RUTAS.get(competition_slug)
    if rutas is None:
        raise FileNotFoundError(f"slug sin ruta local configurada: {competition_slug!r}")
    resultados_csv, fixture_csv, tabla_csv = rutas
    return (
        pd.read_csv(resultados_csv, encoding="utf-8"),
        pd.read_csv(fixture_csv, encoding="utf-8"),
        pd.read_csv(tabla_csv, encoding="utf-8"),
    )


def _lpf_average_history_local():
    return pd.read_csv(PROMEDIOS_LPF_CSV, encoding="utf-8")


def _cup_records_local():
    with open(CUADRO_COPA_CSV, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _parchear_data_access():
    import data_access

    data_access.league_data = _league_data_local
    data_access.lpf_average_history_df = _lpf_average_history_local
    data_access.cup_records = _cup_records_local
    print("[validación local] data_access parcheado para las 5 ligas + Copa, leyendo CSV de datos/.")


def main():
    print("=" * 70)
    print("VALIDACIÓN ETAPA 5 (LOCAL, sin Supabase) -- las 6 competencias juntas")
    print("con SeasonEngine._correr_competencias() y el código/datos 100% reales")
    print("=" * 70)

    try:
        _parchear_data_access()
    except FileNotFoundError as e:
        print(f"\n❌ No encontré uno de los CSV esperados: {e}")
        return

    from season.season_engine import SeasonEngine, ADAPTERS
    from season.club_registry import ClubRegistry

    registry = ClubRegistry.build_from_current_data()
    engine = SeasonEngine(registry)

    print(f"\nADAPTERS registrados: {sorted(ADAPTERS.keys())}")
    print("Corriendo las 6 competencias juntas (n_sims=15, modo shadow)...\n")

    resultados = engine._correr_competencias(n_sims=15)

    errores = []
    for slug in ADAPTERS:
        if slug not in resultados:
            errores.append(f"Falta la clave '{slug}' en resultados")
            continue
        r = resultados[slug]
        print(f"[{slug}] campeon={r.campeon!r} | ascensos={r.ascensos} | "
              f"descensos={r.descensos} | clasificados_copa={r.clasificados_copa}")
        if slug != "copa" and r.campeon is None:
            errores.append(f"{slug}: campeon vino None")

    # Chequeos puntuales, mismo criterio que documenta el addendum v15.
    if resultados["lpf"].ascensos != []:
        errores.append(f"lpf.ascensos debería ser [] (máxima categoría): {resultados['lpf'].ascensos}")
    if len(resultados["lpf"].descensos) != 2:
        errores.append(f"lpf.descensos debería tener 2: {resultados['lpf'].descensos}")
    if not resultados["lpf"].ratings_finales:
        errores.append("lpf.ratings_finales vino vacío (necesario para el Apertura simulado siguiente)")
    if len(resultados["nacional"].ascensos) != 2:
        errores.append(f"nacional.ascensos debería tener 2: {resultados['nacional'].ascensos}")
    if len(resultados["nacional"].descensos) != 4:
        errores.append(f"nacional.descensos debería tener 4: {resultados['nacional'].descensos}")
    if not resultados["nacional"].ratings_finales:
        errores.append("nacional.ratings_finales vino vacío (necesario para el carryover a LPF)")
    if resultados["copa"].clasificados_copa != [resultados["copa"].campeon]:
        errores.append("copa.clasificados_copa debería ser [campeon]")

    print()
    print("=" * 70)
    if errores:
        print("❌ Encontré diferencias:")
        for e in errores:
            print(f"   - {e}")
    else:
        print("✅ Las 6 competencias corrieron juntas con código Y datos 100% reales,")
        print("   sin stubs -- primera vez que se confirma esto (antes solo se había")
        print("   probado con los 6 main_X.py stubeados). Sin aplicar promoción todavía")
        print("   (modo shadow): el ClubRegistry no se tocó.")
    print("=" * 70)


if __name__ == "__main__":
    main()
