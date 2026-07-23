# -*- coding: utf-8 -*-
"""manager_mode/test_dirigencia.py

Tests del sistema de dirigencia. Ejecutar con:
    python -m unittest manager_mode.test_dirigencia -v
"""
from __future__ import annotations

import random
import unittest

from manager_mode.dirigencia import (
    CATALOGO_PERFILES_CLUB,
    DecisionContinuidad,
    EvaluadorDirigenciaService,
    ResultadoTemporada,
    TipoObjetivo,
    crear_objetivo,
    generar_objetivos_temporada,
)
from manager_mode.domain import Contrato, Entrenador, IdentidadTactica
from manager_mode.eventos import EstadoClub


class TestGenerarObjetivos(unittest.TestCase):
    def test_river_genera_objetivos_de_su_pool(self) -> None:
        perfil = CATALOGO_PERFILES_CLUB["River"]
        objetivos = generar_objetivos_temporada(perfil, rng=random.Random(1), cantidad=2)
        self.assertEqual(len(objetivos), 2)
        tipos_generados = {o.tipo for o in objetivos}
        tipos_posibles = {t.value for t in perfil.objetivos_posibles}
        self.assertTrue(tipos_generados.issubset(tipos_posibles))

    def test_no_genera_objetivos_repetidos(self) -> None:
        perfil = CATALOGO_PERFILES_CLUB["River"]
        objetivos = generar_objetivos_temporada(perfil, rng=random.Random(2), cantidad=3)
        descripciones = [o.descripcion for o in objetivos]
        self.assertEqual(len(descripciones), len(set(descripciones)))

    def test_perfil_con_un_solo_objetivo_no_rompe_con_cantidad_mayor(self) -> None:
        perfil = CATALOGO_PERFILES_CLUB["Temperley"]
        objetivos = generar_objetivos_temporada(perfil, rng=random.Random(3), cantidad=2)
        self.assertEqual(len(objetivos), 1)


class TestEvaluadorDirigenciaService(unittest.TestCase):
    def setUp(self) -> None:
        self.evaluador = EvaluadorDirigenciaService()

    def test_evaluar_objetivo_sin_tipo_lanza_value_error(self) -> None:
        from manager_mode.domain import ObjetivoTemporada

        objetivo = ObjetivoTemporada(descripcion="Objetivo narrativo sin tipo")
        resultado = ResultadoTemporada(posicion_final=1, total_equipos=20)
        with self.assertRaises(ValueError):
            self.evaluador.evaluar_objetivo(objetivo, resultado)

    def test_salir_campeon_cumplido(self) -> None:
        objetivo = crear_objetivo(TipoObjetivo.SALIR_CAMPEON)
        resultado = ResultadoTemporada(posicion_final=1, total_equipos=20, gano_titulo=True)
        self.assertTrue(self.evaluador.evaluar_objetivo(objetivo, resultado))
        self.assertTrue(objetivo.cumplido)

    def test_ascender_incumplido(self) -> None:
        objetivo = crear_objetivo(TipoObjetivo.ASCENDER)
        resultado = ResultadoTemporada(posicion_final=5, total_equipos=20, ascendio=False)
        self.assertFalse(self.evaluador.evaluar_objetivo(objetivo, resultado))
        self.assertFalse(objetivo.cumplido)

    def test_river_descendido_es_despido_automatico(self) -> None:
        perfil = CATALOGO_PERFILES_CLUB["River"]
        objetivos = [crear_objetivo(TipoObjetivo.SALIR_CAMPEON)]
        resultado = ResultadoTemporada(posicion_final=19, total_equipos=20, descendio=True)
        estado = EstadoClub(confianza=90.0)
        evaluacion = self.evaluador.evaluar_temporada(objetivos, resultado, perfil, estado)
        self.assertEqual(evaluacion.decision, DecisionContinuidad.DESPEDIR)

    def test_temperley_no_descender_alcanza_para_renovar(self) -> None:
        perfil = CATALOGO_PERFILES_CLUB["Temperley"]
        objetivos = [crear_objetivo(TipoObjetivo.CONSOLIDARSE)]
        resultado = ResultadoTemporada(posicion_final=10, total_equipos=20, descendio=False)
        estado = EstadoClub(confianza=70.0)
        evaluacion = self.evaluador.evaluar_temporada(objetivos, resultado, perfil, estado)
        self.assertEqual(evaluacion.decision, DecisionContinuidad.RENOVAR)

    def test_river_cumpliendo_todo_renueva(self) -> None:
        perfil = CATALOGO_PERFILES_CLUB["River"]
        objetivos = [
            crear_objetivo(TipoObjetivo.SALIR_CAMPEON),
            crear_objetivo(TipoObjetivo.SEMIFINAL_COPA_CONTINENTAL),
        ]
        resultado = ResultadoTemporada(
            posicion_final=1, total_equipos=20,
            gano_titulo=True, llego_semifinal_copa_continental=True,
        )
        estado = EstadoClub(confianza=90.0)
        evaluacion = self.evaluador.evaluar_temporada(objetivos, resultado, perfil, estado)
        self.assertEqual(evaluacion.objetivos_cumplidos, 2)
        self.assertEqual(evaluacion.decision, DecisionContinuidad.RENOVAR)

    def test_aplicar_decision_renovar_extiende_contrato_y_sube_reputacion(self) -> None:
        entrenador = Entrenador(
            nombre="Marcelo", identidad=IdentidadTactica.PRAGMATICO, reputacion=50.0,
        )
        entrenador.firmar_contrato(Contrato(club_id=1, temporadas_restantes=1, sueldo=1000.0))
        evaluacion = self.evaluador.evaluar_temporada(
            [crear_objetivo(TipoObjetivo.CONSOLIDARSE)],
            ResultadoTemporada(posicion_final=5, total_equipos=20, descendio=False),
            CATALOGO_PERFILES_CLUB["Temperley"],
            EstadoClub(confianza=70.0),
        )
        self.evaluador.aplicar_decision(entrenador, evaluacion)
        self.assertEqual(entrenador.contrato.temporadas_restantes, 2)
        self.assertEqual(entrenador.reputacion, 55.0)

    def test_aplicar_decision_despedir_libera_al_entrenador(self) -> None:
        entrenador = Entrenador(
            nombre="Marcelo", identidad=IdentidadTactica.PRAGMATICO, reputacion=50.0,
        )
        entrenador.firmar_contrato(Contrato(club_id=1, temporadas_restantes=1, sueldo=1000.0))
        evaluacion = self.evaluador.evaluar_temporada(
            [crear_objetivo(TipoObjetivo.SALIR_CAMPEON)],
            ResultadoTemporada(posicion_final=19, total_equipos=20, descendio=True),
            CATALOGO_PERFILES_CLUB["River"],
            EstadoClub(confianza=90.0),
        )
        self.evaluador.aplicar_decision(entrenador, evaluacion)
        self.assertTrue(entrenador.libre)
        self.assertEqual(entrenador.historial_clubes, [1])
        self.assertEqual(entrenador.reputacion, 40.0)


if __name__ == "__main__":
    unittest.main()
