# -*- coding: utf-8 -*-
"""manager_mode/ofertas.py

Pool de ofertas de club al finalizar cada temporada. Cuatro clubes le
ofrecen dirigir al DT, ponderados por su reputación: cuanto más alta,
más chance de que aparezcan ofertas de clubes exigentes (River, Boca) y
-- por encima de un umbral -- una chance de dirigir a la Selección
Argentina. Fase 2 del plan (docs/PLAN_MODO_DT.md).
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from manager_mode.dirigencia import (
    CATALOGO_PERFILES_CLUB,
    PerfilClub,
    generar_objetivos_temporada,
)
from manager_mode.domain import Entrenador, ObjetivoTemporada

# Reputación mínima para que la Selección Argentina pueda aparecer en
# el pool de ofertas. Por debajo de este umbral ni siquiera entra en
# la selección ponderada (no alcanza con tener suerte).
UMBRAL_REPUTACION_SELECCION = 85.0

# Aun habilitada por reputación, la Selección es una oferta rara: este
# factor multiplica su peso relativo frente a un club de exigencia
# equivalente, para que no aparezca en la mitad de los pooles apenas
# se cruza el umbral.
FACTOR_RAREZA_SELECCION = 0.3


@dataclass(frozen=True)
class OfertaClub:
    """Una oferta concreta de un club (o la Selección) al DT."""

    perfil: PerfilClub
    presupuesto: float
    sueldo: float
    duracion_temporadas: int
    objetivos: tuple[ObjetivoTemporada, ...]

    @property
    def nombre(self) -> str:
        return self.perfil.nombre

    @property
    def escudo(self) -> str | None:
        return self.perfil.escudo

    @property
    def presion(self) -> float:
        """Presión de la hinchada/prensa esperable en este proyecto,
        proporcional a la exigencia del club."""
        return self.perfil.exigencia


def _candidatos_disponibles(entrenador: Entrenador) -> list[PerfilClub]:
    candidatos = [perfil for perfil in CATALOGO_PERFILES_CLUB.values() if not perfil.es_seleccion]
    if entrenador.reputacion >= UMBRAL_REPUTACION_SELECCION:
        candidatos.append(CATALOGO_PERFILES_CLUB["Selección Argentina"])
    return candidatos


def _peso_oferta(perfil: PerfilClub, entrenador: Entrenador) -> float:
    """Pondera por cercanía entre la reputación del DT (0-100) y la
    exigencia del club (0.0-1.0, escalada a 0-100): un DT de baja
    reputación rara vez recibe una oferta de River, y viceversa."""
    cercania = 1.0 - abs(entrenador.reputacion - perfil.exigencia * 100.0) / 100.0
    peso = max(0.05, cercania)
    if perfil.es_seleccion:
        peso *= FACTOR_RAREZA_SELECCION
    return peso


def _sample_ponderado_sin_reemplazo(
    items: list[PerfilClub], pesos: list[float], k: int, rng: random.Random,
) -> list[PerfilClub]:
    """Elige `k` elementos de `items` sin repetir, respetando los pesos
    relativos (random.choices no evita repetidos, así que se remueve
    el elegido y se repite)."""
    items = list(items)
    pesos = list(pesos)
    elegidos: list[PerfilClub] = []
    for _ in range(k):
        if not items:
            break
        idx = rng.choices(range(len(items)), weights=pesos, k=1)[0]
        elegidos.append(items.pop(idx))
        pesos.pop(idx)
    return elegidos


def _presupuesto_base(perfil: PerfilClub) -> float:
    return 500.0 + perfil.exigencia * 4500.0


def _sueldo_base(perfil: PerfilClub) -> float:
    return 100.0 + perfil.exigencia * 900.0


def generar_pool_ofertas(
    entrenador: Entrenador,
    rng: random.Random,
    cantidad: int = 4,
) -> list[OfertaClub]:
    """Genera el pool de ofertas de fin de temporada para `entrenador`.

    Args:
      entrenador: DT libre (o próximo a quedar libre) que recibe las
        ofertas. Su reputación pondera qué clubes aparecen.
      rng: generador de números aleatorios (para tests determinísticos).
      cantidad: cantidad de ofertas a generar (por defecto 4, como en
        el brief). Si hay menos clubes candidatos que `cantidad`,
        devuelve todos los disponibles.
    """
    candidatos = _candidatos_disponibles(entrenador)
    cantidad = min(cantidad, len(candidatos))
    pesos = [_peso_oferta(perfil, entrenador) for perfil in candidatos]
    elegidos = _sample_ponderado_sin_reemplazo(candidatos, pesos, cantidad, rng)

    ofertas = []
    for perfil in elegidos:
        objetivos = generar_objetivos_temporada(perfil, rng, cantidad=2)
        duracion = 2 if perfil.es_seleccion else rng.randint(1, 3)
        ofertas.append(OfertaClub(
            perfil=perfil,
            presupuesto=_presupuesto_base(perfil),
            sueldo=_sueldo_base(perfil),
            duracion_temporadas=duracion,
            objetivos=tuple(objetivos),
        ))
    return ofertas
