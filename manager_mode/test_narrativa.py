# -*- coding: utf-8 -*-
"""manager_mode/test_narrativa.py

Tests del motor de narrativa. Ejecutar con:
    python -m unittest manager_mode.test_narrativa -v
"""
from __future__ import annotations

import random
import unittest

from manager_mode.narrativa import Intensidad, NarrativaService, TipoReaccion


class TestNarrativaService(unittest.TestCase):
    def setUp(self) -> None:
        self.service = NarrativaService(rng=random.Random(1))

    def test_reaccion_interpola_variables_del_contexto(self) -> None:
        frase = self.service.reaccion(
            TipoReaccion.PRENSA,
            Intensidad.NEGATIVA,
            {"club": "Quilmes", "rival": "Boca", "entrenador": "Marcelo"},
        )
        self.assertNotIn("{", frase)
        self.assertNotIn("}", frase)

    def test_reaccion_con_contexto_incompleto_lanza_key_error(self) -> None:
        with self.assertRaises(KeyError):
            self.service.reaccion(TipoReaccion.PRENSA, Intensidad.NEGATIVA, {})

    def test_reaccion_varia_entre_llamadas(self) -> None:
        contexto = {"club": "Quilmes", "rival": "Boca", "entrenador": "Marcelo"}
        frases = {
            self.service.reaccion(TipoReaccion.HINCHADA, Intensidad.POSITIVA, contexto)
            for _ in range(20)
        }
        self.assertGreater(len(frases), 1)

    def test_portada_interpola_variables_del_contexto(self) -> None:
        titular = self.service.portada(Intensidad.POSITIVA, {"club": "Quilmes", "entrenador": "Marcelo"})
        self.assertNotIn("{", titular)

    def test_todas_las_combinaciones_de_reaccion_tienen_al_menos_una_frase(self) -> None:
        from manager_mode.narrativa import BANCO_REACCIONES

        for tipo in TipoReaccion:
            for intensidad in Intensidad:
                self.assertIn((tipo, intensidad), BANCO_REACCIONES)
                self.assertGreater(len(BANCO_REACCIONES[(tipo, intensidad)]), 0)


if __name__ == "__main__":
    unittest.main()
