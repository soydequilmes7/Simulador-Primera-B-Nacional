# -*- coding: utf-8 -*-
"""manager_mode/test_ofertas.py

Tests del pool de ofertas de club. Ejecutar con:
    python -m unittest manager_mode.test_ofertas -v
"""
from __future__ import annotations

import random
import unittest

from manager_mode.domain import Entrenador, IdentidadTactica
from manager_mode.ofertas import (
    UMBRAL_REPUTACION_SELECCION,
    generar_pool_ofertas,
)


class TestGenerarPoolOfertas(unittest.TestCase):
    def test_pool_devuelve_la_cantidad_pedida(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.PRAGMATICO, reputacion=50.0)
        ofertas = generar_pool_ofertas(entrenador, rng=random.Random(1), cantidad=4)
        self.assertEqual(len(ofertas), 4)

    def test_pool_no_repite_clubes(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.PRAGMATICO, reputacion=50.0)
        ofertas = generar_pool_ofertas(entrenador, rng=random.Random(2), cantidad=4)
        nombres = [oferta.nombre for oferta in ofertas]
        self.assertEqual(len(nombres), len(set(nombres)))

    def test_seleccion_no_aparece_bajo_el_umbral_de_reputacion(self) -> None:
        entrenador = Entrenador(
            nombre="Marcelo", identidad=IdentidadTactica.PRAGMATICO,
            reputacion=UMBRAL_REPUTACION_SELECCION - 1,
        )
        rng = random.Random(0)
        for _ in range(50):
            ofertas = generar_pool_ofertas(entrenador, rng=rng, cantidad=4)
            self.assertNotIn("Selección Argentina", [oferta.nombre for oferta in ofertas])

    def test_seleccion_puede_aparecer_por_encima_del_umbral(self) -> None:
        entrenador = Entrenador(
            nombre="Marcelo", identidad=IdentidadTactica.PRAGMATICO, reputacion=100.0,
        )
        rng = random.Random(5)
        apariciones = sum(
            1 for _ in range(200)
            if "Selección Argentina" in [o.nombre for o in generar_pool_ofertas(entrenador, rng=rng, cantidad=7)]
        )
        self.assertGreater(apariciones, 0)

    def test_dt_reputacion_alta_recibe_mas_ofertas_de_clubes_exigentes(self) -> None:
        alta = Entrenador(nombre="A", identidad=IdentidadTactica.PRAGMATICO, reputacion=90.0)
        baja = Entrenador(nombre="B", identidad=IdentidadTactica.PRAGMATICO, reputacion=20.0)

        rng_alta = random.Random(9)
        rng_baja = random.Random(9)
        n = 200
        ofertas_river_alta = sum(
            1 for _ in range(n)
            if "River" in [o.nombre for o in generar_pool_ofertas(alta, rng=rng_alta, cantidad=4)]
        )
        ofertas_river_baja = sum(
            1 for _ in range(n)
            if "River" in [o.nombre for o in generar_pool_ofertas(baja, rng=rng_baja, cantidad=4)]
        )
        self.assertGreater(ofertas_river_alta, ofertas_river_baja)

    def test_oferta_expone_escudo_del_perfil(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.PRAGMATICO, reputacion=90.0)
        ofertas = generar_pool_ofertas(entrenador, rng=random.Random(3), cantidad=4)
        river = next((o for o in ofertas if o.nombre == "River"), None)
        if river is not None:
            self.assertEqual(river.escudo, "river.png")

    def test_oferta_seleccion_no_tiene_escudo_cargado_todavia(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.PRAGMATICO, reputacion=100.0)
        rng = random.Random(11)
        for _ in range(100):
            ofertas = generar_pool_ofertas(entrenador, rng=rng, cantidad=7)
            seleccion = next((o for o in ofertas if o.nombre == "Selección Argentina"), None)
            if seleccion is not None:
                self.assertIsNone(seleccion.escudo)
                return
        self.fail("la Seleccion nunca aparecio en 100 pooles con reputacion 100")

    def test_pool_pedido_mayor_al_catalogo_no_rompe(self) -> None:
        entrenador = Entrenador(nombre="Marcelo", identidad=IdentidadTactica.PRAGMATICO, reputacion=50.0)
        ofertas = generar_pool_ofertas(entrenador, rng=random.Random(4), cantidad=100)
        self.assertEqual(len(ofertas), 7)  # 7 perfiles no-seleccion en el catalogo


if __name__ == "__main__":
    unittest.main()
