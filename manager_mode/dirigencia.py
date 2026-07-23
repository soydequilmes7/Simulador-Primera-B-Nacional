# -*- coding: utf-8 -*-
"""manager_mode/dirigencia.py

Sistema de dirigencia del Modo DT: cada club tiene un perfil con
objetivos posibles y un nivel de exigencia (River tolera menos que
Temperley). Al cierre de temporada, EvaluadorDirigenciaService resuelve
si el DT cumplió sus objetivos y decide su continuidad (renovar / en
observación / despedir). Fase 2 del plan (docs/PLAN_MODO_DT.md).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from manager_mode.domain import Entrenador, ObjetivoTemporada
from manager_mode.eventos import EstadoClub


class TipoObjetivo(str, Enum):
    """Objetivos medibles que la dirigencia le puede fijar al DT. No
    todos los objetivos del brief son medibles con datos objetivos
    (ej. "jugar con intensidad" es subjetivo) -- se modelan solo los
    que se pueden evaluar contra el resultado real de la temporada."""

    SALIR_CAMPEON = "salir_campeon"
    SEMIFINAL_COPA_CONTINENTAL = "semifinal_copa_continental"
    PROMOVER_JUVENILES = "promover_juveniles"
    ASCENDER = "ascender"
    REDUCIR_DEUDA = "reducir_deuda"
    PELEAR_ARRIBA = "pelear_arriba"
    NO_VENDER_FIGURAS = "no_vender_figuras"
    CONSOLIDARSE = "consolidarse"
    PROYECTO_LARGO = "proyecto_largo"
    CLASIFICAR_MUNDIAL = "clasificar_mundial"
    GANAR_COPA_AMERICA = "ganar_copa_america"


DESCRIPCION_OBJETIVO: dict[TipoObjetivo, str] = {
    TipoObjetivo.SALIR_CAMPEON: "Salir campeón",
    TipoObjetivo.SEMIFINAL_COPA_CONTINENTAL: "Llegar a semifinales de Copa continental",
    TipoObjetivo.PROMOVER_JUVENILES: "Promover juveniles de cantera",
    TipoObjetivo.ASCENDER: "Ascender de categoría",
    TipoObjetivo.REDUCIR_DEUDA: "Reducir la deuda del club",
    TipoObjetivo.PELEAR_ARRIBA: "Pelear en la parte alta de la tabla",
    TipoObjetivo.NO_VENDER_FIGURAS: "No vender a las figuras del plantel",
    TipoObjetivo.CONSOLIDARSE: "Consolidarse en la categoría",
    TipoObjetivo.PROYECTO_LARGO: "Sostener un proyecto a largo plazo",
    TipoObjetivo.CLASIFICAR_MUNDIAL: "Clasificar al Mundial",
    TipoObjetivo.GANAR_COPA_AMERICA: "Ganar la Copa América",
}


def crear_objetivo(tipo: TipoObjetivo) -> ObjetivoTemporada:
    """Crea un ObjetivoTemporada a partir de un TipoObjetivo del
    catálogo, con su descripción narrativa correspondiente."""
    return ObjetivoTemporada(descripcion=DESCRIPCION_OBJETIVO[tipo], tipo=tipo.value)


@dataclass(frozen=True)
class PerfilClub:
    """Personalidad de un club: qué objetivos puede fijar y qué tan
    exigente es al evaluar la continuidad del DT.

    Atributos:
      nombre: nombre del club.
      objetivos_posibles: pool de TipoObjetivo del que la dirigencia
        elige (ver generar_objetivos_temporada).
      exigencia: 0.0 (muy tolerante, ej. Instituto) a 1.0 (exige todo,
        ej. River). Sube el umbral de puntaje necesario para renovar y
        determina si un descenso es causal automática de despido.
      escudo: nombre de archivo bajo public/escudos/ (mismo criterio
        que ESCUDOS/slugifyEquipo del frontend). None si todavía no
        hay asset cargado (ej. Selección Argentina).
      es_seleccion: True si el "club" es en realidad un seleccionado
        nacional (cambia el pool de objetivos y las reglas de
        aparición en el pool de ofertas -- ver ofertas.py).
      clasifica_libertadores: True si el club puede jugar (y ganar) la
        Copa Libertadores en el Modo DT -- reservado a los clubes de
        mayor nivel, como en la realidad (Argentina tiene pocos cupos
        directos a Libertadores frente a los de Sudamericana).
      clasifica_sudamericana: True si el club puede jugar (y ganar) la
        Copa Sudamericana -- pool más amplio que Libertadores, incluye
        a la mitad de la tabla de Primera. Ver copas_continentales.py.
        Deliberadamente NO conectado a los motores reales de
        Libertadores/Sudamericana de season/ (simulación simplificada,
        propia del Modo DT).
      division: división del club. Los de "Liga Profesional" son los
        de arriba (solo aparecen como ofertas post-reputación, nunca
        como club inicial); los de "Primera Nacional"/"Primera C" son
        los de arranque de carrera (ver generar_ofertas_iniciales en
        ofertas.py).
    """

    nombre: str
    objetivos_posibles: tuple[TipoObjetivo, ...]
    exigencia: float
    escudo: str | None = None
    es_seleccion: bool = False
    clasifica_libertadores: bool = False
    clasifica_sudamericana: bool = False
    division: str = "Liga Profesional"

    @property
    def clasifica_alguna_copa_continental(self) -> bool:
        return self.clasifica_libertadores or self.clasifica_sudamericana


CATALOGO_PERFILES_CLUB: dict[str, PerfilClub] = {
    "River": PerfilClub(
        "River",
        (TipoObjetivo.SALIR_CAMPEON, TipoObjetivo.SEMIFINAL_COPA_CONTINENTAL,
         TipoObjetivo.PROMOVER_JUVENILES),
        exigencia=0.9,
        escudo="river.png",
        clasifica_libertadores=True,
        clasifica_sudamericana=True,
    ),
    "Boca": PerfilClub(
        "Boca",
        (TipoObjetivo.SALIR_CAMPEON, TipoObjetivo.PELEAR_ARRIBA),
        exigencia=0.85,
        escudo="boca.png",
        clasifica_libertadores=True,
        clasifica_sudamericana=True,
    ),
    "Independiente": PerfilClub(
        "Independiente",
        (TipoObjetivo.SALIR_CAMPEON, TipoObjetivo.SEMIFINAL_COPA_CONTINENTAL),
        exigencia=0.75,
        escudo="independiente.png",
        clasifica_libertadores=True,
        clasifica_sudamericana=True,
    ),
    "Racing": PerfilClub(
        "Racing",
        (TipoObjetivo.SALIR_CAMPEON, TipoObjetivo.SEMIFINAL_COPA_CONTINENTAL, TipoObjetivo.PELEAR_ARRIBA),
        exigencia=0.7,
        escudo="racing.png",
        clasifica_libertadores=True,
        clasifica_sudamericana=True,
    ),
    "San Lorenzo": PerfilClub(
        "San Lorenzo",
        (TipoObjetivo.PELEAR_ARRIBA, TipoObjetivo.SEMIFINAL_COPA_CONTINENTAL),
        exigencia=0.65,
        escudo="sanlorenzo.png",
        clasifica_libertadores=True,
        clasifica_sudamericana=True,
    ),
    "Vélez": PerfilClub(
        "Vélez",
        (TipoObjetivo.PELEAR_ARRIBA, TipoObjetivo.PROMOVER_JUVENILES),
        exigencia=0.6,
        escudo="velez.png",
        clasifica_libertadores=True,
        clasifica_sudamericana=True,
    ),
    "Talleres": PerfilClub(
        "Talleres",
        (TipoObjetivo.PELEAR_ARRIBA, TipoObjetivo.NO_VENDER_FIGURAS),
        exigencia=0.55,
        escudo="talleres.png",
        clasifica_sudamericana=True,
    ),
    "Estudiantes": PerfilClub(
        "Estudiantes",
        (TipoObjetivo.PELEAR_ARRIBA, TipoObjetivo.SEMIFINAL_COPA_CONTINENTAL),
        exigencia=0.6,
        escudo="estudiantes.png",
        clasifica_sudamericana=True,
    ),
    "Newell's Old Boys": PerfilClub(
        "Newell's Old Boys",
        (TipoObjetivo.PELEAR_ARRIBA, TipoObjetivo.NO_VENDER_FIGURAS),
        exigencia=0.5,
        escudo="newells.png",
        clasifica_sudamericana=True,
    ),
    "Huracán": PerfilClub(
        "Huracán",
        (TipoObjetivo.PELEAR_ARRIBA, TipoObjetivo.CONSOLIDARSE),
        exigencia=0.45,
        escudo="huracan.png",
        clasifica_sudamericana=True,
    ),
    "Godoy Cruz": PerfilClub(
        "Godoy Cruz",
        (TipoObjetivo.CONSOLIDARSE, TipoObjetivo.NO_VENDER_FIGURAS),
        exigencia=0.4,
        escudo="godoycruz.png",
        clasifica_sudamericana=True,
    ),
    "Lanús": PerfilClub(
        "Lanús",
        (TipoObjetivo.PELEAR_ARRIBA, TipoObjetivo.SEMIFINAL_COPA_CONTINENTAL),
        exigencia=0.5,
        escudo="lanus.png",
        clasifica_sudamericana=True,
    ),
    "Quilmes": PerfilClub(
        "Quilmes",
        (TipoObjetivo.ASCENDER, TipoObjetivo.REDUCIR_DEUDA),
        exigencia=0.4,
        escudo="quilmes.png",
        division="Primera Nacional",
    ),
    "San Martín de Tucumán": PerfilClub(
        "San Martín de Tucumán",
        (TipoObjetivo.PELEAR_ARRIBA, TipoObjetivo.NO_VENDER_FIGURAS),
        exigencia=0.5,
        escudo="sanmartintuc.png",
        division="Primera Nacional",
    ),
    "Temperley": PerfilClub(
        "Temperley",
        (TipoObjetivo.CONSOLIDARSE,),
        exigencia=0.3,
        escudo="temperley.png",
        division="Primera Nacional",
    ),
    "Instituto": PerfilClub(
        "Instituto",
        (TipoObjetivo.PROYECTO_LARGO,),
        exigencia=0.25,
        escudo="instituto.png",
        division="Primera C",
    ),
    "Selección Argentina": PerfilClub(
        "Selección Argentina",
        (TipoObjetivo.CLASIFICAR_MUNDIAL, TipoObjetivo.GANAR_COPA_AMERICA),
        exigencia=0.95,
        escudo=None,  # TODO(Pablo): falta el asset -- no hay escudo de
        # seleccionados en public/escudos/ hoy. Mientras tanto el
        # frontend puede resolver con la bandera de Argentina en su
        # lugar (banderaHTML() ya existe para el resto del sitio).
        es_seleccion=True,
    ),
}


def generar_objetivos_temporada(
    perfil: PerfilClub,
    rng: random.Random,
    cantidad: int = 2,
) -> list[ObjetivoTemporada]:
    """Elige `cantidad` objetivos (sin repetir) del pool del perfil y
    los devuelve como ObjetivoTemporada listos para asignar a un
    Contrato. Si el perfil tiene menos objetivos posibles que
    `cantidad`, devuelve todos los que tenga."""
    tipos = list(perfil.objetivos_posibles)
    cantidad = min(cantidad, len(tipos))
    elegidos = rng.sample(tipos, k=cantidad)
    return [crear_objetivo(tipo) for tipo in elegidos]


@dataclass
class ResultadoTemporada:
    """Datos objetivos del cierre de temporada, contra los que se
    evalúan los objetivos fijados por la dirigencia."""

    posicion_final: int
    total_equipos: int
    gano_titulo: bool = False
    llego_semifinal_copa_continental: bool = False
    ascendio: bool = False
    descendio: bool = False
    juveniles_debutados: int = 0
    vendio_figura: bool = False
    deuda_reducida: bool = False
    clasifico_mundial: bool = False
    gano_copa_america: bool = False


_EVALUADORES: dict[TipoObjetivo, Callable[[ResultadoTemporada], bool]] = {
    TipoObjetivo.SALIR_CAMPEON: lambda r: r.gano_titulo,
    TipoObjetivo.SEMIFINAL_COPA_CONTINENTAL: lambda r: r.llego_semifinal_copa_continental,
    TipoObjetivo.PROMOVER_JUVENILES: lambda r: r.juveniles_debutados >= 2,
    TipoObjetivo.ASCENDER: lambda r: r.ascendio,
    TipoObjetivo.REDUCIR_DEUDA: lambda r: r.deuda_reducida,
    TipoObjetivo.PELEAR_ARRIBA: lambda r: r.posicion_final <= max(1, r.total_equipos // 3),
    TipoObjetivo.NO_VENDER_FIGURAS: lambda r: not r.vendio_figura,
    TipoObjetivo.CONSOLIDARSE: lambda r: not r.descendio,
    TipoObjetivo.PROYECTO_LARGO: lambda r: not r.descendio,
    TipoObjetivo.CLASIFICAR_MUNDIAL: lambda r: r.clasifico_mundial,
    TipoObjetivo.GANAR_COPA_AMERICA: lambda r: r.gano_copa_america,
}


class DecisionContinuidad(str, Enum):
    RENOVAR = "renovar"
    EN_OBSERVACION = "en_observacion"
    DESPEDIR = "despedir"


@dataclass(frozen=True)
class EvaluacionTemporada:
    """Resultado de evaluar una temporada completa: cuántos objetivos
    se cumplieron y qué decide la dirigencia sobre la continuidad."""

    objetivos_cumplidos: int
    objetivos_totales: int
    decision: DecisionContinuidad


class EvaluadorDirigenciaService:
    """Evalúa objetivos de temporada contra el resultado real y decide
    la continuidad del DT según el perfil de exigencia del club."""

    def evaluar_objetivo(self, objetivo: ObjetivoTemporada, resultado: ResultadoTemporada) -> bool:
        """Resuelve `objetivo.cumplido` in-place contra `resultado` y
        lo devuelve. Lanza ValueError si el objetivo no tiene `tipo`
        asignado (ej. se creó a mano con solo `descripcion`, sin pasar
        por `crear_objetivo`)."""
        if objetivo.tipo is None:
            raise ValueError(f"el objetivo {objetivo.descripcion!r} no tiene tipo asignado")
        tipo = TipoObjetivo(objetivo.tipo)
        cumplido = _EVALUADORES[tipo](resultado)
        objetivo.cumplido = cumplido
        return cumplido

    def evaluar_temporada(
        self,
        objetivos: list[ObjetivoTemporada],
        resultado: ResultadoTemporada,
        perfil: PerfilClub,
        estado: EstadoClub,
    ) -> EvaluacionTemporada:
        """Evalúa todos los objetivos vigentes y decide la continuidad.

        La decisión combina el cumplimiento de objetivos (60%) con la
        confianza acumulada de la dirigencia vía eventos (40%), pero un
        descenso en un club exigente (`exigencia >= 0.6`) es causal de
        despido automática sin importar el resto.
        """
        cumplidos = sum(1 for objetivo in objetivos if self.evaluar_objetivo(objetivo, resultado))
        total = len(objetivos)
        proporcion_cumplida = (cumplidos / total) if total else 1.0

        if resultado.descendio and perfil.exigencia >= 0.6:
            decision = DecisionContinuidad.DESPEDIR
        else:
            puntaje = proporcion_cumplida * 0.6 + (estado.confianza / 100.0) * 0.4
            umbral_renovar = 0.5 + perfil.exigencia * 0.3
            umbral_observacion = 0.3
            if puntaje >= umbral_renovar:
                decision = DecisionContinuidad.RENOVAR
            elif puntaje >= umbral_observacion:
                decision = DecisionContinuidad.EN_OBSERVACION
            else:
                decision = DecisionContinuidad.DESPEDIR

        return EvaluacionTemporada(
            objetivos_cumplidos=cumplidos,
            objetivos_totales=total,
            decision=decision,
        )

    def aplicar_decision(self, entrenador: Entrenador, evaluacion: EvaluacionTemporada) -> None:
        """Aplica los efectos de la decisión sobre el Entrenador:
        RENOVAR extiende un año el contrato y sube reputación; DESPEDIR
        libera al DT (contrato=None) y baja reputación; EN_OBSERVACION
        no toca el contrato (queda para la próxima evaluación)."""
        if evaluacion.decision == DecisionContinuidad.RENOVAR:
            if entrenador.contrato is not None:
                entrenador.contrato.renovar(1)
            entrenador.reputacion = min(100.0, entrenador.reputacion + 5.0)
        elif evaluacion.decision == DecisionContinuidad.DESPEDIR:
            if entrenador.contrato is not None:
                entrenador.historial_clubes.append(entrenador.contrato.club_id)
            entrenador.contrato = None
            entrenador.reputacion = max(0.0, entrenador.reputacion - 10.0)
        # EN_OBSERVACION: sin cambios en el contrato ni la reputación.
