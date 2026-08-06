# -*- coding: utf-8 -*-
"""
tests/test_mapeo_equipos.py

Cubre resolver_equipo() (mapeo_equipos.py, usado por actualizar_resultados.py
de Primera Nacional).
"""
from __future__ import annotations

import unittest

from mapeo_equipos import resolver_equipo


class ResolverEquipoTests(unittest.TestCase):

    def test_ciudad_de_bolivar_resuelve_a_bolivar(self) -> None:
        # Caso real reportado por Pablo (06/08/2026): Promiedos empezó a
        # mandar el nombre completo oficial "Ciudad De Bolívar" en vez
        # del corto "Bolivar" que usa el resto del proyecto (fixture.csv,
        # tabla.csv) -- 4 partidos quedaban "sin identificar" hasta
        # agregar el alias.
        for variante in ("Ciudad De Bolívar", "Ciudad de Bolívar", "ciudad de bolivar"):
            with self.subTest(variante=variante):
                self.assertEqual(resolver_equipo(variante), "Bolivar")

    def test_nombre_canonico_resuelve_a_si_mismo(self) -> None:
        self.assertEqual(resolver_equipo("Bolivar"), "Bolivar")

    def test_nombre_desconocido_no_matchea_nada(self) -> None:
        self.assertIsNone(resolver_equipo("Un Club Que No Existe En Ningún Lado"))


if __name__ == "__main__":
    unittest.main()
