# -*- coding: utf-8 -*-
"""
season/geografia_clubes.py

Resuelve el problema planteado por el usuario en Etapa 4: cuando
descienden 4 clubes de Primera Nacional, el reglamento real de AFA
dice que van "a la Primera B Metropolitana o al Torneo Federal A,
SEGÚN LA AFILIACIÓN CORRESPONDIENTE" (confirmado buscando la
reglamentación vigente de Primera Nacional 2026, no es un supuesto).

IMPORTANTE -- esto NO es un reparto fijo de "2 y 2": cada club
desciende a la división que le corresponda por afiliación geográfica
(clubes de Capital Federal / Gran Buenos Aires -> B Metro; clubes del
resto del país -> Federal A). En una temporada real el split entre
los 4 descendidos podría ser 4-0, 3-1, 2-2, etc., según qué clubes
específicos terminen últimos de cada zona -- no hay ninguna regla que
fuerce un reparto parejo.

--------------------------------------------------------------------
ORIGEN DE LOS DATOS -- CORREGIDO CONTRA EL tabla.csv REAL
--------------------------------------------------------------------
La primera versión de esta tabla usaba nombres "lindos" (ej.
"Deportivo Morón", "Ciudad de Bolívar") supuestos a partir de notas
periodísticas del sorteo de zonas. Se corrigió leyendo el
tabla.csv REAL del proyecto (36 filas, columna "equipo") -- las
claves de CLUB_ZONA_GEOGRAFICA de acá abajo son ahora EXACTAMENTE
los strings que aparecen en esa columna, no una versión "prolija" del
nombre. Ejemplos de por qué esto importa: el CSV real dice "Bolivar"
(sin "Ciudad de", sin acento), "Defensores" (no "Defensores de
Belgrano"), "CA Mitre" (no "Mitre (SDE)"), "Chicago" (no "Nueva
Chicago"). Si esta tabla no usa el string EXACTO del CSV, el club cae
en el fallback al azar sin necesidad.

Clasificación geográfica en sí (a qué ciudad/zona pertenece cada
club) sigue siendo la misma investigación de origen (Wikipedia /
Infobae / Relatores.com.ar, sorteo de zonas Nacional 2026,
22/12/2025) -- lo que cambió es el string usado como clave, no el
criterio de AMBA/interior.

Criterio de clasificación:
    "amba"     -> Ciudad Autónoma de Buenos Aires o Gran Buenos Aires
                  (el club desciende a B Metro si corresponde)
    "interior" -> resto del país (el club desciende a Federal A si
                  corresponde)

--------------------------------------------------------------------
CLUBES SIN CLASIFICAR / ROSTER FUTURO
--------------------------------------------------------------------
Esta tabla está armada sobre el roster de Nacional QUE HOY (julio
2026) tenés en tabla.csv. Cada temporada entran/salen equipos por
ascenso/descenso -- si en el futuro aparece un club nuevo acá no
reconocido, clasificar_zona_geografica() devuelve None y es
responsabilidad de quien llama (PromotionManager) decidir el
fallback (acá se usa al azar, según lo charlado con el usuario). Lo
ideal es agregar el club real a esta tabla apenas se detecta el
hueco (el aviso que genera PromotionManager ya dice el nombre exacto
que faltó), no depender del azar para siempre.
"""

CLUB_ZONA_GEOGRAFICA = {
    # -------------------- Zona A (tabla.csv real) --------------------
    "Morón": "amba",
    "Ferro": "amba",
    "Los Andes": "amba",
    "Colón": "interior",
    "Dep. Madryn": "interior",
    "Bolivar": "interior",          # interior de la pcia. de Bs. As. (no GBA)
    "Alte. Brown": "amba",
    "Estudiantes": "amba",          # Estudiantes (Caseros, GBA) -- no confundir con Estudiantes de Río Cuarto (ascendió a LPF)
    "Godoy Cruz": "interior",
    "San Miguel": "amba",
    "San Telmo": "amba",
    "Defensores": "amba",           # Defensores de Belgrano (Núñez, CABA)
    "Racing (Cba)": "interior",
    "All Boys": "amba",
    "Central Norte": "interior",
    "Acassuso": "amba",
    "CA Mitre": "interior",         # Mitre de Santiago del Estero
    "Chaco For Ever": "interior",

    # -------------------- Zona B (tabla.csv real) --------------------
    "Gimnasia (J)": "interior",     # Gimnasia y Esgrima de Jujuy
    "Atlanta": "amba",
    "Tristan Suárez": "amba",
    "Atlético Rafaela": "interior",
    "Temperley": "amba",
    "Midland": "amba",
    "San Martín": "interior",       # San Martín de San Juan (distinto de "San Martín (T)")
    "Colegiales": "amba",
    "San Martín (T)": "interior",   # San Martín de Tucumán
    "Maipú": "interior",            # Deportivo Maipú (Mendoza)
    "Chicago": "amba",              # Nueva Chicago (Mataderos, CABA)
    "Almagro": "amba",
    "Quilmes": "amba",
    "Gimnasia y Tiro": "interior",  # Salta
    "Patronato": "interior",        # Paraná, Entre Ríos
    "Chacarita": "amba",
    "Güemes": "interior",           # Güemes de Santiago del Estero
    "Agropecuario": "interior",     # Agropecuario Argentino, Carlos Casares
}


def clasificar_zona_geografica(nombre_club: str) -> str | None:
    """Devuelve "amba" o "interior" según la tabla de arriba, o None
    si el club no está clasificado (ver docstring del módulo: es
    responsabilidad de quien llama decidir el fallback)."""
    return CLUB_ZONA_GEOGRAFICA.get(nombre_club)
