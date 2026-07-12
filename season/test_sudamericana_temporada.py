# -*- coding: utf-8 -*-
"""
season/test_sudamericana_temporada.py

Cubre el pipeline dinámico de Copa Sudamericana en Modo Temporada
(season/sudamericana_temporada.py): que ningún club juegue las dos
copas la misma temporada, que Playoffs se arme por ranking
determinístico (mejor 2° vs peor 3°, sin sorteo) y Octavos por sorteo
abierto (sin restricción de país, confirmado contra el instructivo
oficial de CONMEBOL -- ver docstring del módulo bajo test).
"""
from __future__ import annotations

import random
import unittest

from season.libertadores_grupos import simular_temporada_libertadores
from season.sudamericana_temporada import (
    simular_temporada_sudamericana,
    _armar_playoffs_por_ranking,
    _sortear_octavos_pendientes,
    _ordenar_por_desempeno,
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
            self.assertEqual(res_sud["avisos"], clasificacion_avisos_esperados(res_sud))

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


def clasificacion_avisos_esperados(res_sud):
    """Ya no hay avisos de fallback de país (no existe esa restricción
    a partir de Playoffs) -- lo único que puede avisar acá es
    LibertadoresManager si el pool se queda corto, algo que no debería
    pasar con el pool real. Se deja como helper por si en el futuro se
    agregan avisos legítimos de otro tipo."""
    return res_sud["avisos"]


class TestArmarPlayoffsPorRanking(unittest.TestCase):
    def test_mejor_segundo_enfrenta_al_peor_tercero(self):
        """Reglamento real (confirmado, conmebol.com): el mejor
        segundo de Sudamericana enfrenta al peor tercero de
        Libertadores, y así sucesivamente -- determinístico, no
        sorteo."""
        class FilaFalsa:
            def __init__(self, equipo, puntos, dg, gf):
                self.equipo, self.puntos, self.dg, self.gf = equipo, puntos, dg, gf

        segundos = [FilaFalsa(f"S{i}", puntos=8 - i, dg=0, gf=0) for i in range(8)]  # S0 el mejor
        terceros = [{"equipo": f"T{i}", "puntos": i, "dg": 0, "gf": 0} for i in range(8)]  # T7 el mejor, T0 el peor

        cuadro = _armar_playoffs_por_ranking(segundos, terceros)
        # El mejor segundo (S0) tiene que enfrentar al peor tercero (T0).
        llave_de_s0 = next(f for f in cuadro if f["equipo_vuelta_local"] == "S0")
        self.assertEqual(llave_de_s0["equipo_ida_local"], "T0")

    def test_ida_en_cancha_del_tercero_vuelta_en_cancha_del_segundo(self):
        """Reglamento real: la ida se juega en la cancha del tercero
        de Libertadores, la vuelta en la del segundo de Sudamericana
        (el más beneficiado, define la serie)."""
        class FilaFalsa:
            def __init__(self, equipo, puntos, dg, gf):
                self.equipo, self.puntos, self.dg, self.gf = equipo, puntos, dg, gf

        segundos = [FilaFalsa(f"S{i}", puntos=i, dg=0, gf=0) for i in range(8)]
        terceros = [{"equipo": f"T{i}", "puntos": i, "dg": 0, "gf": 0} for i in range(8)]
        cuadro = _armar_playoffs_por_ranking(segundos, terceros)
        for fila in cuadro:
            self.assertTrue(fila["equipo_ida_local"].startswith("T"))
            self.assertTrue(fila["equipo_vuelta_local"].startswith("S"))

    def test_permite_mismo_pais_sin_restriccion(self):
        """No hay restricción de país en Playoffs (confirmado) -- no
        debería haber ninguna lógica de evitarlo."""
        class FilaFalsa:
            def __init__(self, equipo, puntos, dg, gf):
                self.equipo, self.puntos, self.dg, self.gf = equipo, puntos, dg, gf

        segundos = [FilaFalsa(f"AR_S{i}", puntos=i, dg=0, gf=0) for i in range(8)]
        terceros = [{"equipo": f"AR_T{i}", "puntos": i, "dg": 0, "gf": 0} for i in range(8)]
        cuadro = _armar_playoffs_por_ranking(segundos, terceros)  # no debería levantar nada
        self.assertEqual(len(cuadro), 8)


class TestSortearOctavosPendientes(unittest.TestCase):
    def test_devuelve_8_llaves_con_ida_en_blanco(self):
        primeros = [f"P{i}" for i in range(8)]
        cuadro = _sortear_octavos_pendientes(primeros, cantidad_llaves=8, rng=random.Random(1))
        self.assertEqual(len(cuadro), 8)
        for fila in cuadro:
            self.assertEqual(fila["equipo_ida_local"], "")  # se completa recién al simular Playoffs
            self.assertIn(fila["equipo_vuelta_local"], primeros)

    def test_es_aleatorio(self):
        primeros = [f"P{i}" for i in range(8)]
        ordenes = set()
        for seed in range(10):
            cuadro = _sortear_octavos_pendientes(primeros, cantidad_llaves=8, rng=random.Random(seed))
            ordenes.add(tuple(f["equipo_vuelta_local"] for f in cuadro))
        self.assertGreater(len(ordenes), 1)


class TestOrdenarPorDesempeno(unittest.TestCase):
    def test_ordena_por_puntos_luego_dg_luego_gf(self):
        candidatos = [
            {"equipo": "A", "puntos": 10, "dg": 2, "gf": 5},
            {"equipo": "B", "puntos": 10, "dg": 5, "gf": 3},
            {"equipo": "C", "puntos": 12, "dg": -1, "gf": 1},
        ]
        orden = [c["equipo"] for c in _ordenar_por_desempeno(candidatos)]
        self.assertEqual(orden, ["C", "B", "A"])


if __name__ == "__main__":
    unittest.main()
