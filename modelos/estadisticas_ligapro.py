# -*- coding: utf-8 -*-
"""
estadisticas_ligapro.py

Motor de simulación para LigaPro Serie A (Ecuador), temporada 2026.

A diferencia de Brasileirão (tabla única, clasificación por posición
final sin partidos de por medio) o de las ligas AFA (ascenso/descenso
por zona real), LigaPro tiene un formato de DOS FASES con arrastre de
puntos, según el Reglamento de Competiciones vigente (Art. 8-10) y el
cambio de formato aprobado por el Consejo de Presidentes de LigaPro el
15/12/2025 para la temporada 2026 (fuente: Wikipedia "2026 LigaPro Serie
A", Primicias, Extra.ec -- ver nota más abajo sobre por qué NO se siguió
el PDF del reglamento a secas):

  FASE INICIAL (16 equipos, todos contra todos ida y vuelta, 30 fechas):
    - Se juega una tabla única (zona "FaseInicial").
    - A diferencia de la temporada 2025 (y de lo que todavía dice el
      Art. 9.c del PDF de reglamento vigente, edición marzo 2025), el 1°
      de esta fase YA NO tiene cupo asegurado a Copa Libertadores como
      "Ecuador 2" -- ese privilegio se eliminó para 2026. Sólo define en
      qué grupo de la Fase Final juega cada equipo.

  FASE FINAL (arranca con los puntos de la Fase Inicial ya sumados,
  Art. 10.a del reglamento -- este punto SÍ sigue vigente en 2026):
    - HEXAGONAL CAMPEÓN (posiciones 1-6 de la Fase Inicial): todos
      contra todos ida y vuelta (10 fechas). Define el campeón y reparte
      3 cupos a Copa Libertadores (1°-3°) y 3 a Copa Sudamericana
      (4°-6°). El campeón juega además la Supercopa Ecuador.
    - CUADRANGULAR SUDAMERICANA (posiciones 7-10): todos contra todos
      ida y vuelta (6 fechas). El 1° obtiene el cupo restante a Copa
      Sudamericana (Ecuador 4). Este es el cambio de formato más grande
      de 2026: en 2025 este grupo era un HEXAGONAL de 6 equipos
      (posiciones 7-12); para 2026 se achicó a un cuadrangular de 4
      (posiciones 7-10).
    - HEXAGONAL DESCENSO (posiciones 11-16): todos contra todos ida y
      vuelta (10 fechas). Los últimos 2 descienden a Serie B. En 2025
      este grupo también era distinto (cuadrangular de 4, posiciones
      13-16) -- para 2026 pasó a ser hexagonal de 6.

NOTA IMPORTANTE sobre la fuente de este formato: el PDF oficial del
Reglamento de Competiciones de LigaPro (ed. marzo 2025, el más reciente
públicamente disponible al armar este módulo) todavía describe el
formato VIEJO -- dos hexagonales de 6 (posiciones 1-6 y 7-12) más un
cuadrangular de descenso de 4 (posiciones 13-16), y el cupo directo a
Libertadores para el puntero de la Fase Inicial. Ese reglamento no
estaba actualizado todavía a la fecha de esta investigación con la
resolución del 15/12/2025. Los cortes de grupo salen de la cobertura
periodística de esa resolución (Wikipedia "2026 LigaPro Serie A",
Primicias, Extra.ec, OneFootball).

REPARTO DE CUPOS CONMEBOL (confirmado, fuente: Wikipedia "Serie A de
Ecuador 2026", sección de clasificación a torneos internacionales):

  Copa Libertadores 2027 (4 cupos, de los cuales sólo 3 salen de la
  tabla de LigaPro -- el 4° es de otro torneo):
    - Ecuador 1: Campeón (1° del Hexagonal Campeón).
    - Ecuador 2: Subcampeón (2° del Hexagonal Campeón).
    - Ecuador 3: Tercer puesto (3° del Hexagonal Campeón).
    - Ecuador 4: campeón, subcampeón o mejor ubicado de la Copa Ecuador
      2026 -- un torneo de copa totalmente aparte (eliminación directa,
      con equipos de todas las categorías) que este proyecto NO simula
      todavía. clasificar_zonas_ligapro() de acá abajo, por lo tanto,
      sólo devuelve 3 nombres en "libertadores" (los que sí salen de la
      tabla de LigaPro) -- el 4° cupo queda fuera del alcance de este
      motor a propósito, no es un olvido.

  Copa Sudamericana 2027 (4 cupos, los 4 sí salen de la tabla de
  LigaPro):
    - Ecuador 1/2/3: los 3 mejores del Hexagonal Campeón que NO
      clasificaron a Libertadores, o sea las posiciones 4°-6° de ese
      grupo (la redacción de la fuente dice "1°/2°/3° de la Fase Final I
      para Sudamericana", que hay que leer como "los 3 mejores ubicados
      todavía sin cupo a Libertadores", no como el 1°-3° a secas -- esos
      ya se fueron a Libertadores).
    - Ecuador 4: 1° del Cuadrangular Sudamericana ("Fase Final II").

DESEMPATES: el reglamento (Art. 9.f / 10.h, idéntico para ambas fases)
usa, en orden: 1) diferencia de gol, 2) goles a favor, 3) goles como
visitante, 4) resultado del enfrentamiento directo entre los
involucrados, 5) sorteo público. Igual que en Brasileirão, este motor
sólo implementa el mismo criterio simple que usa el resto del proyecto
(puntos > dg > gf > nombre, ver Estadisticas._armar_tabla_final) --
los criterios 3° y 4° del reglamento (goles de visitante, cara a cara)
NO están implementados; si hace falta el desempate exacto más adelante,
hay que tocar este archivo Y _armar_tabla_final() en la clase base.

Arquitectura elegida: se reusa el mismo truco de "zona" que agrupa
Brasileirão/B Metro/Nacional en la clase base (Estadisticas), pero acá
la zona de cada equipo CAMBIA a mitad de temporada: arranca en
"FaseInicial" (una sola zona = tabla única) y, una vez resuelta esa
fase, cada equipo se reasigna a una de las 3 zonas de la Fase Final
según su posición final. El fixture de la Fase Final se genera
dinámicamente (fixture_generator, mismo generador que usan Federal A y
el fixture inicial de esta misma liga) recién en ese momento, porque
depende de qué equipos clasificaron a cada grupo -- no se puede
pre-generar como el de la Fase Inicial.
"""
import numpy as np
import pandas as pd

import data_access
import rutas
from modelos.estadisticas import Estadisticas
from fixture_generator import generar_fixture_ida_vuelta

ZONA_FASE_INICIAL = "FaseInicial"
ZONA_HEXAGONAL_CAMPEON = "Hexagonal Campeón"
ZONA_CUADRANGULAR_SUDAMERICANA = "Cuadrangular Sudamericana"
ZONA_HEXAGONAL_DESCENSO = "Hexagonal Descenso"


class EstadisticasLigaPro(Estadisticas):

    # Cortes de la Fase Inicial (posición final, 1-indexed, inclusive)
    # que determinan a qué grupo de la Fase Final clasifica cada equipo.
    CORTE_HEXAGONAL_CAMPEON = 6     # posiciones 1..6
    CORTE_CUADRANGULAR = 10         # posiciones 7..10
    # posiciones 11..16 -> Hexagonal Descenso (el resto)

    # Dentro del Hexagonal Campeón ya jugado: reparto de cupos
    # internacionales por posición final del grupo. Confirmado (Wikipedia
    # "Serie A de Ecuador 2026"): 1°-3° = Ecuador 1/2/3 a Libertadores;
    # 4°-6° = Ecuador 1/2/3 a Sudamericana (el Ecuador 4 de Libertadores
    # sale de la Copa Ecuador, fuera de este motor -- ver docstring
    # del módulo).
    LIBERTADORES_HEXAGONAL_N = 3    # posiciones 1..3 del hexagonal -> Libertadores
    # posiciones 4..6 del hexagonal -> Sudamericana

    DESCENSOS_N = 2                 # últimos 2 del Hexagonal Descenso

    # ------------------------------------------------------------------
    # Carga de datos
    # ------------------------------------------------------------------
    def cargar_datos_ligapro(self):
        print("Leyendo datos de LigaPro Serie A...")

        self.resultados, self.fixture, self.tabla = data_access.league_data("ligapro")

        print(f"Resultados: {len(self.resultados)}")
        print(f"Fixture: {len(self.fixture)}")
        print(f"Tabla: {len(self.tabla)}")

        self._validar_datos_ligapro()

        # Igual que en Brasileirão: recalibrar el promedio de gol de liga
        # con los datos reales de la temporada en curso en vez de
        # arrastrar el default (calibrado para Primera Nacional).
        if len(self.resultados) > 0:
            self.PROMEDIO_GF_LOCAL_LIGA = round(self.resultados["goles_local"].mean(), 3)
            self.PROMEDIO_GF_VISITANTE_LIGA = round(self.resultados["goles_visitante"].mean(), 3)
            print(
                f"Promedios de liga recalibrados para LigaPro: "
                f"local={self.PROMEDIO_GF_LOCAL_LIGA}, visitante={self.PROMEDIO_GF_VISITANTE_LIGA}"
            )
        else:
            print("Sin partidos jugados todavía: se mantiene el promedio de liga por default.")

    def _validar_datos_ligapro(self):
        if len(self.tabla) != 16:
            raise ValueError(
                f"tabla_ligapro.csv tiene {len(self.tabla)} equipos, se esperan "
                "16 (Serie A siempre tiene 16 equipos) -- revisar si el archivo "
                "está roto/vacío/duplicado, o si hubo un descenso/ascenso mal cargado."
            )
        self.validar_datos()

    def crear_equipos_ligapro(self):
        self.crear_equipos()  # heredado

    # ------------------------------------------------------------------
    # Transición Fase Inicial -> Fase Final
    # ------------------------------------------------------------------
    def _en_fase_inicial(self) -> bool:
        """True si todavía no se dividió en los 3 grupos de la Fase Final
        (o sea: todos los equipos siguen en zona FaseInicial)."""
        zonas_actuales = {e.zona for e in self.equipos.values()}
        return zonas_actuales == {ZONA_FASE_INICIAL}

    def _dividir_en_grupos_fase_final(self, tabla_fase_inicial: pd.DataFrame):
        """Reasigna la zona de cada Equipo según su posición final en la
        Fase Inicial (ya jugada o recién simulada) y devuelve la lista de
        equipos de cada grupo, en orden de posición de Fase Inicial (ese
        orden es el que usa fixture_generator para armar el calendario de
        cada grupo -- no afecta el resultado, sólo el orden del fixture)."""
        equipos_orden = tabla_fase_inicial["equipo"].tolist()

        hexagonal_campeon = equipos_orden[:self.CORTE_HEXAGONAL_CAMPEON]
        cuadrangular = equipos_orden[self.CORTE_HEXAGONAL_CAMPEON:self.CORTE_CUADRANGULAR]
        hexagonal_descenso = equipos_orden[self.CORTE_CUADRANGULAR:]

        for nombre in hexagonal_campeon:
            self.equipos[nombre].zona = ZONA_HEXAGONAL_CAMPEON
        for nombre in cuadrangular:
            self.equipos[nombre].zona = ZONA_CUADRANGULAR_SUDAMERICANA
        for nombre in hexagonal_descenso:
            self.equipos[nombre].zona = ZONA_HEXAGONAL_DESCENSO

        return {
            ZONA_HEXAGONAL_CAMPEON: hexagonal_campeon,
            ZONA_CUADRANGULAR_SUDAMERICANA: cuadrangular,
            ZONA_HEXAGONAL_DESCENSO: hexagonal_descenso,
        }

    def _generar_fixture_fase_final(self, grupos: dict) -> pd.DataFrame:
        """Arma el fixture (ida y vuelta) de cada uno de los 3 grupos de
        la Fase Final y lo concatena en un único DataFrame, mismo formato
        que fixture_ligapro.csv (fecha, jornada, equipo_local,
        equipo_visitante)."""
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

    def _sincronizar_equipos_desde_tabla(self, tabla: pd.DataFrame):
        """simular_fase_regular() devuelve la tabla final ya calculada
        (puntos/gf/gc), pero -- a propósito, según su propio docstring --
        NO modifica los objetos Equipo originales (self.equipos), para no
        pisar el estado real entre llamadas. Para el arrastre de puntos
        de Fase Inicial a Fase Final (Art. 10.a del reglamento: "todos
        los clubes mantienen sus puntajes obtenidos en la FASE INICIAL")
        hace falta el efecto contrario: escribir la tabla final de Fase
        Inicial DE VUELTA en self.equipos, para que la siguiente llamada
        a simular_fase_regular() (ya con el fixture de Fase Final) parta
        de esos totales en vez de los del arranque de temporada."""
        for fila in tabla.itertuples():
            equipo_obj = self.equipos[fila.equipo]
            equipo_obj.puntos = int(fila.puntos)
            equipo_obj.goles_favor = int(fila.gf)
            equipo_obj.goles_contra = int(fila.gc)

    # ------------------------------------------------------------------
    # Simulación de la temporada completa (Fase Inicial + Fase Final)
    # ------------------------------------------------------------------
    def simular_temporada_ligapro(self):
        """Devuelve un dict con:
          - "fase_inicial": DataFrame de la tabla final de Fase Inicial.
          - "hexagonal_campeon" / "cuadrangular_sudamericana" /
            "hexagonal_descenso": DataFrames de la Fase Final.
        Si al llamar este método la temporada YA está dividida en los 3
        grupos (zona real de tabla_ligapro.csv distinta de FaseInicial,
        con fixture_ligapro.csv conteniendo ya los partidos pendientes de
        Fase Final), simula directamente la Fase Final sin re-jugar la
        Fase Inicial. Si todavía está todo en FaseInicial, resuelve
        primero esa fase (con los resultados reales ya cargados +
        partidos pendientes simulados) y arma/simula la Fase Final a
        continuación, todo en la misma corrida."""
        if self._en_fase_inicial():
            tablas_fi = self.simular_fase_regular()
            tabla_fase_inicial = tablas_fi[ZONA_FASE_INICIAL]

            self._sincronizar_equipos_desde_tabla(tabla_fase_inicial)
            grupos = self._dividir_en_grupos_fase_final(tabla_fase_inicial)
            self.fixture = self._generar_fixture_fase_final(grupos)
            self._pares_fixture_cache = None  # invalidar cache de _pares_fixture()

            tablas_ff = self.simular_fase_regular()
        else:
            tabla_fase_inicial = None
            tablas_ff = self.simular_fase_regular()

        return {
            "fase_inicial": tabla_fase_inicial,
            "hexagonal_campeon": tablas_ff[ZONA_HEXAGONAL_CAMPEON],
            "cuadrangular_sudamericana": tablas_ff[ZONA_CUADRANGULAR_SUDAMERICANA],
            "hexagonal_descenso": tablas_ff[ZONA_HEXAGONAL_DESCENSO],
        }

    def clasificar_zonas_ligapro(self, tablas_fase_final: dict):
        """A partir de las 3 tablas finales de la Fase Final, arma el
        cuadro de clasificación internacional/descenso completo.

        "libertadores" trae sólo 3 nombres a propósito (Ecuador 1/2/3):
        el 4° cupo a Copa Libertadores no sale de la tabla de LigaPro,
        sale de la Copa Ecuador (torneo de copa aparte, no simulado acá)
        -- ver la nota de "REPARTO DE CUPOS CONMEBOL" en el docstring
        del módulo."""
        hexagonal = tablas_fase_final["hexagonal_campeon"]["equipo"].tolist()
        cuadrangular = tablas_fase_final["cuadrangular_sudamericana"]["equipo"].tolist()
        descenso_tabla = tablas_fase_final["hexagonal_descenso"]["equipo"].tolist()

        return {
            "campeon": hexagonal[0],
            "vicecampeon": hexagonal[1],
            "libertadores": hexagonal[:self.LIBERTADORES_HEXAGONAL_N],
            "sudamericana_hexagonal": hexagonal[self.LIBERTADORES_HEXAGONAL_N:6],
            "sudamericana_cuadrangular": cuadrangular[:1],
            "descenso": descenso_tabla[-self.DESCENSOS_N:],
        }

    # ------------------------------------------------------------------
    # Monte Carlo
    # ------------------------------------------------------------------
    def monte_carlo_ligapro(self, n_simulaciones=1000):
        """Monte Carlo simple (no vectorizado): cada simulación resuelve
        Fase Inicial + Fase Final completas desde cero. A diferencia de
        Brasileirão/B Metro, acá no se pudo reusar
        _simular_fase_regular_vectorizado() tal cual porque el fixture de
        la Fase Final depende del resultado de la Fase Inicial de CADA
        simulación individual (no es un fixture fijo de antemano) -- si
        n_simulaciones empieza a pesar en producción, se puede vectorizar
        en dos pasadas (vectorizar la Fase Inicial, agrupar en 3 zonas
        por simulación, y vectorizar cada Fase Final por separado), pero
        eso queda para una siguiente iteración."""
        print(f"\nCorriendo Monte Carlo LigaPro ({n_simulaciones} simulaciones)...")

        estado_inicial = {
            nombre: {
                "puntos": e.puntos, "gf": e.goles_favor, "gc": e.goles_contra, "zona": e.zona,
            }
            for nombre, e in self.equipos.items()
        }
        fixture_original = self.fixture.copy()
        en_fase_inicial_original = self._en_fase_inicial()

        contador = {
            nombre: {
                "campeon": 0, "libertadores": 0, "sudamericana": 0, "descenso": 0,
                "puntos_total": 0, "posicion_total": 0,
            }
            for nombre in self.equipos
        }

        paso_reporte = max(1, n_simulaciones // 10)

        for i in range(n_simulaciones):
            # Restaurar el estado de arranque antes de cada simulación.
            for nombre, datos in estado_inicial.items():
                self.equipos[nombre].puntos = datos["puntos"]
                self.equipos[nombre].goles_favor = datos["gf"]
                self.equipos[nombre].goles_contra = datos["gc"]
                self.equipos[nombre].zona = datos["zona"]
            self.fixture = fixture_original.copy()
            self._pares_fixture_cache = None

            resultado = self.simular_temporada_ligapro()
            clasif = self.clasificar_zonas_ligapro(resultado)

            tabla_final_hexagonal = resultado["hexagonal_campeon"]
            for posicion, fila in enumerate(tabla_final_hexagonal.itertuples(), start=1):
                contador[fila.equipo]["puntos_total"] += fila.puntos
                contador[fila.equipo]["posicion_total"] += posicion

            contador[clasif["campeon"]]["campeon"] += 1
            for nombre_equipo in clasif["libertadores"]:
                contador[nombre_equipo]["libertadores"] += 1
            for nombre_equipo in clasif["sudamericana_hexagonal"] + clasif["sudamericana_cuadrangular"]:
                contador[nombre_equipo]["sudamericana"] += 1
            for nombre_equipo in clasif["descenso"]:
                contador[nombre_equipo]["descenso"] += 1

            if (i + 1) % paso_reporte == 0:
                print(f"  {i + 1}/{n_simulaciones} simulaciones...")

        # Restaurar el estado real (post-loop, para no dejar el objeto
        # Estadisticas en un estado simulado si se lo sigue usando).
        for nombre, datos in estado_inicial.items():
            self.equipos[nombre].puntos = datos["puntos"]
            self.equipos[nombre].goles_favor = datos["gf"]
            self.equipos[nombre].goles_contra = datos["gc"]
            self.equipos[nombre].zona = datos["zona"]
        self.fixture = fixture_original
        self._pares_fixture_cache = None

        filas = []
        for nombre, datos in contador.items():
            filas.append({
                "equipo": nombre,
                "%campeon": round(100 * datos["campeon"] / n_simulaciones, 1),
                "%libertadores": round(100 * datos["libertadores"] / n_simulaciones, 1),
                "%sudamericana": round(100 * datos["sudamericana"] / n_simulaciones, 1),
                "%descenso": round(100 * datos["descenso"] / n_simulaciones, 1),
            })
        resumen = pd.DataFrame(filas).sort_values("%campeon", ascending=False).reset_index(drop=True)
        resumen.index = resumen.index + 1

        filas_tabla = []
        for nombre, datos in contador.items():
            filas_tabla.append({
                "equipo": nombre,
                "puntos_prom_hexagonal": round(datos["puntos_total"] / n_simulaciones, 1),
                "posicion_prom_hexagonal": round(datos["posicion_total"] / n_simulaciones, 1),
            })
        tabla_esperada = pd.DataFrame(filas_tabla).sort_values("posicion_prom_hexagonal").reset_index(drop=True)
        tabla_esperada.index = tabla_esperada.index + 1

        print("Monte Carlo LigaPro terminado.")
        return resumen, tabla_esperada
