# -*- coding: utf-8 -*-
"""manager_mode/domain.py

Entidades de dominio del Modo DT (Director Técnico). Sin IO: no tocan
Supabase, CSVs ni el motor de simulación -- eso es responsabilidad de las
capas de servicio (ver match_service.py). Fase 0 del plan
(docs/PLAN_MODO_DT.md).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class IdentidadTactica(str, Enum):
    """Filosofía táctica elegida por el DT al crear la carrera. Cada una
    modifica los ratings de ataque/defensa del club dirigido y, más
    adelante (Fase 1+), el peso de eventos relacionados (ej. el
    Formador recibe más eventos de juveniles)."""

    PRAGMATICO = "pragmatico"
    OFENSIVO = "ofensivo"
    FORMADOR = "formador"
    MOTIVADOR = "motivador"


@dataclass(frozen=True)
class ModificadorTactico:
    """Modificadores multiplicativos que una IdentidadTactica aplica
    sobre los ratings base de ataque/defensa de un club.

    Atributos:
      ataque: multiplicador sobre el rating de ataque (>1 = más gol).
      defensa: multiplicador sobre el rating de defensa (>1 = menos
        goles recibidos -- ojo, en el motor vectorizado un rating de
        defensa más ALTO significa mejor defensa, así que aplica
        directo, sin invertir).
      moral_por_victoria: cuánta moral de vestuario suma cada victoria.
      peso_eventos_juveniles: multiplicador sobre la probabilidad de
        que aparezcan eventos de cantera/juveniles (Fase 1).
    """

    ataque: float
    defensa: float
    moral_por_victoria: float
    peso_eventos_juveniles: float = 1.0


MODIFICADORES_POR_IDENTIDAD: dict[IdentidadTactica, ModificadorTactico] = {
    IdentidadTactica.PRAGMATICO: ModificadorTactico(
        ataque=0.95, defensa=1.10, moral_por_victoria=1.0,
    ),
    IdentidadTactica.OFENSIVO: ModificadorTactico(
        ataque=1.12, defensa=0.92, moral_por_victoria=1.2,
    ),
    IdentidadTactica.FORMADOR: ModificadorTactico(
        ataque=0.97, defensa=0.97, moral_por_victoria=1.0,
        peso_eventos_juveniles=1.8,
    ),
    IdentidadTactica.MOTIVADOR: ModificadorTactico(
        ataque=1.0, defensa=1.0, moral_por_victoria=1.5,
    ),
}


@dataclass
class ObjetivoTemporada:
    """Objetivo que la dirigencia le fija al DT para la temporada
    (ej. River: 'Salir campeón'; Quilmes: 'Ascender'). `cumplido` queda
    en None hasta que EvaluadorDirigenciaService lo resuelva (Fase 2)."""

    descripcion: str
    cumplido: bool | None = None


@dataclass
class Contrato:
    """Contrato vigente entre el DT y un club.

    Atributos:
      club_id: id del club (ver modelos.club.Club).
      temporadas_restantes: cuenta regresiva; 0 = último año del vínculo.
      sueldo: sueldo por temporada, en la moneda del simulador.
      objetivos: lista de ObjetivoTemporada vigentes para el ciclo.
    """

    club_id: int
    temporadas_restantes: int
    sueldo: float
    objetivos: list[ObjetivoTemporada] = field(default_factory=list)

    def renovar(self, temporadas: int) -> None:
        """Extiende el contrato. `temporadas` debe ser > 0."""
        if temporadas <= 0:
            raise ValueError("temporadas debe ser mayor a 0")
        self.temporadas_restantes += temporadas

    def avanzar_temporada(self) -> None:
        """Descuenta un año de contrato. No baja de 0 (un contrato
        vencido se resuelve por fuera, vía oferta/despido, no acá)."""
        if self.temporadas_restantes > 0:
            self.temporadas_restantes -= 1

    @property
    def vencido(self) -> bool:
        return self.temporadas_restantes <= 0


@dataclass
class RecordEntrenador:
    """Récord acumulado de partidos dirigidos."""

    partidos_jugados: int = 0
    victorias: int = 0
    empates: int = 0
    derrotas: int = 0

    def registrar_resultado(self, goles_propios: int, goles_rival: int) -> None:
        self.partidos_jugados += 1
        if goles_propios > goles_rival:
            self.victorias += 1
        elif goles_propios == goles_rival:
            self.empates += 1
        else:
            self.derrotas += 1


@dataclass
class Entrenador:
    """Entidad principal del Modo DT: el entrenador que el usuario
    dirige a lo largo de la carrera.

    Atributos:
      nombre: nombre elegido por el usuario.
      identidad: IdentidadTactica elegida al crear la carrera
        (inmutable durante la carrera en Fase 0; podría volverse
        cambiable en fases futuras vía evento especial).
      reputacion: 0-100, sube con títulos/objetivos cumplidos, baja con
        despidos y objetivos incumplidos.
      contrato: Contrato vigente, o None si está libre.
      record: RecordEntrenador acumulado histórico (todos los clubes).
      titulos: lista de descripciones de títulos ganados.
      historial_clubes: ids de clubes dirigidos, en orden cronológico.
    """

    nombre: str
    identidad: IdentidadTactica
    reputacion: float = 50.0
    contrato: Contrato | None = None
    record: RecordEntrenador = field(default_factory=RecordEntrenador)
    titulos: list[str] = field(default_factory=list)
    historial_clubes: list[int] = field(default_factory=list)

    @property
    def modificador_tactico(self) -> ModificadorTactico:
        return MODIFICADORES_POR_IDENTIDAD[self.identidad]

    @property
    def libre(self) -> bool:
        return self.contrato is None

    def firmar_contrato(self, contrato: Contrato) -> None:
        """Firma un contrato nuevo. Si dirigía otro club, queda
        registrado en el historial antes de pisarlo."""
        if self.contrato is not None:
            self.historial_clubes.append(self.contrato.club_id)
        self.contrato = contrato

    def sumar_titulo(self, descripcion: str, bonus_reputacion: float = 10.0) -> None:
        self.titulos.append(descripcion)
        self.reputacion = min(100.0, self.reputacion + bonus_reputacion)
