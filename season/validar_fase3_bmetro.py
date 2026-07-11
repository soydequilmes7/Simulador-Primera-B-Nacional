# -*- coding: utf-8 -*-
"""
season/validar_fase3_bmetro.py

Validación de la Fase 3 del plan de HANDOFF_carryover_ratings.md:
motor season-only de B Metro (season/carryover_engines/bmetro.py) +
BMetroAdapter.run_desde_carryover().

No toca Supabase ni CSV reales -- datos sintéticos en memoria.

Correrlo desde la raíz del proyecto:

    python -m season.validar_fase3_bmetro
"""
from __future__ import annotations

from dataclasses import dataclass, field

from modelos.club import Club
from modelos.estadisticas_bmetro import EstadisticasBMetro
from season.adapters.bmetro_adapter import BMetroAdapter
from season.carryover_engines.bmetro import armar_ratings_iniciales, correr_temporada_desde_carryover
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
    print("\n[Parte A] armar_ratings_iniciales() -- continuidad + ascendidos de Nacional/Primera C")
    errores = []

    club_continua = Club(id=1, name="Club Continúa BMetro", division="Primera B Metropolitana")
    club_continua.history = [
        {"temporada": "2025", "division": "Primera B Metropolitana", "ratings": _rating(1.05, 0.95, 1.02, 0.98)},
    ]
    club_de_nacional = Club(id=2, name="Club Desciende de Nacional", division="Primera B Metropolitana")
    club_de_primerac = Club(id=3, name="Club Asciende de Primera C", division="Primera B Metropolitana")
    registry = _FakeClubRegistry([club_continua, club_de_nacional, club_de_primerac])

    resultados_anterior = {
        "bmetro": _FakeResultadoTorneo(ratings_finales={
            "Club Continúa BMetro": _rating(1.10, 0.90, 1.00, 1.00),
        }),
        "nacional": _FakeResultadoTorneo(ratings_finales={
            "Club Desciende de Nacional": _rating(0.85, 0.95, 1.15, 1.05),
        }),
        "primerac": _FakeResultadoTorneo(ratings_finales={}),  # vacío -> genérico
    }
    roster = ["Club Continúa BMetro", "Club Desciende de Nacional", "Club Asciende de Primera C"]

    obtenido = armar_ratings_iniciales(registry, resultados_anterior, roster)
    print(f"  obtenido: {obtenido}")

    esperado_continua = combinar_con_memoria(
        resultados_anterior["bmetro"].ratings_finales["Club Continúa BMetro"], club_continua, "bmetro"
    )
    errores += _comparar("Club Continúa BMetro", esperado_continua, obtenido["Club Continúa BMetro"])

    politica = RatingCarryoverPolicy()
    esperado_nacional = politica.rating_para_recien_llegado(
        resultados_anterior["nacional"].ratings_finales["Club Desciende de Nacional"], "nacional", "bmetro"
    )
    errores += _comparar("Club Desciende de Nacional", esperado_nacional, obtenido["Club Desciende de Nacional"])

    esperado_generico = politica.rating_para_recien_llegado(None, None, "bmetro")
    errores += _comparar("Club Asciende de Primera C (genérico)", esperado_generico, obtenido["Club Asciende de Primera C"])

    return errores


def validar_corrida_end_to_end() -> list:
    """Corrida real de correr_temporada_desde_carryover() -- motor
    heredado SIN TOCAR: simular_fase_regular, obtener_puntero,
    jugar_reducido_bmetro. REDUCIDO_N=9 -> necesita >= 9 clubes."""
    print("\n[Parte B] Corrida real de correr_temporada_desde_carryover() (B Metro)")
    errores = []

    roster = [f"Club {i}" for i in range(1, 23)]  # 22 clubes, tamaño real típico
    ratings_iniciales = {nombre: _rating(1.0, 1.0, 1.0, 1.0) for nombre in roster}
    ratings_iniciales["Club 1"] = _rating(1.8, 1.6, 0.6, 0.6)  # ventaja clara

    resultado = correr_temporada_desde_carryover(roster, ratings_iniciales)

    print(f"  campeon (=puntero ascenso directo): {resultado.campeon}")
    print(f"  ascensos: {resultado.ascensos}")
    print(f"  descensos: {resultado.descensos}")
    print(f"  ratings_finales (Club 1): {resultado.ratings_finales.get('Club 1')}")

    if len(resultado.ascensos) != 2:
        errores.append(f"esperaba 2 ascensos (directo + reducido), dio {resultado.ascensos}")
    if len(resultado.descensos) != EstadisticasBMetro.DESCENSOS_N:
        errores.append(f"esperaba {EstadisticasBMetro.DESCENSOS_N} descensos, dio {resultado.descensos}")
    if resultado.campeon not in roster:
        errores.append(f"campeón {resultado.campeon!r} no está en el roster")
    if set(resultado.ratings_finales.keys()) != set(roster):
        errores.append("ratings_finales no cubre todo el roster")

    # Fail-fast: menos de REDUCIDO_N clubes tiene que romper.
    try:
        correr_temporada_desde_carryover(roster[:5], {n: _rating(1, 1, 1, 1) for n in roster[:5]})
        errores.append("esperaba ValueError con menos de REDUCIDO_N clubes, no rompió")
    except ValueError:
        print(f"  OK -- menos de {EstadisticasBMetro.REDUCIDO_N} clubes levanta ValueError (fail-fast)")

    # Fail-fast: ratings_iniciales incompleto.
    try:
        correr_temporada_desde_carryover(roster, {})
        errores.append("esperaba ValueError con ratings_iniciales vacío, no rompió")
    except ValueError:
        print("  OK -- ratings_iniciales incompleto levanta ValueError (fail-fast)")

    return errores


def validar_wiring_adapter() -> list:
    print("\n[Parte C] BMetroAdapter.run_desde_carryover() -- wiring completo")
    errores = []

    roster = [f"Club {i}" for i in range(1, 23)]
    club_registry = _FakeClubRegistry([])
    resultados_anterior = {}

    adapter = BMetroAdapter()
    resultado = adapter.run_desde_carryover(roster, club_registry, resultados_anterior)

    print(f"  campeón: {resultado.campeon}, ascensos: {resultado.ascensos}, descensos: {resultado.descensos}")
    if resultado.campeon not in roster:
        errores.append(f"campeón {resultado.campeon!r} no está en el roster")
    if len(resultado.descensos) != EstadisticasBMetro.DESCENSOS_N:
        errores.append(f"esperaba {EstadisticasBMetro.DESCENSOS_N} descensos, dio {len(resultado.descensos)}")

    return errores


def main():
    print("=" * 70)
    print("VALIDACIÓN FASE 3 -- B Metro, motor season-only")
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
        print("✅ Todo OK -- Fase 3 (B Metro) validada.")
    print("=" * 70)


if __name__ == "__main__":
    main()
