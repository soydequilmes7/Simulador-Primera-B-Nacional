# -*- coding: utf-8 -*-
"""
tests/test_promotion_manager_lpf_rename.py

Cubre el bug real reportado por el usuario en Modo Temporada (ronda 6):
un club asciende a LPF con un alias corto sin desambiguar en el origen
de datos (ej. "Estudiantes" en vez de "Estudiantes (Caseros)"). LPF
normaliza alias cortos internamente (NORMALIZACION_NOMBRES), así que
si el ascenso no normaliza el nombre en el momento de mover el club,
la temporada siguiente EstadisticasLPF.cargar_datos_lpf() lo fusiona
por accidente con el club que YA tenía el nombre completo -- dos
clubes distintos terminan compartiendo un nombre y sus partidos se
suman en un solo fixture roto (síntoma real visto: "Estudiantes de La
Plata" con el doble de partidos que el resto).

Ver season/promotion_manager.py (PromotionManager._mover_club) y
season/club_registry.py (ClubRegistry.renombrar_club).
"""
from __future__ import annotations

import unittest

from season.club_registry import ClubRegistry
from season.promotion_manager import PromotionManager


class _ResultadoTorneoFake:
    """Mínimo objeto con .ascensos/.descensos que PromotionManager
    necesita -- mismo patrón que usa validar_etapa4_qualification.py."""

    def __init__(self, ascensos=None, descensos=None):
        self.ascensos = ascensos or []
        self.descensos = descensos or []


def _resultados_vacios(**overrides) -> dict:
    base = {
        "lpf": _ResultadoTorneoFake(),
        "nacional": _ResultadoTorneoFake(),
        "bmetro": _ResultadoTorneoFake(),
        "federal_a": _ResultadoTorneoFake(),
        "primerac": _ResultadoTorneoFake(),
    }
    base.update(overrides)
    return base


class TestAscensoLPFNormalizaAlias(unittest.TestCase):
    def test_ascenso_normaliza_alias_corto_sin_colision(self):
        """Un club que asciende con un alias corto de LPF (sin que
        exista otro club real con el nombre completo) queda
        renombrado a su nombre completo en el registro."""
        registry = ClubRegistry()
        registry.agregar_club("Riestra", "Primera Nacional")  # alias corto: normaliza a "Deportivo Riestra"

        resultados = _resultados_vacios(
            nacional=_ResultadoTorneoFake(ascensos=["Riestra"]),
        )
        resumen = PromotionManager().aplicar(resultados, registry, temporada_destino="R2")

        self.assertIsNone(registry.get_by_name("Riestra"))
        club = registry.get_by_name("Deportivo Riestra")
        self.assertIsNotNone(club)
        self.assertEqual(club.division, "Liga Profesional")
        self.assertFalse(resumen["avisos"])

    def test_colision_real_levanta_error_explicito(self):
        """Si el nombre normalizado ya pertenece a OTRO club real (el
        bug tal como lo vivió el usuario: Estudiantes de Caseros
        asciende como "Estudiantes" a secas, colisionando con
        Estudiantes de La Plata, que ya está en LPF), tiene que fallar
        fuerte y explícito -- NUNCA fusionarse en silencio y duplicar
        partidos en el fixture."""
        registry = ClubRegistry()
        registry.agregar_club("Estudiantes de La Plata", "Liga Profesional")
        registry.agregar_club("Estudiantes", "Primera Nacional")  # alias corto sin desambiguar

        resultados = _resultados_vacios(
            nacional=_ResultadoTorneoFake(ascensos=["Estudiantes"]),
        )
        with self.assertRaises(ValueError) as ctx:
            PromotionManager().aplicar(resultados, registry, temporada_destino="R2")

        self.assertIn("Colisión de nombres", str(ctx.exception))
        # el estado previo al ascenso no debería haber quedado mutado
        # a medias por el intento fallido
        self.assertEqual(registry.get_by_name("Estudiantes").division, "Primera Nacional")
        self.assertEqual(registry.get_by_name("Estudiantes de La Plata").division, "Liga Profesional")


if __name__ == "__main__":
    unittest.main()
