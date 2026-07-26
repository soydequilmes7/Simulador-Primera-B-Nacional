# -*- coding: utf-8 -*-
"""
tests/test_sincronizar_fixture_clausura_lpf.py

Cubre calcular_filas_nuevas() (sincronizar_fixture_clausura_lpf.py):
caso real reportado por Pablo (22/07/2026 -- 9 partidos sin identificar
en LPF, Clausura arrancó con las mismas parejas de equipos y la misma
numeración de "Fecha N" que usó el Apertura, ver docstring del módulo).
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from sincronizar_fixture_clausura_lpf import calcular_filas_nuevas


def _pendiente(jornada, local, visitante):
    return {"fecha": "", "jornada": jornada, "equipo_local": local, "equipo_visitante": visitante}


def _promiedos(jornada, local, visitante, jugado):
    return {
        "jornada": jornada, "equipo_local": local, "equipo_visitante": visitante,
        "jugado": jugado, "goles_local": 1 if jugado else None, "goles_visitante": 0 if jugado else None,
        "estado": "", "fecha_hora": "",
    }


class CalcularFilasNuevasTests(unittest.TestCase):

    def test_caso_real_clausura_mismo_par_que_apertura(self) -> None:
        # El Apertura ya jugó Fecha 1 (Sarmiento Junín vs Argentinos
        # Juniors) hace meses -- está en "jugados", no en "pending".
        jugados_actual = [_pendiente(1, "Sarmiento Junín", "Argentinos Juniors")]
        pending_actual = []  # Apertura ya se jugó completo, no queda nada pendiente

        # Promiedos ahora reporta la MISMA pareja como pendiente (jugado=False
        # todavía) bajo "Fecha 1" otra vez -- es el Clausura.
        with patch("sincronizar_fixture_clausura_lpf.obtener_partidos_lpf",
                   return_value=[_promiedos(1, "Sarmiento Junín", "Argentinos Juniors", jugado=False)]):
            filas_nuevas, offset = calcular_filas_nuevas(pending_actual, jugados_actual)

        self.assertEqual(offset, 1)  # jornada máxima ya usada (por el Apertura jugado)
        self.assertEqual(len(filas_nuevas), 1)
        self.assertEqual(filas_nuevas[0]["jornada"], 2)  # offset(1) + jornada de Promiedos(1)
        self.assertEqual(filas_nuevas[0]["equipo_local"], "Sarmiento Junín")
        self.assertEqual(filas_nuevas[0]["equipo_visitante"], "Argentinos Juniors")

    def test_partido_ya_jugado_en_promiedos_SI_se_agrega_si_no_esta_cargado(self) -> None:
        # Este es el bug real reportado por Pablo (26/07/2026, después
        # de mergear el primer fix): para cuando se corre "Actualizar
        # Resultados", el partido del Clausura casi siempre YA está
        # jugado en Promiedos -- si lo descartáramos acá, nunca se
        # crea la fila de fixture que el matcheo principal necesita.
        with patch("sincronizar_fixture_clausura_lpf.obtener_partidos_lpf",
                   return_value=[_promiedos(1, "Boca Juniors", "River Plate", jugado=True)]):
            filas_nuevas, _ = calcular_filas_nuevas([], [])
        self.assertEqual(len(filas_nuevas), 1)
        self.assertEqual(filas_nuevas[0]["equipo_local"], "Boca Juniors")
        self.assertEqual(filas_nuevas[0]["equipo_visitante"], "River Plate")

    def test_partido_jugado_con_mismo_marcador_ya_cargado_no_se_duplica(self) -> None:
        # Si Promiedos sigue mostrando en su ventana un partido del
        # Apertura que YA está en resultados con el MISMO marcador,
        # no hay que crear una fila de fixture nueva para él (sería
        # un duplicado del mismo partido histórico, no uno nuevo).
        jugados_actual = [{"jornada": 1, "equipo_local": "Boca Juniors", "equipo_visitante": "River Plate",
                            "goles_local": 2, "goles_visitante": 1}]
        partido_promiedos = _promiedos(1, "Boca Juniors", "River Plate", jugado=True)
        partido_promiedos["goles_local"], partido_promiedos["goles_visitante"] = 2, 1
        with patch("sincronizar_fixture_clausura_lpf.obtener_partidos_lpf", return_value=[partido_promiedos]):
            filas_nuevas, _ = calcular_filas_nuevas([], jugados_actual)
        self.assertEqual(filas_nuevas, [])

    def test_partido_jugado_con_marcador_distinto_al_ya_cargado_se_agrega(self) -> None:
        # Mismos equipos, pero un marcador que nunca se cargó -- es el
        # partido de la revancha (Clausura), no el mismo de antes.
        jugados_actual = [{"jornada": 1, "equipo_local": "Boca Juniors", "equipo_visitante": "River Plate",
                            "goles_local": 2, "goles_visitante": 1}]
        partido_promiedos = _promiedos(1, "Boca Juniors", "River Plate", jugado=True)
        partido_promiedos["goles_local"], partido_promiedos["goles_visitante"] = 0, 0
        with patch("sincronizar_fixture_clausura_lpf.obtener_partidos_lpf", return_value=[partido_promiedos]):
            filas_nuevas, _ = calcular_filas_nuevas([], jugados_actual)
        self.assertEqual(len(filas_nuevas), 1)

    def test_partido_ya_en_fixture_pendiente_no_se_duplica(self) -> None:
        # Idempotencia: correr el script dos veces no debe duplicar filas.
        pending_actual = [_pendiente(2, "Sarmiento Junín", "Argentinos Juniors")]
        with patch("sincronizar_fixture_clausura_lpf.obtener_partidos_lpf",
                   return_value=[_promiedos(1, "Sarmiento Junín", "Argentinos Juniors", jugado=False)]):
            filas_nuevas, _ = calcular_filas_nuevas(pending_actual, [])
        self.assertEqual(filas_nuevas, [])

    def test_offset_toma_el_maximo_entre_jugados_y_pendientes(self) -> None:
        jugados_actual = [_pendiente(14, "Boca Juniors", "River Plate")]
        pending_actual = [_pendiente(16, "Talleres de Córdoba", "Instituto")]  # remanente Apertura sin jugar
        with patch("sincronizar_fixture_clausura_lpf.obtener_partidos_lpf",
                   return_value=[_promiedos(1, "Huracán", "Banfield", jugado=False)]):
            filas_nuevas, offset = calcular_filas_nuevas(pending_actual, jugados_actual)
        self.assertEqual(offset, 16)  # el máximo de los dos, no solo de jugados
        self.assertEqual(filas_nuevas[0]["jornada"], 17)

    def test_resuelve_nombres_no_canonicos_de_promiedos(self) -> None:
        # Si Promiedos manda el nombre corto en vez del canónico de
        # fixture_lpf.csv, resolver_equipo_lpf lo normaliza.
        with patch("sincronizar_fixture_clausura_lpf.obtener_partidos_lpf",
                   return_value=[_promiedos(1, "River", "Racing", jugado=False)]):
            filas_nuevas, _ = calcular_filas_nuevas([], [])
        self.assertEqual(filas_nuevas[0]["equipo_local"], "River Plate")
        self.assertEqual(filas_nuevas[0]["equipo_visitante"], "Racing Club")


if __name__ == "__main__":
    unittest.main()
