import math
import pandas as pd
import numpy as np

import rutas
import data_access
from modelos import equipo
from modelos.equipo import Equipo

class Estadisticas:
    """Motor de simulación de la Primera C. Calcado de
    modelos/estadisticas.py (B Nacional), con 3 diferencias
    reglamentarias (Boletín Especial N° 6825):

      1. jugar_final_ascenso(): B Nacional la juega a partido único en
         cancha neutral. Primera C la juega a doble partido (ida y
         vuelta), de local en la vuelta el que sacó más puntos en la
         fase regular.

      2. jugar_reducido(): B Nacional toma 2°-8° de cada zona (7+7=14)
         y juega cuartos/semis a partido único. Primera C toma 2°-7°
         de cada zona (6+6=12) y TODAS las rondas son ida y vuelta:
         Primera Fase (6 cruces) -> Segunda Fase (3 cruces) -> se suma
         el perdedor de la Final -> Semifinales (2 cruces) -> Final.

      3. _tabla_general_reducido(): para armar las Semifinales, el
         criterio de "Tabla General" de Primera C no es la tabla
         combinada simple (puntos/dg/gf de ambas zonas mezcladas, como
         en B Nacional) sino: primero posición en la zona propia,
         luego puntos, dg, gf y sorteo -- considerando al perdedor de
         la Final como 1° por reglamento.

    El resto del motor (ratings, simular_partido, Monte Carlo,
    goleadores, backtest) es IDÉNTICO a B Nacional -- no depende de
    ninguna de las reglas de arriba.
    """

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

        print("Leyendo archivos...")

        # Antes: pd.read_csv() directo sobre datos/tabla_primerac.csv +
        # resultados_primerac.csv + fixture_primerac.csv. Eso dejaba a
        # Primera C desconectada de Supabase -- PromotionManager movía
        # a un club ascendido (ej. Berazategui) fuera de Primera C en
        # el ClubRegistry, y HistoryManager.persist_season() armaba el
        # roster nuevo (sin ese club) en Supabase, pero esta función
        # nunca lo leía: seguía devolviendo siempre el mismo CSV
        # estático, con el club ascendido todavía adentro. Mismo
        # patrón que ya usan nacional/lpf/bmetro/federal_a vía
        # data_access.league_data() -- en Pyodide sigue leyendo los
        # mismos 3 CSV (ver data_access.usando_pyodide()), en backend
        # lee de Supabase (con bootstrap automático desde CSV la
        # primera vez, ver data_access.league_data()).
        self.resultados, self.fixture, self.tabla = data_access.league_data("primerac")

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
            equipo_obj = Equipo(fila["equipo"])
            equipo_obj.zona = fila["zona"]

            equipo_obj.puntos = int(fila["puntos"])
            equipo_obj.goles_favor = int(fila["gf"])
            equipo_obj.goles_contra = int(fila["gc"])

            self.equipos[fila["equipo"]] = equipo_obj

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

        for nombre, equipo_obj in self.equipos.items():
            partidos_equipo = resultados_ordenados[
                (resultados_ordenados["equipo_local"] == nombre) |
                (resultados_ordenados["equipo_visitante"] == nombre)
            ]
            equipo_obj.ultimos10 = self._procesar_partidos(partidos_equipo, nombre, ultimos_n=10)

            partidos_local = resultados_ordenados[resultados_ordenados["equipo_local"] == nombre].tail(10)
            equipo_obj.local_gf, equipo_obj.local_gc = self._promedio_goles(partidos_local, "goles_local", "goles_visitante")
            equipo_obj.partidos_local_n = len(partidos_local)

            partidos_visitante = resultados_ordenados[resultados_ordenados["equipo_visitante"] == nombre].tail(10)
            equipo_obj.visitante_gf, equipo_obj.visitante_gc = self._promedio_goles(partidos_visitante, "goles_visitante", "goles_local")
            equipo_obj.partidos_visitante_n = len(partidos_visitante)

        print(f"Estadísticas calculadas para {len(self.equipos)} equipos.")

    def calcular_ratings(self):
        """Calcula fuerza de ataque/defensa de cada equipo (local y visitante)
        relativa al promedio de la liga, ponderando partidos recientes y aplicando
        regresión a la media para equipos con pocos partidos jugados."""
        print("\nCalculando ratings...")

        if len(self.resultados) == 0:
            print(f"Sin partidos jugados todavía: se mantiene el rating prior para los {len(self.equipos)} equipos.")
            return

        DECAY = 0.99        # peso decae con la antigüedad del partido (por jornada)
        K_REGRESION = 12    # "partidos virtuales" de peso hacia el promedio de liga

        promedio_gf_local_liga = self.resultados["goles_local"].mean()
        promedio_gc_local_liga = self.resultados["goles_visitante"].mean()
        promedio_gf_visitante_liga = self.resultados["goles_visitante"].mean()
        promedio_gc_visitante_liga = self.resultados["goles_local"].mean()

        jornada_actual = self.resultados["jornada"].max()

        for nombre, equipo_obj in self.equipos.items():
            partidos_local = self.resultados[self.resultados["equipo_local"] == nombre]
            partidos_visitante = self.resultados[self.resultados["equipo_visitante"] == nombre]

            if len(partidos_local) > 0:
                pesos = DECAY ** (jornada_actual - partidos_local["jornada"])
                gf_local = np.average(partidos_local["goles_local"], weights=pesos)
                gc_local = np.average(partidos_local["goles_visitante"], weights=pesos)

                ataque_local_bruto = gf_local / promedio_gf_local_liga
                defensa_local_bruto = gc_local / promedio_gc_local_liga

                n = len(partidos_local)
                equipo_obj.ataque_local = round((n * ataque_local_bruto + K_REGRESION * equipo_obj.ataque_local) / (n + K_REGRESION), 3)
                equipo_obj.defensa_local = round((n * defensa_local_bruto + K_REGRESION * equipo_obj.defensa_local) / (n + K_REGRESION), 3)

            if len(partidos_visitante) > 0:
                pesos = DECAY ** (jornada_actual - partidos_visitante["jornada"])
                gf_visitante = np.average(partidos_visitante["goles_visitante"], weights=pesos)
                gc_visitante = np.average(partidos_visitante["goles_local"], weights=pesos)

                ataque_visitante_bruto = gf_visitante / promedio_gf_visitante_liga
                defensa_visitante_bruto = gc_visitante / promedio_gc_visitante_liga

                n = len(partidos_visitante)
                equipo_obj.ataque_visitante = round((n * ataque_visitante_bruto + K_REGRESION * equipo_obj.ataque_visitante) / (n + K_REGRESION), 3)
                equipo_obj.defensa_visitante = round((n * defensa_visitante_bruto + K_REGRESION * equipo_obj.defensa_visitante) / (n + K_REGRESION), 3)

        print(f"Ratings calculados para {len(self.equipos)} equipos.")

    # Forma del Gamma que genera el "shock" de partido (media=1). Más bajo
    # = más variable (más dispersión extra sobre el Poisson puro); más
    # alto = shock casi nulo, se acerca al Poisson puro de antes. 10 es un
    # punto medio razonable: sube la varianza de goles por partido sin
    # volverla descontrolada. Ajustable sin tocar el resto del método.
    K_SHOCK_PARTIDO = 10

    def simular_partido(self, nombre_local, nombre_visitante):
        """Simula el resultado de un partido cruzando ataque de un equipo
        con defensa del rival, con dos correcciones sobre el Poisson puro
        (Dixon-Coles + mezcla Poisson-Gamma). Idéntico a B Nacional."""

        RHO = -0.1  # correlación negativa típica entre goles local/visitante en marcadores bajos

        local = self.equipos[nombre_local]
        visitante = self.equipos[nombre_visitante]

        lambda_local_base = local.ataque_local * visitante.defensa_visitante * self.PROMEDIO_GF_LOCAL_LIGA
        lambda_visitante_base = visitante.ataque_visitante * local.defensa_local * self.PROMEDIO_GF_VISITANTE_LIGA

        shock_local = np.random.gamma(shape=self.K_SHOCK_PARTIDO, scale=1 / self.K_SHOCK_PARTIDO)
        shock_visitante = np.random.gamma(shape=self.K_SHOCK_PARTIDO, scale=1 / self.K_SHOCK_PARTIDO)

        lambda_local = lambda_local_base * shock_local
        lambda_visitante = lambda_visitante_base * shock_visitante

        k = self._RANGO_GOLES
        p_x = (lambda_local ** k) * np.exp(-lambda_local) / self._FACTORIALES
        p_y = (lambda_visitante ** k) * np.exp(-lambda_visitante) / self._FACTORIALES
        probs = np.outer(p_x, p_y)

        # Corrección Dixon-Coles: solo afecta a 0-0, 1-0, 0-1, 1-1
        probs[0, 0] *= 1 - lambda_local * lambda_visitante * RHO
        probs[1, 0] *= 1 + lambda_visitante * RHO
        probs[0, 1] *= 1 + lambda_local * RHO
        probs[1, 1] *= 1 - RHO

        flat_probs = probs.ravel()
        flat_probs = flat_probs / flat_probs.sum()
        idx = np.random.choice(flat_probs.size, p=flat_probs)
        max_goles = self._MAX_GOLES
        goles_local, goles_visitante = idx // (max_goles + 1), idx % (max_goles + 1)

        return int(goles_local), int(goles_visitante)

    def _pares_fixture(self):
        """Lista (local, visitante) de los partidos pendientes, cacheada."""
        if getattr(self, "_pares_fixture_cache", None) is None:
            self._pares_fixture_cache = list(
                self.fixture[["equipo_local", "equipo_visitante"]].itertuples(index=False, name=None)
            )
        return self._pares_fixture_cache

    def simular_fase_regular(self):
        """Simula todos los partidos pendientes del fixture y devuelve la tabla final
        de cada zona (puntos, gf, gc, dg), sin modificar los objetos Equipo originales."""

        totales = {
            nombre: {"puntos": equipo_obj.puntos, "gf": equipo_obj.goles_favor, "gc": equipo_obj.goles_contra}
            for nombre, equipo_obj in self.equipos.items()
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
        Devuelve un dict {"A": DataFrame, "B": DataFrame}, con índice
        (empezando en 1) igual a la posición dentro de la zona."""

        nombres = np.array(list(totales.keys()))
        zonas = np.array([self.equipos[n].zona for n in nombres])
        puntos = np.array([totales[n]["puntos"] for n in nombres])
        gf = np.array([totales[n]["gf"] for n in nombres])
        gc = np.array([totales[n]["gc"] for n in nombres])
        dg = gf - gc

        tablas_por_zona = {}
        for zona in sorted(set(zonas.tolist())):
            mask = zonas == zona
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
        Monte Carlo. Idéntica a B Nacional -- no depende de ninguna
        regla específica de Primera C."""
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
            return {
                nombre: {
                    "puntos": np.full(S, puntos_base[i], dtype=np.int64),
                    "gf": np.full(S, gf_base[i], dtype=np.int64),
                    "gc": np.full(S, gc_base[i], dtype=np.int64),
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

        RHO = -0.1
        K_SHOCK = self.K_SHOCK_PARTIDO
        k = self._RANGO_GOLES        # 0..8
        fact = self._FACTORIALES
        max_goles = self._MAX_GOLES
        n_marcadores = (max_goles + 1) * (max_goles + 1)  # 81

        puntos_tot = np.zeros((n_equipos, S), dtype=np.int64)
        gf_tot = np.zeros((n_equipos, S), dtype=np.int64)
        gc_tot = np.zeros((n_equipos, S), dtype=np.int64)
        puntos_tot[:] = puntos_base[:, None]
        gf_tot[:] = gf_base[:, None]
        gc_tot[:] = gc_base[:, None]

        tanda = max(1, min(S, max_elems_por_bloque // max(1, M * n_marcadores)))

        for inicio in range(0, S, tanda):
            s = min(tanda, S - inicio)

            shock_local = np.random.gamma(shape=K_SHOCK, scale=1 / K_SHOCK, size=(M, s))
            shock_visitante = np.random.gamma(shape=K_SHOCK, scale=1 / K_SHOCK, size=(M, s))

            lambda_local = lambda_local_base[:, None] * shock_local          # (M, s)
            lambda_visitante = lambda_visitante_base[:, None] * shock_visitante

            p_x = (lambda_local[..., None] ** k) * np.exp(-lambda_local)[..., None] / fact   # (M, s, 9)
            p_y = (lambda_visitante[..., None] ** k) * np.exp(-lambda_visitante)[..., None] / fact

            probs = p_x[..., :, None] * p_y[..., None, :]  # (M, s, 9, 9)

            probs[..., 0, 0] *= 1 - lambda_local * lambda_visitante * RHO
            probs[..., 1, 0] *= 1 + lambda_visitante * RHO
            probs[..., 0, 1] *= 1 + lambda_local * RHO
            probs[..., 1, 1] *= 1 - RHO

            flat = probs.reshape(M, s, n_marcadores)
            flat = flat / flat.sum(axis=-1, keepdims=True)

            cumulativo = np.cumsum(flat, axis=-1)
            r = np.random.random((M, s, 1))
            idx_marcador = (cumulativo < r).sum(axis=-1)  # (M, s), valores 0..80

            goles_local = idx_marcador // (max_goles + 1)
            goles_visitante = idx_marcador % (max_goles + 1)

            gana_local = goles_local > goles_visitante
            gana_visitante = goles_local < goles_visitante
            empate = ~gana_local & ~gana_visitante

            pts_local = np.where(gana_local, 3, np.where(empate, 1, 0))
            pts_visitante = np.where(gana_visitante, 3, np.where(empate, 1, 0))

            bloque_puntos = puntos_tot[:, inicio:inicio + s]
            bloque_gf = gf_tot[:, inicio:inicio + s]
            bloque_gc = gc_tot[:, inicio:inicio + s]

            np.add.at(bloque_puntos, idx_local, pts_local)
            np.add.at(bloque_puntos, idx_visitante, pts_visitante)
            np.add.at(bloque_gf, idx_local, goles_local)
            np.add.at(bloque_gf, idx_visitante, goles_visitante)
            np.add.at(bloque_gc, idx_local, goles_visitante)
            np.add.at(bloque_gc, idx_visitante, goles_local)

        return {
            nombre: {
                "puntos": puntos_tot[i],
                "gf": gf_tot[i],
                "gc": gc_tot[i],
            }
            for i, nombre in enumerate(nombres_equipos)
        }

    # =================================================================
    # DIFERENCIA #1 vs B Nacional: Final por el 1er Ascenso a doble
    # partido (no partido único en cancha neutral).
    # =================================================================
    def jugar_final_ascenso(self, tablas):
        """Simula la Final por el 1er Ascenso entre el puntero de Zona A
        y el puntero de Zona B: DOBLE PARTIDO (ida y vuelta), de local
        en la vuelta el que sacó más puntos en la fase regular (Boletín
        6825, punto 2). Si empatan en puntos, desempata dg y después gf
        de la fase regular (mismo criterio de la Tabla Final de
        Posiciones); si sigue empatado, sorteo -- el reglamento no lo
        aclara para este caso puntual.

        Devuelve (ganador, perdedor, detalle_dict) -- mismo shape que
        jugar_serie_ida_vuelta(), para que main_primerac.py no tenga
        que tratarlo distinto del resto de las series ida/vuelta.
        """
        fila_a = tablas["A"].iloc[0]
        fila_b = tablas["B"].iloc[0]
        nombre_a, nombre_b = fila_a["equipo"], fila_b["equipo"]

        for campo in ("puntos", "dg", "gf"):
            if fila_a[campo] != fila_b[campo]:
                mejor, peor = (nombre_a, nombre_b) if fila_a[campo] > fila_b[campo] else (nombre_b, nombre_a)
                break
        else:
            mejor, peor = (nombre_a, nombre_b) if np.random.random() < 0.5 else (nombre_b, nombre_a)

        # Local en la vuelta: "mejor" (más puntos). Local en la ida: "peor".
        ganador, detalle = self.jugar_serie_ida_vuelta(peor, mejor)
        perdedor = peor if ganador == mejor else mejor

        detalle["equipo_a"] = nombre_a
        detalle["equipo_b"] = nombre_b
        return ganador, perdedor, detalle

    def _info_equipo(self, tablas, nombre):
        """Zona, posición (índice de la tabla final de esa zona), puntos,
        dg y gf de un equipo, buscándolo en las tablas de ambas zonas."""
        for zona, tabla_zona in tablas.items():
            fila = tabla_zona[tabla_zona["equipo"] == nombre]
            if not fila.empty:
                fila = fila.iloc[0]
                return {
                    "zona": zona,
                    "posicion": int(fila.name),
                    "puntos": int(fila["puntos"]),
                    "dg": int(fila["dg"]),
                    "gf": int(fila["gf"]),
                }
        return None

    def _mejor_ubicado_por_tabla(self, tablas, equipo_x, equipo_y):
        """¿Cuál de los dos está mejor ubicado en la Tabla Final de
        Posiciones de su zona? Menor número de posición gana. Si ambos
        ocupan la MISMA posición numérica en zonas distintas (el caso
        del Partido C de la Segunda Fase del Reducido, ej. 3°A vs 3°B),
        desempata por puntos, luego dg, luego gf, luego sorteo (Boletín
        6825, punto 6, párrafo de la Segunda Fase)."""
        info_x = self._info_equipo(tablas, equipo_x)
        info_y = self._info_equipo(tablas, equipo_y)

        if info_x["posicion"] != info_y["posicion"]:
            return (equipo_x, equipo_y) if info_x["posicion"] < info_y["posicion"] else (equipo_y, equipo_x)

        for campo in ("puntos", "dg", "gf"):
            if info_x[campo] != info_y[campo]:
                return (equipo_x, equipo_y) if info_x[campo] > info_y[campo] else (equipo_y, equipo_x)

        return (equipo_x, equipo_y) if np.random.random() < 0.5 else (equipo_y, equipo_x)

    def _tabla_general_reducido(self, tablas, integrantes, perdedor_final_ascenso):
        """Arma el orden de la "Tabla General" que arma las Semifinales y
        la Final del Reducido (Boletín 6825, punto 6): primero posición
        en la Tabla Final de Posiciones de su propia zona, luego puntos,
        dg, gf y sorteo -- considerando al perdedor de la Final por el
        1er Ascenso como 1° por decreto reglamentario (no por
        comparación real de sus números)."""
        filas = []
        for nombre in integrantes:
            if nombre == perdedor_final_ascenso:
                # posición "0": mejor que cualquier posición real (que
                # arranca en 2, porque el 1° de cada zona ya jugó la
                # Final). Así queda 1° sin ambigüedad, tal como lo fija
                # el reglamento, sin necesitar comparar puntos/dg/gf.
                filas.append({"equipo": nombre, "posicion": 0, "puntos": 0, "dg": 0, "gf": 0})
            else:
                filas.append({"equipo": nombre, **self._info_equipo(tablas, nombre)})

        filas.sort(key=lambda f: (f["posicion"], -f["puntos"], -f["dg"], -f["gf"]))
        return [f["equipo"] for f in filas]

    # =================================================================
    # DIFERENCIA #2 vs B Nacional: Reducido con 2°-7° de cada zona
    # (12 equipos, no 14) y TODAS las rondas a doble partido.
    # =================================================================
    def jugar_reducido(self, tablas, perdedor_final_ascenso):
        """Torneo Reducido por el 2° Ascenso (Boletín 6825, punto 6):

        Primera Fase (6 cruces, ida y vuelta, local en la vuelta el
        equipo mejor ubicado -- 2°/3°/4° de su zona):
            P1: 2°A - 7°B      P2: 2°B - 7°A
            P3: 3°A - 6°B      P4: 3°B - 6°A
            P5: 4°A - 5°B      P6: 4°B - 5°A

        Segunda Fase (3 cruces, ida y vuelta, local en la vuelta el
        mejor ubicado en la Tabla Final de Posiciones):
            A) ganador P1 - ganador P6
            B) ganador P2 - ganador P5
            C) ganador P3 - ganador P4

        Semifinales: se suman los 3 ganadores de la Segunda Fase + el
        perdedor de la Final por el 1er Ascenso, se arma la "Tabla
        General" (ver _tabla_general_reducido) y se cruzan 1°-4° y
        2°-3°, ida y vuelta.

        Final: los 2 ganadores de semis, ida y vuelta.
        """
        tabla_a, tabla_b = tablas["A"], tablas["B"]

        diccionario = {
            "perdedor_final_ascenso": perdedor_final_ascenso,
            "primera_fase": [],
            "segunda_fase": [],
            "semifinales": [],
            "final": {}
        }

        equipos_a = tabla_a["equipo"].tolist()
        equipos_b = tabla_b["equipo"].tolist()

        def equipo_pos(lista, posicion):
            return lista[posicion - 1]

        # --- Primera Fase ---
        # Cada tupla es (mejor_ubicado, peor_ubicado); "mejor_ubicado"
        # es local en la vuelta.
        cruces_primera_fase = [
            (equipo_pos(equipos_a, 2), equipo_pos(equipos_b, 7)),  # Partido 1
            (equipo_pos(equipos_b, 2), equipo_pos(equipos_a, 7)),  # Partido 2
            (equipo_pos(equipos_a, 3), equipo_pos(equipos_b, 6)),  # Partido 3
            (equipo_pos(equipos_b, 3), equipo_pos(equipos_a, 6)),  # Partido 4
            (equipo_pos(equipos_a, 4), equipo_pos(equipos_b, 5)),  # Partido 5
            (equipo_pos(equipos_b, 4), equipo_pos(equipos_a, 5)),  # Partido 6
        ]

        ganadores_primera_fase = []
        for mejor, peor in cruces_primera_fase:
            ganador, detalle = self.jugar_serie_ida_vuelta(peor, mejor)
            diccionario["primera_fase"].append(detalle)
            ganadores_primera_fase.append(ganador)

        g1, g2, g3, g4, g5, g6 = ganadores_primera_fase

        # --- Segunda Fase ---
        cruces_segunda_fase = [
            (g1, g6),  # Partido A
            (g2, g5),  # Partido B
            (g3, g4),  # Partido C (acá puede darse el empate de posición, ej. 3°A vs 3°B)
        ]

        ganadores_segunda_fase = []
        for x, y in cruces_segunda_fase:
            mejor, peor = self._mejor_ubicado_por_tabla(tablas, x, y)
            ganador, detalle = self.jugar_serie_ida_vuelta(peor, mejor)
            diccionario["segunda_fase"].append(detalle)
            ganadores_segunda_fase.append(ganador)

        # --- Semifinales ---
        integrantes_semis = ganadores_segunda_fase + [perdedor_final_ascenso]
        orden_general = self._tabla_general_reducido(tablas, integrantes_semis, perdedor_final_ascenso)
        posiciones_generales = {nombre: i for i, nombre in enumerate(orden_general)}

        cruces_semis = [
            (orden_general[0], orden_general[3]),
            (orden_general[1], orden_general[2]),
        ]

        finalistas = []
        for x, y in cruces_semis:
            mejor, peor = (x, y) if posiciones_generales[x] < posiciones_generales[y] else (y, x)
            ganador, detalle = self.jugar_serie_ida_vuelta(peor, mejor)
            diccionario["semifinales"].append(detalle)
            finalistas.append(ganador)

        # --- Final ---
        f1, f2 = finalistas
        mejor, peor = (f1, f2) if posiciones_generales[f1] < posiciones_generales[f2] else (f2, f1)
        campeon, detalle_final = self.jugar_serie_ida_vuelta(peor, mejor)
        diccionario["final"] = detalle_final

        return campeon, diccionario

    def jugar_partido_unico(self, mejor, peor):
        """Se mantiene por si hace falta en el futuro (ej. el partido por
        la desafiliación, que sí es a partido único). Primera C no usa
        esto en jugar_reducido() -- ahí todas las rondas son ida/vuelta."""
        gl, gv = self.simular_partido(mejor, peor)
        ganador = mejor if gl >= gv else peor

        detalle = {
            "local": mejor,
            "visitante": peor,
            "golesLocal": gl,
            "golesVisitante": gv,
            "avanza": ganador
        }
        return ganador, detalle

    def jugar_serie_ida_vuelta(self, equipo_x, equipo_y):
        """equipo_x es local en la ida, equipo_y es local en la vuelta.
        Empate en puntos/goles agregados -> penales (50/50). Idéntico a
        B Nacional; el reglamento de Primera C usa el mismo criterio de
        desempate para el Reducido y (sin alargue) para la Final por el
        1er Ascenso."""
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
            "equipo_x": equipo_x,
            "equipo_y": equipo_y,
            "goles_x": goles_x,
            "goles_y": goles_y,
            "detalle": detalle_str,
            "campeon": ganador
        }
        return ganador, detalle

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
        """Corre la fase regular + ascensos n_simulaciones veces y
        devuelve (resumen_ascensos, tabla_esperada_por_zona).

        DIFERENCIA vs B Nacional: Primera C no tiene "descenso" en el
        sentido tradicional (ya es la categoría más baja de AFA); en
        cambio, el último de cada zona juega un partido por la
        SUSPENSIÓN DE AFILIACIÓN (Boletín 6825, punto 7). Ese partido
        depende además del rival del Torneo Promocional Amateur, que
        este motor no simula -- así que en vez de "%descenso" se
        reporta "%riesgo_ultimo" (probabilidad de terminar último de su
        zona, que es lo que dispara ese partido)."""
        print(f"\nCorriendo Monte Carlo ({n_simulaciones} simulaciones)...")

        contador = {
            nombre: {"puntero_zona": 0, "ascenso_directo": 0, "ascenso_reducido": 0, "riesgo_ultimo": 0,
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

            ganador, perdedor, _ = self.jugar_final_ascenso(tablas)
            contador[ganador]["ascenso_directo"] += 1

            campeon_reducido, _ = self.jugar_reducido(tablas, perdedor)
            contador[campeon_reducido]["ascenso_reducido"] += 1

            ultimo_a = tablas["A"].iloc[-1]["equipo"]
            ultimo_b = tablas["B"].iloc[-1]["equipo"]
            contador[ultimo_a]["riesgo_ultimo"] += 1
            contador[ultimo_b]["riesgo_ultimo"] += 1

            if (i + 1) % paso_reporte == 0:
                print(f"  {i + 1}/{n_simulaciones} simulaciones...")

        filas = []
        for nombre, datos in contador.items():
            ascenso_total = datos["ascenso_directo"] + datos["ascenso_reducido"]
            filas.append({
                "equipo": nombre,
                "zona": self.equipos[nombre].zona,
                "%puntero_zona": round(100 * datos["puntero_zona"] / n_simulaciones, 1),
                "%ascenso_directo": round(100 * datos["ascenso_directo"] / n_simulaciones, 1),
                "%ascenso_reducido": round(100 * datos["ascenso_reducido"] / n_simulaciones, 1),
                "ascenso_total": round(100 * ascenso_total / n_simulaciones, 1),
                "riesgo_ultimo": round(100 * datos["riesgo_ultimo"] / n_simulaciones, 1),
            })
        resumen = pd.DataFrame(filas).sort_values("ascenso_total", ascending=False).reset_index(drop=True)
        resumen.index = resumen.index + 1

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
    PROB_DISPONIBLE = 0.85    # probabilidad genérica de que un jugador esté disponible en un partido dado

    def calcular_goleadores(self, n_simulaciones=1000):
        """Igual que en B Nacional: lee datos/goleadores.csv y proyecta
        el total a fin de temporada con regresión a la media + Monte
        Carlo de los partidos que le quedan al EQUIPO del jugador (no
        hay dato de minutos/partidos por jugador)."""
        columnas = ["jugador", "equipo", "goles", "proyeccion", "proyeccion_min", "proyeccion_max"]
        try:
            goleadores = pd.read_csv(rutas.datos_dir() / "goleadores_primerac.csv")
        except FileNotFoundError:
            print("\n[aviso] No existe datos/goleadores_primerac.csv todavía — corré "
                  "un backfill de goleadores una vez para poder calcular esto.")
            return pd.DataFrame(columns=columnas)

        if goleadores.empty:
            return pd.DataFrame(columns=columnas)

        partidos_jugados_equipo = self.tabla.set_index("equipo")["partidos_jugados"]

        restantes_local = self.fixture["equipo_local"].value_counts()
        restantes_visitante = self.fixture["equipo_visitante"].value_counts()
        partidos_restantes_equipo = restantes_local.add(restantes_visitante, fill_value=0)

        goles_arr = goleadores["goles"].to_numpy(dtype=float)
        jugados_arr = goleadores["equipo"].map(partidos_jugados_equipo).fillna(0).to_numpy(dtype=float)
        con_partidos = jugados_arr > 0
        if con_partidos.any():
            ritmo_promedio_liga = (goles_arr[con_partidos] / jugados_arr[con_partidos]).mean()
        else:
            ritmo_promedio_liga = 0.0

        pendientes_arr = goleadores["equipo"].map(partidos_restantes_equipo).fillna(0).to_numpy(dtype=int)

        try:
            novedades = pd.read_csv(rutas.datos_dir() / "novedades_primerac.csv")
            afectados = {
                (fila["jugador"], fila["equipo"]): int(fila["partidos_afectados"])
                for _, fila in novedades.iterrows()
            }
            reduccion = goleadores.apply(
                lambda fila: afectados.get((fila["jugador"], fila["equipo"]), 0), axis=1
            ).to_numpy(dtype=int)
            pendientes_arr = np.maximum(pendientes_arr - reduccion, 0)
        except FileNotFoundError:
            pass

        with np.errstate(divide="ignore", invalid="ignore"):
            ritmo_bruto = np.where(jugados_arr > 0, goles_arr / np.maximum(jugados_arr, 1), ritmo_promedio_liga)
        K = self.K_REGRESION_GOLEADOR
        ritmo_ajustado = (jugados_arr * ritmo_bruto + K * ritmo_promedio_liga) / (jugados_arr + K)

        n_jugadores = len(goleadores)
        max_pendientes = int(pendientes_arr.max()) if n_jugadores > 0 else 0

        proyeccion = np.zeros(n_jugadores)
        proyeccion_min = np.zeros(n_jugadores)
        proyeccion_max = np.zeros(n_jugadores)

        if max_pendientes > 0:
            lam_si_juega = (ritmo_ajustado / self.PROB_DISPONIBLE).reshape(-1, 1, 1)
            goles_si_juega = np.random.poisson(lam=lam_si_juega, size=(n_jugadores, n_simulaciones, max_pendientes))
            disponible = np.random.random(size=(n_jugadores, n_simulaciones, max_pendientes)) < self.PROB_DISPONIBLE
            simulados = goles_si_juega * disponible
            mascara_partidos = (np.arange(max_pendientes).reshape(1, 1, -1) < pendientes_arr.reshape(-1, 1, 1))
            goles_restantes_sim = (simulados * mascara_partidos).sum(axis=2)

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
