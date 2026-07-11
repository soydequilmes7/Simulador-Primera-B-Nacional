# -*- coding: utf-8 -*-
"""
season/rating_carryover.py

Etapa 3 del plan (ver PLAN_MODO_TEMPORADA_NACIONAL.txt, sección 5 y 6):
RatingCarryoverPolicy resuelve el "agujero" que hoy existe en
modelos/estadisticas.py -- calcular_ratings() solo calcula ataque/
defensa a partir de self.resultados (partidos jugados EN ESA
división). Si un club tiene cero partidos ahí (exactamente el caso de
un recién ascendido o descendido), el bloque `if len(partidos_local) > 0:`
se salta entero y el club queda con lo que Equipo.__init__ ponga por
default -- no hay ningún carryover real entre divisiones hoy.

Esta política generaliza el patrón que YA existe en
modelos/estadisticas_copa.py (_cosechar_ratings_ligas()): a los clubes
de Copa sin historial en ninguna liga cargada se les asigna un rating
genérico fijo (ATAQUE_ASCENSO=0.70, DEFENSA_ASCENSO=1.35). Acá se
generaliza ese mismo criterio a CUALQUIER cambio de división, agregando
además un ajuste por diferencia de nivel entre divisiones quIe Copa no
hace (_cosechar_ratings_ligas() copia el rating tal cual, sin ese
ajuste -- es un precedente real, pero una simplificación).

--------------------------------------------------------------------
LA FÓRMULA
--------------------------------------------------------------------
Tratamos el rating heredado de la otra división como si fuera otra
fuente de evidencia más, con su propio peso "en partidos virtuales",
en la misma familia de fórmulas de regresión-a-la-media que ya usa
modelos/estadisticas.py (K_REGRESION=12 ahí):

    rating_destino = (n_carry * rating_ajustado + K_REGRESION * 1.0)
                      / (n_carry + K_REGRESION)

donde `rating_ajustado` corrige primero por la diferencia de NIVEL
entre la división de origen y la de destino:

    rating_ajustado = 1.0 + (rating_origen - 1.0) * (NIVEL_DIVISION[origen] / NIVEL_DIVISION[destino])

Interpretación: `rating_origen - 1.0` es "cuánto se aparta del
promedio de SU propia liga". Si el club viene de una división más
débil que la de destino, esa distancia se COMPRIME hacia el promedio
(ser goleador en Primera C no te vuelve automáticamente goleador en
LPF). Si viene de una división más fuerte, se AMPLIFICA (ser un
equipo del montón en LPF probablemente te hace bastante mejor que el
promedio del Federal A).

Para un recién llegado sin ningún historial en ninguna división
(n_local=0 en TODAS partes, no solo en la de destino), no hay
`rating_origen` de dónde partir -- se usa directamente el rating
genérico (mismo valor que ya usa Copa: ATAQUE_ASCENSO/DEFENSA_ASCENSO
de estadisticas_copa.py, renombrados acá ATAQUE_GENERICO/
DEFENSA_GENERICO por prolijidad, mismo número).

--------------------------------------------------------------------
NIVEL_DIVISION -- ADVERTENCIA IMPORTANTE
--------------------------------------------------------------------
Estos valores son una ESTIMACIÓN MANUAL de arranque, documentada como
tal a propósito -- NO están calibrados con datos reales todavía.

La única fuente de señal cruzada entre divisiones que existe hoy en
el proyecto es la Copa Argentina (ahí sí juegan entre sí clubes de
distintas divisiones, con goles reales). Calibrar NIVEL_DIVISION con
una regresión sobre cruces históricos de Copa Argentina requeriría
resultados de VARIAS ediciones pasadas -- el proyecto hoy solo tiene
el cuadro de la edición vigente (copa_argentina.csv), no un historial
multi-temporada. Se decidió (con el usuario, ver conversación de
Etapa 3) sembrar los valores a mano mientras tanto y dejar el punto de
calibración desacoplado, para poder reemplazar estos números por unos
calculados empíricamente el día que haya datos, SIN tener que tocar
la interfaz de RatingCarryoverPolicy.

Jerarquía usada (LPF = referencia = 1.00, resto por debajo, orden de
fuerza según el fútbol argentino real):
    LPF        -> 1.00 (máxima categoría)
    Nacional   -> 0.85
    Federal A  -> 0.65 (mismo nivel que B Metro, tercera división)
    B Metro    -> 0.65
    Primera C  -> 0.55 (categoría más baja de las 5 simuladas)

Ajustar estos números es tan simple como editar el diccionario -- no
requiere cambios en la fórmula ni en RatingCarryoverPolicy.

--------------------------------------------------------------------
N_CARRYOVER
--------------------------------------------------------------------
Parámetro nuevo (no existía en modelos/estadisticas.py): cuántos
"partidos virtuales" de confianza le damos al dato heredado antes de
que la nueva división empiece a pesar más. Con N_CARRYOVER bajo, el
club arranca casi en el promedio de la liga nueva; con N_CARRYOVER
alto, arranca casi igual que terminó en la liga vieja.

Se fija en el mismo valor que K_REGRESION (12) como punto de partida
razonable: un 50/50 entre "lo que el club ya demostró" (ajustado por
nivel) y "el promedio de la liga nueva" cuando el club recién llega y
no acumuló NINGÚN partido todavía en destino. Es, igual que
NIVEL_DIVISION, un valor de arranque documentado y ajustable, no una
constante derivada matemáticamente de otro lado.

--------------------------------------------------------------------
ALCANCE DE ESTA ETAPA (Etapa 3 del plan)
--------------------------------------------------------------------
Esta política se prueba con datos MOCKEADOS (ver
season/validar_etapa3.py) -- sin tocar ClubRegistry real todavía.
RatingCarryoverPolicy.rating_para_recien_llegado() recibe los ratings
YA CALCULADOS de un club (un dict con las 4 claves de CAMPOS_RATING),
no arrays crudos de partidos -- por diseño: los objetos Equipo de
modelos/equipo.py solo guardan el rating final ya regresionado, no el
tamaño de muestra que lo originó, así que no hay forma de "reabrir" la
regresión original desde acá. Tratar el carryover con un N_CARRYOVER
fijo de nivel de clase (en vez de uno por club derivado de partidos
jugados) es la simplificación consciente que corresponde a este
alcance.

--------------------------------------------------------------------
FASE 0 -- MEMORIA MULTI-TEMPORADA + HANDICAP DE ADAPTACIÓN
(ver HANDOFF_carryover_ratings.md)
--------------------------------------------------------------------
Motivo: con solo la fórmula de arriba, un club recién ascendido/
descendido arranca su primera temporada en destino ya "curado" (mezcla
50/50 con el rating de origen ajustado por nivel), pero de ahí en
adelante queda 100% a merced del rating de UNA sola temporada real
(ratings_desde_tabla_anual() / equivalentes) -- eso permite que un
campeón chico quede con un rating inflado por una racha corta, o que
un grande golpeado por una mala temporada quede subvaluado, sin ningún
amortiguador. Se agregan acá dos mecanismos, ambos alimentados por
Club.history (ver modelos/club.py y HistoryManager._actualizar_history,
que ahora guarda una clave "ratings" además de "temporada"/"division"):

  1. Memoria EWMA (memoria_ewma() / combinar_con_memoria()): para
     clubes que YA vienen jugando en una división (no pasan por
     rating_para_recien_llegado()), el rating de la temporada que
     recién terminó se mezcla con un promedio móvil exponencial de
     las temporadas anteriores EN ESA MISMA división -- no se mezcla
     memoria de otra división distinta si el club cambió de categoría.

  2. Handicap de adaptación (_factor_handicap()): un club recién
     llegado a una división arranca con su distancia al promedio de
     liga (1.0) comprimida más de lo que ya hace el ajuste por
     NIVEL_DIVISION, y esa compresión extra se disuelve en
     N_TEMPORADAS_HANDICAP temporadas. Se aplica tanto en
     rating_para_recien_llegado() (temporada 1 en destino, factor fijo
     porque por definición esa función solo se llama en la llegada)
     como en combinar_con_memoria() (temporadas 2..N para el mismo
     club, vía temporadas_consecutivas_en_division()).

Deliberadamente NO se hardcodea ninguna lista de equipos "históricos":
el amortiguador sale entero de Club.history (cuántas temporadas lleva
cada club en su división actual, y qué ratings tuvo), nunca del nombre
del club.
"""
from __future__ import annotations

from modelos.club import Club
from season.club_registry import DIVISIONES
from season.prestigio import aplicar_piso_prestigio

# --------------------------------------------------------------
# Nivel relativo de cada división (ver docstring del módulo).
# LPF = referencia = 1.00. ESTIMACIÓN MANUAL, no calibrada.
# --------------------------------------------------------------
NIVEL_DIVISION = {
    "lpf": 1.00,
    "nacional": 0.85,
    "federal_a": 0.65,
    "bmetro": 0.65,
    "primerac": 0.55,
}

# Peso (en "partidos virtuales") que se le da al rating heredado de
# otra división frente a la regresión al promedio de la liga nueva --
# para un ASCENSO. Deliberadamente CONSERVADOR (peso bajo, mucha
# regresión al promedio): no hay certeza de que un club recién
# ascendido pueda sostener su nivel contra rivales más exigentes.
N_CARRYOVER = 12

# BUG DE CALIBRACIÓN ENCONTRADO Y CORREGIDO -- reportado por el
# usuario (Riestra, Banfield, San Lorenzo -- un club DISTINTO cada
# vez, lo que confirmó que no era un bug puntual de un club sino un
# problema sistémico de calibración): incluso después de sacarle el
# handicap a los descensos, el rating final seguía quedando MUY por
# debajo de lo que un club realmente fuerte de LPF debería mantener
# al bajar a Nacional -- ej. un candidato a puntero de LPF
# (ataque_local~1.35) quedaba en apenas 1.206 en Nacional, cuando
# debería dominar la categoría casi de entrada (en el fútbol
# argentino real, los recién descendidos de Primera suelen pelear
# arriba enseguida).
#
# La causa: N_CARRYOVER=12 trata el rating heredado como si solo
# tuviera el peso de 12 partidos de evidencia -- razonable para un
# ASCENSO (incertidumbre real de si aguanta el nivel), pero
# demasiado poco para un DESCENSO, donde no hay ninguna duda de que
# la calidad del plantel se mantiene (el club sigue siendo el mismo,
# juega contra rivales más débiles). Un descenso necesita CONFIAR
# mucho más en el rating heredado, no tratarlo como un dato dudoso.
#
# N_CARRYOVER_DESCENSO -- valor de arranque razonable, documentado,
# NO calibrado con datos reales todavía (mismo criterio que
# NIVEL_DIVISION/ALPHA_MEMORIA): bastante más alto que N_CARRYOVER,
# para que el rating amplificado por NIVEL_DIVISION se sostenga en
# vez de diluirse casi a la mitad contra el promedio genérico.
N_CARRYOVER_DESCENSO = 40

# Mismo peso de regresión a la media que usa modelos/estadisticas.py
# para equipos con pocos partidos (K_REGRESION=12 ahí). Se repite acá
# como constante propia del módulo para no depender de un import
# cruzado hacia modelos/estadisticas.py por un solo número.
K_REGRESION = 12

# Rating genérico para un club sin historial en NINGUNA división.
# Mismo valor que ATAQUE_ASCENSO/DEFENSA_ASCENSO de
# modelos/estadisticas_copa.py (_cosechar_ratings_ligas()) -- se
# reutiliza el precedente ya validado en producción para Copa.
ATAQUE_GENERICO = 0.70
DEFENSA_GENERICO = 1.35

# Claves que debe tener cualquier dict de ratings de un club, en el
# mismo orden/nombre que usa modelos/equipo.py.
CAMPOS_RATING = (
    "ataque_local",
    "ataque_visitante",
    "defensa_local",
    "defensa_visitante",
)

# --------------------------------------------------------------
# Fase 0 (ver docstring del módulo): memoria multi-temporada +
# handicap de adaptación. Valores de arranque documentados, mismo
# criterio que NIVEL_DIVISION/N_CARRYOVER: no calibrados con datos
# reales todavía, pensados para poder ajustarse sin tocar la forma
# de las funciones.
# --------------------------------------------------------------

# Peso de la temporada que acaba de terminar frente a la memoria EWMA
# acumulada de temporadas anteriores EN LA MISMA división (solo para
# clubes que continúan -- ver combinar_con_memoria()). 0.65 = 65%
# temporada actual / 35% memoria previa.
ALPHA_MEMORIA = 0.65

# Cuántas temporadas completas le toma a un recién ASCENDIDO dejar de
# tener handicap de adaptación aplicado. Se disuelve linealmente:
# temporada 1 en destino -> factor 1/3, temporada 2 -> 2/3, temporada 3
# en adelante -> 1.0 (sin handicap).
N_TEMPORADAS_HANDICAP = 2

# BUG ENCONTRADO Y CORREGIDO -- reportado por el usuario: "el equipo
# que desciende se le hace muy difícil volver a pelear... en el
# fútbol argentino real esto no pasa, los que descienden de Primera
# suelen tener mejor plantel/presupuesto que los que ya están arriba
# en la categoría de abajo, y suelen pelear el ascenso casi enseguida".
#
# La causa: el factor de NIVEL_DIVISION YA amplifica correctamente la
# distancia al promedio para un club que desciende (viene de una
# división más fuerte -> factor > 1, ver rating_para_recien_llegado()
# más abajo) -- pero el handicap de adaptación se multiplicaba SIEMPRE
# encima de eso, sin importar la dirección, aplastando esa
# amplificación de vuelta hacia 1.0 exactamente igual que a un club
# CHICO recién ascendido. Un club que baja de categoría no necesita
# "adaptarse" al mismo ritmo que uno que sube -- su plantel sigue
# siendo el mismo, juega contra rivales más débiles. Por eso el
# handicap de ADAPTACIÓN (pensado para "¿puede competir a este nivel
# más exigente?") no tiene sentido aplicado a un descenso.
#
# Fix: el handicap de ascenso (arriba) sigue igual para cuando el
# club sube de nivel. Para cuando BAJA de nivel, no se aplica ningún
# handicap -- se confía de entrada en el rating amplificado por
# NIVEL_DIVISION. Ver _es_ascenso() más abajo.
def _es_ascenso(division_origen: str, division_destino: str) -> bool:
    """True si mover de division_origen a division_destino es subir de
    nivel (NIVEL_DIVISION más alto en destino) -- el único caso que
    amerita el handicap de adaptación. False para descenso O para un
    movimiento lateral (mismo NIVEL_DIVISION, ej. bmetro<->federal_a
    si algún día se diera -- un lateral tampoco necesita adaptarse a
    "más exigencia", así que se trata igual que un descenso: sin
    handicap)."""
    return NIVEL_DIVISION[division_destino] > NIVEL_DIVISION[division_origen]


def _factor_handicap(temporadas_consecutivas: int) -> float:
    """temporadas_consecutivas: cuántas temporadas COMPLETAS ya jugó
    el club en la división de destino antes de la que está por
    arrancar (0 = está por jugar su primera temporada ahí -- el caso
    de rating_para_recien_llegado()). Devuelve un factor en (0, 1]
    que se multiplica sobre la distancia al promedio de liga (1.0);
    1.0 significa "sin handicap, confiar 100% en el rating". Este
    handicap es SOLO para ascensos -- ver _es_ascenso() y el docstring
    de arriba sobre por qué un descenso no lo necesita."""
    return min(1.0, (temporadas_consecutivas + 1) / (N_TEMPORADAS_HANDICAP + 1))


class RatingCarryoverPolicy:
    """Calcula el rating de arranque de un club que cambia de
    división (ascenso o descenso), o que no tiene historial en
    ninguna división todavía.

    Ver el docstring de este módulo para la fórmula completa y las
    advertencias sobre NIVEL_DIVISION / N_CARRYOVER.
    """

    def rating_para_recien_llegado(
        self,
        ratings_origen: dict | None,
        division_origen: str | None,
        division_destino: str,
        club_nombre: str | None = None,
    ) -> dict:
        """
        ratings_origen: dict con las 4 claves de CAMPOS_RATING, los
            ratings ya calculados del club en su división de origen.
            None si el club no tiene historial en NINGUNA división
            (recién llegado al sistema).
        division_origen: clave de NIVEL_DIVISION correspondiente a la
            división donde el club jugó antes. Se ignora (puede ser
            None) si ratings_origen es None.
        division_destino: clave de NIVEL_DIVISION correspondiente a la
            división a la que el club se incorpora ahora.
        club_nombre: opcional (default None = sin piso de prestigio,
            comportamiento idéntico al de antes de este parámetro --
            no rompe ninguna llamada existente). Si se pasa, aplica
            aplicar_piso_prestigio() (season/prestigio.py) al final --
            un club con historial de títulos que desciende no pierde
            tanto terreno en la caída como uno sin ese historial.

        Devuelve un dict con las 4 claves de CAMPOS_RATING.

        Lanza ValueError si division_destino no es una división
        válida, si division_origen no es válida (cuando corresponde
        chequearla), o si a ratings_origen le faltan claves.

        Fase 0 (ver docstring del módulo): además del ajuste por
        NIVEL_DIVISION, se aplica el handicap de adaptación de la
        temporada 1 en destino (_factor_handicap(0), fijo -- esta
        función por diseño solo se llama en el momento de la
        llegada; las temporadas siguientes de handicap las aplica
        combinar_con_memoria() para clubes que ya vienen jugando en
        destino) -- SOLO cuando es un ASCENSO (ver _es_ascenso()). Un
        descenso confía de entrada en el rating ya amplificado por
        NIVEL_DIVISION, sin handicap adicional (ver el bloque de
        comentarios sobre N_TEMPORADAS_HANDICAP más arriba en el
        módulo: reportado por el usuario, un club que baja de
        categoría no necesita "adaptarse", su plantel sigue siendo el
        mismo).
        """
        if division_destino not in NIVEL_DIVISION:
            raise ValueError(
                f"división de destino inválida: {division_destino!r} "
                f"(válidas: {sorted(NIVEL_DIVISION)})"
            )

        # Sin historial en ninguna división -> rating genérico fijo,
        # mismo criterio que _cosechar_ratings_ligas() de la Copa.
        # (El piso de prestigio no se aplica acá: un club sin
        # ratings_origen tampoco tiene forma de estar "rindiendo mal",
        # está en el genérico neutro -- no hay nada que amortiguar.)
        if ratings_origen is None:
            return {
                "ataque_local": ATAQUE_GENERICO,
                "ataque_visitante": ATAQUE_GENERICO,
                "defensa_local": DEFENSA_GENERICO,
                "defensa_visitante": DEFENSA_GENERICO,
            }

        if division_origen not in NIVEL_DIVISION:
            raise ValueError(
                f"división de origen inválida: {division_origen!r} "
                f"(válidas: {sorted(NIVEL_DIVISION)})"
            )

        faltantes = [c for c in CAMPOS_RATING if c not in ratings_origen]
        if faltantes:
            raise ValueError(
                f"ratings_origen no tiene todas las claves esperadas, "
                f"faltan: {faltantes}"
            )

        factor = NIVEL_DIVISION[division_origen] / NIVEL_DIVISION[division_destino]
        es_ascenso = _es_ascenso(division_origen, division_destino)
        # Handicap de adaptación, SOLO si es ascenso (ver _es_ascenso()
        # y el docstring de la sección de arriba -- un descenso no
        # necesita "adaptarse a más exigencia", así que no se le
        # aplasta la amplificación que ya le dio el factor de arriba).
        if es_ascenso:
            factor *= _factor_handicap(0)

        # N_CARRYOVER_DESCENSO en vez de N_CARRYOVER para un descenso
        # (ver su docstring más arriba -- bug de calibración
        # encontrado por el usuario): confiar mucho más en el rating
        # heredado, no diluirlo casi a la mitad contra el promedio.
        n_carryover = N_CARRYOVER if es_ascenso else N_CARRYOVER_DESCENSO

        resultado = {}
        for campo in CAMPOS_RATING:
            valor_origen = ratings_origen[campo]
            valor_ajustado = 1.0 + (valor_origen - 1.0) * factor
            resultado[campo] = round(
                (n_carryover * valor_ajustado + K_REGRESION * 1.0)
                / (n_carryover + K_REGRESION),
                3,
            )
        if club_nombre is not None:
            resultado = aplicar_piso_prestigio(resultado, club_nombre)
        return resultado


# --------------------------------------------------------------------
# Fase 0 -- funciones a nivel de módulo (no de la política, no hace
# falta estado propio) que leen Club.history. Ver docstring del
# módulo para el porqué y HANDOFF_carryover_ratings.md para el plan
# completo.
# --------------------------------------------------------------------

def temporadas_consecutivas_en_division(club: Club, division_slug: str) -> int | None:
    """Cuenta cuántas entradas CONSECUTIVAS al final de club.history
    corresponden a `division_slug`, recorriendo de la más reciente
    hacia atrás y cortando en la primera que sea de otra división.

    BUG ENCONTRADO Y CORREGIDO (reportado por el usuario: "River
    descendió a la cuarta ronda" -- club.history vacío estaba
    aplastando el rating de clubes establecidos como si acabaran de
    ascender, TODAS las temporadas, porque Club.history hoy no
    persiste entre llamadas reales -- ver HANDOFF_elo_persistente.md,
    sección 3.1/3.4, mismo hueco). Antes, "0 temporadas consecutivas"
    quería decir dos cosas MUY distintas con el mismo número:
      a) el club genuinamente accaba de cambiar de división (la
         entrada más reciente de su historial es de OTRA división --
         evidencia real de un ascenso/descenso reciente), o
      b) club.history está VACÍO -- no hay ningún dato, ni a favor ni
         en contra de que sea un recién llegado.
    (a) es la señal real que el handicap de adaptación necesita. (b)
    es simplemente "no sabemos" -- y "no sabemos" NO debería
    comportarse igual que "sabemos que acaba de llegar": aplicarle el
    handicap fuerte a un club sin datos es asumir lo peor sin
    evidencia, exactamente lo que este proyecto evita en todos los
    demás casos (ver ATAQUE_GENERICO/DEFENSA_GENERICO: "sin
    evidencia, rating neutro", no "sin evidencia, asumir que rinde
    mal"). Ahora devuelve None para el caso (b) -- combinar_con_memoria()
    lo interpreta como "sin handicap, confiar en el rating recién
    calculado" en vez de aplicar la compresión más fuerte.

    division_slug: clave de NIVEL_DIVISION (ej. "lpf", "nacional").
    Lanza ValueError si no es una división válida.
    """
    nombre_pretty = DIVISIONES.get(division_slug)
    if nombre_pretty is None:
        raise ValueError(
            f"división inválida: {division_slug!r} (válidas: {sorted(DIVISIONES)})"
        )

    if not club.history:
        return None

    contador = 0
    for entrada in reversed(club.history):
        if entrada.get("division") != nombre_pretty:
            break
        contador += 1
    return contador


# Reverso de DIVISIONES (slug -> nombre lindo) para poder traducir la
# división ANTERIOR de una entrada de Club.history (que guarda el
# nombre lindo) de vuelta a un slug de NIVEL_DIVISION -- ver
# _ascenso_o_descenso_reciente() más abajo.
_SLUG_DESDE_PRETTY = {pretty: slug for slug, pretty in DIVISIONES.items()}


def _ascenso_o_descenso_reciente(club: Club, division_slug: str) -> bool | None:
    """Mira la entrada de club.history INMEDIATAMENTE ANTERIOR a la
    racha actual en `division_slug` (la división distinta más reciente
    antes de esa racha) y determina si el club LLEGÓ a esta división
    por ascenso o por descenso -- ver _es_ascenso() y el bloque de
    comentarios sobre N_TEMPORADAS_HANDICAP más arriba en el módulo
    (reportado por el usuario: un descenso no debería sufrir el mismo
    handicap que un ascenso).

    Devuelve True si fue ascenso, False si fue descenso, None si no
    hay forma de saberlo (sin historial suficiente, o la división
    anterior no se pudo traducir de vuelta a un slug -- degrada a
    "tratar como ascenso" en combinar_con_memoria(), el criterio más
    conservador, ya que ese era el comportamiento de siempre)."""
    nombre_pretty = DIVISIONES.get(division_slug)
    if nombre_pretty is None or not club.history:
        return None

    entradas = list(reversed(club.history))
    i = 0
    while i < len(entradas) and entradas[i].get("division") == nombre_pretty:
        i += 1
    if i >= len(entradas):
        return None  # toda la historia es de esta misma división -- no hay "llegada" que mirar

    division_anterior_pretty = entradas[i].get("division")
    division_anterior_slug = _SLUG_DESDE_PRETTY.get(division_anterior_pretty)
    if division_anterior_slug is None or division_anterior_slug not in NIVEL_DIVISION:
        return None

    return _es_ascenso(division_anterior_slug, division_slug)


def memoria_ewma(club: Club, division_slug: str, alpha: float = ALPHA_MEMORIA) -> dict | None:
    """Arma la memoria EWMA de ratings de `club` en `division_slug`,
    a partir de la racha CONSECUTIVA de entradas de club.history en
    esa misma división (se corta apenas aparece una entrada de otra
    división -- no se mezcla memoria de una división distinta a la
    actual, ni siquiera si el club jugó ahí en el pasado).

    Entradas de la racha sin clave "ratings" (hoy, Federal A -- ver
    docstring de HistoryManager._actualizar_history()) se saltean sin
    cortar la racha: cuentan para temporadas_consecutivas_en_division()
    pero no aportan dato a la EWMA.

    Devuelve None si la racha está vacía o ninguna de sus entradas
    tiene ratings todavía (primera temporada del club con datos en
    esta división -- combinar_con_memoria() usa el rating_actual tal
    cual en ese caso)."""
    nombre_pretty = DIVISIONES.get(division_slug)
    if nombre_pretty is None:
        raise ValueError(
            f"división inválida: {division_slug!r} (válidas: {sorted(DIVISIONES)})"
        )

    racha = []
    for entrada in reversed(club.history):
        if entrada.get("division") != nombre_pretty:
            break
        racha.append(entrada)
    racha.reverse()  # orden cronológico: la más vieja de la racha primero

    ewma: dict | None = None
    for entrada in racha:
        ratings = entrada.get("ratings")
        if ratings is None:
            continue
        if ewma is None:
            ewma = dict(ratings)
        else:
            ewma = {
                campo: round(alpha * ratings[campo] + (1 - alpha) * ewma[campo], 3)
                for campo in CAMPOS_RATING
            }
    return ewma


def combinar_con_memoria(
    rating_actual: dict,
    club: Club,
    division_slug: str,
    alpha: float = ALPHA_MEMORIA,
) -> dict:
    """Punto de entrada para clubes que CONTINÚAN en la misma división
    de una temporada a la siguiente (no pasan por
    RatingCarryoverPolicy.rating_para_recien_llegado(), que es solo
    para el instante de la llegada). Combina dos cosas:

      1. Memoria EWMA: mezcla `rating_actual` (el rating recién
         calculado con los partidos reales de la temporada que
         termina) con memoria_ewma() de temporadas previas en la
         misma división. Si no hay memoria todavía (primera vez que
         se registra este club con ratings acá), usa rating_actual
         sin mezclar.
      2. Handicap de adaptación: si el club todavía está dentro de
         sus primeras N_TEMPORADAS_HANDICAP temporadas en destino
         (típicamente un recién ascendido/descendido jugando su
         segunda o tercera temporada ahí), comprime el resultado
         hacia el promedio de liga (1.0) con el mismo criterio que
         _factor_handicap() -- ver docstring del módulo. Un club
         asentado (temporadas_consecutivas_en_division() >=
         N_TEMPORADAS_HANDICAP) sale de acá sin ningún handicap.
         BUG CORREGIDO (ver docstring de temporadas_consecutivas_en_division()):
         si no hay NINGÚN dato de historial (club.history vacío --
         hoy pasa siempre que no persiste entre llamadas reales,
         ver HANDOFF_elo_persistente.md), tampoco se aplica handicap
         -- "no sabemos si es reciente" ya NO se trata igual que
         "sabemos que es reciente".
         SEGUNDO BUG CORREGIDO (mismo reporte del usuario que el de
         arriba, "al equipo que desciende le cuesta mucho volver a
         pelear"): el handicap ahora SOLO se aplica si la llegada a
         esta división fue por ASCENSO (ver _ascenso_o_descenso_reciente()
         y _es_ascenso()) -- un club que llegó por DESCENSO no lo
         sufre, en ninguna de sus primeras temporadas ahí.
      3. Piso de prestigio histórico (season/prestigio.py, ver su
         docstring): DESPUÉS de la memoria y el handicap, amortigua
         qué tan lejos del promedio puede quedar cada componente del
         lado MALO, solo para clubes con historial de títulos. No
         empuja a nadie hacia arriba -- un club sin historial pasa por
         acá sin ningún cambio.

    rating_actual: dict con las 4 claves de CAMPOS_RATING.
    Devuelve un dict con las mismas 4 claves.
    """
    memoria = memoria_ewma(club, division_slug, alpha=alpha)
    if memoria is None:
        base = dict(rating_actual)
    else:
        base = {
            campo: round(alpha * rating_actual[campo] + (1 - alpha) * memoria[campo], 3)
            for campo in CAMPOS_RATING
        }

    temporadas = temporadas_consecutivas_en_division(club, division_slug)
    fue_ascenso = _ascenso_o_descenso_reciente(club, division_slug)
    if temporadas is None or fue_ascenso is False:
        # Sin ningún dato de historial (no hay evidencia de que sea un
        # recién llegado), O llegó por descenso (no necesita
        # handicap, ver docstring) -- no se penaliza.
        resultado = base
    else:
        factor = _factor_handicap(temporadas)
        if factor >= 1.0:
            resultado = base
        else:
            resultado = {
                campo: round(1.0 + (base[campo] - 1.0) * factor, 3)
                for campo in CAMPOS_RATING
            }
    return aplicar_piso_prestigio(resultado, club.name)
