# -*- coding: utf-8 -*-
"""
modelos/club.py

Entidad Club: identidad única de un equipo a través de todas las
divisiones del fútbol argentino modeladas por el simulador. A diferencia
del resto del proyecto (donde cada motor de simulación -- Estadisticas,
EstadisticasLPF, EstadisticasBMetro, EstadisticasFederal, la Estadisticas
propia de Primera C, etc. -- trata a los equipos como simples strings
dentro del CSV/tabla de SU división), un Club es una entidad que persiste
ENTRE divisiones y ENTRE temporadas: cuando asciende o desciende, no se
crea un Club nuevo -- se le reasigna el atributo `division`.

Etapa 0 del Modo Temporada Nacional: esta clase y ClubRegistry (en
season/club_registry.py) se arman de SOLO LECTURA a partir de los datos
que ya existen (tabla_X.csv / repository, vía data_access.league_data),
sin escribir nada todavía ni tocar ningún motor de simulación existente.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Club:
    """Un club de fútbol argentino, con identidad única a través de las
    divisiones y temporadas.

    Atributos:
      id: identificador estable, nunca cambia (ni al ascender/descender).
      name: nombre tal como aparece en la tabla de su división actual.
        OJO: este es el nombre "canónico" de la Etapa 0 (viene de
        tabla_X.csv / repository); no resuelve alias entre scrapers --
        eso sigue siendo responsabilidad de mapeo_equipos*.py para la
        ingesta de resultados, un problema distinto al de este registro.
      division: nombre de división actual (mutable). Cuando el club
        asciende o desciende, SOLO se reasigna este campo -- nunca se
        crea un Club nuevo. Lo muta PromotionManager (etapa posterior
        del plan), nunca el propio Club ni el ClubRegistry directamente.
      rating: reservado para cuando haga falta un rating "portable"
        entre divisiones (ver Etapa 3 del plan de implementación: hoy
        el rating de cada motor se recalcula en tiempo real a partir
        del historial de resultados DE ESA división -- no es un
        atributo persistente en ningún lado). En Etapa 0 queda en None;
        no se calcula ni se usa todavía.
      shield: ruta/nombre de archivo del escudo, si está disponible.
        Ningún tabla_X.csv trae esto hoy -- queda en None salvo que se
        pueble después desde otra fuente.
      history: lista de entradas de historial por temporada (dicts
        libres, p.ej. {"temporada": 2026, "division": "Primera C", ...}).
        Vacía en Etapa 0; HistoryManager (etapa posterior) la completa.
    """
    id: int
    name: str
    division: str
    rating: Optional[float] = None
    shield: Optional[str] = None
    history: list = field(default_factory=list)

    def __repr__(self) -> str:
        return f"Club(id={self.id}, name={self.name!r}, division={self.division!r})"
