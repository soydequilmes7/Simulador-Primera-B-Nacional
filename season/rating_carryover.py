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
"""

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
# otra división frente a la regresión al promedio de la liga nueva.
N_CARRYOVER = 12

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

        Devuelve un dict con las 4 claves de CAMPOS_RATING.

        Lanza ValueError si division_destino no es una división
        válida, si division_origen no es válida (cuando corresponde
        chequearla), o si a ratings_origen le faltan claves.
        """
        if division_destino not in NIVEL_DIVISION:
            raise ValueError(
                f"división de destino inválida: {division_destino!r} "
                f"(válidas: {sorted(NIVEL_DIVISION)})"
            )

        # Sin historial en ninguna división -> rating genérico fijo,
        # mismo criterio que _cosechar_ratings_ligas() de la Copa.
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

        resultado = {}
        for campo in CAMPOS_RATING:
            valor_origen = ratings_origen[campo]
            valor_ajustado = 1.0 + (valor_origen - 1.0) * factor
            resultado[campo] = round(
                (N_CARRYOVER * valor_ajustado + K_REGRESION * 1.0)
                / (N_CARRYOVER + K_REGRESION),
                3,
            )
        return resultado
