# -*- coding: utf-8 -*-
"""
season/dt_carrera.py

Núcleo de "Modo Carrera DT" (director técnico). Reemplaza al viejo Modo
Carrera de jugador (sacado del proyecto -- no había base de jugadores
para sostenerlo). Este módulo trabaja a nivel de CLUB, no de jugador,
por eso no necesita ninguna base de datos nueva: reutiliza el mismo
nivel de abstracción que ya usan season/prestigio.py y
season/rating_carryover.py (un club es un puñado de números -- ataque,
defensa, prestigio -- no una lista de nombres).

Tres piezas, cada una independiente y testeable por separado:

1. Núcleo del DT -- reputación, ofertas de clubes según esa reputación,
   objetivo de la dirigencia para la temporada, y evaluación al final
   (¿cumplió? ¿sigue, hay presión, o lo echan?).
2. Mercado simplificado -- en vez de fichar jugadores reales, el DT
   compra "refuerzos" por categoría (arquero/defensa/mediocampo/
   ataque). Cada compra es una tirada de riesgo (flop/promedio/pega)
   que suma o resta puntos al rating del club -- el mismo rating que
   ya alimenta el motor Poisson.
3. Motor de partido -- NO reemplaza al motor Poisson que ya decide
   los resultados de la temporada (season/*.py, modelos/estadisticas_*.py).
   Formación y mentalidad solo ajustan los lambda de ataque/defensa
   ANTES de tirar el resultado (`ajustar_lambdas`); el resultado en sí
   sigue siendo la misma tirada de siempre. Lo "minuto a minuto" es
   una capa de narración que arma una cronología creíble a partir de
   un marcador YA DECIDIDO (`generar_cronologia`) -- no una segunda
   simulación estadística, así que nunca puede desviarse del resultado
   real que alimenta la tabla de posiciones.

Este módulo es puro (sin I/O, sin Supabase, sin Pyodide) a propósito:
las capas de arriba (API endpoints, luego el frontend) le pasan los
datos que necesita (candidatos a club, rating actual, etc.) en vez de
que el módulo los busque él mismo -- mismo criterio de responsabilidad
única que ya sigue el resto de season/.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum

import numpy as np


# ---------------------------------------------------------------------
# 1) Núcleo del DT: reputación, ofertas, objetivos, evaluación
# ---------------------------------------------------------------------

REPUTACION_MINIMA = 0
REPUTACION_MAXIMA = 100

# Umbral de factor_resistencia (season/prestigio.factor_resistencia,
# rango 0..0.5) que un club puede tener como máximo para ofertarle a
# un DT con determinada reputación -- un DT reputación 5 no puede
# arrancar dirigiendo a un "grande" (factor_resistencia alto). El
# propio factor de prestigio ya nos da gratis una escala de "tamaño de
# club" sin inventar una nueva.
_TECHO_PRESTIGIO_POR_REPUTACION = (
    (20, 0.05),
    (45, 0.15),
    (70, 0.30),
    (REPUTACION_MAXIMA, 0.50),
)


@dataclass(frozen=True)
class ClubCandidato:
    """Un club candidato a ofertarle al DT. `factor_prestigio` es
    season.prestigio.factor_resistencia(nombre) -- se le pasa ya
    calculado para no acoplar este módulo a esa consulta."""
    nombre: str
    division_slug: str
    factor_prestigio: float


def techo_prestigio_para(reputacion: int) -> float:
    """Devuelve el factor_prestigio máximo que un club puede tener
    para poder ofertarle a un DT con esta reputación."""
    for umbral_reputacion, techo in _TECHO_PRESTIGIO_POR_REPUTACION:
        if reputacion <= umbral_reputacion:
            return techo
    return _TECHO_PRESTIGIO_POR_REPUTACION[-1][1]


def ofertas_de_clubes(
    reputacion: int,
    candidatos: list[ClubCandidato],
    cantidad: int = 3,
    rng: random.Random | None = None,
) -> list[ClubCandidato]:
    """Elige hasta `cantidad` clubes que le ofertan al DT esta
    temporada, filtrando por `techo_prestigio_para(reputacion)`.

    Si no hay candidatos elegibles devuelve lista vacía (la capa de
    arriba decide qué hacer -- ej. mostrar solo clubes de Primera C
    como red de contención)."""
    rng = rng or random.Random()
    techo = techo_prestigio_para(reputacion)
    elegibles = [c for c in candidatos if c.factor_prestigio <= techo]
    if not elegibles:
        return []
    cantidad = min(cantidad, len(elegibles))
    return rng.sample(elegibles, cantidad)


class TipoObjetivo(str, Enum):
    EVITAR_DESCENSO = "evitar_descenso"
    MITAD_TABLA = "mitad_tabla"
    PLAYOFFS = "playoffs"
    ASCENSO = "ascenso"
    PELEAR_TITULO = "pelear_titulo"


_DESCRIPCION_OBJETIVO = {
    TipoObjetivo.EVITAR_DESCENSO: "Evitar el descenso",
    TipoObjetivo.MITAD_TABLA: "Terminar en la mitad de tabla para arriba",
    TipoObjetivo.PLAYOFFS: "Meterse en zona de playoffs / reducido",
    TipoObjetivo.ASCENSO: "Conseguir el ascenso",
    TipoObjetivo.PELEAR_TITULO: "Pelear el campeonato",
}

# División de corte: por debajo de esto un objetivo de ascenso tiene
# sentido; en LPF no hay ascenso, así que el objetivo más alto ahí es
# pelear el título.
_DIVISIONES_CON_ASCENSO = {"nacional", "bmetro", "federal_a", "primerac"}


def generar_objetivo(club: ClubCandidato, rng: random.Random | None = None) -> TipoObjetivo:
    """El objetivo depende del prestigio del club, no de resultados
    pasados del DT (todavía no dirigió ahí) -- un club chico pide no
    descender, uno grande pide pelear arriba."""
    rng = rng or random.Random()
    factor = club.factor_prestigio
    if factor >= 0.30:
        return TipoObjetivo.PELEAR_TITULO
    if factor >= 0.12:
        return rng.choice([TipoObjetivo.PLAYOFFS, TipoObjetivo.PELEAR_TITULO])
    if club.division_slug in _DIVISIONES_CON_ASCENSO and factor >= 0.03:
        return rng.choice([TipoObjetivo.ASCENSO, TipoObjetivo.PLAYOFFS])
    return rng.choice([TipoObjetivo.EVITAR_DESCENSO, TipoObjetivo.MITAD_TABLA])


def descripcion_objetivo(objetivo: TipoObjetivo) -> str:
    return _DESCRIPCION_OBJETIVO[objetivo]


# Cumplir un objetivo alto (pelear título) da más reputación que uno
# bajo (evitar descenso) -- y fallar uno bajo cuesta más caro que
# fallar uno alto (de un club grande casi nadie espera el título todos
# los años).
_REPUTACION_CUMPLIDO = {
    TipoObjetivo.EVITAR_DESCENSO: 3,
    TipoObjetivo.MITAD_TABLA: 4,
    TipoObjetivo.PLAYOFFS: 6,
    TipoObjetivo.ASCENSO: 10,
    TipoObjetivo.PELEAR_TITULO: 12,
}
_REPUTACION_FALLIDO = {
    TipoObjetivo.EVITAR_DESCENSO: -15,
    TipoObjetivo.MITAD_TABLA: -8,
    TipoObjetivo.PLAYOFFS: -5,
    TipoObjetivo.ASCENSO: -4,
    TipoObjetivo.PELEAR_TITULO: -2,
}
# Fallar el objetivo más de esto de veces seguidas (con el mismo club)
# significa despido -- no hace falta que sea inmediato, un club le da
# margen a un DT que viene de golpes buenos.
UMBRAL_TEMPORADAS_FALLIDAS_PARA_DESPIDO = 2


@dataclass
class EvaluacionTemporada:
    cumplido: bool
    delta_reputacion: int
    despedido: bool


def evaluar_temporada(
    objetivo: TipoObjetivo,
    cumplido: bool,
    temporadas_fallidas_seguidas_previas: int,
) -> EvaluacionTemporada:
    """`temporadas_fallidas_seguidas_previas` es el contador ANTES de
    este resultado -- la capa de arriba es responsable de persistirlo
    en DTState.historial y de resetearlo a 0 cuando `cumplido=True`."""
    if cumplido:
        return EvaluacionTemporada(cumplido=True, delta_reputacion=_REPUTACION_CUMPLIDO[objetivo], despedido=False)

    fallidas_totales = temporadas_fallidas_seguidas_previas + 1
    despedido = fallidas_totales >= UMBRAL_TEMPORADAS_FALLIDAS_PARA_DESPIDO
    return EvaluacionTemporada(
        cumplido=False,
        delta_reputacion=_REPUTACION_FALLIDO[objetivo],
        despedido=despedido,
    )


@dataclass
class TemporadaResumen:
    numero: int
    club: str
    objetivo: TipoObjetivo
    cumplido: bool
    despedido: bool


@dataclass
class DTState:
    """Estado del DT a través de las temporadas. Vive en memoria en el
    frontend/API (mismo patrón que el `estado_anterior`/`proximo_estado`
    de Modo Temporada local) -- no se persiste en Supabase."""
    reputacion: int = 10
    club_actual: str | None = None
    numero_temporada: int = 0
    temporadas_fallidas_seguidas: int = 0
    historial: list[TemporadaResumen] = field(default_factory=list)

    def aplicar_resultado(self, club: str, objetivo: TipoObjetivo, cumplido: bool) -> EvaluacionTemporada:
        evaluacion = evaluar_temporada(objetivo, cumplido, self.temporadas_fallidas_seguidas)
        self.reputacion = min(REPUTACION_MAXIMA, max(REPUTACION_MINIMA, self.reputacion + evaluacion.delta_reputacion))
        self.temporadas_fallidas_seguidas = 0 if cumplido else self.temporadas_fallidas_seguidas + 1
        self.numero_temporada += 1
        self.historial.append(TemporadaResumen(
            numero=self.numero_temporada,
            club=club,
            objetivo=objetivo,
            cumplido=cumplido,
            despedido=evaluacion.despedido,
        ))
        if evaluacion.despedido:
            self.club_actual = None
        return evaluacion


# ---------------------------------------------------------------------
# 2) Mercado simplificado: fichajes por categoría, sin jugadores reales
# ---------------------------------------------------------------------

class CategoriaFichaje(str, Enum):
    ARQUERO = "arquero"
    DEFENSA = "defensa"
    MEDIOCAMPO = "mediocampo"
    ATAQUE = "ataque"


class ResultadoFichaje(str, Enum):
    FLOP = "flop"
    PROMEDIO = "promedio"
    PEGO = "pego"


# (probabilidad, delta_rating, texto) -- delta_rating es el ajuste que
# recibe el componente de rating correspondiente a la categoría (ver
# CATEGORIA_A_CAMPO_RATING más abajo). Probabilidades suman 1.0.
_TIRADAS_FICHAJE: tuple[tuple[float, float, ResultadoFichaje, str], ...] = (
    (0.20, -0.03, ResultadoFichaje.FLOP, "No rindió, quedó relegado del equipo"),
    (0.55, 0.02, ResultadoFichaje.PROMEDIO, "Cumplió sin destacarse"),
    (0.25, 0.06, ResultadoFichaje.PEGO, "Se ganó un lugar titular de entrada"),
)

# Mapea cada categoría de fichaje al campo de rating que ajusta -- los
# mismos 4 campos que ya usa aplicar_piso_prestigio (CAMPOS_RATING en
# season/prestigio.py), así que el delta se puede sumar directo sobre
# el rating real del club sin traducir nada.
CATEGORIA_A_CAMPO_RATING = {
    CategoriaFichaje.ARQUERO: "defensa_local",
    CategoriaFichaje.DEFENSA: "defensa_visitante",
    CategoriaFichaje.MEDIOCAMPO: "ataque_local",
    CategoriaFichaje.ATAQUE: "ataque_visitante",
}

COSTO_FICHAJE = 25  # en "puntos de plantel" del presupuesto abstracto de pretemporada


@dataclass(frozen=True)
class Fichaje:
    categoria: CategoriaFichaje
    resultado: ResultadoFichaje
    delta_rating: float
    texto: str


def fichar(categoria: CategoriaFichaje, rng: random.Random | None = None) -> Fichaje:
    """Una tirada de mercado para la categoría dada. No cobra el
    presupuesto -- la capa de arriba resta COSTO_FICHAJE y decide si
    hay plata para llamar a esta función."""
    rng = rng or random.Random()
    r = rng.random()
    acumulado = 0.0
    for probabilidad, delta, resultado, texto in _TIRADAS_FICHAJE:
        acumulado += probabilidad
        if r <= acumulado:
            return Fichaje(categoria=categoria, resultado=resultado, delta_rating=delta, texto=texto)
    # Por redondeo de floats podría no entrar en ningún tramo -- cae
    # en el último definido en vez de reventar.
    probabilidad, delta, resultado, texto = _TIRADAS_FICHAJE[-1]
    return Fichaje(categoria=categoria, resultado=resultado, delta_rating=delta, texto=texto)


# ---------------------------------------------------------------------
# 3) Motor de partido: ajuste de lambdas + narrador de cronología
# ---------------------------------------------------------------------

class Formacion(str, Enum):
    OFENSIVA = "4-3-3"
    EQUILIBRADA = "4-4-2"
    DEFENSIVA = "5-3-2"


class Mentalidad(str, Enum):
    OFENSIVA = "ofensiva"
    EQUILIBRADA = "equilibrada"
    DEFENSIVA = "defensiva"


# (multiplicador de ataque propio, multiplicador de defensa propia --
# >1.0 es PEOR defensa, misma convención que season/prestigio.py).
_MODIFICADOR_FORMACION = {
    Formacion.OFENSIVA: (1.15, 1.10),
    Formacion.EQUILIBRADA: (1.00, 1.00),
    Formacion.DEFENSIVA: (0.85, 0.90),
}
_MODIFICADOR_MENTALIDAD = {
    Mentalidad.OFENSIVA: (1.10, 1.08),
    Mentalidad.EQUILIBRADA: (1.00, 1.00),
    Mentalidad.DEFENSIVA: (0.90, 0.85),
}


def ajustar_lambdas(
    lambda_local: float,
    lambda_visitante: float,
    formacion: Formacion,
    mentalidad: Mentalidad,
) -> tuple[float, float]:
    """Ajusta los goles esperados ANTES de que el motor Poisson tire
    el resultado -- formación y mentalidad son del equipo LOCAL (el
    del DT). `lambda_local` sube con el multiplicador de ataque;
    `lambda_visitante` (lo que le mete el rival) sube con el
    multiplicador de defensa, porque una defensa peor te hace conceder
    más goles al rival, no menos goles propios."""
    mult_ataque_f, mult_defensa_f = _MODIFICADOR_FORMACION[formacion]
    mult_ataque_m, mult_defensa_m = _MODIFICADOR_MENTALIDAD[mentalidad]
    nuevo_local = lambda_local * mult_ataque_f * mult_ataque_m
    nuevo_visitante = lambda_visitante * mult_defensa_f * mult_defensa_m
    return round(nuevo_local, 4), round(nuevo_visitante, 4)



# ---------------------------------------------------------------------
# 0) Rating de un club a partir de su prestigio (sin base de jugadores
#    NI enganche al motor Poisson en vivo de cada división -- ver nota
#    de diseño en el docstring de rating_por_prestigio).
# ---------------------------------------------------------------------

PROMEDIO_GF_LIGA_DT = 1.35  # gol promedio de referencia (genérico, no por división)


def rating_por_prestigio(factor_prestigio: float) -> dict[str, float]:
    """Aproxima el rating de un club (los mismos 4 campos que usa
    Estadisticas.simular_partido: ataque_local/visitante,
    defensa_local/visitante) a partir de SOLO su factor_prestigio
    (season.prestigio.factor_resistencia, rango 0..0.5).

    DECISIÓN DE DISEÑO: no engancha con el rating Poisson EN VIVO de
    cada división (ese vive adentro de cada Estadisticas*/motor
    mientras corre una simulación completa, no es un atributo
    portable -- Club.rating en modelos/club.py está reservado y sin
    usar, ver su docstring). Enganchar ahí habría acoplado Modo
    Carrera DT a que exista una temporada real corriendo en la
    división del club elegido, y complicado mucho este módulo para
    una mejora que el usuario no pidió. El prestigio histórico ya es
    una escala razonable de "qué tan fuerte es este plantel" y este
    módulo la estira a los 4 números que necesita el resto del motor.

    factor 0.0 (club sin historial) -> rating base 1.0 en las 4 patas.
    factor 0.5 (máximo, ver RESISTENCIA_MAXIMA) -> ataque ~1.4,
    defensa ~0.7 (mejor -- convención ya establecida: defensa < 1.0 es
    buena)."""
    factor = max(0.0, min(0.5, factor_prestigio))
    ataque = round(1.0 + factor * 0.8, 4)
    defensa = round(1.0 - factor * 0.6, 4)
    return {
        "ataque_local": ataque,
        "ataque_visitante": ataque,
        "defensa_local": defensa,
        "defensa_visitante": defensa,
    }


def candidatos_desde_registry(club_registry, divisiones: tuple[str, ...] | None = None) -> list[ClubCandidato]:
    """Arma la lista de ClubCandidato a partir de un ClubRegistry ya
    construido (típicamente vía ClubRegistry.build_from_current_data(),
    igual que Modo Temporada) -- import local para no crear un ciclo
    (season/club_registry.py y season/prestigio.py no dependen de este
    módulo, pero se importan acá adentro para que dt_carrera.py siga
    siendo usable sin esas dos piezas si algún test solo necesita el
    resto)."""
    from season.club_registry import DIVISIONES
    from season.prestigio import factor_resistencia

    divisiones = divisiones or tuple(DIVISIONES.keys())
    candidatos = []
    for slug in divisiones:
        for club in club_registry.get_by_division(DIVISIONES[slug]):
            candidatos.append(ClubCandidato(
                nombre=club.name,
                division_slug=slug,
                factor_prestigio=factor_resistencia(club.name),
            ))
    return candidatos


def lambda_partido(
    rating_local: dict[str, float],
    rating_visitante: dict[str, float],
    promedio_liga: float = PROMEDIO_GF_LIGA_DT,
) -> tuple[float, float]:
    """Misma fórmula que Estadisticas.simular_partido (modelos/estadisticas.py,
    línea ~254): lambda = ataque propio * defensa rival * promedio de
    liga. Reimplementada acá (no importada) para que dt_carrera.py siga
    sin depender de pandas/CSV -- este módulo solo necesita los 4
    números de rating de cada lado."""
    lambda_local = rating_local["ataque_local"] * rating_visitante["defensa_visitante"] * promedio_liga
    lambda_visitante = rating_visitante["ataque_visitante"] * rating_local["defensa_local"] * promedio_liga
    return round(lambda_local, 4), round(lambda_visitante, 4)


def resolver_partido(lambda_local: float, lambda_visitante: float, rng: np.random.Generator | None = None) -> tuple[int, int]:
    """Sortea el marcador final -- Poisson independiente por lado,
    igual de simple que jugar_final_ascenso en modelos/estadisticas.py
    (no hace falta la corrección Dixon-Coles de baja anotación acá:
    esa corrección importa para el ranking fino de una liga completa
    de 30 equipos, no para un partido individual de Modo Carrera DT)."""
    rng = rng or np.random.default_rng()
    goles_local = int(rng.poisson(lambda_local))
    goles_visitante = int(rng.poisson(lambda_visitante))
    return goles_local, goles_visitante


@dataclass(frozen=True)
class EventoPartido:
    minuto: int
    equipo: str  # "local" | "visitante"
    gol: bool
    texto: str
    marcador_local: int
    marcador_visitante: int


@dataclass(frozen=True)
class ResultadoPartidoDT:
    goles_local: int
    goles_visitante: int
    lambda_local: float
    lambda_visitante: float
    eventos: list[EventoPartido]


def jugar_partido_dt(
    rating_dt: dict[str, float],
    rating_rival: dict[str, float],
    formacion: Formacion,
    mentalidad: Mentalidad,
    rng_poisson: np.random.Generator | None = None,
    rng_narracion: random.Random | None = None,
) -> ResultadoPartidoDT:
    """Punto de entrada único para "jugar" un partido de Modo Carrera
    DT -- encadena las 3 piezas de la sección 3 del módulo: calcula los
    lambda base, los ajusta por formación/mentalidad, sortea el
    marcador, y arma la cronología. El DT del usuario siempre juega de
    local acá (simplificación deliberada -- el rol de local/visitante
    real de cada fecha no cambia el mecanismo, solo qué lado se le
    muestra al usuario como "vos")."""
    lambda_local_base, lambda_visitante_base = lambda_partido(rating_dt, rating_rival)
    lambda_local, lambda_visitante = ajustar_lambdas(lambda_local_base, lambda_visitante_base, formacion, mentalidad)
    goles_local, goles_visitante = resolver_partido(lambda_local, lambda_visitante, rng=rng_poisson)
    eventos = generar_cronologia(goles_local, goles_visitante, lambda_local, lambda_visitante, rng=rng_narracion)
    return ResultadoPartidoDT(
        goles_local=goles_local,
        goles_visitante=goles_visitante,
        lambda_local=lambda_local,
        lambda_visitante=lambda_visitante,
        eventos=eventos,
    )


# ---------------------------------------------------------------------
# 4) Evaluación de objetivo a partir de puntos acumulados
# ---------------------------------------------------------------------

# Porcentaje mínimo de los puntos posibles (partidos_jugados * 3) que
# hay que sacar para dar el objetivo por cumplido -- más exigente
# cuanto más alto el objetivo.
_PORCENTAJE_PUNTOS_MINIMO = {
    TipoObjetivo.EVITAR_DESCENSO: 0.30,
    TipoObjetivo.MITAD_TABLA: 0.42,
    TipoObjetivo.PLAYOFFS: 0.50,
    TipoObjetivo.ASCENSO: 0.55,
    TipoObjetivo.PELEAR_TITULO: 0.62,
}


def objetivo_cumplido(objetivo: TipoObjetivo, puntos: int, partidos_jugados: int) -> bool:
    """Sencillo a propósito: no arma una tabla de posiciones completa
    con los demás equipos (eso ya lo hace Modo Temporada) -- alcanza
    con comparar el propio rendimiento contra un umbral fijo, que es
    lo único que le importa a la dirigencia para juzgar al DT."""
    if partidos_jugados <= 0:
        return False
    return (puntos / (partidos_jugados * 3)) >= _PORCENTAJE_PUNTOS_MINIMO[objetivo]
    minuto: int
    equipo: str  # "local" | "visitante"
    gol: bool
    texto: str
    marcador_local: int
    marcador_visitante: int


_TEXTOS_GOL = (
    "remata cruzado y no hay nada que hacer -- ¡gol!",
    "cabezazo tras el córner que se clava en el ángulo -- ¡gol!",
    "contragolpe letal, definición al primer palo -- ¡gol!",
    "la pelota pega en el travesaño y entra -- ¡gol!",
)
_TEXTOS_FALLO = (
    "remate que se va apenas desviado",
    "el arquero rival responde con una gran tapada",
    "cabezazo que se pierde por arriba del travesaño",
    "la defensa rival despeja sobre la línea",
    "tiro libre que pega en la barrera",
)


def _n_ocasiones(lam: float, goles: int) -> int:
    """Cuántas ocasiones (goles + fallos) generar para un equipo dado
    su lambda -- siempre al menos `goles`, y algo más para que el
    partido no se sienta como puro gol tras gol."""
    return max(goles, round(lam * 3.5)) + 1


def generar_cronologia(
    goles_local: int,
    goles_visitante: int,
    lambda_local: float,
    lambda_visitante: float,
    rng: random.Random | None = None,
) -> list[EventoPartido]:
    """Arma una cronología de 90 minutos que llega EXACTO al marcador
    ya decidido por el motor Poisson (goles_local/goles_visitante no
    se recalculan acá, son un dato de entrada fijo). Ver el docstring
    del módulo, punto 3.

    Invariantes garantizados:
      - todos los eventos con gol=True de un equipo suman exactamente
        sus goles finales;
      - los minutos están estrictamente ordenados de forma no
        decreciente y en el rango [1, 90];
      - el marcador acumulado de cada evento coincide con el conteo de
        goles reales hasta ese minuto.
    """
    rng = rng or random.Random()

    eventos_crudos: list[tuple[str, bool]] = []
    for equipo, goles, lam in (("local", goles_local, lambda_local), ("visitante", goles_visitante, lambda_visitante)):
        n = _n_ocasiones(lam, goles)
        fallos = n - goles
        eventos_crudos += [(equipo, True)] * goles
        eventos_crudos += [(equipo, False)] * fallos

    minutos_usados: set[int] = set()
    con_minuto: list[tuple[int, str, bool]] = []
    for equipo, es_gol in eventos_crudos:
        minuto = rng.randint(1, 90)
        while minuto in minutos_usados:
            minuto = rng.randint(1, 90)
        minutos_usados.add(minuto)
        con_minuto.append((minuto, equipo, es_gol))
    con_minuto.sort(key=lambda e: e[0])

    eventos: list[EventoPartido] = []
    marcador_local = 0
    marcador_visitante = 0
    for minuto, equipo, es_gol in con_minuto:
        if es_gol:
            if equipo == "local":
                marcador_local += 1
            else:
                marcador_visitante += 1
            texto = rng.choice(_TEXTOS_GOL)
        else:
            texto = rng.choice(_TEXTOS_FALLO)
        eventos.append(EventoPartido(
            minuto=minuto,
            equipo=equipo,
            gol=es_gol,
            texto=texto,
            marcador_local=marcador_local,
            marcador_visitante=marcador_visitante,
        ))
    return eventos
