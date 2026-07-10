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
from season.copa_argentina_manager import CopaArgentinaManager
from season.copa_argentina_sorteo import sortear_32avos
from season.history_manager import HistoryManager

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
    # Etapa 8 (Boletín 6812 AFA 2027): output de CopaArgentinaManager --
    # quién clasifica a la PRÓXIMA Copa Argentina (64 invitados de las 5
    # divisiones que alimentan, ver season/copa_argentina_manager.py).
    # No confundir con `clasificacion` de arriba, que es a copas
    # internacionales (Libertadores/Sudamericana).
    clasificacion_copa_argentina: dict = field(default_factory=dict)
    promocion: dict = field(default_factory=dict)        # output de PromotionManager (vacío si no se aplicó)
    # Etapa 7: output de HistoryManager.persist_season() (vacío si
    # generar_temporada_siguiente=False, ver correr_temporada()).
    historia: dict = field(default_factory=dict)
    # Cuadro de 32avos YA SORTEADO para la PRÓXIMA Copa Argentina (ver
    # season/copa_argentina_sorteo.py), armado con los 64 clasificados
    # de esta misma corrida (`clasificacion_copa_argentina` de arriba).
    # Pasarlo como `cuadro_copa_override` en la próxima llamada a
    # correr_temporada()/_correr_competencias() para que esa Copa
    # Argentina se juegue con equipos nuevos en vez de repetir siempre
    # el cuadro real. Lista vacía si el sorteo no se pudo armar (avisos
    # de conteo en CopaArgentinaManager, ver armar_grupos_sorteo()).
    cuadro_copa_siguiente: list = field(default_factory=list)


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

    def _correr_competencias(self, n_sims: int, cuadro_copa_override: list | None = None) -> Dict[str, ResultadoTorneo]:
        """cuadro_copa_override: cuadro de 32avos ya sorteado (ver
        season/copa_argentina_sorteo.py) para pasarle a CopaAdapter en
        vez de que lea el cuadro real -- pensado para encadenar rondas
        del Modo Temporada (ver api/index.py, _correr_temporada_desde_
        estado()). None (default) deja a CopaAdapter con su
        comportamiento de siempre (cuadro real)."""
        resultados = {}
        for slug, adapter_cls in ADAPTERS.items():
            adapter = adapter_cls()
            # Ningún adaptador necesita recibir nada externo hoy salvo
            # Copa (ver arriba). Los 5 motores de liga reales leen sus
            # propios CSV vía data_access.league_data(). El parámetro
            # setup() queda para cuando el SeasonEngine necesite pasar
            # el roster actualizado -- ver TournamentEngine.setup().
            kwargs = {"cuadro_override": cuadro_copa_override} if slug == "copa" else {}
            adapter.setup(**kwargs)
            adapter.run(n_sims=n_sims)
            resultados[slug] = adapter.result()
        return resultados

    def correr_temporada(self, n_sims: int = 1000,
                          aplicar_promocion: bool = False,
                          generar_temporada_siguiente: bool = False,
                          temporada_actual: str | None = None,
                          temporada_siguiente: str | None = None,
                          history_manager: HistoryManager | None = None,
                          cuadro_copa_override: list | None = None) -> ResultadoTemporada:
        """
        cuadro_copa_override: ver _correr_competencias() -- cuadro de
            32avos ya sorteado para esta corrida de Copa Argentina, en
            vez del cuadro real de siempre.
        generar_temporada_siguiente: Etapa 7 -- si es True, además de
            correr las 6 competencias y (opcionalmente) promocionar,
            persiste la temporada N+1 vía HistoryManager.persist_season()
            (standings/fixture de las 4 divisiones round-robin simple +
            el Apertura simulado de LPF, ver PLAN_ADDENDUM_ETAPA6_
            APERTURA_LPF.txt). Requiere aplicar_promocion=True -- si no,
            se levanta ValueError: persistir la temporada siguiente
            contra un club_registry SIN promocionar dejaría a cada club
            en la división de la temporada que recién terminó, no en la
            que le corresponde.
        temporada_actual / temporada_siguiente: strings requeridos si
            generar_temporada_siguiente=True (ej. "2026"/"2027") --
            ver HistoryManager.persist_season().
        history_manager: instancia inyectable (mismo patrón que
            PromotionManager/QualificationManager no toman una custom,
            pero HistoryManager sí porque encapsula acceso a repo/rng
            -- ver su constructor). Si no se pasa, se instancia
            HistoryManager() default (repo real vía db.repository,
            rng sin semilla).
        """
        resultados = self._correr_competencias(n_sims, cuadro_copa_override=cuadro_copa_override)

        # QualificationManager.calcular(resultado_lpf, resultado_copa)
        # -- confirmado contra season/qualification_manager.py real.
        clasificacion = QualificationManager().calcular(
            resultado_lpf=resultados["lpf"],
            resultado_copa=resultados["copa"],
        )

        # CopaArgentinaManager.calcular(resultados) -- quién clasifica a
        # la PRÓXIMA Copa Argentina (Boletín 6812 AFA 2027), a partir de
        # las 5 divisiones que alimentan invitados (Copa Argentina misma
        # queda afuera, ver docstring de CopaArgentinaManager).
        clasificacion_copa_argentina = CopaArgentinaManager().calcular(resultados)

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

        historia = {}
        if generar_temporada_siguiente:
            if not aplicar_promocion:
                raise ValueError(
                    "generar_temporada_siguiente=True necesita aplicar_promocion=True -- "
                    "si no, HistoryManager.persist_season() armaría la temporada siguiente "
                    "leyendo el club_registry SIN promocionar (cada club seguiría en la "
                    "división de la temporada que recién terminó, no en la que le "
                    "corresponde tras ascensos/descensos)."
                )
            if not temporada_actual or not temporada_siguiente:
                raise ValueError(
                    "generar_temporada_siguiente=True necesita temporada_actual y "
                    "temporada_siguiente (ej. '2026' / '2027')."
                )
            hm = history_manager or HistoryManager()
            # persist_season(club_registry, temporada_actual,
            # temporada_siguiente, resultados) -- confirmado contra
            # season/history_manager.py real (con el fix de
            # PLAN_ADDENDUM_v9). resultados se pasa TAL CUAL viene de
            # _correr_competencias(), de la temporada QUE TERMINA --
            # HistoryManager usa resultados["lpf"]/["nacional"] para el
            # Apertura simulado de LPF (ver su docstring).
            historia = hm.persist_season(
                self.club_registry, temporada_actual, temporada_siguiente, resultados,
            )

        # Sorteo de 32avos para la PRÓXIMA Copa Argentina, con los 64
        # clasificados que acaba de armar CopaArgentinaManager (ver
        # season/copa_argentina_sorteo.py). Si los conteos no cierran
        # 32+32 (avisos de CopaArgentinaManager por algún caso raro),
        # se deja vacío -- quien reciba este ResultadoTemporada debería
        # entonces NO pasar cuadro_copa_override en la corrida
        # siguiente, y CopaAdapter vuelve a su comportamiento de
        # siempre (cuadro real).
        try:
            cuadro_copa_siguiente = sortear_32avos(clasificacion_copa_argentina)
        except ValueError:
            cuadro_copa_siguiente = []

        return ResultadoTemporada(
            resultados=resultados,
            clasificacion=clasificacion,
            clasificacion_copa_argentina=clasificacion_copa_argentina,
            promocion=promocion,
            historia=historia,
            cuadro_copa_siguiente=cuadro_copa_siguiente,
        )
