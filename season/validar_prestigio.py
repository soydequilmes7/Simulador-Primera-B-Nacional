# -*- coding: utf-8 -*-
"""
season/validar_prestigio.py

Validación del piso de prestigio histórico (season/prestigio.py) y su
integración en season/rating_carryover.py (combinar_con_memoria() /
RatingCarryoverPolicy.rating_para_recien_llegado()).

Correrlo desde la raíz del proyecto:

    python -m season.validar_prestigio
"""
from __future__ import annotations

from modelos.club import Club
from season.prestigio import (
    TITULOS_HISTORICOS,
    RESISTENCIA_MAXIMA,
    factor_resistencia,
    aplicar_piso_prestigio,
)
from season.rating_carryover import RatingCarryoverPolicy, combinar_con_memoria, CAMPOS_RATING


def _rating(a_l, a_v, d_l, d_v) -> dict:
    return {"ataque_local": a_l, "ataque_visitante": a_v, "defensa_local": d_l, "defensa_visitante": d_v}


def validar_factor_resistencia() -> list:
    print("\n[Parte A] factor_resistencia() -- escala logarítmica, tope RESISTENCIA_MAXIMA")
    errores = []

    boca = factor_resistencia("Boca Jrs.")
    print(f"  Boca Jrs. ({TITULOS_HISTORICOS['Boca Jrs.']} títulos): {boca}")
    if boca != RESISTENCIA_MAXIMA:
        errores.append(f"Boca Jrs. (máximo histórico) debería dar exactamente RESISTENCIA_MAXIMA={RESISTENCIA_MAXIMA}, dio {boca}")

    sin_titulos = factor_resistencia("Club Cualquiera Sin Historial")
    print(f"  club sin títulos: {sin_titulos}")
    if sin_titulos != 0.0:
        errores.append(f"club sin títulos debería dar 0.0, dio {sin_titulos}")

    # Monotonía: más títulos -> más resistencia (no estrictamente
    # proporcional, es logarítmico, pero sí monótono).
    river = factor_resistencia("River")
    racing = factor_resistencia("Racing")
    belgrano = factor_resistencia("Belgrano")  # 1 título
    print(f"  River ({TITULOS_HISTORICOS['River']}): {river} | Racing ({TITULOS_HISTORICOS['Racing']}): {racing} "
          f"| Belgrano ({TITULOS_HISTORICOS['Belgrano']}): {belgrano}")
    if not (boca >= river > racing > belgrano > sin_titulos):
        errores.append(f"esperaba orden monótono boca>=river>racing>belgrano>0, dio {boca},{river},{racing},{belgrano},{sin_titulos}")

    # No lineal: la razón títulos Boca/Belgrano es 74x, la razón de
    # resistencia tiene que ser MUCHO menor que 74x (ver docstring).
    razon_titulos = TITULOS_HISTORICOS["Boca Jrs."] / TITULOS_HISTORICOS["Belgrano"]
    razon_resistencia = boca / belgrano
    print(f"  razón de títulos Boca/Belgrano: {razon_titulos}x | razón de resistencia: {round(razon_resistencia, 2)}x")
    if not (razon_resistencia < razon_titulos / 5):
        errores.append(f"esperaba que la razón de resistencia sea MUCHO menor que la de títulos (no lineal), dio {razon_resistencia}x vs {razon_titulos}x")

    # Confirmar que las entradas ambiguas documentadas NO están en la tabla.
    ambiguas = ["Defensa y Justicia", "Sportivo Barracas", "Barracas",
                "Estudiantes de Buenos Aires", "Estudiantes RC", "Atlético Tucumán"]
    for nombre in ambiguas:
        if nombre in TITULOS_HISTORICOS:
            errores.append(f"'{nombre}' está en TITULOS_HISTORICOS pero debería estar excluida por ambigüedad (ver docstring)")
    print(f"  confirmado: {len(ambiguas)} entradas ambiguas NO están en la tabla (Defensa, Barracas, etc.)")

    return errores


def validar_aplicar_piso_no_toca_lado_bueno() -> list:
    print("\n[Parte B] aplicar_piso_prestigio() -- NO empuja hacia arriba, solo amortigua el lado malo")
    errores = []

    # Boca RINDIENDO BIEN (ataque > 1.0, defensa < 1.0) -> sin cambios.
    rating_bueno = _rating(1.30, 1.20, 0.75, 0.80)
    resultado = aplicar_piso_prestigio(rating_bueno, "Boca Jrs.")
    print(f"  Boca rindiendo BIEN: {rating_bueno} -> {resultado}")
    if resultado != rating_bueno:
        errores.append(f"un club rindiendo bien no debería cambiar NADA, dio {resultado} (original {rating_bueno})")

    # Boca RINDIENDO MAL (ataque < 1.0, defensa > 1.0) -> amortiguado
    # hacia 1.0, pero sin llegar a 1.0 (RESISTENCIA_MAXIMA=0.5 -> mitad
    # de camino, no el 100%).
    rating_malo = _rating(0.60, 0.70, 1.40, 1.30)
    resultado_malo = aplicar_piso_prestigio(rating_malo, "Boca Jrs.")
    print(f"  Boca rindiendo MAL: {rating_malo} -> {resultado_malo}")
    factor = factor_resistencia("Boca Jrs.")
    esperado = {
        "ataque_local": round(0.60 + factor * (1.0 - 0.60), 4),
        "ataque_visitante": round(0.70 + factor * (1.0 - 0.70), 4),
        "defensa_local": round(1.40 + factor * (1.0 - 1.40), 4),
        "defensa_visitante": round(1.30 + factor * (1.0 - 1.30), 4),
    }
    if resultado_malo != esperado:
        errores.append(f"esperaba {esperado}, dio {resultado_malo}")
    for campo in CAMPOS_RATING:
        if not (min(rating_malo[campo], 1.0) <= resultado_malo[campo] <= max(rating_malo[campo], 1.0)):
            errores.append(f"[{campo}] el amortiguado debería quedar ENTRE el valor original y 1.0, dio {resultado_malo[campo]}")

    # Un club SIN historial, rindiendo igual de mal -> sin ningún cambio.
    resultado_sin_historial = aplicar_piso_prestigio(rating_malo, "Club Chico Sin Historial")
    print(f"  Club chico rindiendo MAL (mismo rating): {rating_malo} -> {resultado_sin_historial}")
    if resultado_sin_historial != rating_malo:
        errores.append(f"un club sin historial no debería amortiguarse nada, dio {resultado_sin_historial}")

    return errores


def validar_integracion_combinar_con_memoria() -> list:
    print("\n[Parte C] Integración con combinar_con_memoria() -- club real con historial de rating")
    errores = []

    # Boca con una temporada mala en LPF -- la memoria EWMA + handicap
    # ya lo empujarían un poco hacia 1.0, y el piso de prestigio debería
    # empujarlo un poco más (en la misma dirección, no al revés).
    boca = Club(id=1, name="Boca Jrs.", division="Liga Profesional")
    boca.history = [
        {"temporada": "2025", "division": "Liga Profesional", "ratings": _rating(1.35, 1.20, 0.70, 0.75)},
        {"temporada": "2026", "division": "Liga Profesional", "ratings": _rating(1.30, 1.15, 0.75, 0.80)},
    ]
    rating_actual_malo = _rating(0.65, 0.75, 1.35, 1.25)  # temporada mala de verdad

    resultado_boca = combinar_con_memoria(rating_actual_malo, boca, "lpf")
    print(f"  Boca (temporada mala + buen historial reciente): {resultado_boca}")

    # Mismo escenario pero con un club sin prestigio -- para comparar.
    club_generico = Club(id=2, name="Club Sin Historial De Titulos", division="Liga Profesional")
    club_generico.history = list(boca.history)  # mismo historial de PERFORMANCE reciente
    resultado_generico = combinar_con_memoria(rating_actual_malo, club_generico, "lpf")
    print(f"  Club sin prestigio (mismo historial reciente): {resultado_generico}")

    # Con la misma memoria/handicap, Boca tiene que quedar MÁS cerca de
    # 1.0 que el club genérico en TODOS los componentes (por el piso).
    for campo in CAMPOS_RATING:
        dist_boca = abs(resultado_boca[campo] - 1.0)
        dist_generico = abs(resultado_generico[campo] - 1.0)
        if not (dist_boca <= dist_generico):
            errores.append(
                f"[{campo}] Boca debería quedar MÁS cerca de 1.0 que el club sin prestigio "
                f"(Boca: {resultado_boca[campo]}, genérico: {resultado_generico[campo]})"
            )

    return errores


def validar_integracion_recien_llegado() -> list:
    print("\n[Parte D] Integración con rating_para_recien_llegado() -- club prestigioso que desciende")
    errores = []

    politica = RatingCarryoverPolicy()
    ratings_origen_malos = _rating(0.65, 0.70, 1.35, 1.30)  # LPF, temporada de descenso

    con_prestigio = politica.rating_para_recien_llegado(
        ratings_origen_malos, "lpf", "nacional", club_nombre="Racing",
    )
    sin_club_nombre = politica.rating_para_recien_llegado(
        ratings_origen_malos, "lpf", "nacional",  # sin club_nombre -- default None, comportamiento viejo
    )
    print(f"  Racing (sin club_nombre, comportamiento viejo): {sin_club_nombre}")
    print(f"  Racing (con club_nombre, con piso de prestigio): {con_prestigio}")

    for campo in CAMPOS_RATING:
        dist_con = abs(con_prestigio[campo] - 1.0)
        dist_sin = abs(sin_club_nombre[campo] - 1.0)
        if not (dist_con <= dist_sin):
            errores.append(
                f"[{campo}] con club_nombre='Racing' debería quedar más cerca de 1.0 (o igual) que sin él, "
                f"dio con={con_prestigio[campo]} vs sin={sin_club_nombre[campo]}"
            )

    # club_nombre=None (default) tiene que dar EXACTAMENTE lo mismo que
    # antes de agregar este parámetro -- no rompe ninguna llamada vieja.
    otra_vez_sin = politica.rating_para_recien_llegado(ratings_origen_malos, "lpf", "nacional")
    if otra_vez_sin != sin_club_nombre:
        errores.append("llamar dos veces sin club_nombre debería dar resultados idénticos (determinismo)")

    return errores


def main():
    print("=" * 70)
    print("VALIDACIÓN -- Piso de prestigio histórico (season/prestigio.py)")
    print("=" * 70)

    errores = []
    errores += validar_factor_resistencia()
    errores += validar_aplicar_piso_no_toca_lado_bueno()
    errores += validar_integracion_combinar_con_memoria()
    errores += validar_integracion_recien_llegado()

    print("\n" + "=" * 70)
    if errores:
        print(f"❌ {len(errores)} error(es):")
        for e in errores:
            print(f"  - {e}")
    else:
        print("✅ Todo OK -- piso de prestigio validado.")
    print("=" * 70)


if __name__ == "__main__":
    main()
