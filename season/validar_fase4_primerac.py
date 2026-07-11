# -*- coding: utf-8 -*-
"""
season/validar_fase4_primerac.py

Validación de la Fase 4 del plan de HANDOFF_carryover_ratings.md:
motor season-only de Primera C (season/carryover_engines/primerac.py)
+ PrimeraCAdapter.run_desde_carryover().

No toca Supabase ni CSV reales -- datos sintéticos en memoria.

Correrlo desde la raíz del proyecto:

    python -m season.validar_fase4_primerac
"""
from __future__ import annotations

from dataclasses import dataclass, field

from modelos.club import Club
from season.adapters.primerac_adapter import PrimeraCAdapter
from season.carryover_engines.primerac import armar_ratings_iniciales, correr_temporada_desde_carryover
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
    print("\n[Parte A] armar_ratings_iniciales() -- continuidad + descendidos de B Metro")
    errores = []

    club_continua = Club(id=1, name="Club Continúa PrimeraC", division="Primera C")
    club_continua.history = [
        {"temporada": "2025", "division": "Primera C", "ratings": _rating(1.05, 0.95, 1.02, 0.98)},
    ]
    club_de_bmetro = Club(id=2, name="Club Desciende de BMetro", division="Primera C")
    registry = _FakeClubRegistry([club_continua, club_de_bmetro])

    resultados_anterior = {
        "primerac": _FakeResultadoTorneo(ratings_finales={
            "Club Continúa PrimeraC": _rating(1.10, 0.90, 1.00, 1.00),
        }),
        "bmetro": _FakeResultadoTorneo(ratings_finales={
            "Club Desciende de BMetro": _rating(0.80, 0.90, 1.20, 1.10),
        }),
    }
    roster = ["Club Continúa PrimeraC", "Club Desciende de BMetro", "Club Sin Historial En Ningún Lado"]

    obtenido = armar_ratings_iniciales(registry, resultados_anterior, roster)
    print(f"  obtenido: {obtenido}")

    esperado_continua = combinar_con_memoria(
        resultados_anterior["primerac"].ratings_finales["Club Continúa PrimeraC"], club_continua, "primerac"
    )
    errores += _comparar("Club Continúa PrimeraC", esperado_continua, obtenido["Club Continúa PrimeraC"])

    politica = RatingCarryoverPolicy()
    esperado_bmetro = politica.rating_para_recien_llegado(
        resultados_anterior["bmetro"].ratings_finales["Club Desciende de BMetro"], "bmetro", "primerac"
    )
    errores += _comparar("Club Desciende de BMetro", esperado_bmetro, obtenido["Club Desciende de BMetro"])

    esperado_generico = politica.rating_para_recien_llegado(None, None, "primerac")
    errores += _comparar(
        "Club Sin Historial En Ningún Lado (genérico)",
        esperado_generico,
        obtenido["Club Sin Historial En Ningún Lado"],
    )

    return errores


def _roster_16() -> tuple[list[str], dict[str, str]]:
    roster: list[str] = []
    zona_por_club: dict[str, str] = {}
    for zona in ("A", "B"):
        for i in range(1, 9):
            nombre = f"Club {zona}{i}"
            roster.append(nombre)
            zona_por_club[nombre] = zona
    return roster, zona_por_club


def validar_corrida_end_to_end() -> list:
    """Corrida real de correr_temporada_desde_carryover() (motor
    propio de la clase, SIN TOCAR: simular_fase_regular,
    jugar_final_ascenso(tablas), jugar_reducido). REDUCIDO_N implícito
    en la Primera Fase (2°-7° de cada zona) -- necesita >= 7 por zona."""
    print("\n[Parte B] Corrida real de correr_temporada_desde_carryover() (Primera C)")
    errores = []

    roster, zona_por_club = _roster_16()
    ratings_iniciales = {nombre: _rating(1.0, 1.0, 1.0, 1.0) for nombre in roster}
    ratings_iniciales["Club A1"] = _rating(1.8, 1.6, 0.6, 0.6)

    resultado = correr_temporada_desde_carryover(roster, zona_por_club, ratings_iniciales)

    print(f"  campeón (1er ascenso): {resultado.campeon}")
    print(f"  ascensos: {resultado.ascensos}")
    print(f"  descensos: {resultado.descensos}")
    print(f"  ratings_finales (Club A1): {resultado.ratings_finales.get('Club A1')}")

    if len(resultado.ascensos) != 2:
        errores.append(f"esperaba 2 ascensos (directo + reducido), dio {resultado.ascensos}")
    if resultado.descensos != []:
        errores.append(f"Primera C no debería tener descensos, dio {resultado.descensos}")
    if resultado.campeon not in roster:
        errores.append(f"campeón {resultado.campeon!r} no está en el roster")
    if set(resultado.ratings_finales.keys()) != set(roster):
        errores.append("ratings_finales no cubre todo el roster")

    try:
        correr_temporada_desde_carryover(roster, zona_por_club, {})
        errores.append("esperaba ValueError con ratings_iniciales vacío, no rompió")
    except ValueError:
        print("  OK -- ratings_iniciales incompleto levanta ValueError (fail-fast)")

    return errores


def validar_wiring_adapter() -> list:
    print("\n[Parte C] PrimeraCAdapter.run_desde_carryover() -- wiring completo")
    errores = []

    roster, zona_por_club = _roster_16()
    club_registry = _FakeClubRegistry([])
    resultados_anterior = {}

    adapter = PrimeraCAdapter()
    resultado = adapter.run_desde_carryover(roster, zona_por_club, club_registry, resultados_anterior)

    print(f"  campeón: {resultado.campeon}, ascensos: {resultado.ascensos}, descensos: {resultado.descensos}")
    if resultado.campeon not in roster:
        errores.append(f"campeón {resultado.campeon!r} no está en el roster")
    if resultado.descensos != []:
        errores.append("descensos debería ser [] siempre en Primera C")

    return errores


def main():
    print("=" * 70)
    print("VALIDACIÓN FASE 4 -- Primera C, motor season-only")
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
        print("✅ Todo OK -- Fase 4 (Primera C) validada.")
    print("=" * 70)


if __name__ == "__main__":
    main()
