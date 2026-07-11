# -*- coding: utf-8 -*-
"""
season/history_manager.py

Etapa 6 del plan (ver PLAN_MODO_TEMPORADA_NACIONAL.txt): HistoryManager
toma el ClubRegistry YA ACTUALIZADO por PromotionManager (con las
divisiones nuevas de cada club, ver season_engine.correr_temporada(...,
aplicar_promocion=True)) y:

  1. Crea/activa la temporada N+1 en la DB (ensure_competition_season()
     parametrizado -- ver repository.py, este mismo trabajo detectó que
     estaba hardcodeado a "2026" y lo rompía).
  2. Arma la tabla de posiciones "en cero" (0 partidos jugados) de la
     temporada nueva, con las zonas sorteadas al azar (decisión del
     usuario -- no hay reparto por afiliación/cabezas de serie todavía).
     EXCEPCIÓN: LPF (ver PLAN_ADDENDUM_ETAPA6_APERTURA_LPF) -- la tabla
     no arranca en cero, arranca con el Apertura de esa temporada YA
     SIMULADO (zonas A/B, todos contra todos + playoffs cruzados, igual
     formato que el Clausura), con ratings iniciales combinando la
     Tabla Anual de la temporada que termina (clubes que continúan) y
     RatingCarryoverPolicy sobre los ratings finales de Nacional
     (ascendidos). El Clausura de esa misma temporada comparte la
     MISMA zona que el Apertura recién simulado.
  3. Genera el fixture de ida y vuelta con fixture_generator.py y lo
     persiste como partidos "pending" (repo.replace_matches()). Para
     LPF, este fixture es el del CLAUSURA (el Apertura ya se simuló
     completo en el paso 2, no queda pendiente).
  4. Agrega una entrada a Club.history por cada club, con la temporada
     ANTERIOR (de dónde viene) -- no la nueva, que todavía no jugó
     nada -- y, si está disponible, sus ratings finales ahí (Fase 0
     de HANDOFF_carryover_ratings.md; ver _actualizar_history() más
     abajo y season/rating_carryover.py).
  5. Para LPF, además persiste el campeón del Apertura recién simulado
     vía data_access.guardar_campeon_apertura_lpf() (key
     "lpf_campeon_apertura" en simulation_outputs) -- lo consume
     EstadisticasLPF.CAMPEON_APERTURA (ver estadisticas_lpf.py) para el
     Trofeo de Campeones y los cupos a copas de la temporada siguiente.

--------------------------------------------------------------------
ALCANCE: LAS 5 DIVISIONES CON FIXTURE DE LIGA POR ZONAS
--------------------------------------------------------------------
Cubre nacional, lpf, bmetro, primerac y federal_a. Para Federal A
sólo se genera la PRIMERA FASE (4 zonas, round-robin ida y vuelta,
mismo generador genérico que las demás divisiones -- confirmado
contra fixture_federal_a.csv real: 37 clubes en zonas de 9/10,
18 jornadas = 2×9, o sea rueda doble). La Segunda Fase, el camino
principal de eliminación directa y la Reválida (6 etapas, ver
season/adapters/federal_adapter.py) NO se persisten acá -- se
calculan en vivo durante la simulación de la temporada, igual que ya
pasa con los playoffs de las otras divisiones. Copa Argentina sigue
sin entrar: su "fixture" es un sorteo de cuadro con invitados de
varias categorías, no una liga con zonas.

--------------------------------------------------------------------
ZONAS: SORTEO AL AZAR (decisión del usuario, Etapa 6)
--------------------------------------------------------------------
A diferencia de geografia_clubes.py (que resuelve destino de DIVISIÓN
por afiliación real), acá el usuario pidió explícitamente que el
reparto de ZONA dentro de una misma división (A/B) sea al azar cada
temporada, sin ningún criterio geográfico ni de cabezas de serie. Con
cantidad impar de clubes, la zona A se lleva el que sobra (misma
convención que ya usa BMetro con su "Unica", no afecta acá porque acá
sí hay 2 zonas parejas en los 3 casos reales del proyecto).

Federal A es el mismo criterio (sorteo al azar, sin geografía ni
cabezas de serie) pero a 4 zonas en vez de 2 -- ver _sortear_zonas_n()
más abajo, generalización de _sortear_zonas() para N zonas parejas
(con 37 clubes no repartidos exactos entre 4, el resto se lleva un
club extra en las primeras zonas, "1", "2", ... en ese orden).

--------------------------------------------------------------------
LO QUE ESTE MÓDULO *NO* HACE TODAVÍA
--------------------------------------------------------------------
- No corre goleadores_*.csv ni resetea scorer_totals (arranca la
  temporada sin goleadores acumulados, que es lo correcto).
- No toca Copa Argentina.
- No resetea lpf_average_history -- ese historial es justamente
  ACUMULATIVO entre temporadas (ver estadisticas_lpf.py), no se debe
  tocar acá.
- No decide qué pasa si `persist_season()` se llama dos veces para la
  misma `temporada_siguiente` -- hoy es re-entrante en standings/matches
  (ON CONFLICT DO UPDATE), pero Club.history quedaría con una entrada
  duplicada. Si hace falta re-correr, es responsabilidad de quien llama
  no invocarlo dos veces para la misma temporada, o limpiar
  club.history a mano antes de reintentar.
"""
from __future__ import annotations

import random
from typing import Optional

import pandas as pd

import data_access
from season.club_registry import ClubRegistry, DIVISIONES
from season.rating_carryover import RatingCarryoverPolicy, combinar_con_memoria
from fixture_generator import generar_fixture_ida_vuelta, generar_fixture_una_rueda
from modelos.estadisticas_lpf import EstadisticasLPF

# slug interno -> nombre lindo de división (mismo diccionario que ya
# usa ClubRegistry, no se duplica).
SLUG_A_DIVISION = DIVISIONES  # {"lpf": "Liga Profesional", ...}

# Divisiones con 2 zonas parejas (A/B). BMetro NO entra acá -- es tabla
# única, ver ZONA_UNICA_SLUGS más abajo.
DIVISIONES_DOS_ZONAS = ("nacional", "lpf", "primerac")

# Divisiones de zona única (el "truco" de poner a todos en "Unica" que
# ya usa estadisticas_bmetro.py -- se respeta el mismo nombre de zona).
DIVISIONES_ZONA_UNICA = ("bmetro",)

# Federal A: Primera Fase se juega en 4 zonas (confirmado contra
# fixture_federal_a.csv real -- 37 clubes en zonas de 9/10, ver
# docstring del módulo). Va aparte de DIVISIONES_DOS_ZONAS porque el
# resto del código (ej. _sortear_zonas) asume 2 zonas A/B a mano.
DIVISIONES_CUATRO_ZONAS = ("federal_a",)

SLUGS_CUBIERTOS = DIVISIONES_DOS_ZONAS + DIVISIONES_ZONA_UNICA + DIVISIONES_CUATRO_ZONAS


def _sortear_zonas(clubes: list[str], rng: random.Random) -> dict[str, str]:
    """Reparte `clubes` al azar en dos zonas A/B lo más parejas posible
    (si es impar, A se lleva uno más). Devuelve {nombre_club: "A"|"B"}."""
    mezclados = list(clubes)
    rng.shuffle(mezclados)
    mitad = (len(mezclados) + 1) // 2
    return {nombre: "A" for nombre in mezclados[:mitad]} | {
        nombre: "B" for nombre in mezclados[mitad:]
    }


def _sortear_zonas_n(clubes: list[str], n: int, rng: random.Random) -> dict[str, str]:
    """Generalización de _sortear_zonas a N zonas parejas (hace falta
    para Federal A, Primera Fase a 4 zonas -- ver docstring del
    módulo). Reparte `clubes` al azar lo más parejo posible entre `n`
    zonas etiquetadas "1".."n"; si no hay reparto exacto, el resto se
    lleva un club extra cada una, empezando por la zona "1" (mismo
    criterio que _sortear_zonas usa para el que sobra en 2 zonas).
    Devuelve {nombre_club: "1"|"2"|...|str(n)}."""
    mezclados = list(clubes)
    rng.shuffle(mezclados)
    base, resto = divmod(len(mezclados), n)
    zona_por_club: dict[str, str] = {}
    idx = 0
    for i in range(n):
        tamanio_zona = base + (1 if i < resto else 0)
        etiqueta = str(i + 1)
        for _ in range(tamanio_zona):
            zona_por_club[mezclados[idx]] = etiqueta
            idx += 1
    return zona_por_club


def _armar_standings_en_cero(zona_por_club: dict[str, str]) -> list[dict]:
    """Fila de standings "recién arrancada" para cada club: 0 partidos,
    0 puntos, posición 1..N dentro de su zona (orden alfabético --
    sin partidos jugados no hay ningún criterio deportivo para
    ordenar, así que se usa uno estable y determinístico)."""
    filas = []
    for zona in sorted(set(zona_por_club.values())):
        clubes_zona = sorted(n for n, z in zona_por_club.items() if z == zona)
        for posicion, nombre in enumerate(clubes_zona, start=1):
            filas.append({
                "zona": zona,
                "posicion": posicion,
                "equipo": nombre,
                "partidos_jugados": 0,
                "ganados": 0,
                "empatados": 0,
                "perdidos": 0,
                "gf": 0,
                "gc": 0,
                "dg": 0,
                "puntos": 0,
            })
    return filas


def _armar_fixture_pendiente(zona_por_club: dict[str, str], ida_y_vuelta: bool = True) -> list[dict]:
    """Fixture DENTRO de cada zona (no hay cruces de zona en la fase
    regular de ninguna de las 4 divisiones cubiertas). Devuelve filas
    en el shape que espera repo.replace_matches()/MATCH_COLUMNS:
    fecha/jornada/equipo_local/equipo_visitante, sin goles (pending).

    ida_y_vuelta=True (default): rueda doble -- Nacional/BMetro/
    Primera C juegan la fase regular completa a ida y vuelta, mismo
    formato real. ida_y_vuelta=False: rueda simple -- el Clausura de
    LPF es más corto que la fase regular de las otras 3 (BUG
    ENCONTRADO: antes esta función siempre generaba ida y vuelta
    también para LPF -- 28 partidos por equipo en vez de los 16 reales
    del Clausura -- lo que hacía que _validar_datos_lpf() rechazara el
    fixture recién generado apenas se intentaba simular esa temporada;
    no se había notado porque nadie había llegado a simular DOS
    temporadas seguidas todavía)."""
    filas = []
    generador = generar_fixture_ida_vuelta if ida_y_vuelta else generar_fixture_una_rueda
    for zona in sorted(set(zona_por_club.values())):
        clubes_zona = sorted(n for n, z in zona_por_club.items() if z == zona)
        partidos = generador(clubes_zona)
        for p in partidos:
            filas.append({
                "fecha": "",
                "jornada": p.jornada,
                "equipo_local": p.equipo_local,
                "equipo_visitante": p.equipo_visitante,
            })
    return filas


class HistoryManager:
    """Persiste la temporada N+1 (standings en cero + fixture) para las
    5 divisiones de liga por zonas (para Federal A, sólo la Primera
    Fase -- ver docstring del módulo), y registra en Club.history de
    dónde viene cada club. Ver docstring del módulo para el alcance
    exacto (no cubre Copa Argentina)."""

    def __init__(self, repo=None, rng: Optional[random.Random] = None,
                 guardar_campeon_apertura=None):
        # repo inyectable para poder testear con un mock/fake en vez de
        # la DB real (mismo patrón que rng en PromotionManager).
        self._repo = repo
        self._rng = rng or random.Random()
        # ADDENDUM v13 (hallazgo de diseño del v12, resuelto): antes,
        # persist_season() llamaba SIEMPRE a
        # data_access.guardar_campeon_apertura_lpf(), que pega contra
        # el singleton global db.repository.repository() -- sin
        # importar qué `repo` se haya inyectado acá. Si alguien
        # inyectaba un repo custom (tests, staging) sin también
        # parchear el singleton global a mano (como hizo el smoke
        # test del addendum v12), el campeón del Apertura terminaba
        # guardado en un repo distinto del resto de persist_season().
        #
        # Ahora es inyectable, mismo patrón que `repo`: si no se pasa
        # nada, el default sigue siendo data_access.guardar_campeon_
        # apertura_lpf() (comportamiento IDÉNTICO al de antes, cero
        # cambio para quien no inyecta nada). Si se inyecta un `repo`
        # custom, quien llama debe inyectar TAMBIÉN un
        # `guardar_campeon_apertura` que pegue contra ESE mismo repo
        # (ej. `lambda campeon: mi_repo.guardar_campeon_apertura_lpf(campeon)`
        # si el repo custom expone ese método, o cualquier callable
        # equivalente) -- de lo contrario, sigue yendo al singleton
        # global, pero ahora es una decisión EXPLÍCITA de quien
        # instancia HistoryManager, no un bug escondido.
        self._guardar_campeon_apertura = (
            guardar_campeon_apertura or data_access.guardar_campeon_apertura_lpf
        )

    def _get_repo(self):
        if self._repo is not None:
            return self._repo
        from db.repository import repository
        return repository()

    def persist_season(
        self,
        club_registry: ClubRegistry,
        temporada_actual: str,
        temporada_siguiente: str,
        resultados: Optional[dict] = None,
    ) -> dict:
        """
        club_registry: el registro YA promocionado (después de
            PromotionManager.aplicar()) -- club.division ya refleja
            ascensos/descensos/altas/bajas de Federal A.
        temporada_actual: string de la temporada que termina (ej.
            "2026") -- se usa solo para la entrada de Club.history, no
            se toca ningún dato de esa temporada en la DB.
        temporada_siguiente: string de la temporada que arranca (ej.
            "2027") -- nombre que va a `seasons.name`.
        resultados: dict[str, ResultadoTorneo] con las corridas de la
            temporada QUE TERMINA (la salida de
            SeasonEngine._correr_competencias(), o equivalente armado a
            mano) -- SOLO hace falta para la rama especial de LPF (ver
            PLAN_ADDENDUM_ETAPA6_APERTURA_LPF): se leen
            resultados["lpf"].datos_crudos["tabla_anual"] (Tabla Anual
            de la temporada que termina, para los clubes que continúan
            en LPF) y resultados["nacional"].ratings_finales (para los
            ascendidos vía RatingCarryoverPolicy). Si el roster de LPF
            de la temporada siguiente no está vacío y `resultados` es
            None (o no trae "lpf"), levanta ValueError -- mejor fallar
            fuerte que persistir standings en cero para LPF sin que
            nadie note que el Apertura no se simuló.
            nacional/bmetro/primerac/federal_a NO usan este parámetro
            (siguen con standings en cero + fixture simple, sin
            cambios; para federal_a, "fixture simple" es la Primera
            Fase a 4 zonas -- ver docstring del módulo).

        Devuelve un resumen: {slug: {"clubes": N, "partidos": M,
        "zonas": {"A": [...], "B": [...]}}} por cada división cubierta
        (para federal_a, "zonas" usa las etiquetas "1".."4"), más
        "clubes_sin_persistir" con lo que quedó afuera (Copa Argentina
        y cualquier división no reconocida). Para "lpf" además incluye
        "campeon_apertura" con el campeón recién simulado.
        """
        repo = self._get_repo()
        resumen = {"divisiones": {}, "no_cubiertas": []}

        for slug, nombre_division in SLUG_A_DIVISION.items():
            if slug not in SLUGS_CUBIERTOS:
                resumen["no_cubiertas"].append(slug)
                continue

            clubes = [c.name for c in club_registry.get_by_division(nombre_division)]
            if not clubes:
                resumen["divisiones"][slug] = {"clubes": 0, "partidos": 0, "zonas": {}}
                continue

            if slug in DIVISIONES_ZONA_UNICA:
                zona_por_club = {nombre: "Unica" for nombre in clubes}
            elif slug in DIVISIONES_CUATRO_ZONAS:
                zona_por_club = _sortear_zonas_n(clubes, 4, self._rng)
            else:
                zona_por_club = _sortear_zonas(clubes, self._rng)

            campeon_apertura = None
            if slug == "lpf":
                if not resultados or "lpf" not in resultados:
                    raise ValueError(
                        "persist_season() necesita 'resultados[\"lpf\"]' (la corrida "
                        "de LPF de la temporada que termina) para simular el Apertura "
                        "siguiente -- ver PLAN_ADDENDUM_ETAPA6_APERTURA_LPF."
                    )
                standings, campeon_apertura = self._simular_apertura_lpf(
                    clubes, zona_por_club, resultados, club_registry
                )
                # el Clausura de esta misma temporada comparte zona con
                # el Apertura recién simulado (decisión 1 del addendum).
                # Rueda SIMPLE -- el Clausura real es más corto que la
                # fase regular completa de las otras 3 divisiones (ver
                # el comentario de _armar_fixture_pendiente()).
                fixture = _armar_fixture_pendiente(zona_por_club, ida_y_vuelta=False)
            else:
                standings = _armar_standings_en_cero(zona_por_club)
                fixture = _armar_fixture_pendiente(zona_por_club)

            repo.ensure_competition_season(slug, season=temporada_siguiente)
            repo.upsert_standings(slug, standings)
            repo.replace_matches(slug, pending=fixture, played=[])

            if slug == "lpf":
                # antes: data_access.guardar_campeon_apertura_lpf(...)
                # directo, bypasseando self._repo -- ver ADDENDUM v13
                # en __init__.
                self._guardar_campeon_apertura(campeon_apertura)

            zonas_resumen: dict[str, list[str]] = {}
            for nombre, zona in zona_por_club.items():
                zonas_resumen.setdefault(zona, []).append(nombre)
            for lista in zonas_resumen.values():
                lista.sort()

            entrada_resumen = {
                "clubes": len(clubes),
                "partidos": len(fixture),
                "zonas": zonas_resumen,
            }
            if slug == "lpf":
                entrada_resumen["campeon_apertura"] = campeon_apertura
            resumen["divisiones"][slug] = entrada_resumen

        self._actualizar_history(club_registry, temporada_actual, resultados)

        return resumen

    def _simular_apertura_lpf(
        self, roster: list[str], zona_por_club: dict[str, str], resultados: dict,
        club_registry: ClubRegistry,
    ) -> tuple[list[dict], str]:
        """Arma los ratings iniciales del Apertura siguiente (decisión 2
        del addendum, + memoria EWMA/handicap de Fase 0 -- ver
        _ratings_iniciales_lpf()) y corre EstadisticasLPF.simular_apertura_desde_carryover().
        Devuelve (standings_flat, campeon) -- standings_flat es una
        lista plana (zonas A+B juntas) en shape STANDING_COLUMNS, lista
        para repo.upsert_standings("lpf", ...)."""
        ratings_iniciales = self._ratings_iniciales_lpf(resultados, roster, club_registry)
        tabla_por_zona, campeon = EstadisticasLPF().simular_apertura_desde_carryover(
            roster, zona_por_club, ratings_iniciales
        )
        standings_flat: list[dict] = []
        for filas_zona in tabla_por_zona.values():
            standings_flat.extend(filas_zona)
        return standings_flat, campeon

    def _ratings_iniciales_lpf(
        self, resultados: dict, roster_siguiente: list[str], club_registry: ClubRegistry,
    ) -> dict:
        """Combina las dos fuentes de ratings iniciales (decisión 2 del
        PLAN_ADDENDUM_ETAPA6_APERTURA_LPF), y ahora además la memoria
        multi-temporada de la Fase 0 (HANDOFF_carryover_ratings.md):
          a) clubes que YA estaban en LPF: ratings_desde_tabla_anual()
             sobre la Tabla Anual + zona de la temporada que termina
             (resultados["lpf"].datos_crudos["tabla_anual"] / ["apertura"]
             -- claves confirmadas en la Etapa 2 del plan, validada
             contra Supabase real). ESE rating "crudo" de la temporada
             que termina se combina con combinar_con_memoria()
             (season/rating_carryover.py): mezcla EWMA con las
             temporadas anteriores del club EN LPF (Club.history) y,
             si el club todavía está en sus primeras
             N_TEMPORADAS_HANDICAP temporadas ahí (un ascendido
             reciente jugando su 2da/3ra temporada), aplica el
             handicap de adaptación que se va disolviendo. Si el club
             no está en club_registry (no debería pasar para el
             roster de LPF, pero se degrada con gracia) se usa el
             rating crudo sin combinar.
          b) clubes recién ascendidos desde Nacional:
             RatingCarryoverPolicy.rating_para_recien_llegado() usando
             resultados["nacional"].ratings_finales (si existe esa
             entrada -- si "nacional" no viene en `resultados`, o el
             club no está en su ratings_finales todavía porque
             main.py/nacional_adapter.py no llenan ese campo, se cae al
             rating GENÉRICO de la política, degradando con gracia en
             vez de romper). El handicap de la temporada 1 en destino
             YA está adentro de rating_para_recien_llegado() (Fase 0),
             no hace falta aplicarlo acá de nuevo."""
        resultado_lpf = resultados["lpf"]
        # BUG ENCONTRADO Y CORREGIDO acá (confirmado leyendo main_lpf.py
        # real): datos_crudos["tabla_anual"] y ["apertura"] NO son los
        # DataFrames originales de calcular_tabla_anual()/self.apertura --
        # main_lpf.armar_datos_web_lpf() los aplana para JSON antes de
        # meterlos en datos_web (_tabla_a_lista() -> list[dict];
        # _apertura_a_zonas() -> {"A": [...], "B": [...]}). Como
        # ResultadoTorneo.datos_crudos = datos_web tal cual (ver
        # LPFAdapter.result()), acá llegan ya aplanados.
        # ratings_desde_tabla_anual() (estadisticas_lpf.py) exige un
        # DataFrame real (usa .isin()/indexing por columna) y un dict
        # plano {equipo: zona} -- NO se puede llamar .set_index() sobre
        # un dict, por eso se reconstruyen los dos acá antes de llamarla.
        tabla_anual = pd.DataFrame(resultado_lpf.datos_crudos["tabla_anual"])
        apertura_actual = resultado_lpf.datos_crudos["apertura"]
        zona_por_club_actual = {
            fila["equipo"]: zona
            for zona, filas in apertura_actual.items()
            for fila in filas
        }

        ratings_continuan = EstadisticasLPF().ratings_desde_tabla_anual(
            tabla_anual, zona_por_club_actual
        )

        resultado_nacional = resultados.get("nacional")
        ratings_finales_nacional = (
            resultado_nacional.ratings_finales if resultado_nacional is not None else {}
        )
        politica = RatingCarryoverPolicy()

        ratings: dict[str, dict] = {}
        for club in roster_siguiente:
            if club in ratings_continuan:
                rating_crudo = ratings_continuan[club]
                club_obj = club_registry.get_by_name(club)
                ratings[club] = (
                    combinar_con_memoria(rating_crudo, club_obj, "lpf")
                    if club_obj is not None
                    else rating_crudo
                )
                continue
            ratings_origen = ratings_finales_nacional.get(club)
            ratings[club] = politica.rating_para_recien_llegado(
                ratings_origen,
                "nacional" if ratings_origen is not None else None,
                "lpf",
            )
        return ratings

    def _resolver_temporada_saliente(
        self, resultados: Optional[dict]
    ) -> tuple[dict[str, dict], dict[str, str]]:
        """A partir de `resultados` (dict slug->ResultadoTorneo de la
        temporada QUE TERMINA), arma dos mapas name->valor: ratings
        finales (de ResultadoTorneo.ratings_finales, campo aditivo que
        hoy llenan lpf/nacional/bmetro/primerac -- ver
        season/tournament_adapter.py) y división "linda" REALMENTE
        jugada esa temporada (derivada del mismo slug, no de
        club.division -- ver Fase 0 en _actualizar_history()).
        Ninguno de los dos mapas incluye clubes de Federal A
        (ratings_finales vacío ahí a propósito) ni nada si
        `resultados` es None (llamada sin ese dato -- degrada con
        gracia)."""
        ratings_por_club: dict[str, dict] = {}
        division_por_club: dict[str, str] = {}
        if not resultados:
            return ratings_por_club, division_por_club
        for slug, nombre_division in SLUG_A_DIVISION.items():
            resultado = resultados.get(slug)
            if resultado is None:
                continue
            for nombre_club, ratings in (resultado.ratings_finales or {}).items():
                ratings_por_club[nombre_club] = ratings
                division_por_club[nombre_club] = nombre_division
        return ratings_por_club, division_por_club

    def _actualizar_history(
        self,
        club_registry: ClubRegistry,
        temporada_actual: str,
        resultados: Optional[dict] = None,
    ) -> None:
        """Agrega una entrada por club con la división en la que jugó
        la temporada que termina y, si está disponible, sus ratings
        finales ahí (Fase 0 de HANDOFF_carryover_ratings.md -- ver
        season/rating_carryover.py: memoria_ewma() y
        temporadas_consecutivas_en_division() consumen esto). No toca
        la DB -- Club.history vive en memoria sobre el objeto Club
        (ver modelos/club.py).

        BUG ENCONTRADO Y CORREGIDO acá: la versión anterior guardaba
        club.division tal cual al momento de llamar a este método --
        pero persist_season() recibe el club_registry YA MUTADO por
        PromotionManager (ver docstring de la clase más arriba), o
        sea que en ese punto club.division es la división de DESTINO
        (temporada_siguiente), no la que el club jugó en
        `temporada_actual`. El docstring de este método siempre dijo
        la intención correcta ("la división en la que jugó la
        temporada que termina"); el código no la cumplía. No se había
        notado porque nada consumía Club.history todavía. Ahora se
        resuelve la división REALMENTE jugada vía
        _resolver_temporada_saliente() (misma fuente que los ratings:
        ResultadoTorneo.ratings_finales por slug). Si no se puede
        determinar (resultados=None, club sin ratings_finales en
        ningún lado, o Federal A -- que no llena ese campo a
        propósito) se cae a club.division actual, mismo comportamiento
        que antes."""
        ratings_por_club, division_por_club = self._resolver_temporada_saliente(resultados)

        for club in club_registry.all_clubs():
            entrada = {
                "temporada": temporada_actual,
                "division": division_por_club.get(club.name, club.division),
            }
            ratings = ratings_por_club.get(club.name)
            if ratings is not None:
                entrada["ratings"] = ratings
            club.history.append(entrada)
