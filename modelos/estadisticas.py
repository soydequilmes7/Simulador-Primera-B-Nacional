import math
import pandas as pd
import numpy as np

import data_access
import rutas
from modelos import equipo
from modelos.motor_vectorizado import muestrear_marcador_dixon_coles
from modelos.equipo import Equipo
from modelos.promotion_requirements import construir_requisitos_ascenso

class Estadisticas:

    PROMEDIO_GF_LOCAL_LIGA = 1.35
    PROMEDIO_GF_VISITANTE_LIGA = 1.05

    # Factoriales de 0 a 8 precalculados una sola vez (se usan en cada
    # simular_partido para la tabla de probabilidades Poisson). Evita
    # llamar math.factorial() en un loop 81 veces por partido simulado --
    # con miles de partidos por Monte Carlo, esto ahorra millones de
    # llamadas redundantes (siempre son los mismos 9 valores).
    _MAX_GOLES = 8
    _FACTORIALES = np.array([math.factorial(i) for i in range(_MAX_GOLES + 1)], dtype=np.float64)
    _RANGO_GOLES = np.arange(_MAX_GOLES + 1)

    def __init__(self):

        self.resultados = None
        self.fixture = None
        self.tabla = None

        self.equipos = {}

    def cargar_datos(self):

        print("Leyendo datos...")

        self.resultados, self.fixture, self.tabla = data_access.league_data("nacional")

        print(f"Resultados: {len(self.resultados)}")
        print(f"Fixture: {len(self.fixture)}")
        print(f"Tabla: {len(self.tabla)}")
        self.validar_datos()

    def validar_datos(self):
        """Verifica que los CSV tengan las columnas esperadas y sin datos faltantes."""
        
        columnas_esperadas = {
            "resultados": {"fecha", "jornada", "equipo_local", "equipo_visitante", "goles_local", "goles_visitante"},
            "fixture": {"fecha", "jornada", "equipo_local", "equipo_visitante"},
            "tabla": {"zona", "posicion", "equipo", "partidos_jugados", "ganados",
                      "empatados", "perdidos", "gf", "gc", "dg", "puntos"},
        }

        dataframes = {
            "resultados": self.resultados,
            "fixture": self.fixture,
            "tabla": self.tabla,
        }

        for nombre, df in dataframes.items():
            columnas_faltantes = columnas_esperadas[nombre] - set(df.columns)
            if columnas_faltantes:
                raise ValueError(f"{nombre}.csv no tiene las columnas: {columnas_faltantes}")

        # Tipos: las columnas numéricas de resultados no pueden tener texto
        columnas_numericas_resultados = ["jornada", "goles_local", "goles_visitante"]
        for col in columnas_numericas_resultados:
            if not pd.api.types.is_numeric_dtype(self.resultados[col]):
                raise TypeError(f"resultados.csv: la columna '{col}' debería ser numérica")

        # resultados.csv solo debe tener partidos jugados: goles_local/visitante no pueden faltar
        if self.resultados[["goles_local", "goles_visitante"]].isnull().any().any():
            raise ValueError(
                "resultados.csv tiene partidos sin goles cargados. "
                "Este archivo debe contener únicamente partidos ya jugados."
            )
        print(f"Partidos jugados en resultados.csv: {len(self.resultados)}")

       # resultados.csv y fixture.csv deben ser disjuntos: un partido no puede estar jugado y pendiente a la vez
        claves_resultados = set(zip(self.resultados["jornada"], self.resultados["equipo_local"], self.resultados["equipo_visitante"]))
        claves_fixture = set(zip(self.fixture["jornada"], self.fixture["equipo_local"], self.fixture["equipo_visitante"]))

        solapados = claves_resultados & claves_fixture
        if solapados:
            raise ValueError(
                f"Hay {len(solapados)} partidos que aparecen como jugados Y pendientes a la vez: "
                f"{list(solapados)[:5]}..."
            )

        partidos_pendientes = len(claves_fixture)
        print(f"Partidos pendientes de simular: {partidos_pendientes}")

        if self.tabla[["partidos_jugados", "puntos"]].isnull().any().any():
            raise ValueError("tabla.csv tiene valores faltantes en partidos_jugados o puntos")

        print("Validación de datos OK.\n")

    def crear_equipos(self):
        """Crea un objeto Equipo por cada fila de tabla.csv y carga sus totales actuales."""
        print("\nCreando equipos...")

        for _, fila in self.tabla.iterrows():
            equipo = Equipo(fila["equipo"])
            equipo.zona = fila["zona"]

            equipo.puntos = int(fila["puntos"])
            equipo.goles_favor = int(fila["gf"])
            equipo.goles_contra = int(fila["gc"])

            self.equipos[fila["equipo"]] = equipo

        self._aplicar_ratings_persistentes()
        print(f"Equipos creados: {len(self.equipos)}")

    def _aplicar_ratings_persistentes(self):
        """Usa el rating vivo por club como prior inicial si existe."""
        try:
            ratings = data_access.club_ratings_by_names(list(self.equipos.keys()))
        except Exception as exc:
            print(f"Ratings persistentes no disponibles, se usan defaults: {exc}")
            return
        for nombre, rating in ratings.items():
            equipo_obj = self.equipos.get(nombre)
            if equipo_obj is None:
                continue
            equipo_obj.ataque_local = float(rating["ataque_local"])
            equipo_obj.ataque_visitante = float(rating["ataque_visitante"])
            equipo_obj.defensa_local = float(rating["defensa_local"])
            equipo_obj.defensa_visitante = float(rating["defensa_visitante"])
        if ratings:
            print(f"Ratings persistentes aplicados a {len(ratings)} equipos.")

    def calcular_estadisticas(self):
        """Calcula estadísticas de los últimos 10 partidos (general, local, visitante) para cada equipo."""
        print("\nCalculando estadísticas...")

        resultados_ordenados = self.resultados.sort_values("jornada")

        for nombre, equipo in self.equipos.items():
            partidos_equipo = resultados_ordenados[
                (resultados_ordenados["equipo_local"] == nombre) |
                (resultados_ordenados["equipo_visitante"] == nombre)
            ]
            equipo.ultimos10 = self._procesar_partidos(partidos_equipo, nombre, ultimos_n=10)

            partidos_local = resultados_ordenados[resultados_ordenados["equipo_local"] == nombre].tail(10)
            equipo.local_gf, equipo.local_gc = self._promedio_goles(partidos_local, "goles_local", "goles_visitante")
            equipo.partidos_local_n = len(partidos_local)

            partidos_visitante = resultados_ordenados[resultados_ordenados["equipo_visitante"] == nombre].tail(10)
            equipo.visitante_gf, equipo.visitante_gc = self._promedio_goles(partidos_visitante, "goles_visitante", "goles_local")
            equipo.partidos_visitante_n = len(partidos_visitante)

        print(f"Estadísticas calculadas para {len(self.equipos)} equipos.")

    def calcular_ratings(self):
        """Calcula fuerza de ataque/defensa de cada equipo (local y visitante)
        relativa al promedio de la liga, ponderando partidos recientes y aplicando
        regresión a la media para equipos con pocos partidos jugados."""
        print("\nCalculando ratings...")

        if len(self.resultados) == 0:
            # Temporada 100% arrancando (nadie jugó nada todavía -- ej.
            # la "próxima temporada" recién generada de Modo Temporada,
            # antes de simular su primer partido): promedio_gf_liga
            # sobre una tabla vacía da NaN para TODOS los equipos, no
            # solo los recién ascendidos. Sin partidos de referencia no
            # hay de dónde derivar nada -- se deja el rating genérico
            # que Equipo.__init__() ya pone por default (1.0/1.0),
            # mismo criterio "sin evidencia, sin ventaja" que ya usa el
            # resto del proyecto para equipos sin historial (ver
            # ATAQUE_ASCENSO/DEFENSA_ASCENSO en estadisticas_copa.py).
            print(f"Sin partidos jugados todavía: rating genérico para los {len(self.equipos)} equipos.")
            return

        DECAY = 0.99        # peso decae con la antigüedad del partido (por jornada)
        K_REGRESION = 12    # "partidos virtuales" de peso hacia el promedio de liga

        promedio_gf_local_liga = self.resultados["goles_local"].mean()
        promedio_gc_local_liga = self.resultados["goles_visitante"].mean()
        promedio_gf_visitante_liga = self.resultados["goles_visitante"].mean()
        promedio_gc_visitante_liga = self.resultados["goles_local"].mean()

        jornada_actual = self.resultados["jornada"].max()

        for nombre, equipo in self.equipos.items():
            partidos_local = self.resultados[self.resultados["equipo_local"] == nombre]
            partidos_visitante = self.resultados[self.resultados["equipo_visitante"] == nombre]

            if len(partidos_local) > 0:
                pesos = DECAY ** (jornada_actual - partidos_local["jornada"])
                gf_local = np.average(partidos_local["goles_local"], weights=pesos)
                gc_local = np.average(partidos_local["goles_visitante"], weights=pesos)

                ataque_local_bruto = gf_local / promedio_gf_local_liga
                defensa_local_bruto = gc_local / promedio_gc_local_liga

                n = len(partidos_local)
                equipo.ataque_local = round((n * ataque_local_bruto + K_REGRESION * equipo.ataque_local) / (n + K_REGRESION), 3)
                equipo.defensa_local = round((n * defensa_local_bruto + K_REGRESION * equipo.defensa_local) / (n + K_REGRESION), 3)

            if len(partidos_visitante) > 0:
                pesos = DECAY ** (jornada_actual - partidos_visitante["jornada"])
                gf_visitante = np.average(partidos_visitante["goles_visitante"], weights=pesos)
                gc_visitante = np.average(partidos_visitante["goles_local"], weights=pesos)

                ataque_visitante_bruto = gf_visitante / promedio_gf_visitante_liga
                defensa_visitante_bruto = gc_visitante / promedio_gc_visitante_liga

                n = len(partidos_visitante)
                equipo.ataque_visitante = round((n * ataque_visitante_bruto + K_REGRESION * equipo.ataque_visitante) / (n + K_REGRESION), 3)
                equipo.defensa_visitante = round((n * defensa_visitante_bruto + K_REGRESION * equipo.defensa_visitante) / (n + K_REGRESION), 3)

        print(f"Ratings calculados para {len(self.equipos)} equipos.")

    # Forma del Gamma que genera el "shock" de partido (media=1). Más bajo
    # = más variable (más dispersión extra sobre el Poisson puro); más
    # alto = shock casi nulo, se acerca al Poisson puro de antes. 10 es un
    # punto medio razonable: sube la varianza de goles por partido sin
    # volverla descontrolada. Ajustable sin tocar el resto del método.
    K_SHOCK_PARTIDO = 10

    def simular_partido(self, nombre_local, nombre_visitante):
        """Simula el resultado de un partido cruzando ataque de un equipo
        con defensa del rival, con dos correcciones sobre el Poisson puro:

        1. Corrección de Dixon-Coles para los marcadores bajos (0-0, 1-0,
           0-1, 1-1), donde el Poisson independiente puro subestima la
           probabilidad real de empate.

        2. Mezcla Poisson-Gamma (equivalente a una Binomial Negativa): antes
           de sortear los goles, cada equipo recibe un "shock" aleatorio de
           partido (factor con media 1, ~Gamma) que representa todo lo que
           el modelo no puede ver de antemano en ESE partido puntual -- una
           baja de último momento, el árbitro, el clima, una sorpresa
           táctica. Se sortea independiente para cada equipo (una racha de
           bajas afecta a uno, no necesariamente al rival). El Poisson puro
           por sí solo se queda corto en varianza frente a los resultados
           reales de fútbol; esto le agrega esa dispersión extra de forma
           realista, sin necesitar saber qué pasó puntualmente en cada caso.
        """

        RHO = -0.1  # correlación negativa típica entre goles local/visitante en marcadores bajos

        local = self.equipos[nombre_local]
        visitante = self.equipos[nombre_visitante]

        lambda_local_base = local.ataque_local * visitante.defensa_visitante * self.PROMEDIO_GF_LOCAL_LIGA
        lambda_visitante_base = visitante.ataque_visitante * local.defensa_local * self.PROMEDIO_GF_VISITANTE_LIGA

        shock_local = np.random.gamma(shape=self.K_SHOCK_PARTIDO, scale=1 / self.K_SHOCK_PARTIDO)
        shock_visitante = np.random.gamma(shape=self.K_SHOCK_PARTIDO, scale=1 / self.K_SHOCK_PARTIDO)

        lambda_local = lambda_local_base * shock_local
        lambda_visitante = lambda_visitante_base * shock_visitante

        # Probabilidades Poisson independientes para un rango de marcadores
        # razonable. Vectorizado con NumPy en vez de un doble loop de Python
        # con math.factorial() en cada iteración (81 llamadas por partido):
        # esta es, por lejos, la función más llamada de toda la simulación
        # (miles de veces en cada corrida de Monte Carlo), así que evitar el
        # overhead del intérprete acá es lo que más impacta en la velocidad
        # total -- tanto en el backend como corriendo en el navegador vía
        # Pyodide.
        k = self._RANGO_GOLES
        p_x = (lambda_local ** k) * np.exp(-lambda_local) / self._FACTORIALES
        p_y = (lambda_visitante ** k) * np.exp(-lambda_visitante) / self._FACTORIALES
        probs = np.outer(p_x, p_y)

        # Corrección Dixon-Coles: solo afecta a 0-0, 1-0, 0-1, 1-1
        probs[0, 0] *= 1 - lambda_local * lambda_visitante * RHO
        probs[1, 0] *= 1 + lambda_visitante * RHO
        probs[0, 1] *= 1 + lambda_local * RHO
        probs[1, 1] *= 1 - RHO

        # Samplear un marcador (x, y) según esas probabilidades ajustadas.
        # np.random.choice acepta que p no sume exactamente 1 (con que sea
        # muy cercano alcanza), pero normalizamos igual por prolijidad.
        flat_probs = probs.ravel()
        flat_probs = flat_probs / flat_probs.sum()
        idx = np.random.choice(flat_probs.size, p=flat_probs)
        max_goles = self._MAX_GOLES
        goles_local, goles_visitante = idx // (max_goles + 1), idx % (max_goles + 1)


        return int(goles_local), int(goles_visitante)
    
    def _pares_fixture(self):
        """Lista (local, visitante) de los partidos pendientes, calculada una
        sola vez y cacheada. simular_fase_regular() se llama una vez por
        cada simulación de Monte Carlo (hasta 1000+ veces) y el fixture no
        cambia entre una simulación y otra, así que recorrerlo con
        DataFrame.iterrows() en cada vuelta (que reconstruye una Series por
        fila) es trabajo repetido de más. Se guarda como lista de tuplas
        nativas de Python, mucho más liviana de recorrer."""
        if getattr(self, "_pares_fixture_cache", None) is None:
            self._pares_fixture_cache = list(
                self.fixture[["equipo_local", "equipo_visitante"]].itertuples(index=False, name=None)
            )
        return self._pares_fixture_cache

    def simular_fase_regular(self):
        """Simula todos los partidos pendientes del fixture y devuelve la tabla final
        de cada zona (puntos, gf, gc, dg), sin modificar los objetos Equipo originales."""

        # Partimos de los totales actuales (ya jugados), copiados aparte
        totales = {
            nombre: {"puntos": equipo.puntos, "gf": equipo.goles_favor, "gc": equipo.goles_contra}
            for nombre, equipo in self.equipos.items()
        }

        registrar = bool(getattr(self, "registrar_partidos_simulados_oficiales", False))
        if registrar:
            iterable_fixture = self.fixture[["fecha", "jornada", "equipo_local", "equipo_visitante"]].to_dict("records")
        else:
            iterable_fixture = [
                {"equipo_local": local, "equipo_visitante": visitante}
                for local, visitante in self._pares_fixture()
            ]
        for orden, fila_fixture in enumerate(iterable_fixture, start=1):
            local = fila_fixture["equipo_local"]
            visitante = fila_fixture["equipo_visitante"]
            gl, gv = self.simular_partido(local, visitante)
            if registrar:
                self.partidos_simulados_oficiales = getattr(self, "partidos_simulados_oficiales", [])
                self.partidos_simulados_oficiales.append({
                    "fecha": fila_fixture.get("fecha", ""),
                    "jornada": int(fila_fixture.get("jornada") or orden),
                    "equipo_local": local,
                    "equipo_visitante": visitante,
                    "goles_local": gl,
                    "goles_visitante": gv,
                    "event_key": f"{orden}:{local}:{visitante}",
                })

            totales[local]["gf"] += gl
            totales[local]["gc"] += gv
            totales[visitante]["gf"] += gv
            totales[visitante]["gc"] += gl

            if gl > gv:
                totales[local]["puntos"] += 3
            elif gl < gv:
                totales[visitante]["puntos"] += 3
            else:
                totales[local]["puntos"] += 1
                totales[visitante]["puntos"] += 1

        return self._armar_tabla_final(totales)

    def _armar_tabla_final(self, totales):
        """Ordena los totales finales por zona, aplicando desempates:
        1) puntos, 2) diferencia de gol, 3) goles a favor.
        Devuelve un dict {"A": DataFrame, "B": DataFrame}.

        Se arma con arrays de NumPy + np.lexsort en vez de
        DataFrame.sort_values(): esta función se llama una vez por cada
        simulación de Monte Carlo (1000+ veces) sobre una tabla de apenas
        ~19 equipos, y el overhead propio de pandas para ordenar (conversión
        a categórico, lexsort_indexer, etc.) termina pesando más que el
        trabajo real. El resultado final sigue siendo un DataFrame por
        zona, con las mismas columnas/orden que antes, para no romper nada
        de lo que ya consume esta salida (export a JSON, etc.)."""

        nombres = np.array(list(totales.keys()))
        zonas = np.array([self.equipos[n].zona for n in nombres])
        puntos = np.array([totales[n]["puntos"] for n in nombres])
        gf = np.array([totales[n]["gf"] for n in nombres])
        gc = np.array([totales[n]["gc"] for n in nombres])
        dg = gf - gc

        tablas_por_zona = {}
        for zona in sorted(set(zonas.tolist())):
            mask = zonas == zona
            # np.lexsort ordena por la ÚLTIMA clave como criterio principal,
            # así que el orden de desempate (puntos > dg > gf, todos desc)
            # va de menos a más importante: gf, luego dg, luego puntos.
            orden = np.lexsort((-gf[mask], -dg[mask], -puntos[mask]))
            tabla_zona = pd.DataFrame({
                "equipo": nombres[mask][orden],
                "puntos": puntos[mask][orden],
                "gf": gf[mask][orden],
                "gc": gc[mask][orden],
                "dg": dg[mask][orden],
            })
            tabla_zona.index = tabla_zona.index + 1  # posición arranca en 1
            tablas_por_zona[zona] = tabla_zona

        return tablas_por_zona

    def _simular_fase_regular_vectorizado(self, n_simulaciones, max_elems_por_bloque=8_000_000):
        """Versión vectorizada de simular_fase_regular(), pensada para
        Monte Carlo. En vez de llamar simular_partido() una vez por cada
        partido pendiente Y por cada simulación (partidos_pendientes x
        n_simulaciones llamadas individuales, cada una con su propio
        overhead de Python + numpy), arma TODOS los partidos pendientes de
        TODAS las simulaciones en un solo bloque de arrays y los resuelve
        con operaciones vectorizadas de una sola vez.

        Usa EXACTAMENTE el mismo modelo que simular_partido(): mismo
        lambda por Dixon-Coles + shock Gamma, mismas probabilidades por
        marcador, mismo muestreo por función de distribución acumulada
        (matemáticamente equivalente a np.random.choice(p=...), que es lo
        que usa la versión partido-por-partido) -- estadísticamente
        equivalente, no una aproximación. Lo único que cambia es que se
        sortean todos los partidos juntos en vez de uno a la vez.

        Devuelve un dict {equipo: {"puntos": array(n_simulaciones),
        "gf": array(...), "gc": array(...)}} con los totales finales de
        CADA simulación, arrancando de los totales ya jugados (igual que
        simular_fase_regular()).

        max_elems_por_bloque limita cuántas celdas de la grilla de
        probabilidades (partidos x simulaciones x 81 marcadores posibles)
        se arman de una sola vez, para no reventar la memoria del
        navegador cuando corre en Pyodide -- si hace falta, procesa las
        simulaciones en tandas y las concatena al final (el resultado es
        idéntico a procesarlas todas juntas, solo cambia cuánta memoria
        pico se usa)."""
        pares = self._pares_fixture()
        M = len(pares)
        S = n_simulaciones
        nombres_equipos = list(self.equipos.keys())
        idx_por_nombre = {n: i for i, n in enumerate(nombres_equipos)}
        n_equipos = len(nombres_equipos)

        puntos_base = np.array([self.equipos[n].puntos for n in nombres_equipos], dtype=np.int64)
        gf_base = np.array([self.equipos[n].goles_favor for n in nombres_equipos], dtype=np.int64)
        gc_base = np.array([self.equipos[n].goles_contra for n in nombres_equipos], dtype=np.int64)

        if M == 0:
            # No quedan partidos pendientes: todas las simulaciones
            # devuelven la misma tabla ya jugada, repetida S veces.
            return {
                nombre: {
                    "puntos": np.full(S, puntos_base[i], dtype=np.int64),
                    "gf": np.full(S, gf_base[i], dtype=np.int64),
                    "gc": np.full(S, gc_base[i], dtype=np.int64),
                    # Sin partidos pendientes no hay victorias/empates/derrotas
                    # que sumar de acá en más.
                    "victorias": np.zeros(S, dtype=np.int64),
                    "empates": np.zeros(S, dtype=np.int64),
                    "derrotas": np.zeros(S, dtype=np.int64),
                }
                for i, nombre in enumerate(nombres_equipos)
            }

        idx_local = np.array([idx_por_nombre[l] for l, _ in pares])
        idx_visitante = np.array([idx_por_nombre[v] for _, v in pares])

        lambda_local_base = np.array([
            self.equipos[l].ataque_local * self.equipos[v].defensa_visitante * self.PROMEDIO_GF_LOCAL_LIGA
            for l, v in pares
        ])
        lambda_visitante_base = np.array([
            self.equipos[v].ataque_visitante * self.equipos[l].defensa_local * self.PROMEDIO_GF_VISITANTE_LIGA
            for l, v in pares
        ])

        K_SHOCK = self.K_SHOCK_PARTIDO
        max_goles = self._MAX_GOLES
        n_marcadores = (max_goles + 1) * (max_goles + 1)  # 81

        puntos_tot = np.zeros((n_equipos, S), dtype=np.int64)
        gf_tot = np.zeros((n_equipos, S), dtype=np.int64)
        gc_tot = np.zeros((n_equipos, S), dtype=np.int64)
        puntos_tot[:] = puntos_base[:, None]
        gf_tot[:] = gf_base[:, None]
        gc_tot[:] = gc_base[:, None]

        # Victorias/empates/derrotas de CADA simulación, contando solo los
        # partidos pendientes que se sortean acá (no arrastran base como
        # puntos/gf/gc, porque esa base ya está implícita en puntos_base).
        # Se usan para "¿Qué necesita [Equipo]?": el rendimiento que
        # necesita el equipo en lo que queda de temporada.
        victorias_tot = np.zeros((n_equipos, S), dtype=np.int64)
        empates_tot = np.zeros((n_equipos, S), dtype=np.int64)
        derrotas_tot = np.zeros((n_equipos, S), dtype=np.int64)

        # Tamaño de tanda: cuántas simulaciones procesar juntas para no
        # superar max_elems_por_bloque celdas (M x tanda x 81) de una vez.
        tanda = max(1, min(S, max_elems_por_bloque // max(1, M * n_marcadores)))

        for inicio in range(0, S, tanda):
            s = min(tanda, S - inicio)

            shock_local = np.random.gamma(shape=K_SHOCK, scale=1 / K_SHOCK, size=(M, s))
            shock_visitante = np.random.gamma(shape=K_SHOCK, scale=1 / K_SHOCK, size=(M, s))

            lambda_local = lambda_local_base[:, None] * shock_local          # (M, s)
            lambda_visitante = lambda_visitante_base[:, None] * shock_visitante

            # Muestreo marginal + rejection sampling exacto (ver
            # modelos/motor_vectorizado.py::muestrear_marcador_dixon_coles):
            # reemplaza el tensor conjunto (M,s,9,9) de 81 celdas por
            # marginales O(9) independientes y una corrección puntual solo
            # en las 4 celdas que Dixon-Coles afecta (0-0, 1-0, 0-1, 1-1),
            # bajando el pico de memoria de la tanda ~3.65x a costa de un
            # ~1.7x en tiempo (loop de rejection) -- estadísticamente
            # equivalente, validado contra la pmf exacta de 81 celdas.
            goles_local, goles_visitante = muestrear_marcador_dixon_coles(
                lambda_local, lambda_visitante, np.random
            )

            gana_local = goles_local > goles_visitante
            gana_visitante = goles_local < goles_visitante
            empate = ~gana_local & ~gana_visitante

            pts_local = np.where(gana_local, 3, np.where(empate, 1, 0))
            pts_visitante = np.where(gana_visitante, 3, np.where(empate, 1, 0))

            bloque_puntos = puntos_tot[:, inicio:inicio + s]
            bloque_gf = gf_tot[:, inicio:inicio + s]
            bloque_gc = gc_tot[:, inicio:inicio + s]
            bloque_victorias = victorias_tot[:, inicio:inicio + s]
            bloque_empates = empates_tot[:, inicio:inicio + s]
            bloque_derrotas = derrotas_tot[:, inicio:inicio + s]

            np.add.at(bloque_puntos, idx_local, pts_local)
            np.add.at(bloque_puntos, idx_visitante, pts_visitante)
            np.add.at(bloque_gf, idx_local, goles_local)
            np.add.at(bloque_gf, idx_visitante, goles_visitante)
            np.add.at(bloque_gc, idx_local, goles_visitante)
            np.add.at(bloque_gc, idx_visitante, goles_local)

            gana_local_i = gana_local.astype(np.int64)
            gana_visitante_i = gana_visitante.astype(np.int64)
            empate_i = empate.astype(np.int64)

            np.add.at(bloque_victorias, idx_local, gana_local_i)
            np.add.at(bloque_victorias, idx_visitante, gana_visitante_i)
            np.add.at(bloque_empates, idx_local, empate_i)
            np.add.at(bloque_empates, idx_visitante, empate_i)
            np.add.at(bloque_derrotas, idx_local, gana_visitante_i)
            np.add.at(bloque_derrotas, idx_visitante, gana_local_i)

        return {
            nombre: {
                "puntos": puntos_tot[i],
                "gf": gf_tot[i],
                "gc": gc_tot[i],
                "victorias": victorias_tot[i],
                "empates": empates_tot[i],
                "derrotas": derrotas_tot[i],
            }
            for i, nombre in enumerate(nombres_equipos)
        }
    
    def jugar_final_ascenso(self, nombre_a, nombre_b):
        """Simula la final a partido único por el 1° ascenso entre el puntero
        de Zona A y el puntero de Zona B. Cancha neutral, con alargue y penales
        si hay empate. Devuelve (ganador, perdedor, detalle_dict)."""

        equipo_a = self.equipos[nombre_a]
        equipo_b = self.equipos[nombre_b]

        ataque_a = (equipo_a.ataque_local + equipo_a.ataque_visitante) / 2
        defensa_a = (equipo_a.defensa_local + equipo_a.defensa_visitante) / 2
        ataque_b = (equipo_b.ataque_local + equipo_b.ataque_visitante) / 2
        defensa_b = (equipo_b.defensa_local + equipo_b.defensa_visitante) / 2

        promedio_liga_neutral = (self.PROMEDIO_GF_LOCAL_LIGA + self.PROMEDIO_GF_VISITANTE_LIGA) / 2

        lambda_a = ataque_a * defensa_b * promedio_liga_neutral
        lambda_b = ataque_b * defensa_a * promedio_liga_neutral

        goles_a = int(np.random.poisson(lambda_a))
        goles_b = int(np.random.poisson(lambda_b))

        # Estructuramos el detalle como un diccionario para que no falle la web
        detalle = {
            "marcador": [goles_a, goles_b],
            "texto": f"{nombre_a} {goles_a} - {goles_b} {nombre_b}"
        }

        if goles_a != goles_b:
            ganador, perdedor = (nombre_a, nombre_b) if goles_a > goles_b else (nombre_b, nombre_a)
            return ganador, perdedor, detalle

        # Empate en los 90: alargue de 30 minutos (1/3 del tiempo normal)
        goles_a_alargue = int(np.random.poisson(lambda_a / 3))
        goles_b_alargue = int(np.random.poisson(lambda_b / 3))

        # Actualizamos el marcador sumando los goles del alargue
        detalle["marcador"] = [goles_a + goles_a_alargue, goles_b + goles_b_alargue]
        detalle["texto"] += f" (alargue: {goles_a_alargue}-{goles_b_alargue})"

        if goles_a_alargue != goles_b_alargue:
            ganador, perdedor = (nombre_a, nombre_b) if goles_a_alargue > goles_b_alargue else (nombre_b, nombre_a)
            return ganador, perdedor, detalle

        # Sigue empatado: se define por penales (50/50)
        ganador, perdedor = (nombre_a, nombre_b) if np.random.random() < 0.5 else (nombre_b, nombre_a)
        detalle["texto"] += " (definido por penales)"
        return ganador, perdedor, detalle
    
    def _tabla_general(self, tablas):
        """Combina las tablas de ambas zonas en una sola, ordenada por
        puntos, diferencia de gol y goles a favor (ignorando la zona)."""
        combinada = pd.concat([tablas["A"], tablas["B"]], ignore_index=True)
        combinada = combinada.sort_values(
            by=["puntos", "dg", "gf"], ascending=[False, False, False]
        ).reset_index(drop=True)
        return combinada

    def _posiciones(self, tabla_general):
        """Diccionario {equipo: posicion} armado UNA vez a partir de la
        tabla general ya ordenada. _mejor_ubicado() se llama muchas veces
        por cada Reducido (una por cada cruce), y antes cada llamada hacía
        una búsqueda booleana sobre todo el DataFrame (tabla_general["equipo"]
        == equipo_x) para encontrar un solo valor -- con este dict el
        lookup pasa a ser O(1) en Python puro."""
        return {nombre: pos for pos, nombre in enumerate(tabla_general["equipo"])}

    def _mejor_ubicado(self, posiciones, equipo_x, equipo_y):
        """Devuelve (mejor, peor) según la posición en la tabla general
        combinada. `posiciones` es el dict que arma _posiciones()."""
        return (equipo_x, equipo_y) if posiciones[equipo_x] < posiciones[equipo_y] else (equipo_y, equipo_x)

    def jugar_partido_unico(self, mejor, peor):
        gl, gv = self.simular_partido(mejor, peor)
        ganador = mejor if gl >= gv else peor
        
        # Diccionario estructurado para la web
        detalle = {
            "local": mejor,
            "visitante": peor,
            "golesLocal": gl,
            "golesVisitante": gv,
            "avanza": ganador
        }
        return ganador, detalle

    def jugar_serie_ida_vuelta(self, equipo_x, equipo_y):
        gl1, gv1 = self.simular_partido(equipo_x, equipo_y)
        gl2, gv2 = self.simular_partido(equipo_y, equipo_x)

        goles_x = gl1 + gv2
        goles_y = gv1 + gl2

        detalle_str = f"Ida: {gl1}-{gv1} | Vuelta: {gl2}-{gv2}"

        if goles_x != goles_y:
            ganador = equipo_x if goles_x > goles_y else equipo_y
        else:
            ganador = equipo_x if np.random.random() < 0.5 else equipo_y
            detalle_str += " (Penales)"

        detalle = {
            # Nombres de los dos equipos que jugaron la serie. Se agregan
            # además de "detalle"/"campeon" (que ya se usaban) para que el
            # frontend pueda armar el bracket sin depender de la ronda
            # anterior para saber quién jugó -- necesario para B Metro,
            # donde cuartos y semis también son ida y vuelta (a diferencia
            # de Nacional/LPF, donde solo la final lo es y ahí sí alcanza
            # con los "avanza" de semis para saber los dos finalistas).
            "equipo_x": equipo_x,
            "equipo_y": equipo_y,
            "goles_x": goles_x,
            "goles_y": goles_y,
            "detalle": detalle_str,
            "campeon": ganador
        }
        return ganador, detalle

    def jugar_reducido(self, tablas, perdedor_final_ascenso):
        tabla_a, tabla_b = tablas["A"], tablas["B"]
        
        diccionario = {
            "perdedor_final_ascenso": perdedor_final_ascenso,
            "primera_ronda": [],
            "cuartos": [],
            "semis": [],
            "final": {}
        }

        # Listas planas de Python en vez de indexar el DataFrame con
        # .iloc[...]["equipo"] repetidas veces (cada .iloc[i] arma una
        # Series entera solo para leer un valor).
        equipos_a = tabla_a["equipo"].tolist()
        equipos_b = tabla_b["equipo"].tolist()

        def equipo(lista, posicion):
            return lista[posicion - 1]

        cruces_primera_ronda = [
            (equipo(equipos_a, 2), equipo(equipos_b, 8)),
            (equipo(equipos_b, 2), equipo(equipos_a, 8)),
            (equipo(equipos_a, 3), equipo(equipos_b, 7)),
            (equipo(equipos_b, 3), equipo(equipos_a, 7)),
            (equipo(equipos_a, 4), equipo(equipos_b, 6)),
            (equipo(equipos_b, 4), equipo(equipos_a, 6)),
            (equipo(equipos_a, 5), equipo(equipos_b, 5)),
        ]

        tabla_general = self._tabla_general(tablas)
        posiciones = self._posiciones(tabla_general)
        # Orden general ya calculado en _tabla_general(); lo reutilizamos
        # como lista plana para armar los seeds de cada ronda con simples
        # comprensiones de lista (preservan el orden) en vez de
        # DataFrame.isin() + reset_index() sobre toda la tabla combinada
        # para elegir apenas 7 u 8 equipos.
        orden_general = tabla_general["equipo"].tolist()

        ganadores_primera_ronda = []
        for x, y in cruces_primera_ronda:
            mejor, peor = self._mejor_ubicado(posiciones, x, y)
            ganador, detalle = self.jugar_partido_unico(mejor, peor)
            diccionario["primera_ronda"].append(detalle)
            ganadores_primera_ronda.append(ganador)

        clasificados = set(ganadores_primera_ronda) | {perdedor_final_ascenso}
        seeds = [nombre for nombre in orden_general if nombre in clasificados]

        cruces_cuartos = [(0, 7), (1, 6), (2, 5), (3, 4)]
        ganadores_cuartos = []
        for i, j in cruces_cuartos:
            mejor, peor = seeds[i], seeds[j]
            ganador, detalle = self.jugar_partido_unico(mejor, peor)
            diccionario["cuartos"].append(detalle)
            ganadores_cuartos.append(ganador)

        ganadores_cuartos_set = set(ganadores_cuartos)
        seeds_semis = [nombre for nombre in orden_general if nombre in ganadores_cuartos_set]

        finalistas = []
        for i, j in [(0, 3), (1, 2)]:
            mejor, peor = seeds_semis[i], seeds_semis[j]
            ganador, detalle = self.jugar_partido_unico(mejor, peor)
            diccionario["semis"].append(detalle)
            finalistas.append(ganador)

        campeon, detalle_final = self.jugar_serie_ida_vuelta(finalistas[0], finalistas[1])
        diccionario["final"] = detalle_final

        return campeon, diccionario

    def _procesar_partidos(self, partidos_equipo, nombre, ultimos_n):
        """Devuelve una lista de dicts con resultado (puntos, gf, gc) de los últimos N partidos de un equipo."""

        ultimos = partidos_equipo.tail(ultimos_n)
        historial = []

        for _, partido in ultimos.iterrows():
            es_local = partido["equipo_local"] == nombre
            gf = partido["goles_local"] if es_local else partido["goles_visitante"]
            gc = partido["goles_visitante"] if es_local else partido["goles_local"]

            if gf > gc:
                puntos = 3
            elif gf == gc:
                puntos = 1
            else:
                puntos = 0

            rival = partido["equipo_visitante"] if es_local else partido["equipo_local"]
            # resultados.csv trae "fecha" vacía en muchas filas -> pandas la
            # lee como NaN, y json.dump vuelca eso como el literal `NaN`,
            # que no es JSON válido (rompe JSON.parse en el navegador).
            # La convertimos a None -> se exporta como null.
            fecha = partido["fecha"]
            if pd.isna(fecha):
                fecha = None

            historial.append({
                "gf": int(gf),
                "gc": int(gc),
                "puntos": puntos,
                "fecha": fecha,
                "jornada": int(partido["jornada"]),
                "rival": rival,
                "condicion": "local" if es_local else "visitante",
            })

        return historial

    def _promedio_goles(self, partidos, col_gf, col_gc):
        """Calcula el promedio de goles a favor y en contra sobre un subconjunto de partidos."""

        if len(partidos) == 0:
            return 0.0, 0.0

        promedio_gf = partidos[col_gf].mean()
        promedio_gc = partidos[col_gc].mean()
        return round(promedio_gf, 2), round(promedio_gc, 2)
    
    def monte_carlo(self, n_simulaciones=1000):
        """Corre la fase regular + ascensos + descensos n_simulaciones veces y
        devuelve (resumen_ascensos_descensos, tabla_esperada_por_zona)."""
        print(f"\nCorriendo Monte Carlo ({n_simulaciones} simulaciones)...")

        contador = {
            nombre: {"puntero_zona": 0, "ascenso_directo": 0, "ascenso_reducido": 0, "descenso": 0,
                      "puntos_total": 0, "posicion_total": 0}
            for nombre in self.equipos
        }

        paso_reporte = max(1, n_simulaciones // 10)

        # Flags por-simulación de "esta simulación terminó en ascenso para
        # este equipo" (directo o por Reducido). Se usan después del loop,
        # sin volver a simular nada, para armar "¿Qué necesita [Equipo]?"
        # (ver modelos/promotion_requirements.py).
        asciende_flags = {
            nombre: np.zeros(n_simulaciones, dtype=bool) for nombre in self.equipos
        }

        # Resuelve TODOS los partidos pendientes de TODAS las simulaciones
        # de una sola vez (vectorizado), en vez de hacerlo partido por
        # partido dentro del loop de abajo -- ver el docstring de
        # _simular_fase_regular_vectorizado() para el detalle. Esto es,
        # por lejos, la parte más pesada de todo el Monte Carlo (la fase
        # regular tiene muchos más partidos que cualquier playoff), así
        # que es donde más rinde vectorizar.
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

            # Acumular puntos y posición de cada equipo, por zona.
            # to_numpy() + zip en vez de itertuples(): itertuples arma un
            # namedtuple por fila (overhead de pandas) para leer solo dos
            # columnas; con arrays de numpy se evita esa construcción.
            # Mismo orden, mismos valores, mismo resultado -- solo cambia
            # cómo se recorren.
            for zona, tabla_zona in tablas.items():
                equipos_col = tabla_zona["equipo"].to_numpy()
                puntos_col = tabla_zona["puntos"].to_numpy()
                for posicion, (nombre_equipo, pts) in enumerate(zip(equipos_col, puntos_col), start=1):
                    contador[nombre_equipo]["puntos_total"] += pts
                    contador[nombre_equipo]["posicion_total"] += posicion

            puntero_a = tablas["A"].iloc[0]["equipo"]
            puntero_b = tablas["B"].iloc[0]["equipo"]
            contador[puntero_a]["puntero_zona"] += 1
            contador[puntero_b]["puntero_zona"] += 1

            ganador, perdedor, _ = self.jugar_final_ascenso(puntero_a, puntero_b)
            contador[ganador]["ascenso_directo"] += 1
            asciende_flags[ganador][i] = True

            campeon_reducido, _ = self.jugar_reducido(tablas, perdedor)
            contador[campeon_reducido]["ascenso_reducido"] += 1
            asciende_flags[campeon_reducido][i] = True

            descendidos_a = tablas["A"].iloc[-2:]["equipo"].tolist()
            descendidos_b = tablas["B"].iloc[-2:]["equipo"].tolist()
            for descendido in descendidos_a + descendidos_b:
                contador[descendido]["descenso"] += 1

            if (i + 1) % paso_reporte == 0:
                print(f"  {i + 1}/{n_simulaciones} simulaciones...")

        # ---  Resumen de ascensos/descensos (igual que antes) ---
        filas = []
        for nombre, datos in contador.items():
            ascenso_total = datos["ascenso_directo"] + datos["ascenso_reducido"]
            filas.append({
                "equipo": nombre,
                "zona": self.equipos[nombre].zona,
                "%puntero_zona": round(100 * datos["puntero_zona"] / n_simulaciones, 1),
                "%ascenso_directo": round(100 * datos["ascenso_directo"] / n_simulaciones, 1),
                "%ascenso_reducido": round(100 * datos["ascenso_reducido"] / n_simulaciones, 1),
                "ascenso_total": round(100 * ascenso_total / n_simulaciones, 1), # ¡Sin %!
                "descenso": round(100 * datos["descenso"] / n_simulaciones, 1),  # ¡Sin %!
            })
        resumen = pd.DataFrame(filas).sort_values("ascenso_total", ascending=False).reset_index(drop=True)
        resumen.index = resumen.index + 1

        # --- Tabla de posición final esperada, por zona ---
        filas_tabla = []
        for nombre, datos in contador.items():
            filas_tabla.append({
                "zona": self.equipos[nombre].zona,
                "equipo": nombre,
                "puntos_prom": round(datos["puntos_total"] / n_simulaciones, 1),
                "posicion_prom": round(datos["posicion_total"] / n_simulaciones, 1),
            })
        tabla_esperada = pd.DataFrame(filas_tabla)

        tabla_esperada_por_zona = {}
        for zona in sorted(tabla_esperada["zona"].unique()):
            tabla_zona = tabla_esperada[tabla_esperada["zona"] == zona].drop(columns=["zona"])
            tabla_zona = tabla_zona.sort_values("posicion_prom").reset_index(drop=True)
            tabla_zona.index = tabla_zona.index + 1
            tabla_esperada_por_zona[zona] = tabla_zona

        # --- "¿Qué necesita [Equipo]?": objeto por equipo para la ficha ---
        # Se arma acá, una sola vez, a partir de los arrays por-simulación
        # que ya calculó _simular_fase_regular_vectorizado() (puntos
        # finales, victorias/empates/derrotas en lo que quedaba de
        # temporada) y de asciende_flags (armado arriba, en este mismo
        # loop). No se vuelve a correr Monte Carlo ni se recalcula nada del
        # motor de simulación -- ver modelos/promotion_requirements.py.
        partidos_restantes_por_equipo = {nombre: 0 for nombre in self.equipos}
        for local, visitante in self._pares_fixture():
            partidos_restantes_por_equipo[local] += 1
            partidos_restantes_por_equipo[visitante] += 1

        self.requisitos_ascenso = {
            nombre: construir_requisitos_ascenso(
                equipo=nombre,
                puntos_actuales=self.equipos[nombre].puntos,
                partidos_restantes=partidos_restantes_por_equipo[nombre],
                puntos_final_sims=totales_vectorizados[nombre]["puntos"],
                victorias_restantes_sims=totales_vectorizados[nombre]["victorias"],
                empates_restantes_sims=totales_vectorizados[nombre]["empates"],
                derrotas_restantes_sims=totales_vectorizados[nombre]["derrotas"],
                asciende_sims=asciende_flags[nombre],
            )
            for nombre in self.equipos
        }

        print("Monte Carlo terminado.")
        return resumen, tabla_esperada_por_zona
    
    K_REGRESION_GOLEADOR = 4  # "partidos virtuales" de peso hacia el ritmo promedio de goleador

    # Probabilidad GENÉRICA de que un jugador esté disponible en un partido
    # dado (no lesionado, no suspendido, no afuera por rotación). No es un
    # dato real de nadie en particular -- no tenemos parte médico de nadie
    # -- es un supuesto razonable a nivel liga para que la simulación
    # contemple ese riesgo como incertidumbre, en vez de asumir que todos
    # los goleadores van a jugar el 100% de los partidos que le quedan a
    # su equipo. Se puede ajustar sin tocar el resto del método.
    PROB_DISPONIBLE = 0.85

    def calcular_goleadores(self, n_simulaciones=1000):
        """
        Lee datos/goleadores.csv (goles acumulados por jugador, sumados
        fecha a fecha por actualizar_resultados.py) y proyecta el total a
        fin de temporada.

        LIMITACIÓN A TENER EN CUENTA: no tenemos partidos jugados/minutos
        por JUGADOR (Promiedos no lo expone fácil), así que se usa como
        aproximación los partidos jugados/restantes de su EQUIPO. Dentro
        de esa limitación, la proyección ahora es un poco más realista
        que una simple regla de tres, con dos mejoras (mismo criterio que
        ya se usa en calcular_ratings() y monte_carlo() en otras partes
        de esta clase, para mantener el modelo consistente):

          1. Regresión a la media (shrinkage): un jugador con pocos
             partidos de muestra (p. ej. 2 goles en las primeras 3 fechas
             de su equipo) se "encoge" hacia el ritmo promedio de goleador
             de la liga, en vez de extrapolarse tal cual — igual que los
             ratings de ataque/defensa de los equipos se regresionan hacia
             1.0 con K_REGRESION. Evita proyecciones disparatadas por
             muestras chicas.

          2. Simulación Monte Carlo (Poisson) de los partidos que le
             quedan al equipo, en vez de multiplicar el ritmo por los
             partidos restantes de forma determinística. Esto da, además
             del valor esperado, un rango realista (proyeccion_min/max)
             que refleja que el número real de goles a fin de temporada
             es incierto, no una cifra exacta.

        Sigue sin contemplar rotación ni que un jugador se vaya a otro
        club — eso ya excede lo que se puede inferir de los datos
        disponibles. Sirve para tener una foto orientativa más sensata,
        no un dato preciso.

        NOVEDADES (lesiones, suspensiones, etc.): Promiedos no expone esta
        info de forma confiable para esta liga, así que no se puede
        scrapear. En cambio, si existe datos/novedades.csv (opcional,
        se carga a mano), con columnas:
            jugador, equipo, partidos_afectados
        se le restan esos partidos a los "pendientes" de ese jugador
        puntual antes de simular — o sea, el modelo asume que no va a
        convertir en esos próximos N partidos de su equipo. Si el
        archivo no existe, el cálculo funciona exactamente igual que
        antes (no rompe nada).

        Devuelve un DataFrame con columnas:
            jugador, equipo, goles (reales a la fecha), proyeccion
            (esperanza de la simulación a fin de temporada),
            proyeccion_min / proyeccion_max (percentiles 20/80 de la
            simulación, como rango orientativo),
            ordenado de mayor a menor proyección.
        Si todavía no se corrió el backfill (no existe el CSV), devuelve
        un DataFrame vacío con esas columnas, sin romper el resto del flujo.
        """
        columnas = ["jugador", "equipo", "goles", "proyeccion", "proyeccion_min", "proyeccion_max"]
        try:
            goleadores = data_access.scorer_totals_df("nacional")
        except Exception as e:
            print(f"\n[aviso] No se pudieron cargar goleadores: {e}")
            return pd.DataFrame(columns=columnas)

        if goleadores.empty:
            return pd.DataFrame(columns=columnas)

        partidos_jugados_equipo = self.tabla.set_index("equipo")["partidos_jugados"]

        restantes_local = self.fixture["equipo_local"].value_counts()
        restantes_visitante = self.fixture["equipo_visitante"].value_counts()
        partidos_restantes_equipo = restantes_local.add(restantes_visitante, fill_value=0)

        # Ritmo promedio de goleador en toda la liga (goles de jugador por
        # partido jugado de su equipo), usado como "ancla" de la regresión
        # a la media. Se calcula solo con jugadores que tienen partidos
        # jugados por su equipo, para no diluirlo con casos sin datos.
        goles_arr = goleadores["goles"].to_numpy(dtype=float)
        jugados_arr = goleadores["equipo"].map(partidos_jugados_equipo).fillna(0).to_numpy(dtype=float)
        con_partidos = jugados_arr > 0
        if con_partidos.any():
            ritmo_promedio_liga = (goles_arr[con_partidos] / jugados_arr[con_partidos]).mean()
        else:
            ritmo_promedio_liga = 0.0

        pendientes_arr = goleadores["equipo"].map(partidos_restantes_equipo).fillna(0).to_numpy(dtype=int)

        # Novedades manuales (lesiones, suspensiones, etc.): si el archivo
        # existe, le restamos a cada jugador afectado sus partidos_afectados
        # de los pendientes que le tocan por equipo, sin bajar de 0.
        try:
            novedades = pd.read_csv(rutas.datos_dir() / "novedades.csv")
            afectados = {
                (fila["jugador"], fila["equipo"]): int(fila["partidos_afectados"])
                for _, fila in novedades.iterrows()
            }
            reduccion = goleadores.apply(
                lambda fila: afectados.get((fila["jugador"], fila["equipo"]), 0), axis=1
            ).to_numpy(dtype=int)
            pendientes_arr = np.maximum(pendientes_arr - reduccion, 0)
        except FileNotFoundError:
            pass  # sin novedades cargadas, funciona igual que antes

        # Ritmo "crudo" observado, y ritmo ajustado por regresión a la media
        with np.errstate(divide="ignore", invalid="ignore"):
            ritmo_bruto = np.where(jugados_arr > 0, goles_arr / np.maximum(jugados_arr, 1), ritmo_promedio_liga)
        K = self.K_REGRESION_GOLEADOR
        ritmo_ajustado = (jugados_arr * ritmo_bruto + K * ritmo_promedio_liga) / (jugados_arr + K)

        # Simulación Monte Carlo de los goles en los partidos restantes:
        # para cada jugador, Poisson(ritmo_ajustado) por cada partido
        # pendiente de su equipo, sumado n_simulaciones veces.
        n_jugadores = len(goleadores)
        max_pendientes = int(pendientes_arr.max()) if n_jugadores > 0 else 0

        proyeccion = np.zeros(n_jugadores)
        proyeccion_min = np.zeros(n_jugadores)
        proyeccion_max = np.zeros(n_jugadores)

        if max_pendientes > 0:
            # Simulamos de una sola vez para todos los jugadores: goles por
            # partido pendiente (matriz jugadores x max_pendientes x sims),
            # y después recortamos cada jugador a sus propios "pendientes"
            # con una máscara (los equipos no todos tienen los mismos
            # partidos restantes).
            #
            # Disponibilidad: para cada partido restante simulado, primero
            # sorteamos si el jugador lo juega (PROB_DISPONIBLE) antes de
            # sortear cuántos goles hace. Si no lo juega, ese partido queda
            # en 0 goles. Para que el PROMEDIO de la proyección no baje
            # artificialmente por esto (el ritmo histórico ya asume que
            # jugó lo que jugó), el lambda usado cuando SÍ está disponible
            # se escala hacia arriba (ritmo / PROB_DISPONIBLE). El efecto
            # neto es que el valor esperado no cambia, pero el rango
            # (proyeccion_min/max) se ensancha para reflejar que en algunas
            # simulaciones el jugador se pierde partidos y en otras los
            # juega todos -- exactamente el tipo de incertidumbre que
            # lesiones/suspensiones/rotación introducen en la realidad,
            # sin necesitar un dato real de qué le pasó a cada uno.
            lam_si_juega = (ritmo_ajustado / self.PROB_DISPONIBLE).reshape(-1, 1, 1)
            goles_si_juega = np.random.poisson(lam=lam_si_juega, size=(n_jugadores, n_simulaciones, max_pendientes))
            disponible = np.random.random(size=(n_jugadores, n_simulaciones, max_pendientes)) < self.PROB_DISPONIBLE
            simulados = goles_si_juega * disponible
            mascara_partidos = (np.arange(max_pendientes).reshape(1, 1, -1) < pendientes_arr.reshape(-1, 1, 1))
            goles_restantes_sim = (simulados * mascara_partidos).sum(axis=2)  # (jugadores, sims)

            totales_sim = goles_arr.reshape(-1, 1) + goles_restantes_sim
            proyeccion = totales_sim.mean(axis=1)
            proyeccion_min = np.percentile(totales_sim, 20, axis=1)
            proyeccion_max = np.percentile(totales_sim, 80, axis=1)
        else:
            proyeccion = goles_arr
            proyeccion_min = goles_arr
            proyeccion_max = goles_arr

        df = pd.DataFrame({
            "jugador": goleadores["jugador"],
            "equipo": goleadores["equipo"],
            "goles": goles_arr.astype(int),
            "proyeccion": np.round(proyeccion, 1),
            "proyeccion_min": np.round(proyeccion_min, 0).astype(int),
            "proyeccion_max": np.round(proyeccion_max, 0).astype(int),
        }, columns=columnas)

        df = df.sort_values(["proyeccion", "goles"], ascending=False).reset_index(drop=True)
        df.index = df.index + 1
        return df

    def backtest(self, frac_test=0.2, n_simulaciones_por_partido=200):
        """Evalúa el modelo con un split temporal: calcula ratings usando solo
        las jornadas más antiguas (entrenamiento) y testea las más recientes,
        comparando probabilidades predichas vs resultado real con Brier score.
        Devuelve (brier_modelo, brier_baseline, detalle_df)."""
        print(f"\nCorriendo backtest (frac_test={frac_test})...")

        jornadas_ordenadas = sorted(self.resultados["jornada"].unique())
        corte_idx = int(len(jornadas_ordenadas) * (1 - frac_test))
        jornada_corte = jornadas_ordenadas[corte_idx]

        resultados_completos = self.resultados
        entrenamiento = resultados_completos[resultados_completos["jornada"] < jornada_corte]
        test = resultados_completos[resultados_completos["jornada"] >= jornada_corte]

        print(f"Entrenamiento: {len(entrenamiento)} partidos (jornadas < {jornada_corte})")
        print(f"Test: {len(test)} partidos (jornadas >= {jornada_corte})")

        if len(entrenamiento) == 0 or len(test) == 0:
            print("No hay suficientes datos para el split. Aborto backtest.")
            return None, None, None

        # Ratings calculados SOLO con el entrenamiento (simula no conocer el futuro)
        self.resultados = entrenamiento
        self.calcular_ratings()

        # Baseline ingenuo: frecuencia histórica de W/D/L, igual para todos los partidos
        p_local_base = (entrenamiento["goles_local"] > entrenamiento["goles_visitante"]).mean()
        p_empate_base = (entrenamiento["goles_local"] == entrenamiento["goles_visitante"]).mean()
        p_visitante_base = (entrenamiento["goles_local"] < entrenamiento["goles_visitante"]).mean()

        briers_modelo = []
        briers_baseline = []
        detalle = []

        for _, partido in test.iterrows():
            local = partido["equipo_local"]
            visitante = partido["equipo_visitante"]
            if local not in self.equipos or visitante not in self.equipos:
                continue

            victorias_local = empates = victorias_visitante = 0
            for _ in range(n_simulaciones_por_partido):
                gl, gv = self.simular_partido(local, visitante)
                if gl > gv:
                    victorias_local += 1
                elif gl == gv:
                    empates += 1
                else:
                    victorias_visitante += 1

            p_local = victorias_local / n_simulaciones_por_partido
            p_empate = empates / n_simulaciones_por_partido
            p_visitante = victorias_visitante / n_simulaciones_por_partido

            gl_real, gv_real = partido["goles_local"], partido["goles_visitante"]
            if gl_real > gv_real:
                real = (1, 0, 0)
            elif gl_real == gv_real:
                real = (0, 1, 0)
            else:
                real = (0, 0, 1)

            brier_modelo = (p_local - real[0])**2 + (p_empate - real[1])**2 + (p_visitante - real[2])**2
            brier_baseline = (p_local_base - real[0])**2 + (p_empate_base - real[1])**2 + (p_visitante_base - real[2])**2

            briers_modelo.append(brier_modelo)
            briers_baseline.append(brier_baseline)

            detalle.append({
                "partido": f"{local} vs {visitante}",
                "resultado_real": f"{gl_real}-{gv_real}",
                "p_local": round(p_local, 2), "p_empate": round(p_empate, 2), "p_visitante": round(p_visitante, 2),
                "brier_modelo": round(brier_modelo, 3), "brier_baseline": round(brier_baseline, 3),
            })

        # Restauramos todo a la temporada completa
        self.resultados = resultados_completos
        self.calcular_ratings()

        brier_modelo_prom = sum(briers_modelo) / len(briers_modelo) if briers_modelo else None
        brier_baseline_prom = sum(briers_baseline) / len(briers_baseline) if briers_baseline else None

        print(f"Brier score modelo:   {brier_modelo_prom:.3f}")
        print(f"Brier score baseline: {brier_baseline_prom:.3f}")
        print("(más bajo = mejor; si el modelo < baseline, los ratings agregan valor real)")

        return brier_modelo_prom, brier_baseline_prom, pd.DataFrame(detalle)
