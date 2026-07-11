# -*- coding: utf-8 -*-
"""
season/libertadores_manager.py

Arma los 32 clasificados a la fase de grupos de Copa Libertadores para
UNA temporada de Modo Temporada: los 6 cupos argentinos son dinámicos
(salen de QualificationManager.calcular()["libertadores"] de la propia
temporada, ver season/qualification_manager.py) y los 26 cupos
internacionales rotan cada temporada por sorteo simple sobre un pool
fijo de candidatos por país (datos/libertadores_pool_internacional.csv),
respetando la cuota real de cada país.

Por qué rotar y no simular las 9 ligas extranjeras: modelar el
campeonato completo de Brasil/Uruguay/Chile/etc. está fuera de alcance
(el proyecto no tiene datos de esas ligas). Rotar al azar dentro de un
pool de clubes reales (los que jugaron alguna Libertadores/Sudamericana
reciente, ver el pool) da variedad temporada a temporada sin pretender
una precisión que no se puede sostener con los datos disponibles.

Cuotas usadas (suman 32, ver docstring de QUOTAS_PAIS más abajo para
la fuente): Argentina 6 (dinámico), Brasil 6, Uruguay 3, Colombia 4,
Ecuador 3, Perú 3, Chile 2, Paraguay 2, Bolivia 2, Venezuela 1.
"""
from __future__ import annotations

import csv
import random
from dataclasses import dataclass, field

import rutas

# Cuota de cupos en la fase de grupos por país, sin contar Argentina
# (esos 6 salen de QualificationManager). Aproximación de los cupos
# reales de la Copa Libertadores 2026 (ver Anexo:Equipos participantes
# en la Copa Libertadores 2026, Wikipedia), simplificando las fases
# previas: acá se salta directo a los 32 de grupos.
QUOTAS_PAIS: dict[str, int] = {
    "Brasil": 6,
    "Uruguay": 3,
    "Colombia": 4,
    "Ecuador": 3,
    "Peru": 3,
    "Chile": 2,
    "Paraguay": 2,
    "Bolivia": 2,
    "Venezuela": 1,
}
CUPOS_ARGENTINA = 6
CANTIDAD_TOTAL = CUPOS_ARGENTINA + sum(QUOTAS_PAIS.values())  # 32


@dataclass
class ClubInternacional:
    """Un club del pool internacional con su Elo de referencia."""
    equipo: str
    pais: str
    elo: float


@dataclass
class ClasificacionLibertadores:
    """Los 32 clasificados de una temporada, ya con Elo asignado --
    listo para pasarle a LibertadoresSorteo (ver
    season/libertadores_sorteo.py)."""
    equipos: list[ClubInternacional] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    def elo_por_equipo(self) -> dict[str, float]:
        return {c.equipo: c.elo for c in self.equipos}


def cargar_pool_internacional(ruta: str | None = None) -> list[ClubInternacional]:
    """Lee datos/libertadores_pool_internacional.csv. `ruta` es
    opcional, pensado para tests (pasar un CSV de prueba en vez del
    real)."""
    ruta = ruta or str(rutas.datos_dir() / "libertadores_pool_internacional.csv")
    with open(ruta, encoding="utf-8") as f:
        return [
            ClubInternacional(equipo=fila["equipo"], pais=fila["pais"], elo=float(fila["elo"]))
            for fila in csv.DictReader(f)
        ]


class LibertadoresManager:
    """Arma la clasificación completa (32 equipos) de una temporada de
    Modo Temporada, combinando los cupos argentinos reales de la
    temporada con una rotación aleatoria del pool internacional."""

    def __init__(self, pool: list[ClubInternacional] | None = None):
        self.pool = pool if pool is not None else cargar_pool_internacional()

    def armar_clasificacion(
        self,
        clasificados_argentinos: list[str],
        elo_argentinos: dict[str, float] | None = None,
        rng: random.Random | None = None,
    ) -> ClasificacionLibertadores:
        """clasificados_argentinos: los hasta 6 nombres que devuelve
        QualificationManager.calcular()["libertadores"] de la propia
        temporada (ya viene con el reglamento real de cascada
        aplicado, ver ese módulo -- acá no se revalida nada de eso).

        elo_argentinos: Elo opcional por club argentino (si no se
        pasa, se usa un valor genérico -- ver DEFAULT_ELO_ARGENTINO).
        Pensado para engancharse más adelante con
        season/rating_carryover.py si se quiere Elo real de LPF.
        """
        rng = rng or random.Random()
        elo_argentinos = elo_argentinos or {}
        avisos: list[str] = []
        equipos: list[ClubInternacional] = []

        if len(clasificados_argentinos) > CUPOS_ARGENTINA:
            avisos.append(
                f"Se recibieron {len(clasificados_argentinos)} clasificados argentinos, "
                f"se usan solo los primeros {CUPOS_ARGENTINA}."
            )
        for nombre in clasificados_argentinos[:CUPOS_ARGENTINA]:
            equipos.append(ClubInternacional(
                equipo=nombre, pais="Argentina",
                elo=elo_argentinos.get(nombre, DEFAULT_ELO_ARGENTINO),
            ))
        if len(clasificados_argentinos) < CUPOS_ARGENTINA:
            avisos.append(
                f"Solo hay {len(clasificados_argentinos)}/{CUPOS_ARGENTINA} clasificados "
                f"argentinos disponibles -- la fase de grupos queda con menos de 32 equipos."
            )

        pool_por_pais: dict[str, list[ClubInternacional]] = {}
        for club in self.pool:
            pool_por_pais.setdefault(club.pais, []).append(club)

        for pais, cupo in QUOTAS_PAIS.items():
            candidatos = pool_por_pais.get(pais, [])
            if len(candidatos) < cupo:
                avisos.append(
                    f"El pool de {pais} tiene {len(candidatos)} equipos pero la cuota es "
                    f"{cupo} -- se usan todos los disponibles."
                )
            elegidos = candidatos[:] if len(candidatos) <= cupo else rng.sample(candidatos, cupo)
            equipos.extend(elegidos)

        return ClasificacionLibertadores(equipos=equipos, avisos=avisos)


# Elo genérico para un clasificado argentino sin Elo propio cargado --
# valor medio del pool internacional, ni favorito ni underdog (mismo
# criterio que "fuerza neutra" en estadisticas_libertadores.py).
DEFAULT_ELO_ARGENTINO = 1550.0
