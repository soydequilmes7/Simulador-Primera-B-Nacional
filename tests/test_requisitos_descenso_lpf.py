# -*- coding: utf-8 -*-
"""
tests/test_requisitos_descenso_lpf.py

Cubre _texto_requisitos_descenso() de EstadisticasLPF: el desglose del
objetivo de puntos específico para el criterio de descenso por promedios
(distinto del objetivo genérico "evita cualquiera de los dos descensos"),
agregado a pedido de Pablo tras la sesión que completó requisitos_descenso/
requisitos_copas para LPF.
"""
from __future__ import annotations

import unittest

import numpy as np

from modelos.estadisticas_lpf import EstadisticasLPF
from modelos.promotion_requirements import construir_requisitos_ascenso


def _requisitos(puntos_final, umbral):
    n = len(puntos_final)
    victorias = np.zeros(n, dtype=int)
    empates = np.zeros(n, dtype=int)
    derrotas = np.full(n, 10, dtype=int)
    return construir_requisitos_ascenso(
        equipo="Equipo Test", puntos_actuales=20, partidos_restantes=10,
        puntos_final_sims=puntos_final, victorias_restantes_sims=victorias,
        empates_restantes_sims=empates, derrotas_restantes_sims=derrotas,
        asciende_sims=puntos_final >= umbral,
    )


class TextoRequisitosDescensoLPFTests(unittest.TestCase):

    def setUp(self) -> None:
        rng = np.random.default_rng(0)
        self.puntos_final = rng.integers(20, 70, size=1000)

    def test_menciona_objetivo_de_promedios_cuando_difiere_del_generico(self) -> None:
        r_generico = _requisitos(self.puntos_final, umbral=30)
        r_promedios = _requisitos(self.puntos_final, umbral=60)
        self.assertNotEqual(r_generico["targetPoints"], r_promedios["targetPoints"])

        out = EstadisticasLPF._texto_requisitos_descenso(
            "Equipo Test", dict(r_generico),
            pct_desc_promedios=15.0, pct_desc_tabla_anual=3.0, r_promedios=r_promedios,
        )
        self.assertEqual(out["targetPointsPromedios"], r_promedios["targetPoints"])
        self.assertIn("Puntualmente", out["summary"])

    def test_no_repite_el_numero_si_coincide_con_el_generico(self) -> None:
        r_generico = _requisitos(self.puntos_final, umbral=30)
        r_promedios = dict(r_generico)  # mismo objetivo, sin divergencia

        out = EstadisticasLPF._texto_requisitos_descenso(
            "Equipo Test", dict(r_generico),
            pct_desc_promedios=15.0, pct_desc_tabla_anual=3.0, r_promedios=r_promedios,
        )
        self.assertNotIn("Puntualmente", out["summary"])

    def test_sin_riesgo_real_por_promedios_no_agrega_las_claves(self) -> None:
        r_generico = _requisitos(self.puntos_final, umbral=30)
        r_promedios = _requisitos(self.puntos_final, umbral=60)

        out = EstadisticasLPF._texto_requisitos_descenso(
            "Equipo Test", dict(r_generico),
            pct_desc_promedios=0.0, pct_desc_tabla_anual=8.0, r_promedios=r_promedios,
        )
        self.assertNotIn("targetPointsPromedios", out)

    def test_sin_r_promedios_funciona_igual_que_antes(self) -> None:
        r_generico = _requisitos(self.puntos_final, umbral=30)
        out = EstadisticasLPF._texto_requisitos_descenso(
            "Equipo Test", dict(r_generico),
            pct_desc_promedios=15.0, pct_desc_tabla_anual=3.0,
        )
        self.assertNotIn("targetPointsPromedios", out)
        self.assertIn("Según las simulaciones", out["summary"])

    def test_ningun_escenario_exitoso_no_rompe(self) -> None:
        puntos_final = np.full(100, 10)  # nunca llega al umbral
        r_generico = _requisitos(puntos_final, umbral=90)
        self.assertIsNone(r_generico["targetPoints"])

        out = EstadisticasLPF._texto_requisitos_descenso(
            "Equipo Test", dict(r_generico), pct_desc_promedios=40.0, pct_desc_tabla_anual=10.0,
        )
        self.assertIn("no logra evitar el descenso", out["summary"])


if __name__ == "__main__":
    unittest.main()
