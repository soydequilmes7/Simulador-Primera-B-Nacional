# -*- coding: utf-8 -*-
"""manager_mode/match_service.py

Servicio de simulación de partidos del Modo DT. Responsabilidad única
(SRP): aplicar el modificador de IdentidadTactica del entrenador sobre
los ratings de su club y delegar el resultado en el motor de simulación
YA EXISTENTE del proyecto (modelos.motor_vectorizado), sin reimplementar
Dixon-Coles. Fase 0 del plan (docs/PLAN_MODO_DT.md).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from manager_mode.domain import Entrenador
from modelos.motor_vectorizado import simular_partido_simple


@dataclass(frozen=True)
class ResultadoPartidoDT:
    """Resultado de un partido simulado en Modo DT.

    Atributos:
      goles_local: goles del equipo local.
      goles_visitante: goles del equipo visitante.
      goles_entrenador: goles del club que dirige el entrenador (según
        haya jugado de local o visitante).
      goles_rival: goles del rival.
    """

    goles_local: int
    goles_visitante: int
    goles_entrenador: int
    goles_rival: int

    @property
    def victoria_entrenador(self) -> bool:
        return self.goles_entrenador > self.goles_rival

    @property
    def empate(self) -> bool:
        return self.goles_entrenador == self.goles_rival


class PartidoDTService:
    """Simula partidos del Modo DT aplicando la identidad táctica del
    entrenador sobre los ratings base de su club."""

    def __init__(self, rng: np.random.Generator | None = None) -> None:
        self._rng = rng if rng is not None else np.random.default_rng()

    def simular_partido(
        self,
        entrenador: Entrenador,
        ataque_club: float,
        defensa_club: float,
        ataque_rival: float,
        defensa_rival: float,
        de_local: bool,
    ) -> ResultadoPartidoDT:
        """Simula un partido del club dirigido por `entrenador` contra
        un rival con ratings `ataque_rival`/`defensa_rival`.

        Args:
          entrenador: DT a cargo (aporta el modificador táctico).
          ataque_club, defensa_club: ratings base del club dirigido,
            relativos al promedio de liga (1.0 = promedio), ANTES de
            aplicar el modificador táctico.
          ataque_rival, defensa_rival: ratings base del rival, sin
            modificador (el rival no lo dirige el usuario).
          de_local: True si el club dirigido juega de local.

        Returns:
          ResultadoPartidoDT con el marcador y helpers de victoria/empate
          ya resueltos desde el punto de vista del entrenador.
        """
        mod = entrenador.modificador_tactico
        ataque_club_mod = ataque_club * mod.ataque
        defensa_club_mod = defensa_club * mod.defensa

        if de_local:
            goles_local, goles_visitante = simular_partido_simple(
                ataque_local=ataque_club_mod,
                defensa_visitante=defensa_rival,
                ataque_visitante=ataque_rival,
                defensa_local=defensa_club_mod,
                rng=self._rng,
            )
            goles_entrenador, goles_rival = goles_local, goles_visitante
        else:
            goles_local, goles_visitante = simular_partido_simple(
                ataque_local=ataque_rival,
                defensa_visitante=defensa_club_mod,
                ataque_visitante=ataque_club_mod,
                defensa_local=defensa_rival,
                rng=self._rng,
            )
            goles_entrenador, goles_rival = goles_visitante, goles_local

        entrenador.record.registrar_resultado(goles_entrenador, goles_rival)

        return ResultadoPartidoDT(
            goles_local=goles_local,
            goles_visitante=goles_visitante,
            goles_entrenador=goles_entrenador,
            goles_rival=goles_rival,
        )
