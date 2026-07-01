import math
import pandas as pd
import numpy as np

from modelos import equipo
from modelos.equipo import Equipo

class Estadisticas:

    PROMEDIO_GF_LOCAL_LIGA = 1.35
    PROMEDIO_GF_VISITANTE_LIGA = 1.05

    def __init__(self):

        self.resultados = None
        self.fixture = None
        self.tabla = None

        self.equipos = {}

    def cargar_datos(self):

        print("Leyendo archivos...")

        self.resultados = pd.read_csv("datos/resultados.csv")
        self.fixture = pd.read_csv("datos/fixture.csv")
        self.tabla = pd.read_csv("datos/tabla.csv")

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

        print(f"Equipos creados: {len(self.equipos)}")

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
                equipo.ataque_local = round((n * ataque_local_bruto + K_REGRESION * 1.0) / (n + K_REGRESION), 3)
                equipo.defensa_local = round((n * defensa_local_bruto + K_REGRESION * 1.0) / (n + K_REGRESION), 3)

            if len(partidos_visitante) > 0:
                pesos = DECAY ** (jornada_actual - partidos_visitante["jornada"])
                gf_visitante = np.average(partidos_visitante["goles_visitante"], weights=pesos)
                gc_visitante = np.average(partidos_visitante["goles_local"], weights=pesos)

                ataque_visitante_bruto = gf_visitante / promedio_gf_visitante_liga
                defensa_visitante_bruto = gc_visitante / promedio_gc_visitante_liga

                n = len(partidos_visitante)
                equipo.ataque_visitante = round((n * ataque_visitante_bruto + K_REGRESION * 1.0) / (n + K_REGRESION), 3)
                equipo.defensa_visitante = round((n * defensa_visitante_bruto + K_REGRESION * 1.0) / (n + K_REGRESION), 3)

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

        # Probabilidades Poisson independientes para un rango de marcadores razonable
        max_goles = 8
        probs = np.zeros((max_goles + 1, max_goles + 1))
        for x in range(max_goles + 1):
            for y in range(max_goles + 1):
                p_x = (lambda_local ** x) * np.exp(-lambda_local) / math.factorial(x)
                p_y = (lambda_visitante ** y) * np.exp(-lambda_visitante) / math.factorial(y)
                probs[x, y] = p_x * p_y

        # Corrección Dixon-Coles: solo afecta a 0-0, 1-0, 0-1, 1-1
        probs[0, 0] *= 1 - lambda_local * lambda_visitante * RHO
        probs[1, 0] *= 1 + lambda_visitante * RHO
        probs[0, 1] *= 1 + lambda_local * RHO
        probs[1, 1] *= 1 - RHO

        probs = probs / probs.sum()  # renormalizar para que sigan sumando 1

        # Samplear un marcador (x, y) según esas probabilidades ajustadas
        flat_probs = probs.flatten()
        idx = np.random.choice(len(flat_probs), p=flat_probs)
        goles_local, goles_visitante = idx // (max_goles + 1), idx % (max_goles + 1)


        return int(goles_local), int(goles_visitante)
    
    def simular_fase_regular(self):
        """Simula todos los partidos pendientes del fixture y devuelve la tabla final
        de cada zona (puntos, gf, gc, dg), sin modificar los objetos Equipo originales."""

        # Partimos de los totales actuales (ya jugados), copiados aparte
        totales = {
            nombre: {"puntos": equipo.puntos, "gf": equipo.goles_favor, "gc": equipo.goles_contra}
            for nombre, equipo in self.equipos.items()
        }

        for _, partido in self.fixture.iterrows():
            local = partido["equipo_local"]
            visitante = partido["equipo_visitante"]

            gl, gv = self.simular_partido(local, visitante)

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
        Devuelve un dict {"A": DataFrame, "B": DataFrame}."""

        filas = []
        for nombre, datos in totales.items():
            zona = self.equipos[nombre].zona
            dg = datos["gf"] - datos["gc"]
            filas.append({
                "zona": zona, "equipo": nombre,
                "puntos": datos["puntos"], "gf": datos["gf"],
                "gc": datos["gc"], "dg": dg,
            })

        tabla = pd.DataFrame(filas)
        tabla = tabla.sort_values(
            by=["zona", "puntos", "dg", "gf"],
            ascending=[True, False, False, False]
        ).reset_index(drop=True)

        tablas_por_zona = {}
        for zona in sorted(tabla["zona"].unique()):
            tabla_zona = tabla[tabla["zona"] == zona].drop(columns=["zona"]).reset_index(drop=True)
            tabla_zona.index = tabla_zona.index + 1  # posición arranca en 1
            tablas_por_zona[zona] = tabla_zona

        return tablas_por_zona
    
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

    def _mejor_ubicado(self, tabla_general, equipo_x, equipo_y):
        """Devuelve (mejor, peor) según la posición en la tabla general combinada."""
        pos_x = tabla_general.index[tabla_general["equipo"] == equipo_x][0]
        pos_y = tabla_general.index[tabla_general["equipo"] == equipo_y][0]
        return (equipo_x, equipo_y) if pos_x < pos_y else (equipo_y, equipo_x)

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

        def equipo(tabla, posicion):
            return tabla.iloc[posicion - 1]["equipo"]

        cruces_primera_ronda = [
            (equipo(tabla_a, 2), equipo(tabla_b, 8)),
            (equipo(tabla_b, 2), equipo(tabla_a, 8)),
            (equipo(tabla_a, 3), equipo(tabla_b, 7)),
            (equipo(tabla_b, 3), equipo(tabla_a, 7)),
            (equipo(tabla_a, 4), equipo(tabla_b, 6)),
            (equipo(tabla_b, 4), equipo(tabla_a, 6)),
            (equipo(tabla_a, 5), equipo(tabla_b, 5)),
        ]

        tabla_general = self._tabla_general(tablas)

        ganadores_primera_ronda = []
        for x, y in cruces_primera_ronda:
            mejor, peor = self._mejor_ubicado(tabla_general, x, y)
            ganador, detalle = self.jugar_partido_unico(mejor, peor)
            diccionario["primera_ronda"].append(detalle)
            ganadores_primera_ronda.append(ganador)

        clasificados = ganadores_primera_ronda + [perdedor_final_ascenso]
        seeds = tabla_general[tabla_general["equipo"].isin(clasificados)].reset_index(drop=True)

        cruces_cuartos = [(0, 7), (1, 6), (2, 5), (3, 4)]
        ganadores_cuartos = []
        for i, j in cruces_cuartos:
            mejor, peor = seeds.iloc[i]["equipo"], seeds.iloc[j]["equipo"]
            ganador, detalle = self.jugar_partido_unico(mejor, peor)
            diccionario["cuartos"].append(detalle)
            ganadores_cuartos.append(ganador)

        seeds_semis = tabla_general[tabla_general["equipo"].isin(ganadores_cuartos)].reset_index(drop=True)

        finalistas = []
        for i, j in [(0, 3), (1, 2)]:
            mejor, peor = seeds_semis.iloc[i]["equipo"], seeds_semis.iloc[j]["equipo"]
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

        for i in range(n_simulaciones):
            tablas = self.simular_fase_regular()

            # Acumular puntos y posición de cada equipo, por zona
            for zona, tabla_zona in tablas.items():
                for posicion, fila in tabla_zona.iterrows():
                    contador[fila["equipo"]]["puntos_total"] += fila["puntos"]
                    contador[fila["equipo"]]["posicion_total"] += posicion

            puntero_a = tablas["A"].iloc[0]["equipo"]
            puntero_b = tablas["B"].iloc[0]["equipo"]
            contador[puntero_a]["puntero_zona"] += 1
            contador[puntero_b]["puntero_zona"] += 1

            ganador, perdedor, _ = self.jugar_final_ascenso(puntero_a, puntero_b)
            contador[ganador]["ascenso_directo"] += 1

            campeon_reducido, _ = self.jugar_reducido(tablas, perdedor)
            contador[campeon_reducido]["ascenso_reducido"] += 1

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
            goleadores = pd.read_csv("datos/goleadores.csv")
        except FileNotFoundError:
            print("\n[aviso] No existe datos/goleadores.csv todavía — corré "
                  "backfill_goleadores.py una vez para poder calcular esto.")
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
            novedades = pd.read_csv("datos/novedades.csv")
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
        

        