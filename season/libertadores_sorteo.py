# -*- coding: utf-8 -*-
"""
season/libertadores_sorteo.py

Sorteo de la fase de grupos de Copa Libertadores (8 zonas de 4), a
partir de los 32 clasificados que arma LibertadoresManager (ver
season/libertadores_manager.py). Mismo criterio real de CONMEBOL:

    - 4 bombos de 8 equipos cada uno, ordenados por Elo (bombo 1 = los
      8 mejores, ..., bombo 4 = los 8 más débiles).
    - Cada zona recibe un equipo de cada bombo.
    - Dos equipos del mismo país NO pueden compartir zona.

Con 6 cupos argentinos y 6 brasileños repartidos en bombos distintos
(un país nunca ocupa más de un lugar por bombo, ver
_repartir_en_bombos()), el sorteo con backtracking casi nunca necesita
reintentar -- pero se deja el reintento igual por si el pool
internacional rotado ese año concentra demasiado un mismo país en un
bombo.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

CANTIDAD_ZONAS = 8
EQUIPOS_POR_ZONA = 4
LETRAS_ZONA = "ABCDEFGH"


@dataclass
class ZonaSorteada:
    letra: str
    equipos: list[str] = field(default_factory=list)


def _repartir_en_bombos(equipos_ordenados: list) -> list[list]:
    """Corta la lista (ya ordenada de mejor a peor Elo) en 4 bombos de
    8. Requiere exactamente 32 equipos."""
    if len(equipos_ordenados) != CANTIDAD_ZONAS * EQUIPOS_POR_ZONA:
        raise ValueError(
            f"El sorteo de grupos necesita exactamente {CANTIDAD_ZONAS * EQUIPOS_POR_ZONA} "
            f"clasificados, se recibieron {len(equipos_ordenados)}."
        )
    return [equipos_ordenados[i:i + CANTIDAD_ZONAS] for i in range(0, len(equipos_ordenados), CANTIDAD_ZONAS)]


def sortear_grupos(
    clasificacion,
    rng: random.Random | None = None,
    max_intentos: int = 200,
) -> list[ZonaSorteada]:
    """clasificacion: un ClasificacionLibertadores (ver
    season/libertadores_manager.py) con exactamente 32 equipos.

    Devuelve 8 ZonaSorteada (A a H). Levanta ValueError si no se
    consigue un sorteo válido (sin dos equipos del mismo país en la
    misma zona) en `max_intentos` intentos -- en la práctica no
    debería pasar con las cuotas por país actuales (ningún país tiene
    más de 6 cupos, y hay 8 zonas).
    """
    rng = rng or random.Random()
    equipos = sorted(clasificacion.equipos, key=lambda c: -c.elo)
    bombos = _repartir_en_bombos(equipos)

    for _ in range(max_intentos):
        bombos_mezclados = [b[:] for b in bombos]
        for b in bombos_mezclados:
            rng.shuffle(b)

        zonas = [ZonaSorteada(letra=LETRAS_ZONA[i]) for i in range(CANTIDAD_ZONAS)]
        paises_por_zona: list[set] = [set() for _ in range(CANTIDAD_ZONAS)]
        exito = True

        for bombo in bombos_mezclados:
            candidatos = bombo[:]
            orden_zonas = list(range(CANTIDAD_ZONAS))
            for i in orden_zonas:
                # Busca, entre los candidatos que quedan de este bombo,
                # el primero cuyo país todavía no esté en la zona i.
                asignado = None
                for c in candidatos:
                    if c.pais not in paises_por_zona[i]:
                        asignado = c
                        break
                if asignado is None:
                    exito = False
                    break
                zonas[i].equipos.append(asignado.equipo)
                paises_por_zona[i].add(asignado.pais)
                candidatos.remove(asignado)
            if not exito:
                break

        if exito:
            return zonas

    raise ValueError(
        "No se pudo armar un sorteo válido de 8 zonas sin repetir país "
        f"por zona en {max_intentos} intentos -- revisar si el pool rotado "
        "concentra demasiados equipos de un mismo país en un bombo."
    )
