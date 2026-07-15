# -*- coding: utf-8 -*-
"""
observatorio_ascenso.py

Módulo puro (sin efectos secundarios, sin IA, sin acceso a disco/red) que
compara dos "fotos" del estado de Primera Nacional -- una de ANTES y otra
de DESPUÉS de una actualización -- y arma el contenido de la sección
"Observatorio del Ascenso" que se muestra en el frontend.

Cada "foto" (anteriores / nuevas) es un dict con esta forma, que es
exactamente el subconjunto de datos.json que ya persiste el resto del
sistema (ver actualizar_resultados.py):

    {
        "monte_carlo": {
            "A": [{"equipo": str, "ascenso_total": float, ...}, ...],
            "B": [{"equipo": str, "ascenso_total": float, ...}, ...],
        },
        "tabla_actual": {
            "A": [{"equipo": str, "posicion": int, "zona": "A", ...}, ...],
            "B": [{"equipo": str, "posicion": int, "zona": "B", ...}, ...],
        },
    }

La función principal, calcular_observatorio_ascenso(anteriores, nuevas),
devuelve un dict con el shape que consume el frontend:

    {
        "biggestRise":     {"equipo": str, "zona": str, "delta": float} | None,
        "biggestFall":     {"equipo": str, "zona": str, "delta": float} | None,
        "newFavorite":     {"equipo": str, "zona": str, "probabilidad": float} | None,
        "enteredPlayoffs": [str, ...],
        "leftPlayoffs":    [str, ...],
        "topChanges":      [{"equipo": str, "zona": str, "delta": float}, ...],  # hasta 5
        "summary":         str,
    }

o None si "anteriores" no tiene datos con los que comparar (por ejemplo,
la primera vez que se corre "Actualizar resultados" en un deploy nuevo).

No hardcodea nombres de equipos ni textos fijos por equipo: todo sale de
comparar los números entre los dos estados.
"""

# Posiciones 2 a 8 de cada zona juegan el Reducido (ver
# modelos/estadisticas.py -> jugar_reducido). La posición 1 asciende
# directo a la Final del Ascenso y no forma parte del Reducido.
POSICION_REDUCIDO_DESDE = 2
POSICION_REDUCIDO_HASTA = 8

TOP_CHANGES_N = 5


def _flatten_monte_carlo(monte_carlo):
    """
    {"A": [...], "B": [...]} -> {equipo: {"zona": "A", "ascenso_total": float}}
    """
    planilla = {}
    if not monte_carlo:
        return planilla
    for zona, equipos in monte_carlo.items():
        for fila in equipos or []:
            nombre = fila.get("equipo")
            if not nombre:
                continue
            try:
                ascenso_total = float(fila.get("ascenso_total", 0) or 0)
            except (TypeError, ValueError):
                ascenso_total = 0.0
            planilla[nombre] = {"zona": zona, "ascenso_total": ascenso_total}
    return planilla


def _equipos_en_reducido(tabla_actual):
    """
    {"A": [...], "B": [...]} -> set de equipos en posiciones 2-8 de
    cualquiera de las dos zonas, según tabla_actual (posiciones reales,
    no probabilísticas).
    """
    equipos = set()
    if not tabla_actual:
        return equipos
    for _zona, filas in tabla_actual.items():
        for fila in filas or []:
            posicion = fila.get("posicion")
            nombre = fila.get("equipo")
            if not nombre or posicion is None:
                continue
            if POSICION_REDUCIDO_DESDE <= posicion <= POSICION_REDUCIDO_HASTA:
                equipos.add(nombre)
    return equipos


def _favorito(planilla):
    """Equipo con mayor ascenso_total en una planilla ya aplanada, o None."""
    if not planilla:
        return None
    nombre, datos = max(planilla.items(), key=lambda item: item[1]["ascenso_total"])
    return {"equipo": nombre, "zona": datos["zona"], "probabilidad": round(datos["ascenso_total"], 1)}


def _armar_resumen(biggest_rise, biggest_fall, new_favorite, entered, left):
    """
    Arma el texto automático a partir de los datos ya calculados. Sin IA:
    es un template que solo rellena con los números/nombres calculados.
    """
    frases = []

    if biggest_rise:
        frases.append(
            f"La suba de {biggest_rise['equipo']} fue la más marcada de la fecha "
            f"({biggest_rise['delta']:+.1f}%)"
        )
    if biggest_fall:
        conector = ", mientras que" if frases else "La caída de"
        if frases:
            frases[-1] += (
                f"{conector} {biggest_fall['equipo']} sufrió la mayor caída "
                f"({biggest_fall['delta']:+.1f}%)."
            )
        else:
            frases.append(
                f"La caída de {biggest_fall['equipo']} fue la más marcada de la fecha "
                f"({biggest_fall['delta']:+.1f}%)."
            )
    elif frases:
        frases[-1] += "."

    if new_favorite:
        frases.append(
            f"{new_favorite['equipo']} pasó a ser el nuevo principal candidato al ascenso "
            f"({new_favorite['probabilidad']:.1f}%)."
        )

    if entered:
        if len(entered) == 1:
            frases.append(f"{entered[0]} ingresó a la zona de Reducido.")
        else:
            frases.append(f"{', '.join(entered)} ingresaron a la zona de Reducido.")

    if left:
        if len(left) == 1:
            frases.append(f"{left[0]} salió de la zona de Reducido.")
        else:
            frases.append(f"{', '.join(left)} salieron de la zona de Reducido.")

    if not frases:
        return "No hubo cambios significativos en las probabilidades desde la última actualización."

    return " ".join(frases)


def calcular_observatorio_ascenso(anteriores, nuevas):
    """
    Compara el estado anterior con el nuevo y devuelve el objeto del
    Observatorio del Ascenso, o None si no hay estado anterior válido
    para comparar (primera actualización).

    anteriores / nuevas: dicts con las claves "monte_carlo" y
    "tabla_actual" (ver docstring del módulo). Se aceptan None/{} para
    "anteriores" (en ese caso se devuelve None).
    """
    if not anteriores or not anteriores.get("monte_carlo"):
        return None
    if not nuevas or not nuevas.get("monte_carlo"):
        return None

    mc_antes = _flatten_monte_carlo(anteriores.get("monte_carlo"))
    mc_ahora = _flatten_monte_carlo(nuevas.get("monte_carlo"))

    # Solo comparamos equipos presentes en ambas fotos (evita falsos
    # "cambios" si un equipo recién aparece, p.ej. por corrección de
    # nombre en el mapeo).
    deltas = []
    for nombre, datos_ahora in mc_ahora.items():
        datos_antes = mc_antes.get(nombre)
        if datos_antes is None:
            continue
        delta = round(datos_ahora["ascenso_total"] - datos_antes["ascenso_total"], 1)
        if delta == 0:
            continue
        deltas.append({"equipo": nombre, "zona": datos_ahora["zona"], "delta": delta})

    biggest_rise = None
    biggest_fall = None
    if deltas:
        subidas = [d for d in deltas if d["delta"] > 0]
        caidas = [d for d in deltas if d["delta"] < 0]
        if subidas:
            biggest_rise = max(subidas, key=lambda d: d["delta"])
        if caidas:
            biggest_fall = min(caidas, key=lambda d: d["delta"])

    favorito_antes = _favorito(mc_antes)
    favorito_ahora = _favorito(mc_ahora)
    new_favorite = None
    if (
        favorito_ahora
        and (not favorito_antes or favorito_antes["equipo"] != favorito_ahora["equipo"])
    ):
        new_favorite = favorito_ahora

    reducido_antes = _equipos_en_reducido(anteriores.get("tabla_actual"))
    reducido_ahora = _equipos_en_reducido(nuevas.get("tabla_actual"))
    entered_playoffs = sorted(reducido_ahora - reducido_antes)
    left_playoffs = sorted(reducido_antes - reducido_ahora)

    top_changes = sorted(deltas, key=lambda d: abs(d["delta"]), reverse=True)[:TOP_CHANGES_N]

    summary = _armar_resumen(biggest_rise, biggest_fall, new_favorite, entered_playoffs, left_playoffs)

    return {
        "biggestRise": biggest_rise,
        "biggestFall": biggest_fall,
        "newFavorite": new_favorite,
        "enteredPlayoffs": entered_playoffs,
        "leftPlayoffs": left_playoffs,
        "topChanges": top_changes,
        "summary": summary,
    }
