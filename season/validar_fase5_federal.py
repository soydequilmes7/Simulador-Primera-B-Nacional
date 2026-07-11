# -*- coding: utf-8 -*-
"""
season/validar_fase5_federal.py

Validación de la Fase 5 del plan de HANDOFF_carryover_ratings.md:
motor season-only del Torneo Federal A
(season/carryover_engines/federal.py) + FederalAdapter.run_desde_carryover().

No toca Supabase ni CSV reales -- datos sintéticos en memoria. Esta es
la corrida más pesada de las 5 fases (37 clubes, 5 Fases + Reválida de
6 Etapas) -- puede tardar unos segundos más que las otras.

Correrlo desde la raíz del proyecto:

    python -m season.validar_fase5_federal
"""
from __future__ import annotations

from dataclasses import dataclass, field

from modelos.club import Club
from season.adapters.federal_adapter import FederalAdapter
from season.carryover_engines.federal import armar_ratings_iniciales, correr_temporada_desde_carryover
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
    print("\n[Parte A] armar_ratings_iniciales() -- continuidad + descendidos de Nacional + relleno")
    errores = []

    club_continua = Club(id=1, name="Club Continúa Federal", division="Federal A")
    club_continua.history = [
        {"temporada": "2025", "division": "Federal A", "ratings": _rating(1.05, 0.95, 1.02, 0.98)},
    ]
    club_de_nacional = Club(id=2, name="Club Desciende de Nacional", division="Federal A")
    club_relleno = Club(id=3, name="Club Relleno Revalida", division="Federal A")  # sin historial
    registry = _FakeClubRegistry([club_continua, club_de_nacional, club_relleno])

    resultados_anterior = {
        "federal_a": _FakeResultadoTorneo(ratings_finales={
            "Club Continúa Federal": _rating(1.10, 0.90, 1.00, 1.00),
        }),
        "nacional": _FakeResultadoTorneo(ratings_finales={
            "Club Desciende de Nacional": _rating(0.85, 0.95, 1.15, 1.05),
        }),
    }
    roster = ["Club Continúa Federal", "Club Desciende de Nacional", "Club Relleno Revalida"]

    obtenido = armar_ratings_iniciales(registry, resultados_anterior, roster)
    print(f"  obtenido: {obtenido}")

    esperado_continua = combinar_con_memoria(
        resultados_anterior["federal_a"].ratings_finales["Club Continúa Federal"], club_continua, "federal_a"
    )
    errores += _comparar("Club Continúa Federal", esperado_continua, obtenido["Club Continúa Federal"])

    politica = RatingCarryoverPolicy()
    esperado_nacional = politica.rating_para_recien_llegado(
        resultados_anterior["nacional"].ratings_finales["Club Desciende de Nacional"], "nacional", "federal_a"
    )
    errores += _comparar("Club Desciende de Nacional", esperado_nacional, obtenido["Club Desciende de Nacional"])

    esperado_generico = politica.rating_para_recien_llegado(None, None, "federal_a")
    errores += _comparar("Club Relleno Revalida (genérico)", esperado_generico, obtenido["Club Relleno Revalida"])

    return errores


def _roster_37() -> tuple[list[str], dict[str, str]]:
    """Mismo reparto real: zona '1' (ZONA_DIEZ) con 10 clubes,
    '2'/'3'/'4' con 9 cada una -- ver docstring de
    carryover_engines/federal.py sobre por qué esto importa."""
    roster: list[str] = []
    zona_por_club: dict[str, str] = {}
    tamanios = {"1": 10, "2": 9, "3": 9, "4": 9}
    for zona, n in tamanios.items():
        for i in range(1, n + 1):
            nombre = f"Club {zona}-{i}"
            roster.append(nombre)
            zona_por_club[nombre] = zona
    assert len(roster) == 37
    return roster, zona_por_club


def validar_corrida_end_to_end() -> list:
    """Corrida real de correr_temporada_desde_carryover() -- reproduce
    las 5 Fases + Reválida de 6 Etapas, TODAS con los métodos propios
    de EstadisticasFederal sin tocar una línea."""
    print("\n[Parte B] Corrida real de correr_temporada_desde_carryover() (Federal A, 37 clubes)")
    errores = []

    roster, zona_por_club = _roster_37()
    ratings_iniciales = {nombre: _rating(1.0, 1.0, 1.0, 1.0) for nombre in roster}
    ratings_iniciales["Club 1-1"] = _rating(1.8, 1.6, 0.6, 0.6)  # ventaja clara

    resultado = correr_temporada_desde_carryover(roster, zona_por_club, ratings_iniciales)

    print(f"  campeón (1er ascenso): {resultado.campeon}")
    print(f"  ascensos: {resultado.ascensos}")
    print(f"  descensos: {resultado.descensos}")
    print(f"  ratings_finales (Club 1-1): {resultado.ratings_finales.get('Club 1-1')}")

    if len(resultado.ascensos) != 2:
        errores.append(f"esperaba 2 ascensos (1er ascenso + Reválida), dio {resultado.ascensos}")
    if resultado.ascensos[0] == resultado.ascensos[1]:
        errores.append("el mismo club no puede ascender dos veces (1er ascenso y Reválida)")
    if len(resultado.descensos) != 4:
        errores.append(f"esperaba 4 descensos (2 por zona de Reválida), dio {resultado.descensos}")
    if len(set(resultado.descensos)) != 4:
        errores.append(f"descensos duplicados: {resultado.descensos}")
    if resultado.campeon not in roster:
        errores.append(f"campeón {resultado.campeon!r} no está en el roster")
    for nombre in resultado.ascensos + resultado.descensos:
        if nombre not in roster:
            errores.append(f"{nombre!r} no está en el roster de 37 clubes")
    if set(resultado.ratings_finales.keys()) != set(roster):
        errores.append("ratings_finales no cubre todo el roster")

    try:
        correr_temporada_desde_carryover(roster, zona_por_club, {})
        errores.append("esperaba ValueError con ratings_iniciales vacío, no rompió")
    except ValueError:
        print("  OK -- ratings_iniciales incompleto levanta ValueError (fail-fast)")

    return errores


def validar_wiring_adapter() -> list:
    print("\n[Parte C] FederalAdapter.run_desde_carryover() -- wiring completo")
    errores = []

    roster, zona_por_club = _roster_37()
    club_registry = _FakeClubRegistry([])
    resultados_anterior = {}

    adapter = FederalAdapter()
    resultado = adapter.run_desde_carryover(roster, zona_por_club, club_registry, resultados_anterior)

    print(f"  campeón: {resultado.campeon}, ascensos: {resultado.ascensos}, descensos: {len(resultado.descensos)}")
    if resultado.campeon not in roster:
        errores.append(f"campeón {resultado.campeon!r} no está en el roster")
    if len(resultado.descensos) != 4:
        errores.append(f"esperaba 4 descensos, dio {len(resultado.descensos)}")

    return errores


def main():
    print("=" * 70)
    print("VALIDACIÓN FASE 5 -- Federal A, motor season-only")
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
        print("✅ Todo OK -- Fase 5 (Federal A) validada.")
    print("=" * 70)


if __name__ == "__main__":
    main()
