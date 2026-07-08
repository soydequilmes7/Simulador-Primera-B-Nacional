# -*- coding: utf-8 -*-
"""
season/season_engine.py

Etapa 5 — orquestador end-to-end en modo "shadow": corre las 6
competencias (5 divisiones + Copa Argentina), calcula clasificación a
copas internacionales y (opcionalmente) aplica ascensos/descensos
sobre el ClubRegistry real. NO persiste nada en DB todavía (eso es
Etapa 6) y NO genera el fixture de la temporada siguiente (también
Etapa 6) ni llama a HistoryManager (Etapa 7, no existe todavía).

VALIDADO -- ya no es un borrador. Las 5 interfaces (ClubRegistry,
PromotionManager, QualificationManager, TournamentEngine y los 5
adaptadores de liga) se confirmaron contra el código real de cada
módulo, y todo el motor se corrió de punta a punta con los 5 CSV
reales del repo (tabla.csv, tablalpf.csv, tabla_bmetro.csv,
tabla_federal_a.csv, tabla_primerac.csv + sus resultados/fixture):

  - Modo shadow (aplicar_promocion=False): las 6 competencias corren
    y devuelven campeón/ascensos/descensos reales, sin tocar el
    ClubRegistry.
  - Modo con promoción (aplicar_promocion=True): 20 movimientos entre
    las 5 divisiones (incluyendo los 4 retiros de Federal A por
    Reválida + sus 4 rellenos), CERO avisos de "club no encontrado"
    -- confirma que los nombres que devuelven los adaptadores calzan
    exacto con los nombres del ClubRegistry, incluida la
    desambiguación de "Estudiantes (Caseros)" / "Central Córdoba
    (Rosario)" (ver season/geografia_clubes.py).

Lo único que sigue sin revalidar en esta ronda es CopaAdapter (no se
volvió a subir main_copa.py/estadisticas_copa.py en la sesión donde
se validaron los otros 5) -- pero ya se había confirmado a fondo en
una sesión anterior con copa_argentina.csv real.
"""
from dataclasses import dataclass, field
from typing import Dict

from season.club_registry import ClubRegistry
from season.tournament_adapter import ResultadoTorneo
from season.adapters.nacional_adapter import NacionalAdapter
from season.adapters.lpf_adapter import LPFAdapter
from season.adapters.bmetro_adapter import BMetroAdapter
from season.adapters.federal_adapter import FederalAdapter
from season.adapters.primerac_adapter import PrimeraCAdapter
from season.adapters.copa_adapter import CopaAdapter
from season.promotion_manager import PromotionManager
from season.qualification_manager import QualificationManager

# Slugs que espera PromotionManager.aplicar() según su docstring
# (DIVISIONES_PROMOTION) -- Copa queda afuera a propósito, no alimenta
# ascensos/descensos.
SLUGS_PROMOTION = ["lpf", "nacional", "bmetro", "federal_a", "primerac"]

# Un adaptador por competencia. Los 6 comparten la interfaz TournamentEngine
# (setup/run/result), así que se orquestan todos igual sin código especial
# por división.
ADAPTERS = {
    "lpf": LPFAdapter,
    "nacional": NacionalAdapter,
    "bmetro": BMetroAdapter,
    "federal_a": FederalAdapter,
    "primerac": PrimeraCAdapter,
    "copa": CopaAdapter,
}


@dataclass
class ResultadoTemporada:
    """Lo que devuelve una corrida completa del SeasonEngine."""
    resultados: Dict[str, ResultadoTorneo] = field(default_factory=dict)
    clasificacion: dict = field(default_factory=dict)   # output de QualificationManager
    promocion: dict = field(default_factory=dict)        # output de PromotionManager (vacío si no se aplicó)


class SeasonEngine:
    """Orquesta las 6 competencias contra un ClubRegistry real.

    En modo "shadow" (aplicar_promocion=False, default) SOLO corre las
    simulaciones y calcula clasificación/promoción de forma informativa,
    SIN mutar el ClubRegistry -- se puede llamar tantas veces como se
    quiera sin efectos secundarios, ideal para comparar contra correr
    los 6 main_X.correr_simulacion*() a mano.

    Con aplicar_promocion=True, delega en PromotionManager, que SÍ muta
    el club_registry recibido (division de cada club, altas/bajas de
    Federal A) -- ahí deja de ser "shadow" puro. Pensado para cuando ya
    se validó la corrida shadow y se quiere efectivamente promocionar.
    """

    def __init__(self, club_registry: ClubRegistry):
        self.club_registry = club_registry

    def _correr_competencias(self, n_sims: int) -> Dict[str, ResultadoTorneo]:
        resultados = {}
        for slug, adapter_cls in ADAPTERS.items():
            adapter = adapter_cls()
            # Ningún adaptador necesita recibir nada externo hoy (los 5
            # motores reales leen sus propios CSV vía data_access.
            # league_data()). El parámetro setup() queda para cuando el
            # SeasonEngine necesite pasar el roster actualizado -- ver
            # TournamentEngine.setup().
            adapter.setup()
            adapter.run(n_sims=n_sims)
            resultados[slug] = adapter.result()
        return resultados

    def correr_temporada(self, n_sims: int = 1000,
                          aplicar_promocion: bool = False) -> ResultadoTemporada:
        resultados = self._correr_competencias(n_sims)

        # QualificationManager.calcular(resultado_lpf, resultado_copa)
        # -- confirmado contra season/qualification_manager.py real.
        clasificacion = QualificationManager().calcular(
            resultado_lpf=resultados["lpf"],
            resultado_copa=resultados["copa"],
        )

        promocion = {}
        if aplicar_promocion:
            resultados_promotion = {slug: resultados[slug] for slug in SLUGS_PROMOTION}
            # PromotionManager().aplicar(resultados, club_registry,
            # temporada_destino) -- confirmado contra
            # season/promotion_manager.py real, y probado con los 5 CSV
            # reales del repo: 20 movimientos, cero avisos de "club no
            # encontrado" (ver header del módulo).
            promocion = PromotionManager().aplicar(
                resultados_promotion, self.club_registry, temporada_destino="N+1",
            )

        return ResultadoTemporada(
            resultados=resultados,
            clasificacion=clasificacion,
            promocion=promocion,
        )
