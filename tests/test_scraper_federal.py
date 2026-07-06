# -*- coding: utf-8 -*-
"""
test_scraper_federal.py

Cubre mapeo_equipos_federal.py (resolución de nombres Promiedos -> nombre
local, sin red real) y calcular_tabla_federal.py (armado incremental de
tabla_federal_a.csv). Reemplaza al test_scraper_federal.py viejo, que
apuntaba a funciones (_construir_alias/_resolver_equipo) que ya no existen
después de reescribir el scraper con mapeo_equipos_federal.py.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from actualizar_resultados_federal import _clasificar_partidos_jugados, _preparar_sync_promiedos
from calcular_tabla_federal import _aplicar_partido, _reordenar_posiciones
from mapeo_equipos_federal import normalizar, resolver_equipo
from scraper_promiedos_federal import _deduplicar_partidos, _fechas_por_rango, _parsear_partido


class NormalizarTests(unittest.TestCase):

    def test_saca_tildes_mayusculas_y_puntuacion(self) -> None:
        self.assertEqual(normalizar("Atlético Escobar"), "atletico escobar")
        self.assertEqual(normalizar("9 De Julio Rafaela"), "9 de julio rafaela")

    def test_colapsa_espacios_repetidos(self) -> None:
        self.assertEqual(normalizar("Costa   Brava"), "costa brava")

    def test_nombre_vacio_devuelve_vacio(self) -> None:
        self.assertEqual(normalizar(""), "")
        self.assertEqual(normalizar(None), "")

    def test_conserva_parentesis(self) -> None:
        self.assertEqual(normalizar("Sarmiento (LB)"), "sarmiento (lb)")


class ResolverEquipoTests(unittest.TestCase):
    """Casos confirmados contra un dump real de Promiedos (ver el
    docstring de mapeo_equipos_federal.py) -- si alguno de estos falla,
    es porque cambió el archivo de overrides, no un problema del test."""

    def test_nombre_local_exacto_se_resuelve_a_si_mismo(self) -> None:
        self.assertEqual(resolver_equipo("Costa Brava (Gral Pico)"), "Costa Brava (Gral Pico)")

    def test_alias_confirmado_resuelve_al_nombre_local(self) -> None:
        self.assertEqual(resolver_equipo("Sp. Belgrano"), "Sportivo Belgrano")
        self.assertEqual(resolver_equipo("Boca Unidos"), "Boca Unidos de Corrientes")
        self.assertEqual(resolver_equipo("Defensores (VR)"), "Defensores Belgrano (VR)")
        self.assertEqual(resolver_equipo("Sarmiento (R)"), "Sarmiento de Resistencia")
        self.assertEqual(resolver_equipo("Sarmiento (LB)"), "Sarmiento De La Banda")

    def test_alias_case_insensitive_y_sin_tildes(self) -> None:
        self.assertEqual(resolver_equipo("SP. BELGRANO"), "Sportivo Belgrano")
        self.assertEqual(resolver_equipo("boca unidos"), "Boca Unidos de Corrientes")

    def test_fuzzy_matching_tolera_pequenas_variantes_no_listadas(self) -> None:
        # "Sp Belgrano" (sin punto) no está listado tal cual en OVERRIDES,
        # pero debería resolver por fuzzy matching contra "sp. belgrano".
        self.assertEqual(resolver_equipo("Sp Belgrano"), "Sportivo Belgrano")

    def test_nombre_sin_match_devuelve_none(self) -> None:
        self.assertIsNone(resolver_equipo("Club Que No Existe En Ninguna Zona"))

    def test_nombre_vacio_devuelve_none(self) -> None:
        self.assertIsNone(resolver_equipo(""))


class ScraperFederalTests(unittest.TestCase):

    def test_fallback_de_fechas_prueba_todos_los_prefijos_por_numero(self) -> None:
        def fake_get_json(path: str) -> dict:
            if path.endswith("/A_1") or path.endswith("/B_2"):
                return {"games": [{"id": "ok"}]}
            return {"games": []}

        with patch("scraper_promiedos_federal._get_json", side_effect=fake_get_json), \
             patch("scraper_promiedos_federal.time.sleep"):
            fechas = _fechas_por_rango(("A_", "B_"), max_fechas=4)

        self.assertEqual(
            fechas,
            [
                {"nombre": "Fecha 1", "key": "A_1"},
                {"nombre": "Fecha 2", "key": "B_2"},
            ],
        )

    def test_parsear_partido_finalizado_con_scores(self) -> None:
        partido = _parsear_partido(
            {
                "stage_round_name": "Fecha 16",
                "teams": [
                    {"short_name": "Sp. Belgrano", "name": "Sportivo Belgrano"},
                    {"short_name": "Independiente (Chi)", "name": "Independiente Chivilcoy"},
                ],
                "scores": [2.0, 1.0],
                "status": {"enum": 3, "name": "Finalizado"},
            },
            {"Sportivo Belgrano": "1", "Independiente Chivilcoy": "1"},
        )

        self.assertTrue(partido["jugado"])
        self.assertEqual(partido["equipo_local"], "Sportivo Belgrano")
        self.assertEqual(partido["equipo_visitante"], "Independiente Chivilcoy")
        self.assertEqual(partido["goles_local"], 2)
        self.assertEqual(partido["goles_visitante"], 1)

    def test_deduplicar_partidos_prefiere_version_jugada(self) -> None:
        pendiente = {
            "jornada": 16,
            "equipo_local": "Local",
            "equipo_visitante": "Visitante",
            "jugado": False,
        }
        jugado = {
            "jornada": 16,
            "equipo_local": "Local",
            "equipo_visitante": "Visitante",
            "jugado": True,
            "goles_local": 1,
            "goles_visitante": 0,
        }

        self.assertEqual(_deduplicar_partidos([pendiente, jugado]), [jugado])


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
    """A diferencia de B Metro (una sola zona "Unica"), el Federal A
    tiene 4 zonas reales: cada una debe numerarse por separado."""

    def test_cada_zona_tiene_su_propio_1(self) -> None:
        filas = [
            {"zona": "1", "equipo": "A1", "puntos": 10, "dg": 5, "gf": 10},
            {"zona": "1", "equipo": "A2", "puntos": 20, "dg": 8, "gf": 12},
            {"zona": "2", "equipo": "B1", "puntos": 5, "dg": 1, "gf": 5},
            {"zona": "2", "equipo": "B2", "puntos": 15, "dg": 3, "gf": 7},
        ]
        resultado = _reordenar_posiciones(filas)
        posiciones = {f["equipo"]: f["posicion"] for f in resultado}

        self.assertEqual(posiciones["A2"], 1)
        self.assertEqual(posiciones["A1"], 2)
        self.assertEqual(posiciones["B2"], 1)
        self.assertEqual(posiciones["B1"], 2)

    def test_empate_en_puntos_desempata_por_dg_luego_gf(self) -> None:
        filas = [
            {"zona": "1", "equipo": "Mejor_GF", "puntos": 10, "dg": 2, "gf": 20},
            {"zona": "1", "equipo": "Peor", "puntos": 10, "dg": 2, "gf": 15},
        ]
        resultado = _reordenar_posiciones(filas)
        self.assertEqual(resultado[0]["equipo"], "Mejor_GF")


class ActualizarFederalTests(unittest.TestCase):

    def test_ignora_partidos_ya_cargados_antes_de_sin_matchear(self) -> None:
        partidos_promiedos = [
            {
                "jornada": 15,
                "equipo_local": "El Linqueño",
                "equipo_visitante": "Sportivo Belgrano",
                "goles_local": 1,
                "goles_visitante": 1,
            },
            {
                "jornada": 16,
                "equipo_local": "Sportivo Belgrano",
                "equipo_visitante": "Independiente Chivilcoy",
                "goles_local": 2,
                "goles_visitante": 0,
            },
        ]
        fixture = [
            {
                "fecha": "",
                "jornada": "16",
                "equipo_local": "Sportivo Belgrano",
                "equipo_visitante": "Independiente Chivilcoy",
            },
        ]
        resultados = [
            {
                "fecha": "",
                "jornada": "15",
                "equipo_local": "El Linqueño",
                "equipo_visitante": "Sportivo Belgrano",
                "goles_local": 1,
                "goles_visitante": 1,
            },
        ]

        fixture_restante, resultados_actualizados, cargados, sin_matchear = _clasificar_partidos_jugados(
            partidos_promiedos, fixture, resultados,
        )

        self.assertEqual(sin_matchear, [])
        self.assertEqual(len(cargados), 1)
        self.assertEqual(cargados[0]["jornada"], 16)
        self.assertEqual(fixture_restante, [])
        self.assertEqual(len(resultados_actualizados), 2)

    def test_sync_promiedos_repara_fixture_incompleto_sin_sin_matchear(self) -> None:
        partidos_promiedos = [
            {
                "jornada": 1,
                "equipo_local": "Local",
                "equipo_visitante": "Visitante",
                "jugado": True,
                "goles_local": 2,
                "goles_visitante": 0,
            },
            {
                "jornada": 2,
                "equipo_local": "Visitante",
                "equipo_visitante": "Local",
                "jugado": False,
            },
        ]
        standings = [
            {"equipo": "Local"},
            {"equipo": "Visitante"},
        ]

        sync = _preparar_sync_promiedos(
            partidos_promiedos,
            fixture_actual=[],
            resultados_actuales=[],
            standings_actuales=standings,
            standings_promiedos=None,
        )

        self.assertTrue(sync["fixture_reparado"])
        self.assertTrue(sync["resultados_reparados"])
        self.assertEqual(sync["sin_matchear"], [])
        self.assertEqual(len(sync["cargados"]), 1)
        self.assertEqual(sync["fixture"][0]["jornada"], 2)
        self.assertEqual(sync["resultados"][0]["goles_local"], 2)


if __name__ == "__main__":
    unittest.main()
