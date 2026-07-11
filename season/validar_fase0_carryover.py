# -*- coding: utf-8 -*-
"""
season/validar_fase0_carryover.py

Validación de la Fase 0 del plan de HANDOFF_carryover_ratings.md:
memoria EWMA + handicap de adaptación (season/rating_carryover.py) y
el fix de _actualizar_history() (season/history_manager.py) que ahora
guarda ratings y corrige qué división queda registrada.

No toca Supabase ni ningún CSV real -- todo con datos sintéticos en
memoria, mismo espíritu que season/validar_etapa3.py.

Correrlo desde la raíz del proyecto:

    python -m season.validar_fase0_carryover
"""
from __future__ import annotations

from dataclasses import dataclass, field

from modelos.club import Club
from season.rating_carryover import (
    RatingCarryoverPolicy,
    ALPHA_MEMORIA,
    N_TEMPORADAS_HANDICAP,
    CAMPOS_RATING,
    memoria_ewma,
    temporadas_consecutivas_en_division,
    combinar_con_memoria,
    _factor_handicap,
)


def _comparar(nombre_caso: str, esperado: dict, obtenido: dict, tolerancia=1e-9) -> list:
    errores = []
    for campo in CAMPOS_RATING:
        if abs(esperado[campo] - obtenido[campo]) > tolerancia:
            errores.append(
                f"[{nombre_caso}] {campo}: esperado {esperado[campo]}, obtenido {obtenido[campo]}"
            )
    return errores


def _rating(a_l, a_v, d_l, d_v) -> dict:
    return {
        "ataque_local": a_l,
        "ataque_visitante": a_v,
        "defensa_local": d_l,
        "defensa_visitante": d_v,
    }


# ----------------------------------------------------------------
# Parte A: _factor_handicap() -- se disuelve en N_TEMPORADAS_HANDICAP
# ----------------------------------------------------------------
def validar_factor_handicap() -> list:
    print("\n[Parte A] _factor_handicap() -- decaimiento del handicap")
    errores = []
    esperados = {0: 1 / 3, 1: 2 / 3, 2: 1.0, 3: 1.0, 10: 1.0}
    for temporadas, esperado in esperados.items():
        obtenido = _factor_handicap(temporadas)
        print(f"  temporadas_consecutivas={temporadas} -> {obtenido:.4f} (esperado {esperado:.4f})")
        if abs(obtenido - esperado) > 1e-9:
            errores.append(f"[handicap] temporadas={temporadas}: esperado {esperado}, dio {obtenido}")
    return errores


# ----------------------------------------------------------------
# Parte B: rating_para_recien_llegado() ahora incluye el handicap de
# la temporada 1 (factor 1/3 adicional sobre el ajuste de nivel).
# ----------------------------------------------------------------
def validar_recien_llegado_con_handicap() -> list:
    print("\n[Parte B] rating_para_recien_llegado() con handicap de temporada 1")
    errores = []
    politica = RatingCarryoverPolicy()

    ratings_origen = _rating(1.30, 0.85, 1.10, 0.95)
    obtenido = politica.rating_para_recien_llegado(ratings_origen, "federal_a", "bmetro")

    # Reimplementación manual CON handicap (mismo nivel federal_a/bmetro
    # -> factor de nivel = 1.0, factor_handicap(0) = 1/3).
    from season.rating_carryover import NIVEL_DIVISION, N_CARRYOVER, K_REGRESION
    factor = (NIVEL_DIVISION["federal_a"] / NIVEL_DIVISION["bmetro"]) * (1 / 3)
    esperado = {}
    for campo in CAMPOS_RATING:
        valor_ajustado = 1.0 + (ratings_origen[campo] - 1.0) * factor
        esperado[campo] = round((N_CARRYOVER * valor_ajustado + K_REGRESION * 1.0) / (N_CARRYOVER + K_REGRESION), 3)

    print(f"  ratings_origen: {ratings_origen}")
    print(f"  esperado (con handicap 1/3): {esperado}")
    print(f"  obtenido: {obtenido}")
    errores += _comparar("recien_llegado con handicap", esperado, obtenido)

    # Chequeo cualitativo: el resultado con handicap debe estar MÁS
    # cerca de 1.0 (promedio de liga) que el que daría la fórmula
    # vieja (sin el factor 1/3) -- confirma que el handicap comprime.
    factor_sin_handicap = NIVEL_DIVISION["federal_a"] / NIVEL_DIVISION["bmetro"]
    for campo in CAMPOS_RATING:
        valor_ajustado_viejo = 1.0 + (ratings_origen[campo] - 1.0) * factor_sin_handicap
        viejo = round((N_CARRYOVER * valor_ajustado_viejo + K_REGRESION * 1.0) / (N_CARRYOVER + K_REGRESION), 3)
        distancia_nueva = abs(obtenido[campo] - 1.0)
        distancia_vieja = abs(viejo - 1.0)
        if not (distancia_nueva <= distancia_vieja):
            errores.append(
                f"[recien_llegado, chequeo compresión] {campo}: con handicap ({obtenido[campo]}) "
                f"no quedó más cerca de 1.0 que sin handicap ({viejo})"
            )
    return errores


# ----------------------------------------------------------------
# Parte C: memoria_ewma() / temporadas_consecutivas_en_division() /
# combinar_con_memoria() sobre un Club con historial sintético.
# ----------------------------------------------------------------
def validar_memoria_y_handicap_continuidad() -> list:
    print("\n[Parte C] memoria EWMA + handicap para clubes que continúan")
    errores = []

    # Club recién ascendido a Nacional hace 2 temporadas: una entrada
    # de handicap (Primera C, sin ratings -- simula que antes de esta
    # Fase 0 no se guardaban) + 2 temporadas ya jugadas EN Nacional
    # con ratings reales.
    club = Club(id=1, name="Club Ejemplo", division="Primera Nacional")
    club.history = [
        {"temporada": "2024", "division": "Primera C"},  # antes de ascender, sin ratings (pre-Fase 0)
        {"temporada": "2025", "division": "Primera Nacional", "ratings": _rating(1.05, 0.95, 1.02, 0.98)},
        {"temporada": "2026", "division": "Primera Nacional", "ratings": _rating(1.10, 0.90, 1.05, 0.95)},
    ]

    temporadas = temporadas_consecutivas_en_division(club, "nacional")
    print(f"  temporadas_consecutivas_en_division(nacional) = {temporadas} (esperado 2)")
    if temporadas != 2:
        errores.append(f"[temporadas_consecutivas] esperado 2, dio {temporadas}")

    memoria = memoria_ewma(club, "nacional")
    ewma_manual = dict(club.history[1]["ratings"])
    for campo in CAMPOS_RATING:
        ewma_manual[campo] = round(
            ALPHA_MEMORIA * club.history[2]["ratings"][campo] + (1 - ALPHA_MEMORIA) * ewma_manual[campo], 3
        )
    print(f"  memoria_ewma(nacional) = {memoria}")
    print(f"  esperado (EWMA manual) = {ewma_manual}")
    errores += _comparar("memoria_ewma", ewma_manual, memoria)

    # Con temporadas_consecutivas=2 (== N_TEMPORADAS_HANDICAP), el
    # handicap ya debería estar en factor 1.0 -- combinar_con_memoria
    # no debería comprimir nada extra, solo mezclar con la memoria.
    rating_actual = _rating(1.20, 0.80, 1.15, 0.90)
    obtenido = combinar_con_memoria(rating_actual, club, "nacional")
    esperado_sin_handicap = {
        campo: round(ALPHA_MEMORIA * rating_actual[campo] + (1 - ALPHA_MEMORIA) * memoria[campo], 3)
        for campo in CAMPOS_RATING
    }
    print(f"  combinar_con_memoria (sin handicap, temporadas={temporadas}) = {obtenido}")
    print(f"  esperado = {esperado_sin_handicap}")
    errores += _comparar("combinar_con_memoria sin handicap", esperado_sin_handicap, obtenido)

    # Ahora un club que ACABA de ascender la temporada pasada (1 sola
    # temporada en destino) -- combinar_con_memoria debe comprimir con
    # factor_handicap(1) = 2/3.
    club_nuevo = Club(id=2, name="Recién Ascendido", division="Primera Nacional")
    club_nuevo.history = [
        {"temporada": "2026", "division": "Primera Nacional", "ratings": _rating(0.75, 1.25, 0.80, 1.20)},
    ]
    temporadas_nuevo = temporadas_consecutivas_en_division(club_nuevo, "nacional")
    print(f"\n  Club recién ascendido: temporadas_consecutivas = {temporadas_nuevo} (esperado 1)")
    if temporadas_nuevo != 1:
        errores.append(f"[temporadas_consecutivas recién ascendido] esperado 1, dio {temporadas_nuevo}")

    rating_actual_2 = _rating(0.70, 1.30, 0.75, 1.25)
    memoria_2 = club_nuevo.history[0]["ratings"]
    base = {
        campo: round(ALPHA_MEMORIA * rating_actual_2[campo] + (1 - ALPHA_MEMORIA) * memoria_2[campo], 3)
        for campo in CAMPOS_RATING
    }
    factor_esperado = _factor_handicap(1)
    esperado_2 = {campo: round(1.0 + (base[campo] - 1.0) * factor_esperado, 3) for campo in CAMPOS_RATING}
    obtenido_2 = combinar_con_memoria(rating_actual_2, club_nuevo, "nacional")
    print(f"  combinar_con_memoria (con handicap 2/3) = {obtenido_2}")
    print(f"  esperado = {esperado_2}")
    errores += _comparar("combinar_con_memoria con handicap", esperado_2, obtenido_2)

    # Club sin ninguna entrada de historial en la división -> memoria
    # None, combinar_con_memoria debe devolver el rating_actual
    # comprimido por el handicap de temporada 1 (factor 1/3), ya que
    # temporadas_consecutivas_en_division da None en ese caso (BUG
    # CORREGIDO -- ver su docstring: antes daba 0, que combinar_con_memoria()
    # interpretaba como "recién llegado", aplastando el rating de
    # cualquier club sin historial persistido -- reportado por el
    # usuario como "River descendió a la cuarta ronda").
    club_sin_historial = Club(id=3, name="Sin Historial", division="Primera Nacional")
    memoria_vacia = memoria_ewma(club_sin_historial, "nacional")
    print(f"\n  Club sin historial: memoria_ewma = {memoria_vacia} (esperado None)")
    if memoria_vacia is not None:
        errores.append(f"[memoria_ewma sin historial] esperado None, dio {memoria_vacia}")

    temporadas_sin_historial = temporadas_consecutivas_en_division(club_sin_historial, "nacional")
    print(f"  Club sin historial: temporadas_consecutivas_en_division = {temporadas_sin_historial} (esperado None)")
    if temporadas_sin_historial is not None:
        errores.append(f"[temporadas_consecutivas sin historial] esperado None, dio {temporadas_sin_historial}")

    # Y lo más importante: combinar_con_memoria() NO debe aplastar el
    # rating de un club sin historial -- debe devolverlo tal cual (sin
    # handicap, ver bug arriba).
    rating_sin_tocar = _rating(1.30, 1.10, 0.80, 0.85)
    resultado_sin_historial = combinar_con_memoria(rating_sin_tocar, club_sin_historial, "nacional")
    print(f"  combinar_con_memoria SIN historial: {rating_sin_tocar} -> {resultado_sin_historial}")
    if resultado_sin_historial != rating_sin_tocar:
        errores.append(
            f"[BUG] un club sin Club.history NO debería sufrir ningún handicap -- "
            f"esperaba {rating_sin_tocar} sin cambios, dio {resultado_sin_historial}"
        )

    return errores


# ----------------------------------------------------------------
# Parte D: HistoryManager._actualizar_history() -- fix del bug de
# división + guardado de ratings, con FakeResultadoTorneo sintético
# (sin tocar Supabase/CSV).
# ----------------------------------------------------------------
@dataclass
class _FakeResultadoTorneo:
    ratings_finales: dict = field(default_factory=dict)


class _FakeClubRegistry:
    """Standin mínimo de ClubRegistry -- solo necesita all_clubs()
    para _actualizar_history()."""
    def __init__(self, clubes: list[Club]):
        self._clubes = clubes

    def all_clubs(self) -> list[Club]:
        return self._clubes


def validar_fix_actualizar_history() -> list:
    print("\n[Parte D] HistoryManager._actualizar_history() -- fix de división + ratings")
    errores = []

    from season.history_manager import HistoryManager

    # Escenario: "Club Chico" jugó Nacional esta temporada y SALIÓ
    # CAMPEÓN -> PromotionManager ya lo ascendió a LPF ANTES de esta
    # llamada (así es como llega club_registry a persist_season() en
    # la vida real -- ver docstring de la clase). Si el bug viejo
    # siguiera ahí, quedaría anotado como "Liga Profesional" para la
    # temporada 2026, cuando en realidad jugó Nacional.
    club = Club(id=1, name="Club Chico", division="Liga Profesional")  # YA promocionado
    registry = _FakeClubRegistry([club])

    resultados = {
        "nacional": _FakeResultadoTorneo(ratings_finales={
            "Club Chico": _rating(1.40, 1.10, 1.30, 1.05),
        }),
        "lpf": _FakeResultadoTorneo(ratings_finales={}),  # no jugó LPF todavía
        "federal_a": _FakeResultadoTorneo(ratings_finales={}),  # a propósito vacío
    }

    hm = HistoryManager(repo=object())  # no se usa _get_repo() acá
    hm._actualizar_history(registry, "2026", resultados)

    entrada = club.history[-1]
    print(f"  club.division (post-promoción, ANTES de la llamada) = 'Liga Profesional'")
    print(f"  entrada.history guardada = {entrada}")

    if entrada["division"] != "Primera Nacional":
        errores.append(
            f"[fix división] esperaba 'Primera Nacional' (la que jugó), "
            f"dio {entrada['division']!r} -- el bug de la división post-promoción no se corrigió"
        )
    if entrada.get("ratings") != resultados["nacional"].ratings_finales["Club Chico"]:
        errores.append(
            f"[ratings] esperaba {resultados['nacional'].ratings_finales['Club Chico']}, "
            f"dio {entrada.get('ratings')}"
        )

    # Caso Federal A: ratings_finales vacío a propósito -> debe
    # degradar con gracia (usa club.division actual, sin clave
    # "ratings"), sin romper.
    club_federal = Club(id=2, name="Club Federal", division="Federal A")
    registry_federal = _FakeClubRegistry([club_federal])
    hm._actualizar_history(registry_federal, "2026", resultados)
    entrada_federal = club_federal.history[-1]
    print(f"  entrada Federal A (sin ratings_finales) = {entrada_federal}")
    if "ratings" in entrada_federal:
        errores.append("[Federal A] no debería tener clave 'ratings' (ratings_finales vacío a propósito)")
    if entrada_federal["division"] != "Federal A":
        errores.append(
            f"[Federal A, fallback] esperaba 'Federal A' (fallback a club.division), "
            f"dio {entrada_federal['division']!r}"
        )

    # Caso resultados=None (llamada sin ese dato) -> mismo
    # comportamiento de siempre, sin romper.
    club_sin_resultados = Club(id=3, name="Club Sin Resultados", division="Primera C")
    registry_sin = _FakeClubRegistry([club_sin_resultados])
    hm._actualizar_history(registry_sin, "2026", None)
    entrada_sin = club_sin_resultados.history[-1]
    print(f"  entrada sin `resultados` = {entrada_sin}")
    if entrada_sin != {"temporada": "2026", "division": "Primera C"}:
        errores.append(f"[resultados=None] esperaba fallback simple, dio {entrada_sin}")

    return errores


def main():
    print("=" * 70)
    print("VALIDACIÓN FASE 0 -- memoria EWMA + handicap de adaptación")
    print("(HANDOFF_carryover_ratings.md)")
    print("=" * 70)
    print(f"\nConstantes: ALPHA_MEMORIA={ALPHA_MEMORIA}, N_TEMPORADAS_HANDICAP={N_TEMPORADAS_HANDICAP}")

    errores = []
    errores += validar_factor_handicap()
    errores += validar_recien_llegado_con_handicap()
    errores += validar_memoria_y_handicap_continuidad()
    errores += validar_fix_actualizar_history()

    print("\n" + "=" * 70)
    if errores:
        print(f"❌ {len(errores)} error(es):")
        for e in errores:
            print(f"  - {e}")
    else:
        print("✅ Todo OK -- Fase 0 validada.")
    print("=" * 70)


if __name__ == "__main__":
    main()
