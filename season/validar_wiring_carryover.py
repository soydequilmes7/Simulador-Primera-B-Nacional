# -*- coding: utf-8 -*-
"""
season/validar_wiring_carryover.py

Validación del wiring de los motores season-only (Fases 2-5) dentro de
SeasonEngine._correr_competencias() -- el paso que faltaba para que
api/index.py pueda usarlos de verdad en vez de solo tener la
capacidad construida y sin conectar.

Usa adapters FAKE (no los reales) para poder verificar el ROUTING
(quién recibe run_desde_carryover() vs. setup()/run()/result()) sin
depender de CSV/Supabase reales -- mismo espíritu que
season/test_promotion_manager_lpf_rename.py.

Correrlo desde la raíz del proyecto:

    python -m season.validar_wiring_carryover
"""
from __future__ import annotations

from modelos.club import Club
from season.club_registry import ClubRegistry
from season.tournament_adapter import ResultadoTorneo


def _comparar_llamadas(nombre_caso, esperado, obtenido) -> list:
    if esperado != obtenido:
        return [f"[{nombre_caso}] esperado {esperado!r}, obtenido {obtenido!r}"]
    return []


class _FakeAdapterNormal:
    """Simula LPF/Copa -- SIEMPRE camino normal, ni siquiera tiene
    run_desde_carryover() (para confirmar que el dispatch nunca
    intenta llamarlo ahí)."""
    llamadas: list = []

    def __init__(self):
        pass

    def setup(self, **kwargs):
        _FakeAdapterNormal.llamadas.append(("setup", kwargs.get("cuadro_override")))

    def run(self, n_sims):
        _FakeAdapterNormal.llamadas.append(("run", n_sims))

    def result(self):
        return ResultadoTorneo(campeon="Campeon Normal", ratings_finales={"X": {}})


class _FakeAdapterNacional:
    llamadas: list = []

    def setup(self, **kwargs):
        _FakeAdapterNacional.llamadas.append(("setup",))

    def run(self, n_sims):
        _FakeAdapterNacional.llamadas.append(("run", n_sims))

    def result(self):
        return ResultadoTorneo(campeon="Campeon Nacional Normal")

    def run_desde_carryover(self, roster, zona_por_club, club_registry, resultados_anterior):
        _FakeAdapterNacional.llamadas.append(("run_desde_carryover", tuple(roster), dict(zona_por_club)))
        return ResultadoTorneo(campeon="Campeon Nacional Carryover")


class _FakeAdapterBMetro:
    llamadas: list = []

    def setup(self, **kwargs):
        _FakeAdapterBMetro.llamadas.append(("setup",))

    def run(self, n_sims):
        _FakeAdapterBMetro.llamadas.append(("run", n_sims))

    def result(self):
        return ResultadoTorneo(campeon="Campeon BMetro Normal")

    def run_desde_carryover(self, roster, club_registry, resultados_anterior):
        # OJO: BMetro NO recibe zona_por_club (zona única) -- si el
        # dispatch le pasara 4 argumentos como a Nacional, esto
        # rompería con TypeError y el test lo detectaría.
        _FakeAdapterBMetro.llamadas.append(("run_desde_carryover", tuple(roster)))
        return ResultadoTorneo(campeon="Campeon BMetro Carryover")


class _FakeAdapterFederal:
    llamadas: list = []

    def setup(self, **kwargs):
        _FakeAdapterFederal.llamadas.append(("setup",))

    def run(self, n_sims):
        _FakeAdapterFederal.llamadas.append(("run", n_sims))

    def result(self):
        return ResultadoTorneo(campeon="Campeon Federal Normal")

    def run_desde_carryover(self, roster, zona_por_club, club_registry, resultados_anterior):
        _FakeAdapterFederal.llamadas.append(("run_desde_carryover", tuple(roster)))
        return ResultadoTorneo(campeon="Campeon Federal Carryover")


class _FakeAdapterPrimeraC:
    llamadas: list = []

    def setup(self, **kwargs):
        _FakeAdapterPrimeraC.llamadas.append(("setup",))

    def run(self, n_sims):
        _FakeAdapterPrimeraC.llamadas.append(("run", n_sims))

    def result(self):
        return ResultadoTorneo(campeon="Campeon PrimeraC Normal")

    def run_desde_carryover(self, roster, zona_por_club, club_registry, resultados_anterior):
        _FakeAdapterPrimeraC.llamadas.append(("run_desde_carryover", tuple(roster)))
        return ResultadoTorneo(campeon="Campeon PrimeraC Carryover")


def _limpiar_llamadas():
    for cls in (_FakeAdapterNormal, _FakeAdapterNacional, _FakeAdapterBMetro,
                _FakeAdapterFederal, _FakeAdapterPrimeraC):
        cls.llamadas = []


def _armar_registry() -> ClubRegistry:
    registry = ClubRegistry()
    registry.agregar_club("Club Nacional 1", "Primera Nacional")
    registry.agregar_club("Club BMetro 1", "Primera B Metropolitana")
    registry.agregar_club("Club Federal 1", "Federal A")
    registry.agregar_club("Club PrimeraC 1", "Primera C")
    return registry


def validar_sin_carryover_no_cambia_nada() -> list:
    """carryover=None (default) -- TODAS las competencias tienen que
    seguir el camino normal, cero cambio de comportamiento para
    cualquier llamador existente (validar_etapaX.py,
    /api/season/generate-next, etc.)."""
    print("\n[Caso 1] carryover=None -- comportamiento de siempre, sin cambios")
    errores = []
    _limpiar_llamadas()

    import season.season_engine as se
    fake_adapters = {
        "lpf": _FakeAdapterNormal, "copa": _FakeAdapterNormal,
        "nacional": _FakeAdapterNacional, "bmetro": _FakeAdapterBMetro,
        "federal_a": _FakeAdapterFederal, "primerac": _FakeAdapterPrimeraC,
    }
    original_adapters = se.ADAPTERS
    se.ADAPTERS = fake_adapters
    try:
        engine = se.SeasonEngine(_armar_registry())
        resultados = engine._correr_competencias(n_sims=1)
    finally:
        se.ADAPTERS = original_adapters

    for slug, cls in (("nacional", _FakeAdapterNacional), ("bmetro", _FakeAdapterBMetro),
                       ("federal_a", _FakeAdapterFederal), ("primerac", _FakeAdapterPrimeraC)):
        tipos_llamados = [c[0] for c in cls.llamadas]
        errores += _comparar_llamadas(f"{slug} sin carryover", ["setup", "run"], tipos_llamados)
        if resultados[slug].campeon != f"Campeon {slug.capitalize() if slug != 'federal_a' else 'Federal'} Normal":
            pass  # el nombre exacto no importa, solo confirmamos que vino del camino normal
        if "Normal" not in resultados[slug].campeon:
            errores.append(f"[{slug}] esperaba resultado del camino NORMAL, dio {resultados[slug].campeon!r}")

    print(f"  {len(errores)} error(es) en este caso")
    return errores


def validar_con_carryover_completo() -> list:
    """carryover con las 4 divisiones presentes en zonas_por_liga --
    las 4 deben ir por run_desde_carryover(), LPF/Copa siguen
    normales."""
    print("\n[Caso 2] carryover con las 4 divisiones -- todas por el motor season-only")
    errores = []
    _limpiar_llamadas()

    import season.season_engine as se
    fake_adapters = {
        "lpf": _FakeAdapterNormal, "copa": _FakeAdapterNormal,
        "nacional": _FakeAdapterNacional, "bmetro": _FakeAdapterBMetro,
        "federal_a": _FakeAdapterFederal, "primerac": _FakeAdapterPrimeraC,
    }
    original_adapters = se.ADAPTERS
    se.ADAPTERS = fake_adapters
    try:
        engine = se.SeasonEngine(_armar_registry())
        carryover = {
            "resultados_anterior": {},
            "zonas_por_liga": {
                "nacional": {"Club Nacional 1": "A"},
                "bmetro": {},  # zona única -- solo importa que la clave esté
                "federal_a": {"Club Federal 1": "1"},
                "primerac": {"Club PrimeraC 1": "A"},
            },
        }
        resultados = engine._correr_competencias(n_sims=1, carryover=carryover)
    finally:
        se.ADAPTERS = original_adapters

    for slug, cls, roster_esperado in (
        ("nacional", _FakeAdapterNacional, ("Club Nacional 1",)),
        ("bmetro", _FakeAdapterBMetro, ("Club BMetro 1",)),
        ("federal_a", _FakeAdapterFederal, ("Club Federal 1",)),
        ("primerac", _FakeAdapterPrimeraC, ("Club PrimeraC 1",)),
    ):
        tipos_llamados = [c[0] for c in cls.llamadas]
        errores += _comparar_llamadas(f"{slug} con carryover", ["run_desde_carryover"], tipos_llamados)
        if cls.llamadas and cls.llamadas[0][1] != roster_esperado:
            errores.append(f"[{slug}] roster pasado a run_desde_carryover: esperaba {roster_esperado}, dio {cls.llamadas[0][1]}")
        if "Carryover" not in resultados[slug].campeon:
            errores.append(f"[{slug}] esperaba resultado del motor CARRYOVER, dio {resultados[slug].campeon!r}")

    for slug in ("lpf", "copa"):
        tipos_llamados = [c[0] for c in _FakeAdapterNormal.llamadas if True]
    if [c[0] for c in _FakeAdapterNormal.llamadas].count("setup") != 2:
        errores.append("lpf/copa deberían seguir por el camino normal (2 setup(), uno cada uno)")

    print(f"  {len(errores)} error(es) en este caso")
    return errores


def validar_carryover_parcial() -> list:
    """carryover presente pero solo con ALGUNAS divisiones en
    zonas_por_liga (ej. primera ronda de una cadena, todavía no hay
    standings-en-cero de Nacional/PrimeraC pero sí de BMetro/Federal A
    por algún motivo) -- las ausentes degradan al camino normal, sin
    romper."""
    print("\n[Caso 3] carryover parcial -- las divisiones sin datos degradan al camino normal")
    errores = []
    _limpiar_llamadas()

    import season.season_engine as se
    fake_adapters = {
        "lpf": _FakeAdapterNormal, "copa": _FakeAdapterNormal,
        "nacional": _FakeAdapterNacional, "bmetro": _FakeAdapterBMetro,
        "federal_a": _FakeAdapterFederal, "primerac": _FakeAdapterPrimeraC,
    }
    original_adapters = se.ADAPTERS
    se.ADAPTERS = fake_adapters
    try:
        engine = se.SeasonEngine(_armar_registry())
        carryover = {
            "resultados_anterior": {},
            "zonas_por_liga": {
                "bmetro": {},
                "federal_a": {"Club Federal 1": "1"},
                # nacional y primerac AUSENTES a propósito
            },
        }
        resultados = engine._correr_competencias(n_sims=1, carryover=carryover)
    finally:
        se.ADAPTERS = original_adapters

    if [c[0] for c in _FakeAdapterBMetro.llamadas] != ["run_desde_carryover"]:
        errores.append(f"bmetro debería ir por carryover, llamadas: {_FakeAdapterBMetro.llamadas}")
    if [c[0] for c in _FakeAdapterFederal.llamadas] != ["run_desde_carryover"]:
        errores.append(f"federal_a debería ir por carryover, llamadas: {_FakeAdapterFederal.llamadas}")
    if [c[0] for c in _FakeAdapterNacional.llamadas] != ["setup", "run"]:
        errores.append(f"nacional (ausente de zonas_por_liga) debería ir por el camino normal, llamadas: {_FakeAdapterNacional.llamadas}")
    if [c[0] for c in _FakeAdapterPrimeraC.llamadas] != ["setup", "run"]:
        errores.append(f"primerac (ausente de zonas_por_liga) debería ir por el camino normal, llamadas: {_FakeAdapterPrimeraC.llamadas}")

    print(f"  {len(errores)} error(es) en este caso")
    return errores


def main():
    print("=" * 70)
    print("VALIDACIÓN -- wiring de carryover en SeasonEngine._correr_competencias()")
    print("=" * 70)

    errores = []
    errores += validar_sin_carryover_no_cambia_nada()
    errores += validar_con_carryover_completo()
    errores += validar_carryover_parcial()

    print("\n" + "=" * 70)
    if errores:
        print(f"❌ {len(errores)} error(es):")
        for e in errores:
            print(f"  - {e}")
    else:
        print("✅ Todo OK -- wiring de carryover en SeasonEngine validado.")
    print("=" * 70)


if __name__ == "__main__":
    main()
