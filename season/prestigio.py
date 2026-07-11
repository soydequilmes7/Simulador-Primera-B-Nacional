# -*- coding: utf-8 -*-
"""
season/prestigio.py

Piso de prestigio histórico -- NO reemplaza al ELO ni a la memoria EWMA
de Fase 0 (season/rating_carryover.py), es un tercer ingrediente,
ortogonal a los dos: un club históricamente ganador rara vez colapsa
del todo en una temporada mala (plantel más profundo, más presupuesto,
mejor cantera) -- eso no sale de los resultados de la simulación,
tiene que venir de afuera.

Motivado por una observación real del usuario corriendo varias
temporadas encadenadas de Modo Temporada: clubes que en la vida real
casi nunca salen campeones ni descienden estaban haciendo las dos
cosas con una frecuencia que no se sentía realista. Pidió una tabla de
títulos históricos (liga + copas nacionales + copas internacionales,
amateur y profesional, sin ascensos ni torneos regionales -- fuente:
elgrafico.com.ar, actualizada a Apertura 2026) para calibrar esto.

QUÉ HACE: NO empuja el rating hacia arriba -- un club grande con una
gran temporada se refleja tal cual, sin ningún bonus artificial. SOLO
amortigua qué tan lejos del promedio de liga (1.0) puede caer cada
componente de rating cuando el club está rindiendo POR DEBAJO de lo
esperado. Un club sin historial de títulos no tiene ningún
amortiguador -- una mala temporada le pega entero, como en la vida
real (donde clubes chicos sí pueden desplomarse).

TABLA DE TÍTULOS -- IMPORTANTE, LEER ANTES DE CONFIAR EN ESTO: los
nombres de club de acá están escritos EXACTAMENTE como aparecen HOY en
los CSV del proyecto (datos/tablalpf.csv, datos/tabla.csv,
datos/tabla_bmetro.csv, datos/tabla_federal_a.csv,
datos/tabla_primerac.csv) -- confirmados uno por uno el 11/07/2026,
grepeando cada CSV por separado, para evitar el mismo tipo de bug que
ya existió en este proyecto (nombres ambiguos compartidos entre
divisiones -- ver memoria del proyecto: Estudiantes de La Plata /
Estudiantes de Caseros, Central Córdoba Rosario / SdE, y acá mismo se
encontró un caso nuevo: "Racing" en LPF es Racing Club de Avellaneda,
"Racing (Cba)" en Nacional es un club DISTINTO, Racing Club de
Córdoba -- con eso hay que tener cuidado en cualquier tabla nueva
que use nombres de club como clave).

Algunas entradas de la tabla original NO se incluyeron a propósito por
ambigüedad real, sin forma de confirmar con certeza a qué club del
roster actual corresponden -- ver _ENTRADAS_EXCLUIDAS_POR_AMBIGUEDAD
más abajo. Si alguna resulta importante, confirmarla a mano antes de
agregarla -- no adivinar.
"""
from __future__ import annotations

import math

CAMPOS_RATING = (
    "ataque_local",
    "ataque_visitante",
    "defensa_local",
    "defensa_visitante",
)

# títulos oficiales -- ver docstring del módulo. Nombre de club =
# EXACTAMENTE como aparece en los CSV del proyecto.
TITULOS_HISTORICOS: dict[str, int] = {
    "Boca Jrs.": 74,
    "River": 72,
    "Independiente": 45,
    "Racing": 41,                    # Racing Club (Avellaneda) -- LPF.
                                      # NO confundir con "Racing (Cba)"
                                      # (Nacional), club distinto, sin
                                      # título en la fuente.
    "San Lorenzo": 22,
    "Vélez": 19,
    "Estudiantes": 19,                # Estudiantes de LA PLATA -- LPF.
                                      # NO confundir con "Estudiantes
                                      # (Caseros)" (Nacional) ni
                                      # "Estudiantes RC" (LPF, seguramente
                                      # Río Cuarto), ninguno de esos dos
                                      # tiene título en la fuente.
    "Central": 13,                    # Rosario Central -- LPF.
    "Huracán": 13,
    "Newell's": 9,
    "Lanús": 9,
    "Arsenal de Sarandí": 5,
    "Argentinos": 5,
    "Quilmes": 3,
    "Ferro": 2,
    "Talleres": 2,                    # Talleres de CÓRDOBA -- LPF.
                                      # "Talleres RE" (BMetro) es un
                                      # club distinto, sin título.
    "Banfield": 2,
    "Gimnasia": 2,                    # Gimnasia y Esgrima LA PLATA --
                                      # LPF. NO confundir con
                                      # "Gimnasia (M)" (Mendoza, LPF),
                                      # "Gimnasia (J)" (Jujuy, Nacional)
                                      # ni "Gimnasia y Tiro" (Salta,
                                      # Nacional) -- ninguno tiene
                                      # título en la fuente.
    "Central Córdoba (Rosario)": 1,   # NO confundir con "Central
                                      # Córdoba SdE" (Santiago del
                                      # Estero, LPF), que también está
                                      # en esta tabla pero con su
                                      # propia entrada (1 título cada
                                      # uno, son dos clubes distintos).
    "Central Córdoba SdE": 1,
    "Atlanta": 1,
    "Chacarita": 1,
    "San Martín (T)": 1,              # San Martín de TUCUMÁN -- Nacional.
                                      # NO confundir con "San Martín" a
                                      # secas (Nacional), "San Martín
                                      # Burzaco" (BMetro), "San Martín
                                      # de Formosa" ni "San Martín de
                                      # Mendoza" (Federal A) -- ninguno
                                      # tiene título en la fuente.
    "Tigre": 1,
    "Colón": 1,
    "Patronato": 1,
    "Platense": 1,
    "Independiente Riv.": 1,          # Independiente Rivadavia -- LPF.
    "Sportivo Dock Sud": 1,           # BMetro.
    "Belgrano": 1,                    # Belgrano de Córdoba -- LPF.
}

# Entradas de la fuente original (elgrafico.com.ar) que NO se
# incluyeron arriba, a propósito -- ambigüedad real entre variantes de
# nombre en los CSV del proyecto, sin forma de confirmar con certeza
# cuál es cuál. Antes de agregar cualquiera de estas a
# TITULOS_HISTORICOS, confirmar a mano el nombre exacto:
#
#   - "Defensa y Justicia" (2 títulos): en LPF hay un club "Defensa" a
#     secas -- razonablemente sería este, pero no está confirmado 1:1
#     (no se encontró ningún otro "Defensa*" en los 5 CSV que generara
#     duda, así que es la hipótesis más probable -- pero se prefirió
#     no adivinar).
#   - "Sportivo Barracas" (2 títulos): hay DOS clubes de nombre
#     parecido en el roster actual -- "Barracas" (LPF) y "Sportivo
#     Barracas" (Primera C). La fuente dice "Sportivo Barracas"
#     textual, pero es MUY posible que el club realmente ganador
#     (Barracas Central, Copa Argentina) sea el de LPF, no el de
#     Primera C -- exactamente el tipo de ambigüedad que este módulo
#     quiere evitar. CONFIRMAR antes de incluir cualquiera de las dos.
#   - "Estudiantes de Buenos Aires" (1 título): en el roster hay
#     "Estudiantes RC" (LPF) -- "RC" probablemente sea "Río Cuarto",
#     no "Buenos Aires". No incluido por esa duda.
#   - "Atlético Tucumán" (1 título), "Nueva Chicago" (1 título),
#     "Tiro Federal de Rosario" (1 título): no se encontró ningún club
#     con esos nombres (ni similares) en ninguno de los 5 CSV al
#     armar esta tabla (11/07/2026) -- puede que hoy no estén en
#     ningún roster activo, o que tengan otro nombre en los datos. No
#     incluidos.

# Resistencia MÁXIMA (para el club con más títulos de la tabla, hoy
# Boca) -- valor de arranque razonable, documentado, NO calibrado con
# datos reales todavía (mismo criterio que NIVEL_DIVISION/ALPHA_MEMORIA
# en season/rating_carryover.py). 0.5 significa: en el peor de los
# casos, un club de máximo prestigio recupera la MITAD de la distancia
# entre su rating real y el promedio de liga (1.0) -- nunca el 100%,
# la mala temporada sigue pesando, solo se amortigua.
RESISTENCIA_MAXIMA = 0.5

_TITULOS_MAXIMOS = max(TITULOS_HISTORICOS.values())  # hoy: 74 (Boca)


def factor_resistencia(club_nombre: str) -> float:
    """Factor en [0, RESISTENCIA_MAXIMA] según el prestigio histórico
    del club -- 0 para cualquier club fuera de TITULOS_HISTORICOS (sin
    evidencia, sin ventaja: mismo criterio que el resto del proyecto,
    ej. RatingCarryoverPolicy con ratings_origen=None).

    Escala LOGARÍTMICA, no lineal -- la brecha real entre el top 4-6
    (Boca/River/Independiente/Racing, 40-74 títulos) y el resto (la
    inmensa mayoría con 1-3) es grande, pero no debería traducirse en
    "74 veces más resistencia" -- eso sería absurdo. Con log1p, Boca
    (74) da resistencia máxima, un club de 1 título da ~16% de esa
    resistencia, no ~1.4%."""
    titulos = TITULOS_HISTORICOS.get(club_nombre)
    if not titulos:
        return 0.0
    prestigio = math.log1p(titulos) / math.log1p(_TITULOS_MAXIMOS)
    return round(prestigio * RESISTENCIA_MAXIMA, 4)


def aplicar_piso_prestigio(rating: dict, club_nombre: str) -> dict:
    """Amortigua (sin revertir del todo) qué tan lejos del promedio de
    liga (1.0) puede caer cada componente de `rating`, PARA EL LADO
    MALO únicamente:
      - ataque_local/ataque_visitante: se amortigua si están POR
        DEBAJO de 1.0 (rindiendo menos de lo esperado).
      - defensa_local/defensa_visitante: se amortigua si están POR
        ENCIMA de 1.0 (concediendo más de lo esperado -- convención ya
        establecida en todo el proyecto: defensa > 1.0 es mala).
    Un componente que está rindiendo POR ENCIMA del promedio (del lado
    bueno) queda EXACTAMENTE IGUAL -- esto no empuja a nadie hacia
    arriba, solo evita que alguien con historia se hunda del todo.

    rating: dict con (al menos) las 4 claves de CAMPOS_RATING -- otras
    claves que traiga (ej. "partidos_computados") se devuelven tal
    cual, sin tocar. Devuelve un dict NUEVO."""
    factor = factor_resistencia(club_nombre)
    if factor <= 0:
        return dict(rating)

    resultado = dict(rating)
    for campo in CAMPOS_RATING:
        if campo not in resultado:
            continue
        valor = resultado[campo]
        es_defensa = "defensa" in campo
        rindiendo_mal = (valor > 1.0) if es_defensa else (valor < 1.0)
        if rindiendo_mal:
            resultado[campo] = round(valor + factor * (1.0 - valor), 4)
    return resultado
