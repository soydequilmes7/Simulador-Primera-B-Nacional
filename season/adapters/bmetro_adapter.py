# -*- coding: utf-8 -*-
"""
season/adapters/bmetro_adapter.py

Adaptador de la Primera B Metropolitana (BMetro) para el SeasonEngine.
Envuelve main_bmetro.correr_simulacion_bmetro() tal cual (no se toca
el motor) y traduce su dict de salida al shape común ResultadoTorneo.

Mapeo (ver PLAN_MODO_TEMPORADA_NACIONAL.txt, sección 3 y 4):

  correr_simulacion_bmetro() -> dict con tabla (única, sin zonas),
  puntero_ascenso_directo, reducido, campeon_reducido, descensos.

DIFERENCIA con Nacional/Primera C: ahí el campeón del reducido queda
anidado en reducido["final"]["campeon"]; acá campeon_reducido es una
clave de PRIMER NIVEL en datos_web (main_bmetro.py la expone directo,
no hace falta bucear dentro de "reducido").

Decisiones de diseño para este adaptador:

  1. ResultadoTorneo.ascensos = [puntero_ascenso_directo,
     campeon_reducido]. Esto está anotado tal cual en la sección 4
     del plan ("BMetro: puntero_ascenso_directo + campeon_reducido").

  2. ResultadoTorneo.campeon = puntero_ascenso_directo. BMetro no
     tiene un "campeón" en sentido literal fuera del contexto de
     ascenso -- se sigue el mismo criterio ya usado en NacionalAdapter
     (campeon = final_ascenso.ganador, el ganador del ascenso directo,
     no un campeón de la categoría). PROPUESTO por Claude siguiendo
     ese precedente; pendiente de confirmación explícita del usuario
     (a diferencia de LPF/Nacional, donde este punto específico para
     BMetro no había quedado documentado como "confirmado con el
     usuario" en el plan).

  3. ResultadoTorneo.descensos = datos_web["descensos"] tal cual
     (calcular_descensos() ya devuelve los últimos DESCENSOS_N=2 de la
     tabla, no hace falta traducir nada -- igual que LPF).

  4. ResultadoTorneo.clasificados_copa = [] siempre: BMetro no
     alimenta cupos de Libertadores/Sudamericana (mismo criterio ya
     usado en PrimeraCAdapter).
"""

import main_bmetro
from season.tournament_adapter import ResultadoTorneo, TournamentEngine


class BMetroAdapter(TournamentEngine):

    def __init__(self):
        self._datos_web = None

    def setup(self, **kwargs):
        # main_bmetro.correr_simulacion_bmetro() lee sus propios CSV vía
        # data_access.league_data("bmetro"); no necesita nada externo
        # todavía (ver nota en TournamentEngine.setup).
        pass

    def run(self, n_sims: int = 1000):
        self._datos_web = main_bmetro.correr_simulacion_bmetro(
            n_sims=n_sims, imprimir=False, guardar_json=False
        )

    def run_desde_carryover(self, roster: list, club_registry, resultados_anterior: dict) -> ResultadoTorneo:
        """Fase 3 de HANDOFF_carryover_ratings.md -- análogo a
        NacionalAdapter.run_desde_carryover() (ver su docstring):
        reemplaza a run()+result() SOLO para una temporada de Modo
        Temporada recién generada, sin pasar por main_bmetro.py. Ver
        season/carryover_engines/bmetro.py para el motor.

        setup()/run()/result() (el camino de siempre) quedan sin
        ningún cambio.

        roster: la temporada siguiente ya armada (ver
            ClubRegistry.get_by_division("Primera B Metropolitana")).
            B Metro es zona única -- no hace falta zona_por_club acá.
        club_registry: para leer Club.history de los que continúan.
        resultados_anterior: dict[str, ResultadoTorneo] de la
            temporada QUE TERMINA (se leen "bmetro"/"nacional"/
            "primerac" si están -- ver
            carryover_engines.bmetro.armar_ratings_iniciales())."""
        from season.carryover_engines import bmetro as motor_carryover

        ratings_iniciales = motor_carryover.armar_ratings_iniciales(
            club_registry, resultados_anterior, roster
        )
        return motor_carryover.correr_temporada_desde_carryover(roster, ratings_iniciales)

    def result(self) -> ResultadoTorneo:
        if self._datos_web is None:
            raise RuntimeError("Llamá a run() antes de result().")

        datos_web = self._datos_web
        ascenso_directo = datos_web["puntero_ascenso_directo"]
        ascenso_reducido = datos_web["campeon_reducido"]

        return ResultadoTorneo(
            campeon=ascenso_directo,
            ascensos=[ascenso_directo, ascenso_reducido],
            descensos=datos_web["descensos"],
            clasificados_copa=[],
            datos_crudos=datos_web,
        )
