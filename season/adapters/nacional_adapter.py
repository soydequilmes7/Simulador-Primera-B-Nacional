"""
Adaptador de Primera Nacional para el SeasonEngine.

Envuelve main.correr_simulacion() (el motor real, sin tocarlo) y
traduce su dict de salida a ResultadoTorneo.

Shape de datos_web relevante (confirmado contra el código real de
main.py y modelos/estadisticas.py, NO por el resumen del plan):

    datos_web["final_ascenso"]["ganador"]   -> 1er ascenso (directo)
    datos_web["final_ascenso"]["perdedor"]  -> pasa al Reducido
    datos_web["reducido"]["final"]["campeon"] -> 2do ascenso

Igual que en Primera C, el campeón del Reducido NO se guarda como
clave suelta en datos_web: jugar_reducido() devuelve (campeon, dict)
pero main.py solo persiste el dict en datos_web["reducido"]. La final
del Reducido se juega con jugar_serie_ida_vuelta(), cuyo detalle sí
trae una clave "campeon" directa -- por eso alcanza con
reducido["final"]["campeon"], sin tener que rejugar ni inferir nada.

Diferencia con Primera C (documentada, no asumida): en Nacional la
final por el 1er ascenso es a PARTIDO ÚNICO (jugar_final_ascenso),
mientras que en Primera C jugar_final_ascenso recibe las tablas
completas. Esto no afecta al adaptador porque en ambos casos
datos_web["final_ascenso"]["ganador"] ya viene resuelto como string
plano -- la diferencia vive adentro del motor, no en el shape de
salida que consume el adaptador.

Descensos: main.py (Primera Nacional) NO expone descensos como clave
suelta de datos_web (a diferencia de main_lpf.py, que sí trae
calcular_descensos()). Pero la regla real SÍ existe en el motor --
está adentro de Estadisticas.monte_carlo() (modelos/estadisticas.py),
usada ahí solo para las estadísticas de % descenso:

    descendidos_a = tablas["A"].iloc[-2:]["equipo"]
    descendidos_b = tablas["B"].iloc[-2:]["equipo"]

(los últimos 2 de cada zona, 4 en total, sobre la MISMA tabla ya
ordenada que usa main.py para sacar puntero_a/puntero_b). Confirmado
con el reglamento real vigente de AFA (Primera Nacional 2026): "los
dos últimos de cada zona pierden la categoría hacia la Primera B
Metropolitana o el Torneo Federal A, según la afiliación
correspondiente" -- ver PromotionManager/geografia_clubes.py para
cómo se resuelve esa afiliación.

Se aplica la MISMA regla acá, sobre datos_web["tablas"] de la corrida
única (no sobre el Monte Carlo, que es un resumen estadístico aparte)
-- _extraer_descendidos() replica la lógica sin tocar main.py ni
estadisticas.py. datos_web["tablas"]["A"]/["B"] son listas de dicts
(to_dict(orient="records")) que preservan el mismo orden que la
DataFrame original -- los últimos 2 elementos de cada lista son
exactamente los mismos 2 equipos que .iloc[-2:] tomaría.
"""

import main as main_nacional


def _extraer_campeon_reducido(reducido: dict) -> str:
    """Rescata el nombre del campeón del Reducido desde el bracket.
    Ver docstring del módulo: no está guardado como clave suelta."""
    return reducido["final"]["campeon"]


def _extraer_descendidos(tablas: dict) -> list:
    """Últimos 2 de cada zona (4 en total), misma regla que ya usa
    Estadisticas.monte_carlo() para las estadísticas de % descenso.
    Ver docstring del módulo."""
    descendidos = []
    for zona in ("A", "B"):
        ultimos_2 = tablas[zona][-2:]
        descendidos.extend(fila["equipo"] for fila in ultimos_2)
    return descendidos


from season.tournament_adapter import TournamentEngine, ResultadoTorneo


class NacionalAdapter(TournamentEngine):

    def __init__(self):
        self._datos_web = None

    def setup(self, **kwargs):
        # main.correr_simulacion() lee sus propios CSV vía
        # data_access.league_data("nacional"); no necesita nada externo
        # todavía (ver nota en TournamentEngine.setup).
        pass

    def run(self, n_sims: int = 1000):
        self._datos_web = main_nacional.correr_simulacion(
            n_sims=n_sims, imprimir=False, guardar_json=False
        )

    def result(self) -> ResultadoTorneo:
        if self._datos_web is None:
            raise RuntimeError("Llamá a run() antes de result().")

        datos_web = self._datos_web
        ganador_directo = datos_web["final_ascenso"]["ganador"]
        campeon_reducido = _extraer_campeon_reducido(datos_web["reducido"])
        descensos = _extraer_descendidos(datos_web["tablas"])

        return ResultadoTorneo(
            campeon=ganador_directo,
            ascensos=[ganador_directo, campeon_reducido],
            descensos=descensos,
            clasificados_copa=[],
            datos_crudos=datos_web,
            # Item e (addendum Etapa 6): ratings finales de cada club de
            # Nacional, ya calculados por Estadisticas.calcular_ratings()
            # y expuestos por correr_simulacion() (ver item d, main.py).
            # Es la fuente que necesita NacionalAdapter para que los
            # ascendidos a LPF hereden su rating real vía
            # RatingCarryoverPolicy.rating_para_recien_llegado(), en vez
            # de caer al rating genérico (degradación prevista, pero ya
            # no necesaria una vez cableado esto). .get() con default {}
            # por las mismas razones que en LPFAdapter.
            ratings_finales=datos_web.get("ratings_finales", {}),
        )
