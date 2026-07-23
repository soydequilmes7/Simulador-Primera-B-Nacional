# -*- coding: utf-8 -*-
"""manager_mode/copas_continentales.py

Simulación simplificada de Copa Libertadores y Copa Sudamericana para
el Modo DT. A DIFERENCIA de Modo Temporada, esto NO se conecta con los
motores reales (season/libertadores_manager.py,
season/libertadores_grupos.py, season/sudamericana_temporada.py, sorteo
CONMEBOL) -- es una tirada de fases simplificada, propia y aislada del
Modo DT, pensada para darle al usuario la CHANCE de ganar la copa sin
simular el certamen completo. Solo aplica a clubes con
`PerfilClub.clasifica_copas_internacionales=True` (los grandes de
Primera). Fase 2.5 del plan (docs/PLAN_MODO_DT.md).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum

from manager_mode.dirigencia import PerfilClub
from manager_mode.domain import Entrenador

# Fases del cuadro, en orden. "campeon" es la última: llegar hasta ahí
# significa ganar el torneo.
FASES: tuple[str, ...] = ("grupos", "octavos", "cuartos", "semifinal", "final", "campeon")


class CopaContinental(str, Enum):
    LIBERTADORES = "libertadores"
    SUDAMERICANA = "sudamericana"


NOMBRE_COPA: dict[CopaContinental, str] = {
    CopaContinental.LIBERTADORES: "Copa Libertadores",
    CopaContinental.SUDAMERICANA: "Copa Sudamericana",
}


@dataclass(frozen=True)
class ResultadoCopaContinental:
    """Resultado de la campaña continental de una temporada."""

    copa: CopaContinental
    fase_alcanzada: str
    campeon: bool


def simular_copa_continental(
    entrenador: Entrenador,
    perfil: PerfilClub,
    copa: CopaContinental,
    rng: random.Random,
) -> ResultadoCopaContinental:
    """Simula, fase por fase, cuánto avanza el club en la copa.

    En cada una de las 5 transiciones del cuadro (grupos→octavos→
    cuartos→semifinal→final→campeón) se tira una probabilidad de
    avanzar; se corta en la primera que no supera. La probabilidad
    combina la reputación del DT y la exigencia del club (perfiles más
    grandes rinden mejor en promedio, pero nunca es un resultado
    garantizado).

    Lanza ValueError si `perfil` no clasifica a la copa pedida -- la
    Libertadores y la Sudamericana tienen elegibilidad independiente
    (`PerfilClub.clasifica_libertadores` / `clasifica_sudamericana`);
    un club puede jugar una sin jugar la otra.
    """
    clasifica = (
        perfil.clasifica_libertadores if copa == CopaContinental.LIBERTADORES
        else perfil.clasifica_sudamericana
    )
    if not clasifica:
        raise ValueError(
            f"{perfil.nombre} no clasifica a la {NOMBRE_COPA[copa]} en este catálogo"
        )

    prob_avance = 0.30 + (entrenador.reputacion / 100.0) * 0.25 + perfil.exigencia * 0.15
    prob_avance = min(prob_avance, 0.85)

    fase_idx = 0
    for _ in range(len(FASES) - 1):
        if rng.random() < prob_avance:
            fase_idx += 1
        else:
            break

    fase_alcanzada = FASES[fase_idx]
    return ResultadoCopaContinental(
        copa=copa,
        fase_alcanzada=fase_alcanzada,
        campeon=(fase_alcanzada == "campeon"),
    )


def aplicar_resultado_copa(entrenador: Entrenador, resultado: ResultadoCopaContinental) -> None:
    """Aplica los efectos del resultado sobre el Entrenador: si salió
    campeón, suma título + desbloquea el logro "campeon_continental" y
    da un buen envión de reputación; llegar a semifinal o final sin
    ganar también suma reputación, en menor medida."""
    if resultado.campeon:
        entrenador.sumar_titulo(f"Campeón {NOMBRE_COPA[resultado.copa]}", bonus_reputacion=15.0)
        entrenador.desbloquear_logro("campeon_continental")
    elif resultado.fase_alcanzada in ("semifinal", "final"):
        entrenador.reputacion = min(100.0, entrenador.reputacion + 3.0)
