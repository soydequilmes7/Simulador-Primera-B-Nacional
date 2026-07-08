"""
Interfaz común que deben cumplir todos los adaptadores de torneo
(PrimeraCAdapter, NacionalAdapter, LPFAdapter, BMetroAdapter,
FederalAdapter, CopaAdapter).

Cada adaptador ENVUELVE el main_X.correr_simulacion() real (no lo
reescribe, no lo modifica) y traduce su dict de salida específico a
un shape normalizado: ResultadoTorneo. Así el SeasonEngine (Etapa 5)
puede tratar a las 6 competencias de manera uniforme sin conocer los
detalles internos de cada una.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ResultadoTorneo:
    """Shape normalizado que devuelve cualquier adaptador, sin importar
    el torneo real que haya corrido por debajo.

    campeon:            nombre del campeón de la competencia (o None si
                         el torneo no tiene un único campeón, ej. una
                         fase regular sin definición a torneo).
    ascensos:            lista de nombres de clubes que ascienden.
                         Vacía para competencias sin ascenso/descenso
                         (ej. LPF, Copa Argentina).
    descensos:           lista de nombres de clubes que descienden.
    clasificados_copa:   lista de nombres de clubes clasificados a
                         copas internacionales (Libertadores/
                         Sudamericana) o a la Copa Argentina, según
                         corresponda a esa competencia.
    datos_crudos:        el dict ORIGINAL devuelto por
                         main_X.correr_simulacion(), sin tocar. Se
                         conserva para no perder nada de lo que hoy
                         consume el frontend (tablas, monte_carlo,
                         goleadores, etc.) ni tener que adivinar de
                         nuevo el shape más adelante.
    ratings_finales:     dict[str, dict] -- {equipo: {ataque_local,
                         ataque_visitante, defensa_local,
                         defensa_visitante}} con el rating FINAL de
                         cada equipo al cierre del torneo (leído de
                         equipo.ataque_*/defensa_* DESPUÉS de
                         calcular_ratings()/calcular_ratings_lpf()).
                         Campo ADITIVO (PLAN_ADDENDUM_ETAPA6_APERTURA_LPF,
                         punto 3): lo llenan los adaptadores que usan
                         objetos Equipo real (Nacional, LPF, BMetro,
                         PrimeraC); es la fuente para que un club
                         ascendido/descendido herede su rating real
                         vía RatingCarryoverPolicy en vez de arrancar
                         siempre en el rating genérico. Queda vacío
                         ({}) en los adaptadores que todavía no lo
                         completan (comportamiento default seguro:
                         un club ausente de este dict se trata igual
                         que hoy, como recién llegado sin historial).
                         Federal A (FederalAdapter) queda afuera a
                         propósito -- motor vectorizado sin objetos
                         Equipo.
    """
    campeon: str | None
    ascensos: list = field(default_factory=list)
    descensos: list = field(default_factory=list)
    clasificados_copa: list = field(default_factory=list)
    datos_crudos: dict = field(default_factory=dict)
    ratings_finales: dict = field(default_factory=dict)


class TournamentEngine(ABC):
    """Interfaz que debe implementar cada adaptador concreto.

    Uso esperado (ver season/season_engine.py en etapas futuras):
        motor = XAdapter()
        motor.setup(clubes=...)
        motor.run(n_sims=1000)
        resultado = motor.result()   # -> ResultadoTorneo
    """

    @abstractmethod
    def setup(self, **kwargs):
        """Prepara el adaptador con lo que necesite antes de correr
        (por ahora, en Etapas 1-2, ningún adaptador necesita recibir
        nada externo porque main_X.correr_simulacion() lee sus propios
        CSV vía data_access.league_data(); el parámetro queda acá para
        cuando el SeasonEngine necesite pasar el roster actualizado en
        Etapa 5+)."""
        raise NotImplementedError

    @abstractmethod
    def run(self, n_sims: int = 1000):
        """Corre la simulación real (llama a main_X.correr_simulacion()
        o equivalente)."""
        raise NotImplementedError

    @abstractmethod
    def result(self) -> ResultadoTorneo:
        """Traduce la última corrida a un ResultadoTorneo normalizado.
        Lanza RuntimeError si se llama antes de run()."""
        raise NotImplementedError
