# -*- coding: utf-8 -*-
"""
season/validar_fase2_nacional.py

Validación de la Fase 2 del plan de HANDOFF_carryover_ratings.md:
motor season-only de Primera Nacional
(season/carryover_engines/nacional.py) + NacionalAdapter.run_desde_carryover().

No toca Supabase ni CSV reales -- datos sintéticos en memoria, mismo
espíritu que validar_fase0_carryover.py / validar_fase1_lpf.py.

Correrlo desde la raíz del proyecto:

    python -m season.validar_fase2_nacional
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from modelos.club import Club
from season.adapters.nacional_adapter import NacionalAdapter
from season.carryover_engines.nacional import armar_ratings_iniciales, correr_temporada_desde_carryover
from season.rating_carryover import CAMPOS_RATING, combinar_con_memoria, RatingCarryoverPolicy


def _comparar(nombre_caso: str, esperado: dict, obtenido: dict, tolerancia=1e-9) -> list:
    errores = []
    for campo in CAMPOS_RATING:
        if abs(esperado[campo] - obtenido[campo]) > tolerancia:
            errores.append(
                f"[{nombre_caso}] {campo}: esperado {esperado[campo]}, obtenido {obtenido[campo]}"
            )
    return errores


def _rating(a_l, a_v, d_l, d_v) -> dict:
    return {"ataque_local": a_l, "ataque_visitante": a_v, "defensa_local": d_l, "defensa_visitante": d_v}


@dataclass
class _FakeResultadoTorneo:
    ratings_finales: dict = field(default_factory=dict)


class _FakeClubRegistry:
    def __init__(self, clubes: list[Club]):
        self._por_nombre = {c.name: c for c in clubes}

    def get_by_name(self, name: str):
        return self._por_nombre.get(name)


def validar_armar_ratings_iniciales() -> list:
    print("\n[Parte A] armar_ratings_iniciales() -- continuidad + ascendidos de BMetro/Federal A")
    errores = []

    club_continua = Club(id=1, name="Club Continúa", division="Primera Nacional")
    club_continua.history = [
        {"temporada": "2025", "division": "Primera Nacional", "ratings": _rating(1.05, 0.95, 1.02, 0.98)},
    ]
    club_de_bmetro = Club(id=2, name="Club Asciende BMetro", division="Primera Nacional")  # ya promocionado
    club_de_federal = Club(id=3, name="Club Asciende Federal", division="Primera Nacional")
    registry = _FakeClubRegistry([club_continua, club_de_bmetro, club_de_federal])

    resultados_anterior = {
        "nacional": _FakeResultadoTorneo(ratings_finales={
            "Club Continúa": _rating(1.10, 0.90, 1.00, 1.00),
        }),
        "bmetro": _FakeResultadoTorneo(ratings_finales={
            "Club Asciende BMetro": _rating(1.25, 1.05, 0.95, 0.90),
        }),
        "federal_a": _FakeResultadoTorneo(ratings_finales={}),  # vacío a propósito
    }
    roster = ["Club Continúa", "Club Asciende BMetro", "Club Asciende Federal"]

    obtenido = armar_ratings_iniciales(registry, resultados_anterior, roster)
    print(f"  obtenido: {obtenido}")

    # Club Continúa: combinar_con_memoria(rating_actual=ratings_finales["nacional"], club, "nacional")
    esperado_continua = combinar_con_memoria(
        resultados_anterior["nacional"].ratings_finales["Club Continúa"], club_continua, "nacional"
    )
    errores += _comparar("Club Continúa", esperado_continua, obtenido["Club Continúa"])

    # Club Asciende BMetro: rating_para_recien_llegado(origen=bmetro)
    politica = RatingCarryoverPolicy()
    esperado_bmetro = politica.rating_para_recien_llegado(
        resultados_anterior["bmetro"].ratings_finales["Club Asciende BMetro"], "bmetro", "nacional"
    )
    errores += _comparar("Club Asciende BMetro", esperado_bmetro, obtenido["Club Asciende BMetro"])

    # Club Asciende Federal: no está en bmetro.ratings_finales ni en
    # federal_a.ratings_finales (vacío a propósito) -> genérico.
    esperado_federal = politica.rating_para_recien_llegado(None, None, "nacional")
    errores += _comparar("Club Asciende Federal (genérico)", esperado_federal, obtenido["Club Asciende Federal"])

    # club_registry=None -> degrada a "sin memoria" (usa el crudo tal cual)
    obtenido_sin_registry = armar_ratings_iniciales(None, resultados_anterior, ["Club Continúa"])
    errores += _comparar(
        "Club Continúa sin club_registry",
        resultados_anterior["nacional"].ratings_finales["Club Continúa"],
        obtenido_sin_registry["Club Continúa"],
    )

    return errores


def _roster_16(n_por_zona: int = 8) -> tuple[list[str], dict[str, str]]:
    roster: list[str] = []
    zona_por_club: dict[str, str] = {}
    for zona in ("A", "B"):
        for i in range(1, n_por_zona + 1):
            nombre = f"Club {zona}{i}"
            roster.append(nombre)
            zona_por_club[nombre] = zona
    return roster, zona_por_club


def validar_corrida_end_to_end() -> list:
    """Corrida real de correr_temporada_desde_carryover() (motor
    heredado SIN TOCAR: simular_fase_regular, jugar_final_ascenso,
    jugar_reducido) -- confirma que arma un ResultadoTorneo completo y
    consistente, con 4 descensos (últimos 2 de cada zona) y 2 ascensos
    (directo + reducido)."""
    print("\n[Parte B] Corrida real de correr_temporada_desde_carryover()")
    errores = []

    roster, zona_por_club = _roster_16()
    ratings_iniciales = {nombre: _rating(1.0, 1.0, 1.0, 1.0) for nombre in roster}
    # Un club con ventaja clara de ataque, para chequear cualitativamente
    # que el motor responde a los ratings inyectados (no es determinista
    # -- Dixon-Coles + shock Gamma -- así que no se afirma el resultado
    # exacto, solo que no rompe y que el shape es correcto).
    ratings_iniciales["Club A1"] = _rating(1.8, 1.6, 0.6, 0.6)

    resultado = correr_temporada_desde_carryover(roster, zona_por_club, ratings_iniciales)

    print(f"  campeón: {resultado.campeon}")
    print(f"  ascensos: {resultado.ascensos}")
    print(f"  descensos: {resultado.descensos}")
    print(f"  ratings_finales (Club A1): {resultado.ratings_finales.get('Club A1')}")

    if len(resultado.ascensos) != 2:
        errores.append(f"esperaba 2 ascensos (directo + reducido), dio {resultado.ascensos}")
    if len(resultado.descensos) != 4:
        errores.append(f"esperaba 4 descensos (2 por zona), dio {resultado.descensos}")
    if resultado.campeon not in roster:
        errores.append(f"campeón {resultado.campeon!r} no está en el roster")
    if set(resultado.ratings_finales.keys()) != set(roster):
        errores.append("ratings_finales no cubre todo el roster")
    if resultado.clasificados_copa != []:
        errores.append("clasificados_copa debería quedar vacío (Nacional no alimenta copas internacionales acá)")

    # Fail-fast: ratings_iniciales incompleto tiene que romper con
    # ValueError, no arrancar un equipo con el default 1.0/1.0 silencioso.
    try:
        correr_temporada_desde_carryover(roster, zona_por_club, {})
        errores.append("esperaba ValueError con ratings_iniciales vacío, no rompió")
    except ValueError:
        print("  OK -- ratings_iniciales incompleto levanta ValueError (fail-fast)")

    return errores


def validar_wiring_adapter() -> list:
    """NacionalAdapter.run_desde_carryover() -- confirma que el wiring
    del adapter llega al motor y devuelve un ResultadoTorneo real,
    sin pasar por main.correr_simulacion() en ningún momento."""
    print("\n[Parte C] NacionalAdapter.run_desde_carryover() -- wiring completo")
    errores = []

    roster, zona_por_club = _roster_16()
    club_registry = _FakeClubRegistry([])  # ninguno con historial -- todos "recién llegados"
    resultados_anterior = {}  # sin datos de la temporada anterior -- degrada a genérico

    adapter = NacionalAdapter()
    resultado = adapter.run_desde_carryover(roster, zona_por_club, club_registry, resultados_anterior)

    print(f"  campeón: {resultado.campeon}, ascensos: {resultado.ascensos}, descensos: {len(resultado.descensos)}")
    if resultado.campeon not in roster:
        errores.append(f"campeón {resultado.campeon!r} no está en el roster")
    if len(resultado.descensos) != 4:
        errores.append(f"esperaba 4 descensos, dio {len(resultado.descensos)}")

    return errores


def main():
    print("=" * 70)
    print("VALIDACIÓN FASE 2 -- Nacional, motor season-only")
    print("(HANDOFF_carryover_ratings.md)")
    print("=" * 70)

    errores = []
    errores += validar_armar_ratings_iniciales()
    errores += validar_corrida_end_to_end()
    errores += validar_wiring_adapter()

    print("\n" + "=" * 70)
    if errores:
        print(f"❌ {len(errores)} error(es):")
        for e in errores:
            print(f"  - {e}")
    else:
        print("✅ Todo OK -- Fase 2 (Nacional) validada.")
    print("=" * 70)


if __name__ == "__main__":
    main()
