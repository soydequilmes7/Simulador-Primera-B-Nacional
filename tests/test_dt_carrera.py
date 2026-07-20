# -*- coding: utf-8 -*-
"""
tests/test_dt_carrera.py

Cubre los tres bloques de season/dt_carrera.py. El foco está en los
invariantes que no pueden romperse sin arruinar el diseño:
  - las ofertas de clubes nunca superan el techo de prestigio de la
    reputación del DT;
  - evaluar_temporada despide al segundo objetivo fallido seguido, no
    antes ni después;
  - generar_cronologia siempre llega EXACTO al marcador que se le pasó
    (esto es lo que garantiza que la narración nunca pueda desviarse
    del resultado real que alimenta la tabla de posiciones).
"""
from __future__ import annotations

import random
import unittest

import numpy as np

from season.club_registry import ClubRegistry
from season.dt_carrera import (
    CategoriaFichaje,
    ClubCandidato,
    DTState,
    Formacion,
    Mentalidad,
    ResultadoPartidoDT,
    TipoObjetivo,
    ajustar_lambdas,
    candidatos_desde_registry,
    evaluar_temporada,
    fichar,
    generar_cronologia,
    generar_objetivo,
    jugar_partido_dt,
    lambda_partido,
    objetivo_cumplido,
    ofertas_de_clubes,
    rating_por_prestigio,
    resolver_partido,
    techo_prestigio_para,
)


class TestOfertasDeClubes(unittest.TestCase):
    def setUp(self):
        self.candidatos = [
            ClubCandidato("Chico A", "primerac", 0.0),
            ClubCandidato("Chico B", "bmetro", 0.02),
            ClubCandidato("Mediano", "nacional", 0.12),
            ClubCandidato("Grande", "lpf", 0.35),
            ClubCandidato("Gigante", "lpf", 0.50),
        ]

    def test_reputacion_baja_no_recibe_clubes_grandes(self):
        rng = random.Random(1)
        for _ in range(50):
            ofertas = ofertas_de_clubes(reputacion=5, candidatos=self.candidatos, cantidad=3, rng=rng)
            for club in ofertas:
                self.assertLessEqual(club.factor_prestigio, techo_prestigio_para(5))

    def test_reputacion_alta_puede_recibir_cualquier_club(self):
        rng = random.Random(2)
        vistos = set()
        for _ in range(200):
            for club in ofertas_de_clubes(reputacion=100, candidatos=self.candidatos, cantidad=5, rng=rng):
                vistos.add(club.nombre)
        self.assertIn("Gigante", vistos)

    def test_sin_candidatos_elegibles_devuelve_vacio(self):
        ofertas = ofertas_de_clubes(reputacion=0, candidatos=[ClubCandidato("Gigante", "lpf", 0.5)])
        self.assertEqual(ofertas, [])

    def test_no_repite_el_mismo_club_en_una_tanda(self):
        rng = random.Random(3)
        ofertas = ofertas_de_clubes(reputacion=100, candidatos=self.candidatos, cantidad=5, rng=rng)
        nombres = [c.nombre for c in ofertas]
        self.assertEqual(len(nombres), len(set(nombres)))


class TestObjetivosYEvaluacion(unittest.TestCase):
    def test_club_grande_pide_pelear_el_titulo(self):
        club = ClubCandidato("Gigante", "lpf", 0.45)
        self.assertEqual(generar_objetivo(club, rng=random.Random(1)), TipoObjetivo.PELEAR_TITULO)

    def test_club_chico_con_ascenso_no_pide_pelear_titulo(self):
        rng = random.Random(4)
        club = ClubCandidato("Chico", "primerac", 0.0)
        for _ in range(30):
            objetivo = generar_objetivo(club, rng=rng)
            self.assertIn(objetivo, (TipoObjetivo.EVITAR_DESCENSO, TipoObjetivo.MITAD_TABLA))

    def test_cumplir_objetivo_nunca_despide(self):
        evaluacion = evaluar_temporada(TipoObjetivo.EVITAR_DESCENSO, cumplido=True, temporadas_fallidas_seguidas_previas=5)
        self.assertFalse(evaluacion.despedido)
        self.assertGreater(evaluacion.delta_reputacion, 0)

    def test_despide_recien_en_la_segunda_fallida_seguida(self):
        primera = evaluar_temporada(TipoObjetivo.PLAYOFFS, cumplido=False, temporadas_fallidas_seguidas_previas=0)
        self.assertFalse(primera.despedido)
        segunda = evaluar_temporada(TipoObjetivo.PLAYOFFS, cumplido=False, temporadas_fallidas_seguidas_previas=1)
        self.assertTrue(segunda.despedido)

    def test_dtstate_resetea_contador_de_fallidas_al_cumplir(self):
        estado = DTState(reputacion=20)
        estado.aplicar_resultado("Club X", TipoObjetivo.PLAYOFFS, cumplido=False)
        self.assertEqual(estado.temporadas_fallidas_seguidas, 1)
        estado.aplicar_resultado("Club X", TipoObjetivo.PLAYOFFS, cumplido=True)
        self.assertEqual(estado.temporadas_fallidas_seguidas, 0)
        self.assertEqual(len(estado.historial), 2)

    def test_dtstate_queda_libre_al_ser_despedido(self):
        estado = DTState(reputacion=20, club_actual="Club X")
        estado.aplicar_resultado("Club X", TipoObjetivo.EVITAR_DESCENSO, cumplido=False)
        self.assertIsNotNone(estado.club_actual)
        estado.aplicar_resultado("Club X", TipoObjetivo.EVITAR_DESCENSO, cumplido=False)
        self.assertIsNone(estado.club_actual)

    def test_reputacion_nunca_sale_del_rango_valido(self):
        estado = DTState(reputacion=98)
        for _ in range(10):
            estado.aplicar_resultado("Club X", TipoObjetivo.PELEAR_TITULO, cumplido=True)
        self.assertLessEqual(estado.reputacion, 100)

        estado = DTState(reputacion=2)
        for _ in range(10):
            estado.aplicar_resultado("Club Y", TipoObjetivo.EVITAR_DESCENSO, cumplido=False)
        self.assertGreaterEqual(estado.reputacion, 0)


class TestMercado(unittest.TestCase):
    def test_fichar_devuelve_siempre_un_resultado_valido(self):
        rng = random.Random(7)
        for _ in range(200):
            fichaje = fichar(CategoriaFichaje.ATAQUE, rng=rng)
            self.assertIn(fichaje.resultado.value, ("flop", "promedio", "pego"))

    def test_distribucion_de_resultados_es_razonable(self):
        rng = random.Random(42)
        conteos = {"flop": 0, "promedio": 0, "pego": 0}
        n = 4000
        for _ in range(n):
            conteos[fichar(CategoriaFichaje.DEFENSA, rng=rng).resultado.value] += 1
        # tolerancia amplia (+-6 puntos porcentuales) -- no es un test
        # de precisión estadística, es una red para detectar si algún
        # tramo de probabilidad se rompió (ej. quedó en 0% o en 100%).
        self.assertAlmostEqual(conteos["flop"] / n, 0.20, delta=0.06)
        self.assertAlmostEqual(conteos["promedio"] / n, 0.55, delta=0.06)
        self.assertAlmostEqual(conteos["pego"] / n, 0.25, delta=0.06)


class TestMotorDePartido(unittest.TestCase):
    def test_formacion_ofensiva_sube_ataque_y_empeora_defensa(self):
        local, visitante = ajustar_lambdas(1.4, 1.1, Formacion.OFENSIVA, Mentalidad.EQUILIBRADA)
        self.assertGreater(local, 1.4)
        self.assertGreater(visitante, 1.1)

    def test_formacion_defensiva_baja_ataque_y_mejora_defensa(self):
        local, visitante = ajustar_lambdas(1.4, 1.1, Formacion.DEFENSIVA, Mentalidad.EQUILIBRADA)
        self.assertLess(local, 1.4)
        self.assertLess(visitante, 1.1)

    def test_formacion_y_mentalidad_equilibradas_no_cambian_nada(self):
        local, visitante = ajustar_lambdas(1.4, 1.1, Formacion.EQUILIBRADA, Mentalidad.EQUILIBRADA)
        self.assertEqual(local, 1.4)
        self.assertEqual(visitante, 1.1)

    def test_cronologia_llega_exacto_al_marcador_pedido(self):
        rng = random.Random(11)
        for goles_local, goles_visitante in ((0, 0), (2, 1), (0, 3), (4, 4)):
            eventos = generar_cronologia(goles_local, goles_visitante, 1.3, 1.0, rng=rng)
            self.assertEqual(sum(1 for e in eventos if e.gol and e.equipo == "local"), goles_local)
            self.assertEqual(sum(1 for e in eventos if e.gol and e.equipo == "visitante"), goles_visitante)
            if eventos:
                ultimo = eventos[-1]
                self.assertEqual(ultimo.marcador_local, goles_local)
                self.assertEqual(ultimo.marcador_visitante, goles_visitante)

    def test_cronologia_tiene_minutos_validos_y_ordenados(self):
        rng = random.Random(13)
        eventos = generar_cronologia(3, 2, 1.6, 1.2, rng=rng)
        minutos = [e.minuto for e in eventos]
        self.assertEqual(minutos, sorted(minutos))
        self.assertTrue(all(1 <= m <= 90 for m in minutos))
        self.assertEqual(len(minutos), len(set(minutos)))

    def test_marcador_acumulado_es_consistente_evento_a_evento(self):
        rng = random.Random(17)
        eventos = generar_cronologia(2, 3, 1.1, 1.7, rng=rng)
        goles_local = 0
        goles_visitante = 0
        for evento in eventos:
            if evento.gol and evento.equipo == "local":
                goles_local += 1
            elif evento.gol and evento.equipo == "visitante":
                goles_visitante += 1
            self.assertEqual(evento.marcador_local, goles_local)
            self.assertEqual(evento.marcador_visitante, goles_visitante)


class TestRatingYLambda(unittest.TestCase):
    def test_rating_base_es_neutro_sin_prestigio(self):
        rating = rating_por_prestigio(0.0)
        self.assertEqual(rating["ataque_local"], 1.0)
        self.assertEqual(rating["defensa_local"], 1.0)

    def test_mas_prestigio_da_mejor_ataque_y_mejor_defensa(self):
        chico = rating_por_prestigio(0.0)
        grande = rating_por_prestigio(0.5)
        self.assertGreater(grande["ataque_local"], chico["ataque_local"])
        self.assertLess(grande["defensa_local"], chico["defensa_local"])

    def test_rating_se_recorta_al_rango_valido(self):
        rating = rating_por_prestigio(999)
        self.assertEqual(rating, rating_por_prestigio(0.5))

    def test_lambda_partido_favorece_al_mas_fuerte(self):
        fuerte = rating_por_prestigio(0.5)
        debil = rating_por_prestigio(0.0)
        lam_fuerte, lam_debil = lambda_partido(fuerte, debil)
        self.assertGreater(lam_fuerte, lam_debil)

    def test_resolver_partido_es_reproducible_con_la_misma_semilla(self):
        r1 = resolver_partido(1.4, 1.1, rng=np.random.default_rng(99))
        r2 = resolver_partido(1.4, 1.1, rng=np.random.default_rng(99))
        self.assertEqual(r1, r2)

    def test_resolver_partido_devuelve_enteros_no_negativos(self):
        rng = np.random.default_rng(5)
        for _ in range(100):
            local, visitante = resolver_partido(1.6, 1.2, rng=rng)
            self.assertGreaterEqual(local, 0)
            self.assertGreaterEqual(visitante, 0)


class TestJugarPartidoDT(unittest.TestCase):
    def test_orquestador_devuelve_cronologia_consistente_con_el_marcador(self):
        rating_dt = rating_por_prestigio(0.1)
        rating_rival = rating_por_prestigio(0.05)
        resultado = jugar_partido_dt(
            rating_dt, rating_rival, Formacion.OFENSIVA, Mentalidad.OFENSIVA,
            rng_poisson=np.random.default_rng(21), rng_narracion=random.Random(21),
        )
        self.assertIsInstance(resultado, ResultadoPartidoDT)
        goles_local_en_eventos = sum(1 for e in resultado.eventos if e.gol and e.equipo == "local")
        goles_visitante_en_eventos = sum(1 for e in resultado.eventos if e.gol and e.equipo == "visitante")
        self.assertEqual(goles_local_en_eventos, resultado.goles_local)
        self.assertEqual(goles_visitante_en_eventos, resultado.goles_visitante)


class TestCandidatosDesdeRegistry(unittest.TestCase):
    def test_arma_candidatos_con_su_division_y_prestigio(self):
        registry = ClubRegistry()
        registry.agregar_club("Boca Juniors", "Liga Profesional")
        registry.agregar_club("Un Club Chico", "Primera Nacional")

        candidatos = candidatos_desde_registry(registry, divisiones=("lpf", "nacional"))
        por_nombre = {c.nombre: c for c in candidatos}

        self.assertEqual(len(candidatos), 2)
        self.assertEqual(por_nombre["Boca Juniors"].division_slug, "lpf")
        self.assertGreater(por_nombre["Boca Juniors"].factor_prestigio, por_nombre["Un Club Chico"].factor_prestigio)

    def test_filtra_por_las_divisiones_pedidas(self):
        registry = ClubRegistry()
        registry.agregar_club("Boca Juniors", "Liga Profesional")
        registry.agregar_club("Un Club Chico", "Primera Nacional")

        candidatos = candidatos_desde_registry(registry, divisiones=("lpf",))
        self.assertEqual([c.nombre for c in candidatos], ["Boca Juniors"])


class TestObjetivoCumplido(unittest.TestCase):
    def test_sin_partidos_jugados_nunca_esta_cumplido(self):
        self.assertFalse(objetivo_cumplido(TipoObjetivo.EVITAR_DESCENSO, puntos=0, partidos_jugados=0))

    def test_objetivo_bajo_se_cumple_con_pocos_puntos(self):
        self.assertTrue(objetivo_cumplido(TipoObjetivo.EVITAR_DESCENSO, puntos=12, partidos_jugados=10))

    def test_objetivo_alto_no_se_cumple_con_los_mismos_puntos(self):
        self.assertFalse(objetivo_cumplido(TipoObjetivo.PELEAR_TITULO, puntos=12, partidos_jugados=10))

    def test_campana_perfecta_cumple_cualquier_objetivo(self):
        for objetivo in TipoObjetivo:
            self.assertTrue(objetivo_cumplido(objetivo, puntos=30, partidos_jugados=10))


if __name__ == "__main__":
    unittest.main()
