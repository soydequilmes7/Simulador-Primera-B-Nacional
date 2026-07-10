# -*- coding: utf-8 -*-
"""
season/promotion_manager.py

Etapa 4 del plan (ver PLAN_MODO_TEMPORADA_NACIONAL.txt, sección 4 y
6): PromotionManager centraliza "cuántos bajan de LPF, cuántos suben
de Nacional, cómo se resuelven los cupos cruzados" -- hoy disperso
implícitamente entre los distintos main_X.py/estadisticas_X.py.

--------------------------------------------------------------------
SLUG vs NOMBRE LINDO DE DIVISIÓN -- IMPORTANTE
--------------------------------------------------------------------
season/club_registry.py (Etapa 0, ya validado) guarda club.division
como el NOMBRE LINDO ("Primera Nacional", "Federal A", "Primera B
Metropolitana", etc. -- ver DIVISIONES en ese módulo), NO el slug
interno ("nacional", "federal_a") que usan los adaptadores de
season/adapters/*.py y las claves de `resultados` acá abajo.

Este módulo trabaja en SLUGS internamente (coherente con
ResultadoTorneo y con los adaptadores) y traduce a nombre lindo
SOLO en el borde donde toca club.division -- vía
club_registry.DIVISIONES, importado directo del módulo real. Si en
algún momento DIVISIONES cambia de valores en club_registry.py, este
módulo se actualiza solo (no tiene su propia copia del diccionario).

--------------------------------------------------------------------
INTERFAZ QUE PromotionManager USA DE club_registry
--------------------------------------------------------------------
Confirmada contra el season/club_registry.py real (Etapa 4):

    club_registry.get_by_name(nombre) -> Club | None
    club_registry.agregar_club(nombre, division_linda) -> Club   (nuevo, agregado en Etapa 4)
    club_registry.retirar_club(nombre) -> Club | None            (nuevo, agregado en Etapa 4)

Un Club (real, modelos/club.py) tiene como mínimo `.nombre`/`.name` y
`.division` (mutable). OJO: el Club real usa el atributo `name`, no
`nombre` -- ver _nombre_de(club) más abajo, que soporta las dos
formas por si el mock de validar_etapa4.py usa `.nombre`.

--------------------------------------------------------------------
REGLAS DE ASCENSO/DESCENSO (confirmadas leyendo el código real de
cada adaptador -- ver season/adapters/*.py y el plan, sección 4)
--------------------------------------------------------------------
    LPF        <-> Nacional:   LPF desciende 2, Nacional asciende 2
                               (ganador ascenso directo + campeón
                               reducido).
    Nacional   -> {BMetro, Federal A}: Nacional desciende 4 (últimos
                               2 de cada zona, ver la corrección de
                               NacionalAdapter en Etapa 4). CADA club
                               va a la división que le corresponda
                               por afiliación geográfica (AMBA ->
                               BMetro, interior -> Federal A) -- NO es
                               un reparto fijo 2-y-2, ver
                               season/geografia_clubes.py.
    BMetro     -> Nacional:    BMetro asciende 2 (puntero_ascenso_
                               directo + campeon_reducido).
    Federal A  -> Nacional:    Federal A asciende 2 (ascenso_1 +
                               ascenso_2).
    BMetro     <-> Primera C:  BMetro desciende 2 (últimos de tabla),
                               Primera C asciende 2 (mismo shape que
                               Nacional).
    Federal A  -> (afuera del sistema): Federal A desciende 4 por la
                               Reválida, a torneos regionales que
                               este proyecto NO simula. Esos 4 clubes
                               salen del ClubRegistry. Por decisión
                               del usuario (Etapa 4), se reponen esos
                               cupos con clubes REALES del Torneo
                               Regional Federal Amateur (ver
                               POOL_ASCENSO_REGIONAL más abajo)
                               mientras el pool tenga nombres sin usar;
                               si se agota, cae a un nombre ficticio
                               tipo "Ingreso Regional N" como
                               respaldo, para que el roster de
                               Federal A no se achique temporada a
                               temporada.
    Primera C  -> (nada):      Primera C es el piso del sistema
                               modelado, no tiene descensos (ya
                               confirmado en Etapa 1/2, PrimeraCAdapter
                               siempre trae descensos=[]).
    Copa Argentina:            NO alimenta ascensos/descensos (torneo
                               paralelo, no es división del sistema).
                               PromotionManager no la recibe.
"""

import random

from season.club_registry import DIVISIONES
from season.geografia_clubes import clasificar_zona_geografica

DIVISIONES_PROMOTION = ("lpf", "nacional", "bmetro", "federal_a", "primerac")

# Cuántos clubes de relleno hay que generar por cada uno que Federal A
# pierde por Reválida (1 a 1: se repone exactamente lo que se fue).
RELLENO_FEDERAL_POR_DESCENSO = 1

# Pool real de clubes que ascienden a Federal A por el Torneo Regional
# Federal Amateur (torneo que este proyecto no simula -- ver más abajo,
# _elegir_club_relleno()). Lista provista por el usuario; reemplaza los
# nombres ficticios tipo "Ingreso Regional N" mientras haya clubes
# disponibles en el pool sin usar.
POOL_ASCENSO_REGIONAL = (
    "Ben Hur",
    "Crucero del Norte",
    "Gutiérrez Sportivo",
    "Estudiantes (SL)",
    "Defensores de Pronunciamiento",
    "Ferro Carril Oeste (GP)",
    "Sansinena",
    "Unión (S)",
    "Liniers (BB)",
    "Sportivo Peñarol (C)",
)


def _nombre_de(club) -> str:
    """Soporta tanto Club real (.name) como un mock que use .nombre,
    para no atarse a un solo naming en los tests."""
    return getattr(club, "name", None) or getattr(club, "nombre")


class PromotionManager:
    def __init__(self, rng: random.Random | None = None, pool_regional: list[str] | None = None):
        # rng inyectable para que validar_etapa4.py pueda fijar semilla
        # y tener corridas reproducibles al testear el fallback al azar.
        self._rng = rng or random.Random()
        self._contador_relleno = 0
        # Pool de reposición real, en orden -- se va agotando a medida
        # que aplicar() lo usa (no se repite un club mientras esté
        # activo en el registro), pero un club que vuelve a bajar de
        # Federal A por Reválida se reincorpora al final de la cola
        # (ver _retirar_club) para poder re-ascender más adelante en
        # vez de perderse para siempre -- así, mientras el sistema siga
        # corriendo temporadas, casi nunca hace falta el nombre
        # ficticio de respaldo.
        #
        # `pool_regional` es inyectable para que quien llame (ver
        # api/index.py, _correr_temporada_desde_estado) pueda pasar el
        # estado del pool de la ronda anterior en vez de arrancar
        # siempre de los 10 nombres originales de POOL_ASCENSO_REGIONAL
        # -- PromotionManager se instancia de nuevo en cada request
        # (no hay estado en memoria entre rondas), así que sin esto el
        # pool se reseteaba entero cada vez.
        self._pool_restante = (
            list(pool_regional) if pool_regional is not None
            else list(POOL_ASCENSO_REGIONAL)
        )

    def aplicar(self, resultados: dict, club_registry, temporada_destino: str = "N+1") -> dict:
        """
        resultados: dict con las 5 claves de DIVISIONES_PROMOTION (los
            SLUGS internos, no el nombre lindo), cada una un
            ResultadoTorneo (o cualquier objeto con .ascensos /
            .descensos -- ver season/tournament_adapter.py). NO
            incluye "copa" -- Copa Argentina no alimenta esto.
        club_registry: instancia de season.club_registry.ClubRegistry
            (o un mock con la misma interfaz -- ver docstring del
            módulo).
        temporada_destino: string libre usado solo para nombrar los
            clubes de relleno generados (ej. "2027").

        Devuelve un resumen (dict) con "movimientos" (lista de dicts
        club/origen/destino/motivo, en SLUGS), "avisos" (lista de
        strings -- clubes no encontrados, clasificaciones geográficas
        resueltas al azar, etc.) y "pool_regional_restante" (lista de
        nombres, el estado del pool de reposición de Federal A después
        de esta corrida -- incluye tanto lo que quedó sin usar de
        POOL_ASCENSO_REGIONAL como los clubes que bajaron por Reválida
        en ESTA misma corrida y volvieron a la cola). Quien llama debe
        guardar esa lista y pasarla como `pool_regional` en la próxima
        instancia de PromotionManager (ver api/index.py,
        _correr_temporada_desde_estado) -- si no se hace, el pool se
        resetea a los 10 nombres originales en cada ronda y el
        reciclado de clubes que bajan no tiene efecto.
        """
        faltantes = [d for d in DIVISIONES_PROMOTION if d not in resultados]
        if faltantes:
            raise ValueError(
                f"Faltan resultados de división en `resultados`: {faltantes}"
            )

        resumen = {"movimientos": [], "avisos": []}

        # 1) LPF <-> Nacional
        for nombre in resultados["lpf"].descensos:
            self._mover_club(club_registry, nombre, "lpf", "nacional", resumen)
        for nombre in resultados["nacional"].ascensos:
            self._mover_club(club_registry, nombre, "nacional", "lpf", resumen)

        # 2) Nacional -> {bmetro, federal_a}, por afiliación geográfica
        for nombre in resultados["nacional"].descensos:
            destino = self._resolver_destino_geografico(nombre, resumen)
            self._mover_club(club_registry, nombre, "nacional", destino, resumen)

        # 3) {bmetro, federal_a} -> Nacional
        for nombre in resultados["bmetro"].ascensos:
            self._mover_club(club_registry, nombre, "bmetro", "nacional", resumen)
        for nombre in resultados["federal_a"].ascensos:
            self._mover_club(club_registry, nombre, "federal_a", "nacional", resumen)

        # 4) bmetro <-> primerac
        for nombre in resultados["bmetro"].descensos:
            self._mover_club(club_registry, nombre, "bmetro", "primerac", resumen)
        for nombre in resultados["primerac"].ascensos:
            self._mover_club(club_registry, nombre, "primerac", "bmetro", resumen)

        # 5) Federal A pierde 4 por Reválida -> salen del sistema,
        #    se generan clubes de relleno para reponer el roster.
        #    (reincorporar_al_pool=True: el club retirado vuelve a la
        #    cola de candidatos a re-ascender más adelante, ver
        #    _retirar_club()).
        descensos_federal = resultados["federal_a"].descensos
        for nombre in descensos_federal:
            self._retirar_club(club_registry, nombre, resumen, reincorporar_al_pool=True)

        n_relleno = len(descensos_federal) * RELLENO_FEDERAL_POR_DESCENSO
        for _ in range(n_relleno):
            nombre_nuevo, del_pool = self._elegir_club_relleno(club_registry, temporada_destino)
            club = club_registry.agregar_club(nombre_nuevo, DIVISIONES["federal_a"])
            try:
                club.es_relleno = True
            except Exception:
                pass  # si Club usara __slots__, no es crítico -- el resumen ya lo etiqueta
            motivo = (
                "ascenso_torneo_regional (reemplaza baja por Reválida -- club real "
                "del Torneo Regional Federal Amateur, ver POOL_ASCENSO_REGIONAL)"
                if del_pool else
                "relleno_federal_a (reemplaza baja por Reválida hacia torneo regional "
                "no simulado -- pool de clubes reales agotado, nombre ficticio de respaldo)"
            )
            resumen["movimientos"].append({
                "club": nombre_nuevo,
                "origen": None,
                "destino": "federal_a",
                "motivo": motivo,
            })

        resumen["pool_regional_restante"] = list(self._pool_restante)
        return resumen

    # ------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------

    def _resolver_destino_geografico(self, nombre_club: str, resumen: dict) -> str:
        zona = clasificar_zona_geografica(nombre_club)
        if zona is None:
            zona = self._rng.choice(["amba", "interior"])
            resumen["avisos"].append(
                f"{nombre_club!r}: sin clasificación geográfica en "
                f"season/geografia_clubes.py, asignado a {zona!r} al azar. "
                f"Agregar el club a CLUB_ZONA_GEOGRAFICA para que deje de "
                f"depender del azar."
            )
        return "bmetro" if zona == "amba" else "federal_a"

    def _mover_club(self, club_registry, nombre: str, division_origen_esperada_slug: str,
                     division_destino_slug: str, resumen: dict) -> None:
        club = club_registry.get_by_name(nombre)
        if club is None:
            resumen["avisos"].append(
                f"Club no encontrado en el registro: {nombre!r} "
                f"(se esperaba mover de {division_origen_esperada_slug!r} a "
                f"{division_destino_slug!r}, no se hizo nada)"
            )
            return

        division_origen_linda_esperada = DIVISIONES[division_origen_esperada_slug]
        if club.division != division_origen_linda_esperada:
            resumen["avisos"].append(
                f"{nombre!r}: se esperaba que estuviera en "
                f"{division_origen_linda_esperada!r} pero el registro dice "
                f"{club.division!r}. Se movió igual a "
                f"{DIVISIONES[division_destino_slug]!r}, pero esto puede indicar "
                f"una inconsistencia con el ClubRegistry (revisar antes de Etapa 5)."
            )

        # BUG ENCONTRADO Y CORREGIDO: LPF normaliza alias cortos
        # internamente (estadisticas_lpf.NORMALIZACION_NOMBRES, p.ej.
        # "Estudiantes" -> "Estudiantes de La Plata") cada vez que
        # EstadisticasLPF.cargar_datos_lpf() lee un fixture. Si un club
        # asciende a LPF con un alias corto sin desambiguar en el
        # origen de datos (ej. Estudiantes de Caseros llegando como
        # "Estudiantes" a secas), quedaba así en el registro; la
        # temporada siguiente, cargar_datos_lpf() lo renombraba por su
        # cuenta al cargar el fixture recién generado -- fusionándolo
        # por accidente con el Estudiantes de La Plata real (mismo
        # nombre final, dos clubes distintos) y duplicando sus
        # partidos en el fixture (detectado con la validación de
        # "todos deben tener la misma cantidad de partidos"). Se
        # aplica la MISMA normalización acá, en el momento del
        # ascenso, para que el registro y el fixture generado ya
        # queden con el nombre completo -- si el nombre normalizado
        # ya pertenece a OTRO club, renombrar_club() corta con un
        # ValueError explícito en vez de dejar que la colisión se
        # filtre en silencio hasta la ronda siguiente.
        nombre_final = nombre
        if division_destino_slug == "lpf":
            from modelos.estadisticas_lpf import normalizar as _normalizar_lpf
            nombre_final = _normalizar_lpf(nombre)
            if nombre_final != nombre:
                club_registry.renombrar_club(nombre, nombre_final)

        club.division = DIVISIONES[division_destino_slug]
        resumen["movimientos"].append({
            "club": nombre_final,
            "origen": division_origen_esperada_slug,
            "destino": division_destino_slug,
            "motivo": "ascenso" if _es_ascenso(division_origen_esperada_slug, division_destino_slug) else "descenso",
        })

    def _retirar_club(self, club_registry, nombre: str, resumen: dict,
                       reincorporar_al_pool: bool = False) -> None:
        club = club_registry.get_by_name(nombre)
        if club is None:
            resumen["avisos"].append(
                f"Club no encontrado en el registro al intentar retirarlo: {nombre!r}"
            )
            return
        division_previa = club.division
        club_registry.retirar_club(nombre)
        resumen["movimientos"].append({
            "club": nombre,
            "origen": division_previa,
            "destino": None,
            "motivo": "descenso_fuera_del_sistema (Reválida Federal A, torneo regional no simulado)",
        })
        if reincorporar_al_pool:
            # Se va al final de la cola (no al principio): en la misma
            # ronda en la que baja no debería volver a subir de
            # casualidad -- primero se prueban los candidatos que ya
            # estaban esperando en el pool. Ver POOL_ASCENSO_REGIONAL
            # y _elegir_club_relleno().
            self._pool_restante.append(nombre)

    def _elegir_club_relleno(self, club_registry, temporada_destino: str) -> tuple[str, bool]:
        """Elige el próximo club para reponer un cupo de Federal A.
        Recorre self._pool_restante en orden (sin repetir mientras
        haya otros disponibles) y descarta cualquier candidato que ya
        esté en el ClubRegistry (por si en algún momento ya se agregó
        antes por otra vía) probando con el siguiente. Si el pool se
        agota, cae al nombre ficticio de siempre como respaldo, sin
        romper. Devuelve (nombre, es_del_pool)."""
        while self._pool_restante:
            candidato = self._pool_restante.pop(0)
            if club_registry.get_by_name(candidato) is None:
                return candidato, True
            # ya está en el registro -- se descarta, se prueba el que sigue
        return self._generar_nombre_relleno_ficticio(temporada_destino), False

    def _generar_nombre_relleno_ficticio(self, temporada_destino: str) -> str:
        self._contador_relleno += 1
        return f"Ingreso Regional {temporada_destino}-{self._contador_relleno}"


# Orden de nivel de división (en SLUGS), solo para decidir si un
# movimiento es "ascenso" o "descenso" al armar el resumen (no tiene
# otro uso, no se compara contra club.division real).
_ORDEN_DIVISION = {"lpf": 4, "nacional": 3, "bmetro": 2, "federal_a": 2, "primerac": 1}


def _es_ascenso(origen_slug: str, destino_slug: str) -> bool:
    return _ORDEN_DIVISION.get(destino_slug, 0) > _ORDEN_DIVISION.get(origen_slug, 0)
