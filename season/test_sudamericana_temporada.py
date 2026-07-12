# -*- coding: utf-8 -*-
"""
season/test_sudamericana_temporada.py

Cubre el pipeline dinámico de Copa Sudamericana en Modo Temporada
(season/sudamericana_temporada.py): que ningún club juegue las dos
copas la misma temporada, y el caso borde real encontrado durante el
desarrollo -- con varios cupos argentinos repartidos en 8 zonas, la
restricción "sin choque de país" en el cruce Playoffs/Octavos es a
veces imposible de cumplir del todo (no un bug: ver docstring de
_armar_octavos_desde_playoffs), así que hace falta un fallback avisado
en vez de una excepción dura.
"""
from __future__ import annotations

import random
import unittest

from season.libertadores_grupos import simular_temporada_libertadores
from season.sudamericana_temporada import (
    simular_temporada_sudamericana,
    _armar_octavos_desde_playoffs,
    CANTIDAD_TOTAL,
)

ARGENTINOS_LIBERTADORES = ["Boca Juniors", "River Plate", "Racing Club", "Talleres",
                           "Vélez Sarsfield", "Estudiantes de la Plata"]
ARGENTINOS_SUDAMERICANA = ["Independiente", "Huracán", "Argentinos Juniors", "Banfield",
                           "San Lorenzo", "Unión"]


class TestSimularTemporadaSudamericana(unittest.TestCase):
    def test_pipeline_completo_sin_solapar_clubes_con_libertadores(self):
        for seed in range(15):
            rng = random.Random(seed)
            res_lib = simular_temporada_libertadores(ARGENTINOS_LIBERTADORES, rng=rng)
            res_sud = simular_temporada_sudamericana(ARGENTINOS_SUDAMERICANA, res_lib, rng=rng)

            self.assertTrue(res_sud["campeon"])
            self.assertEqual(len(res_sud["zonas"]), 8)
            self.assertEqual(len(res_sud["cuadro_playoffs"]), 8)
            self.assertEqual(len(res_sud["cuadro_octavos"]), 8)

            usados_libertadores = set(res_lib["equipos_internacionales_usados"])
            usados_sudamericana = {
                fila["equipo"] for z in res_sud["zonas"] for fila in z["tabla"]
                if fila["equipo"] not in ARGENTINOS_SUDAMERICANA
            }
            self.assertEqual(
                usados_libertadores & usados_sudamericana, set(),
                f"seed={seed}: un club jugó las dos copas la misma temporada",
            )

    def test_cantidad_total_32(self):
        self.assertEqual(CANTIDAD_TOTAL, 32)


class TestArmarOctavosDesdePlayoffsFallback(unittest.TestCase):
    def test_devuelve_8_llaves_incluso_cuando_la_restriccion_es_imposible(self):
        """Caso extremo real: si TODOS los directos y TODOS los
        posibles rivales de Playoffs son del mismo país, la
        restricción de país es imposible de cumplir en cualquier
        combinación -- tiene que caer al fallback avisado, no romper."""
        primeros = [f"AR_directo_{i}" for i in range(8)]
        cuadro_playoffs = [
            {
                "ronda": "playoffs", "llave": i + 1,
                "equipo_ida_local": f"AR_segundo_{i}", "equipo_vuelta_local": f"AR_tercero_{i}",
            }
            for i in range(8)
        ]
        pais_por_equipo = {f"AR_directo_{i}": "Argentina" for i in range(8)}
        pais_por_equipo.update({f"AR_segundo_{i}": "Argentina" for i in range(8)})
        pais_por_equipo.update({f"AR_tercero_{i}": "Argentina" for i in range(8)})

        filas, aviso = _armar_octavos_desde_playoffs(primeros, cuadro_playoffs, pais_por_equipo)
        self.assertEqual(len(filas), 8)
        self.assertIsNotNone(aviso)

    def test_sin_conflicto_no_genera_aviso(self):
        primeros = [f"P{i}" for i in range(8)]
        cuadro_playoffs = [
            {
                "ronda": "playoffs", "llave": i + 1,
                "equipo_ida_local": f"X{i}", "equipo_vuelta_local": f"Y{i}",
            }
            for i in range(8)
        ]
        pais_por_equipo = {f"P{i}": f"PaisP{i}" for i in range(8)}
        pais_por_equipo.update({f"X{i}": f"PaisX{i}" for i in range(8)})
        pais_por_equipo.update({f"Y{i}": f"PaisY{i}" for i in range(8)})

        filas, aviso = _armar_octavos_desde_playoffs(primeros, cuadro_playoffs, pais_por_equipo)
        self.assertEqual(len(filas), 8)
        self.assertIsNone(aviso)


if __name__ == "__main__":
    unittest.main()
