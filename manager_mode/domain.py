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
from typing import ClassVar


class IdentidadTactica(str, Enum):
    """Filosofía táctica elegida por el DT al crear la carrera. Cada una
    modifica los ratings de ataque/defensa del club dirigido y, más
    adelante (Fase 1+), el peso de eventos relacionados (ej. el
    Formador recibe más eventos de juveniles)."""

    PRAGMATICO = "pragmatico"
    OFENSIVO = "ofensivo"
    FORMADOR = "formador"
    MOTIVADOR = "motivador"
    REVOLUCIONARIO = "revolucionario"


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
    IdentidadTactica.REVOLUCIONARIO: ModificadorTactico(
        # Mucho riesgo: sube más el ataque de lo que resigna en defensa
        # que cualquier otra identidad -- partidos con más goles en
        # ambos arcos (boom/bust), en vez de resultados calculados.
        ataque=1.20, defensa=0.80, moral_por_victoria=1.3,
    ),
}


@dataclass
class ObjetivoTemporada:
    """Objetivo que la dirigencia le fija al DT para la temporada
    (ej. River: 'Salir campeón'; Quilmes: 'Ascender'). `cumplido` queda
    en None hasta que EvaluadorDirigenciaService lo resuelva (Fase 2).

    `tipo` es el código de TipoObjetivo (manager_mode/dirigencia.py)
    cuando el objetivo viene del catálogo medible -- queda en None si
    se crea a mano solo con descripción (ej. objetivos puramente
    narrativos, no evaluables contra datos objetivos)."""

    descripcion: str
    cumplido: bool | None = None
    tipo: str | None = None


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


@dataclass(frozen=True)
class Logro:
    """Definición de un logro desbloqueable (catálogo estático, ver
    CATALOGO_LOGROS). No confundir con `titulos` de Entrenador: un
    título es un trofeo concreto (ej. "Campeón LPF 2026"); un logro es
    una distinción por hito de carrera (ej. "Rey del Ascenso")."""

    codigo: str
    nombre: str
    descripcion: str


CATALOGO_LOGROS: dict[str, Logro] = {
    logro.codigo: logro
    for logro in (
        Logro("especialista_clasicos", "Especialista en Clásicos", "Ganó 5 clásicos dirigiendo."),
        Logro("maestro_juveniles", "Maestro de Juveniles", "Debutó a 10 juveniles de cantera."),
        Logro("milagro_deportivo", "Milagro Deportivo", "Evitó un descenso que parecía sentenciado."),
        Logro("rey_del_ascenso", "Rey del Ascenso", "Logró 3 ascensos en la carrera."),
        Logro("invicto", "Invicto", "Terminó una temporada completa sin perder."),
        Logro("arquitecto", "Arquitecto", "Construyó un plantel campeón con más de la mitad de cantera."),
        Logro("leyenda", "Leyenda", "Dirigió a un mismo club durante 10 temporadas o más."),
        Logro("entrenador_del_anio", "Entrenador del Año", "Distinción de la temporada por objetivos y campaña."),
        Logro("campeon_continental", "Campeón Continental", "Ganó la Libertadores o la Sudamericana."),
    )
}


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
      edad: edad del DT. Arranca en 30 (fijo, como muestra el
        frontend) y sube de a un año por temporada vía
        `avanzar_edad()`. El retiro es a los 75 -- ver `retirado`.
    """

    nombre: str
    identidad: IdentidadTactica
    reputacion: float = 50.0
    contrato: Contrato | None = None
    record: RecordEntrenador = field(default_factory=RecordEntrenador)
    titulos: list[str] = field(default_factory=list)
    historial_clubes: list[int] = field(default_factory=list)
    logros_desbloqueados: list[str] = field(default_factory=list)
    edad: int = 30

    EDAD_RETIRO: ClassVar[int] = 75

    @property
    def retirado(self) -> bool:
        return self.edad >= self.EDAD_RETIRO

    def avanzar_edad(self) -> bool:
        """Suma un año a la edad tras cerrar una temporada. Devuelve
        True si con este año el DT llega (o ya estaba en) la edad de
        retiro -- el llamador decide qué hacer con eso (fin de carrera,
        pantalla de despedida, etc.), esto solo informa el hito."""
        self.edad += 1
        return self.retirado

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

    def desbloquear_logro(self, codigo: str) -> bool:
        """Desbloquea un logro del catálogo si todavía no lo tenía.
        Devuelve True si se desbloqueó recién ahora, False si ya lo
        tenía (para que el llamador sepa si debe disparar un evento de
        celebración) o si el código no existe en el catálogo."""
        if codigo not in CATALOGO_LOGROS:
            return False
        if codigo in self.logros_desbloqueados:
            return False
        self.logros_desbloqueados.append(codigo)
        return True
