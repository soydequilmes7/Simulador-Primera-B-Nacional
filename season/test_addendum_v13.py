"""
Smoke test del ADDENDUM v13: HistoryManager con repo Y guardar_campeon_apertura
inyectados JUNTOS, sin tocar ningún singleton global -- confirma que ambos
caminos (standings/fixture/history vs. campeon del apertura) terminan en el
MISMO backend fake, cosa que antes (v12) requería parchear el singleton
global a mano para que el smoke test fuera representativo.
"""
import sys
import types
from unittest.mock import MagicMock

# --- Stub mínimo de las dependencias que history_manager.py importa a nivel
# de módulo, para poder ejercitar SOLO la parte del constructor/persist_season
# que nos interesa (no repetimos el smoke test completo del addendum v12).
sys.modules.setdefault("data_access", types.SimpleNamespace(
    guardar_campeon_apertura_lpf=lambda campeon: (_ for _ in ()).throw(
        AssertionError(
            "Se llamo al data_access global -- el fix del addendum v13 "
            "deberia haber usado el callable inyectado, no el default."
        )
    )
))

# season.club_registry / rating_carryover / fixture_generator / estadisticas_lpf
# no se ejercitan en este test puntual (no se llama persist_season() completo,
# solo se prueba el wiring del constructor) -- se stubean vacíos para poder
# importar el módulo sin el resto del repo real presente en este sandbox.
season_pkg = types.ModuleType("season")
season_pkg.__path__ = []
sys.modules["season"] = season_pkg

club_registry_mod = types.ModuleType("season.club_registry")
club_registry_mod.ClubRegistry = object
club_registry_mod.DIVISIONES = {"lpf": "Liga Profesional", "nacional": "Nacional",
                                  "bmetro": "B Metro", "primerac": "Primera C"}
sys.modules["season.club_registry"] = club_registry_mod

rating_carryover_mod = types.ModuleType("season.rating_carryover")
rating_carryover_mod.RatingCarryoverPolicy = object
sys.modules["season.rating_carryover"] = rating_carryover_mod

sys.modules["fixture_generator"] = types.SimpleNamespace(
    generar_fixture_ida_vuelta=lambda clubes: []
)

modelos_pkg = types.ModuleType("modelos")
modelos_pkg.__path__ = []
sys.modules["modelos"] = modelos_pkg
estadisticas_lpf_mod = types.ModuleType("modelos.estadisticas_lpf")
estadisticas_lpf_mod.EstadisticasLPF = object
sys.modules["modelos.estadisticas_lpf"] = estadisticas_lpf_mod

from history_manager import HistoryManager  # noqa: E402

# --- Test 1: comportamiento DEFAULT sin cambios (nadie inyecta nada nuevo) ---
hm_default = HistoryManager()
assert hm_default._guardar_campeon_apertura is sys.modules["data_access"].guardar_campeon_apertura_lpf, (
    "Sin inyectar nada, el default debe seguir siendo data_access.guardar_campeon_apertura_lpf "
    "-- cero cambio de comportamiento para callers existentes."
)
print("OK: default sin inyeccion preserva el comportamiento anterior (bypass documentado, no silencioso).")

# --- Test 2: repo custom + guardar_campeon_apertura custom, MISMO backend ---
fake_repo = MagicMock(name="fake_repo")
campeones_guardados = []

def guardar_en_fake_repo(campeon):
    # Simula un caller que ata el guardado del campeon al MISMO fake_repo
    # que se inyecto como `repo` -- exactamente el arreglo (a) que quedo
    # anotado en PLAN_ADDENDUM_v12.
    fake_repo.campeon_apertura_lpf = campeon
    campeones_guardados.append(campeon)

hm_custom = HistoryManager(repo=fake_repo, guardar_campeon_apertura=guardar_en_fake_repo)
assert hm_custom._get_repo() is fake_repo
hm_custom._guardar_campeon_apertura("Racing")

assert campeones_guardados == ["Racing"], "El campeon deberia haberse guardado via el callable inyectado."
assert fake_repo.campeon_apertura_lpf == "Racing", (
    "El campeon deberia haber terminado en el MISMO fake_repo que se inyecto como `repo`, "
    "sin pasar por ningun singleton global."
)
print("OK: repo custom + guardar_campeon_apertura custom terminan en el mismo backend, sin singleton global.")

# --- Test 3: si NO se inyecta guardar_campeon_apertura pero SI se inyecta un
# repo custom, el default sigue siendo data_access (bypass ahora EXPLICITO,
# no un bug escondido) -- confirma que no rompimos el caso "me olvide de
# inyectar el segundo parametro".
hm_solo_repo = HistoryManager(repo=fake_repo)
assert hm_solo_repo._guardar_campeon_apertura is sys.modules["data_access"].guardar_campeon_apertura_lpf
print("OK: repo custom sin guardar_campeon_apertura cae al default explicitamente documentado (no silencioso).")

print("\nTodo verde -- ADDENDUM v13 confirmado: el hallazgo de diseño del v12 queda resuelto.")
