# -*- coding: utf-8 -*-
"""
season/adapters/federal_adapter.py

Adaptador del Torneo Federal A para el SeasonEngine. Envuelve
main_federal.correr_simulacion_federal() tal cual (no se toca el
motor, el más complejo de los 6: Primera Fase 4 zonas -> Segunda Fase
2 zonas -> camino principal (3ª/4ª/5ª Fase, eliminación directa) en
paralelo con la Reválida de 6 Etapas) y traduce su dict de salida
(datos_web, armado por _armar_datos_web() en main_federal.py) al
shape común ResultadoTorneo.

Shape de datos_web CONFIRMADO leyendo main_federal.py directo (no
supuesto -- este era el pendiente anotado en el plan, sección 3):

    {
      "liga": "federal_a", "generado": ..., "n_simulaciones": ...,
      "primera_fase": {"tablas": {...}},
      "segunda_fase": {"tablas": {...}},
      "camino_principal": {
          "tercera_fase": {...}, "cuarta_fase": {...},
          "quinta_fase_final": {...},
          "ascenso_1": <nombre del club>,   # resultado_5f.ganador
      },
      "revalida": {
          "primera_etapa": {"tablas": {...}},
          "descensos": [<4 nombres>],       # calcular_descensos(), ya
                                             # devuelve list[str] (2 por
                                             # zona, ver estadisticas_federal.py)
          "segunda_etapa": {...}, "tercera_etapa": {...},
          "cuarta_etapa": {...}, "quinta_etapa": {...},
          "sexta_etapa_final": {...},
          "ascenso_2": <nombre del club>,   # resultado_r6.ganador
      },
      "monte_carlo": [...], "rachas": {...},
    }

Decisiones de diseño para este adaptador (mismo criterio ya usado en
NacionalAdapter/PrimeraCAdapter/BMetroAdapter -- dos vías de ascenso,
una "directa"/camino principal y una de repechaje):

  1. ResultadoTorneo.campeon = datos_web["camino_principal"]["ascenso_1"].
     El Federal A no tiene un único "campeón" en sentido literal (es
     una categoría de ascenso, no la máxima categoría): se toma el
     ganador del camino principal (3ª/4ª/5ª Fase), igual que en
     Nacional/Primera C se toma final_ascenso.ganador y en BMetro
     puntero_ascenso_directo. PROPUESTO por Claude siguiendo ese
     precedente; pendiente de confirmación explícita del usuario, como
     ya se marcó para BMetroAdapter.

  2. ResultadoTorneo.ascensos = [ascenso_1, ascenso_2], es decir
     [datos_web["camino_principal"]["ascenso_1"],
      datos_web["revalida"]["ascenso_2"]].

  3. ResultadoTorneo.descensos = datos_web["revalida"]["descensos"]
     tal cual (calcular_descensos() ya devuelve una lista de 4 nombres
     -- 2 por zona de Reválida --, no hace falta traducir nada).

  4. ResultadoTorneo.clasificados_copa = [] siempre: el Federal A no
     alimenta cupos de Libertadores/Sudamericana (mismo criterio que
     BMetro/Primera C).
"""

import main_federal
from season.tournament_adapter import ResultadoTorneo, TournamentEngine


class FederalAdapter(TournamentEngine):

    def __init__(self):
        self._datos_web = None

    def setup(self, **kwargs):
        # main_federal.correr_simulacion_federal() lee sus propios CSV
        # vía data_access.league_data("federal_a"); no necesita nada
        # externo todavía (ver nota en TournamentEngine.setup).
        pass

    def run(self, n_sims: int = 1000):
        self._datos_web = main_federal.correr_simulacion_federal(
            n_sims=n_sims, imprimir=False, guardar_json=False
        )

    def run_desde_carryover(
        self, roster: list, zona_por_club: dict, club_registry, resultados_anterior: dict,
    ) -> ResultadoTorneo:
        """Fase 5 de HANDOFF_carryover_ratings.md -- análogo a
        NacionalAdapter.run_desde_carryover() (ver su docstring):
        reemplaza a run()+result() SOLO para una temporada de Modo
        Temporada recién generada, sin pasar por main_federal.py. Ver
        season/carryover_engines/federal.py para el motor (5 Fases +
        Reválida de 6 Etapas, reproducidas sin tocar una línea de
        modelos/estadisticas_federal.py).

        setup()/run()/result() (el camino de siempre) quedan sin
        ningún cambio.

        roster: 37 clubes de Federal A (después de PromotionManager).
        zona_por_club: {equipo: "1"|"2"|"3"|"4"} -- mismo sorteo de
            4 zonas que usa HistoryManager (_sortear_zonas_n)."""
        from season.carryover_engines import federal as motor_carryover

        ratings_iniciales = motor_carryover.armar_ratings_iniciales(
            club_registry, resultados_anterior, roster
        )
        return motor_carryover.correr_temporada_desde_carryover(
            roster, zona_por_club, ratings_iniciales
        )

    def result(self) -> ResultadoTorneo:
        if self._datos_web is None:
            raise RuntimeError("Llamá a run() antes de result().")

        datos_web = self._datos_web
        ascenso_1 = datos_web["camino_principal"]["ascenso_1"]
        ascenso_2 = datos_web["revalida"]["ascenso_2"]
        descensos = datos_web["revalida"]["descensos"]

        return ResultadoTorneo(
            campeon=ascenso_1,
            ascensos=[ascenso_1, ascenso_2],
            descensos=descensos,
            clasificados_copa=[],
            datos_crudos=datos_web,
        )
