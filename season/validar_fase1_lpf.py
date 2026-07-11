# -*- coding: utf-8 -*-
"""
season/validar_fase1_lpf.py

Validación de la Fase 1 del plan de HANDOFF_carryover_ratings.md:
aplicar la infraestructura de Fase 0 (memoria EWMA + handicap de
adaptación) sobre el camino de ratings iniciales del Apertura de LPF.

Decisión de diseño (documentada acá porque el plan original hablaba
de tocar directamente ratings_desde_tabla_anual()/
simular_apertura_desde_carryover() en modelos/estadisticas_lpf.py):
NO se tocó ese archivo. ratings_desde_tabla_anual() sigue devolviendo
el rating "crudo" de la temporada que termina, sin cambios -- la
combinación con memoria_ewma()/handicap se hace en
HistoryManager._ratings_iniciales_lpf() (season/history_manager.py),
que ya era el punto donde se arma el dict final de ratings_iniciales
y donde SÍ hay acceso a club_registry (con Club.history). Mismo
resultado funcional, cero cambios en modelos/estadisticas_lpf.py
-- más acotado, más fácil de revertir si hace falta.

No toca Supabase -- data_access no se importa en este flujo (LPF
recibe todo por parámetro: tabla_anual/zona_por_club ya construidos
por el caller a partir de resultados["lpf"].datos_crudos).

Correrlo desde la raíz del proyecto:

    python -m season.validar_fase1_lpf
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from modelos.club import Club
from modelos.estadisticas_lpf import EstadisticasLPF
from season.history_manager import HistoryManager
from season.rating_carryover import combinar_con_memoria, CAMPOS_RATING


def _comparar(nombre_caso: str, esperado: dict, obtenido: dict, tolerancia=1e-9) -> list:
    errores = []
    for campo in CAMPOS_RATING:
        if abs(esperado[campo] - obtenido[campo]) > tolerancia:
            errores.append(
                f"[{nombre_caso}] {campo}: esperado {esperado[campo]}, obtenido {obtenido[campo]}"
            )
    return errores


@dataclass
class _FakeResultadoTorneo:
    datos_crudos: dict = field(default_factory=dict)
    ratings_finales: dict = field(default_factory=dict)


class _FakeClubRegistry:
    def __init__(self, clubes: list[Club]):
        self._por_nombre = {c.name: c for c in clubes}

    def get_by_name(self, name: str):
        return self._por_nombre.get(name)


# ----------------------------------------------------------------
# Datos sintéticos: 2 clubes que YA jugaban LPF la temporada que
# termina (con distinta cantidad de historial previo) + 1 club recién
# ascendido desde Nacional.
# ----------------------------------------------------------------
TABLA_ANUAL = pd.DataFrame([
    # "Club Asentado": rindió bien la temporada que termina, y tiene
    # 2 temporadas previas de historial EN LPF -- sin handicap.
    {"equipo": "Club Asentado", "puntos": 70, "gf": 55, "gc": 30, "dg": 25},
    # "Club Reciente": ascendió hace 1 temporada, esta es su 2da en
    # LPF -- todavía le queda handicap (factor 2/3).
    {"equipo": "Club Reciente", "puntos": 40, "gf": 35, "gc": 40, "dg": -5},
    # Rivales de zona -- solo hacen falta para que
    # _partidos_jugados_tabla_anual() no divida por cero (zona de 1
    # solo club = 0 partidos jugados). No se usan sus ratings en los
    # chequeos.
    {"equipo": "Club Rival A", "puntos": 50, "gf": 40, "gc": 35, "dg": 5},
    {"equipo": "Club Rival B", "puntos": 45, "gf": 38, "gc": 38, "dg": 0},
])
ZONA_POR_CLUB_ACTUAL = {
    "Club Asentado": "A", "Club Rival A": "A",
    "Club Reciente": "B", "Club Rival B": "B",
}

APERTURA_ACTUAL = {
    "A": [{"equipo": "Club Asentado"}, {"equipo": "Club Rival A"}],
    "B": [{"equipo": "Club Reciente"}, {"equipo": "Club Rival B"}],
}


def validar_ratings_iniciales_con_memoria() -> list:
    print("\n[Parte A] _ratings_iniciales_lpf() -- memoria EWMA + handicap para los que continúan")
    errores = []

    # rating "crudo" real, calculado con la función SIN TOCAR de
    # estadisticas_lpf.py -- para comparar contra lo que devuelve el
    # flujo completo.
    ratings_continuan = EstadisticasLPF().ratings_desde_tabla_anual(TABLA_ANUAL, ZONA_POR_CLUB_ACTUAL)
    print(f"  ratings crudos (sin memoria): {ratings_continuan}")

    club_asentado = Club(id=1, name="Club Asentado", division="Liga Profesional")
    club_asentado.history = [
        {"temporada": "2024", "division": "Liga Profesional", "ratings": {
            "ataque_local": 1.10, "ataque_visitante": 0.95, "defensa_local": 1.05, "defensa_visitante": 0.98,
        }},
        {"temporada": "2025", "division": "Liga Profesional", "ratings": {
            "ataque_local": 1.15, "ataque_visitante": 1.00, "defensa_local": 1.08, "defensa_visitante": 1.00,
        }},
    ]

    club_reciente = Club(id=2, name="Club Reciente", division="Liga Profesional")
    club_reciente.history = [
        {"temporada": "2025", "division": "Liga Profesional", "ratings": {
            "ataque_local": 0.75, "ataque_visitante": 1.20, "defensa_local": 0.80, "defensa_visitante": 1.15,
        }},
    ]

    club_ascendido = Club(id=3, name="Club Ascendido", division="Liga Profesional")  # ya promocionado
    club_registry = _FakeClubRegistry([club_asentado, club_reciente, club_ascendido])

    resultados = {
        "lpf": _FakeResultadoTorneo(datos_crudos={
            "tabla_anual": TABLA_ANUAL.to_dict("records"),
            "apertura": APERTURA_ACTUAL,
        }),
        "nacional": _FakeResultadoTorneo(ratings_finales={
            "Club Ascendido": {
                "ataque_local": 1.30, "ataque_visitante": 1.10, "defensa_local": 0.90, "defensa_visitante": 0.95,
            },
        }),
    }
    roster_siguiente = ["Club Asentado", "Club Reciente", "Club Ascendido"]

    hm = HistoryManager(repo=object())
    obtenido = hm._ratings_iniciales_lpf(resultados, roster_siguiente, club_registry)
    print(f"  ratings_iniciales devueltos: {obtenido}")

    # Club Asentado: temporadas_consecutivas_en_division = 2 == N_TEMPORADAS_HANDICAP
    # -> combinar_con_memoria sin handicap (factor 1.0), solo EWMA.
    esperado_asentado = combinar_con_memoria(ratings_continuan["Club Asentado"], club_asentado, "lpf")
    errores += _comparar("Club Asentado", esperado_asentado, obtenido["Club Asentado"])
    if esperado_asentado == ratings_continuan["Club Asentado"]:
        errores.append("[Club Asentado] la memoria EWMA no debería devolver EXACTO el rating crudo (hay historial)")

    # Club Reciente: temporadas_consecutivas_en_division = 1 -> handicap 2/3.
    esperado_reciente = combinar_con_memoria(ratings_continuan["Club Reciente"], club_reciente, "lpf")
    errores += _comparar("Club Reciente", esperado_reciente, obtenido["Club Reciente"])

    # Club Ascendido: no está en ratings_continuan -> pasa por
    # rating_para_recien_llegado(), ya validado en Fase 0. Solo
    # confirmamos que el wiring llega bien (dict con las 4 claves).
    if set(obtenido["Club Ascendido"].keys()) != set(CAMPOS_RATING):
        errores.append(f"[Club Ascendido] shape inesperado: {obtenido['Club Ascendido']}")
    else:
        print(f"  Club Ascendido (recién llegado, vía rating_para_recien_llegado): {obtenido['Club Ascendido']}")

    return errores


def validar_simulacion_apertura_end_to_end() -> list:
    """Corrida real de simular_apertura_desde_carryover() (motor SIN
    TOCAR, Dixon-Coles real + jugar_playoffs con octavos de 8 por
    zona) con los ratings ya combinados -- confirma que el wiring de
    punta a punta no rompe nada y que el Apertura se puede simular y
    arma standings completos."""
    print("\n[Parte B] Corrida real de simular_apertura_desde_carryover() con ratings de Fase 1")
    errores = []

    tabla_anual_16, zona_por_club, apertura_zonas = _roster_completo_16("Club Asentado", "Club Reciente")
    roster = list(zona_por_club.keys())

    club_asentado = Club(id=1, name="Club Asentado", division="Liga Profesional")
    club_asentado.history = [
        {"temporada": "2025", "division": "Liga Profesional", "ratings": {
            "ataque_local": 1.15, "ataque_visitante": 1.00, "defensa_local": 1.08, "defensa_visitante": 1.00,
        }},
    ]
    club_reciente = Club(id=2, name="Club Reciente", division="Liga Profesional")
    club_registry = _FakeClubRegistry([club_asentado, club_reciente])

    resultados = {
        "lpf": _FakeResultadoTorneo(datos_crudos={
            "tabla_anual": tabla_anual_16.to_dict("records"),
            "apertura": apertura_zonas,
        }),
    }

    hm = HistoryManager(repo=object())
    standings, campeon, _detalle_playoffs = hm._simular_apertura_lpf(roster, zona_por_club, resultados, club_registry)

    equipos_en_standings = {fila["equipo"] for fila in standings}
    print(f"  {len(equipos_en_standings)} equipos en standings (roster: {len(roster)})")
    print(f"  campeón simulado: {campeon}")
    if equipos_en_standings != set(roster):
        errores.append(f"standings no cubre todo el roster: {equipos_en_standings.symmetric_difference(set(roster))}")
    if campeon not in roster:
        errores.append(f"campeón {campeon!r} no está en el roster")
    for fila in standings:
        if fila["partidos_jugados"] != 14:  # zonas de 8 clubes, ida y vuelta = 2*(8-1)
            errores.append(f"partidos_jugados inesperado para {fila['equipo']}: {fila['partidos_jugados']}")

    return errores


def _roster_completo_16(club_asentado: str, club_reciente: str) -> tuple[pd.DataFrame, dict, dict]:
    """jugar_playoffs() (heredado, SIN TOCAR) arma octavos fijos con
    posiciones 1..8 por zona -- hace falta un roster de 16 clubes (8
    por zona) para poder correr una simulación real de punta a punta.
    Arma una tabla_anual sintética con esa forma; club_asentado y
    club_reciente ocupan la posición 1 de cada zona (mejor rendimiento
    -- así entran directo a la parte alta del cuadro), el resto son
    rellenos con rendimiento decreciente."""
    filas = []
    zona_por_club: dict[str, str] = {}
    apertura_zonas: dict[str, list] = {"A": [], "B": []}
    for zona, protagonista in (("A", club_asentado), ("B", club_reciente)):
        nombres = [protagonista] + [f"Relleno {zona}{i}" for i in range(2, 9)]
        for i, nombre in enumerate(nombres):
            puntos = 70 - i * 6
            filas.append({
                "equipo": nombre, "puntos": puntos,
                "gf": 50 - i * 3, "gc": 25 + i * 2, "dg": (50 - i * 3) - (25 + i * 2),
            })
            zona_por_club[nombre] = zona
            apertura_zonas[zona].append({"equipo": nombre})
    return pd.DataFrame(filas), zona_por_club, apertura_zonas


def main():
    print("=" * 70)
    print("VALIDACIÓN FASE 1 -- LPF con memoria EWMA + handicap")
    print("(HANDOFF_carryover_ratings.md)")
    print("=" * 70)

    errores = []
    errores += validar_ratings_iniciales_con_memoria()
    errores += validar_simulacion_apertura_end_to_end()

    print("\n" + "=" * 70)
    if errores:
        print(f"❌ {len(errores)} error(es):")
        for e in errores:
            print(f"  - {e}")
    else:
        print("✅ Todo OK -- Fase 1 (LPF) validada.")
    print("=" * 70)


if __name__ == "__main__":
    main()
