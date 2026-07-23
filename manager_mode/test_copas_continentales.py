# -*- coding: utf-8 -*-
"""manager_mode/test_copas_continentales.py

Tests de la simulación simplificada de Libertadores/Sudamericana.
Ejecutar con:
    python -m unittest manager_mode.test_copas_continentales -v
"""
from __future__ import annotations

import random
import unittest

from manager_mode.copas_continentales import (
    FASES,
    CopaContinental,
    ResultadoCopaContinental,
    aplicar_resultado_copa,
    simular_copa_continental,
)
from manager_mode.dirigencia import CATALOGO_PERFILES_CLUB
from manager_mode.domain import Entrenador, IdentidadTactica


class TestSimularCopaContinental(unittest.TestCase):
    def test_club_sin_clasificacion_lanza_value_error(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.PRAGMATICO)
        quilmes = CATALOGO_PERFILES_CLUB["Quilmes"]
        with self.assertRaises(ValueError):
            simular_copa_continental(entrenador, quilmes, CopaContinental.LIBERTADORES, random.Random(1))

    def test_river_puede_salir_campeon(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.OFENSIVO, reputacion=90.0)
        river = CATALOGO_PERFILES_CLUB["River"]
        rng = random.Random(7)
        resultados = [
            simular_copa_continental(entrenador, river, CopaContinental.LIBERTADORES, rng)
            for _ in range(300)
        ]
        self.assertTrue(any(r.campeon for r in resultados))

    def test_fase_alcanzada_es_campeon_si_y_solo_si_campeon_true(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.OFENSIVO, reputacion=90.0)
        river = CATALOGO_PERFILES_CLUB["River"]
        rng = random.Random(3)
        for _ in range(100):
            resultado = simular_copa_continental(entrenador, river, CopaContinental.SUDAMERICANA, rng)
            self.assertEqual(resultado.campeon, resultado.fase_alcanzada == "campeon")

    def test_mayor_reputacion_avanza_en_promedio_mas_lejos(self) -> None:
        river = CATALOGO_PERFILES_CLUB["River"]

        def indice_fase(entrenador: Entrenador, rng: random.Random) -> int:
            resultado = simular_copa_continental(entrenador, river, CopaContinental.LIBERTADORES, rng)
            return FASES.index(resultado.fase_alcanzada)

        rng_alta = random.Random(42)
        rng_baja = random.Random(42)
        n = 300
        entrenador_alto = Entrenador(nombre="A", identidad=IdentidadTactica.PRAGMATICO, reputacion=95.0)
        entrenador_bajo = Entrenador(nombre="B", identidad=IdentidadTactica.PRAGMATICO, reputacion=10.0)

        promedio_alto = sum(indice_fase(entrenador_alto, rng_alta) for _ in range(n)) / n
        promedio_bajo = sum(indice_fase(entrenador_bajo, rng_baja) for _ in range(n)) / n
        self.assertGreater(promedio_alto, promedio_bajo)


class TestAplicarResultadoCopa(unittest.TestCase):
    def test_campeon_suma_titulo_y_desbloquea_logro(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.OFENSIVO, reputacion=50.0)
        resultado = ResultadoCopaContinental(
            copa=CopaContinental.LIBERTADORES, fase_alcanzada="campeon", campeon=True,
        )
        aplicar_resultado_copa(entrenador, resultado)
        self.assertIn("campeon_continental", entrenador.logros_desbloqueados)
        self.assertEqual(len(entrenador.titulos), 1)
        self.assertEqual(entrenador.reputacion, 65.0)

    def test_semifinal_sin_ganar_solo_suma_reputacion(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.OFENSIVO, reputacion=50.0)
        resultado = ResultadoCopaContinental(
            copa=CopaContinental.SUDAMERICANA, fase_alcanzada="semifinal", campeon=False,
        )
        aplicar_resultado_copa(entrenador, resultado)
        self.assertEqual(entrenador.titulos, [])
        self.assertEqual(entrenador.reputacion, 53.0)

    def test_eliminacion_en_grupos_no_cambia_nada(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.OFENSIVO, reputacion=50.0)
        resultado = ResultadoCopaContinental(
            copa=CopaContinental.SUDAMERICANA, fase_alcanzada="grupos", campeon=False,
        )
        aplicar_resultado_copa(entrenador, resultado)
        self.assertEqual(entrenador.reputacion, 50.0)


if __name__ == "__main__":
    unittest.main()
