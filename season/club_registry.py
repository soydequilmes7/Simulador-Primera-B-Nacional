# -*- coding: utf-8 -*-
"""
season/club_registry.py

ClubRegistry: fuente única de verdad de qué Club existe y a qué división
pertenece HOY. Etapa 0 del Modo Temporada Nacional -- de solo lectura:
build_from_current_data() arma el registro a partir de las tablas de
posiciones de cada división vía data_access.league_data(slug), que es
EXACTAMENTE la misma función que ya usa cada cargar_datos*() de los
motores existentes (main.py, main_lpf.py, main_bmetro.py, main_federal.py,
main_primerac.py). No hace I/O propio, no escribe nada, no toca ningún
main_*.py ni estadisticas_*.py.

IMPORTANTE -- por qué la Copa Argentina no entra acá: la Copa no es una
"división" en el sentido de pertenencia exclusiva de clubes. Participan
clubes de varias divisiones (algunos ni siquiera modelados en este
registro, p. ej. invitados del Torneo Regional Federal Amateur -- ver
ATAQUE_ASCENSO/DEFENSA_ASCENSO en estadisticas_copa.py, que ya contempla
esto) y un mismo club de LPF/Nacional/etc. juega la Copa sin dejar su
división de origen. El ClubRegistry modela pertenencia a UNA división
por vez (para poder aplicar ascensos/descensos); la Copa se sigue
tratando aparte, tal como hoy.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import data_access
from modelos.club import Club

# slug interno de data_access.league_data() -> nombre de división "lindo"
# (el que se usa para pintar en la UI / guardar en historial). data_access
# usa "federal_a" como slug -- se respeta tal cual está en data_access.py,
# no "federal".
DIVISIONES: Dict[str, str] = {
    "lpf": "Liga Profesional",
    "nacional": "Primera Nacional",
    "bmetro": "Primera B Metropolitana",
    "federal_a": "Federal A",
    "primerac": "Primera C",
}


def _normalizar_nombre(slug: str, nombre_crudo: str) -> str:
    """Traduce el nombre "crudo" tal como aparece en tabla_X.csv al
    nombre que usa el resto del ecosistema para esa división.

    Solo LPF necesita esto: estadisticas_lpf.py normaliza internamente
    nombres cortos ("Riestra", "Boca Jrs.", "Vélez") a los nombres
    completos reales ("Deportivo Riestra", "Boca Juniors", "Vélez
    Sarsfield") vía su propio NORMALIZACION_NOMBRES -- por eso TODO lo
    que devuelve main_lpf.py (campeón, descensos, clasificados a copa)
    ya viene con el nombre completo. Si el import falla (por ejemplo,
    corriendo ClubRegistry aislado sin el resto del repo disponible),
    se sigue con el nombre crudo tal cual en vez de romper -- degrada
    con gracia, no bloquea Etapa 0."""
    if slug != "lpf":
        return nombre_crudo
    try:
        from modelos.estadisticas_lpf import normalizar
    except ImportError:
        return nombre_crudo
    return normalizar(nombre_crudo)


class ClubRegistry:
    """Registro de todos los Club conocidos, indexados por id y por
    nombre. No tiene ninguna lógica de simulación ni de ascensos/
    descensos -- eso vive en PromotionManager (etapas siguientes del
    plan), que va a MUTAR club.division sobre este mismo registro, no a
    reconstruirlo."""

    def __init__(self) -> None:
        self._por_id: Dict[int, Club] = {}
        self._por_nombre: Dict[str, Club] = {}
        self._siguiente_id = 1

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------
    @classmethod
    def build_from_current_data(cls, divisiones: Optional[Dict[str, str]] = None) -> "ClubRegistry":
        """Arma el registro leyendo la tabla de posiciones actual de cada
        división vía data_access.league_data(slug) -- la MISMA función
        que ya usa cada cargar_datos*() de los motores existentes. No
        duplica lectura de CSV/DB, no escribe nada.

        Lanza ValueError si el mismo nombre de equipo aparece en más de
        una división: violaría la regla de "un club, una sola vez", y en
        la práctica indicaría un problema de datos (nombre mal cargado
        en el tabla_X.csv equivocado) que conviene que reviente acá y no
        se filtre en silencio a las etapas siguientes.

        CASO ESPECIAL LPF: tablalpf.csv usa nombres cortos ("Riestra",
        "Boca Jrs.", "Vélez", etc.) que estadisticas_lpf.py NORMALIZA
        internamente a los nombres completos reales ("Deportivo
        Riestra", "Boca Juniors", "Vélez Sarsfield") vía
        NORMALIZACION_NOMBRES -- por eso TODO lo que devuelve main_lpf.py
        (campeón, descensos, clasificados a copa) ya viene con el
        nombre completo. Si acá se registrara el nombre corto tal cual
        aparece en el CSV, PromotionManager no podría encontrar en el
        registro a ninguno de esos ~19 clubes cuando ascienden o
        descienden (se detectó corriendo la Etapa 5 con datos reales:
        "Deportivo Riestra" no aparecía en el registro al intentar
        moverlo). Se aplica la MISMA normalización acá, importada
        directo de estadisticas_lpf.py (no se duplica el diccionario),
        para que ClubRegistry hable el mismo idioma que el resto del
        ecosistema de LPF."""
        divisiones = divisiones or DIVISIONES
        registro = cls()

        vistos_en: Dict[str, str] = {}  # nombre -> división donde ya se vio

        for slug, nombre_division in divisiones.items():
            _resultados, _fixture, tabla = data_access.league_data(slug)

            for nombre_crudo in tabla["equipo"].tolist():
                nombre = _normalizar_nombre(slug, nombre_crudo)
                if nombre in vistos_en:
                    raise ValueError(
                        f"Club duplicado entre divisiones: '{nombre}' aparece en "
                        f"'{vistos_en[nombre]}' y en '{nombre_division}'. Un club "
                        f"debe pertenecer a una sola división -- revisar los datos "
                        f"de origen antes de seguir con la Etapa 1."
                    )
                vistos_en[nombre] = nombre_division
                registro._agregar(nombre, nombre_division)

        return registro

    def _agregar(self, name: str, division: str) -> Club:
        club = Club(id=self._siguiente_id, name=name, division=division)
        self._por_id[club.id] = club
        self._por_nombre[name] = club
        self._siguiente_id += 1
        return club

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def get_by_division(self, division: str) -> List[Club]:
        """Clubes que pertenecen HOY a esta división. No viene ordenado
        por posición de tabla -- para eso cada TournamentEngine sigue
        teniendo su propia tabla real; este registro solo sabe "quién
        pertenece a quién", no el rendimiento deportivo."""
        return [c for c in self._por_id.values() if c.division == division]

    def get_by_name(self, name: str) -> Optional[Club]:
        return self._por_nombre.get(name)

    def get_by_id(self, club_id: int) -> Optional[Club]:
        return self._por_id.get(club_id)

    def all_clubs(self) -> List[Club]:
        return list(self._por_id.values())

    # ------------------------------------------------------------------
    # Mutación -- usado por PromotionManager (Etapa 4 del plan)
    # ------------------------------------------------------------------
    def agregar_club(self, name: str, division: str) -> Club:
        """Agrega un club NUEVO al registro (que no existía antes),
        con id autoincremental igual que build_from_current_data().

        Pensado para PromotionManager (Etapa 4): clubes de relleno que
        reemplazan bajas hacia divisiones que este proyecto no modela
        (ej. Federal A -> Reválida -> torneo regional, ver
        season/promotion_manager.py). NO se usa durante la
        construcción normal del registro -- build_from_current_data()
        sigue siendo la única forma de arrancar desde los datos
        reales; este método es para altas posteriores.

        Lanza ValueError si ya existe un club con ese nombre (misma
        regla de unicidad que build_from_current_data())."""
        if name in self._por_nombre:
            raise ValueError(
                f"Ya existe un club con el nombre '{name}' en el registro -- "
                f"no se puede agregar de nuevo."
            )
        return self._agregar(name, division)

    def renombrar_club(self, nombre_actual: str, nombre_nuevo: str) -> Club:
        """Cambia el nombre de un club YA existente, reindexando
        `_por_nombre` (el `id` y todo lo demás no se tocan). Pensado
        para PromotionManager: cuando un club asciende a una división
        cuyo motor normaliza alias cortos internamente (hoy solo LPF,
        ver estadisticas_lpf.NORMALIZACION_NOMBRES), hay que aplicar
        esa misma normalización ACÁ, en el momento del ascenso -- si
        no, el club queda con el alias corto en el registro y en el
        próximo fixture generado, y la temporada siguiente
        EstadisticasLPF.cargar_datos_lpf() lo renombra por su cuenta
        al cargar el fixture, fusionándolo por accidente con el club
        que YA tenía el nombre completo (bug real: dos clubes
        distintos terminan compartiendo un nombre y sus partidos se
        suman en uno solo -- ver el commit que agrega este método).

        Si nombre_actual == nombre_nuevo no hace nada (caso normal:
        el club ya tenía el nombre completo). Lanza ValueError si
        nombre_actual no existe, o si nombre_nuevo ya pertenece a
        OTRO club (colisión real -- mejor fallar acá, con el club y
        la división a mano, que más adelante con un fixture roto y
        un mensaje de error genérico)."""
        club = self._por_nombre.get(nombre_actual)
        if club is None:
            raise ValueError(
                f"No existe ningún club con el nombre '{nombre_actual}' "
                f"en el registro."
            )
        if nombre_actual == nombre_nuevo:
            return club

        existente = self._por_nombre.get(nombre_nuevo)
        if existente is not None and existente is not club:
            raise ValueError(
                f"Colisión de nombres: '{nombre_actual}' normaliza a "
                f"'{nombre_nuevo}', pero ese nombre ya pertenece a otro "
                f"club distinto (id={existente.id}, división "
                f"'{existente.division}'). Esto indica que el club que "
                f"está ascendiendo llegó con un alias corto sin "
                f"desambiguar en el origen de datos -- revisar el "
                f"nombre real ahí (probablemente Supabase) antes de "
                f"re-simular."
            )

        del self._por_nombre[nombre_actual]
        club.name = nombre_nuevo
        self._por_nombre[nombre_nuevo] = club
        return club

    def retirar_club(self, name: str) -> Optional[Club]:
        """Saca un club del registro por completo (no solo le cambia
        la división). Pensado para PromotionManager (Etapa 4): bajas
        hacia divisiones que este proyecto no modela (ej. Federal A ->
        Reválida -> torneo regional, no simulado acá).

        Devuelve el Club retirado, o None si no existía (no lanza
        excepción -- el llamador decide si eso es un problema)."""
        club = self._por_nombre.pop(name, None)
        if club is not None:
            self._por_id.pop(club.id, None)
        return club

    def divisions_summary(self) -> Dict[str, int]:
        """{división: cantidad de clubes} -- para el chequeo de Etapa 0
        contra lo que ya se ve hoy en cada tabla_X.csv."""
        resumen: Dict[str, int] = {}
        for club in self._por_id.values():
            resumen[club.division] = resumen.get(club.division, 0) + 1
        return resumen

    def __len__(self) -> int:
        return len(self._por_id)

    def __repr__(self) -> str:
        resumen = ", ".join(f"{div}={n}" for div, n in self.divisions_summary().items())
        return f"ClubRegistry({len(self)} clubes: {resumen})"
