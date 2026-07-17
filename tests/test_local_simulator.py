import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import data_access
import pysim_dispatch
from modelos.estadisticas import Estadisticas


class EmptyResultsValidationTests(unittest.TestCase):
    def test_accepts_header_only_results_for_a_new_season(self):
        stats = Estadisticas()
        stats.resultados = pd.DataFrame(
            columns=[
                "fecha",
                "jornada",
                "equipo_local",
                "equipo_visitante",
                "goles_local",
                "goles_visitante",
            ]
        )
        stats.fixture = pd.DataFrame(
            [
                {
                    "fecha": "",
                    "jornada": 1,
                    "equipo_local": "Local",
                    "equipo_visitante": "Visitante",
                }
            ]
        )
        stats.tabla = pd.DataFrame(
            [
                {
                    "zona": "Unica",
                    "posicion": 1,
                    "equipo": "Local",
                    "partidos_jugados": 0,
                    "ganados": 0,
                    "empatados": 0,
                    "perdidos": 0,
                    "gf": 0,
                    "gc": 0,
                    "dg": 0,
                    "puntos": 0,
                }
            ]
        )

        stats.validar_datos()


class PyodideDataAccessTests(unittest.TestCase):
    def test_brasileirao_uses_its_bundled_csv_names(self):
        with (
            patch.object(data_access, "usando_pyodide", return_value=True),
            patch.object(data_access.rutas, "datos_dir", return_value=Path("/virtual/datos")),
            patch.object(data_access.pd, "read_csv", side_effect=lambda path: path.name),
        ):
            result = data_access.league_data("brasileirao")

        self.assertEqual(
            result,
            (
                "resultados_brasileirao.csv",
                "fixture_brasileirao.csv",
                "tabla_brasileirao.csv",
            ),
        )


class PyodideDispatcherSmokeTests(unittest.TestCase):
    def _run_local_task(self, task):
        with patch.object(data_access, "usando_pyodide", return_value=True), patch("builtins.print"):
            return pysim_dispatch.ejecutar_tarea(task, n_sims=1)

    def test_ligapro_runs_before_the_first_played_match(self):
        result = self._run_local_task("simular-ligapro")

        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual(result["data"]["liga"], "ligapro")


if __name__ == "__main__":
    unittest.main()
