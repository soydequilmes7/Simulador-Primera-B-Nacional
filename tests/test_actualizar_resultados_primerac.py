# -*- coding: utf-8 -*-
"""
tests/test_actualizar_resultados_primerac.py

Cubre _clasificar_partidos_primerac() (actualizar_resultados_primerac.py):
matching de partidos jugados (Promiedos) contra el fixture pendiente,
incluido el fallback de swap local/visitante agregado tras el caso real
reportado por Pablo (22/07/2026: Fecha 20 Puerto Nuevo vs CA Fenix
guardado en Supabase como CA Fenix vs Puerto Nuevo).
"""
from __future__ import annotations

import unittest

from actualizar_resultados_primerac import _clasificar_partidos_primerac


def _fixture(jornada: int, local: str, visitante: str) -> dict:
    return {"fecha": "", "jornada": jornada, "equipo_local": local, "equipo_visitante": visitante}


def _jugado(jornada: int, local: str, visitante: str, gl: int, gv: int) -> dict:
    return {
        "jornada": jornada, "equipo_local": local, "equipo_visitante": visitante,
        "goles_local": gl, "goles_visitante": gv,
    }


class ClasificarPartidosPrimeraCTests(unittest.TestCase):

    def test_matchea_partido_en_el_mismo_orden(self) -> None:
        fixture = [_fixture(20, "Puerto Nuevo", "CA Fenix")]
        jugados = [_jugado(20, "Puerto Nuevo", "CA Fenix", 0, 1)]

        fixture_restante, resultados, cargados, elo_cargados, sin_matchear, swaps = \
            _clasificar_partidos_primerac(jugados, fixture, [])

        self.assertEqual(fixture_restante, [])
        self.assertEqual(len(cargados), 1)
        self.assertEqual(len(resultados), 1)
        self.assertEqual(sin_matchear, [])
        self.assertEqual(swaps, [])

    def test_detecta_y_carga_swap_de_local_visitante(self) -> None:
        # Caso real: fixture guardado con CA Fenix de local, pero Promiedos
        # ahora reporta el partido con Puerto Nuevo de local (reprogramación
        # de cancha) -- antes de este fix quedaba "sin_matchear".
        fixture = [_fixture(20, "CA Fenix", "Puerto Nuevo")]
        jugados = [_jugado(20, "Puerto Nuevo", "CA Fenix", 0, 1)]

        fixture_restante, resultados, cargados, elo_cargados, sin_matchear, swaps = \
            _clasificar_partidos_primerac(jugados, fixture, [])

        self.assertEqual(fixture_restante, [])
        self.assertEqual(sin_matchear, [])
        self.assertEqual(len(cargados), 1)
        self.assertEqual(len(swaps), 1)
        self.assertEqual(swaps[0]["jornada"], 20)
        # El resultado cargado respeta el orden REAL (el que jugaron), no
        # el que tenía guardado el fixture viejo.
        self.assertEqual(resultados[0]["equipo_local"], "Puerto Nuevo")
        self.assertEqual(resultados[0]["equipo_visitante"], "CA Fenix")

    def test_no_confunde_partido_de_ida_con_el_de_vuelta(self) -> None:
        # Mismos dos equipos, jornadas distintas (ida y vuelta) -- el
        # fallback de swap exige la MISMA jornada para no matchear el
        # partido equivocado.
        fixture = [
            _fixture(4, "CA Fenix", "Puerto Nuevo"),   # ida, ya jugada (no debería tocarse)
            _fixture(20, "Puerto Nuevo", "CA Fenix"),  # vuelta, pendiente
        ]
        jugados = [_jugado(20, "Puerto Nuevo", "CA Fenix", 2, 0)]

        fixture_restante, resultados, cargados, elo_cargados, sin_matchear, swaps = \
            _clasificar_partidos_primerac(jugados, fixture, [])

        self.assertEqual(len(cargados), 1)
        self.assertEqual(swaps, [])  # matcheó directo, sin necesitar el fallback
        # La fila de la ida (jornada 4) sigue intacta en el fixture restante.
        self.assertEqual(len(fixture_restante), 1)
        self.assertEqual(fixture_restante[0]["jornada"], 4)

    def test_partido_ya_cargado_se_ignora(self) -> None:
        fixture = [_fixture(20, "Puerto Nuevo", "CA Fenix")]
        resultados_previos = [
            {"fecha": "", "jornada": 20, "equipo_local": "Puerto Nuevo",
             "equipo_visitante": "CA Fenix", "goles_local": 0, "goles_visitante": 1},
        ]
        jugados = [_jugado(20, "Puerto Nuevo", "CA Fenix", 0, 1)]

        fixture_restante, resultados, cargados, elo_cargados, sin_matchear, swaps = \
            _clasificar_partidos_primerac(jugados, fixture, resultados_previos)

        self.assertEqual(cargados, [])
        self.assertEqual(sin_matchear, [])
        self.assertEqual(swaps, [])
        # El fixture pendiente no se tocó (el partido ya estaba cargado).
        self.assertEqual(len(fixture_restante), 1)

    def test_partido_realmente_sin_fixture_queda_sin_matchear(self) -> None:
        fixture = [_fixture(20, "Puerto Nuevo", "CA Fenix")]
        jugados = [_jugado(21, "Sacachispas", "Muñiz", 1, 1)]

        fixture_restante, resultados, cargados, elo_cargados, sin_matchear, swaps = \
            _clasificar_partidos_primerac(jugados, fixture, [])

        self.assertEqual(cargados, [])
        self.assertEqual(len(sin_matchear), 1)
        self.assertEqual(swaps, [])
        self.assertEqual(len(fixture_restante), 1)


if __name__ == "__main__":
    unittest.main()
