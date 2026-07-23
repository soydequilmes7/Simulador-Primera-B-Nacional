# -*- coding: utf-8 -*-
"""manager_mode/evento_service.py

Orquesta el catálogo de eventos: elige un evento (opcionalmente de una
categoría dada), aplica los efectos de la opción elegida sobre el
EstadoClub y devuelve la reacción narrativa correspondiente (o None si
la opción no dispara reacción pública). Fase 1 del plan
(docs/PLAN_MODO_DT.md).
"""
from __future__ import annotations

import random

from manager_mode.eventos import CATALOGO_EVENTOS, CategoriaEvento, EstadoClub, Evento, eventos_por_categoria
from manager_mode.narrativa import NarrativaService


class EventoService:
    """Elige eventos del catálogo y resuelve sus opciones."""

    def __init__(
        self,
        rng: random.Random | None = None,
        narrativa: NarrativaService | None = None,
    ) -> None:
        self._rng = rng if rng is not None else random.Random()
        self._narrativa = narrativa if narrativa is not None else NarrativaService(rng=self._rng)

    def elegir_evento(self, categoria: CategoriaEvento | None = None) -> Evento:
        """Elige un evento al azar del catálogo. Si se pasa `categoria`,
        restringe la elección a esa categoría."""
        candidatos = eventos_por_categoria(categoria) if categoria is not None else list(CATALOGO_EVENTOS.values())
        if not candidatos:
            raise ValueError(f"no hay eventos cargados para la categoria {categoria!r}")
        return self._rng.choice(candidatos)

    def resolver_opcion(
        self,
        estado: EstadoClub,
        evento: Evento,
        codigo_opcion: str,
        contexto: dict[str, str],
    ) -> str | None:
        """Aplica los efectos de la opción elegida sobre `estado` y
        devuelve la frase narrativa correspondiente, o None si esa
        opción no dispara una reacción pública (tipo_reaccion=None).

        Args:
          estado: EstadoClub a modificar in-place.
          evento: evento resuelto (ver EventoService.elegir_evento).
          codigo_opcion: código de la opción elegida por el usuario.
          contexto: variables para interpolar en la frase narrativa
            (club, rival, entrenador, racha).
        """
        opcion = evento.opcion(codigo_opcion)
        estado.aplicar(opcion.efectos)
        if opcion.tipo_reaccion is None:
            return None
        return self._narrativa.reaccion(opcion.tipo_reaccion, opcion.intensidad, contexto)
