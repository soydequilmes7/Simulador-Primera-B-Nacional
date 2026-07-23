# -*- coding: utf-8 -*-
"""manager_mode/test_domain.py

Tests de dominio del Modo DT. Ejecutar con:
    python -m unittest manager_mode.test_domain -v
"""
from __future__ import annotations

import unittest

from manager_mode.domain import (
    CATALOGO_LOGROS,
    Contrato,
    Entrenador,
    IdentidadTactica,
    ObjetivoTemporada,
    RecordEntrenador,
)


class TestContrato(unittest.TestCase):
    def test_avanzar_temporada_descuenta_un_anio(self) -> None:
        contrato = Contrato(club_id=1, temporadas_restantes=2, sueldo=1000.0)
        contrato.avanzar_temporada()
        self.assertEqual(contrato.temporadas_restantes, 1)
        self.assertFalse(contrato.vencido)

    def test_avanzar_temporada_no_baja_de_cero(self) -> None:
        contrato = Contrato(club_id=1, temporadas_restantes=0, sueldo=1000.0)
        contrato.avanzar_temporada()
        self.assertEqual(contrato.temporadas_restantes, 0)
        self.assertTrue(contrato.vencido)

    def test_renovar_suma_temporadas(self) -> None:
        contrato = Contrato(club_id=1, temporadas_restantes=1, sueldo=1000.0)
        contrato.renovar(2)
        self.assertEqual(contrato.temporadas_restantes, 3)

    def test_renovar_con_valor_invalido_lanza_error(self) -> None:
        contrato = Contrato(club_id=1, temporadas_restantes=1, sueldo=1000.0)
        with self.assertRaises(ValueError):
            contrato.renovar(0)

    def test_objetivos_por_defecto_vacios(self) -> None:
        contrato = Contrato(club_id=1, temporadas_restantes=1, sueldo=1000.0)
        self.assertEqual(contrato.objetivos, [])


class TestRecordEntrenador(unittest.TestCase):
    def test_registrar_victoria(self) -> None:
        record = RecordEntrenador()
        record.registrar_resultado(goles_propios=2, goles_rival=1)
        self.assertEqual(record.victorias, 1)
        self.assertEqual(record.partidos_jugados, 1)

    def test_registrar_empate(self) -> None:
        record = RecordEntrenador()
        record.registrar_resultado(goles_propios=1, goles_rival=1)
        self.assertEqual(record.empates, 1)

    def test_registrar_derrota(self) -> None:
        record = RecordEntrenador()
        record.registrar_resultado(goles_propios=0, goles_rival=2)
        self.assertEqual(record.derrotas, 1)


class TestEntrenador(unittest.TestCase):
    def test_entrenador_nuevo_esta_libre(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.OFENSIVO)
        self.assertTrue(entrenador.libre)

    def test_firmar_contrato_deja_de_estar_libre(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.OFENSIVO)
        entrenador.firmar_contrato(Contrato(club_id=5, temporadas_restantes=2, sueldo=500.0))
        self.assertFalse(entrenador.libre)
        self.assertEqual(entrenador.contrato.club_id, 5)

    def test_firmar_nuevo_contrato_registra_historial(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.PRAGMATICO)
        entrenador.firmar_contrato(Contrato(club_id=1, temporadas_restantes=1, sueldo=100.0))
        entrenador.firmar_contrato(Contrato(club_id=2, temporadas_restantes=1, sueldo=200.0))
        self.assertEqual(entrenador.historial_clubes, [1])
        self.assertEqual(entrenador.contrato.club_id, 2)

    def test_sumar_titulo_sube_reputacion_sin_pasar_100(self) -> None:
        entrenador = Entrenador(
            nombre="Marcelo", identidad=IdentidadTactica.MOTIVADOR, reputacion=95.0,
        )
        entrenador.sumar_titulo("Campeón LPF 2026", bonus_reputacion=10.0)
        self.assertEqual(entrenador.reputacion, 100.0)
        self.assertEqual(entrenador.titulos, ["Campeón LPF 2026"])

    def test_modificador_tactico_segun_identidad(self) -> None:
        formador = Entrenador(nombre="Pedro", identidad=IdentidadTactica.FORMADOR)
        self.assertGreater(formador.modificador_tactico.peso_eventos_juveniles, 1.0)

    def test_objetivo_temporada_cumplido_por_defecto_none(self) -> None:
        objetivo = ObjetivoTemporada(descripcion="Ascender")
        self.assertIsNone(objetivo.cumplido)

    def test_entrenador_arranca_con_30_anios(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.PRAGMATICO)
        self.assertEqual(entrenador.edad, 30)
        self.assertFalse(entrenador.retirado)

    def test_avanzar_edad_suma_un_anio(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.PRAGMATICO)
        entrenador.avanzar_edad()
        self.assertEqual(entrenador.edad, 31)

    def test_avanzar_edad_devuelve_true_al_llegar_al_retiro(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.PRAGMATICO, edad=74)
        retirado = entrenador.avanzar_edad()
        self.assertTrue(retirado)
        self.assertEqual(entrenador.edad, 75)
        self.assertTrue(entrenador.retirado)

    def test_retirado_es_false_antes_de_los_75(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.PRAGMATICO, edad=74)
        self.assertFalse(entrenador.retirado)

    def test_desbloquear_logro_valido_devuelve_true_una_sola_vez(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.REVOLUCIONARIO)
        self.assertTrue(entrenador.desbloquear_logro("rey_del_ascenso"))
        self.assertFalse(entrenador.desbloquear_logro("rey_del_ascenso"))
        self.assertEqual(entrenador.logros_desbloqueados, ["rey_del_ascenso"])

    def test_desbloquear_logro_inexistente_devuelve_false(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.PRAGMATICO)
        self.assertFalse(entrenador.desbloquear_logro("logro_que_no_existe"))
        self.assertEqual(entrenador.logros_desbloqueados, [])

    def test_catalogo_logros_tiene_codigo_consistente_con_su_clave(self) -> None:
        for codigo, logro in CATALOGO_LOGROS.items():
            self.assertEqual(codigo, logro.codigo)


if __name__ == "__main__":
    unittest.main()
