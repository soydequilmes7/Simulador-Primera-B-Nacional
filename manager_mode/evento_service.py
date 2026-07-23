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

from manager_mode.domain import Entrenador, IdentidadTactica
from manager_mode.eventos import CATALOGO_EVENTOS, CategoriaEvento, EstadoClub, Evento, eventos_por_categoria
from manager_mode.narrativa import NarrativaService

# Pesos relativos de aparición por categoría, según la identidad táctica
# del DT (ver docs/PLAN_MODO_DT.md, Fase 1). Toda categoría no listada
# para una identidad usa peso 1.0 (frecuencia normal). Solo aplica
# cuando `elegir_evento` se llama SIN `categoria` explícita -- si el
# llamador pide una categoría puntual, la ponderación no corresponde.
PESOS_CATEGORIA_POR_IDENTIDAD: dict[IdentidadTactica, dict[CategoriaEvento, float]] = {
    IdentidadTactica.FORMADOR: {
        CategoriaEvento.JUVENILES: 2.5,
    },
    IdentidadTactica.MOTIVADOR: {
        CategoriaEvento.VESTUARIO: 1.8,
        CategoriaEvento.VIDA_PLANTEL: 1.5,
    },
    IdentidadTactica.PRAGMATICO: {
        CategoriaEvento.DIRIGENCIA: 1.5,
        CategoriaEvento.CRISIS: 0.7,
    },
    IdentidadTactica.OFENSIVO: {
        CategoriaEvento.CLASICOS: 1.5,
        CategoriaEvento.COPAS: 1.5,
    },
    IdentidadTactica.REVOLUCIONARIO: {
        CategoriaEvento.RUMORES: 1.6,
        CategoriaEvento.CRISIS: 1.6,
        CategoriaEvento.VIDA_PLANTEL: 1.3,
    },
}


class EventoService:
    """Elige eventos del catálogo y resuelve sus opciones."""

    def __init__(
        self,
        rng: random.Random | None = None,
        narrativa: NarrativaService | None = None,
    ) -> None:
        self._rng = rng if rng is not None else random.Random()
        self._narrativa = narrativa if narrativa is not None else NarrativaService(rng=self._rng)

    def elegir_evento(
        self,
        categoria: CategoriaEvento | None = None,
        entrenador: Entrenador | None = None,
        club_clasifica_libertadores: bool = False,
        club_clasifica_sudamericana: bool = False,
    ) -> Evento:
        """Elige un evento del catálogo.

        Args:
          categoria: si se pasa, restringe la elección a esa categoría
            (elección uniforme dentro de ella, sin ponderar). Se
            respeta tal cual la pida el llamador, incluso si es
            LIBERTADORES/SUDAMERICANA y el club no clasifica -- la
            responsabilidad de no pedir una categoría que no
            corresponde es del llamador en ese caso.
          entrenador: si se pasa (y `categoria` es None), pondera la
            probabilidad de cada evento según
            PESOS_CATEGORIA_POR_IDENTIDAD para su identidad táctica
            (ej. un Formador ve más seguido eventos de Juveniles).
          club_clasifica_libertadores: si es False (default) y
            `categoria` es None, excluye del sorteo la categoría
            LIBERTADORES -- ver PerfilClub.clasifica_libertadores.
          club_clasifica_sudamericana: idem para la categoría
            SUDAMERICANA -- ver PerfilClub.clasifica_sudamericana.
        """
        if categoria is not None:
            candidatos = eventos_por_categoria(categoria)
            if not candidatos:
                raise ValueError(f"no hay eventos cargados para la categoria {categoria!r}")
            return self._rng.choice(candidatos)

        candidatos = list(CATALOGO_EVENTOS.values())
        if not club_clasifica_libertadores:
            candidatos = [e for e in candidatos if e.categoria != CategoriaEvento.LIBERTADORES]
        if not club_clasifica_sudamericana:
            candidatos = [e for e in candidatos if e.categoria != CategoriaEvento.SUDAMERICANA]

        if entrenador is None:
            return self._rng.choice(candidatos)

        pesos_identidad = PESOS_CATEGORIA_POR_IDENTIDAD.get(entrenador.identidad, {})
        pesos = [pesos_identidad.get(evento.categoria, 1.0) for evento in candidatos]
        return self._rng.choices(candidatos, weights=pesos, k=1)[0]

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
