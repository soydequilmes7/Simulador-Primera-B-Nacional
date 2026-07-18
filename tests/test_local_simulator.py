import unittest
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import data_access
import pysim_dispatch
from api.index import PYSIM_SOURCE_FILES as API_PYSIM_SOURCE_FILES
from modelos.estadisticas import Estadisticas
from servidor import PYSIM_SOURCE_FILES as LOCAL_PYSIM_SOURCE_FILES


ROOT = Path(__file__).resolve().parent.parent


class PyodideSourceBundleTests(unittest.TestCase):
    def test_api_and_local_server_publish_the_same_importable_bundle(self):
        self.assertEqual(API_PYSIM_SOURCE_FILES, LOCAL_PYSIM_SOURCE_FILES)

        with tempfile.TemporaryDirectory() as tmp:
            bundle_root = Path(tmp)
            for relative_name in API_PYSIM_SOURCE_FILES:
                source_path = ROOT / relative_name
                target_path = bundle_root / relative_name
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")

            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            completed = subprocess.run(
                [sys.executable, "-c", "import pysim_dispatch"],
                cwd=bundle_root,
                env=env,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)


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
