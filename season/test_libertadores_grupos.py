# -*- coding: utf-8 -*-
"""
season/test_libertadores_grupos.py

Cubre los casos borde de la fase de grupos de Libertadores: pool
insuficiente por país, cupos argentinos incompletos, y el sorteo de
Octavos (sortear_octavos()) -- confirmado contra el instructivo
oficial de CONMEBOL que a partir de Octavos NO hay restricción de país
(a diferencia de la fase de grupos, ver season/libertadores_sorteo.py)
y que el Bombo 1 (mejor ranking) define la vuelta como local.
"""
from __future__ import annotations

import random
import unittest

from season.libertadores_manager import (
    ClubInternacional, LibertadoresManager, CUPOS_ARGENTINA, CANTIDAD_TOTAL,
)
from season.libertadores_sorteo import sortear_grupos
from season.libertadores_grupos import sortear_octavos


def _pool_minimo() -> list[ClubInternacional]:
    """Un pool sintético con exactamente la cuota de cada país (sin
    margen para rotar) -- caso límite pero válido."""
    from season.libertadores_manager import QUOTAS_PAIS
    pool = []
    for pais, cupo in QUOTAS_PAIS.items():
        for i in range(cupo):
            pool.append(ClubInternacional(equipo=f"{pais}_{i}", pais=pais, elo=1500 + i))
    return pool


class TestLibertadoresManager(unittest.TestCase):
    def test_armado_normal_da_32_equipos_unicos(self):
        manager = LibertadoresManager(pool=_pool_minimo())
        clasificacion = manager.armar_clasificacion(
            ["A", "B", "C", "D", "E", "F"], rng=random.Random(1),
        )
        self.assertEqual(len(clasificacion.equipos), CANTIDAD_TOTAL)
        nombres = [c.equipo for c in clasificacion.equipos]
        self.assertEqual(len(nombres), len(set(nombres)))
        self.assertEqual(clasificacion.avisos, [])

    def test_menos_de_6_clasificados_argentinos_avisa_y_no_rompe(self):
        manager = LibertadoresManager(pool=_pool_minimo())
        clasificacion = manager.armar_clasificacion(["A", "B"], rng=random.Random(1))
        self.assertEqual(len([c for c in clasificacion.equipos if c.pais == "Argentina"]), 2)
        self.assertTrue(any("Solo hay 2/6" in a for a in clasificacion.avisos))

    def test_pool_de_un_pais_por_debajo_de_la_cuota_usa_todos_y_avisa(self):
        pool = _pool_minimo()
        pool = [c for c in pool if not (c.pais == "Venezuela")]  # saca el único de Venezuela
        manager = LibertadoresManager(pool=pool)
        clasificacion = manager.armar_clasificacion(
            ["A", "B", "C", "D", "E", "F"], rng=random.Random(1),
        )
        self.assertEqual(len([c for c in clasificacion.equipos if c.pais == "Venezuela"]), 0)
        self.assertTrue(any("Venezuela" in a for a in clasificacion.avisos))


class TestSortearOctavos(unittest.TestCase):
    def test_devuelve_8_llaves_con_los_16_equipos(self):
        bombo1 = [f"P{i}" for i in range(8)]
        bombo2 = [f"S{i}" for i in range(8)]
        cuadro = sortear_octavos(bombo1, bombo2, rng=random.Random(1))
        self.assertEqual(len(cuadro), 8)
        equipos_en_cuadro = {f["equipo_ida_local"] for f in cuadro} | {f["equipo_vuelta_local"] for f in cuadro}
        self.assertEqual(equipos_en_cuadro, set(bombo1) | set(bombo2))

    def test_bombo1_siempre_define_la_vuelta_como_local(self):
        bombo1 = [f"P{i}" for i in range(8)]
        bombo2 = [f"S{i}" for i in range(8)]
        cuadro = sortear_octavos(bombo1, bombo2, rng=random.Random(2))
        for fila in cuadro:
            self.assertIn(fila["equipo_vuelta_local"], bombo1)
            self.assertIn(fila["equipo_ida_local"], bombo2)

    def test_permite_cruce_de_mismo_pais_sin_restriccion(self):
        """A partir de Octavos, CONMEBOL no restringe por país (a
        diferencia de la fase de grupos) -- sortear_octavos() no debe
        aplicar ninguna lógica de evitar países, y con dos bombos
        íntegramente del mismo país (caso extremo) tiene que poder
        devolver un cuadro sin problema."""
        bombo1 = [f"AR{i}" for i in range(8)]
        bombo2 = [f"AR2_{i}" for i in range(8)]
        cuadro = sortear_octavos(bombo1, bombo2, rng=random.Random(3))
        self.assertEqual(len(cuadro), 8)

    def test_es_aleatorio_no_espejado(self):
        """Con semillas distintas, el orden del cruce tiene que variar
        -- si fuera siempre el mismo orden (ej. espejado fijo), no
        sería un sorteo real."""
        bombo1 = [f"P{i}" for i in range(8)]
        bombo2 = [f"S{i}" for i in range(8)]
        ordenes = set()
        for seed in range(10):
            cuadro = sortear_octavos(bombo1, bombo2, rng=random.Random(seed))
            ordenes.add(tuple(f["equipo_ida_local"] for f in cuadro))
        self.assertGreater(len(ordenes), 1)


class TestSorteoGrupos(unittest.TestCase):
    def test_sorteo_nunca_repite_pais_en_una_zona(self):
        manager = LibertadoresManager(pool=_pool_minimo())
        for seed in range(20):
            rng = random.Random(seed)
            clasificacion = manager.armar_clasificacion(
                ["A", "B", "C", "D", "E", "F"], rng=rng,
            )
            zonas = sortear_grupos(clasificacion, rng=rng)
            pais_por_equipo = {c.equipo: c.pais for c in clasificacion.equipos}
            for zona in zonas:
                paises = [pais_por_equipo[e] for e in zona.equipos]
                self.assertEqual(len(paises), len(set(paises)), f"seed={seed} zona={zona.letra}")


class TestWiringSeasonEngine(unittest.TestCase):
    """Etapa 9: correr_libertadores en SeasonEngine.correr_temporada()
    -- ver season/season_engine.py. Con mocks porque _correr_
    competencias() real necesita Supabase (psycopg), no disponible acá;
    el pipeline de Libertadores en sí ya está cubierto por los tests de
    arriba y por season/validar_libertadores_grupos.py."""

    def _engine_con_mocks(self):
        from unittest.mock import patch
        from season.club_registry import ClubRegistry
        from season.season_engine import SeasonEngine
        from season.tournament_adapter import ResultadoTorneo

        registry = ClubRegistry()
        resultados_fake = {
            slug: ResultadoTorneo(campeon="X", ascensos=[], descensos=[], clasificados_copa=[],
                                   ratings_finales={}, datos_crudos={})
            for slug in ("lpf", "nacional", "bmetro", "federal_a", "primerac", "copa")
        }
        clasificacion_fake = {
            "libertadores": ["Boca Juniors", "River Plate", "Racing Club", "Talleres",
                              "Vélez Sarsfield", "Estudiantes de la Plata"],
            "sudamericana": ["Independiente", "Huracán", "Argentinos Juniors", "Banfield",
                              "San Lorenzo", "Unión"],
        }
        return patch.object(SeasonEngine, "_correr_competencias", return_value=resultados_fake), \
            patch("season.season_engine.QualificationManager"), \
            patch("season.season_engine.CopaArgentinaManager"), \
            patch("season.season_engine.sortear_32avos", side_effect=ValueError("sin datos")), \
            registry, clasificacion_fake

    def test_default_false_no_corre_libertadores(self):
        from season.club_registry import ClubRegistry
        from season.season_engine import SeasonEngine
        p1, p2, p3, p4, registry, clasificacion_fake = self._engine_con_mocks()
        with p1, p2 as QM, p3 as CAM, p4:
            QM.return_value.calcular.return_value = clasificacion_fake
            CAM.return_value.calcular.return_value = {"por_division": {}}
            resultado = SeasonEngine(registry).correr_temporada(n_sims=10, correr_libertadores=False)
        self.assertEqual(resultado.resultado_libertadores, {})

    def test_true_corre_el_pipeline_completo(self):
        from season.season_engine import SeasonEngine
        p1, p2, p3, p4, registry, clasificacion_fake = self._engine_con_mocks()
        with p1, p2 as QM, p3 as CAM, p4:
            QM.return_value.calcular.return_value = clasificacion_fake
            CAM.return_value.calcular.return_value = {"por_division": {}}
            resultado = SeasonEngine(registry).correr_temporada(n_sims=10, correr_libertadores=True)
        self.assertIn("campeon", resultado.resultado_libertadores)
        self.assertEqual(len(resultado.resultado_libertadores["zonas"]), 8)
        self.assertNotIn("error", resultado.resultado_libertadores)

    def test_sudamericana_sin_libertadores_levanta_valueerror(self):
        from season.season_engine import SeasonEngine
        p1, p2, p3, p4, registry, clasificacion_fake = self._engine_con_mocks()
        with p1, p2 as QM, p3 as CAM, p4:
            QM.return_value.calcular.return_value = clasificacion_fake
            CAM.return_value.calcular.return_value = {"por_division": {}}
            with self.assertRaises(ValueError):
                SeasonEngine(registry).correr_temporada(n_sims=10, correr_sudamericana=True)

    def test_ambos_true_corren_las_dos_copas(self):
        from season.season_engine import SeasonEngine
        p1, p2, p3, p4, registry, clasificacion_fake = self._engine_con_mocks()
        with p1, p2 as QM, p3 as CAM, p4:
            QM.return_value.calcular.return_value = clasificacion_fake
            CAM.return_value.calcular.return_value = {"por_division": {}}
            resultado = SeasonEngine(registry).correr_temporada(
                n_sims=10, correr_libertadores=True, correr_sudamericana=True,
            )
        self.assertNotIn("error", resultado.resultado_libertadores)
        self.assertNotIn("error", resultado.resultado_sudamericana)
        self.assertIn("campeon", resultado.resultado_sudamericana)
        self.assertEqual(len(resultado.resultado_sudamericana["zonas"]), 8)

        # Ningún club internacional debería repetirse entre las dos copas.
        usados_libertadores = set(resultado.resultado_libertadores["equipos_internacionales_usados"])
        usados_sudamericana = {
            f["equipo"] for z in resultado.resultado_sudamericana["zonas"] for f in z["tabla"]
            if f["pais"] != "Argentina"
        }
        self.assertEqual(usados_libertadores & usados_sudamericana, set())


if __name__ == "__main__":
    unittest.main()
