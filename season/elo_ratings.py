# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

CAMPOS_RATING = (
    "ataque_local",
    "ataque_visitante",
    "defensa_local",
    "defensa_visitante",
)

RATING_DEFAULT = {
    "ataque_local": 1.0,
    "ataque_visitante": 1.0,
    "defensa_local": 1.0,
    "defensa_visitante": 1.0,
    "partidos_computados": 0,
}

# Learning rate inicial. Se aplica sobre ratings relativos a promedio de liga,
# por eso un K bajo mueve gradual incluso ante resultados extremos.
K_ELO = 0.035

# Evita que una racha corta vuelva a un club invencible o inviable.
RATING_MIN = 0.45
RATING_MAX = 1.90

# A partir de este volumen de partidos el K efectivo baja lentamente.
PARTIDOS_ESTABILIZACION = 40

PROMEDIOS_COMPETITION = {
    "nacional": (1.35, 1.05),
    "lpf": (1.35, 1.05),
    "bmetro": (1.06, 0.94),
    "federal_a": (1.35, 1.05),
    "primerac": (1.35, 1.05),
}


@dataclass(frozen=True)
class RatingUpdate:
    local_pre: dict
    visitante_pre: dict
    local_post: dict
    visitante_post: dict
    expected_local: float
    expected_visitante: float


def rating_default() -> dict:
    return dict(RATING_DEFAULT)


def _clamp(valor: float) -> float:
    return round(max(RATING_MIN, min(RATING_MAX, valor)), 3)


def _k_efectivo(partidos_computados: int, k: float = K_ELO) -> float:
    return k / sqrt(1 + max(0, partidos_computados) / PARTIDOS_ESTABILIZACION)


def goles_esperados(
    rating_local: dict,
    rating_visitante: dict,
    promedio_local: float,
    promedio_visitante: float,
) -> tuple[float, float]:
    expected_local = (
        rating_local["ataque_local"]
        * rating_visitante["defensa_visitante"]
        * promedio_local
    )
    expected_visitante = (
        rating_visitante["ataque_visitante"]
        * rating_local["defensa_local"]
        * promedio_visitante
    )
    return expected_local, expected_visitante


def actualizar_por_partido(
    rating_local: dict,
    rating_visitante: dict,
    goles_local: int,
    goles_visitante: int,
    promedio_local: float,
    promedio_visitante: float,
    k: float = K_ELO,
) -> RatingUpdate:
    """Actualiza 4 componentes de rating con error de goles esperado.

    Defensa sigue la convención del motor actual: mayor valor significa que
    concede más goles, por lo tanto un rival que convierte por encima de lo
    esperado sube la defensa propia (peor defensa).
    """
    local_pre = {campo: float(rating_local.get(campo, 1.0)) for campo in CAMPOS_RATING}
    visitante_pre = {campo: float(rating_visitante.get(campo, 1.0)) for campo in CAMPOS_RATING}
    local_pre["partidos_computados"] = int(rating_local.get("partidos_computados", 0))
    visitante_pre["partidos_computados"] = int(rating_visitante.get("partidos_computados", 0))

    expected_local, expected_visitante = goles_esperados(
        local_pre, visitante_pre, promedio_local, promedio_visitante
    )

    k_local = _k_efectivo(local_pre["partidos_computados"], k)
    k_visitante = _k_efectivo(visitante_pre["partidos_computados"], k)

    error_local = (int(goles_local) - expected_local) / max(0.1, promedio_local)
    error_visitante = (int(goles_visitante) - expected_visitante) / max(0.1, promedio_visitante)

    local_post = {
        "ataque_local": _clamp(local_pre["ataque_local"] + k_local * error_local),
        "ataque_visitante": local_pre["ataque_visitante"],
        "defensa_local": _clamp(local_pre["defensa_local"] + k_local * error_visitante),
        "defensa_visitante": local_pre["defensa_visitante"],
        "partidos_computados": local_pre["partidos_computados"] + 1,
    }
    visitante_post = {
        "ataque_local": visitante_pre["ataque_local"],
        "ataque_visitante": _clamp(visitante_pre["ataque_visitante"] + k_visitante * error_visitante),
        "defensa_local": visitante_pre["defensa_local"],
        "defensa_visitante": _clamp(visitante_pre["defensa_visitante"] + k_visitante * error_local),
        "partidos_computados": visitante_pre["partidos_computados"] + 1,
    }

    return RatingUpdate(
        local_pre=local_pre,
        visitante_pre=visitante_pre,
        local_post=local_post,
        visitante_post=visitante_post,
        expected_local=round(expected_local, 4),
        expected_visitante=round(expected_visitante, 4),
    )
