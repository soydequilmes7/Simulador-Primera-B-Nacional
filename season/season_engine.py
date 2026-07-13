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

from season.club_registry import ClubRegistry, DIVISIONES
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

# Divisiones con motor season-only propio (Fases 2-5 de
# HANDOFF_carryover_ratings.md, ver season/carryover_engines/) -- las
# que NO tienen memoria propia entre temporadas de Modo Temporada
# porque HistoryManager las arma en standings-en-cero sin ratings
# iniciales (a diferencia de LPF, que ya resuelve esto con el
# Apertura pre-simulado -- ver HistoryManager._simular_apertura_lpf(),
# no necesita pasar por acá). Usado por _correr_competencias() cuando
# se le pasa `carryover` -- ver su docstring.
DIVISIONES_CARRYOVER = ("nacional", "bmetro", "federal_a", "primerac")

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
    elo_actualizados: dict = field(default_factory=dict)
    # Cuadro de 32avos YA SORTEADO para la PRÓXIMA Copa Argentina (ver
    # season/copa_argentina_sorteo.py), armado con los 64 clasificados
    # de esta misma corrida (`clasificacion_copa_argentina` de arriba).
    # Pasarlo como `cuadro_copa_override` en la próxima llamada a
    # correr_temporada()/_correr_competencias() para que esa Copa
    # Argentina se juegue con equipos nuevos en vez de repetir siempre
    # el cuadro real. Lista vacía si el sorteo no se pudo armar (avisos
    # de conteo en CopaArgentinaManager, ver armar_grupos_sorteo()).
    cuadro_copa_siguiente: list = field(default_factory=list)
    # Etapa 9: Copa Libertadores dentro de Modo Temporada (fase de
    # grupos + octavos/cuartos/semis/final), ver
    # season/libertadores_grupos.py::simular_temporada_libertadores().
    # Vacío si correr_libertadores=False (default, ver
    # correr_temporada()) -- cero cambio de comportamiento para
    # cualquier llamador existente.
    resultado_libertadores: dict = field(default_factory=dict)
    # Etapa 10: Copa Sudamericana dentro de Modo Temporada, ver
    # season/sudamericana_temporada.py::simular_temporada_sudamericana().
    # Necesita resultado_libertadores de la MISMA corrida (usa sus
    # terceros de zona) -- por eso correr_sudamericana=True exige
    # correr_libertadores=True (ver correr_temporada(), levanta
    # ValueError si no). Vacío si correr_sudamericana=False (default).
    resultado_sudamericana: dict = field(default_factory=dict)
    # Etapa 11: Recopa Sudamericana (campeón Libertadores vs campeón
    # Sudamericana de ESTA MISMA temporada, partido único a cancha
    # neutral), ver season/recopa_sudamericana.py::simular_recopa().
    # Necesita resultado_libertadores/resultado_sudamericana de la misma
    # corrida -- por eso correr_recopa=True exige correr_sudamericana
    # =True (ver correr_temporada(), levanta ValueError si no). None si
    # correr_recopa=False (default) o si algún campeón/Elo no está
    # disponible (temporada con error en alguna de las dos copas).
    resultado_recopa: dict | None = None
    # Etapa 12 (fix "calendario real" de clasificación continental):
    # cupos de Libertadores/Sudamericana que ACABA de calcular
    # QualificationManager a partir de ESTA temporada (`clasificacion`,
    # arriba) -- estos NO se usaron para poblar resultado_libertadores/
    # resultado_sudamericana de ESTA corrida (ver el porqué en el
    # docstring de correr_temporada(), parámetro `plazas_diferidas`).
    # Son los cupos que hay que guardar y pasarle como
    # `plazas_diferidas` a la PRÓXIMA llamada a correr_temporada() (la
    # de la temporada_siguiente), para que esa corrida sí juegue la
    # Libertadores/Sudamericana con los clasificados de ESTA temporada,
    # que es la edición del calendario real que les corresponde.
    plazas_diferidas_siguiente: dict = field(default_factory=dict)


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

    def _correr_competencias(
        self, n_sims: int, cuadro_copa_override: list | None = None, carryover: dict | None = None,
    ) -> Dict[str, ResultadoTorneo]:
        """cuadro_copa_override: cuadro de 32avos ya sorteado (ver
        season/copa_argentina_sorteo.py) para pasarle a CopaAdapter en
        vez de que lea el cuadro real -- pensado para encadenar rondas
        del Modo Temporada (ver api/index.py, _correr_temporada_desde_
        estado()). None (default) deja a CopaAdapter con su
        comportamiento de siempre (cuadro real).

        carryover: contexto opcional para usar los motores season-only
        de la Fase 2-5 de HANDOFF_carryover_ratings.md
        (season/carryover_engines/) en vez del main_X.py normal, para
        las divisiones en DIVISIONES_CARRYOVER. None (default): TODAS
        las competencias corren por el camino de siempre -- cero
        cambio de comportamiento para cualquier llamador existente
        (validar_etapaX.py, /api/season/generate-next, etc.).

        Shape esperado si se pasa:
            {
              "resultados_anterior": {slug: objeto con .ratings_finales
                  (ej. ResultadoTorneo) de la temporada QUE TERMINA --
                  falta o vacío degrada a rating genérico, no rompe},
              "zonas_por_liga": {slug: {equipo: zona}} -- SOLO para
                  "nacional"/"federal_a"/"primerac" (2 y 4 zonas resp.);
                  "bmetro" es zona única, alcanza con que la clave
                  "bmetro" esté presente (el valor no se usa) como
                  señal de "esta división tiene datos de Modo Temporada
                  para esta ronda, correla por el motor season-only".
            }
        Un slug de DIVISIONES_CARRYOVER que NO tenga entrada en
        "zonas_por_liga" sigue el camino normal (adapter.run() de
        siempre) para ESA división puntual -- degrada con gracia,
        pensado para la primera ronda de una cadena (todavía no hay
        standings-en-cero de Modo Temporada que traer)."""
        resultados = {}
        zonas_por_liga = (carryover or {}).get("zonas_por_liga", {})
        resultados_anterior = (carryover or {}).get("resultados_anterior", {})

        for slug, adapter_cls in ADAPTERS.items():
            adapter = adapter_cls()

            if slug in DIVISIONES_CARRYOVER and slug in zonas_por_liga:
                roster = [c.name for c in self.club_registry.get_by_division(DIVISIONES[slug])]
                if slug == "bmetro":
                    resultados[slug] = adapter.run_desde_carryover(
                        roster, self.club_registry, resultados_anterior,
                    )
                else:
                    resultados[slug] = adapter.run_desde_carryover(
                        roster, zonas_por_liga[slug], self.club_registry, resultados_anterior,
                    )
                continue

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
                          cuadro_copa_override: list | None = None,
                          correr_libertadores: bool = False,
                          correr_sudamericana: bool = False,
                          correr_recopa: bool = False,
                          plazas_diferidas: dict | None = None) -> ResultadoTemporada:
        """
        cuadro_copa_override: ver _correr_competencias() -- cuadro de
            32avos ya sorteado para esta corrida de Copa Argentina, en
            vez del cuadro real de siempre.
        plazas_diferidas: Etapa 12 (fix "calendario real" de
            clasificación continental) -- los cupos de Libertadores/
            Sudamericana que YA HABÍA CALCULADO QualificationManager al
            CIERRE DE LA TEMPORADA ANTERIOR (ResultadoTemporada.
            plazas_diferidas_siguiente de esa corrida). Shape:
            {"libertadores": [...], "sudamericana": [...],
            "temporada_clasificacion": "2026" (opcional, solo para
            trazabilidad/mensajes -- la temporada en la que se
            clasificaron, distinta de la que están por jugar)}.

            ESTO ES LA CORRECCIÓN DEL BUG DE CALENDARIO: antes esta
            función calculaba `clasificacion` (los cupos de la
            temporada QUE ESTÁ TERMINANDO acá mismo) y los usaba EN LA
            MISMA CORRIDA para poblar resultado_libertadores/
            resultado_sudamericana -- eso hacía que un club jugara la
            copa continental el mismo año en que ganó la plaza, cuando
            el reglamento real (Libertadores/Sudamericana) exige que
            juegue recién la edición del año SIGUIENTE. Ahora
            resultado_libertadores/resultado_sudamericana de ESTA
            corrida se pueblan con `plazas_diferidas` (los clasificados
            de la temporada ANTERIOR, que es a quien le toca jugar
            ESTE año) -- si no se pasa nada (None, default: primera
            temporada de una cadena, no hay "temporada anterior" de
            Modo Temporada de la cual arrastrar clasificados),
            resultado_libertadores/resultado_sudamericana quedan con
            {"error": "..."} en vez de correr con datos de la
            temporada equivocada. Los cupos que SÍ calcula esta misma
            corrida (a partir de resultados["lpf"]/["copa"] de ESTA
            temporada) se devuelven en
            ResultadoTemporada.plazas_diferidas_siguiente, listos para
            pasarlos como `plazas_diferidas` en la PRÓXIMA llamada
            (temporada_siguiente) -- así el flujo completo respeta el
            calendario real: clasificar en la temporada N, jugar en la
            N+1.
        correr_libertadores: Etapa 9 -- si es True, corre el pipeline
            completo de season/libertadores_grupos.py::simular_
            temporada_libertadores() (32 clasificados con rotación
            internacional, sorteo de 8 zonas, fase de grupos y
            octavos/cuartos/semis/final), poblado con los cupos
            argentinos de `plazas_diferidas` (ver arriba, NO con los
            cupos que recién calcula esta misma corrida), y lo deja en
            ResultadoTemporada.resultado_libertadores. False (default):
            cero cambio de comportamiento para cualquier llamador
            existente.
        correr_sudamericana: Etapa 10 -- igual que correr_libertadores
            pero para Copa Sudamericana (ver season/sudamericana_
            temporada.py::simular_temporada_sudamericana()). Exige
            correr_libertadores=True: Sudamericana usa los 8 terceros
            de zona de la Libertadores de ESTA MISMA temporada para
            armar sus Playoffs (ver ese módulo) -- levanta ValueError
            si se pide correr_sudamericana=True sin correr_libertadores
            =True, en vez de correr con datos de Libertadores vacíos o
            de una temporada anterior.
        correr_recopa: Etapa 11 -- si es True, además de las dos copas
            de arriba, juega la Recopa Sudamericana (campeón
            Libertadores vs campeón Sudamericana, partido único a
            cancha neutral, ver season/recopa_sudamericana.py) y la
            deja en ResultadoTemporada.resultado_recopa. Exige
            correr_sudamericana=True (que a su vez exige
            correr_libertadores=True) -- levanta ValueError si no.
            False (default): cero cambio de comportamiento para
            cualquier llamador existente.
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

        resultado_libertadores = {}
        if correr_libertadores:
            if plazas_diferidas is None:
                # BUG ORIGINAL (ver docstring de correr_temporada): acá se
                # usaba clasificacion.get("libertadores", []) -- los
                # clasificados de ESTA MISMA temporada -- para poblar la
                # Libertadores de ESTA MISMA corrida. Eso hacía jugar a un
                # club la copa continental el mismo año en que recién
                # ganó la plaza, cuando en el calendario real juega la
                # edición del año SIGUIENTE. Sin `plazas_diferidas` (los
                # clasificados que quedaron pendientes al cierre de la
                # temporada ANTERIOR) no hay con qué poblar esta copa de
                # forma correcta -- se deja constancia en vez de adivinar
                # con los datos de la temporada equivocada.
                resultado_libertadores = {
                    "error": (
                        "Sin plazas diferidas de la temporada anterior -- no se puede "
                        "poblar la Copa Libertadores de esta temporada sin arrastrar "
                        "clasificados de la temporada que ya terminó."
                    )
                }
            else:
                from season.libertadores_grupos import simular_temporada_libertadores
                try:
                    resultado_libertadores = simular_temporada_libertadores(
                        plazas_diferidas.get("libertadores", []),
                    )
                    resultado_libertadores["temporada_clasificacion"] = plazas_diferidas.get("temporada_clasificacion")
                except ValueError as e:
                    # No debería tumbar toda la temporada por un problema
                    # puntual de Libertadores (ej. pool internacional
                    # corrupto/incompleto) -- se deja constancia en el
                    # resultado y el resto de la temporada sigue normal.
                    resultado_libertadores = {"error": str(e)}

        resultado_sudamericana = {}
        if correr_sudamericana:
            if not correr_libertadores:
                raise ValueError(
                    "correr_sudamericana=True necesita correr_libertadores=True -- "
                    "Sudamericana arma sus Playoffs con los 8 terceros de zona de la "
                    "Libertadores de esta misma temporada (ver season/sudamericana_"
                    "temporada.py), no puede correr sin ese resultado."
                )
            if plazas_diferidas is None:
                resultado_sudamericana = {
                    "error": (
                        "Sin plazas diferidas de la temporada anterior -- misma razón "
                        "que Libertadores arriba."
                    )
                }
            elif "error" not in resultado_libertadores:
                from season.sudamericana_temporada import simular_temporada_sudamericana
                try:
                    resultado_sudamericana = simular_temporada_sudamericana(
                        plazas_diferidas.get("sudamericana", []),
                        resultado_libertadores,
                    )
                    resultado_sudamericana["temporada_clasificacion"] = plazas_diferidas.get("temporada_clasificacion")
                except ValueError as e:
                    # Mismo criterio no-bloqueante que Libertadores arriba.
                    resultado_sudamericana = {"error": str(e)}
            else:
                # Si Libertadores ya vino con error, Sudamericana no
                # tiene de dónde sacar los terceros de zona -- se deja
                # constancia sin intentar correr con datos a medias.
                resultado_sudamericana = {"error": f"Libertadores falló esta temporada: {resultado_libertadores['error']}"}

        resultado_recopa = None
        if correr_recopa:
            if not correr_sudamericana:
                raise ValueError(
                    "correr_recopa=True necesita correr_sudamericana=True -- la Recopa "
                    "enfrenta a los campeones de Libertadores y Sudamericana de esta misma "
                    "temporada, no puede correr sin esos dos resultados."
                )
            if "error" not in resultado_libertadores and "error" not in resultado_sudamericana:
                from season.recopa_sudamericana import simular_recopa
                resultado_recopa = simular_recopa(resultado_libertadores, resultado_sudamericana)
            # Si alguna de las dos copas falló, resultado_recopa queda en
            # None -- mismo criterio no bloqueante que Libertadores/
            # Sudamericana arriba, sin levantar excepción por esto.

        elo_actualizados = {}
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
            elo_actualizados = _aplicar_elo_temporada_generada(resultados, temporada_actual)

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

        # Cupos de ESTA temporada (recién calculados arriba, variable
        # `clasificacion`) para que el llamador los guarde y se los pase
        # como `plazas_diferidas` a la próxima corrida (temporada_
        # siguiente) -- ver docstring de `plazas_diferidas` más arriba.
        plazas_diferidas_siguiente = {
            "libertadores": clasificacion.get("libertadores", []),
            "sudamericana": clasificacion.get("sudamericana", []),
            "detalle": clasificacion.get("detalle", {}),
            "avisos": clasificacion.get("avisos", []),
            "temporada_clasificacion": temporada_actual,
        }

        return ResultadoTemporada(
            resultados=resultados,
            clasificacion=clasificacion,
            clasificacion_copa_argentina=clasificacion_copa_argentina,
            promocion=promocion,
            historia=historia,
            elo_actualizados=elo_actualizados,
            cuadro_copa_siguiente=cuadro_copa_siguiente,
            resultado_libertadores=resultado_libertadores,
            resultado_sudamericana=resultado_sudamericana,
            resultado_recopa=resultado_recopa,
            plazas_diferidas_siguiente=plazas_diferidas_siguiente,
        )


def _aplicar_elo_temporada_generada(resultados: dict, temporada_actual: str) -> dict:
    """Persiste ELO solo para /api/season/generate-next, nunca para shadow."""
    from db.repository import transaction

    resumen = {}
    slugs = ("lpf", "nacional", "bmetro", "federal_a", "primerac")
    with transaction() as repo:
        for slug in slugs:
            resultado = resultados.get(slug)
            partidos = []
            if resultado is not None:
                partidos = list((resultado.datos_crudos or {}).get("partidos_simulados") or [])
            if not partidos:
                continue
            partidos_evento = []
            for index, partido in enumerate(partidos, start=1):
                fila = dict(partido)
                fila["event_key"] = f"{slug}:{temporada_actual}:{index}:{fila.get('event_key', '')}"
                partidos_evento.append(fila)
            resumen[slug] = repo.apply_club_rating_events(
                slug,
                partidos_evento,
                source="season_generate_next",
                metadata={"temporada_actual": temporada_actual},
            )
    return resumen
