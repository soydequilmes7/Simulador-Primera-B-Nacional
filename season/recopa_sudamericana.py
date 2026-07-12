# -*- coding: utf-8 -*-
"""
season/recopa_sudamericana.py

Recopa Sudamericana dentro de Modo Temporada: partido único (cancha
neutral, con alargue y penales si hace falta) entre el campeón de la
Copa Libertadores y el campeón de la Copa Sudamericana de la MISMA
temporada simulada.

Reusa EstadisticasLibertadores.jugar_final_ascenso() (heredado de
Estadisticas, ver modelos/estadisticas.py) -- el mismo motor de
partido único a cancha neutral que ya usan las finales de ascenso de
Primera Nacional/Primera C y la final de la propia Copa Libertadores/
Sudamericana. No reimplementa lógica de simulación.

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
    """Devuelve {"local", "visitante", "golesLocal", "golesVisitante",
    "avanza", "penales", "texto"} con el campeón de Libertadores como
    "local" (cancha neutral: la etiqueta es solo para reusar el mismo
    shape que matchHTML() ya sabe pintar en el frontend, no implica
    localía real). None si falta el campeón de alguna de las dos copas
    o su Elo (temporada con error/incompleta) -- criterio no bloqueante,
    igual que el resto de las copas internacionales.
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
    ganador, _perdedor, detalle = motor.jugar_final_ascenso(campeon_libertadores, campeon_sudamericana)

    return {
        "local": campeon_libertadores,
        "visitante": campeon_sudamericana,
        "golesLocal": detalle["marcador"][0],
        "golesVisitante": detalle["marcador"][1],
        "avanza": ganador,
        "penales": "penales" in detalle["texto"] or None,
        "texto": detalle["texto"],
    }
