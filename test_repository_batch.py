# -*- coding: utf-8 -*-
"""
test_repository_batch.py

Cubre la optimización de db/repository.py: upsert_standings() y
replace_matches() deben hacer una cantidad FIJA de round-trips a la
base (3 y 4 respectivamente), sin importar cuántas filas/partidos se
carguen -- antes hacían 1 por fila (~4 por partido en replace_matches),
lo que en tablas de cientos de filas causaba timeouts reales al generar
la temporada siguiente. _execute() se mockea: estos tests no tocan
ninguna base real.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from db.repository import SimulatorRepository


def _fake_execute_factory(llamadas: list):
    """Devuelve un reemplazo de _execute() que registra cada llamada y
    simula season_id()/ensure_teams_bulk() con datos mínimos válidos."""
    def fake_execute(self, query, params=None):
        llamadas.append((query.strip().split()[0].lower(), params))
        if "select s.id" in query:
            return [{"id": 1}]
        if "insert into teams" in query:
            return [{"id": i + 100, "name": n} for i, n in enumerate(params)]
        return []
    return fake_execute


class UpsertStandingsBatchTests(unittest.TestCase):

    def setUp(self) -> None:
        self.repo = SimulatorRepository.__new__(SimulatorRepository)
        self.repo.conn = None
        self.llamadas: list = []

    def _filas(self, n: int) -> list[dict]:
        return [
            {"equipo": f"Equipo{i}", "zona": "A", "posicion": i, "partidos_jugados": 10,
             "ganados": 5, "empatados": 2, "perdidos": 3, "gf": 15, "gc": 10, "dg": 5, "puntos": 17}
            for i in range(1, n + 1)
        ]

    def test_hace_exactamente_3_round_trips_sin_importar_la_cantidad_de_filas(self) -> None:
        for cantidad in (1, 5, 50):
            with self.subTest(cantidad=cantidad):
                self.llamadas.clear()
                with patch.object(SimulatorRepository, "_execute", _fake_execute_factory(self.llamadas)):
                    self.repo.upsert_standings("nacional", self._filas(cantidad))
                self.assertEqual(len(self.llamadas), 3)
                self.assertEqual([l[0] for l in self.llamadas], ["select", "insert", "insert"])

    def test_lista_vacia_no_genera_ninguna_llamada(self) -> None:
        with patch.object(SimulatorRepository, "_execute", _fake_execute_factory(self.llamadas)):
            self.repo.upsert_standings("nacional", [])
        self.assertEqual(len(self.llamadas), 0)

    def test_parametros_del_insert_final_incluyen_todas_las_filas(self) -> None:
        with patch.object(SimulatorRepository, "_execute", _fake_execute_factory(self.llamadas)):
            self.repo.upsert_standings("nacional", self._filas(5))
        _, insert_params = self.llamadas[2]
        # competition_slug es el primer parámetro de cada fila -> debe
        # aparecer 5 veces si se agruparon las 5 filas en un solo insert.
        self.assertEqual(insert_params.count("nacional"), 5)


class ReplaceMatchesBatchTests(unittest.TestCase):

    def setUp(self) -> None:
        self.repo = SimulatorRepository.__new__(SimulatorRepository)
        self.repo.conn = None
        self.llamadas: list = []

    def test_hace_exactamente_4_round_trips_sin_importar_la_cantidad_de_partidos(self) -> None:
        for n_pending, n_played in ((3, 2), (100, 100), (0, 5)):
            with self.subTest(pending=n_pending, played=n_played):
                self.llamadas.clear()
                pending = [{"equipo_local": "A", "equipo_visitante": "B", "jornada": i, "fecha": ""}
                           for i in range(n_pending)]
                played = [{"equipo_local": "C", "equipo_visitante": "D", "jornada": i, "fecha": "",
                           "goles_local": 1, "goles_visitante": 0} for i in range(n_played)]
                with patch.object(SimulatorRepository, "_execute", _fake_execute_factory(self.llamadas)):
                    self.repo.replace_matches("nacional", pending, played)
                self.assertEqual(len(self.llamadas), 4)
                self.assertEqual([l[0] for l in self.llamadas], ["select", "delete", "insert", "insert"])

    def test_sin_partidos_solo_hace_season_id_y_delete(self) -> None:
        with patch.object(SimulatorRepository, "_execute", _fake_execute_factory(self.llamadas)):
            self.repo.replace_matches("nacional", [], [])
        self.assertEqual(len(self.llamadas), 2)
        self.assertEqual([l[0] for l in self.llamadas], ["select", "delete"])


if __name__ == "__main__":
    unittest.main()
