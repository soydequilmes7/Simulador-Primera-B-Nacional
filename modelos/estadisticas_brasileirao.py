# -*- coding: utf-8 -*-
"""
estadisticas_brasileirao.py

Motor de simulación para el Campeonato Brasileiro Série A, temporada
2026 (Brasileirão).

Es la liga MÁS SIMPLE del proyecto en términos de formato: 20 equipos,
todos contra todos ida y vuelta (38 fechas), tabla única, SIN zonas y
SIN ningún tipo de playoff/reducido -- el campeón es directamente el
puntero al final de la fecha 38. Se sigue el mismo truco que B Metro /
Nacional: todos los equipos comparten zona="Unica" en tabla_brasileirao.csv
para reusar Estadisticas.crear_equipos() / simular_fase_regular() /
_armar_tabla_final() sin tocarles una línea.

Lo que SÍ es propio de esta liga (y no existe en ninguna de AFA) son
las zonas de clasificación por POSICIÓN final en la tabla, sin
partidos de por medio:

  - Posiciones 1-4:   Copa Libertadores, fase de grupos directa.
  - Posiciones 5-6:   Copa Libertadores, fase previa (repechaje).
  - Posiciones 7-12:  Copa Sudamericana.
  - Posiciones 17-20 (últimos 4): descenso a la Série B.

Los cortes de arriba están confirmados para la temporada 2026 (se
verificó al armar este módulo); si la CBF/Conmebol cambian el número
de cupos de un año a otro, ajustar las constantes de clase de acá
abajo -- el resto del motor no necesita tocarse.

A diferencia de B Metro, acá NO hay:
  - jugar_reducido_brasileirao(): no existe el Torneo Reducido, no hay
    segunda vía de nada. Clasificación = tabla final, punto.
  - jugar_final_ascenso(): no hay final cruzada entre zonas (una sola
    zona, sin nada que cruzar).

monte_carlo_brasileirao() reemplaza a monte_carlo() de la clase base
con las probabilidades de estas 4 franjas en vez de ascenso/descenso
estilo AFA.
"""
import numpy as np
import pandas as pd

import data_access
import rutas
from modelos.estadisticas import Estadisticas


class EstadisticasBrasileirao(Estadisticas):

    # Cortes de tabla (posición final, 1-indexed, inclusive) para cada
    # zona de clasificación continental / descenso. Confirmados para
    # la temporada 2026: top 4 a Libertadores directo, 5-6 a la previa,
    # 7-12 a Sudamericana, últimos 4 descienden.
    LIBERTADORES_DIRECTA_N = 4    # posiciones 1..4
    LIBERTADORES_PREVIA_N = 6     # posiciones 5..6 (hasta la 6, exclusive de la directa)
    SUDAMERICANA_N = 12           # posiciones 7..12
    DESCENSOS_N = 4               # últimos 4 de la tabla (posiciones 17..20)

    # ------------------------------------------------------------------
    # Carga de datos
    # ------------------------------------------------------------------
    def cargar_datos_brasileirao(self):
        print("Leyendo datos del Brasileirão Série A...")

        self.resultados, self.fixture, self.tabla = data_access.league_data("brasileirao")

        print(f"Resultados: {len(self.resultados)}")
        print(f"Fixture: {len(self.fixture)}")
        print(f"Tabla: {len(self.tabla)}")

        self._validar_datos_brasileirao()

        # Igual que en B Metro: las constantes PROMEDIO_GF_LOCAL_LIGA /
        # PROMEDIO_GF_VISITANTE_LIGA heredadas de la clase base están
        # calibradas para Primera Nacional (fútbol argentino de
        # ascenso). El Brasileirão es una liga de otro país con otro
        # promedio de goles, así que hay que recalibrar con los datos
        # reales de la temporada en curso en vez de arrastrar el
        # default. Si todavía no se jugó nada, se mantiene el default
        # heredado (no hay de dónde recalibrar).
        if len(self.resultados) > 0:
            self.PROMEDIO_GF_LOCAL_LIGA = round(self.resultados["goles_local"].mean(), 3)
            self.PROMEDIO_GF_VISITANTE_LIGA = round(self.resultados["goles_visitante"].mean(), 3)
            print(
                f"Promedios de liga recalibrados para Brasileirão: "
                f"local={self.PROMEDIO_GF_LOCAL_LIGA}, visitante={self.PROMEDIO_GF_VISITANTE_LIGA}"
            )
        else:
            print("Sin partidos jugados todavía: se mantiene el promedio de liga por default.")

    def _validar_datos_brasileirao(self):
        if (self.tabla["zona"] != "Unica").any():
            raise ValueError(
                "tabla_brasileirao.csv tiene valores de 'zona' distintos de 'Unica'. "
                "El Brasileirão es tabla única -- todas las filas deben decir "
                "zona=Unica (es el truco para reusar la clase base sin zonas reales)."
            )
        if len(self.tabla) != 20:
            raise ValueError(
                f"tabla_brasileirao.csv tiene {len(self.tabla)} equipos, se esperan "
                "20 (Série A siempre tiene 20 equipos) -- revisar si el archivo "
                "está roto/vacío/duplicado, o si hubo un descenso/ascenso mal cargado."
            )

        # Reusa el resto de las validaciones genéricas (columnas, tipos,
        # resultados/fixture disjuntos, etc.)
        self.validar_datos()

    def crear_equipos_brasileirao(self):
        self.crear_equipos()  # heredado; agrupa todo bajo zona="Unica"

    # ------------------------------------------------------------------
    # Zonas de clasificación por posición final. Sin partidos de por
    # medio -- a diferencia de AFA, la CBF no juega ningún tipo de
    # definición extra por posición.
    # ------------------------------------------------------------------
    def obtener_puntero(self, tabla_unica):
        return tabla_unica.iloc[0]["equipo"]

    def clasificar_zonas(self, tabla_unica):
        """Devuelve un dict con las 4 franjas de la tabla ya armada,
        en orden de posición. Útil tanto para el reporte de una
        simulación puntual (main_brasileirao.py) como, entre corridas,
        para inspeccionar una tabla ya jugada de verdad."""
        equipos_orden = tabla_unica["equipo"].tolist()
        return {
            "libertadores_directa": equipos_orden[:self.LIBERTADORES_DIRECTA_N],
            "libertadores_previa": equipos_orden[self.LIBERTADORES_DIRECTA_N:self.LIBERTADORES_PREVIA_N],
            "sudamericana": equipos_orden[self.LIBERTADORES_PREVIA_N:self.SUDAMERICANA_N],
            "descenso": equipos_orden[-self.DESCENSOS_N:],
        }

    # ------------------------------------------------------------------
    # Monte Carlo de tabla única sin playoffs: mismo patrón vectorizado
    # que monte_carlo_bmetro(), pero contando las 4 franjas de
    # clasificación por posición en vez de ascenso directo/reducido.
    # ------------------------------------------------------------------
    def monte_carlo_brasileirao(self, n_simulaciones=1000):
        print(f"\nCorriendo Monte Carlo Brasileirão ({n_simulaciones} simulaciones)...")

        contador = {
            nombre: {
                "campeon": 0,
                "libertadores_directa": 0,
                "libertadores_previa": 0,
                "sudamericana": 0,
                "descenso": 0,
                "puntos_total": 0,
                "posicion_total": 0,
            }
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

            contador[equipos_col[0]]["campeon"] += 1

            zonas = self.clasificar_zonas(tabla_unica)
            for nombre_equipo in zonas["libertadores_directa"]:
                contador[nombre_equipo]["libertadores_directa"] += 1
            for nombre_equipo in zonas["libertadores_previa"]:
                contador[nombre_equipo]["libertadores_previa"] += 1
            for nombre_equipo in zonas["sudamericana"]:
                contador[nombre_equipo]["sudamericana"] += 1
            for nombre_equipo in zonas["descenso"]:
                contador[nombre_equipo]["descenso"] += 1

            if (i + 1) % paso_reporte == 0:
                print(f"  {i + 1}/{n_simulaciones} simulaciones...")

        filas = []
        for nombre, datos in contador.items():
            libertadores_total = datos["libertadores_directa"] + datos["libertadores_previa"]
            filas.append({
                "equipo": nombre,
                "%campeon": round(100 * datos["campeon"] / n_simulaciones, 1),
                "%libertadores_directa": round(100 * datos["libertadores_directa"] / n_simulaciones, 1),
                "%libertadores_previa": round(100 * datos["libertadores_previa"] / n_simulaciones, 1),
                "libertadores_total": round(100 * libertadores_total / n_simulaciones, 1),
                "%sudamericana": round(100 * datos["sudamericana"] / n_simulaciones, 1),
                "%descenso": round(100 * datos["descenso"] / n_simulaciones, 1),
            })
        resumen = pd.DataFrame(filas).sort_values("%campeon", ascending=False).reset_index(drop=True)
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

        print("Monte Carlo Brasileirão terminado.")
        return resumen, tabla_esperada
