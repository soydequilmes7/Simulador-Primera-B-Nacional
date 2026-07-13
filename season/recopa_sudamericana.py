# -*- coding: utf-8 -*-
"""
season/recopa_sudamericana.py

Recopa Sudamericana dentro de Modo Temporada: a diferencia de las
finales de Copa Libertadores y Copa Sudamericana (partido único a
cancha neutral), la Recopa SÍ se juega a ida y vuelta -- reglamento
CONMEBOL vigente (Reglamento CONMEBOL Recopa 2026, Art. 13: "La
Competición será disputada en dos partidos (IDA y VUELTA). El campeón
de CONMEBOL Libertadores será local en el segundo partido (VUELTA)").
Es decir: el campeón de la Sudamericana abre de local en la ida, el
campeón de la Libertadores cierra de local en la vuelta -- ventaja de
localía para quien ganó la copa "mayor", como en la Recopa real.

Reusa EstadisticasLibertadores.jugar_llave_ida_vuelta() (mismo motor a
dos partidos que ya usan octavos/cuartos/semis de la propia
Libertadores, ver modelos/estadisticas_libertadores.py): sin ventaja
de gol de visitante, alargue en la vuelta y penales si sigue empatado.
No reimplementa lógica de simulación.

Necesita el Elo de ambos campeones, que salen de los resultados YA
CORRIDOS de esta misma temporada:
  - resultado_libertadores["elo_por_equipo"] (ver
    season/libertadores_grupos.py::simular_temporada_libertadores()).
  - resultado_sudamericana["elo_por_equipo"] (ver
    season/sudamericana_temporada.py::simular_temporada_sudamericana()).

Solo tiene sentido llamarla si las dos copas ya corrieron sin error
en esta temporada (ver SeasonEngine.correr_temporada(correr_recopa=...)
y api/index.py, que la invocan solo en ese caso).
"""
from __future__ import annotations

from modelos.estadisticas_libertadores import EstadisticasLibertadores


def simular_recopa(resultado_libertadores: dict, resultado_sudamericana: dict) -> dict | None:
    """Devuelve el mismo shape de llave a ida y vuelta que ya usa el
    resto de la Libertadores (ver jugar_llave_ida_vuelta():
    "ida"/"vuelta"/"agregado"/"penales"/"avanza"), con el campeón de
    Sudamericana como local de la ida y el campeón de Libertadores
    como local de la vuelta (ver docstring del módulo). None si falta
    el campeón de alguna de las dos copas o su Elo (temporada con
    error/incompleta) -- criterio no bloqueante, igual que el resto de
    las copas internacionales.
    """
    campeon_libertadores = resultado_libertadores.get("campeon")
    campeon_sudamericana = resultado_sudamericana.get("campeon")
    if not campeon_libertadores or not campeon_sudamericana:
        return None
    if campeon_libertadores == campeon_sudamericana:
        # No debería pasar (Libertadores y Sudamericana clasifican
        # equipos distintos, ver QualificationManager), pero si algún
        # día colisionan por un dato raro, mejor no jugar la Recopa de
        # un equipo contra sí mismo que romper la temporada.
        return None

    elo_libertadores = (resultado_libertadores.get("elo_por_equipo") or {}).get(campeon_libertadores)
    elo_sudamericana = (resultado_sudamericana.get("elo_por_equipo") or {}).get(campeon_sudamericana)
    if elo_libertadores is None or elo_sudamericana is None:
        return None

    motor = EstadisticasLibertadores()
    motor.crear_equipos_desde_elo(
        {campeon_libertadores, campeon_sudamericana},
        {campeon_libertadores: elo_libertadores, campeon_sudamericana: elo_sudamericana},
    )
    detalle = motor.jugar_llave_ida_vuelta(local_ida=campeon_sudamericana, local_vuelta=campeon_libertadores)
    detalle["campeon_libertadores"] = campeon_libertadores
    detalle["campeon_sudamericana"] = campeon_sudamericana
    return detalle
