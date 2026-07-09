# -*- coding: utf-8 -*-
"""
estadisticas_federal.py

Motor de simulación del Torneo Federal A 2026, según el Reglamento oficial
(37 clubes, 4 zonas, 5 Fases + Reválida paralela de 6 Etapas). Hereda de
Estadisticas (modelos/estadisticas.py) y reutiliza su infraestructura
genérica: ratings Poisson (calcular_ratings), tablas por zona
(simular_fase_regular/_armar_tabla_final, ya genéricas sobre N zonas) y
series a partido único o ida-y-vuelta (jugar_partido_unico,
jugar_serie_ida_vuelta).

Simplificaciones documentadas respecto de la letra del Reglamento (Art.
12/12.1/12.2/12.3), consistentes con las que ya usan Nacional/LPF/B Metro:
  - Los desempates usan siempre (puntos ->) diferencia de gol -> goles a
    favor. Se omite el criterio de "goles a favor como visitante" (Art.
    12.3 y Notas 1) porque implicaría trackear goles local/visitante por
    equipo a través de CADA simulación de Monte Carlo, no solo en los
    resultados reales ya jugados -- el resto del proyecto tampoco lo hace.
  - Para una serie a dos partidos entre dos equipos, "empatados en puntos
    y en diferencia de gol" es matemáticamente equivalente a "empatados
    en gol diferencia agregada" (la diferencia de un lado es siempre el
    negativo de la del otro), así que el desempate por puntos+dg de la
    serie se resuelve comparando directamente el marcador agregado de los
    dos partidos.
  - No se arma la mini-tabla "solo entre los equipos empatados" del Art.
    12 antes de ir a la tabla general (mismo criterio que ya usan las
    otras 4 ligas del proyecto).

Cuando el reglamento requiere desempatar por sorteo (Nota 2 de la
Reválida, o el "mejor quinto" en último extremo), se usa un sorteo
determinístico basado en un hash de los nombres -- misma corrida siempre
da el mismo resultado, para que las simulaciones sean reproducibles.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import data_access
import rutas
from modelos.estadisticas import Estadisticas

ZONAS_PRIMERA_FASE = ("1", "2", "3", "4")
ZONA_DIEZ = "1"  # única zona de 10 clubes; las demás (2, 3, 4) son de 9
CLASIFICAN_ZONA_DIEZ = 5
CLASIFICAN_ZONA_NUEVE = 4
DESCENSOS_POR_ZONA_REVALIDA = 2  # 2 en Zona A + 2 en Zona B = 4 total (Art. 2.2)


def _sorteo_deterministico(opciones: list[str], semilla_extra: str) -> str:
    """Sorteo reproducible: mismo listado de opciones + misma semilla
    siempre elige lo mismo. Se usa solo en los desempates de último
    recurso que el propio Reglamento resuelve por sorteo real."""
    texto = semilla_extra + "|" + "|".join(sorted(opciones))
    digest = hashlib.sha256(texto.encode("utf-8")).hexdigest()
    indice = int(digest, 16) % len(opciones)
    return sorted(opciones)[indice]


@dataclass
class ResultadoSerie:
    """Resultado de una llave a partido único o ida-y-vuelta. `detalle`
    es el dict con forma web que ya devuelven jugar_partido_unico() /
    jugar_serie_ida_vuelta() (se reexpone tal cual para el frontend)."""
    ganador: str
    perdedor: str
    detalle: dict


@dataclass
class ResultadoFase:
    """Snapshot de una fase de grupos ya simulada: tablas por zona más
    quién avanza a cada destino posible."""
    tablas: dict[str, pd.DataFrame]
    avanzan: dict[str, list[str]] = field(default_factory=dict)


class EstadisticasFederal(Estadisticas):
    """Simula el Torneo Federal A completo: Primera Fase (4 zonas) ->
    Segunda Fase (2 zonas) -> Tercera/Cuarta/Quinta Fase (llaves de
    eliminación directa, 1° ascenso) en paralelo con la Reválida
    (Primera a Sexta Etapa, 2° ascenso + los 4 descensos)."""

    # ------------------------------------------------------------------
    # Carga de datos
    # ------------------------------------------------------------------
    def cargar_datos_federal(self) -> None:
        """Lee posiciones, fixture y resultados actuales del Federal A."""
        print("Leyendo datos de Federal A...")

        self.resultados, self.fixture, self.tabla = data_access.league_data("federal_a")
        self.tabla["zona"] = self.tabla["zona"].astype(str)
        # dtype explícito: con 0 filas (antes del primer resultado real
        # cargado por el scraper) pandas no tiene de dónde inferir que
        # 'jornada'/goles son numéricas y las deja como object.
        for col in ("jornada", "goles_local", "goles_visitante"):
            if col in self.resultados.columns and not self.resultados.empty:
                self.resultados[col] = self.resultados[col].astype("int64")

        self.validar_datos()
        print(f"Clubes: {len(self.tabla)} | Fixture Primera Fase: {len(self.fixture)} partidos")

        # Snapshot de Primera Fase (zonas 1-4 + fixture), para poder
        # restaurar el estado antes de cada corrida completa del torneo
        # (correr_simulacion_federal() reutiliza el mismo objeto `e` para
        # el Monte Carlo, y cada fase pisa equipo.zona/self.fixture).
        self._zonas_primera_fase = {nombre: fila["zona"] for nombre, fila in
                                     self.tabla.set_index("equipo").iterrows()}
        self._totales_primera_fase = {
            fila["equipo"]: {
                "puntos": int(fila["puntos"]),
                "gf": int(fila["gf"]),
                "gc": int(fila["gc"]),
            }
            for _, fila in self.tabla.iterrows()
        }
        self._fixture_primera_fase = self.fixture.copy()

        # Snapshot de los puntos/gf/gc REALES de la Primera Fase (los que
        # ya salieron de partidos jugados, según tabla_federal_a.csv).
        # reiniciar_para_nueva_corrida() debe restaurar ESTOS valores
        # antes de simular_primera_fase(), no ponerlos en cero -- cero
        # es correcto para el arranque de la Segunda Fase y de la
        # Reválida (que sí empiezan la tabla desde cero por reglamento,
        # Art. 11), pero la Primera Fase arranca desde lo ya jugado.
        self._puntajes_primera_fase = {
            nombre: {"puntos": int(fila["puntos"]), "gf": int(fila["gf"]), "gc": int(fila["gc"])}
            for nombre, fila in self.tabla.set_index("equipo").iterrows()
        }

    def reiniciar_para_nueva_corrida(self) -> None:
        """Restaura zonas (1-4), fixture y puntajes al estado de arranque
        de la Primera Fase. Hay que llamarlo antes de cada corrida
        completa del torneo cuando se reutiliza la misma instancia (p.
        ej. cada repetición del Monte Carlo)."""
        self._asignar_zonas(self._zonas_primera_fase)
        self._restaurar_puntajes_primera_fase()
        self._reset_fixture(self._fixture_primera_fase)

    def crear_equipos_federal(self) -> None:
        """Delegado a crear_equipos() (genérico, ya lee self.tabla con
        cualquier etiqueta de zona)."""
        self.crear_equipos()

    def _reset_fixture(self, nuevo_fixture: pd.DataFrame) -> None:
        """Reemplaza self.fixture e invalida el cache de _pares_fixture(),
        que si no seguiría devolviendo los partidos de la fase anterior."""
        self.fixture = nuevo_fixture.reset_index(drop=True)
        self._pares_fixture_cache = None

    def _resetear_puntajes(self, equipos: list[str]) -> None:
        """Pone puntos/gf/gc en cero para los equipos indicados (cada
        fase de grupos del Federal A arranca 'con puntaje cero', Art.
        11). Los ratings de ataque/defensa NO se tocan: sí siguen
        reflejando la fuerza real de cada equipo."""
        for nombre in equipos:
            equipo = self.equipos[nombre]
            equipo.puntos = 0
            equipo.goles_favor = 0
            equipo.goles_contra = 0

    def _restaurar_puntajes_primera_fase(self) -> None:

        """Restaura puntos/gf/gc de TODOS los equipos a los valores
        reales de tabla_federal_a.csv (partidos ya jugados) -- a
        diferencia de _resetear_puntajes(), que los pone en cero. Se usa
        antes de simular_primera_fase(), porque esa fase NO arranca
        desde cero: ya viene con puntos de jornadas jugadas."""
        for nombre, valores in self._puntajes_primera_fase.items():
            equipo = self.equipos[nombre]
            equipo.puntos = valores["puntos"]
            equipo.goles_favor = valores["gf"]
            equipo.goles_contra = valores["gc"]
        """Restaura la tabla real vigente antes de simular los partidos
        pendientes de la Primera Fase. A diferencia de Segunda Fase y
        Reválida, la Primera Fase no arranca de cero en cada corrida:
        debe partir de datos/tabla_federal_a.csv y proyectar lo que falta."""
        for nombre, totales in self._totales_primera_fase.items():
            equipo = self.equipos[nombre]
            equipo.puntos = totales["puntos"]
            equipo.goles_favor = totales["gf"]
            equipo.goles_contra = totales["gc"]

    # ------------------------------------------------------------------
    # MONTE CARLO VECTORIZADO (Primera Fase, Segunda Fase y Reválida 1ª
    # Etapa -- las tres rondas de todos-contra-todos, que juntas son 153
    # de los ~231 partidos de una corrida completa). Reemplaza, para esas
    # tres fases, el bucle repetición-por-repetición (simular_partido()
    # llamado una vez por partido y por repetición) por UN solo bloque de
    # operaciones NumPy para las S repeticiones a la vez -- mismo modelo
    # matemático que simular_partido()/_simular_fase_regular_vectorizado()
    # de la clase base (Dixon-Coles + shock Gamma + muestreo acumulado),
    # solo que generalizado para que cada partido pueda tener un rating
    # DISTINTO por repetición (porque quién ocupa cada posición de la
    # Segunda Fase y de la Reválida varía según cómo termine la Primera
    # Fase en cada repetición).
    #
    # Las llaves de eliminación (Tercera Fase en adelante + toda la
    # Reválida de la Etapa 2 a la 6, ~65 partidos) siguen corriendo
    # repetición por repetición: dependen secuencialmente de quién ganó
    # cada cruce anterior, lo que las hace mucho más difíciles de
    # vectorizar y son una fracción menor del costo total.
    # ------------------------------------------------------------------
    @staticmethod
    def _rankear_zona_vectorizado(puntos: np.ndarray, gf: np.ndarray, gc: np.ndarray) -> np.ndarray:
        """puntos/gf/gc: arrays (n_equipos_zona, S). Devuelve (n_equipos_zona, S)
        con los ÍNDICES DENTRO DE LA ZONA ordenados de mejor a peor por
        columna (repetición), según puntos desc -> dg desc -> gf desc
        (mismo criterio que _armar_tabla_final, sin el criterio de goles
        de visitante -- misma simplificación documentada en el módulo).
        Combina los 3 criterios en una sola clave numérica para poder
        ordenar con un solo argsort vectorizado en vez de una comparación
        multi-criterio partido a partido."""
        dg = gf - gc
        compuesto = (puntos.astype(np.int64) * 100_000_000
                     + (dg.astype(np.int64) + 100_000) * 10_000
                     + gf.astype(np.int64))
        return np.argsort(-compuesto, axis=0, kind="stable")

    def _simular_ronda_slots_vectorizada(
        self,
        lambda_local_base: np.ndarray,
        lambda_visitante_base: np.ndarray,
        idx_local: np.ndarray,
        idx_visitante: np.ndarray,
        n_slots: int,
        S: int,
        mascara_partido: np.ndarray | None = None,
        max_elems_por_bloque: int = 8_000_000,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generaliza _simular_fase_regular_vectorizado() de la clase base
        para un round-robin de 'lugares' (slots) en vez de equipos fijos:
        cada slot puede estar ocupado por un equipo distinto en cada
        repetición (por eso lambda_local_base/lambda_visitante_base ya
        vienen con forma (n_partidos, S) -- el rating del equipo que
        ocupa cada lugar EN ESA repetición, resuelto por el llamador antes
        de invocar este método -- en vez de (n_partidos,) fijo).

        idx_local/idx_visitante: (n_partidos,) índices de slot (0..n_slots-1)
        que juegan cada partido de la ronda -- el FIXTURE de posiciones es
        el mismo para las S repeticiones, lo único que cambia es el rating.

        mascara_partido: (n_partidos, S) opcional, 1.0 si el partido cuenta
        en esa repetición y 0.0 si no (se usa para las zonas de la
        Reválida, que según la repetición tienen 9 o 10 equipos reales:
        el slot 'de más' se trata como comodín y sus partidos se
        descartan con la máscara en las repeticiones donde no aplica, sin
        tener que armar un fixture distinto por repetición).

        Devuelve (puntos, gf, gc), cada uno (n_slots, S)."""
        M = len(idx_local)
        k = self._RANGO_GOLES
        fact = self._FACTORIALES
        max_goles = self._MAX_GOLES
        n_marcadores = (max_goles + 1) * (max_goles + 1)

        puntos_tot = np.zeros((n_slots, S), dtype=np.int64)
        gf_tot = np.zeros((n_slots, S), dtype=np.int64)
        gc_tot = np.zeros((n_slots, S), dtype=np.int64)

        tanda = max(1, min(S, max_elems_por_bloque // max(1, M * n_marcadores)))
        RHO = -0.1
        K_SHOCK = self.K_SHOCK_PARTIDO

        for inicio in range(0, S, tanda):
            s = min(tanda, S - inicio)
            ll_base = lambda_local_base[:, inicio:inicio + s]
            lv_base = lambda_visitante_base[:, inicio:inicio + s]

            shock_local = np.random.gamma(shape=K_SHOCK, scale=1 / K_SHOCK, size=(M, s))
            shock_visitante = np.random.gamma(shape=K_SHOCK, scale=1 / K_SHOCK, size=(M, s))
            lambda_local = ll_base * shock_local
            lambda_visitante = lv_base * shock_visitante

            p_x = (lambda_local[..., None] ** k) * np.exp(-lambda_local)[..., None] / fact
            p_y = (lambda_visitante[..., None] ** k) * np.exp(-lambda_visitante)[..., None] / fact
            probs = p_x[..., :, None] * p_y[..., None, :]

            probs[..., 0, 0] *= 1 - lambda_local * lambda_visitante * RHO
            probs[..., 1, 0] *= 1 + lambda_visitante * RHO
            probs[..., 0, 1] *= 1 + lambda_local * RHO
            probs[..., 1, 1] *= 1 - RHO

            flat = probs.reshape(M, s, n_marcadores)
            flat = flat / flat.sum(axis=-1, keepdims=True)
            cumulativo = np.cumsum(flat, axis=-1)
            r = np.random.random((M, s, 1))
            idx_marcador = (cumulativo < r).sum(axis=-1)

            goles_local = idx_marcador // (max_goles + 1)
            goles_visitante = idx_marcador % (max_goles + 1)

            gana_local = goles_local > goles_visitante
            gana_visitante = goles_local < goles_visitante
            empate = ~gana_local & ~gana_visitante
            pts_local = np.where(gana_local, 3, np.where(empate, 1, 0))
            pts_visitante = np.where(gana_visitante, 3, np.where(empate, 1, 0))

            if mascara_partido is not None:
                m = mascara_partido[:, inicio:inicio + s]
                pts_local, pts_visitante = pts_local * m, pts_visitante * m
                goles_local, goles_visitante = goles_local * m, goles_visitante * m

            bloque_puntos = puntos_tot[:, inicio:inicio + s]
            bloque_gf = gf_tot[:, inicio:inicio + s]
            bloque_gc = gc_tot[:, inicio:inicio + s]
            np.add.at(bloque_puntos, idx_local, pts_local)
            np.add.at(bloque_puntos, idx_visitante, pts_visitante)
            np.add.at(bloque_gf, idx_local, goles_local)
            np.add.at(bloque_gf, idx_visitante, goles_visitante)
            np.add.at(bloque_gc, idx_local, goles_visitante)
            np.add.at(bloque_gc, idx_visitante, goles_local)

        return puntos_tot, gf_tot, gc_tot

    def simular_temporada_vectorizada(self, S: int) -> dict:
        """Corre Primera Fase + Segunda Fase + Reválida 1ª Etapa para las
        S repeticiones A LA VEZ (vectorizado; ver el bloque de arriba).
        Devuelve un dict con todo lo necesario para reconstruir, PARA
        CADA REPETICIÓN, las tablas de esas 3 fases en el mismo shape de
        DataFrame que devuelven simular_primera_fase()/
        simular_segunda_fase()/simular_revalida_primera_etapa() -- así
        clasificados_primera_fase()/clasificados_segunda_fase()/
        calcular_descensos() (y de ahí en adelante toda la cadena de
        llaves de eliminación) NO cambian ni una línea: siguen recibiendo
        exactamente las mismas tablas que antes, solo que ahora se
        construyen a partir de un array ya simulado en vez de volver a
        simular partido por partido en cada repetición.

        Usar junto con extraer_tablas_repeticion() (en main_federal.py)."""
        self.reiniciar_para_nueva_corrida()
        nombres = list(self.equipos.keys())
        idx_por_nombre = {n: i for i, n in enumerate(nombres)}

        totales_pf = self._simular_fase_regular_vectorizado(S)
        zonas = {z: [n for n in nombres if self.equipos[n].zona == z] for z in ZONAS_PRIMERA_FASE}
        idx_zona = {z: np.array([idx_por_nombre[n] for n in equipos]) for z, equipos in zonas.items()}

        puntos_pf, gf_pf, gc_pf = {}, {}, {}
        for z, equipos in zonas.items():
            puntos_pf[z] = np.stack([totales_pf[n]["puntos"] for n in equipos])
            gf_pf[z] = np.stack([totales_pf[n]["gf"] for n in equipos])
            gc_pf[z] = np.stack([totales_pf[n]["gc"] for n in equipos])
        orden_pf = {z: self._rankear_zona_vectorizado(puntos_pf[z], gf_pf[z], gc_pf[z]) for z in ZONAS_PRIMERA_FASE}

        # Mejor quinto (Art. 12.3): comparar el 5° de las zonas 2/3/4.
        quinto_dg, quinto_gf = {}, {}
        for z in ("2", "3", "4"):
            pos5 = orden_pf[z][CLASIFICAN_ZONA_NUEVE, :]
            quinto_gf[z] = np.take_along_axis(gf_pf[z], pos5[None, :], axis=0)[0]
            quinto_gc = np.take_along_axis(gc_pf[z], pos5[None, :], axis=0)[0]
            quinto_dg[z] = quinto_gf[z] - quinto_gc
        compuesto_quintos = (np.stack([quinto_dg[z] for z in ("2", "3", "4")]).astype(np.int64) * 1_000_000
                             + np.stack([quinto_gf[z] for z in ("2", "3", "4")]).astype(np.int64))
        mejor_quinto_zona_i = np.argmax(compuesto_quintos, axis=0)  # (S,) 0='2',1='3',2='4'

        # ---- Segunda Fase: slots de Zona A y Zona B ----
        slots_a = np.stack(
            [idx_zona["1"][orden_pf["1"][i, :]] for i in range(CLASIFICAN_ZONA_DIEZ)]
            + [idx_zona["2"][orden_pf["2"][i, :]] for i in range(CLASIFICAN_ZONA_NUEVE)]
        )
        quinto_equipo_idx = {z: idx_zona[z][orden_pf[z][CLASIFICAN_ZONA_NUEVE, :]] for z in ("2", "3", "4")}
        mejor_quinto_equipo = np.select(
            [mejor_quinto_zona_i == 0, mejor_quinto_zona_i == 1, mejor_quinto_zona_i == 2],
            [quinto_equipo_idx["2"], quinto_equipo_idx["3"], quinto_equipo_idx["4"]],
        )
        slots_b = np.stack(
            [idx_zona["3"][orden_pf["3"][i, :]] for i in range(CLASIFICAN_ZONA_NUEVE)]
            + [idx_zona["4"][orden_pf["4"][i, :]] for i in range(CLASIFICAN_ZONA_NUEVE)]
            + [mejor_quinto_equipo]
        )
        puntos_a, gf_a, gc_a = self._simular_zona_slots_vectorizada(nombres, slots_a, S)
        puntos_b, gf_b, gc_b = self._simular_zona_slots_vectorizada(nombres, slots_b, S)

        # ---- Reválida 1ª Etapa: slots de Zona A y Zona B (con slot(s)
        # fantasma para el/los 5° condicional(es)) ----
        # OJO: los límites superiores de estos rangos NO pueden ser
        # literales (10, 9, 9) -- eso asume que Zona 1 siempre tiene 10
        # equipos y Zonas 2/3/4 siempre 9, lo cual deja de valer apenas
        # el roster de Federal A cambia de tamaño entre rondas locales
        # (ver /api/season/play, ronda 2+: un ascenso/descenso corrido
        # de otra división puede dejar una zona con 9 equipos en vez de
        # 10). Usamos el tamaño real de cada zona (idx_zona[z].shape[0]),
        # igual que ya hace la versión no vectorizada de más abajo
        # (simular_primera_fase/clasificados_primera_fase, que sólo
        # slicea listas y por eso nunca tuvo este bug).
        n1, n2, n3, n4 = (idx_zona[z].shape[0] for z in ("1", "2", "3", "4"))
        slots_ra = np.stack(
            [idx_zona["1"][orden_pf["1"][i, :]] for i in range(CLASIFICAN_ZONA_DIEZ, n1)]
            + [idx_zona["2"][orden_pf["2"][i, :]] for i in range(CLASIFICAN_ZONA_NUEVE + 1, n2)]
            + [quinto_equipo_idx["2"]]
        )
        n_reales_ra = (n1 - CLASIFICAN_ZONA_DIEZ) + (n2 - CLASIFICAN_ZONA_NUEVE - 1)
        reales_ra = np.stack([np.ones(S, dtype=bool)] * n_reales_ra + [mejor_quinto_zona_i != 0])

        slots_rb = np.stack(
            [idx_zona["3"][orden_pf["3"][i, :]] for i in range(CLASIFICAN_ZONA_NUEVE + 1, n3)]
            + [idx_zona["4"][orden_pf["4"][i, :]] for i in range(CLASIFICAN_ZONA_NUEVE + 1, n4)]
            + [quinto_equipo_idx["3"], quinto_equipo_idx["4"]]
        )
        n_reales_rb = (n3 - CLASIFICAN_ZONA_NUEVE - 1) + (n4 - CLASIFICAN_ZONA_NUEVE - 1)
        reales_rb = np.stack([np.ones(S, dtype=bool)] * n_reales_rb + [mejor_quinto_zona_i != 1, mejor_quinto_zona_i != 2])

        puntos_ra, gf_ra, gc_ra = self._simular_zona_slots_vectorizada(nombres, slots_ra, S, es_real_slot=reales_ra)
        puntos_rb, gf_rb, gc_rb = self._simular_zona_slots_vectorizada(nombres, slots_rb, S, es_real_slot=reales_rb)

        return {
            "nombres": nombres, "S": S,
            "zonas_pf": zonas, "puntos_pf": puntos_pf, "gf_pf": gf_pf, "gc_pf": gc_pf, "orden_pf": orden_pf,
            "slots_a": slots_a, "puntos_a": puntos_a, "gf_a": gf_a, "gc_a": gc_a,
            "slots_b": slots_b, "puntos_b": puntos_b, "gf_b": gf_b, "gc_b": gc_b,
            "slots_ra": slots_ra, "reales_ra": reales_ra, "puntos_ra": puntos_ra, "gf_ra": gf_ra, "gc_ra": gc_ra,
            "slots_rb": slots_rb, "reales_rb": reales_rb, "puntos_rb": puntos_rb, "gf_rb": gf_rb, "gc_rb": gc_rb,
        }

    def _simular_zona_slots_vectorizada(
        self, nombres: list[str], equipo_en_slot: np.ndarray, S: int, es_real_slot: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Envoltorio de _simular_ronda_slots_vectorizada(): a partir de
        equipo_en_slot (n_slots, S, índices GLOBALES de equipo), gatherea
        los ratings de ataque/defensa de quien ocupa cada lugar en cada
        repetición, arma el fixture de una rueda entre los slots, y
        simula. es_real_slot (n_slots, S) opcional enmascara los
        partidos donde alguno de los dos lados es un slot fantasma (ver
        docstring de _simular_ronda_slots_vectorizada)."""
        n_slots = equipo_en_slot.shape[0]
        al = np.array([self.equipos[n].ataque_local for n in nombres])
        dv = np.array([self.equipos[n].defensa_visitante for n in nombres])
        av = np.array([self.equipos[n].ataque_visitante for n in nombres])
        dl = np.array([self.equipos[n].defensa_local for n in nombres])

        ataque_local_slot = al[equipo_en_slot]
        defensa_visitante_slot = dv[equipo_en_slot]
        ataque_visitante_slot = av[equipo_en_slot]
        defensa_local_slot = dl[equipo_en_slot]

        from fixture_generator import generar_fixture_una_rueda
        partidos = generar_fixture_una_rueda(list(range(n_slots)))
        idx_local = np.array([p.equipo_local for p in partidos])
        idx_visitante = np.array([p.equipo_visitante for p in partidos])

        lambda_local_base = ataque_local_slot[idx_local] * defensa_visitante_slot[idx_visitante] * self.PROMEDIO_GF_LOCAL_LIGA
        lambda_visitante_base = ataque_visitante_slot[idx_visitante] * defensa_local_slot[idx_local] * self.PROMEDIO_GF_VISITANTE_LIGA

        mascara = None
        if es_real_slot is not None:
            mascara = (es_real_slot[idx_local] & es_real_slot[idx_visitante]).astype(np.float64)

        return self._simular_ronda_slots_vectorizada(
            lambda_local_base, lambda_visitante_base, idx_local, idx_visitante, n_slots, S,
            mascara_partido=mascara,
        )

    def _asignar_zonas(self, mapa_zona: dict[str, str]) -> None:
        """equipo.zona = zona para cada entrada de mapa_zona (nombre ->
        zona). Es lo que usa simular_fase_regular()/_armar_tabla_final()
        para agrupar."""
        for nombre, zona in mapa_zona.items():
            self.equipos[nombre].zona = zona

    # ------------------------------------------------------------------
    # Desempates auxiliares (comunes a varias fases)
    # ------------------------------------------------------------------
    @staticmethod
    def _tabla_a_dict_posiciones(tabla: pd.DataFrame) -> dict[str, int]:
        """{equipo: posición 1-indexada} a partir de una tabla ya
        ordenada (como las que devuelve simular_fase_regular())."""
        return {equipo: pos for pos, equipo in enumerate(tabla["equipo"], start=1)}

    @staticmethod
    def _fila(tabla: pd.DataFrame, equipo: str) -> pd.Series:
        return tabla.loc[tabla["equipo"] == equipo].iloc[0]

    def _mejor_por_dg_gf(self, tabla: pd.DataFrame, candidatos: list[str], semilla: str) -> str:
        """De una lista de equipos (todos de la MISMA tabla), el de mejor
        diferencia de gol; empate -> más goles a favor; empate total ->
        sorteo determinístico. Usado en el 'mejor quinto' (Art. 12.3) y
        en varias resiembras de la Reválida."""
        filas = {c: self._fila(tabla, c) for c in candidatos}
        mejor_dg = max(f["dg"] for f in filas.values())
        en_dg = [c for c, f in filas.items() if f["dg"] == mejor_dg]
        if len(en_dg) == 1:
            return en_dg[0]
        mejor_gf = max(filas[c]["gf"] for c in en_dg)
        en_gf = [c for c in en_dg if filas[c]["gf"] == mejor_gf]
        if len(en_gf) == 1:
            return en_gf[0]
        return _sorteo_deterministico(en_gf, semilla)

    # ------------------------------------------------------------------
    # PRIMERA FASE (4 zonas, ida y vuelta)
    # ------------------------------------------------------------------
    def simular_primera_fase(self) -> dict[str, pd.DataFrame]:
        """Tabla final de cada una de las 4 zonas (self.fixture debe ser
        el de Primera Fase, ya es el que carga cargar_datos_federal())."""
        return self.simular_fase_regular()

    def clasificados_primera_fase(self, tablas: dict[str, pd.DataFrame]) -> dict[str, list[str]]:
        """A partir de las 4 tablas de Primera Fase, arma:
          - 'segunda_fase_A' / 'segunda_fase_B': los 18 clasificados a la
            Segunda Fase, ya agrupados en sus dos nuevas zonas.
          - 'revalida_A' / 'revalida_B': los 19 que van a la Reválida
            Primera Etapa, agrupados en sus dos zonas.

        Zona A de la Segunda Fase es SIEMPRE zona1[1°-5°] + zona2[1°-4°]
        (9 clubes fijos). Zona B es SIEMPRE zona3[1°-4°] + zona4[1°-4°] +
        el 'mejor quinto' (Art. 11): de los tres 5°-puestos de las zonas
        2/3/4, el de mejor diferencia de gol (empate -> gf, empate total
        -> sorteo) se suma a la Zona B -- nunca a la A, sin importar de
        qué zona haya salido. Los otros dos 5° bajan a la Reválida.
        """
        top_zona1 = tablas[ZONA_DIEZ]["equipo"].tolist()
        zona1_clasif, zona1_revalida = top_zona1[:CLASIFICAN_ZONA_DIEZ], top_zona1[CLASIFICAN_ZONA_DIEZ:]

        top = {z: tablas[z]["equipo"].tolist() for z in ("2", "3", "4")}
        clasif_fijo = {z: top[z][:CLASIFICAN_ZONA_NUEVE] for z in ("2", "3", "4")}
        quintos = {z: top[z][CLASIFICAN_ZONA_NUEVE] for z in ("2", "3", "4")}
        resto = {z: top[z][CLASIFICAN_ZONA_NUEVE + 1:] for z in ("2", "3", "4")}  # posiciones 6-9

        tabla_quintos = pd.concat([tablas[z].iloc[[CLASIFICAN_ZONA_NUEVE]] for z in ("2", "3", "4")])
        mejor_quinto_equipo = self._mejor_por_dg_gf(
            tabla_quintos, list(quintos.values()), semilla="mejor_quinto_primera_fase"
        )
        zona_ganadora = next(z for z, eq in quintos.items() if eq == mejor_quinto_equipo)

        segunda_fase_a = zona1_clasif + clasif_fijo["2"]
        segunda_fase_b = clasif_fijo["3"] + clasif_fijo["4"] + [mejor_quinto_equipo]

        revalida_a = zona1_revalida + resto["2"]
        revalida_b = resto["3"] + resto["4"]
        for z in ("2", "3", "4"):
            if z != zona_ganadora:
                destino = revalida_a if z == "2" else revalida_b
                destino.append(quintos[z])

        return {
            "segunda_fase_A": segunda_fase_a,
            "segunda_fase_B": segunda_fase_b,
            "revalida_A": revalida_a,
            "revalida_B": revalida_b,
        }

    # ------------------------------------------------------------------
    # SEGUNDA FASE (2 zonas de 9, una rueda, ida solamente)
    # ------------------------------------------------------------------
    def armar_segunda_fase(self, clasificados: dict[str, list[str]]) -> None:
        """Prepara self.fixture/self.equipos para simular la Segunda
        Fase: fixture nuevo (una rueda por zona), puntaje en cero y
        equipo.zona = 'A' / 'B' según corresponda."""
        from fixture_generator import generar_fixture_una_rueda

        zona_a, zona_b = clasificados["segunda_fase_A"], clasificados["segunda_fase_B"]
        self._asignar_zonas({**{e: "A" for e in zona_a}, **{e: "B" for e in zona_b}})
        self._resetear_puntajes(zona_a + zona_b)

        partidos = generar_fixture_una_rueda(zona_a) + generar_fixture_una_rueda(zona_b)
        self._reset_fixture(pd.DataFrame(
            [{"fecha": "", "jornada": p.jornada, "equipo_local": p.equipo_local,
              "equipo_visitante": p.equipo_visitante} for p in partidos]
        ))

    def simular_segunda_fase(self) -> dict[str, pd.DataFrame]:
        return self.simular_fase_regular()

    def clasificados_segunda_fase(self, tablas: dict[str, pd.DataFrame]) -> dict[str, list[str]]:
        """1° y 4° de cada zona -> Tercera Fase (8 clubes); 5°-9° de cada
        zona -> Reválida Segunda Etapa (10 clubes)."""
        top4_a, top4_b = tablas["A"]["equipo"].tolist()[:4], tablas["B"]["equipo"].tolist()[:4]
        resto_a, resto_b = tablas["A"]["equipo"].tolist()[4:], tablas["B"]["equipo"].tolist()[4:]
        return {
            "tercera_fase": {"1A": top4_a[0], "2A": top4_a[1], "3A": top4_a[2], "4A": top4_a[3],
                              "1B": top4_b[0], "2B": top4_b[1], "3B": top4_b[2], "4B": top4_b[3]},
            "revalida_segunda_etapa_2f": resto_a + resto_b,
        }

    # ------------------------------------------------------------------
    # Llaves de eliminación directa a ida y vuelta (Tercera/Cuarta Fase y
    # toda la Reválida), con desempate por semilla salvo que se pida
    # penales explícitamente (única vez: Sexta Etapa de la Reválida).
    # ------------------------------------------------------------------
    def _jugar_llave_ida_vuelta(self, local_ida: str, visitante_ida: str,
                                 ganador_en_empate: str | None) -> ResultadoSerie:
        """Juega ida y vuelta entre dos equipos. Si termina empatada en
        goles agregados (equivalente a "empatada en puntos y en
        diferencia de gol" para una serie a dos partidos, ver
        docstring del módulo):
          - si `ganador_en_empate` es un nombre de equipo, ese avanza
            (desempate por mejor ubicación/sembrado, como en casi todas
            las llaves del Reglamento);
          - si es None, se define por penales 50/50 (único caso: Sexta
            Etapa de la Reválida).
        `local_ida` es quien juega de local el PRIMER partido (la vuelta
        la juega de local el otro)."""
        gl1, gv1 = self.simular_partido(local_ida, visitante_ida)
        gl2, gv2 = self.simular_partido(visitante_ida, local_ida)

        goles_local_ida_agregado = gl1 + gv2
        goles_visitante_ida_agregado = gv1 + gl2

        detalle = {
            "local_ida": local_ida, "visitante_ida": visitante_ida,
            "ida": [gl1, gv1], "vuelta": [gl2, gv2],
            "agregado": [goles_local_ida_agregado, goles_visitante_ida_agregado],
        }

        if goles_local_ida_agregado != goles_visitante_ida_agregado:
            ganador = local_ida if goles_local_ida_agregado > goles_visitante_ida_agregado else visitante_ida
        elif ganador_en_empate is not None:
            ganador = ganador_en_empate
            detalle["definido_por"] = "mejor_ubicacion"
        else:
            ganador = local_ida if np.random.random() < 0.5 else visitante_ida
            detalle["definido_por"] = "penales"

        perdedor = visitante_ida if ganador == local_ida else local_ida
        detalle["avanza"] = ganador
        return ResultadoSerie(ganador=ganador, perdedor=perdedor, detalle=detalle)

    # ------------------------------------------------------------------
    # TERCERA FASE (8 clubes, ida y vuelta)
    # ------------------------------------------------------------------
    def jugar_tercera_fase(self, seeds: dict[str, str]) -> dict[str, ResultadoSerie]:
        """seeds: {"1A":equipo, "2A":equipo, ..., "4B":equipo} (salida de
        clasificados_segunda_fase). Cruces fijados por el Reglamento;
        el 3° y el 4° de cada par hacen de local en la ida."""
        cruces = {
            "p1": (seeds["4B"], seeds["1A"]),  # local ida: 4B (peor ubicado)
            "p2": (seeds["3B"], seeds["2A"]),
            "p3": (seeds["4A"], seeds["1B"]),
            "p4": (seeds["3A"], seeds["2B"]),
        }
        # Empate -> avanza el mejor sembrado (1° o 2°, que siempre es el
        # segundo elemento del par tal como están armados arriba).
        return {
            clave: self._jugar_llave_ida_vuelta(local, visitante, ganador_en_empate=visitante)
            for clave, (local, visitante) in cruces.items()
        }

    # ------------------------------------------------------------------
    # CUARTA FASE (4 clubes, ida y vuelta)
    # ------------------------------------------------------------------
    def jugar_cuarta_fase(self, resultados_tercera: dict[str, ResultadoSerie]) -> dict[str, ResultadoSerie]:
        """Ganador P1 vs Ganador P2, Ganador P3 vs Ganador P4. Local en
        la ida: el de peor ubicación en la Segunda Fase -- que acá
        aproximamos con 'quien vino del partido de la llave con el
        índice más alto' (p2 y p4 fueron cruces de 2°/3°, siempre peor
        ubicados que p1/p3 que cruzan 1°/4°); ante empate de origen, se
        define por sorteo determinístico."""
        g1, g2 = resultados_tercera["p1"].ganador, resultados_tercera["p2"].ganador
        g3, g4 = resultados_tercera["p3"].ganador, resultados_tercera["p4"].ganador
        return {
            "c1": self._jugar_llave_ida_vuelta(g2, g1, ganador_en_empate=g1),
            "c2": self._jugar_llave_ida_vuelta(g4, g3, ganador_en_empate=g3),
        }

    # ------------------------------------------------------------------
    # QUINTA FASE - FINAL (partido único, cancha neutral, penales) ->
    # 1° ASCENSO
    # ------------------------------------------------------------------
    def jugar_quinta_fase(self, resultados_cuarta: dict[str, ResultadoSerie]) -> ResultadoSerie:
        finalista_1, finalista_2 = resultados_cuarta["c1"].ganador, resultados_cuarta["c2"].ganador
        ganador, perdedor, detalle = self.jugar_final_ascenso(finalista_1, finalista_2)
        # jugar_final_ascenso() no expone quién era "nombre_a"/"nombre_b"
        # en su detalle (solo marcador/texto) -- lo agregamos acá, que es
        # donde se conocen, para que el JSON web no tenga que parsear el
        # texto de vuelta para saber quién fue local.
        detalle = {**detalle, "local": finalista_1, "visitante": finalista_2}
        return ResultadoSerie(ganador=ganador, perdedor=perdedor, detalle=detalle)

    # ------------------------------------------------------------------
    # REVÁLIDA - PRIMERA ETAPA (2 zonas, una rueda, ida solamente) +
    # RÉGIMEN DE DESCENSO
    # ------------------------------------------------------------------
    def armar_revalida_primera_etapa(self, clasificados: dict[str, list[str]]) -> None:
        from fixture_generator import generar_fixture_una_rueda

        zona_a, zona_b = clasificados["revalida_A"], clasificados["revalida_B"]
        self._asignar_zonas({**{e: "RA" for e in zona_a}, **{e: "RB" for e in zona_b}})
        self._resetear_puntajes(zona_a + zona_b)

        partidos = generar_fixture_una_rueda(zona_a) + generar_fixture_una_rueda(zona_b)
        self._reset_fixture(pd.DataFrame(
            [{"fecha": "", "jornada": p.jornada, "equipo_local": p.equipo_local,
              "equipo_visitante": p.equipo_visitante} for p in partidos]
        ))

    def simular_revalida_primera_etapa(self) -> dict[str, pd.DataFrame]:
        tablas = self.simular_fase_regular()
        return {"RA": tablas["RA"], "RB": tablas["RB"]}

    _PARTIDOS_PRIMERA_FASE_POR_ZONA = {ZONA_DIEZ: 18, "2": 16, "3": 16, "4": 16}
    """Partidos totales que juega cada equipo en la Primera Fase (rueda
    doble completa): depende solo de la zona de origen, no del resultado
    de ningún partido. Zona de 10 (par, sin descanso): 9 partidos por
    rueda x2 = 18. Zonas de 9 (impar, un descanso por rueda): 8 x2 = 16."""

    def _zona_origen_por_equipo(self) -> dict[str, str]:
        """{equipo: zona ('1'..'4')} de Primera Fase, cacheado -- viene
        de self.tabla (no se pisa entre fases, a diferencia de
        equipo.zona en tiempo de ejecución)."""
        if getattr(self, "_zona_origen_cache", None) is None:
            self._zona_origen_cache = dict(zip(self.tabla["equipo"], self.tabla["zona"]))
        return self._zona_origen_cache

    def _combinar_pf_y_revalida_1a_etapa(
        self,
        tablas_primera_fase: dict[str, pd.DataFrame],
        tablas_revalida_1a_etapa: dict[str, pd.DataFrame],
    ) -> dict[str, pd.DataFrame]:
        """{"RA": DataFrame, "RB": DataFrame} con puntos/gf/gc/dg/
        partidos_jugados/promedio ACUMULADOS de Primera Fase + Reválida
        Primera Etapa. Lo usan tanto calcular_descensos() (Régimen de
        Descenso) como armar_revalida_segunda_etapa() (posiciones 15-24,
        que también se ordenan por promedio -- para la Zona B, donde
        todos jugaron la misma cantidad de partidos, ordenar por
        promedio o por puntos da exactamente el mismo resultado, así que
        usarlo para las dos zonas no contradice que el Art. solo pida
        'Tabla General de Puntos' para B).

        partidos_jugados se calcula por CONSTANTES según el tamaño de
        cada zona (ver _PARTIDOS_PRIMERA_FASE_POR_ZONA), no contando
        filas de self.resultados como antes: eso UNDERCOUNTEABA
        (self.resultados solo tiene partidos reales de Primera Fase; la
        porción de Reválida -- 100% simulada, nunca "real" -- daba
        siempre 0) y además recorría todo el DataFrame por cada equipo y
        por cada repetición del Monte Carlo."""
        zona_origen = self._zona_origen_por_equipo()

        def combinar(zona_revalida: str, zonas_primera_fase: list[str]) -> pd.DataFrame:
            tabla_r1 = tablas_revalida_1a_etapa[zona_revalida]
            partidos_revalida = len(tabla_r1) - 1  # una rueda simple: n_miembros - 1

            equipos_pf = pd.concat([tablas_primera_fase[z] for z in zonas_primera_fase]).set_index("equipo")
            base = equipos_pf.loc[tabla_r1["equipo"]].reset_index()

            tabla = pd.DataFrame({
                "equipo": tabla_r1["equipo"].values,
                "puntos": base["puntos"].values + tabla_r1["puntos"].values,
                "gf": base["gf"].values + tabla_r1["gf"].values,
                "gc": base["gc"].values + tabla_r1["gc"].values,
                "partidos_jugados": [
                    self._PARTIDOS_PRIMERA_FASE_POR_ZONA[zona_origen[eq]] + partidos_revalida
                    for eq in tabla_r1["equipo"]
                ],
            })
            tabla["dg"] = tabla["gf"] - tabla["gc"]
            tabla["promedio"] = (tabla["puntos"] / tabla["partidos_jugados"]).round(3)
            return tabla

        return {
            "RA": combinar("RA", [ZONA_DIEZ, "2"]),
            "RB": combinar("RB", ["3", "4"]),
        }

    def calcular_descensos(
        self,
        tablas_primera_fase: dict[str, pd.DataFrame],
        tablas_revalida_1a_etapa: dict[str, pd.DataFrame],
        clasificados_1f: dict[str, list[str]],
    ) -> list[str]:
        """Régimen de Descenso (Art. 11): combina los puntos/gf/gc/pj de
        Primera Fase + Reválida Primera Etapa. Zona A (mezcla equipos de
        la zona de 10 y de la zona de 9: jugaron distinta cantidad de
        partidos en Primera Fase) desempata por PROMEDIO de puntos; Zona
        B (todos de zonas de 9, misma cantidad de partidos) usa puntos
        directos. Devuelve los 4 equipos que descienden, salvo que
        alguno esté entre los 5 primeros de su zona en esta etapa: en
        ese caso ya se aseguró seguir en el certamen (clasifica a la
        Segunda Etapa igual) y el descenso pasa al siguiente de la
        tabla."""
        combinadas = self._combinar_pf_y_revalida_1a_etapa(tablas_primera_fase, tablas_revalida_1a_etapa)
        combinada_a = combinadas["RA"].sort_values(by=["promedio", "dg", "gf"], ascending=False).reset_index(drop=True)
        combinada_b = combinadas["RB"].sort_values(by=["puntos", "dg", "gf"], ascending=False).reset_index(drop=True)

        # "A salvo" = quien ya clasifica a la Segunda Etapa por la tabla
        # DE ESTA FASE (fase-only, la misma que arma las posiciones
        # 15-24) -- NO por la tabla combinada, que puede ordenar distinto
        # al mezclar los puntos de la Primera Fase. Un equipo puede ser
        # top-5 fase-only y no top-5 combinado (o viceversa); lo que
        # importa acá es que si ya clasificó, el descenso no lo alcanza.
        asegurados = {
            "RA": set(tablas_revalida_1a_etapa["RA"]["equipo"].tolist()[:5]),
            "RB": set(tablas_revalida_1a_etapa["RB"]["equipo"].tolist()[:5]),
        }

        def descensos_de(tabla: pd.DataFrame, zona: str) -> list[str]:
            # Los 2 de peor ubicación en la tabla COMBINADA descienden,
            # salteando a quien ya esté "a salvo" (ver comentario arriba)
            # -- situación borde que el propio Art. 11 contempla y que
            # con datos reales casi nunca ocurre.
            candidatos = tabla["equipo"].tolist()
            cola = [e for e in reversed(candidatos) if e not in asegurados[zona]]
            return cola[:DESCENSOS_POR_ZONA_REVALIDA]

        return descensos_de(combinada_a, "RA") + descensos_de(combinada_b, "RB")

    # ------------------------------------------------------------------
    # REVÁLIDA - SEGUNDA ETAPA (24 clubes, resiembra + ida y vuelta)
    # ------------------------------------------------------------------
    def armar_revalida_segunda_etapa(
        self,
        resultados_tercera_fase: dict[str, ResultadoSerie],
        tablas_segunda_fase: dict[str, pd.DataFrame],
        revalida_segunda_etapa_2f: list[str],
        tablas_primera_fase: dict[str, pd.DataFrame],
        tablas_revalida_1a_etapa: dict[str, pd.DataFrame],
    ) -> dict[int, str]:
        """Arma las posiciones 1 a 24 según el Art. (numeración de la
        Segunda Etapa). Devuelve {posicion: equipo}."""
        posiciones: dict[int, str] = {}

        # Posiciones 1-4: los 4 perdedores de la Tercera Fase, ordenados
        # por mejor ubicación en la Segunda Fase (posición dentro de su
        # propia zona A/B; empate -> dg/gf/sorteo).
        perdedores_3f = [resultados_tercera_fase[p].perdedor for p in ("p1", "p2", "p3", "p4")]
        pos_zona = {
            **self._tabla_a_dict_posiciones(tablas_segunda_fase["A"]),
            **self._tabla_a_dict_posiciones(tablas_segunda_fase["B"]),
        }
        perdedores_ordenados = sorted(
            perdedores_3f,
            key=lambda eq: (pos_zona[eq], self._clave_desempate_segunda_fase(eq, tablas_segunda_fase))
        )
        for i, equipo in enumerate(perdedores_ordenados, start=1):
            posiciones[i] = equipo

        # Posiciones 5-14: los 10 de Segunda Fase (5°-9° de cada zona),
        # de a pares por posición de zona (5°,6°,7°,8°,9°), mejor
        # puntaje primero dentro del par.
        for i, pos_en_zona in enumerate((5, 6, 7, 8, 9)):
            equipo_a = tablas_segunda_fase["A"].iloc[pos_en_zona - 1]
            equipo_b = tablas_segunda_fase["B"].iloc[pos_en_zona - 1]
            mejor, peor = self._mejor_de_par(equipo_a, equipo_b)
            posiciones[5 + i * 2] = mejor
            posiciones[6 + i * 2] = peor

        # Posiciones 15-24: los 10 de la Reválida Primera Etapa (1°-5° de
        # cada zona -- identificados por la tabla DE ESA FASE, orden ya
        # correcto porque _armar_tabla_final ordena por puntos/dg/gf),
        # de a pares por posición de zona; el PROMEDIO acumulado (Primera
        # Fase + Reválida 1a Etapa) se usa solo como desempate entre los
        # dos ya identificados, no para re-rankearlos. Empate en
        # promedio -> sorteo directo (Nota 2, sin criterios de gol).
        combinadas = self._combinar_pf_y_revalida_1a_etapa(tablas_primera_fase, tablas_revalida_1a_etapa)
        promedio_por_equipo = {
            **combinadas["RA"].set_index("equipo")["promedio"].to_dict(),
            **combinadas["RB"].set_index("equipo")["promedio"].to_dict(),
        }
        for i, pos_en_zona in enumerate((1, 2, 3, 4, 5)):
            equipo_ra = tablas_revalida_1a_etapa["RA"].iloc[pos_en_zona - 1]["equipo"]
            equipo_rb = tablas_revalida_1a_etapa["RB"].iloc[pos_en_zona - 1]["equipo"]
            mejor, peor = self._mejor_por_valor(
                equipo_ra, equipo_rb, promedio_por_equipo, semilla="par_revalida_1a"
            )
            posiciones[15 + i * 2] = mejor
            posiciones[16 + i * 2] = peor

        assert len(posiciones) == 24, f"Deberían ser 24 posiciones, hay {len(posiciones)}"
        return posiciones

    @staticmethod
    def _mejor_por_valor(nombre_a: str, nombre_b: str, valor_por_equipo: dict[str, float], semilla: str) -> tuple[str, str]:
        """Compara dos equipos por un valor numérico ya calculado
        (ej. promedio de puntos); empate -> sorteo determinístico."""
        valor_a, valor_b = valor_por_equipo[nombre_a], valor_por_equipo[nombre_b]
        if valor_a != valor_b:
            return (nombre_a, nombre_b) if valor_a > valor_b else (nombre_b, nombre_a)
        mejor = _sorteo_deterministico([nombre_a, nombre_b], semilla_extra=semilla)
        peor = nombre_b if mejor == nombre_a else nombre_a
        return mejor, peor

    def _clave_desempate_segunda_fase(self, equipo: str, tablas: dict[str, pd.DataFrame]) -> tuple[float, float]:
        for tabla in tablas.values():
            match = tabla.loc[tabla["equipo"] == equipo]
            if len(match):
                fila = match.iloc[0]
                return (-fila["dg"], -fila["gf"])  # negativo: "mejor" ordena primero al usar sorted() ascendente
        raise KeyError(equipo)

    def _mejor_de_par(self, fila_a: pd.Series, fila_b: pd.Series) -> tuple[str, str]:
        """De dos filas de tabla (mismo puesto, zonas distintas), cuál
        tuvo mejor puntaje; empate -> dg, luego gf, luego sorteo."""
        if fila_a["puntos"] != fila_b["puntos"]:
            return (fila_a["equipo"], fila_b["equipo"]) if fila_a["puntos"] > fila_b["puntos"] \
                else (fila_b["equipo"], fila_a["equipo"])
        if fila_a["dg"] != fila_b["dg"]:
            return (fila_a["equipo"], fila_b["equipo"]) if fila_a["dg"] > fila_b["dg"] \
                else (fila_b["equipo"], fila_a["equipo"])
        if fila_a["gf"] != fila_b["gf"]:
            return (fila_a["equipo"], fila_b["equipo"]) if fila_a["gf"] > fila_b["gf"] \
                else (fila_b["equipo"], fila_a["equipo"])
        mejor = _sorteo_deterministico([fila_a["equipo"], fila_b["equipo"]], semilla_extra="par_2f")
        peor = fila_b["equipo"] if mejor == fila_a["equipo"] else fila_a["equipo"]
        return mejor, peor

    def jugar_revalida_segunda_etapa(self, posiciones: dict[int, str]) -> dict[str, ResultadoSerie]:
        """1v24, 2v23, ..., 12v13. Local en la ida: la posición más alta
        en número (13-24, la 'peor' del par)."""
        pares = [(i, 25 - i) for i in range(1, 13)]
        resultados = {}
        for mejor_pos, peor_pos in pares:
            mejor, peor = posiciones[mejor_pos], posiciones[peor_pos]
            clave = f"{mejor_pos}v{peor_pos}"
            resultados[clave] = self._jugar_llave_ida_vuelta(peor, mejor, ganador_en_empate=mejor)
        return resultados

    # ------------------------------------------------------------------
    # REVÁLIDA - TERCERA ETAPA (14 clubes)
    # ------------------------------------------------------------------
    def armar_revalida_tercera_etapa(
        self,
        resultados_segunda_etapa: dict[str, ResultadoSerie],
        resultado_cuarta_fase: dict[str, ResultadoSerie],
        tablas_segunda_fase: dict[str, pd.DataFrame],
    ) -> dict[int, str]:
        """Posiciones 1-2: los 2 perdedores de la Cuarta Fase, por mejor
        ubicación en la Segunda Fase. Posiciones 3-14: los 12 ganadores
        de la Reválida Segunda Etapa, en el mismo orden (su posición
        numerada 1-12 ahora se traduce en 3-14)."""
        perdedores_4f = [resultado_cuarta_fase["c1"].perdedor, resultado_cuarta_fase["c2"].perdedor]
        pos_zona = {
            **self._tabla_a_dict_posiciones(tablas_segunda_fase["A"]),
            **self._tabla_a_dict_posiciones(tablas_segunda_fase["B"]),
        }
        perdedores_ordenados = sorted(
            perdedores_4f,
            key=lambda eq: (pos_zona[eq], self._clave_desempate_segunda_fase(eq, tablas_segunda_fase))
        )
        posiciones = {1: perdedores_ordenados[0], 2: perdedores_ordenados[1]}

        ganadores_en_orden = [
            resultados_segunda_etapa[clave].ganador
            for clave in (f"{i}v{25 - i}" for i in range(1, 13))
        ]
        for i, equipo in enumerate(ganadores_en_orden):
            posiciones[3 + i] = equipo

        assert len(posiciones) == 14
        return posiciones

    def jugar_revalida_tercera_etapa(self, posiciones: dict[int, str]) -> dict[str, ResultadoSerie]:
        """1v14, 2v13, ..., 7v8. Local en la ida: posiciones 8-14."""
        pares = [(i, 15 - i) for i in range(1, 8)]
        resultados = {}
        for mejor_pos, peor_pos in pares:
            mejor, peor = posiciones[mejor_pos], posiciones[peor_pos]
            clave = f"{mejor_pos}v{peor_pos}"
            resultados[clave] = self._jugar_llave_ida_vuelta(peor, mejor, ganador_en_empate=mejor)
        return resultados

    # ------------------------------------------------------------------
    # REVÁLIDA - CUARTA ETAPA (8 clubes)
    # ------------------------------------------------------------------
    def armar_revalida_cuarta_etapa(
        self,
        resultados_tercera_etapa: dict[str, ResultadoSerie],
        resultado_quinta_fase: ResultadoSerie,
    ) -> dict[int, str]:
        """Posición 1: el perdedor de la Quinta Fase (la final del 1°
        ascenso). Posiciones 2-8: los 7 ganadores de la Reválida Tercera
        Etapa, mismo orden."""
        posiciones = {1: resultado_quinta_fase.perdedor}
        ganadores_en_orden = [
            resultados_tercera_etapa[clave].ganador
            for clave in (f"{i}v{15 - i}" for i in range(1, 8))
        ]
        for i, equipo in enumerate(ganadores_en_orden):
            posiciones[2 + i] = equipo
        assert len(posiciones) == 8
        return posiciones

    def jugar_revalida_cuarta_etapa(self, posiciones: dict[int, str]) -> dict[str, ResultadoSerie]:
        """1v8, 2v7, 3v6, 4v5. Local en la ida: posiciones 5-8."""
        pares = [(1, 8), (2, 7), (3, 6), (4, 5)]
        resultados = {}
        for mejor_pos, peor_pos in pares:
            mejor, peor = posiciones[mejor_pos], posiciones[peor_pos]
            clave = f"{mejor_pos}v{peor_pos}"
            resultados[clave] = self._jugar_llave_ida_vuelta(peor, mejor, ganador_en_empate=mejor)
        return resultados

    # ------------------------------------------------------------------
    # REVÁLIDA - QUINTA ETAPA (4 clubes)
    # ------------------------------------------------------------------
    def jugar_revalida_quinta_etapa(self, resultados_cuarta_etapa: dict[str, ResultadoSerie]) -> dict[str, ResultadoSerie]:
        """Mantiene el orden de la Cuarta Etapa: 1v4, 2v3. Local en la
        ida: posiciones 3 y 4 (los 2 ganadores de peor numeración)."""
        g1 = resultados_cuarta_etapa["1v8"].ganador
        g2 = resultados_cuarta_etapa["2v7"].ganador
        g3 = resultados_cuarta_etapa["3v6"].ganador
        g4 = resultados_cuarta_etapa["4v5"].ganador
        return {
            "1v4": self._jugar_llave_ida_vuelta(g4, g1, ganador_en_empate=g1),
            "2v3": self._jugar_llave_ida_vuelta(g3, g2, ganador_en_empate=g2),
        }

    # ------------------------------------------------------------------
    # REVÁLIDA - SEXTA ETAPA / FINAL (2 clubes) -> 2° ASCENSO
    # Única llave de toda la Reválida que se define por PENALES en vez
    # de por mejor ubicación (así lo pide el Reglamento explícitamente).
    # ------------------------------------------------------------------
    def jugar_revalida_sexta_etapa(self, resultados_quinta_etapa: dict[str, ResultadoSerie]) -> ResultadoSerie:
        g1 = resultados_quinta_etapa["1v4"].ganador
        g2 = resultados_quinta_etapa["2v3"].ganador
        # Local en la ida: la posición 2 (g2). Empate -> penales (None).
        return self._jugar_llave_ida_vuelta(g2, g1, ganador_en_empate=None)
