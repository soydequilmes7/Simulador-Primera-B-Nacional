# -*- coding: utf-8 -*-
"""
season/validar_libertadores_sudamericana_temporada.py

Validación end-to-end del pipeline COMBINADO de Libertadores +
Sudamericana dentro de Modo Temporada: corre las dos copas de una
temporada sintética muchas veces seguidas y confirma que nunca se
repite un club entre ambas, que el fallback avisado de _armar_
octavos_desde_playoffs() no rompe nada, y que SeasonEngine.
correr_temporada(correr_sudamericana=True) exige correr_libertadores
=True.

Correrlo desde la raíz del proyecto:

    python -m season.validar_libertadores_sudamericana_temporada
"""
from __future__ import annotations

import random

from season.libertadores_grupos import simular_temporada_libertadores
from season.sudamericana_temporada import simular_temporada_sudamericana, CANTIDAD_TOTAL

ARGENTINOS_LIBERTADORES = ["Boca Juniors", "River Plate", "Racing Club", "Talleres",
                           "Vélez Sarsfield", "Estudiantes de la Plata"]
ARGENTINOS_SUDAMERICANA = ["Independiente", "Huracán", "Argentinos Juniors", "Banfield",
                           "San Lorenzo", "Unión"]
N_SEMILLAS = 200


def validar_cuotas() -> list:
    print("\n[Parte A] Cuotas de Sudamericana suman 32")
    fallas = []
    if CANTIDAD_TOTAL != 32:
        fallas.append(f"CANTIDAD_TOTAL de Sudamericana es {CANTIDAD_TOTAL}, se esperaban 32")
    print(f"  {'OK' if not fallas else 'FALLÓ'}")
    return fallas


def validar_pipeline_combinado() -> list:
    print(f"\n[Parte B] Pipeline combinado, {N_SEMILLAS} semillas")
    fallas = []
    con_aviso = 0

    for seed in range(N_SEMILLAS):
        rng = random.Random(seed)
        try:
            res_lib = simular_temporada_libertadores(ARGENTINOS_LIBERTADORES, rng=rng)
            res_sud = simular_temporada_sudamericana(ARGENTINOS_SUDAMERICANA, res_lib, rng=rng)
        except Exception as e:
            fallas.append(f"seed={seed}: excepción no esperada: {e}")
            continue

        if len(res_sud["zonas"]) != 8:
            fallas.append(f"seed={seed}: {len(res_sud['zonas'])} zonas de Sudamericana, se esperaban 8")
        if not res_sud["campeon"]:
            fallas.append(f"seed={seed}: sin campeón de Sudamericana")

        usados_libertadores = set(res_lib["equipos_internacionales_usados"])
        usados_sudamericana = {
            f["equipo"] for z in res_sud["zonas"] for f in z["tabla"]
            if f["equipo"] not in ARGENTINOS_SUDAMERICANA
        }
        solapados = usados_libertadores & usados_sudamericana
        if solapados:
            fallas.append(f"seed={seed}: clubes jugando las dos copas la misma temporada: {solapados}")

        if res_sud["avisos"]:
            con_aviso += 1

    print(f"  {N_SEMILLAS - len(fallas)}/{N_SEMILLAS} sin fallas, {con_aviso} con algún aviso (no bloqueante)")
    print(f"  {'OK' if not fallas else 'FALLÓ'}")
    return fallas


def validar_dependencia_en_season_engine() -> list:
    print("\n[Parte C] correr_sudamericana=True exige correr_libertadores=True en SeasonEngine")
    fallas = []
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
    clasificacion_fake = {"libertadores": ARGENTINOS_LIBERTADORES, "sudamericana": ARGENTINOS_SUDAMERICANA}

    with patch.object(SeasonEngine, "_correr_competencias", return_value=resultados_fake), \
         patch("season.season_engine.QualificationManager") as QM, \
         patch("season.season_engine.CopaArgentinaManager") as CAM, \
         patch("season.season_engine.sortear_32avos", side_effect=ValueError("sin datos")):
        QM.return_value.calcular.return_value = clasificacion_fake
        CAM.return_value.calcular.return_value = {"por_division": {}}
        engine = SeasonEngine(registry)

        try:
            engine.correr_temporada(n_sims=10, correr_sudamericana=True)
            fallas.append("No levantó ValueError con correr_sudamericana=True sin correr_libertadores")
        except ValueError:
            pass

        resultado = engine.correr_temporada(n_sims=10, correr_libertadores=True, correr_sudamericana=True)
        if "error" in resultado.resultado_sudamericana:
            fallas.append(f"resultado_sudamericana con error: {resultado.resultado_sudamericana['error']}")
        if not resultado.resultado_sudamericana.get("campeon"):
            fallas.append("resultado_sudamericana sin campeón")

    print(f"  {'OK' if not fallas else 'FALLÓ'}")
    return fallas


def main():
    fallas = []
    fallas += validar_cuotas()
    fallas += validar_pipeline_combinado()
    fallas += validar_dependencia_en_season_engine()

    print("\n" + "=" * 60)
    if fallas:
        print(f"FALLÓ ({len(fallas)} problema/s):")
        for f in fallas[:20]:
            print(f"  - {f}")
        if len(fallas) > 20:
            print(f"  ... y {len(fallas) - 20} más")
    else:
        print("TODO OK")
    print("=" * 60)


if __name__ == "__main__":
    main()
