# -*- coding: utf-8 -*-
"""
season/adapters/lpf_adapter.py

Adaptador de la Liga Profesional (LPF) para el SeasonEngine. Envuelve
main_lpf.correr_simulacion_lpf() tal cual (no se toca el motor) y
traduce su dict de salida (datos_web, armado por armar_datos_web_lpf()
en main_lpf.py) al shape común ResultadoTorneo.

Decisiones de diseño CONFIRMADAS CON EL USUARIO (no asumidas por
Claude, ver conversación de Etapa 2 -- LPFAdapter):

  1. ResultadoTorneo.campeon = datos_web["campeon_clausura"].
     LPF no tiene un único "campeón" obvio en el dict: existen
     campeon_clausura (lo único que de verdad simula este motor),
     EstadisticasLPF.CAMPEON_APERTURA (dato histórico fijo, "Belgrano",
     el Apertura ya se jugó en la realidad y NO se simula acá) y
     datos_web["trofeo"] (Apertura vs Clausura a partido único, Art.
     20 del reglamento -- salvo que sea el mismo equipo en ambos
     torneos, caso en que ni siquiera se simula esa final, ver
     calcular_trofeo_campeones()). Se decidió que el campeón relevante
     para el SeasonEngine es el del Clausura, sin jugar el Trofeo de
     Campeones.

  2. ResultadoTorneo.clasificados_copa = libertadores_2027 +
     sudamericana_2027, FILTRANDO el string placeholder que
     calcular_copas() mezcla con nombres reales de clubes para el cupo
     "ARGENTINA 3" (campeón de Copa Argentina, no simulado en este
     proyecto). El filtro es por contenido ("no simulado" en el
     string) en vez de por igualdad exacta, para no romper si el texto
     del placeholder cambia de redacción más adelante.

  3. ResultadoTorneo.ascensos = [] siempre: la LPF es la máxima
     categoría, no tiene ascenso.

  4. ResultadoTorneo.descensos = datos_web["descensos"] tal cual
     (calcular_descensos() ya devuelve una lista de 2 nombres de
     clubes, no hace falta traducir nada).

GAP DE ARQUITECTURA CONOCIDO (no resuelto acá, ver
PLAN_MODO_TEMPORADA_NACIONAL.txt, Etapa 6): el Apertura no se simula,
se lee ya jugado desde tablalpf.csv. Cuando el SeasonEngine tenga que
generar la temporada N+2, hará falta un Apertura simulado para
alimentar el Clausura siguiente -- hoy ese mecanismo no existe. Esto
NO bloquea Etapa 2 (el adaptador solo envuelve el comportamiento
actual del motor, sea cual sea), pero queda anotado para no perderlo
antes de llegar a Etapa 6.
"""

import main_lpf
from season.tournament_adapter import ResultadoTorneo, TournamentEngine


def _extraer_clasificados_copa(copas: dict) -> list:
    """Junta libertadores_2027 + sudamericana_2027 en una sola lista,
    filtrando el placeholder de Copa Argentina (no es un club real,
    ver docstring del módulo)."""
    todos = copas["libertadores_2027"] + copas["sudamericana_2027"]
    return [nombre for nombre in todos if "no simulado" not in nombre]


class LPFAdapter(TournamentEngine):

    def __init__(self):
        self._datos_web = None

    def setup(self, **kwargs):
        # main_lpf.correr_simulacion_lpf() lee sus propios CSV vía
        # data_access.league_data("lpf") + data_access.lpf_average_history_df();
        # no necesita nada externo todavía (ver nota en
        # TournamentEngine.setup).
        pass

    def run(self, n_sims: int = 1000):
        self._datos_web = main_lpf.correr_simulacion_lpf(
            n_sims=n_sims, imprimir=False, guardar_json=False
        )

    def result(self) -> ResultadoTorneo:
        if self._datos_web is None:
            raise RuntimeError("Llamá a run() antes de result().")

        datos_web = self._datos_web
        clasificados_copa = _extraer_clasificados_copa(datos_web["copas"])

        return ResultadoTorneo(
            campeon=datos_web["campeon_clausura"],
            ascensos=[],
            descensos=datos_web["descensos"],
            clasificados_copa=clasificados_copa,
            datos_crudos=datos_web,
            # Item c (addendum Etapa 6): ratings finales de cada club LPF,
            # ya calculados por calcular_ratings_lpf() y expuestos por
            # armar_datos_web_lpf() (ver item b, main_lpf.py). .get() con
            # default {} por si corre contra un datos_web viejo (motor
            # LPF sin este cambio todavía) -- no debería pasar en
            # producción, pero no rompe el adaptador si pasa.
            ratings_finales=datos_web.get("ratings_finales", {}),
        )
