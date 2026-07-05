# -*- coding: utf-8 -*-
"""
test_fixture_generator.py

Cubre fixture_generator.py: cantidad de partidos, jornadas sin equipos
repetidos, cada par se enfrenta 2 veces (una de local cada uno), y los
casos borde (cantidad par/impar de equipos, lista mínima de 2).
"""
from __future__ import annotations

import unittest
from collections import Counter

from fixture_generator import BYE, generar_fixture_ida_vuelta, generar_fixture_una_rueda


class GenerarFixtureUnaRuedaTests(unittest.TestCase):

    def test_cantidad_par_de_equipos_todos_contra_todos_una_vez(self) -> None:
        equipos = [f"E{i}" for i in range(8)]
        partidos = generar_fixture_una_rueda(equipos)

        self.assertEqual(len(partidos), 8 * 7 // 2)
        enfrentamientos = Counter(frozenset((p.equipo_local, p.equipo_visitante)) for p in partidos)
        self.assertTrue(all(veces == 1 for veces in enfrentamientos.values()))

    def test_cantidad_impar_de_equipos_agrega_bye_y_lo_descarta(self) -> None:
        equipos = [f"E{i}" for i in range(9)]
        partidos = generar_fixture_una_rueda(equipos)

        self.assertEqual(len(partidos), 9 * 8 // 2)
        for p in partidos:
            self.assertNotEqual(p.equipo_local, BYE)
            self.assertNotEqual(p.equipo_visitante, BYE)

    def test_ninguna_jornada_repite_un_equipo(self) -> None:
        equipos = [f"E{i}" for i in range(9)]
        partidos = generar_fixture_una_rueda(equipos)

        por_jornada: dict[int, set[str]] = {}
        for p in partidos:
            vistos = por_jornada.setdefault(p.jornada, set())
            self.assertNotIn(p.equipo_local, vistos, "equipo local repetido en la misma jornada")
            self.assertNotIn(p.equipo_visitante, vistos, "equipo visitante repetido en la misma jornada")
            vistos.add(p.equipo_local)
            vistos.add(p.equipo_visitante)

    def test_jornada_inicial_se_respeta(self) -> None:
        partidos = generar_fixture_una_rueda(["A", "B", "C", "D"], jornada_inicial=10)
        self.assertEqual(min(p.jornada for p in partidos), 10)

    def test_menos_de_dos_equipos_lanza_error(self) -> None:
        with self.assertRaises(ValueError):
            generar_fixture_una_rueda(["Único equipo"])


class GenerarFixtureIdaYVueltaTests(unittest.TestCase):

    def test_cada_par_se_enfrenta_dos_veces_una_de_local_cada_uno(self) -> None:
        equipos = [f"E{i}" for i in range(6)]
        partidos = generar_fixture_ida_vuelta(equipos)

        self.assertEqual(len(partidos), 6 * 5)  # todos contra todos, ida y vuelta
        enfrentamientos = Counter(frozenset((p.equipo_local, p.equipo_visitante)) for p in partidos)
        self.assertTrue(all(veces == 2 for veces in enfrentamientos.values()))

        localias = Counter(p.equipo_local for p in partidos)
        # Con 6 equipos (par, sin bye) cada uno es local exactamente 5 veces.
        self.assertTrue(all(veces == 5 for veces in localias.values()))

    def test_vuelta_invierte_localia_respecto_de_la_ida(self) -> None:
        equipos = ["A", "B", "C", "D", "E"]
        partidos = generar_fixture_ida_vuelta(equipos)
        n_jornadas_ida = max(p.jornada for p in partidos) // 2

        ida = [p for p in partidos if p.jornada <= n_jornadas_ida]
        vuelta = [p for p in partidos if p.jornada > n_jornadas_ida]

        cruces_ida = {(p.equipo_local, p.equipo_visitante) for p in ida}
        cruces_vuelta_esperados = {(v, l) for (l, v) in cruces_ida}
        cruces_vuelta_reales = {(p.equipo_local, p.equipo_visitante) for p in vuelta}
        self.assertEqual(cruces_vuelta_esperados, cruces_vuelta_reales)


if __name__ == "__main__":
    unittest.main()
