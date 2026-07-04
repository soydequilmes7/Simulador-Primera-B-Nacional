# -*- coding: utf-8 -*-
"""
test_scraper_federal.py

Cubre la lógica que NO depende de la red real (no podemos pegarle a la
API de Promiedos desde acá): resolución de zona por plantel conocido
(scraper_promiedos_federal / scraper_tabla_promiedos_federal) y el
armado incremental de tabla_federal_a.csv por zona
(calcular_tabla_federal). El fetch HTTP en sí (_get_json) se mockea.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from calcular_tabla_federal import _aplicar_partido, _reordenar_posiciones
from scraper_promiedos_federal import _construir_alias, _resolver_equipo
from scraper_tabla_promiedos_federal import _zona_mas_probable

ZONA_POR_EQUIPO = {
    "Boca Unidos": "2", "Juventud Antoniana": "2", "San Martín de Formosa": "2",
    "Cipolletti": "3", "Deportivo Rincón": "3",
    "El Linqueño": "1", "9 de Julio": "1",
}


class ResolverEquipoTests(unittest.TestCase):

    def setUp(self) -> None:
        self.alias = _construir_alias(ZONA_POR_EQUIPO)

    def test_nombre_exacto_se_resuelve_a_si_mismo(self) -> None:
        self.assertEqual(_resolver_equipo("Boca Unidos", ZONA_POR_EQUIPO, self.alias), "Boca Unidos")

    def test_variante_sin_tildes_matchea_por_alias_automatico(self) -> None:
        self.assertEqual(_resolver_equipo("San Martin de Formosa", ZONA_POR_EQUIPO, self.alias),
                          "San Martín de Formosa")

    def test_nombre_desconocido_se_devuelve_sin_cambios(self) -> None:
        self.assertEqual(_resolver_equipo("Club Que No Existe", ZONA_POR_EQUIPO, self.alias),
                          "Club Que No Existe")


class ZonaMasProbableTests(unittest.TestCase):

    def test_zona_con_mas_coincidencias_gana(self) -> None:
        equipos_tabla = ["Boca Unidos", "Juventud Antoniana", "San Martín de Formosa", "Equipo Desconocido"]
        self.assertEqual(_zona_mas_probable(equipos_tabla, ZONA_POR_EQUIPO), "2")

    def test_sin_ninguna_coincidencia_devuelve_none(self) -> None:
        self.assertIsNone(_zona_mas_probable(["Nadie", "Conocido"], ZONA_POR_EQUIPO))

    def test_tabla_de_otra_categoria_no_matchea(self) -> None:
        # Ningún nombre de esta lista pertenece a las zonas conocidas.
        self.assertIsNone(_zona_mas_probable(["Equipo X", "Equipo Y", "Equipo Z"], ZONA_POR_EQUIPO))


class AplicarPartidoTests(unittest.TestCase):
    """calcular_tabla_federal: sumar un resultado a la tabla."""

    def setUp(self) -> None:
        self.indice = {
            "Local": {"partidos_jugados": 0, "ganados": 0, "empatados": 0, "perdidos": 0,
                      "gf": 0, "gc": 0, "dg": 0, "puntos": 0},
            "Visitante": {"partidos_jugados": 0, "ganados": 0, "empatados": 0, "perdidos": 0,
                          "gf": 0, "gc": 0, "dg": 0, "puntos": 0},
        }

    def test_gana_el_local(self) -> None:
        _aplicar_partido(self.indice, "Local", "Visitante", gl=2, gv=0)
        self.assertEqual(self.indice["Local"]["puntos"], 3)
        self.assertEqual(self.indice["Visitante"]["puntos"], 0)
        self.assertEqual(self.indice["Local"]["dg"], 2)
        self.assertEqual(self.indice["Visitante"]["dg"], -2)

    def test_empate_suma_un_punto_a_cada_uno(self) -> None:
        _aplicar_partido(self.indice, "Local", "Visitante", gl=1, gv=1)
        self.assertEqual(self.indice["Local"]["puntos"], 1)
        self.assertEqual(self.indice["Visitante"]["puntos"], 1)

    def test_equipo_inexistente_lanza_keyerror(self) -> None:
        with self.assertRaises(KeyError):
            _aplicar_partido(self.indice, "Local", "No Existe", gl=1, gv=0)


class ReordenarPosicionesTests(unittest.TestCase):
    """calcular_tabla_federal: a diferencia de B Metro, acá SÍ hay que
    numerar cada zona por separado (edge case real que ya causó un bug
    en el motor de simulación con la misma confusión zona-vs-global)."""

    def test_cada_zona_tiene_su_propio_1(self) -> None:
        filas = [
            {"zona": "1", "equipo": "A1", "puntos": 10, "dg": 5, "gf": 10},
            {"zona": "1", "equipo": "A2", "puntos": 20, "dg": 8, "gf": 12},
            {"zona": "2", "equipo": "B1", "puntos": 5, "dg": 1, "gf": 5},
            {"zona": "2", "equipo": "B2", "puntos": 15, "dg": 3, "gf": 7},
        ]
        resultado = _reordenar_posiciones(filas)
        posiciones = {f["equipo"]: f["posicion"] for f in resultado}

        self.assertEqual(posiciones["A2"], 1)  # mejor de zona 1
        self.assertEqual(posiciones["A1"], 2)
        self.assertEqual(posiciones["B2"], 1)  # mejor de zona 2 (posición 1 propia, no global)
        self.assertEqual(posiciones["B1"], 2)

    def test_empate_en_puntos_desempata_por_dg_luego_gf(self) -> None:
        filas = [
            {"zona": "1", "equipo": "Mejor_GF", "puntos": 10, "dg": 2, "gf": 20},
            {"zona": "1", "equipo": "Peor", "puntos": 10, "dg": 2, "gf": 15},
        ]
        resultado = _reordenar_posiciones(filas)
        self.assertEqual(resultado[0]["equipo"], "Mejor_GF")


if __name__ == "__main__":
    unittest.main()
