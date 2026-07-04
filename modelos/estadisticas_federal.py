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
        """Lee tabla_federal_a.csv (posiciones a hoy, con zona '1'..'4'),
        fixture_federal_a.csv y resultados_federal_a.csv."""
        print("Leyendo archivos de Federal A...")
        datos_dir = rutas.datos_dir()

        self.tabla = pd.read_csv(datos_dir / "tabla_federal_a.csv", dtype={"zona": str})
        self.fixture = pd.read_csv(datos_dir / "fixture_federal_a.csv")
        # dtype explícito: con 0 filas (antes del primer resultado real
        # cargado por el scraper) pandas no tiene de dónde inferir que
        # 'jornada'/goles son numéricas y las deja como object.
        self.resultados = pd.read_csv(
            datos_dir / "resultados_federal_a.csv",
            dtype={"jornada": "int64", "goles_local": "int64", "goles_visitante": "int64"},
        )

        self.validar_datos()
        print(f"Clubes: {len(self.tabla)} | Fixture Primera Fase: {len(self.fixture)} partidos")

        # Snapshot de Primera Fase (zonas 1-4 + fixture), para poder
        # restaurar el estado antes de cada corrida completa del torneo
        # (correr_simulacion_federal() reutiliza el mismo objeto `e` para
        # el Monte Carlo, y cada fase pisa equipo.zona/self.fixture).
        self._zonas_primera_fase = {nombre: fila["zona"] for nombre, fila in
                                     self.tabla.set_index("equipo").iterrows()}
        self._fixture_primera_fase = self.fixture.copy()

    def reiniciar_para_nueva_corrida(self) -> None:
        """Restaura zonas (1-4), fixture y puntajes al estado de arranque
        de la Primera Fase. Hay que llamarlo antes de cada corrida
        completa del torneo cuando se reutiliza la misma instancia (p.
        ej. cada repetición del Monte Carlo)."""
        self._asignar_zonas(self._zonas_primera_fase)
        self._resetear_puntajes(list(self.equipos.keys()))
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
        'Tabla General de Puntos' para B)."""

        def combinar(zona_revalida: str, zonas_primera_fase: list[str]) -> pd.DataFrame:
            equipos_pf = pd.concat([tablas_primera_fase[z] for z in zonas_primera_fase]).set_index("equipo")
            filas = []
            for _, fila in tablas_revalida_1a_etapa[zona_revalida].iterrows():
                nombre = fila["equipo"]
                base = equipos_pf.loc[nombre]
                pj = (self._partidos_jugados_zona(nombre, zonas_primera_fase)
                      + self._partidos_jugados_zona(nombre, [zona_revalida]))
                filas.append({
                    "equipo": nombre,
                    "puntos": int(base["puntos"]) + int(fila["puntos"]),
                    "gf": int(base["gf"]) + int(fila["gf"]),
                    "gc": int(base["gc"]) + int(fila["gc"]),
                    "partidos_jugados": pj,
                })
            tabla = pd.DataFrame(filas)
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

    def _partidos_jugados_zona(self, equipo: str, zonas: list[str]) -> int:
        """Partidos jugados por `equipo` en self.resultados, filtrando
        por si hace falta distinguir fases (acá se usa antes de
        sobreescribir self.resultados entre fases, ver main_federal.py:
        cada fase corre calcular_estadisticas()/guarda su cuenta antes
        de pasar a la siguiente)."""
        jugados = self.resultados[
            (self.resultados["equipo_local"] == equipo) | (self.resultados["equipo_visitante"] == equipo)
        ]
        return len(jugados)

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
