# -*- coding: utf-8 -*-
"""
tests/test_sincronizar_fixture_clausura_lpf.py

Cubre calcular_filas_nuevas() (sincronizar_fixture_clausura_lpf.py):
caso real reportado por Pablo (22/07/2026 -- 9 partidos sin identificar
en LPF, Clausura arrancó con las mismas parejas de equipos y la misma
numeración de "Fecha N" que usó el Apertura, ver docstring del módulo).
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from sincronizar_fixture_clausura_lpf import calcular_filas_nuevas


def _pendiente(jornada, local, visitante):
    return {"fecha": "", "jornada": jornada, "equipo_local": local, "equipo_visitante": visitante}


def _promiedos(jornada, local, visitante, jugado):
    return {
        "jornada": jornada, "equipo_local": local, "equipo_visitante": visitante,
        "jugado": jugado, "goles_local": 1 if jugado else None, "goles_visitante": 0 if jugado else None,
        "estado": "", "fecha_hora": "",
    }


class CalcularFilasNuevasTests(unittest.TestCase):

    def test_caso_real_clausura_mismo_par_que_apertura(self) -> None:
        # El Apertura ya jugó Fecha 1 (Sarmiento Junín vs Argentinos
        # Juniors) hace meses -- está en "jugados", no en "pending".
        jugados_actual = [_pendiente(1, "Sarmiento Junín", "Argentinos Juniors")]
        pending_actual = []  # Apertura ya se jugó completo, no queda nada pendiente

        # Promiedos ahora reporta la MISMA pareja como pendiente (jugado=False
        # todavía) bajo "Fecha 1" otra vez -- es el Clausura.
        with patch("sincronizar_fixture_clausura_lpf.obtener_partidos_lpf",
                   return_value=[_promiedos(1, "Sarmiento Junín", "Argentinos Juniors", jugado=False)]):
            filas_nuevas, offset = calcular_filas_nuevas(pending_actual, jugados_actual)

        self.assertEqual(offset, 1)  # jornada máxima ya usada (por el Apertura jugado)
        self.assertEqual(len(filas_nuevas), 1)
        self.assertEqual(filas_nuevas[0]["jornada"], 2)  # offset(1) + jornada de Promiedos(1)
        self.assertEqual(filas_nuevas[0]["equipo_local"], "Sarmiento Junín")
        self.assertEqual(filas_nuevas[0]["equipo_visitante"], "Argentinos Juniors")

    def test_partido_ya_jugado_en_promiedos_no_se_agrega(self) -> None:
        # Si Promiedos ya lo tiene como jugado, ese es trabajo de
        # actualizar_resultados_lpf.py, no de este script.
        with patch("sincronizar_fixture_clausura_lpf.obtener_partidos_lpf",
                   return_value=[_promiedos(1, "Boca Juniors", "River Plate", jugado=True)]):
            filas_nuevas, _ = calcular_filas_nuevas([], [])
        self.assertEqual(filas_nuevas, [])

    def test_partido_ya_en_fixture_pendiente_no_se_duplica(self) -> None:
        # Idempotencia: correr el script dos veces no debe duplicar filas.
        pending_actual = [_pendiente(2, "Sarmiento Junín", "Argentinos Juniors")]
        with patch("sincronizar_fixture_clausura_lpf.obtener_partidos_lpf",
                   return_value=[_promiedos(1, "Sarmiento Junín", "Argentinos Juniors", jugado=False)]):
            filas_nuevas, _ = calcular_filas_nuevas(pending_actual, [])
        self.assertEqual(filas_nuevas, [])

    def test_offset_toma_el_maximo_entre_jugados_y_pendientes(self) -> None:
        jugados_actual = [_pendiente(14, "Boca Juniors", "River Plate")]
        pending_actual = [_pendiente(16, "Talleres de Córdoba", "Instituto")]  # remanente Apertura sin jugar
        with patch("sincronizar_fixture_clausura_lpf.obtener_partidos_lpf",
                   return_value=[_promiedos(1, "Huracán", "Banfield", jugado=False)]):
            filas_nuevas, offset = calcular_filas_nuevas(pending_actual, jugados_actual)
        self.assertEqual(offset, 16)  # el máximo de los dos, no solo de jugados
        self.assertEqual(filas_nuevas[0]["jornada"], 17)

    def test_resuelve_nombres_no_canonicos_de_promiedos(self) -> None:
        # Si Promiedos manda el nombre corto en vez del canónico de
        # fixture_lpf.csv, resolver_equipo_lpf lo normaliza.
        with patch("sincronizar_fixture_clausura_lpf.obtener_partidos_lpf",
                   return_value=[_promiedos(1, "River", "Racing", jugado=False)]):
            filas_nuevas, _ = calcular_filas_nuevas([], [])
        self.assertEqual(filas_nuevas[0]["equipo_local"], "River Plate")
        self.assertEqual(filas_nuevas[0]["equipo_visitante"], "Racing Club")


if __name__ == "__main__":
    unittest.main()
