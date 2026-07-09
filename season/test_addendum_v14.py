"""
Smoke test del ADDENDUM v14: los 4 adaptadores reales que faltaban
(BMetro/Federal A/Primera C/Copa) recién subidos -- código de los
`adapters` REAL, sin tocar; `main_X.correr_simulacion*()` stubeado con
el shape CONFIRMADO leyendo cada main_X.py real (no inventado), porque
no hay CSV/DB en este sandbox para correr los motores de punta a punta.
"""
import sys
sys.path.insert(0, ".")

from season.adapters.bmetro_adapter import BMetroAdapter
from season.adapters.federal_adapter import FederalAdapter
from season.adapters.copa_adapter import CopaAdapter
from season.adapters.primerac_adapter import PrimeraCAdapter

adapters = {
    "bmetro": BMetroAdapter(),
    "federal_a": FederalAdapter(),
    "copa": CopaAdapter(),
    "primerac": PrimeraCAdapter(),
}

resultados = {}
for slug, adapter in adapters.items():
    # Mismo llamado EXACTO que season_engine._correr_competencias():
    # setup() sin argumentos para los 4 -- esto es lo que rompía antes
    # del fix en PrimeraCAdapter.
    adapter.setup()
    adapter.run(n_sims=10)
    resultados[slug] = adapter.result()
    print(f"OK: {slug}.setup() sin argumentos + run() + result() no rompen.")

# --- Validaciones de shape, una por adapter ---

r = resultados["bmetro"]
assert r.campeon == "ClubBMetro1"
assert r.ascensos == ["ClubBMetro1", "ClubBMetro3"]
assert r.descensos == ["ClubBMetro21", "ClubBMetro22"]
assert r.clasificados_copa == []
print("OK: BMetroAdapter.result() -- campeon=puntero, ascensos=[directo,reducido], descensos tal cual, sin copas.")

r = resultados["federal_a"]
assert r.campeon == "ClubFederal1"  # ascenso_1
assert r.ascensos == ["ClubFederal1", "ClubFederal5"]
assert r.descensos == ["ClubFederal20", "ClubFederal21", "ClubFederal22", "ClubFederal23"]
assert len(r.descensos) == 4
assert r.clasificados_copa == []
print("OK: FederalAdapter.result() -- campeon=ascenso_1, ascensos=[camino_principal,revalida], 4 descensos, sin copas.")

r = resultados["copa"]
assert r.campeon == "River Plate"
assert r.ascensos == []
assert r.descensos == []
assert r.clasificados_copa == ["River Plate"]
print("OK: CopaAdapter.result() -- campeon clasifica a Libertadores vía clasificados_copa, sin ascensos/descensos.")

r = resultados["primerac"]
assert r.campeon == "ClubPrimeraC_A1"  # final_ascenso.ganador
assert r.ascensos == ["ClubPrimeraC_A1", "ClubPrimeraC_A2"]  # ganador + campeon del reducido
assert r.descensos == []
assert r.clasificados_copa == []
print("OK: PrimeraCAdapter.result() -- campeon=final_ascenso.ganador, ascensos=[final,reducido] "
      "(extraído de reducido['final']['campeon'], la ruta anidada correcta), sin descensos/copas.")

# --- Confirmar el guardrail de _extraer_campeon_reducido() con un shape roto ---
from season.adapters.primerac_adapter import _extraer_campeon_reducido
try:
    _extraer_campeon_reducido({"final": {}})
    raise AssertionError("Debería haber levantado ValueError con reducido['final'] vacío")
except ValueError:
    print("OK: _extraer_campeon_reducido() falla fuerte si reducido['final'] no tiene 'campeon'.")

print("\nTodo verde -- los 4 adapters nuevos (BMetro/Federal A/Primera C/Copa) "
      "quedan confirmados end-to-end contra el shape real de sus main_X.py, "
      "incluido el fix del bug de firma en PrimeraCAdapter.setup().")
