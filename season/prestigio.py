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
nombres de club de acá tienen que ser el nombre REAL que usa
Club.name a través de todo el sistema -- que NO siempre es el que
aparece en el CSV crudo.

BUG ENCONTRADO Y CORREGIDO (segunda vuelta, reportado por el usuario:
"los equipos que descienden de Primera a la B casi por sentado
descienden de nuevo" seguía pasando después de corregir el motor de
Nacional -- la traza llevó hasta acá): `modelos/estadisticas_lpf.py`
tiene un diccionario `NORMALIZACION_NOMBRES` que traduce nombres
cortos del CSV a nombres largos ANTES de que el club llegue a
`Club.name` (ej. "Boca Jrs." -> "Boca Juniors", "River" -> "River
Plate", "Racing" -> "Racing Club", "Newell's" -> "Newell's Old
Boys"). La primera versión de esta tabla se armó grepeando el CSV
crudo directamente -- coincidía con lo que Devuelve pandas al leer
el archivo, pero NO con el nombre real que circula por
ClubRegistry/Club.history una vez pasado por `normalizar()`. Resultado:
~11 de los ~29 clubes de la tabla original (incluidos Boca, River,
Racing, Vélez, Estudiantes, Newell's, Rosario Central, Argentinos,
Talleres, Gimnasia, Independiente Rivadavia) NUNCA hacían match, el
piso de prestigio les daba 0 resistencia en la práctica aunque
estuvieran "en la tabla". Ahora los nombres de acá son los YA
NORMALIZADOS (el valor de destino del diccionario de arriba, no la
clave). Esta normalización SOLO existe en LPF -- confirmado
grepeando estadisticas.py/estadisticas_bmetro.py/
estadisticas_primerac.py/estadisticas_federal.py, ninguno tiene un
mecanismo equivalente -- así que los clubes de las otras 4 divisiones
de esta tabla no tenían este problema.

De paso, esto resolvió DOS de las ambigüedades que había dejado
afuera en la primera versión (ver
_ENTRADAS_EXCLUIDAS_POR_AMBIGUEDAD más abajo, ahora más corta):
"Barracas" normaliza a "Barracas Central" (confirma que el título de
Sportivo Barracas en la fuente original en realidad corresponde al
club de LPF, no al de Primera C) y "Defensa" normaliza a "Defensa y
Justicia" (ya no es una hipótesis). También apareció "Atl. Tucumán"
-> "Atlético Tucumán" en el diccionario, que antes no había podido
encontrar en ningún CSV con la búsqueda que usé.
"""
from __future__ import annotations

import math

CAMPOS_RATING = (
    "ataque_local",
    "ataque_visitante",
    "defensa_local",
    "defensa_visitante",
)

# títulos oficiales -- ver docstring del módulo. Nombre de club = el
# nombre REAL que usa Club.name (para LPF, ya pasado por
# modelos.estadisticas_lpf.normalizar() -- ver el bug corregido
# arriba), no necesariamente el que aparece crudo en el CSV.
TITULOS_HISTORICOS: dict[str, int] = {
    "Boca Juniors": 74,
    "River Plate": 72,
    "Independiente": 45,
    "Racing Club": 41,                # Racing Club (Avellaneda) -- LPF.
                                      # NO confundir con "Racing (Cba)"
                                      # (Nacional), club distinto, sin
                                      # título en la fuente (ESE sí
                                      # queda tal cual del CSV, Nacional
                                      # no normaliza nombres).
    "San Lorenzo": 22,
    "Vélez Sarsfield": 19,
    "Estudiantes de La Plata": 19,    # LPF. NO confundir con
                                      # "Estudiantes (Caseros)" (Nacional)
                                      # ni "Estudiantes RC" (LPF,
                                      # seguramente Río Cuarto -- no se
                                      # normaliza a ningún nombre largo,
                                      # se queda "Estudiantes RC" tal
                                      # cual), ninguno de esos dos tiene
                                      # título en la fuente.
    "Rosario Central": 13,            # LPF (normaliza desde "Central").
    "Huracán": 13,
    "Newell's Old Boys": 9,           # LPF (normaliza desde "Newell's").
    "Lanús": 9,
    "Arsenal de Sarandí": 5,          # BMetro.
    "Argentinos Juniors": 5,          # LPF (normaliza desde "Argentinos").
    "Quilmes": 3,                     # Nacional.
    "Ferro": 2,                       # Nacional.
    "Talleres de Córdoba": 2,         # LPF (normaliza desde "Talleres").
    "Banfield": 2,
    "Gimnasia La Plata": 2,           # LPF (normaliza desde "Gimnasia").
                                      # NO confundir con "Gimnasia (M)"
                                      # (normaliza a "Gimnasia de
                                      # Mendoza", LPF), "Gimnasia (J)"
                                      # (Jujuy, Nacional) ni "Gimnasia y
                                      # Tiro" (Salta, Nacional) --
                                      # ninguno tiene título en la fuente.
    "Barracas Central": 2,            # LPF (normaliza desde "Barracas").
                                      # Confirmado por la normalización:
                                      # es el club de LPF, NO "Sportivo
                                      # Barracas" (Primera C).
    "Defensa y Justicia": 2,          # LPF (normaliza desde "Defensa").
    "Central Córdoba (Rosario)": 1,   # Primera C. NO confundir con
                                      # "Central Córdoba SdE" (Santiago
                                      # del Estero, LPF), entrada aparte.
    "Central Córdoba SdE": 1,         # LPF (normaliza desde "Central
                                      # Córdoba" a secas).
    "Atlanta": 1,                     # Nacional.
    "Chacarita": 1,                   # Nacional.
    "San Martín (T)": 1,              # San Martín de TUCUMÁN -- Nacional
                                      # (no tiene normalización propia,
                                      # se queda con este nombre). NO
                                      # confundir con "San Martín" a
                                      # secas (Nacional), "San Martín
                                      # Burzaco" (BMetro), "San Martín
                                      # de Formosa" ni "San Martín de
                                      # Mendoza" (Federal A).
    "Tigre": 1,                       # LPF.
    "Colón": 1,                       # Nacional.
    "Patronato": 1,                   # Nacional.
    "Atlético Tucumán": 1,            # LPF (normaliza desde "Atl. Tucumán").
    "Platense": 1,                    # LPF.
    "Independiente Rivadavia": 1,     # LPF (normaliza desde
                                      # "Independiente Riv.").
    "Sportivo Dock Sud": 1,           # BMetro.
    "Belgrano": 1,                    # Belgrano de Córdoba -- LPF.
}

# Entradas de la fuente original (elgrafico.com.ar) que NO se
# incluyeron, a propósito -- ambigüedad real sin forma de confirmar
# con certeza a qué club del roster actual corresponden. Antes de
# agregar cualquiera de estas, confirmar a mano el nombre exacto:
#
#   - "Estudiantes de Buenos Aires" (1 título): en el roster hay
#     "Estudiantes RC" (LPF, sin normalización propia en
#     NORMALIZACION_NOMBRES) -- "RC" probablemente sea "Río Cuarto",
#     no "Buenos Aires". No incluido por esa duda.
#   - "Nueva Chicago" (1 título), "Tiro Federal de Rosario" (1
#     título): no se encontró ningún club con esos nombres (ni
#     similares, ni en el CSV crudo ni en NORMALIZACION_NOMBRES) en
#     ninguno de los 5 CSV al armar esta tabla -- puede que hoy no
#     estén en ningún roster activo. No incluidos.

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
