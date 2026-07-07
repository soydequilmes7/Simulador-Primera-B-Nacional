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

Descensos y clasificados a copa: main.py (Primera Nacional) no los
calcula en este archivo -- a diferencia de main_lpf.py, que sí trae
calcular_descensos()/calcular_copas(). Quedan como listas vacías acá;
si más adelante aparece esa lógica en el motor real, se agrega sin
romper la interfaz.
"""

import main as main_nacional


def _extraer_campeon_reducido(reducido: dict) -> str:
    """Rescata el nombre del campeón del Reducido desde el bracket.
    Ver docstring del módulo: no está guardado como clave suelta."""
    return reducido["final"]["campeon"]


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

        return ResultadoTorneo(
            campeon=ganador_directo,
            ascensos=[ganador_directo, campeon_reducido],
            descensos=[],
            clasificados_copa=[],
            datos_crudos=datos_web,
        )
