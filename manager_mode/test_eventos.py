# -*- coding: utf-8 -*-
"""manager_mode/test_eventos.py

Tests del catálogo de eventos, EstadoClub y EventoService. Ejecutar con:
    python -m unittest manager_mode.test_eventos -v
"""
from __future__ import annotations

import random
import unittest

from manager_mode.domain import Entrenador, IdentidadTactica
from manager_mode.eventos import (
    CATALOGO_EVENTOS,
    CategoriaEvento,
    Efecto,
    EstadoClub,
    eventos_por_categoria,
)
from manager_mode.evento_service import EventoService
from manager_mode.narrativa import NarrativaService


class TestCatalogoEventos(unittest.TestCase):
    def test_catalogo_no_esta_vacio(self) -> None:
        self.assertGreater(len(CATALOGO_EVENTOS), 40)

    def test_todos_los_eventos_tienen_entre_2_y_3_opciones(self) -> None:
        for evento in CATALOGO_EVENTOS.values():
            self.assertIn(len(evento.opciones), (2, 3), msg=evento.codigo)

    def test_todas_las_categorias_tienen_al_menos_un_evento(self) -> None:
        for categoria in CategoriaEvento:
            self.assertGreater(len(eventos_por_categoria(categoria)), 0, msg=categoria)

    def test_codigos_de_evento_son_unicos(self) -> None:
        codigos = [evento.codigo for evento in CATALOGO_EVENTOS.values()]
        self.assertEqual(len(codigos), len(set(codigos)))

    def test_opcion_inexistente_lanza_key_error(self) -> None:
        evento = CATALOGO_EVENTOS["el_capitan"]
        with self.assertRaises(KeyError):
            evento.opcion("opcion_que_no_existe")


class TestEfecto(unittest.TestCase):
    def test_efecto_con_variable_invalida_lanza_value_error(self) -> None:
        with self.assertRaises(ValueError):
            Efecto(variable="variable_inventada", delta=5)


class TestEstadoClub(unittest.TestCase):
    def test_aplicar_efectos_suma_deltas(self) -> None:
        estado = EstadoClub()
        estado.aplicar((Efecto("moral", 10), Efecto("vestuario", -5)))
        self.assertEqual(estado.moral, 60.0)
        self.assertEqual(estado.vestuario, 45.0)

    def test_variables_0_100_se_clampean(self) -> None:
        estado = EstadoClub(moral=95.0, vestuario=3.0)
        estado.aplicar((Efecto("moral", 20), Efecto("vestuario", -10)))
        self.assertEqual(estado.moral, 100.0)
        self.assertEqual(estado.vestuario, 0.0)

    def test_presupuesto_no_se_clampea(self) -> None:
        estado = EstadoClub(presupuesto=100.0)
        estado.aplicar((Efecto("presupuesto", -5000),))
        self.assertEqual(estado.presupuesto, -4900.0)


class TestEventoService(unittest.TestCase):
    def setUp(self) -> None:
        rng = random.Random(3)
        self.service = EventoService(rng=rng, narrativa=NarrativaService(rng=rng))
        self.contexto = {"club": "Quilmes", "rival": "Boca", "entrenador": "Marcelo"}

    def test_elegir_evento_sin_categoria_devuelve_algo_del_catalogo(self) -> None:
        evento = self.service.elegir_evento()
        self.assertIn(evento.codigo, CATALOGO_EVENTOS)

    def test_elegir_evento_con_categoria_respeta_la_categoria(self) -> None:
        evento = self.service.elegir_evento(CategoriaEvento.VIDA_PLANTEL)
        self.assertEqual(evento.categoria, CategoriaEvento.VIDA_PLANTEL)

    def test_resolver_opcion_aplica_efectos_sobre_el_estado(self) -> None:
        estado = EstadoClub()
        evento = CATALOGO_EVENTOS["el_capitan"]
        self.service.resolver_opcion(estado, evento, "hablar", self.contexto)
        self.assertEqual(estado.vestuario, 56.0)

    def test_resolver_opcion_con_reaccion_devuelve_frase_interpolada(self) -> None:
        estado = EstadoClub()
        evento = CATALOGO_EVENTOS["el_capitan"]
        frase = self.service.resolver_opcion(estado, evento, "sacar_cinta", self.contexto)
        self.assertIsNotNone(frase)
        self.assertNotIn("{", frase)

    def test_resolver_opcion_sin_reaccion_devuelve_none(self) -> None:
        estado = EstadoClub()
        evento = CATALOGO_EVENTOS["vuelo_cancelado"]
        frase = self.service.resolver_opcion(estado, evento, "aceptar", self.contexto)
        self.assertIsNone(frase)

    def test_formador_ve_mas_eventos_de_juveniles_que_sin_ponderar(self) -> None:
        formador = Entrenador(nombre="Pedro", identidad=IdentidadTactica.FORMADOR)
        rng_ponderado = random.Random(123)
        rng_sin_ponderar = random.Random(123)
        service_ponderado = EventoService(rng=rng_ponderado)
        service_sin_ponderar = EventoService(rng=rng_sin_ponderar)

        n = 300
        conteo_ponderado = sum(
            1 for _ in range(n)
            if service_ponderado.elegir_evento(entrenador=formador).categoria == CategoriaEvento.JUVENILES
        )
        conteo_sin_ponderar = sum(
            1 for _ in range(n)
            if service_sin_ponderar.elegir_evento().categoria == CategoriaEvento.JUVENILES
        )
        self.assertGreater(conteo_ponderado, conteo_sin_ponderar)

    def test_elegir_evento_con_categoria_ignora_ponderacion_por_identidad(self) -> None:
        formador = Entrenador(nombre="Pedro", identidad=IdentidadTactica.FORMADOR)
        evento = self.service.elegir_evento(categoria=CategoriaEvento.MERCADO, entrenador=formador)
        self.assertEqual(evento.categoria, CategoriaEvento.MERCADO)

    def test_sin_club_clasifica_copas_nunca_sale_libertadores_ni_sudamericana(self) -> None:
        rng = random.Random(17)
        service = EventoService(rng=rng)
        for _ in range(300):
            evento = service.elegir_evento()
            self.assertNotIn(evento.categoria, (CategoriaEvento.LIBERTADORES, CategoriaEvento.SUDAMERICANA))

    def test_con_club_clasifica_copas_pueden_salir_esas_categorias(self) -> None:
        rng = random.Random(23)
        service = EventoService(rng=rng)
        categorias_vistas = {
            service.elegir_evento(
                club_clasifica_libertadores=True, club_clasifica_sudamericana=True,
            ).categoria
            for _ in range(300)
        }
        self.assertTrue(
            {CategoriaEvento.LIBERTADORES, CategoriaEvento.SUDAMERICANA} & categorias_vistas
        )

    def test_solo_sudamericana_habilitada_no_saca_libertadores(self) -> None:
        rng = random.Random(29)
        service = EventoService(rng=rng)
        for _ in range(300):
            evento = service.elegir_evento(club_clasifica_sudamericana=True)
            self.assertNotEqual(evento.categoria, CategoriaEvento.LIBERTADORES)

    def test_categoria_explicita_libertadores_funciona_sin_flag(self) -> None:
        evento = self.service.elegir_evento(categoria=CategoriaEvento.LIBERTADORES)
        self.assertEqual(evento.categoria, CategoriaEvento.LIBERTADORES)


if __name__ == "__main__":
    unittest.main()
