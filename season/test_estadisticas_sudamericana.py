# -*- coding: utf-8 -*-
"""
season/test_estadisticas_sudamericana.py

Cubre el bug real encontrado al construir Monte Carlo: la primera
llamada a simular_sudamericana() completaba en el CSV cargado en
memoria el lado "equipo_vuelta_local" de cada llave de Octavos con el
ganador de Playoffs de ESA corrida -- pero como la escritura era
permanente (mutaba self.cuadro sin volver a un estado original), las
corridas siguientes ya no jugaban los Playoffs de verdad: quedaban
pegadas al primer resultado, sin importar cuántas veces se llamara de
nuevo. Esto rompía en silencio cualquier Monte Carlo (main_sudamericana.
py::monte_carlo_sudamericana()), porque el %octavos de los equipos de
Playoffs hubiera dado siempre 0% o 100%, nunca un valor intermedio real.
"""
from __future__ import annotations

import unittest

from modelos.estadisticas_sudamericana import EstadisticasSudamericana


class TestSimularSudamericanaNoMutaPermanente(unittest.TestCase):
    def setUp(self):
        self.motor = EstadisticasSudamericana()
        self.motor.cargar_datos_sudamericana()
        self.motor.crear_equipos_sudamericana()

    def test_playoffs_se_vuelven_a_jugar_en_cada_corrida(self):
        """En al menos una de 30 corridas, el lado 'playoffs' de la
        llave 1 de octavos tiene que dar un ganador DISTINTO al de
        otra corrida -- si el bug de mutación permanente estuviera de
        vuelta, siempre daría el mismo (el de la primera corrida)."""
        rivales_vistos = set()
        for _ in range(30):
            rondas, _ = self.motor.simular_sudamericana()
            equipos_llave1 = set(rondas["octavos"][0]["agregado"].keys())
            # El lado "directo" (equipo_ida_local, ver datos/sudamericana_cuadro.csv)
            # es siempre el mismo por diseño -- lo que puede variar es
            # el otro lado (el que sale de Playoffs).
            rivales_vistos |= equipos_llave1

        self.assertGreater(
            len(rivales_vistos), 2,
            "Solo se vio un ganador de playoffs distinto en 30 corridas -- "
            "sospecha de mutación permanente (ver docstring del módulo).",
        )

    def test_datos_reales_del_csv_tienen_prioridad_sobre_lo_simulado(self):
        """Si el CSV ya trajera un ganador real de Playoffs (llave 1
        ya jugada de verdad), simular_sudamericana() NO debería
        pisarlo con un resultado simulado."""
        # Usa un equipo YA conocido por el motor (uno de los propios
        # participantes de la llave 1 de Playoffs) para que
        # crear_equipos_sudamericana() ya le haya asignado Elo -- el
        # punto del test es la prioridad del dato "real" del CSV
        # sobre el simulado, no si el nombre existe en self.equipos.
        equipo_confirmado = self.motor.cuadro_playoffs[0]["equipo_ida_local"]
        self.motor._octavos_vuelta_original[1] = equipo_confirmado
        rondas, _ = self.motor.simular_sudamericana()
        equipos_llave1 = set(rondas["octavos"][0]["agregado"].keys())
        self.assertIn(equipo_confirmado, equipos_llave1)


class TestMonteCarloSudamericana(unittest.TestCase):
    def test_directos_a_octavos_dan_100_por_ciento(self):
        motor = EstadisticasSudamericana()
        motor.cargar_datos_sudamericana()
        motor.crear_equipos_sudamericana()
        mc = motor.monte_carlo_sudamericana(n_simulaciones=50)

        directos = {c["equipo_ida_local"] for c in motor.cuadro if c["ronda"] == "octavos"}
        por_equipo = {f["equipo"]: f for f in mc}
        for nombre in directos:
            self.assertEqual(
                por_equipo[nombre]["%octavos"], 100.0,
                f"{nombre} está directo a octavos, tendría que dar 100% siempre",
            )

    def test_equipos_de_playoffs_no_dan_necesariamente_100(self):
        motor = EstadisticasSudamericana()
        motor.cargar_datos_sudamericana()
        motor.crear_equipos_sudamericana()
        mc = motor.monte_carlo_sudamericana(n_simulaciones=200)

        directos = {c["equipo_ida_local"] for c in motor.cuadro if c["ronda"] == "octavos"}
        por_equipo = {f["equipo"]: f for f in mc}
        de_playoffs = [f for n, f in por_equipo.items() if n not in directos]
        self.assertTrue(
            any(f["%octavos"] < 100.0 for f in de_playoffs),
            "Ningún equipo de playoffs dio menos de 100% en 200 corridas -- improbable, revisar el fix de mutación",
        )

    def test_devuelve_24_equipos(self):
        motor = EstadisticasSudamericana()
        motor.cargar_datos_sudamericana()
        motor.crear_equipos_sudamericana()
        mc = motor.monte_carlo_sudamericana(n_simulaciones=20)
        self.assertEqual(len(mc), 24)


if __name__ == "__main__":
    unittest.main()
