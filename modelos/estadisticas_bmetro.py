# -*- coding: utf-8 -*-
"""
estadisticas_bmetro.py

Motor de simulación para la Primera B Metropolitana (tercera división,
clubes directamente afiliados a AFA), temporada 2026.

A diferencia de LPF (Apertura+Clausura+zonas+playoffs cruzados), B Metro
es la liga MÁS PARECIDA a como ya está armado Nacional: temporada
regular larga, todos contra todos. La única diferencia real es que
Nacional tiene 2 zonas (A/B) con una final cruzada + Reducido entre
zonas, mientras que B Metro es una tabla ÚNICA de 22 equipos.

Truco para no reescribir todo el motor: en vez de modelar "sin zonas",
se le pone a TODOS los equipos la misma zona ("Unica") en tabla_bmetro.csv.
Como Estadisticas.crear_equipos() / simular_fase_regular() /
_armar_tabla_final() ya agrupan todo por columna "zona", con una sola
zona se comportan exactamente como una tabla única sin tocarles una
línea. Lo que SÍ hay que reescribir es lo que asume DOS zonas
específicamente:

  - jugar_final_ascenso(puntero_a, puntero_b)  -> no aplica (una sola
    zona no tiene "final cruzada": el puntero asciende directo).
  - jugar_reducido(tablas, perdedor_final_ascenso) -> se reemplaza por
    jugar_reducido_bmetro(tabla), un octogonal (posiciones 2 a 9) con el
    mismo formato de bracket (cuartos/semis/final ida y vuelta) pero
    seedeado dentro de una sola tabla en vez de cruzar A/B.
  - monte_carlo() -> monte_carlo_bmetro(), misma idea pero con
    ascenso_directo = 1 solo puntero (no 2) y descenso configurable.

Reglamento real de AFA para Primera B (Art. pertinente del "Reglamento
General de Torneos de Ascenso"): 1 ascenso directo (el puntero) + 1
ascenso por Torneo Reducido entre los siguientes mejor ubicados, y
descenso por tabla de posiciones (esta división no usa promedios como
Primera División/Primera Nacional). Descienden los últimos 2 equipos
de la tabla (ver DESCENSOS_N).
"""
import numpy as np
import pandas as pd

import data_access
import rutas
from modelos.estadisticas import Estadisticas


class EstadisticasBMetro(Estadisticas):

    # Cuántos equipos entran al Torneo Reducido (posiciones 2..N),
    # detrás del puntero que asciende directo. 8 es el tamaño típico
    # de un octogonal (cuartos de 4 partidos). Ajustable.
    REDUCIDO_N = 9  # posiciones 2 a 9 (8 equipos)

    # Cuántos equipos descienden (últimos N de la tabla). Confirmado por
    # el reglamento de la temporada 2026: 2 descensos.
    DESCENSOS_N = 2

    # ------------------------------------------------------------------
    # Carga de datos (apunta a los archivos _bmetro en vez de a los de
    # Nacional -- todo lo demás de cargar_datos()/validar_datos() de la
    # clase base sirve tal cual porque el shape de las columnas es
    # idéntico).
    # ------------------------------------------------------------------
    def cargar_datos_bmetro(self):
        print("Leyendo datos de B Metropolitana...")

        self.resultados, self.fixture, self.tabla = data_access.league_data("bmetro")

        print(f"Resultados: {len(self.resultados)}")
        print(f"Fixture: {len(self.fixture)}")
        print(f"Tabla: {len(self.tabla)}")

        self._validar_datos_bmetro()

        # Las constantes PROMEDIO_GF_LOCAL_LIGA / PROMEDIO_GF_VISITANTE_LIGA
        # de la clase base (Estadisticas) están calibradas con los promedios
        # reales de Primera Nacional (1.35 / 1.05), pero B Metro es una
        # división de menos goles (promedio real ~1.06 / ~0.94). calcular_ratings()
        # ya usa el promedio real de la liga (calculado sobre self.resultados)
        # para normalizar los ratings de cada equipo, así que para que
        # simular_partido() sea consistente con esos ratings hay que pisar
        # las constantes heredadas con el promedio real de B Metro, en vez
        # de arrastrar las de Nacional. No cambia el resultado del modelo de
        # forma relevante (ya se probó empíricamente: ~62.1% -> ~62.5% en el
        # % puntero de Excursionistas), pero deja el motor calibrado
        # correctamente para esta liga.
        self.PROMEDIO_GF_LOCAL_LIGA = round(self.resultados["goles_local"].mean(), 3)
        self.PROMEDIO_GF_VISITANTE_LIGA = round(self.resultados["goles_visitante"].mean(), 3)
        print(
            f"Promedios de liga recalibrados para B Metro: "
            f"local={self.PROMEDIO_GF_LOCAL_LIGA}, visitante={self.PROMEDIO_GF_VISITANTE_LIGA}"
        )

    def _validar_datos_bmetro(self):
        if (self.tabla["zona"] != "Unica").any():
            raise ValueError(
                "tabla_bmetro.csv tiene valores de 'zona' distintos de 'Unica'. "
                "B Metropolitana es tabla única -- todas las filas deben decir "
                "zona=Unica (es el truco para reusar la clase base sin zonas reales)."
            )
        if len(self.tabla) != 22:
            raise ValueError(f"tabla_bmetro.csv debería tener 22 equipos, tiene {len(self.tabla)}")

        # Reusa el resto de las validaciones genéricas (columnas, tipos,
        # resultados/fixture disjuntos, etc.)
        self.validar_datos()

    def crear_equipos_bmetro(self):
        self.crear_equipos()  # heredado; agrupa todo bajo zona="Unica"

    # ------------------------------------------------------------------
    # Ascenso directo: en una tabla única, no hay "final cruzada" -- el
    # puntero asciende directo, sin partido de por medio.
    # ------------------------------------------------------------------
    def obtener_puntero(self, tabla_unica):
        return tabla_unica.iloc[0]["equipo"]

    # ------------------------------------------------------------------
    # Torneo Reducido de una sola tabla: posiciones 2..REDUCIDO_N.
    # Mismo patrón de bracket que jugar_reducido() de Nacional (cuartos
    # seedeados 2v9/3v8/4v7/5v6, semis re-seedeadas por posición de
    # tabla entre los ganadores, final a ida y vuelta), pero sin cruzar
    # zonas porque acá no las hay.
    # ------------------------------------------------------------------
    def jugar_reducido_bmetro(self, tabla_unica):
        equipos_orden = tabla_unica["equipo"].tolist()  # ya viene ordenada por posición

        def equipo(posicion):
            return equipos_orden[posicion - 1]

        diccionario = {"cuartos": [], "semis": [], "final": {}}

        cruces_cuartos = [
            (2, self.REDUCIDO_N),
            (3, self.REDUCIDO_N - 1),
            (4, self.REDUCIDO_N - 2),
            (5, self.REDUCIDO_N - 3),
        ]

        # NOTA: a diferencia del Reducido de Nacional (donde cuartos y semis
        # son partido único y solo la final es ida y vuelta), el reglamento
        # real del Torneo Reducido de B Metropolitana juega TODAS las rondas
        # -- cuartos, semis y final -- a ida y vuelta. Por eso acá se usa
        # jugar_serie_ida_vuelta() en las tres instancias, en vez de mezclar
        # con jugar_partido_unico() como en el Reducido de Nacional.
        ganadores_cuartos = []
        for pos_x, pos_y in cruces_cuartos:
            x, y = equipo(pos_x), equipo(pos_y)
            ganador, detalle = self.jugar_serie_ida_vuelta(x, y)
            diccionario["cuartos"].append(detalle)
            ganadores_cuartos.append(ganador)

        ganadores_set = set(ganadores_cuartos)
        seeds_semis = [nombre for nombre in equipos_orden if nombre in ganadores_set]

        finalistas = []
        for i, j in [(0, 3), (1, 2)]:
            x, y = seeds_semis[i], seeds_semis[j]
            ganador, detalle = self.jugar_serie_ida_vuelta(x, y)
            diccionario["semis"].append(detalle)
            finalistas.append(ganador)

        campeon, detalle_final = self.jugar_serie_ida_vuelta(finalistas[0], finalistas[1])
        diccionario["final"] = detalle_final

        return campeon, diccionario

    # ------------------------------------------------------------------
    # Monte Carlo de tabla única: mismo patrón que monte_carlo() de
    # Nacional (fase regular vectorizada + loop liviano por simulación
    # para ascenso/descenso/reducido), pero con un solo puntero.
    # ------------------------------------------------------------------
    def monte_carlo_bmetro(self, n_simulaciones=1000):
        print(f"\nCorriendo Monte Carlo B Metropolitana ({n_simulaciones} simulaciones)...")

        contador = {
            nombre: {"puntero": 0, "ascenso_directo": 0, "ascenso_reducido": 0, "descenso": 0,
                      "puntos_total": 0, "posicion_total": 0}
            for nombre in self.equipos
        }

        paso_reporte = max(1, n_simulaciones // 10)

        totales_vectorizados = self._simular_fase_regular_vectorizado(n_simulaciones)

        for i in range(n_simulaciones):
            totales_i = {
                nombre: {
                    "puntos": int(datos["puntos"][i]),
                    "gf": int(datos["gf"][i]),
                    "gc": int(datos["gc"][i]),
                }
                for nombre, datos in totales_vectorizados.items()
            }
            tablas = self._armar_tabla_final(totales_i)
            tabla_unica = tablas["Unica"]

            equipos_col = tabla_unica["equipo"].to_numpy()
            puntos_col = tabla_unica["puntos"].to_numpy()
            for posicion, (nombre_equipo, pts) in enumerate(zip(equipos_col, puntos_col), start=1):
                contador[nombre_equipo]["puntos_total"] += pts
                contador[nombre_equipo]["posicion_total"] += posicion

            puntero = self.obtener_puntero(tabla_unica)
            contador[puntero]["puntero"] += 1
            contador[puntero]["ascenso_directo"] += 1

            campeon_reducido, _ = self.jugar_reducido_bmetro(tabla_unica)
            contador[campeon_reducido]["ascenso_reducido"] += 1

            descendidos = tabla_unica.iloc[-self.DESCENSOS_N:]["equipo"].tolist()
            for descendido in descendidos:
                contador[descendido]["descenso"] += 1

            if (i + 1) % paso_reporte == 0:
                print(f"  {i + 1}/{n_simulaciones} simulaciones...")

        filas = []
        for nombre, datos in contador.items():
            ascenso_total = datos["ascenso_directo"] + datos["ascenso_reducido"]
            filas.append({
                "equipo": nombre,
                "%puntero": round(100 * datos["puntero"] / n_simulaciones, 1),
                "%ascenso_directo": round(100 * datos["ascenso_directo"] / n_simulaciones, 1),
                "%ascenso_reducido": round(100 * datos["ascenso_reducido"] / n_simulaciones, 1),
                "ascenso_total": round(100 * ascenso_total / n_simulaciones, 1),
                "descenso": round(100 * datos["descenso"] / n_simulaciones, 1),
            })
        resumen = pd.DataFrame(filas).sort_values("ascenso_total", ascending=False).reset_index(drop=True)
        resumen.index = resumen.index + 1

        filas_tabla = []
        for nombre, datos in contador.items():
            filas_tabla.append({
                "equipo": nombre,
                "puntos_prom": round(datos["puntos_total"] / n_simulaciones, 1),
                "posicion_prom": round(datos["posicion_total"] / n_simulaciones, 1),
            })
        tabla_esperada = pd.DataFrame(filas_tabla).sort_values("posicion_prom").reset_index(drop=True)
        tabla_esperada.index = tabla_esperada.index + 1

        print("Monte Carlo B Metropolitana terminado.")
        return resumen, tabla_esperada
