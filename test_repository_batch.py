# -*- coding: utf-8 -*-
"""
test_repository_batch.py

Cubre la optimización de db/repository.py: upsert_standings() y
replace_matches() deben hacer una cantidad FIJA de round-trips a la
base (5 y 6 respectivamente), sin importar cuántas filas/partidos se
carguen -- antes hacían 1 por fila (~4 por partido en replace_matches),
lo que en tablas de cientos de filas causaba timeouts reales al generar
la temporada siguiente. _execute() se mockea: estos tests no tocan
ninguna base real.

La cantidad subió de 3->5 y 4->6 cuando _ensure_teams_bulk() empezó a
consultar `teams` (nombres existentes, exacto + normalizado) y
`team_aliases` ANTES de insertar, para no crear una fila duplicada
cuando el nombre entrante difiere solo en mayúsculas/tildes de uno ya
guardado (ver bug real: "Vasco Da Gama" vs. "Vasco da Gama"). Sigue
siendo una cantidad FIJA de round-trips sin importar cuántas filas
haya -- eso es lo que estos tests protegen -- solo cambió la
constante.
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

    def test_hace_exactamente_5_round_trips_sin_importar_la_cantidad_de_filas(self) -> None:
        for cantidad in (1, 5, 50):
            with self.subTest(cantidad=cantidad):
                self.llamadas.clear()
                with patch.object(SimulatorRepository, "_execute", _fake_execute_factory(self.llamadas)):
                    self.repo.upsert_standings("nacional", self._filas(cantidad))
                self.assertEqual(len(self.llamadas), 5)
                self.assertEqual(
                    [l[0] for l in self.llamadas],
                    ["select", "select", "select", "insert", "insert"],
                )

    def test_lista_vacia_no_genera_ninguna_llamada(self) -> None:
        with patch.object(SimulatorRepository, "_execute", _fake_execute_factory(self.llamadas)):
            self.repo.upsert_standings("nacional", [])
        self.assertEqual(len(self.llamadas), 0)

    def test_parametros_del_insert_final_incluyen_todas_las_filas(self) -> None:
        with patch.object(SimulatorRepository, "_execute", _fake_execute_factory(self.llamadas)):
            self.repo.upsert_standings("nacional", self._filas(5))
        _, insert_params = self.llamadas[-1]
        # competition_slug es el primer parámetro de cada fila -> debe
        # aparecer 5 veces si se agruparon las 5 filas en un solo insert.
        self.assertEqual(insert_params.count("nacional"), 5)


class ReplaceMatchesBatchTests(unittest.TestCase):

    def setUp(self) -> None:
        self.repo = SimulatorRepository.__new__(SimulatorRepository)
        self.repo.conn = None
        self.llamadas: list = []

    def test_hace_exactamente_6_round_trips_sin_importar_la_cantidad_de_partidos(self) -> None:
        for n_pending, n_played in ((3, 2), (100, 100), (0, 5)):
            with self.subTest(pending=n_pending, played=n_played):
                self.llamadas.clear()
                pending = [{"equipo_local": "A", "equipo_visitante": "B", "jornada": i, "fecha": ""}
                           for i in range(n_pending)]
                played = [{"equipo_local": "C", "equipo_visitante": "D", "jornada": i, "fecha": "",
                           "goles_local": 1, "goles_visitante": 0} for i in range(n_played)]
                with patch.object(SimulatorRepository, "_execute", _fake_execute_factory(self.llamadas)):
                    self.repo.replace_matches("nacional", pending, played)
                self.assertEqual(len(self.llamadas), 6)
                self.assertEqual(
                    [l[0] for l in self.llamadas],
                    ["select", "delete", "select", "select", "insert", "insert"],
                )

    def test_sin_partidos_solo_hace_season_id_y_delete(self) -> None:
        with patch.object(SimulatorRepository, "_execute", _fake_execute_factory(self.llamadas)):
            self.repo.replace_matches("nacional", [], [])
        self.assertEqual(len(self.llamadas), 2)
        self.assertEqual([l[0] for l in self.llamadas], ["select", "delete"])


class EnsureTeamsBulkNameMatchingTests(unittest.TestCase):
    """Cubre directamente el bug real: 'Vasco Da Gama' (nombre que trajo
    el scraper en una corrida posterior) no debe crear una fila nueva si
    'Vasco da Gama' (nombre canónico) ya existe en `teams` -- deben
    resolver al mismo team_id."""

    def setUp(self) -> None:
        self.repo = SimulatorRepository.__new__(SimulatorRepository)
        self.repo.conn = None

    def _fake_execute_con_equipo_existente(self):
        def fake_execute(self_repo, query, params=None):
            q = query.strip()
            if q == "select id, name from teams":
                return [{"id": 22255, "name": "Vasco da Gama"}]
            if "from team_aliases" in q:
                return []
            if q.startswith("insert into teams"):
                self.fail("No debería insertar una fila nueva: el equipo ya existe (aunque con otra capitalización).")
            return []
        return fake_execute

    def test_nombre_con_distinta_capitalizacion_resuelve_al_mismo_id_existente(self) -> None:
        with patch.object(SimulatorRepository, "_execute", self._fake_execute_con_equipo_existente()):
            resultado = self.repo._ensure_teams_bulk(["Vasco Da Gama"], "brasileirao")
        self.assertEqual(resultado, {"Vasco Da Gama": 22255})

    def test_equipo_genuinamente_nuevo_se_inserta_una_sola_vez_aunque_venga_con_variantes(self) -> None:
        llamadas_insert = []

        def fake_execute(self_repo, query, params=None):
            q = query.strip()
            if q == "select id, name from teams":
                return []  # nada existe todavía
            if "from team_aliases" in q:
                return []
            if q.startswith("insert into teams"):
                llamadas_insert.append(params)
                # Solo se inserta 1 fila (la primera variante vista);
                # el resultado se comparte con la otra variante del batch.
                return [{"id": 999, "name": params[0]}]
            return []

        with patch.object(SimulatorRepository, "_execute", fake_execute):
            resultado = self.repo._ensure_teams_bulk(["Club Nuevo", "club nuevo"], "brasileirao")

        self.assertEqual(len(llamadas_insert), 1)
        self.assertEqual(len(llamadas_insert[0]), 1)  # una sola fila en el insert, no dos
        self.assertEqual(resultado["Club Nuevo"], 999)
        self.assertEqual(resultado["club nuevo"], 999)


if __name__ == "__main__":
    unittest.main()
