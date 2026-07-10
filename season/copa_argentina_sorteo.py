    # -*- coding: utf-8 -*-
"""
season/copa_argentina_sorteo.py

Sorteo de 32avos de final de la PRÓXIMA Copa Argentina, a partir de los
64 clasificados que arma CopaArgentinaManager.calcular() (ver
season/copa_argentina_manager.py). Sin esto, el Modo Temporada corría
la Copa Argentina siempre contra el cuadro real ya sorteado (datos/
copa_argentina.csv) en vez de generar cruces nuevos con los equipos que
clasificaron en la simulación -- ver LIMITACIÓN DOCUMENTADA en
api/index.py (season_play_endpoint).

Reglamento del sorteo (mismo criterio real de AFA):

  Grupo 1 (32 equipos) -- ocupan las posiciones "local" del cuadro:
    - Los 30 equipos de Primera División (LPF).
    - El campeón de la Primera Nacional (ascenso directo).
    - El ganador del segundo ascenso a Primera (Reducido de Nacional).

  Grupo 2 (32 equipos) -- ocupan las posiciones "visitante", opuestas:
    - Los 13 equipos restantes de Primera Nacional.
    - Los 5 de B Metropolitana.
    - Los 4 de Primera C.
    - Los 10 de Federal A.

Condiciones del sorteo: participan los 64, cada equipo aparece una sola
vez, se generan 32 cruces, NO hay cabezas de serie (dentro de cada
grupo cualquiera puede tocarle a cualquiera), y no hay restricción por
categoría/provincia/zona -- se baraja cada grupo de forma independiente
y se cruzan uno a uno (posición i de Grupo 1 vs. posición i de Grupo 2).

CopaArgentinaManager.calcular() ya deja el campeón y el ganador del
Reducido de Nacional como los dos primeros elementos de
por_division["nacional"] (ver ese módulo) -- por eso alcanza con partir
esa lista en [:2] / [2:], sin tener que volver a tocar ResultadoTorneo
acá.
"""
import random

RONDA_INICIAL = "32avos"
CANTIDAD_LLAVES = 32


def armar_grupos_sorteo(clasificacion_copa_argentina: dict) -> tuple[list[str], list[str]]:
    """Devuelve (grupo1, grupo2), cada uno con 32 nombres, SIN barajar
    todavía (ver sortear_32avos() para el sorteo con orden aleatorio).
    Levanta ValueError si los conteos no cierran 32+32 (por ejemplo si
    CopaArgentinaManager.calcular() vino con avisos de conteo raro)."""
    por_division = clasificacion_copa_argentina["por_division"]

    lpf = list(por_division.get("lpf", []))
    nacional = list(por_division.get("nacional", []))
    bmetro = list(por_division.get("bmetro", []))
    primerac = list(por_division.get("primerac", []))
    federal_a = list(por_division.get("federal_a", []))

    cabezas_nacional, resto_nacional = nacional[:2], nacional[2:]

    grupo1 = lpf + cabezas_nacional
    grupo2 = resto_nacional + bmetro + primerac + federal_a

    if len(grupo1) != CANTIDAD_LLAVES or len(grupo2) != CANTIDAD_LLAVES:
        raise ValueError(
            f"El sorteo de 32avos necesita 32+32 clasificados -- se armaron "
            f"Grupo 1={len(grupo1)} (LPF={len(lpf)} + cabezas Nacional="
            f"{len(cabezas_nacional)}) y Grupo 2={len(grupo2)} (resto Nacional="
            f"{len(resto_nacional)} + BMetro={len(bmetro)} + Primera C="
            f"{len(primerac)} + Federal A={len(federal_a)}). Revisar los "
            f"avisos de CopaArgentinaManager.calcular()."
        )

    return grupo1, grupo2


def sortear_32avos(clasificacion_copa_argentina: dict, rng: random.Random | None = None) -> list[dict]:
    """Sortea el cuadro de 32avos y devuelve una lista de 32 cruces con
    el MISMO shape que data_access.cup_records() (una fila por cruce:
    ronda/llave/equipo_local/equipo_visitante/goles_local/
    goles_visitante/ganador, estos 3 últimos vacíos porque todavía no
    se jugaron) -- así se puede pasar directo como cuadro_override de
    EstadisticasCopa (ver main_copa.correr_simulacion_copa()) sin que
    el motor de simulación tenga que enterarse de que es un sorteo
    nuevo en vez del cuadro real.

    Las rondas siguientes (16avos, octavos, cuartos, semis, final) NO
    se arman acá -- EstadisticasCopa.simular_copa() las cablea solas a
    partir de los ganadores de la ronda anterior (ver su docstring),
    con el mismo mecanismo que ya usa para completar el cuadro real
    cuando hay cruces pendientes.
    """
    rng = rng or random.Random()
    grupo1, grupo2 = armar_grupos_sorteo(clasificacion_copa_argentina)

    grupo1_sorteado = grupo1[:]
    grupo2_sorteado = grupo2[:]
    rng.shuffle(grupo1_sorteado)
    rng.shuffle(grupo2_sorteado)

    return [
        {
            "ronda": RONDA_INICIAL,
            "llave": llave,
            "equipo_local": grupo1_sorteado[llave - 1],
            "equipo_visitante": grupo2_sorteado[llave - 1],
            "goles_local": "",
            "goles_visitante": "",
            "ganador": "",
        }
        for llave in range(1, CANTIDAD_LLAVES + 1)
    ]
