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
ORIGEN DE LOS DATOS -- LISTAS OFICIALES DE AFILIACIÓN (provistas por
el usuario, reemplazan la tabla anterior)
--------------------------------------------------------------------
CLUB_ZONA_GEOGRAFICA se arma ahora a partir de las dos listas
oficiales de afiliación de clubes que dio el usuario: "AFILIACIÓN
DIRECTA" (-> "amba", desciende a Primera B Metropolitana) y
"AFILIACIÓN INDIRECTA" (-> "interior", desciende al Federal A). Son
las claves con el nombre "prolijo" del club.

Como el resto del sistema (tabla.csv / public/data.json) sigue
usando para varios clubes un string más corto/abreviado que el
nombre "prolijo" de esas listas (ej. el CSV real dice "Bolivar" en
vez de "Ciudad de Bolívar", "Defensores" en vez de "Defensores de
Belgrano", "CA Mitre" en vez de "Mitre (SDE)", "Chicago" en vez de
"Nueva Chicago"), se agregó debajo de las dos listas un bloque de
ALIAS: la misma clave pero con el string exacto de tabla.csv,
apuntando a la MISMA clasificación amba/interior que su entrada
"prolija" -- no reclasifica ningún club, solo evita que
clasificar_zona_geografica() lo pierda por una diferencia de nombre.

Había 3 clubes de Primera Nacional que hoy están en tabla.csv pero
que no aparecían en ninguna de las dos listas nuevas ("San Telmo",
"Gimnasia y Tiro" de Salta, y "Defensores" / Defensores de Belgrano
de Núñez, CABA). El usuario confirmó su clasificación directamente:
San Telmo y Defensores -> B Metro (amba), Gimnasia y Tiro -> Federal
A (interior).

--------------------------------------------------------------------
DESAMBIGUACIÓN DE HOMÓNIMOS ENTRE DIVISIONES (confirmado con el
usuario)
--------------------------------------------------------------------
ClubRegistry.build_from_current_data() exige nombre único en TODO el
sistema (un club no puede pertenecer a dos divisiones a la vez). Al
correrlo contra los tabla_X.csv reales aparecieron dos colisiones,
ambas clubes distintos de verdad, no error de tipeo:

    "Estudiantes"       -> Estudiantes de La Plata (LPF) vs.
                           Estudiantes de Caseros (Primera Nacional)
    "Central Córdoba"   -> Central Córdoba de Santiago del Estero (LPF)
                           vs. Central Córdoba de Rosario (Primera C)

Se renombró en el CSV de origen el lado que NO es LPF (el de LPF
queda con el nombre corto, por ser el más conocido/mencionado sin
aclaración en medios): "Estudiantes (Caseros)" en tabla.csv,
"Central Córdoba (Rosario)" en tabla_primerac.csv. Central Córdoba
(Rosario) no entra en CLUB_ZONA_GEOGRAFICA porque esta tabla es solo
para clubes de Primera NACIONAL (los que necesitan resolver destino
geográfico al descender) -- Primera C no desciende a ningún lado.

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

# --------------------------------------------------------------------
# Listas de afiliación provistas por el usuario (correguidas, reemplazan
# la tabla anterior). AFILIACIÓN DIRECTA -> "amba" (desciende a Primera B
# Metropolitana). AFILIACIÓN INDIRECTA -> "interior" (desciende al Federal A).
# --------------------------------------------------------------------
CLUB_ZONA_GEOGRAFICA = {
    # ================= AFILIACIÓN DIRECTA (-> "amba" / Primera B Metropolitana) =================
    "Acassuso": "amba",
    "All Boys": "amba",
    "Almagro": "amba",
    "Almirante Brown": "amba",
    "Argentino de Quilmes": "amba",
    "Argentinos Juniors": "amba",
    "Atlanta": "amba",
    "Atlas": "amba",
    "Banfield": "amba",
    "Barracas Central": "amba",
    "Berazategui": "amba",
    "Boca Juniors": "amba",
    "Brown de Adrogué": "amba",
    "CADU (Defensores Unidos)": "amba",
    "Cambaceres": "amba",
    "Cañuelas": "amba",
    "Central Ballester": "amba",
    "Central Córdoba (Rosario)": "amba",
    "Chacarita Juniors": "amba",
    "Claypole": "amba",
    "Colegiales": "amba",
    "Comunicaciones": "amba",
    "Defensa y Justicia": "amba",
    "Deportivo Armenio": "amba",
    "Deportivo Español": "amba",
    "Deportivo Laferrere": "amba",
    "Deportivo Merlo": "amba",
    "Deportivo Morón": "amba",
    "Deportivo Paraguayo": "amba",
    "Deportivo Riestra": "amba",
    "Dock Sud": "amba",
    "El Porvenir": "amba",
    "Estudiantes (Buenos Aires)": "amba",
    "Estudiantes (La Plata)": "amba",
    "Excursionistas": "amba",
    "Ferro": "amba",
    "Ferrocarril Midland": "amba",
    "Fénix": "amba",
    "Flandria": "amba",
    "General Lamadrid": "amba",
    "Gimnasia (La Plata)": "amba",
    "Huracán": "amba",
    "Independiente": "amba",
    "Ituzaingó": "amba",
    "JJ Urquiza": "amba",
    "Juventud Unida": "amba",
    "Lanús": "amba",
    "Leandro N. Alem": "amba",
    "Liniers": "amba",
    "Los Andes": "amba",
    "Lugano": "amba",
    "Luján": "amba",
    "Mercedes": "amba",
    "Muñiz": "amba",
    "Nueva Chicago": "amba",
    "Platense": "amba",
    "Puerto Nuevo": "amba",
    "Quilmes": "amba",
    "Racing Club": "amba",
    "Real Pilar": "amba",
    "River Plate": "amba",
    "Sacachispas": "amba",
    "San Carlos": "amba",
    "San Lorenzo": "amba",
    "San Miguel": "amba",
    "Sportivo Barracas": "amba",
    "Sportivo Italiano": "amba",
    "Temperley": "amba",
    "Tigre": "amba",
    "Tristán Suárez": "amba",
    "UAI Urquiza": "amba",
    "Vélez Sarsfield": "amba",
    "Victoriano Arenas": "amba",
    "Villa Dálmine": "amba",
    "Villa Soldati": "amba",
    "Yupanqui": "amba",

    # ================= AFILIACIÓN INDIRECTA (-> "interior" / Federal A) =================
    "Aldosivi": "interior",
    "Alvarado": "interior",
    "Agropecuario": "interior",
    "Argentino de Monte Maíz": "interior",
    "Atenas de Río Cuarto": "interior",
    "Atlético de Rafaela": "interior",
    "Atlético Escobar": "interior",
    "Atlético Tucumán": "interior",
    "Bartolomé Mitre": "interior",
    "Belgrano": "interior",
    "Boca Unidos de Corrientes": "interior",
    "Central Córdoba (Santiago del Estero)": "interior",
    "Central Norte": "interior",
    "Chaco For Ever": "interior",
    "Cipolletti": "interior",
    "Círculo Deportivo": "interior",
    "Ciudad de Bolívar": "interior",
    "Colón": "interior",
    "Crucero del Norte": "interior",
    "Defensores de Belgrano (Villa Ramallo)": "interior",
    "Defensores de Vilelas": "interior",
    "Deportivo Madryn": "interior",
    "Deportivo Maipú": "interior",
    "Douglas Haig": "interior",
    "El Linqueño": "interior",
    "Estudiantes de Río Cuarto": "interior",
    "FAD": "interior",
    "Germinal": "interior",
    "Gimnasia de Jujuy": "interior",
    "Gimnasia de Mendoza": "interior",
    "Gimnasia de Concepción del Uruguay": "interior",
    "Godoy Cruz": "interior",
    "Gutiérrez": "interior",
    "Güemes": "interior",
    "Huracán Las Heras": "interior",
    "Independiente de Chivilcoy": "interior",
    "Independiente Rivadavia": "interior",
    "Instituto": "interior",
    "Juventud Antoniana": "interior",
    "Juventud Unida Universitario": "interior",
    "Kimberley": "interior",
    "Mitre (Santiago del Estero)": "interior",
    "Newell's Old Boys": "interior",
    "Olimpo": "interior",
    "Patronato": "interior",
    "Racing de Córdoba": "interior",
    "Rosario Central": "interior",
    "San Martín de Formosa": "interior",
    "San Martín de Mendoza": "interior",
    "San Martín de San Juan": "interior",
    "San Martín de Tucumán": "interior",
    "Santamarina": "interior",
    "Sarmiento": "interior",
    "Sarmiento de La Banda": "interior",
    "Sarmiento de Resistencia": "interior",
    "Sol de América": "interior",
    "Sol de Mayo": "interior",
    "Sportivo Belgrano": "interior",
    "Sportivo Estudiantes": "interior",
    "Sportivo Las Parejas": "interior",
    "Sportivo Peñarol": "interior",
    "Talleres": "interior",
    "Tucumán Central": "interior",
    "Unión": "interior",
    "Villa Mitre": "interior",

    # ---------------------------------------------------------------
    # Alias: mismos clubes de arriba, pero con el string EXACTO que
    # aparece hoy en tabla.csv / public/data.json (Primera Nacional),
    # que suele ser más corto/abreviado que el nombre "prolijo" de la
    # lista de afiliación. Se mantienen para que clasificar_zona_geografica()
    # siga funcionando con los nombres reales que usa el resto del sistema.
    # La clasificación (amba/interior) es la misma que la de su entrada
    # "prolija" de arriba -- esto no reclasifica ningún club, solo agrega
    # la clave alternativa.
    # ---------------------------------------------------------------
    "Morón": "amba",  # alias de "Deportivo Morón" (nombre real en tabla.csv)
    "Dep. Madryn": "interior",  # alias de "Deportivo Madryn" (nombre real en tabla.csv)
    "Bolivar": "interior",  # alias de "Ciudad de Bolívar" (nombre real en tabla.csv)
    "Alte. Brown": "amba",  # alias de "Almirante Brown" (nombre real en tabla.csv)
    "Estudiantes (Caseros)": "amba",  # alias de "Estudiantes (Buenos Aires)" (nombre real en tabla.csv)
    "Racing (Cba)": "interior",  # alias de "Racing de Córdoba" (nombre real en tabla.csv)
    "CA Mitre": "interior",  # alias de "Mitre (Santiago del Estero)" (nombre real en tabla.csv)
    "Gimnasia (J)": "interior",  # alias de "Gimnasia de Jujuy" (nombre real en tabla.csv)
    "Tristan Suárez": "amba",  # alias de "Tristán Suárez" (nombre real en tabla.csv)
    "Atlético Rafaela": "interior",  # alias de "Atlético de Rafaela" (nombre real en tabla.csv)
    "Midland": "amba",  # alias de "Ferrocarril Midland" (nombre real en tabla.csv)
    "San Martín": "interior",  # alias de "San Martín de San Juan" (nombre real en tabla.csv)
    "San Martín (T)": "interior",  # alias de "San Martín de Tucumán" (nombre real en tabla.csv)
    "Maipú": "interior",  # alias de "Deportivo Maipú" (nombre real en tabla.csv)
    "Chicago": "amba",  # alias de "Nueva Chicago" (nombre real en tabla.csv)
    "Chacarita": "amba",  # alias de "Chacarita Juniors" (nombre real en tabla.csv)

    # ---------------------------------------------------------------
    # Clubes de Primera Nacional que no venían en ninguna de las dos
    # listas de afiliación originales del usuario. Clasificación
    # confirmada directamente por el usuario.
    # ---------------------------------------------------------------
    "San Telmo": "amba",            # confirmado por el usuario -> B Metro
    "Gimnasia y Tiro": "interior",  # confirmado por el usuario (Salta) -> Federal A
    "Defensores": "amba",           # confirmado por el usuario -- Defensores de Belgrano (Núñez, CABA) -> B Metro
}


def clasificar_zona_geografica(nombre_club: str) -> str | None:
    """Devuelve "amba" o "interior" según la tabla de arriba, o None
    si el club no está clasificado (ver docstring del módulo: es
    responsabilidad de quien llama decidir el fallback)."""
    return CLUB_ZONA_GEOGRAFICA.get(nombre_club)
