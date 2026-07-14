# -*- coding: utf-8 -*-
"""Tests de posiciones_evolucion.py (happy path + casos borde)."""
from __future__ import annotations

import unittest

from posiciones_evolucion import calcular_evolucion, tamano_por_zona


class CalcularEvolucionTests(unittest.TestCase):
    def setUp(self):
        self.zona_por_club = {
            "Quilmes": "A",
            "Chacarita": "A",
            "Ferro": "B",
            "Morón": "B",
        }

    def test_snapshot_despues_de_cada_fecha(self):
        partidos = [
            {"jornada": 1, "equipo_local": "Quilmes", "equipo_visitante": "Chacarita",
             "goles_local": 2, "goles_visitante": 0},
            {"jornada": 2, "equipo_local": "Chacarita", "equipo_visitante": "Quilmes",
             "goles_local": 1, "goles_visitante": 1},
        ]
        evolucion = calcular_evolucion(partidos, self.zona_por_club)

        self.assertEqual(len(evolucion["Quilmes"]), 2)
        self.assertEqual(evolucion["Quilmes"][0]["posicion"], 1)  # ganó fecha 1
        self.assertEqual(evolucion["Quilmes"][0]["puntos"], 3)
        self.assertEqual(evolucion["Quilmes"][1]["puntos"], 4)  # +1 por el empate

        # Equipos de otra zona no juegan pero igual reciben snapshot con su
        # posición dentro de su propia zona (sigue en 1° con 0 puntos, ya
        # que Ferro y Morón todavía no jugaron entre sí).
        self.assertEqual(len(evolucion["Ferro"]), 2)
        self.assertEqual(evolucion["Ferro"][0]["zona"], "B")

    def test_zonas_no_se_mezclan(self):
        partidos = [
            {"jornada": 1, "equipo_local": "Quilmes", "equipo_visitante": "Chacarita",
             "goles_local": 3, "goles_visitante": 0},
        ]
        evolucion = calcular_evolucion(partidos, self.zona_por_club)
        # Ferro/Morón (zona B) no deben verse afectados por resultados de zona
        # A: siguen 0 a 0, se desempatan solo por nombre ("Ferro" < "Morón").
        self.assertEqual(evolucion["Ferro"][0]["posicion"], 1)
        self.assertEqual(evolucion["Morón"][0]["posicion"], 2)

    def test_fecha_sin_partidos_no_genera_snapshot(self):
        partidos = [
            {"jornada": 1, "equipo_local": "Quilmes", "equipo_visitante": "Chacarita",
             "goles_local": 1, "goles_visitante": 0},
            {"jornada": 3, "equipo_local": "Chacarita", "equipo_visitante": "Quilmes",
             "goles_local": 2, "goles_visitante": 0},
        ]
        evolucion = calcular_evolucion(partidos, self.zona_por_club)
        jornadas = [s["jornada"] for s in evolucion["Quilmes"]]
        self.assertEqual(jornadas, [1, 3])  # sin la fecha 2, que no tiene partidos

    def test_equipo_desconocido_se_ignora_sin_romper(self):
        partidos = [
            {"jornada": 1, "equipo_local": "Quilmes", "equipo_visitante": "Club Fantasma",
             "goles_local": 1, "goles_visitante": 0},
        ]
        evolucion = calcular_evolucion(partidos, self.zona_por_club)
        self.assertEqual(evolucion["Quilmes"][0]["puntos"], 0)

    def test_desempate_por_diferencia_de_gol_y_luego_nombre(self):
        partidos = [
            {"jornada": 1, "equipo_local": "Quilmes", "equipo_visitante": "Chacarita",
             "goles_local": 0, "goles_visitante": 0},
        ]
        evolucion = calcular_evolucion(partidos, self.zona_por_club)
        # Mismo puntaje y DG (ambos 1 punto, DG 0) -> desempata por nombre
        self.assertEqual(evolucion["Chacarita"][0]["posicion"], 1)
        self.assertEqual(evolucion["Quilmes"][0]["posicion"], 2)

    def test_tamano_por_zona(self):
        self.assertEqual(tamano_por_zona(self.zona_por_club), {"A": 2, "B": 2})


if __name__ == "__main__":
    unittest.main()
