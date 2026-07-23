# -*- coding: utf-8 -*-
"""manager_mode/narrativa.py

Motor de narrativa del Modo DT: banco de frases fijas por categoría e
intensidad, con variables interpoladas (club, rival, racha, entrenador)
para que no se sientan repetidas. Decisión de diseño confirmada con
Pablo: híbrido, sin llamadas a la API de Claude en runtime (sin costo,
sin latencia). Fase 1 del plan (docs/PLAN_MODO_DT.md).
"""
from __future__ import annotations

import random
from enum import Enum


class TipoReaccion(str, Enum):
    """Quién reacciona ante una decisión o resultado del DT."""

    PRENSA = "prensa"
    HINCHADA = "hinchada"
    VESTUARIO = "vestuario"
    DIRIGENCIA = "dirigencia"


class Intensidad(str, Enum):
    """Qué tan bien o mal le fue al DT, para elegir el tono de la frase."""

    POSITIVA = "positiva"
    NEUTRA = "neutra"
    NEGATIVA = "negativa"


# Placeholders soportados: {club}, {rival}, {racha}, {entrenador}.
# Cada entrada del banco NO necesita usar todos -- solo los que
# correspondan al contexto disponible en ese evento.
BANCO_REACCIONES: dict[tuple[TipoReaccion, Intensidad], list[str]] = {
    (TipoReaccion.PRENSA, Intensidad.POSITIVA): [
        "La prensa destacó el andar de {club} bajo tu mando.",
        "Los diarios hablan de un {club} irreconocible con {entrenador}.",
        "\"Encontró la fórmula\", tituló la prensa deportiva sobre {entrenador}.",
        "Los cronistas más duros empiezan a rendirse ante {entrenador}.",
        "\"Un cambio de era en {club}\", resumió un móvil deportivo.",
        "La radio del gremio elogió el funcionamiento de {club} en la última fecha.",
    ],
    (TipoReaccion.PRENSA, Intensidad.NEUTRA): [
        "La prensa pide paciencia con el proceso de {entrenador} en {club}.",
        "Los cronistas todavía no se deciden sobre este {club}.",
        "\"Hay que verlo en el tiempo\", tituló un diario sobre {entrenador}.",
        "Los micrófonos esperan una racha más larga para opinar de {club}.",
    ],
    (TipoReaccion.PRENSA, Intensidad.NEGATIVA): [
        "La prensa destrozó la decisión de {entrenador}.",
        "\"Se le acaba el tiempo\", advirtieron los diarios sobre {club}.",
        "Los micrófonos ya piden la cabeza de {entrenador} tras la caída ante {rival}.",
        "\"Sin ideas\", tituló un matutino sobre el funcionamiento de {club}.",
        "La transmisión no perdonó ni un minuto la actuación de {club} ante {rival}.",
    ],
    (TipoReaccion.HINCHADA, Intensidad.POSITIVA): [
        "La hinchada de {club} empieza a ilusionarse en serio.",
        "Bancazo de la gente para {entrenador} después de vencer a {rival}.",
        "Las redes explotaron de alegría tras el triunfo de {club}.",
        "La gente ya canta el nombre de {entrenador} en la cancha.",
    ],
    (TipoReaccion.HINCHADA, Intensidad.NEUTRA): [
        "La hinchada de {club} observa con cautela.",
        "Todavía no hay veredicto de la gente sobre {entrenador}.",
        "El clima entre los hinchas de {club} es de expectativa, sin euforia.",
    ],
    (TipoReaccion.HINCHADA, Intensidad.NEGATIVA): [
        "Los hinchas no le perdonan la derrota ante {rival}.",
        "Silbatina para {entrenador} en la salida del estadio.",
        "Las redes de {club} se llenaron de reclamos tras el partido.",
        "Un grupo de socios pidió la salida de {entrenador} a la salida de la cancha.",
    ],
    (TipoReaccion.VESTUARIO, Intensidad.POSITIVA): [
        "El vestuario de {club} empezó a creer en el proyecto de {entrenador}.",
        "Los referentes respaldan a {entrenador} puertas adentro.",
        "El grupo cerró filas en torno a {entrenador} tras la seguidilla de triunfos.",
    ],
    (TipoReaccion.VESTUARIO, Intensidad.NEUTRA): [
        "El vestuario de {club} sigue el proceso sin sobresaltos.",
        "Puertas adentro de {club} el clima es de trabajo, sin grandes definiciones.",
    ],
    (TipoReaccion.VESTUARIO, Intensidad.NEGATIVA): [
        "Rumores de quiebre en el vestuario de {club}.",
        "Algunos jugadores ya cuestionan a {entrenador} puertas adentro.",
        "El clima interno de {club} empieza a resentirse.",
    ],
    (TipoReaccion.DIRIGENCIA, Intensidad.POSITIVA): [
        "La dirigencia de {club} quedó encantada con {entrenador}.",
        "Arriba respaldan el ciclo de {entrenador} sin condiciones.",
        "El presidente de {club} elogió públicamente el trabajo de {entrenador}.",
    ],
    (TipoReaccion.DIRIGENCIA, Intensidad.NEUTRA): [
        "La dirigencia de {club} evalúa el proceso mes a mes.",
        "Arriba prefieren esperar antes de sacar conclusiones sobre {entrenador}.",
    ],
    (TipoReaccion.DIRIGENCIA, Intensidad.NEGATIVA): [
        "La paciencia de la dirigencia con {entrenador} se agota.",
        "Arriba ya no ocultan su malestar con el rumbo de {club}.",
        "Circulan versiones de una reunión de urgencia por la continuidad de {entrenador}.",
    ],
}


BANCO_PORTADAS: dict[Intensidad, list[str]] = {
    Intensidad.POSITIVA: [
        "EL MILAGRO DE {club}",
        "NACIÓ UN CAMPEÓN EN {club}",
        "{entrenador}, EL REY DEL ASCENSO",
        "NADIE CREÍA EN {club}, MENOS ELLOS",
    ],
    Intensidad.NEUTRA: [
        "{club} SIGUE SU CAMINO",
        "PROCESO EN CONSTRUCCIÓN EN {club}",
    ],
    Intensidad.NEGATIVA: [
        "EL FIN DEL CICLO DE {entrenador}",
        "{club} TOCA FONDO",
        "SE ACABÓ LA PACIENCIA CON {entrenador}",
    ],
}


class NarrativaService:
    """Elige y arma frases del banco híbrido (plantilla + variables)."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng if rng is not None else random.Random()

    def reaccion(
        self,
        tipo: TipoReaccion,
        intensidad: Intensidad,
        contexto: dict[str, str],
    ) -> str:
        """Devuelve una frase de reacción ya interpolada con `contexto`.

        Args:
          tipo: quién reacciona (prensa, hinchada, vestuario, dirigencia).
          intensidad: tono de la reacción.
          contexto: valores para los placeholders usados en la plantilla
            elegida (ej. {"club": "Quilmes", "rival": "Boca"}). Si a la
            plantilla elegida le falta una clave, se propaga KeyError --
            mejor fallar rápido en desarrollo que mostrar un placeholder
            sin reemplazar en producción.
        """
        plantillas = BANCO_REACCIONES[(tipo, intensidad)]
        plantilla = self._rng.choice(plantillas)
        return plantilla.format(**contexto)

    def portada(self, intensidad: Intensidad, contexto: dict[str, str]) -> str:
        """Devuelve un titular de portada ya interpolado con `contexto`."""
        plantillas = BANCO_PORTADAS[intensidad]
        plantilla = self._rng.choice(plantillas)
        return plantilla.format(**contexto)
