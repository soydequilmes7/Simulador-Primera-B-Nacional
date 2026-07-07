# -*- coding: utf-8 -*-
"""
season/adapters/primerac_adapter.py

Adaptador de Primera C para el SeasonEngine (Etapa 1 del plan de Modo
Temporada Nacional). Envuelve main_primerac.correr_simulacion() tal
cual -- no reescribe nada del motor de simulación, solo traduce su
dict de salida (datos_web) al formato común ResultadoTorneo.

Mapeo (confirmado leyendo main_primerac.py y estadisticas_primerac.py,
no supuesto):

  - campeon (1er ascenso) = datos_web["final_ascenso"]["ganador"].

  - 2do ascenso = campeón del Torneo Reducido. estadisticas_primerac.
    jugar_reducido() devuelve (campeon, diccionario), pero
    main_primerac.correr_simulacion() solo guarda `diccionario` bajo
    la clave "reducido" de datos_web -- el `campeon` que devuelve la
    función NO se guarda como tal en ningún lado de datos_web.
    Por suerte, la ronda "final" del Reducido se juega con
    jugar_serie_ida_vuelta() (ida y vuelta, Primera C no tiene ronda a
    partido único en el Reducido), y el detalle que arma esa función
    SÍ incluye una clave "campeon" con el nombre del ganador. Por eso
    _extraer_campeon_reducido() lee datos_web["reducido"]["final"]["campeon"]
    en vez de necesitar el valor de retorno directo de jugar_reducido().

  - Primera C no tiene descensos en este dict (no se calculan acá) ni
    clasificados a copas -- se dejan como listas vacías en esta etapa,
    tal como confirma el punto 4 del plan ("Primera C: mismo shape que
    Nacional").
"""
import main_primerac
from season.tournament_adapter import ResultadoTorneo, TournamentEngine


def _extraer_campeon_reducido(reducido):
    """Recupera el nombre del campeón del Torneo Reducido a partir de
    `datos_web["reducido"]` (el `diccionario` que arma jugar_reducido()
    en estadisticas_primerac.py).

    jugar_reducido() devuelve (campeon, diccionario), pero
    main_primerac.correr_simulacion() solo guarda `diccionario` en
    datos_web -- el nombre del campeón hay que sacarlo de adentro. La
    ronda "final" es en sí una serie ida/vuelta jugada con
    jugar_serie_ida_vuelta(), cuyo detalle SÍ trae la clave "campeon"
    (ver estadisticas_primerac.py). Por eso alcanza con leer
    reducido["final"]["campeon"].
    """
    final = reducido.get("final")
    if not final or "campeon" not in final:
        raise ValueError(
            "No pude extraer el campeón del reducido: reducido['final'] "
            f"no tiene la forma esperada (llegó: {final!r})"
        )
    return final["campeon"]


class PrimeraCAdapter(TournamentEngine):
    """Adaptador de Primera C. Ver mapeo completo en el docstring del
    módulo y en el punto 4 de PLAN_MODO_TEMPORADA_NACIONAL.txt."""

    def __init__(self):
        self._datos_web = None
        self._clubes = None

    def setup(self, clubes):
        # Todavía no se usa: correr_simulacion() lee su propio CSV
        # (datos/tabla_primerac.csv) directamente, igual que hoy. Se
        # deja la firma lista para cuando el roster venga del
        # ClubRegistry real (Etapa 5+). Ver TournamentEngine.setup().
        self._clubes = clubes

    def run(self, n_sims=1000):
        self._datos_web = main_primerac.correr_simulacion(
            n_sims=n_sims, imprimir=False, guardar_json=False
        )

    def result(self):
        if self._datos_web is None:
            raise RuntimeError(
                "PrimeraCAdapter.result() llamado antes de run()."
            )

        datos_web = self._datos_web
        ganador = datos_web["final_ascenso"]["ganador"]
        campeon_reducido = _extraer_campeon_reducido(datos_web["reducido"])

        return ResultadoTorneo(
            campeon=ganador,
            ascensos=[ganador, campeon_reducido],
            descensos=[],
            clasificados_copa=[],
            datos_crudos=datos_web,
        )
