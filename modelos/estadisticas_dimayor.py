# -*- coding: utf-8 -*-
"""
estadisticas_dimayor.py

Motor de simulación para la Liga BetPlay Dimayor (Colombia), Torneo
Clausura. Calcado de la arquitectura de estadisticas_ligapro.py (Fase
Inicial -> Fase Final con fixture generado dinámicamente), con dos
diferencias de reglamento importantes:

  1. Esta página NO simula el Torneo Apertura (ya terminó en la vida
     real) -- su tabla final se muestra tal cual la trae el scraper,
     como sección informativa, y nunca pasa por este motor. Acá se
     arranca directo en el Torneo Clausura, con la tabla real
     actualizada por el scraper (tabla_dimayor.csv, zona "Clausura").

  2. A diferencia del Hexagonal Campeón de LigaPro (que ARRASTRA los
     puntos de la Fase Inicial, Art. 10.a de su reglamento), los
     Cuadrangulares de Dimayor arrancan en CERO -- no hay arrastre de
     puntos de la fase de todos-contra-todos. Fuente: reglamento vigente
     de Categoría Primera A / DIMAYOR (confirmado también por la
     cobertura de temporadas recientes, ver Wikipedia "20XX Liga
     DIMAYOR": "semi-final stage (cuadrangulares) played by the top
     eight teams from the previous stage").

FORMATO (temporada 2026, Torneo Clausura):

  FASE TODOS CONTRA TODOS (20 equipos, ida solamente -- NO ida y
  vuelta completo dentro del Clausura en sí; el "ida y vuelta" real de
  la temporada colombiana se reparte entre Apertura y Finalización como
  dos torneos independientes, cada uno de una sola rueda de 19 fechas):
    - 19 fechas, tabla única (zona "Clausura").
    - Desempate: puntos -> diferencia de gol -> goles a favor (mismo
      criterio que ya usa el resto del proyecto en
      Estadisticas._armar_tabla_final -- el reglamento de DIMAYOR
      agrega más criterios (goles como visitante, punto average, etc.)
      que este motor no implementa, igual que LigaPro/Brasileirão).

  CUADRANGULARES (clasifican los 8 primeros de la fase regular):
    - Grupo A: posiciones 1°, 4°, 5°, 8° de la fase regular. El 1° de
      la fase regular es cabeza de serie del grupo.
    - Grupo B: posiciones 2°, 3°, 6°, 7° de la fase regular. El 2° de
      la fase regular es cabeza de serie del grupo.
    - Cada grupo: todos contra todos ida y vuelta (6 fechas, 6 partidos
      por equipo), arrancando en 0 puntos.

  FINAL:
    - Ganador Grupo A vs. ganador Grupo B, ida y vuelta.
    - Si hay empate en el marcador global: campeón por penales.

Arquitectura: se reusa el mismo mecanismo de "zona dinámica" +
fixture_generator que ya usa LigaPro. La diferencia de arrastre de
puntos (acá NO hay) se resuelve simplemente NO llamando a
_sincronizar_equipos_desde_tabla() antes de armar los cuadrangulares --
en cambio, se resetean puntos/gf/gc a 0 para los 8 clasificados justo
al asignarles su zona de cuadrangular.
"""
import numpy as np
import pandas as pd

import data_access
import rutas
from modelos.estadisticas import Estadisticas
from fixture_generator import generar_fixture_ida_vuelta
from calcular_tabla_dimayor import construir_tabla_apertura

ZONA_CLAUSURA = "Clausura"
ZONA_CUADRANGULAR_A = "Cuadrangular A"
ZONA_CUADRANGULAR_B = "Cuadrangular B"

N_EQUIPOS_DIMAYOR = 20
CLASIFICADOS_CUADRANGULARES = 8

# Cortes de la fase regular (posición final, 1-indexed) que arman cada
# grupo de cuadrangulares. Reglamento DIMAYOR: 1-4-5-8 al Grupo A
# (cabeza de serie: el 1° de la fase regular), 2-3-6-7 al Grupo B
# (cabeza de serie: el 2°).
POSICIONES_GRUPO_A = (1, 4, 5, 8)
POSICIONES_GRUPO_B = (2, 3, 6, 7)


class EstadisticasDimayor(Estadisticas):

    # ------------------------------------------------------------------
    # Carga de datos
    # ------------------------------------------------------------------
    def cargar_datos_dimayor(self):
        print("Leyendo datos de Liga BetPlay Dimayor (Torneo Clausura)...")

        self.resultados, self.fixture, self.tabla = data_access.league_data("dimayor")

        # Tabla de promedios (Art. 32 del reglamento DIMAYOR vigente):
        # puntos por partido de los últimos ~3 años. A diferencia de LPF,
        # Colombia desciende DIRECTO a los 2 peores promedios -- sin el
        # sistema doble de la tabla anual de Argentina.
        self.promedios_historicos = data_access.dimayor_average_history_df()

        print(f"Resultados: {len(self.resultados)}")
        print(f"Fixture: {len(self.fixture)}")
        print(f"Tabla: {len(self.tabla)}")

        self._validar_datos_dimayor()

        # Igual que Brasileirão/LigaPro: recalibrar el promedio de gol de
        # liga con los datos reales del Clausura en curso, en vez de
        # arrastrar el default (calibrado para Primera Nacional).
        if len(self.resultados) > 0:
            self.PROMEDIO_GF_LOCAL_LIGA = round(self.resultados["goles_local"].mean(), 3)
            self.PROMEDIO_GF_VISITANTE_LIGA = round(self.resultados["goles_visitante"].mean(), 3)
            print(
                f"Promedios de liga recalibrados para Dimayor: "
                f"local={self.PROMEDIO_GF_LOCAL_LIGA}, visitante={self.PROMEDIO_GF_VISITANTE_LIGA}"
            )
        else:
            print("Sin partidos jugados todavía: se mantiene el promedio de liga por default.")

    def _validar_datos_dimayor(self):
        if len(self.tabla) != N_EQUIPOS_DIMAYOR:
            raise ValueError(
                f"tabla_dimayor.csv tiene {len(self.tabla)} equipos, se esperan "
                f"{N_EQUIPOS_DIMAYOR} (Liga BetPlay siempre tiene 20 equipos) -- "
                "revisar si el archivo está roto/vacío/duplicado."
            )
        self.validar_datos()

    def crear_equipos_dimayor(self):
        self.crear_equipos()  # heredado

    # ------------------------------------------------------------------
    # Transición Fase Regular (Clausura) -> Cuadrangulares
    # ------------------------------------------------------------------
    def _en_fase_clausura(self) -> bool:
        """True si todavía no se dividió en los 2 grupos de
        cuadrangulares (o sea: todos los equipos siguen en zona
        "Clausura")."""
        zonas_actuales = {e.zona for e in self.equipos.values()}
        return zonas_actuales == {ZONA_CLAUSURA}

    def _dividir_en_cuadrangulares(self, tabla_clausura: pd.DataFrame):
        """Reasigna la zona de los 8 clasificados según su posición
        final en la fase regular (Grupo A: 1-4-5-8, Grupo B: 2-3-6-7) y
        RESETEA sus puntos/gf/gc a 0 -- a diferencia de LigaPro, acá los
        cuadrangulares NO arrastran puntos de la fase regular. Los 12
        equipos eliminados quedan con su zona "Clausura" (no se tocan).

        Devuelve {"grupo_a": [equipos...], "grupo_b": [equipos...]},
        cada lista en el orden de posición de fase regular (ese orden
        es el que usa fixture_generator, no afecta el resultado)."""
        top8 = tabla_clausura["equipo"].tolist()[:CLASIFICADOS_CUADRANGULARES]
        if len(top8) < CLASIFICADOS_CUADRANGULARES:
            raise ValueError(
                f"La tabla de fase regular sólo tiene {len(top8)} equipos, "
                f"se necesitan {CLASIFICADOS_CUADRANGULARES} para armar los cuadrangulares."
            )

        grupo_a = [top8[p - 1] for p in POSICIONES_GRUPO_A]
        grupo_b = [top8[p - 1] for p in POSICIONES_GRUPO_B]

        for nombre in grupo_a:
            equipo_obj = self.equipos[nombre]
            equipo_obj.zona = ZONA_CUADRANGULAR_A
            equipo_obj.puntos = 0
            equipo_obj.goles_favor = 0
            equipo_obj.goles_contra = 0
        for nombre in grupo_b:
            equipo_obj = self.equipos[nombre]
            equipo_obj.zona = ZONA_CUADRANGULAR_B
            equipo_obj.puntos = 0
            equipo_obj.goles_favor = 0
            equipo_obj.goles_contra = 0

        return {ZONA_CUADRANGULAR_A: grupo_a, ZONA_CUADRANGULAR_B: grupo_b}

    def _generar_fixture_cuadrangulares(self, grupos: dict) -> pd.DataFrame:
        """Ida y vuelta dentro de cada grupo de 4 (6 fechas, 6 partidos
        por equipo), mismo generador que usa LigaPro/Federal A."""
        filas = []
        for equipos_grupo in grupos.values():
            partidos = generar_fixture_ida_vuelta(equipos_grupo)
            for p in partidos:
                filas.append({
                    "fecha": "",
                    "jornada": p.jornada,
                    "equipo_local": p.equipo_local,
                    "equipo_visitante": p.equipo_visitante,
                })
        return pd.DataFrame(filas, columns=["fecha", "jornada", "equipo_local", "equipo_visitante"])

    # ------------------------------------------------------------------
    # Final (ida y vuelta + penales)
    # ------------------------------------------------------------------
    def jugar_final_dimayor(self, finalista_a, finalista_b):
        """Simula la final ida y vuelta entre el ganador del Grupo A y
        el ganador del Grupo B (a diferencia de jugar_final_ascenso() de
        la clase base, que es a partido único con alargue). Sin regla de
        gol de visitante -- si el global queda igualado tras los dos
        partidos, se define directo por penales (50/50), igual que hace
        el resto del proyecto para cualquier definición por penales.

        Devuelve (campeon, subcampeon, detalle_dict)."""
        gl_ida, gv_ida = self.simular_partido(finalista_a, finalista_b)
        # Vuelta: se invierte la localía.
        gl_vuelta, gv_vuelta = self.simular_partido(finalista_b, finalista_a)

        goles_a = gl_ida + gv_vuelta
        goles_b = gv_ida + gl_vuelta

        detalle = {
            "ida": {"local": finalista_a, "visitante": finalista_b, "marcador": [gl_ida, gv_ida]},
            "vuelta": {"local": finalista_b, "visitante": finalista_a, "marcador": [gl_vuelta, gv_vuelta]},
            "global": {finalista_a: goles_a, finalista_b: goles_b},
            "definicion_por_penales": False,
            "texto": (
                f"Ida: {finalista_a} {gl_ida}-{gv_ida} {finalista_b} | "
                f"Vuelta: {finalista_b} {gl_vuelta}-{gv_vuelta} {finalista_a} | "
                f"Global: {finalista_a} {goles_a}-{goles_b} {finalista_b}"
            ),
        }

        if goles_a != goles_b:
            campeon, subcampeon = (finalista_a, finalista_b) if goles_a > goles_b else (finalista_b, finalista_a)
            return campeon, subcampeon, detalle

        campeon, subcampeon = (finalista_a, finalista_b) if np.random.random() < 0.5 else (finalista_b, finalista_a)
        detalle["definicion_por_penales"] = True
        detalle["texto"] += " (definido por penales)"
        return campeon, subcampeon, detalle

    def _sincronizar_equipos_desde_tabla(self, tabla: pd.DataFrame):
        """Mismo patrón que LigaPro: simular_fase_regular() no toca
        self.equipos, así que hace falta escribir la tabla final de la
        fase regular DE VUELTA antes de resetear/reasignar zonas para
        los cuadrangulares (sólo se usa para dejar el estado de fase
        regular consistente antes de la transición; el reseteo a 0 de
        los 8 clasificados pasa aparte, en _dividir_en_cuadrangulares)."""
        for fila in tabla.itertuples():
            equipo_obj = self.equipos[fila.equipo]
            equipo_obj.puntos = int(fila.puntos)
            equipo_obj.goles_favor = int(fila.gf)
            equipo_obj.goles_contra = int(fila.gc)

    # ------------------------------------------------------------------
    # Simulación de la temporada completa (Clausura + Cuadrangulares + Final)
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Tabla de promedios (descenso) -- Art. 32 del reglamento DIMAYOR:
    # "Los dos equipos con el promedio más bajo en los tres últimos años
    # descienden a la Categoría B." Solo cuenta la fase de todos-contra-
    # todos de cada semestre (Apertura/Clausura, o "Liga BetPlay I/II");
    # los cuadrangulares y la final NO suman para el promedio.
    # ------------------------------------------------------------------
    def _partidos_2026_dimayor_por_equipo(self):
        """Partidos jugados en 2026 (Apertura, ya terminado, + Clausura,
        jugado o pendiente) por equipo -- se suman a los históricos de
        promedios_dimayor.csv (2024+2025 completos). Los partidos
        pendientes del Clausura se simulan pero cuentan igual para el
        promedio real de la temporada, mismo criterio que usa LPF para
        su Clausura."""
        apertura_pj = pd.DataFrame(construir_tabla_apertura()).set_index("equipo")["partidos_jugados"]
        clausura_pj = pd.concat([
            self.fixture["equipo_local"], self.fixture["equipo_visitante"],
            self.resultados["equipo_local"], self.resultados["equipo_visitante"],
        ]).value_counts()
        return apertura_pj + clausura_pj.reindex(apertura_pj.index).fillna(0)

    def calcular_tabla_promedios(self, tabla_fase_regular_clausura):
        """Tabla de promedios: puntos por partido jugado en las últimas
        ~3 temporadas (2024 + 2025 completos, más el 2026 en curso:
        Apertura ya jugado + la fase de todos-contra-todos del Clausura
        que se le pase -- real si ya terminó, con partidos simulados si
        todavía está en curso). Los recién ascendidos (0 históricos en
        promedios_dimayor.csv) solo computan desde su propio ascenso,
        igual que LPF. NO incluye cuadrangulares ni la final: esas fases
        no cuentan para el promedio, por reglamento."""
        apertura = pd.DataFrame(construir_tabla_apertura())
        partidos_2026 = self._partidos_2026_dimayor_por_equipo()

        prom = self.promedios_historicos.merge(
            apertura[["equipo", "puntos"]].rename(columns={"puntos": "puntos_apertura"}),
            on="equipo",
        )
        prom = prom.merge(
            tabla_fase_regular_clausura[["equipo", "puntos"]].rename(columns={"puntos": "puntos_clausura"}),
            on="equipo",
        )
        prom["puntos_totales"] = prom["puntos_historicos"] + prom["puntos_apertura"] + prom["puntos_clausura"]
        prom["partidos_totales"] = prom["partidos_historicos"] + prom["equipo"].map(partidos_2026)
        prom["promedio"] = prom["puntos_totales"] / prom["partidos_totales"]

        prom = prom.sort_values("promedio", ascending=False).reset_index(drop=True)
        prom.index = prom.index + 1
        return prom[["equipo", "puntos_totales", "partidos_totales", "promedio"]]

    def calcular_descensos_promedio(self, tabla_promedios):
        """Los 2 equipos con peor promedio descienden -- directo, sin el
        sistema doble de desempate por tabla anual que usa Argentina."""
        return tabla_promedios.tail(2)["equipo"].tolist()

    def simular_temporada_dimayor(self):
        """Devuelve un dict con:
          - "fase_regular": DataFrame de la tabla final de la fase
            regular del Clausura (o None si al llamar este método la
            temporada YA estaba dividida en cuadrangulares -- mismo
            comportamiento que LigaPro con "fase_inicial").
          - "grupo_a" / "grupo_b": DataFrames de cada cuadrangular.
          - "campeon" / "subcampeon": nombres.
          - "detalle_final": dict de jugar_final_dimayor().
        """
        if self._en_fase_clausura():
            tablas_fr = self.simular_fase_regular()
            tabla_fase_regular = tablas_fr[ZONA_CLAUSURA]

            # Importante: calcular la tabla de promedios ACÁ, con
            # self.fixture todavía siendo el del Clausura -- si se calcula
            # después de _generar_fixture_cuadrangulares() de más abajo,
            # _partidos_2026_dimayor_por_equipo() contaría los partidos
            # de los cuadrangulares (o ninguno, para los que no
            # clasificaron) en vez de los del Clausura real.
            tabla_promedios = self.calcular_tabla_promedios(tabla_fase_regular)
            descensos_promedio = self.calcular_descensos_promedio(tabla_promedios)

            self._sincronizar_equipos_desde_tabla(tabla_fase_regular)
            grupos = self._dividir_en_cuadrangulares(tabla_fase_regular)
            self.fixture = self._generar_fixture_cuadrangulares(grupos)
            self._pares_fixture_cache = None  # invalidar cache de _pares_fixture()

            tablas_cuad = self.simular_fase_regular()
        else:
            tabla_fase_regular = None
            # Igual que "fase_regular": si la temporada YA estaba
            # dividida en cuadrangulares al llamar este método, no hay
            # una tabla de fase regular de ESTA corrida para calcular el
            # promedio -- se devuelve None (mismo criterio de "no
            # disponible en este caso borde" que ya usa el resto del
            # proyecto).
            tabla_promedios = None
            descensos_promedio = None
            tablas_cuad = self.simular_fase_regular()

        grupo_a = tablas_cuad[ZONA_CUADRANGULAR_A]
        grupo_b = tablas_cuad[ZONA_CUADRANGULAR_B]

        ganador_a = grupo_a.iloc[0]["equipo"]
        ganador_b = grupo_b.iloc[0]["equipo"]
        campeon, subcampeon, detalle_final = self.jugar_final_dimayor(ganador_a, ganador_b)

        return {
            "fase_regular": tabla_fase_regular,
            "grupo_a": grupo_a,
            "grupo_b": grupo_b,
            "campeon": campeon,
            "subcampeon": subcampeon,
            "detalle_final": detalle_final,
            "tabla_promedios": tabla_promedios,
            "descensos_promedio": descensos_promedio,
        }

    # ------------------------------------------------------------------
    # Monte Carlo
    # ------------------------------------------------------------------
    def monte_carlo_dimayor(self, n_simulaciones=1000):
        """Monte Carlo vectorizado, mismo patrón que monte_carlo_ligapro():
        el bloque grande (fase regular del Clausura, ~equipos x 19 fechas
        de partidos pendientes) se resuelve vectorizado una sola vez para
        las n_simulaciones juntas; los cuadrangulares + la final (mucho
        más chicos, y dependientes de qué 8 equipos clasificaron en CADA
        simulación individual) se resuelven partido a partido dentro del
        loop, arrancando de esos totales ya vectorizados.

        Cuenta, por equipo:
          - % campeón
          - % clasificó a cuadrangulares (Top 8)
          - % posición final de la fase regular (1..20), para poder
            mostrar la distribución completa de probabilidad de
            posición que pide la interfaz.
        """
        print(f"\nCorriendo Monte Carlo Dimayor ({n_simulaciones} simulaciones)...")

        estado_inicial = {
            nombre: {
                "puntos": e.puntos, "gf": e.goles_favor, "gc": e.goles_contra, "zona": e.zona,
            }
            for nombre, e in self.equipos.items()
        }
        fixture_original = self.fixture.copy()
        en_fase_clausura = self._en_fase_clausura()

        nombres_equipos = list(self.equipos.keys())
        contador = {
            nombre: {
                "campeon": 0, "subcampeon": 0, "cuadrangulares": 0,
                "puntos_total": 0, "posicion_total": 0,
                "posiciones": {p: 0 for p in range(1, N_EQUIPOS_DIMAYOR + 1)},
            }
            for nombre in nombres_equipos
        }

        # Paso vectorizado: resuelve todos los partidos pendientes de la
        # fase regular (o de los cuadrangulares directo, si la temporada
        # real ya está dividida) para las n_simulaciones de una sola vez.
        totales_vectorizados = self._simular_fase_regular_vectorizado(n_simulaciones)

        paso_reporte = max(1, n_simulaciones // 10)

        for i in range(n_simulaciones):
            if en_fase_clausura:
                # La iteración anterior dejó self.equipos[...].zona en
                # Cuadrangular A/B -- hay que devolverla a "Clausura"
                # antes de _armar_tabla_final(), o esta vuelta agruparía
                # por la zona de la simulación pasada.
                for nombre, datos in estado_inicial.items():
                    self.equipos[nombre].zona = datos["zona"]

            totales_i = {
                nombre: {
                    "puntos": int(datos["puntos"][i]),
                    "gf": int(datos["gf"][i]),
                    "gc": int(datos["gc"][i]),
                }
                for nombre, datos in totales_vectorizados.items()
            }
            tablas_zona = self._armar_tabla_final(totales_i)

            if en_fase_clausura:
                tabla_fase_regular = tablas_zona[ZONA_CLAUSURA]
                for posicion, fila in enumerate(tabla_fase_regular.itertuples(), start=1):
                    contador[fila.equipo]["posiciones"][posicion] += 1
                    contador[fila.equipo]["puntos_total"] += fila.puntos
                    contador[fila.equipo]["posicion_total"] += posicion

                self._sincronizar_equipos_desde_tabla(tabla_fase_regular)
                grupos = self._dividir_en_cuadrangulares(tabla_fase_regular)
                self.fixture = self._generar_fixture_cuadrangulares(grupos)
                self._pares_fixture_cache = None
                tablas_cuad_zona = self.simular_fase_regular()
                grupo_a = tablas_cuad_zona[ZONA_CUADRANGULAR_A]
                grupo_b = tablas_cuad_zona[ZONA_CUADRANGULAR_B]

                clasificados = grupos[ZONA_CUADRANGULAR_A] + grupos[ZONA_CUADRANGULAR_B]
            else:
                grupo_a = tablas_zona[ZONA_CUADRANGULAR_A]
                grupo_b = tablas_zona[ZONA_CUADRANGULAR_B]
                clasificados = grupo_a["equipo"].tolist() + grupo_b["equipo"].tolist()

            for nombre_equipo in clasificados:
                contador[nombre_equipo]["cuadrangulares"] += 1

            ganador_a = grupo_a.iloc[0]["equipo"]
            ganador_b = grupo_b.iloc[0]["equipo"]
            campeon, subcampeon, _detalle = self.jugar_final_dimayor(ganador_a, ganador_b)
            contador[campeon]["campeon"] += 1
            contador[subcampeon]["subcampeon"] += 1

            if (i + 1) % paso_reporte == 0:
                print(f"  {i + 1}/{n_simulaciones} simulaciones...")

        # Restaurar el estado real (post-loop).
        for nombre, datos in estado_inicial.items():
            self.equipos[nombre].puntos = datos["puntos"]
            self.equipos[nombre].goles_favor = datos["gf"]
            self.equipos[nombre].goles_contra = datos["gc"]
            self.equipos[nombre].zona = datos["zona"]
        self.fixture = fixture_original
        self._pares_fixture_cache = None

        filas_resumen = []
        for nombre, datos in contador.items():
            filas_resumen.append({
                "equipo": nombre,
                "%campeon": round(100 * datos["campeon"] / n_simulaciones, 1),
                "%subcampeon": round(100 * datos["subcampeon"] / n_simulaciones, 1),
                "%cuadrangulares": round(100 * datos["cuadrangulares"] / n_simulaciones, 1),
            })
        resumen = pd.DataFrame(filas_resumen).sort_values("%campeon", ascending=False).reset_index(drop=True)
        resumen.index = resumen.index + 1

        filas_tabla = []
        for nombre, datos in contador.items():
            filas_tabla.append({
                "equipo": nombre,
                "puntos_prom_clausura": round(datos["puntos_total"] / n_simulaciones, 1),
                "posicion_prom_clausura": round(datos["posicion_total"] / n_simulaciones, 1),
            })
        tabla_esperada = pd.DataFrame(filas_tabla).sort_values("posicion_prom_clausura").reset_index(drop=True)
        tabla_esperada.index = tabla_esperada.index + 1

        # Matriz de probabilidad de posición final de la fase regular
        # (1..20), para el heatmap de "probabilidad de terminar en cada
        # posición" que pide la interfaz.
        filas_matriz = []
        for nombre in nombres_equipos:
            fila = {"equipo": nombre}
            for pos in range(1, N_EQUIPOS_DIMAYOR + 1):
                fila[f"pos_{pos}"] = round(100 * contador[nombre]["posiciones"][pos] / n_simulaciones, 1)
            filas_matriz.append(fila)
        matriz_posiciones = pd.DataFrame(filas_matriz)

        print("Monte Carlo Dimayor terminado.")
        return resumen, tabla_esperada, matriz_posiciones
