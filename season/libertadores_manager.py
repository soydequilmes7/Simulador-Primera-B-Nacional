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
    Modo Temporada, combinando los cupos locales reales de la
    temporada con una rotación aleatoria del pool internacional.

    quotas_pais/cupos_local son parámetros de instancia (no constantes
    del módulo) a propósito: season/sudamericana_temporada.py reusa
    esta MISMA clase con sus propias cuotas en vez de duplicar toda la
    lógica de armado -- ver ese módulo. Default: los de Libertadores
    (QUOTAS_PAIS/CUPOS_ARGENTINA de este módulo)."""

    def __init__(self, pool: list[ClubInternacional] | None = None,
                 quotas_pais: dict[str, int] | None = None,
                 cupos_local: int | None = None):
        self.pool = pool if pool is not None else cargar_pool_internacional()
        self.quotas_pais = quotas_pais if quotas_pais is not None else QUOTAS_PAIS
        self.cupos_local = cupos_local if cupos_local is not None else CUPOS_ARGENTINA

    def armar_clasificacion(
        self,
        clasificados_locales: list[str],
        elo_locales: dict[str, float] | None = None,
        rng: random.Random | None = None,
        excluir: set[str] | None = None,
    ) -> ClasificacionLibertadores:
        """clasificados_locales: los hasta cupos_local nombres que
        devuelve QualificationManager.calcular() de la propia
        temporada (ya viene con el reglamento real de cascada
        aplicado, ver ese módulo -- acá no se revalida nada de eso).

        elo_locales: Elo opcional por club local (si no se pasa, se
        usa un valor genérico -- ver DEFAULT_ELO_ARGENTINO). Pensado
        para engancharse más adelante con season/rating_carryover.py
        si se quiere Elo real de LPF.

        excluir: nombres de equipo a sacar del pool ANTES de elegir --
        pensado para que un mismo club no termine jugando Libertadores
        Y Sudamericana la misma temporada (ver
        season/sudamericana_temporada.py, que arma la clasificación de
        Sudamericana pasando como excluir los equipos que ya sacó
        LibertadoresManager esa temporada)."""
        rng = rng or random.Random()
        elo_locales = elo_locales or {}
        excluir = excluir or set()
        avisos: list[str] = []
        equipos: list[ClubInternacional] = []

        if len(clasificados_locales) > self.cupos_local:
            avisos.append(
                f"Se recibieron {len(clasificados_locales)} clasificados, "
                f"se usan solo los primeros {self.cupos_local}."
            )
        for nombre in clasificados_locales[:self.cupos_local]:
            equipos.append(ClubInternacional(
                equipo=nombre, pais="Argentina",
                elo=elo_locales.get(nombre, DEFAULT_ELO_ARGENTINO),
            ))
        if len(clasificados_locales) < self.cupos_local:
            avisos.append(
                f"Solo hay {len(clasificados_locales)}/{self.cupos_local} clasificados "
                f"disponibles -- la fase de grupos queda con menos de "
                f"{self.cupos_local + sum(self.quotas_pais.values())} equipos."
            )

        pool_por_pais: dict[str, list[ClubInternacional]] = {}
        for club in self.pool:
            if club.equipo in excluir:
                continue
            pool_por_pais.setdefault(club.pais, []).append(club)

        for pais, cupo in self.quotas_pais.items():
            candidatos = pool_por_pais.get(pais, [])
            if len(candidatos) < cupo:
                avisos.append(
                    f"El pool de {pais} tiene {len(candidatos)} equipos disponibles (tras "
                    f"excluir los usados en otra copa) pero la cuota es {cupo} -- se usan "
                    f"todos los disponibles."
                )
            elegidos = candidatos[:] if len(candidatos) <= cupo else rng.sample(candidatos, cupo)
            equipos.extend(elegidos)

        return ClasificacionLibertadores(equipos=equipos, avisos=avisos)


# Elo genérico para un clasificado argentino sin Elo propio cargado --
# valor medio del pool internacional, ni favorito ni underdog (mismo
# criterio que "fuerza neutra" en estadisticas_libertadores.py).
DEFAULT_ELO_ARGENTINO = 1550.0
