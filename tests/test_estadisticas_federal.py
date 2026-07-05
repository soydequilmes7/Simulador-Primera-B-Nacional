# -*- coding: utf-8 -*-
"""
test_estadisticas_federal.py

Cubre la lógica de clasificación/desempate de EstadisticasFederal con
tablas armadas a mano (deterministas, sin depender de una simulación
Monte Carlo real) -- lo más propenso a errores de "off-by-one" en un
reglamento con tantas fases y resiembras.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from modelos.estadisticas_federal import EstadisticasFederal, ResultadoSerie


def _tabla(equipos: list[str], boost: int = 0) -> pd.DataFrame:
    """Tabla de zona ya "ordenada" (equipos en el orden que se les da),
    con dg/gf decrecientes para que el orden sea inequívoco. `boost` deja
    a toda la zona con mejores números que una zona sin boost, para
    poder armar comparaciones entre zonas sin empates accidentales."""
    n = len(equipos)
    return pd.DataFrame({
        "equipo": equipos,
        "puntos": [3 * (n - i) for i in range(n)],
        "gf": [2 * (n - i) + boost for i in range(n)],
        "gc": [i for i in range(n)],
        "dg": [2 * (n - i) - i + boost for i in range(n)],
    })


class ClasificadosPrimeraFaseTests(unittest.TestCase):
    """Art. 11: tamaños de zona de la Segunda Fase (siempre 9 y 9) y de
    la Reválida (19 en total, repartidos 10/9 según de dónde salga el
    'mejor quinto')."""

    def setUp(self) -> None:
        self.e = EstadisticasFederal()
        self.tablas = {
            "1": _tabla([f"Z1-{i}" for i in range(1, 11)]),           # zona de 10
            "2": _tabla([f"Z2-{i}" for i in range(1, 10)], boost=10),  # zonas de 9 (Z2 con mejores números)
            "3": _tabla([f"Z3-{i}" for i in range(1, 10)]),
            "4": _tabla([f"Z4-{i}" for i in range(1, 10)]),
        }

    def test_tamanos_de_zona_siempre_9_y_9_en_segunda_fase(self) -> None:
        clasif = self.e.clasificados_primera_fase(self.tablas)
        self.assertEqual(len(clasif["segunda_fase_A"]), 9)
        self.assertEqual(len(clasif["segunda_fase_B"]), 9)

    def test_zona_a_siempre_es_zona1_top5_mas_zona2_top4(self) -> None:
        """Zona A nunca recibe al 'mejor quinto': es fija (Art. 11)."""
        clasif = self.e.clasificados_primera_fase(self.tablas)
        self.assertEqual(
            set(clasif["segunda_fase_A"]),
            {"Z1-1", "Z1-2", "Z1-3", "Z1-4", "Z1-5", "Z2-1", "Z2-2", "Z2-3", "Z2-4"},
        )

    def test_mejor_quinto_va_siempre_a_zona_b(self) -> None:
        """En esta tabla Z2-5 es, por construcción, mejor en dg/gf que
        Z3-5 y Z4-5 (mismo puesto pero Z2 tiene números más altos en la
        tabla armada por _tabla()), así que debería ganar el 'mejor
        quinto' y sumarse a la Zona B (nunca a la A)."""
        clasif = self.e.clasificados_primera_fase(self.tablas)
        self.assertIn("Z2-5", clasif["segunda_fase_B"])
        self.assertNotIn("Z2-5", clasif["segunda_fase_A"])

    def test_37_equipos_sin_duplicados_ni_faltantes(self) -> None:
        clasif = self.e.clasificados_primera_fase(self.tablas)
        todos = (clasif["segunda_fase_A"] + clasif["segunda_fase_B"]
                 + clasif["revalida_A"] + clasif["revalida_B"])
        self.assertEqual(len(todos), 37)
        self.assertEqual(len(set(todos)), 37)

    def test_revalida_totaliza_19_repartidos_10_y_9(self) -> None:
        clasif = self.e.clasificados_primera_fase(self.tablas)
        tamanos = sorted([len(clasif["revalida_A"]), len(clasif["revalida_B"])])
        self.assertEqual(tamanos, [9, 10])


class JugarLlaveIdaYVueltaTests(unittest.TestCase):
    """La serie a dos partidos: gana quien más goles agregados hace: si
    empatan, se resuelve por el `ganador_en_empate` inyectado (sembrado)
    salvo que sea None, en cuyo caso es 50/50 (penales) -- único caso
    real: la Sexta Etapa de la Reválida."""

    def setUp(self) -> None:
        self.e = EstadisticasFederal()

    def test_gana_quien_convierte_mas_goles_agregados(self) -> None:
        with patch.object(self.e, "simular_partido", side_effect=[(2, 0), (0, 1)]):
            resultado = self.e._jugar_llave_ida_vuelta("A", "B", ganador_en_empate=None)
        # Ida: A 2-0 B. Vuelta: B 0-1 A (A de visitante). Agregado: A=2+1=3, B=0+0=0.
        self.assertEqual(resultado.ganador, "A")
        self.assertEqual(resultado.perdedor, "B")
        self.assertEqual(resultado.detalle["agregado"], [3, 0])

    def test_empate_agregado_con_sembrado_no_usa_penales(self) -> None:
        with patch.object(self.e, "simular_partido", side_effect=[(1, 1), (1, 1)]):
            resultado = self.e._jugar_llave_ida_vuelta("A", "B", ganador_en_empate="B")
        self.assertEqual(resultado.ganador, "B")
        self.assertEqual(resultado.detalle["definido_por"], "mejor_ubicacion")

    def test_empate_agregado_sin_sembrado_se_define_por_penales(self) -> None:
        with patch.object(self.e, "simular_partido", side_effect=[(0, 0), (0, 0)]):
            with patch("numpy.random.random", return_value=0.9):  # > 0.5 -> gana el visitante de ida
                resultado = self.e._jugar_llave_ida_vuelta("A", "B", ganador_en_empate=None)
        self.assertEqual(resultado.ganador, "B")
        self.assertEqual(resultado.detalle["definido_por"], "penales")

    def test_local_de_ida_es_visitante_en_la_vuelta(self) -> None:
        llamadas = []

        def falso_partido(local, visitante):
            llamadas.append((local, visitante))
            return (1, 0)

        with patch.object(self.e, "simular_partido", side_effect=falso_partido):
            self.e._jugar_llave_ida_vuelta("Local1", "Visitante1", ganador_en_empate=None)
        self.assertEqual(llamadas, [("Local1", "Visitante1"), ("Visitante1", "Local1")])


class MejorPorDgGfTests(unittest.TestCase):
    """El desempate del 'mejor quinto' (Art. 12.3, sin el criterio de
    goles como visitante -- simplificación documentada en el módulo)."""

    def setUp(self) -> None:
        self.e = EstadisticasFederal()

    def test_desempata_por_diferencia_de_gol(self) -> None:
        tabla = pd.DataFrame({
            "equipo": ["A", "B", "C"],
            "dg": [5, 8, 2],
            "gf": [10, 10, 10],
        })
        self.assertEqual(self.e._mejor_por_dg_gf(tabla, ["A", "B", "C"], semilla="x"), "B")

    def test_empate_en_dg_desempata_por_gf(self) -> None:
        tabla = pd.DataFrame({
            "equipo": ["A", "B"],
            "dg": [5, 5],
            "gf": [12, 9],
        })
        self.assertEqual(self.e._mejor_por_dg_gf(tabla, ["A", "B"], semilla="x"), "A")

    def test_empate_total_es_reproducible(self) -> None:
        tabla = pd.DataFrame({"equipo": ["A", "B"], "dg": [5, 5], "gf": [9, 9]})
        primero = self.e._mejor_por_dg_gf(tabla, ["A", "B"], semilla="misma-semilla")
        segundo = self.e._mejor_por_dg_gf(tabla, ["A", "B"], semilla="misma-semilla")
        self.assertEqual(primero, segundo)


class CalcularDescensosTests(unittest.TestCase):
    """Regresión de un bug real: el Reglamento asegura de descenso a
    quien sea top-5 en la tabla DE LA REVÁLIDA PRIMERA ETAPA SOLA (la
    misma que arma las posiciones 15-24 de la Segunda Etapa), no a quien
    sea top-5 en la tabla COMBINADA (Primera Fase + Reválida). Un equipo
    puede ordenar distinto en una y otra -- si se usa la combinada para
    decidir quién está "a salvo", un clasificado a la Segunda Etapa
    podía terminar igual en la lista de descensos."""

    def test_top5_fase_only_nunca_desciende_aunque_combinada_lo_ubique_ultimo(self) -> None:
        e = EstadisticasFederal()

        # 9 equipos por zona (tamaño real). "Fantasma" es 5° en la tabla
        # FASE-ONLY (así que está asegurado), pero le fue pésimo en la
        # Primera Fase, así que en la tabla COMBINADA cae al último lugar
        # -- pese a eso, no debe descender.
        equipos_ra = ["RA1", "RA2", "RA3", "RA4", "Fantasma", "RA6", "RA7", "RA8", "RA9"]
        equipos_rb = [f"RB{i}" for i in range(1, 10)]
        tablas_revalida = {
            "RA": pd.DataFrame({
                "equipo": equipos_ra,
                "puntos": [24, 21, 18, 15, 12, 9, 6, 3, 0],
                "gf": [20, 18, 16, 14, 12, 10, 8, 6, 4],
                "gc": [0, 1, 2, 3, 4, 5, 6, 7, 8],
                "dg": [20, 17, 14, 11, 8, 5, 2, -1, -4],
            }),
            "RB": pd.DataFrame({
                "equipo": equipos_rb,
                "puntos": [24, 21, 18, 15, 12, 9, 6, 3, 0],
                "gf": [20, 18, 16, 14, 12, 10, 8, 6, 4],
                "gc": [0, 1, 2, 3, 4, 5, 6, 7, 8],
                "dg": [20, 17, 14, 11, 8, 5, 2, -1, -4],
            }),
        }

        # "Fantasma" es 1° en la Reválida (24 puntos, el máximo de la
        # tabla) -- así que es top-5 fase-only y está asegurado -- pero
        # en Primera Fase no sacó nada, mientras el resto de RA sí sacó
        # puntos altos: en la tabla COMBINADA (Primera Fase + Reválida)
        # termina de todos modos último.
        def puntos_pf(equipos, es_fantasma_bajo):
            return [0 if (es_fantasma_bajo and e == "Fantasma") else 40 for e in equipos]

        ceros = lambda equipos, altos=False: pd.DataFrame({  # noqa: E731 (helper local, solo para el test)
            "equipo": equipos, "puntos": puntos_pf(equipos, altos),
            "gf": [0] * len(equipos), "gc": [0] * len(equipos),
        })
        tablas_primera_fase = {"1": ceros(equipos_ra, altos=True), "2": ceros([]),
                                "3": ceros(equipos_rb, altos=True), "4": ceros([])}

        # _zona_origen_por_equipo() lee self.tabla: todos los equipos de
        # esta prueba se anclan a zona "1" (RA) o "3" (RB) -- alcanza con
        # que sean claves válidas de _PARTIDOS_PRIMERA_FASE_POR_ZONA.
        e.tabla = pd.DataFrame({
            "equipo": equipos_ra + equipos_rb,
            "zona": ["1"] * len(equipos_ra) + ["3"] * len(equipos_rb),
        })

        descensos = e.calcular_descensos(tablas_primera_fase, tablas_revalida, clasificados_1f={})

        self.assertNotIn("Fantasma", descensos)
        self.assertEqual(len(descensos), 4)


if __name__ == "__main__":
    unittest.main()
