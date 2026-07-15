# -*- coding: utf-8 -*-
"""
buildPromotionRequirements (versión Python): construir_requisitos_ascenso()

Módulo NUEVO e independiente del motor de simulación. No corre Monte Carlo,
no toca Estadisticas ni ningún archivo del simulador principal: solo recibe
los arrays por-simulación que Monte Carlo YA calculó (puntos finales,
victorias/empates/derrotas en los partidos pendientes, y si esa simulación
terminó en ascenso o no) y arma la respuesta a "¿Qué necesita [Equipo] para
ascender?" a partir de las simulaciones EXITOSAS (las que terminan en
ascenso, directo o por Reducido).

No inventa números: todo sale de promedios/modas/proporciones calculadas
sobre los arrays recibidos. No usa IA para el resumen: es un template con
los datos ya calculados.
"""

from collections import Counter


def _redondear_manteniendo_total(valores, total_esperado):
    """Redondea una lista de floats a enteros que sumen EXACTO
    total_esperado, usando el método del resto mayor (Hamilton/Hare).

    Se usa para victorias/empates/derrotas promedio: por construcción,
    v + e + d == partidos_restantes en CADA simulación individual, así que
    el promedio de v, e, d entre simulaciones exitosas también suma
    exactamente partidos_restantes -- lo único que puede romper esa suma
    es redondear cada promedio por separado. Este método no inventa
    ningún dato nuevo, solo elige cómo repartir el redondeo para no perder
    esa consistencia."""
    pisos = [int(v) for v in valores]
    restantes = total_esperado - sum(pisos)
    # Reparte las unidades que faltan a quienes tienen mayor parte
    # fraccionaria descartada (los "más cerca de redondear para arriba").
    fracciones = sorted(
        range(len(valores)), key=lambda i: (valores[i] - pisos[i]), reverse=True
    )
    resultado = pisos[:]
    for i in fracciones[:max(0, restantes)]:
        resultado[i] += 1
    return resultado


def construir_requisitos_ascenso(
    equipo,
    puntos_actuales,
    partidos_restantes,
    puntos_final_sims,
    victorias_restantes_sims,
    empates_restantes_sims,
    derrotas_restantes_sims,
    asciende_sims,
):
    """Arma el objeto que consume la tarjeta "¿Qué necesita [Equipo]?".

    Parámetros (todos arrays de NumPy de la MISMA longitud N =
    n_simulaciones de Monte Carlo, uno por simulación, ya calculados por
    Estadisticas.monte_carlo() -- acá no se recalcula nada):
    - equipo: nombre del equipo (str)
    - puntos_actuales: puntos reales de HOY (int, no depende de la simulación)
    - partidos_restantes: cantidad de partidos que le quedan (int)
    - puntos_final_sims: puntos finales de temporada en cada simulación
    - victorias_restantes_sims / empates_restantes_sims / derrotas_restantes_sims:
      resultado del equipo en los partidos PENDIENTES de cada simulación
      (no cuenta lo ya jugado)
    - asciende_sims: bool por simulación -- True si en esa simulación el
      equipo terminó ascendiendo (directo o por Reducido)

    Devuelve un dict con exactamente estas claves:
    targetPoints, currentPoints, remainingPoints, matchesRemaining,
    requiredPPG, averageWins, averageDraws, averageLosses,
    promotionProbabilityAtTarget, summary
    """

    n_sims = len(puntos_final_sims)
    n_exitosas = int(asciende_sims.sum()) if n_sims else 0

    if n_sims == 0 or n_exitosas == 0:
        # No hay ninguna simulación exitosa de la que sacar un objetivo
        # realista -- no inventamos un número, avisamos que no hay datos.
        return {
            "targetPoints": None,
            "currentPoints": int(puntos_actuales),
            "remainingPoints": None,
            "matchesRemaining": int(partidos_restantes),
            "requiredPPG": None,
            "averageWins": None,
            "averageDraws": None,
            "averageLosses": None,
            "promotionProbabilityAtTarget": 0.0,
            "summary": (
                f"Según las simulaciones, {equipo} no logra el ascenso en "
                f"ninguno de los escenarios simulados esta temporada."
            ),
        }

    puntos_exitosos = puntos_final_sims[asciende_sims]

    # "Puntos finales más habituales" entre las simulaciones exitosas: la
    # moda de esa distribución. Ante un empate de frecuencia, Counter
    # devuelve el primer valor más frecuente que encontró recorriendo la
    # lista ordenada de menor a mayor, así que preferimos el más bajo (el
    # objetivo más alcanzable, no el más exigente).
    conteo_puntos = Counter(int(p) for p in sorted(puntos_exitosos))
    target_points = conteo_puntos.most_common(1)[0][0]

    current_points = int(puntos_actuales)
    remaining_points = max(target_points - current_points, 0)
    matches_remaining = int(partidos_restantes)
    required_ppg = round(remaining_points / matches_remaining, 2) if matches_remaining > 0 else 0.0

    media_victorias = float(victorias_restantes_sims[asciende_sims].mean())
    media_empates = float(empates_restantes_sims[asciende_sims].mean())
    media_derrotas = float(derrotas_restantes_sims[asciende_sims].mean())

    average_wins, average_draws, average_losses = _redondear_manteniendo_total(
        [media_victorias, media_empates, media_derrotas], matches_remaining
    )

    # Probabilidad de ascenso CUANDO se llega (o se supera) el objetivo:
    # de TODAS las simulaciones (no solo las exitosas) nos quedamos con las
    # que alcanzaron ese punto de llegada, y vemos qué fracción de esas
    # efectivamente ascendió.
    llega_al_objetivo = puntos_final_sims >= target_points
    n_llega = int(llega_al_objetivo.sum())
    if n_llega > 0:
        prob_en_objetivo = round(100 * float(asciende_sims[llega_al_objetivo].mean()), 1)
    else:
        prob_en_objetivo = 0.0

    prob_texto = int(round(prob_en_objetivo))
    summary = (
        f"Según las simulaciones, {equipo} normalmente necesita llegar a los "
        f"{target_points} puntos para convertirse en un claro candidato al "
        f"ascenso. Con ese rendimiento asciende en alrededor del {prob_texto}% "
        f"de las simulaciones."
    )

    return {
        "targetPoints": target_points,
        "currentPoints": current_points,
        "remainingPoints": remaining_points,
        "matchesRemaining": matches_remaining,
        "requiredPPG": required_ppg,
        "averageWins": average_wins,
        "averageDraws": average_draws,
        "averageLosses": average_losses,
        "promotionProbabilityAtTarget": prob_en_objetivo,
        "summary": summary,
    }
