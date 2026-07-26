# -*- coding: utf-8 -*-
"""
tests/test_actualizar_resultados_lpf_autosync.py

Cubre la integración del auto-sync (calcular_filas_nuevas) dentro de
actualizar_resultados_lpf.actualizar() -- a partir de acá corre solo en
cada actualización, sin que haga falta acordarse de correr
sincronizar_fixture_clausura_lpf.py a mano en cada transición de fase.

Usa un repo falso en memoria (sin Supabase real) para poder testear el
flujo completo de la función, no solo la lógica pura de
calcular_filas_nuevas() (esa ya está cubierta en
tests/test_sincronizar_fixture_clausura_lpf.py).
"""
from __future__ import annotations

import unittest
from contextlib import contextmanager
from unittest.mock import patch

import actualizar_resultados_lpf as modulo


class _FakeRepoLPF:
    """Repo en memoria: implementa solo lo que actualizar() necesita de
    la interfaz real de db.repository.Repository."""

    def __init__(self, pending: list[dict], played: list[dict]) -> None:
        self._pending = pending
        self._played = played
        self.replace_calls: list[tuple[list[dict], list[dict]]] = []
        self.log_calls: list[dict] = []

    def match_records(self, slug: str, status: str) -> list[dict]:
        assert slug == "lpf"
        return list(self._pending if status == "pending" else self._played)

    def replace_matches(self, slug: str, pending: list[dict], played: list[dict]) -> None:
        assert slug == "lpf"
        self.replace_calls.append((list(pending), list(played)))
        self._pending = list(pending)
        self._played = list(played)

    def apply_club_rating_events(self, *args, **kwargs) -> int:
        return 0

    def log_update(self, *args, **kwargs) -> None:
        self.log_calls.append({"args": args, "kwargs": kwargs})


def _patch_transaction(fake_repo: _FakeRepoLPF):
    @contextmanager
    def _fake_transaction():
        yield fake_repo
    return patch.object(modulo, "transaction", _fake_transaction)


class AutoSyncFixtureLPFTests(unittest.TestCase):

    def test_persiste_fixture_nuevo_aunque_no_haya_resultados_para_cargar(self) -> None:
        # Apertura ya jugado (played), sin nada pendiente todavía (el
        # Clausura recién arranca y Promiedos no tiene ningún resultado
        # cargado para él en este momento puntual).
        played = [{"fecha": "", "jornada": 1, "equipo_local": "Sarmiento Junín",
                   "equipo_visitante": "Argentinos Juniors", "goles_local": 1, "goles_visitante": 0}]
        fake_repo = _FakeRepoLPF(pending=[], played=played)
        filas_nuevas = [{"fecha": "", "jornada": 2, "equipo_local": "Sarmiento Junín",
                          "equipo_visitante": "Argentinos Juniors"}]

        with _patch_transaction(fake_repo), \
             patch.object(modulo, "obtener_partidos_jugados_lpf", return_value=[]), \
             patch.object(modulo, "calcular_filas_nuevas", return_value=(filas_nuevas, 1)):
            resultado = modulo.actualizar(imprimir=False)

        self.assertFalse(resultado["actualizado"])  # no se cargó ningún resultado nuevo
        self.assertEqual(resultado["fixture_sincronizado"], 1)
        # Pero el fixture nuevo SÍ se persistió, aunque cargados esté vacío.
        self.assertEqual(len(fake_repo.replace_calls), 1)
        pending_guardado, played_guardado = fake_repo.replace_calls[0]
        self.assertEqual(pending_guardado, filas_nuevas)
        self.assertEqual(played_guardado, played)  # el historial del Apertura no se tocó

    def test_partido_del_clausura_matchea_en_la_misma_corrida_que_se_sincroniza(self) -> None:
        # Caso real completo: el fixture nuevo aparece Y Promiedos ya
        # tiene el resultado -- todo en la misma corrida, sin pasos
        # manuales intermedios.
        played_previo = [{"fecha": "", "jornada": 1, "equipo_local": "Sarmiento Junín",
                           "equipo_visitante": "Argentinos Juniors", "goles_local": 1, "goles_visitante": 0}]
        fake_repo = _FakeRepoLPF(pending=[], played=played_previo)
        filas_nuevas = [{"fecha": "", "jornada": 2, "equipo_local": "Sarmiento Junín",
                          "equipo_visitante": "Argentinos Juniors"}]
        partido_jugado = {"equipo_local": "Sarmiento Junín", "equipo_visitante": "Argentinos Juniors",
                           "goles_local": 2, "goles_visitante": 1,
                           "goleadores_local": {}, "goleadores_visitante": {}}

        with _patch_transaction(fake_repo), \
             patch.object(modulo, "obtener_partidos_jugados_lpf", return_value=[partido_jugado]), \
             patch.object(modulo, "calcular_filas_nuevas", return_value=(filas_nuevas, 1)):
            resultado = modulo.actualizar(imprimir=False)

        self.assertTrue(resultado["actualizado"])
        self.assertEqual(len(resultado["cargados"]), 1)
        self.assertEqual(resultado["sin_matchear"], [])  # el bug real: esto daba 1, no 0
        self.assertEqual(resultado["fixture_sincronizado"], 1)

        pending_guardado, played_guardado = fake_repo.replace_calls[-1]
        self.assertEqual(pending_guardado, [])  # se consumió, no queda pendiente
        self.assertEqual(len(played_guardado), 2)  # Apertura (previo) + Clausura (nuevo)


if __name__ == "__main__":
    unittest.main()
