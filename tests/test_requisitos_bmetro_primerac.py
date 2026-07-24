# -*- coding: utf-8 -*-
"""
tests/test_requisitos_bmetro_primerac.py

Cubre los textos de "¿Qué necesita [Equipo]?" agregados a B Metropolitana
(EstadisticasBMetro._texto_requisitos_descenso) y Primera C
(estadisticas_primerac.Estadisticas._texto_requisitos_riesgo_ultimo).
construir_requisitos_ascenso() en sí ya está cubierto por
tests/test_requisitos_descenso_lpf.py -- acá solo se testea la parte
específica de cada liga: la redacción del summary.
"""
from __future__ import annotations

import unittest

import numpy as np

from modelos.promotion_requirements import construir_requisitos_ascenso
from modelos.estadisticas_bmetro import EstadisticasBMetro
from modelos.estadisticas_primerac import Estadisticas as EstadisticasPrimeraC


def _requisitos(puntos_final, umbral):
    n = len(puntos_final)
    victorias = np.zeros(n, dtype=int)
    empates = np.zeros(n, dtype=int)
    derrotas = np.full(n, 10, dtype=int)
    return construir_requisitos_ascenso(
        equipo="Equipo Test", puntos_actuales=15, partidos_restantes=10,
        puntos_final_sims=puntos_final, victorias_restantes_sims=victorias,
        empates_restantes_sims=empates, derrotas_restantes_sims=derrotas,
        asciende_sims=puntos_final >= umbral,
    )


class TextoRequisitosDescensoBMetroTests(unittest.TestCase):

    def setUp(self) -> None:
        rng = np.random.default_rng(1)
        self.puntos_final = rng.integers(15, 65, size=500)

    def test_summary_menciona_permanencia_cuando_hay_escenarios_exitosos(self) -> None:
        r = _requisitos(self.puntos_final, umbral=25)
        out = EstadisticasBMetro._texto_requisitos_descenso("Equipo Test", dict(r))
        self.assertIn("permanencia", out["summary"])
        self.assertIn(str(r["targetPoints"]), out["summary"])

    def test_summary_sin_escenarios_exitosos_no_rompe(self) -> None:
        r = _requisitos(self.puntos_final, umbral=1000)  # ningún sim llega
        self.assertIsNone(r["targetPoints"])
        out = EstadisticasBMetro._texto_requisitos_descenso("Equipo Test", dict(r))
        self.assertIn("no logra evitar el descenso", out["summary"])


class TextoRequisitosRiesgoUltimoPrimeraCTests(unittest.TestCase):

    def setUp(self) -> None:
        rng = np.random.default_rng(2)
        self.puntos_final = rng.integers(15, 65, size=500)

    def test_summary_menciona_suspension_de_afiliacion(self) -> None:
        r = _requisitos(self.puntos_final, umbral=25)
        out = EstadisticasPrimeraC._texto_requisitos_riesgo_ultimo("Equipo Test", dict(r))
        self.assertIn("Suspensión de Afiliación", out["summary"])
        self.assertIn(str(r["targetPoints"]), out["summary"])

    def test_summary_sin_escenarios_exitosos_no_rompe(self) -> None:
        r = _requisitos(self.puntos_final, umbral=1000)
        self.assertIsNone(r["targetPoints"])
        out = EstadisticasPrimeraC._texto_requisitos_riesgo_ultimo("Equipo Test", dict(r))
        self.assertIn("no logra evitar terminar último", out["summary"])


if __name__ == "__main__":
    unittest.main()
