# -*- coding: utf-8 -*-
"""
season/validar_wiring_api_local.py

Validación END-TO-END del wiring de api/index.py::_correr_temporada_
desde_estado() -- corre 2 rondas ENCADENADAS de Modo Temporada shadow
(mismo mecanismo que /api/season/play) con los CSV reales del repo
(vía _parchear_data_access(), mismo patrón que
season/validar_etapa5_local.py), sin Supabase.

Objetivo: confirmar que la RONDA 2 (la que ya tiene standings-en-cero
de nacional/bmetro/federal_a/primerac, armados por HistoryManager en
la Ronda 1) efectivamente usa los motores season-only -- ratings
iniciales distintos de 1.0/1.0 default -- en vez de caer en el
"agujero" documentado en HANDOFF_carryover_ratings.md.

Correrlo desde la raíz del proyecto:

    python -m season.validar_wiring_api_local
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


def _league_data_local(slug):
    resultados_csv, fixture_csv, tabla_csv = RUTAS[slug]
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
    # Sin esto, la Ronda 1 (sin datos_por_liga["lpf"]["campeon_apertura"]
    # todavía) cae al Supabase real -- no disponible en este sandbox.
    # None -> estadisticas_lpf.py usa el CAMPEON_APERTURA="Belgrano"
    # hardcodeado de la clase (mismo comportamiento que documenta
    # data_access.campeon_apertura_lpf() para "sin nada guardado").
    data_access.campeon_apertura_lpf = lambda: None
    # guardar_campeon_apertura_lpf() lo llama HistoryManager con un
    # callable inyectado (ver su __init__, ADDENDUM v13) -- pero por
    # las dudas, no-op acá también si algo lo llamara directo.
    data_access.guardar_campeon_apertura_lpf = lambda campeon: None


def main():
    print("=" * 70)
    print("VALIDACIÓN END-TO-END -- wiring de api/index.py, 2 rondas encadenadas")
    print("(CSV reales del repo, sin Supabase)")
    print("=" * 70)

    _parchear_data_access()

    from api.index import _correr_temporada_desde_estado

    errores = []

    # ------------------------------------------------------------
    # RONDA 1: estado_anterior=None -- datos reales, camino normal
    # para las 5 divisiones (todavía no hay standings-en-cero de
    # Modo Temporada que traer). Con aplicar_promocion=True para que
    # persist_season() arme la Ronda 2 en memoria.
    # ------------------------------------------------------------
    print("\n--- Ronda 1 (datos reales, camino normal esperado) ---")
    resultados_1, promocion_1, proximo_estado_1, _, _ = _correr_temporada_desde_estado(
        estado_anterior=None, numero_ronda=1, aplicar_promocion=True,
    )
    print(f"  movimientos de promoción: {len(promocion_1.get('movimientos', []))}")
    print(f"  ratings_finales_por_liga capturados: {list(proximo_estado_1.get('ratings_finales_por_liga', {}).keys())}")
    print(f"  history_por_club: {len(proximo_estado_1.get('history_por_club', {}))} clubes")

    if not proximo_estado_1.get("ratings_finales_por_liga"):
        errores.append("Ronda 1: ratings_finales_por_liga vino vacío -- no hay nada para heredar en la Ronda 2")
    if not proximo_estado_1.get("history_por_club"):
        errores.append("Ronda 1: history_por_club vino vacío")
    # Nacional siempre llena ratings_finales por su camino NORMAL (ver
    # main.py::_ratings_finales_nacional) -- debería estar sí o sí.
    if "nacional" not in proximo_estado_1.get("ratings_finales_por_liga", {}):
        errores.append("Ronda 1: 'nacional' no está en ratings_finales_por_liga (main.py siempre lo llena)")

    # Un club de Nacional cualquiera tiene que tener 1 entrada de
    # history con la clave 'ratings' (Fase 0 -- ver
    # HistoryManager._actualizar_history()).
    algun_club_nacional = next(
        (nombre for nombre, div in proximo_estado_1["roster"].items() if div == "Primera Nacional"), None
    )
    if algun_club_nacional is None:
        errores.append("Ronda 1: no encontré ningún club en 'Primera Nacional' en el roster siguiente")
    else:
        entradas = proximo_estado_1["history_por_club"].get(algun_club_nacional, [])
        print(f"  history de '{algun_club_nacional}': {entradas}")
        if not entradas or "ratings" not in entradas[-1]:
            errores.append(
                f"Ronda 1: '{algun_club_nacional}' no tiene 'ratings' en su última entrada de history "
                f"(entradas: {entradas})"
            )

    # ------------------------------------------------------------
    # RONDA 2: estado_anterior = proximo_estado_1 -- ACÁ es donde
    # nacional/bmetro/federal_a/primerac tienen que usar los motores
    # season-only (standings-en-cero armados por la Ronda 1).
    # ------------------------------------------------------------
    print("\n--- Ronda 2 (standings-en-cero de la Ronda 1 -- motor season-only esperado) ---")
    resultados_2, promocion_2, proximo_estado_2, _, _ = _correr_temporada_desde_estado(
        estado_anterior=proximo_estado_1, numero_ronda=2, aplicar_promocion=True,
    )

    for slug in ("nacional", "bmetro", "federal_a", "primerac"):
        r = resultados_2[slug]
        print(f"  [{slug}] campeón/ascenso_1: {r.campeon} | ascensos: {r.ascensos} | descensos: {len(r.descensos)}")
        if not r.ratings_finales:
            errores.append(
                f"Ronda 2 [{slug}]: ratings_finales vacío -- si esta división pasó por el motor "
                "season-only, debería venir lleno (a diferencia de su camino normal)."
            )

    # Chequeo más directo: los ratings iniciales que USÓ el motor para
    # la Ronda 2 no pueden ser todos 1.0/1.0 (el bug que esto arregla)
    # -- se re-deriva llamando armar_ratings_iniciales() con el mismo
    # contexto que usó _correr_temporada_desde_estado() por dentro,
    # para confirmar que efectivamente hay variación.
    from season.club_registry import ClubRegistry
    from season.carryover_engines import nacional as motor_nacional
    from season.tournament_adapter import ResultadoTorneo

    registry_r2 = ClubRegistry()
    for nombre, division in proximo_estado_1["roster"].items():
        registry_r2.agregar_club(nombre, division)
    for nombre, entradas in proximo_estado_1.get("history_por_club", {}).items():
        club = registry_r2.get_by_name(nombre)
        if club is not None:
            club.history = entradas

    resultados_anterior_r2 = {
        slug: ResultadoTorneo(campeon=None, ratings_finales=ratings)
        for slug, ratings in proximo_estado_1.get("ratings_finales_por_liga", {}).items()
    }
    roster_nacional_r2 = [c.name for c in registry_r2.get_by_division("Primera Nacional")]
    ratings_iniciales_nacional_r2 = motor_nacional.armar_ratings_iniciales(
        registry_r2, resultados_anterior_r2, roster_nacional_r2
    )
    todos_default = all(
        r == {"ataque_local": 1.0, "ataque_visitante": 1.0, "defensa_local": 1.0, "defensa_visitante": 1.0}
        for r in ratings_iniciales_nacional_r2.values()
    )
    print(f"\n  ratings iniciales de Nacional para la Ronda 2 (primeros 3): "
          f"{dict(list(ratings_iniciales_nacional_r2.items())[:3])}")
    if todos_default:
        errores.append(
            "Ronda 2: TODOS los ratings iniciales de Nacional quedaron en el default 1.0/1.0 -- "
            "el carryover no está teniendo ningún efecto."
        )
    else:
        print("  OK -- hay variación real entre clubes (no todos 1.0/1.0 default)")

    print("\n" + "=" * 70)
    if errores:
        print(f"❌ {len(errores)} error(es):")
        for e in errores:
            print(f"  - {e}")
    else:
        print("✅ Todo OK -- el wiring de api/index.py funciona de punta a punta en 2 rondas.")
    print("=" * 70)


if __name__ == "__main__":
    main()
