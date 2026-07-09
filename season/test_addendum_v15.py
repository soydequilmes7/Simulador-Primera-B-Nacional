"""
Smoke test del ADDENDUM v15: las 6 competencias juntas vía
SeasonEngine._correr_competencias() -- código REAL de los 6 adapters
(lpf, nacional, bmetro, federal_a, primerac, copa), con
PrimeraCAdapter ya con el fix del bug de setup() del addendum v14.
main_X.correr_simulacion*() stubeados con el shape confirmado leyendo
cada adapter real (no tengo los 6 main_X.py/motores reales ni CSV/DB
en esta sesión) -- esto es justo el punto donde rompía el bug antes
de arreglarlo: las 6 corren en el MISMO loop de
_correr_competencias(), no hay forma de saltear Primera C.
"""
import sys
sys.path.insert(0, ".")

from season.season_engine import SeasonEngine, ADAPTERS, SLUGS_PROMOTION

print("ADAPTERS registrados:", list(ADAPTERS.keys()))
assert list(ADAPTERS.keys()) == ["lpf", "nacional", "bmetro", "federal_a", "primerac", "copa"]

# club_registry no se usa dentro de _correr_competencias() (solo lo
# necesitan aplicar_promocion=True / generar_temporada_siguiente=True,
# fuera del alcance de este test puntual) -- alcanza con un objeto
# cualquiera para instanciar SeasonEngine.
engine = SeasonEngine(club_registry=object())

resultados = engine._correr_competencias(n_sims=10)

assert set(resultados.keys()) == {"lpf", "nacional", "bmetro", "federal_a", "primerac", "copa"}
print("OK: las 6 competencias corrieron en el mismo loop sin romper "
      "(esto es lo que fallaba con TypeError antes del fix de PrimeraCAdapter.setup()).")

for slug in SLUGS_PROMOTION:
    r = resultados[slug]
    assert r.campeon, f"{slug}: campeon vacío"
    print(f"  {slug}: campeon={r.campeon!r}, ascensos={r.ascensos}, descensos={r.descensos}")

r_copa = resultados["copa"]
print(f"  copa: campeon={r_copa.campeon!r}, clasificados_copa={r_copa.clasificados_copa}")
assert r_copa.ascensos == [] and r_copa.descensos == []

r_lpf = resultados["lpf"]
assert r_lpf.ascensos == [], "LPF no tiene ascenso (es la máxima categoría)"
assert len(r_lpf.descensos) == 2
assert r_lpf.ratings_finales, "LPF debería traer ratings_finales para el carryover a Etapa 7"
print(f"  lpf.clasificados_copa (filtrado el placeholder 'no simulado'): {r_lpf.clasificados_copa}")
assert all("no simulado" not in c for c in r_lpf.clasificados_copa), (
    "El placeholder de Copa Argentina no debería colarse en clasificados_copa"
)

r_nacional = resultados["nacional"]
assert len(r_nacional.descensos) == 4, "2 zonas x últimos 2 = 4 descensos totales en Nacional"
assert r_nacional.ratings_finales, "Nacional debería traer ratings_finales para el carryover de LPF"

print("\nTodo verde -- las 6 competencias (código real de los 6 adapters, "
      "incluido el fix de PrimeraCAdapter) corren juntas en "
      "SeasonEngine._correr_competencias() sin romper.")
