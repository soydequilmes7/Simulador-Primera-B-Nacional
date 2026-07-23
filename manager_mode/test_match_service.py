# -*- coding: utf-8 -*-
"""manager_mode/test_match_service.py

Tests del servicio de simulación de partidos del Modo DT. Ejecutar con:
    python -m unittest manager_mode.test_match_service -v
"""
from __future__ import annotations

import unittest

import numpy as np

from manager_mode.domain import Entrenador, IdentidadTactica
from manager_mode.match_service import PartidoDTService


class TestPartidoDTService(unittest.TestCase):
    def setUp(self) -> None:
        self.rng = np.random.default_rng(seed=42)
        self.service = PartidoDTService(rng=self.rng)

    def test_simular_partido_de_local_devuelve_marcador_no_negativo(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.OFENSIVO)
        resultado = self.service.simular_partido(
            entrenador,
            ataque_club=1.1, defensa_club=0.9,
            ataque_rival=0.9, defensa_rival=1.0,
            de_local=True,
        )
        self.assertGreaterEqual(resultado.goles_local, 0)
        self.assertGreaterEqual(resultado.goles_visitante, 0)
        self.assertEqual(resultado.goles_entrenador, resultado.goles_local)

    def test_simular_partido_de_visitante_asigna_goles_correctamente(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.PRAGMATICO)
        resultado = self.service.simular_partido(
            entrenador,
            ataque_club=1.0, defensa_club=1.0,
            ataque_rival=1.0, defensa_rival=1.0,
            de_local=False,
        )
        self.assertEqual(resultado.goles_entrenador, resultado.goles_visitante)
        self.assertEqual(resultado.goles_rival, resultado.goles_local)

    def test_simular_partido_actualiza_record_del_entrenador(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.MOTIVADOR)
        self.service.simular_partido(
            entrenador,
            ataque_club=1.0, defensa_club=1.0,
            ataque_rival=1.0, defensa_rival=1.0,
            de_local=True,
        )
        self.assertEqual(entrenador.record.partidos_jugados, 1)

    def test_identidad_ofensiva_aumenta_ataque_esperado(self) -> None:
        """No determinista partido a partido, pero en una muestra grande
        un DT Ofensivo debe promediar más goles a favor que uno
        Pragmático con los mismos ratings base."""
        rng_ofensivo = np.random.default_rng(seed=7)
        rng_pragmatico = np.random.default_rng(seed=7)
        service_ofensivo = PartidoDTService(rng=rng_ofensivo)
        service_pragmatico = PartidoDTService(rng=rng_pragmatico)

        goles_ofensivo = 0
        goles_pragmatico = 0
        n = 500
        for _ in range(n):
            entrenador_of = Entrenador(nombre="A", identidad=IdentidadTactica.OFENSIVO)
            entrenador_prag = Entrenador(nombre="B", identidad=IdentidadTactica.PRAGMATICO)
            r_of = service_ofensivo.simular_partido(
                entrenador_of,
                ataque_club=1.0, defensa_club=1.0,
                ataque_rival=1.0, defensa_rival=1.0,
                de_local=True,
            )
            r_prag = service_pragmatico.simular_partido(
                entrenador_prag,
                ataque_club=1.0, defensa_club=1.0,
                ataque_rival=1.0, defensa_rival=1.0,
                de_local=True,
            )
            goles_ofensivo += r_of.goles_entrenador
            goles_pragmatico += r_prag.goles_entrenador

        self.assertGreater(goles_ofensivo / n, goles_pragmatico / n)


if __name__ == "__main__":
    unittest.main()
