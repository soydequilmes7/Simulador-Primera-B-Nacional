# -*- coding: utf-8 -*-
"""
fixture_generator.py

Generador genérico de fixtures "todos contra todos" (round-robin) por el
método del círculo. No hay nada de esto en el proyecto todavía porque los
demás torneos (Nacional, LPF, B Metro) arrancan con un fixture.csv ya
armado a mano/scrapeado; el Federal A recién empieza y su fixture de
Primera Fase (37 clubes en 4 zonas, ida y vuelta) hay que generarlo.

Uso típico:
    partidos = generar_fixture_ida_vuelta(["A", "B", "C", "D", "E"])
    # -> lista de PartidoFixture(jornada, local, visitante)
"""
from __future__ import annotations

from dataclasses import dataclass

BYE = "__BYE__"  # equipo ficticio para el que descansa cuando la zona es impar


@dataclass(frozen=True)
class PartidoFixture:
    """Un partido programado (sin resultado todavía)."""
    jornada: int
    equipo_local: str
    equipo_visitante: str


def generar_fixture_una_rueda(equipos: list[str], jornada_inicial: int = 1) -> list[PartidoFixture]:
    """Arma una rueda simple (todos contra todos una vez) por el método
    del círculo. Con cantidad impar de equipos se agrega un descanso (BYE)
    rotativo, que se descarta del resultado final.

    Devuelve las jornadas en un orden fijo (no aleatorio) para que el
    fixture sea reproducible: dado el mismo `equipos`, siempre arma el
    mismo calendario.
    """
    if len(equipos) < 2:
        raise ValueError("Se necesitan al menos 2 equipos para armar un fixture")

    lista = list(equipos)
    tiene_bye = len(lista) % 2 == 1
    if tiene_bye:
        lista.append(BYE)

    n = len(lista)
    n_jornadas = n - 1
    mitad = n // 2

    fijo = lista[0]
    rotables = lista[1:]

    partidos: list[PartidoFixture] = []
    for j in range(n_jornadas):
        ronda = [fijo] + rotables
        for i in range(mitad):
            local, visitante = ronda[i], ronda[n - 1 - i]
            if BYE in (local, visitante):
                continue
            # Alterna quién es local entre jornadas para no favorecer
            # siempre al mismo lado en los cruces que le tocan al equipo fijo.
            if j % 2 == 1:
                local, visitante = visitante, local
            partidos.append(PartidoFixture(jornada_inicial + j, local, visitante))
        rotables = [rotables[-1]] + rotables[:-1]  # rota todos menos el fijo

    return partidos


def generar_fixture_ida_vuelta(equipos: list[str], jornada_inicial: int = 1) -> list[PartidoFixture]:
    """Rueda de ida (generar_fixture_una_rueda) + rueda de vuelta con
    local/visitante invertidos, continuando la numeración de jornadas."""
    ida = generar_fixture_una_rueda(equipos, jornada_inicial)
    n_jornadas_ida = max(p.jornada for p in ida) - jornada_inicial + 1
    vuelta = [
        PartidoFixture(p.jornada + n_jornadas_ida, p.equipo_visitante, p.equipo_local)
        for p in ida
    ]
    return ida + vuelta
