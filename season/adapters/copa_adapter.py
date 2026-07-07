# -*- coding: utf-8 -*-
"""
season/adapters/copa_adapter.py

Adaptador de la Copa Argentina para el SeasonEngine. Envuelve
main_copa.correr_simulacion_copa() tal cual (no se toca el motor) y
traduce su dict de salida al shape común ResultadoTorneo.

Shape de datos_web CONFIRMADO leyendo main_copa.py directo (no
supuesto): correr_simulacion_copa() devuelve

    {
      "liga": "Copa Argentina", "generado": ..., "n_simulaciones": ...,
      "rondas": {...},          # detalle por ronda, no se usa acá
      "campeon": <nombre del club>,
      "monte_carlo": [...], "equipos_vivos": [...],
    }

OJO CON LA FIRMA: a diferencia del resto de los main_X.correr_
simulacion*(), acá el orden de kwargs es
correr_simulacion_copa(imprimir=True, guardar_json=True, n_sims=1000)
-- n_sims va AL FINAL, no primero. El adaptador pasa todo por keyword
para no depender del orden posicional.

La Copa Argentina NO es una división del sistema de ascenso/descenso
(es un torneo paralelo de eliminación directa entre clubes de
distintas categorías) -- por eso ResultadoTorneo.ascensos y
.descensos son [] siempre, a diferencia de los adaptadores de las
6 ligas.

Decisión de diseño para este adaptador (PROPUESTA por Claude,
pendiente de confirmación explícita del usuario -- ver
PLAN_MODO_TEMPORADA_NACIONAL.txt, sección 4):

  ResultadoTorneo.clasificados_copa = [campeon]. El campeón de la Copa
  Argentina se clasifica a la Copa Libertadores por reglamento (es el
  cupo "ARGENTINA 3" que LPFAdapter filtra como placeholder "no
  simulado" -- ver docstring de lpf_adapter.py). QualificationManager
  (Etapa 4) va a necesitar este dato para completar el cupo que LPF
  deja como texto genérico. Si el usuario prefiere que
  QualificationManager tome el campeón directamente de
  ResultadoTorneo.campeon en vez de duplicarlo también acá en
  clasificados_copa, avisar para simplificar (dejar clasificados_copa
  = [] y que sea SIEMPRE campeon quien se consulte para ese cupo).
"""

import main_copa
from season.tournament_adapter import ResultadoTorneo, TournamentEngine


class CopaAdapter(TournamentEngine):

    def __init__(self):
        self._datos_web = None

    def setup(self, **kwargs):
        # main_copa.correr_simulacion_copa() lee sus propios datos vía
        # data_access.cup_records() (+ _cosechar_ratings_ligas(), que
        # internamente llama a data_access.league_data("lpf")/
        # ("nacional") pero atrapa sus propias excepciones); no
        # necesita nada externo todavía (ver nota en
        # TournamentEngine.setup).
        pass

    def run(self, n_sims: int = 1000):
        self._datos_web = main_copa.correr_simulacion_copa(
            imprimir=False, guardar_json=False, n_sims=n_sims
        )

    def result(self) -> ResultadoTorneo:
        if self._datos_web is None:
            raise RuntimeError("Llamá a run() antes de result().")

        datos_web = self._datos_web
        campeon = datos_web["campeon"]

        return ResultadoTorneo(
            campeon=campeon,
            ascensos=[],
            descensos=[],
            clasificados_copa=[campeon],
            datos_crudos=datos_web,
        )
