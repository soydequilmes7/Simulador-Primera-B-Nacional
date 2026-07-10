# -*- coding: utf-8 -*-
"""
Motor de simulación para la Liga Profesional Argentina (LPF), temporada 2026.

Reusa el motor genérico de Estadisticas (simular_partido, Dixon-Coles +
shock Gamma, jugar_partido_unico, etc.) y le agrega todo lo específico de
la LPF que NO tiene Nacional:

  - Un torneo previo YA JUGADO (Apertura 2026, tabla final cargada en
    datos/tablalpf.csv) que sirve de base para:
      (a) estimar los ratings iniciales del Clausura (todavía sin jugarse),
      (b) la Tabla Anual que decide Campeón de Liga, cupos a Libertadores/
          Sudamericana y descensos.
  - Playoffs YA CRUZADOS entre zonas desde los Octavos de Final (a
    diferencia del Reducido de Nacional, que arranca separado por zona).
  - Trofeo de Campeones (Apertura vs. Clausura).

Fuente de las reglas: "Reglamento Torneos Primera División 2026" (LPF/AFA),
capítulos IV (Clausura), VI (Trofeo de Campeones) y VII (Tablas Generales,
descensos y ascensos).
"""
import pandas as pd
import numpy as np

import data_access
import rutas
from modelos.estadisticas import Estadisticas
from fixture_generator import generar_fixture_ida_vuelta


# ---------------------------------------------------------------------
# Normalización de nombres: tablalpf.csv (Apertura, formato abreviado tipo
# Promiedos) usa alias distintos a los de fixture_lpf.csv / el resto del
# proyecto. Completar acá si aparecen más variantes al actualizar datos.
# ---------------------------------------------------------------------
NORMALIZACION_NOMBRES = {
    "Boca Jrs.": "Boca Juniors",
    "Vélez": "Vélez Sarsfield",
    "Central Córdoba": "Central Córdoba SdE",
    "Independiente Riv.": "Independiente Rivadavia",
    "Gimnasia (M)": "Gimnasia de Mendoza",
    "Atl. Tucumán": "Atlético Tucumán",
    "Central": "Rosario Central",
    "Sarmiento": "Sarmiento Junín",
    "Defensa": "Defensa y Justicia",
    "Barracas": "Barracas Central",
    "Talleres": "Talleres de Córdoba",
    "Argentinos": "Argentinos Juniors",
    "Unión": "Unión de Santa Fe",
    "Newell's": "Newell's Old Boys",
    "Racing": "Racing Club",
    "Gimnasia": "Gimnasia La Plata",
    "Estudiantes": "Estudiantes de La Plata",
    "Riestra": "Deportivo Riestra",
    "River": "River Plate",
}


def normalizar(nombre):
    return NORMALIZACION_NOMBRES.get(nombre, nombre)


class EstadisticasLPF(Estadisticas):

    # Campeón del Apertura 2026 (dato real, confirmado): Belgrano.
    CAMPEON_APERTURA = "Belgrano"

    def __init__(self):
        super().__init__()
        self.apertura = None  # tabla final del Apertura (histórico)

    # ------------------------------------------------------------------
    # Carga de datos
    # ------------------------------------------------------------------
    def cargar_datos_lpf(self):
        print("Leyendo datos de LPF...")

        self.resultados, self.fixture, self.apertura = data_access.league_data("lpf")
        self.apertura["equipo"] = self.apertura["equipo"].apply(normalizar)

        # fixture_lpf.csv y resultados_lpf.csv usan los mismos alias
        # "cortos" que tablalpf.csv (p.ej. "Estudiantes" en vez de
        # "Estudiantes de La Plata"). Antes solo se normalizaba
        # self.apertura, así que un alias que SÍ estaba en
        # NORMALIZACION_NOMBRES igual rompía _validar_datos_lpf(): la
        # tabla quedaba con el nombre largo y el fixture con el corto,
        # y ninguna cantidad de alias nuevos lo iba a arreglar porque el
        # fixture nunca pasaba por normalizar(). Se normalizan acá las
        # dos columnas de equipo en fixture y resultados, antes de
        # cualquier comparación o de armar self.tabla/self.equipos.
        for col in ["equipo_local", "equipo_visitante"]:
            self.fixture[col] = self.fixture[col].apply(normalizar)
            self.resultados[col] = self.resultados[col].apply(normalizar)

        # Tabla de promedios (Art. 26 / Estatuto AFA art. 93): puntos y
        # partidos jugados ACUMULADOS ANTES del Apertura 2026 (últimas ~3
        # temporadas). Los recién ascendidos arrancan en 0/0 porque solo
        # computan desde su ascenso. Se les suma la 2026 en
        # calcular_tabla_promedios().
        self.promedios_historicos = data_access.lpf_average_history_df()
        self.promedios_historicos["equipo"] = self.promedios_historicos["equipo"].apply(normalizar)

        # self.tabla es lo que usa crear_equipos() (heredado de Estadisticas)
        # para inicializar cada Equipo. Para el Clausura arranca todo en
        # cero: los puntos/gf/gc de ZONA son solo del Clausura. El Apertura
        # se combina aparte, en calcular_tabla_anual().
        self.tabla = self.apertura.copy()
        for col in ["partidos_jugados", "ganados", "empatados", "perdidos", "gf", "gc", "dg", "puntos"]:
            self.tabla[col] = 0

        self._validar_datos_lpf()


        # CAMPEON_APERTURA dinámico (PLAN_ADDENDUM_ETAPA6_APERTURA_LPF,
        # punto 4). En el flujo real 2026 no hay nada persistido y
        # campeon_apertura_lpf() devuelve None -> cae al default de clase
        # ("Belgrano", el campeón real). En temporadas hipotéticas del Modo
        # Temporada, HistoryManager ya simuló y guardó el campeón del
        # Apertura siguiente (guardar_campeon_apertura_lpf()); lo leemos acá
        # como atributo de instancia que pisa el default de clase, así el
        # Trofeo de Campeones y las copas usan al campeón que de verdad ganó
        # ese Apertura, no siempre "Belgrano".
        campeon_dinamico = data_access.campeon_apertura_lpf()
        if campeon_dinamico:
            self.CAMPEON_APERTURA = normalizar(campeon_dinamico)

        print(f"Apertura (base histórica): {len(self.apertura)} equipos")
        print(f"Fixture Clausura: {len(self.fixture)} partidos pendientes")
        print(f"Resultados Clausura ya jugados: {len(self.resultados)}")
        print(f"Campeón del Apertura: {self.CAMPEON_APERTURA}")

    def _validar_datos_lpf(self):
        columnas_apertura = {"zona", "posicion", "equipo", "partidos_jugados",
                              "ganados", "empatados", "perdidos", "gf", "gc", "dg", "puntos"}
        faltantes = columnas_apertura - set(self.apertura.columns)
        if faltantes:
            raise ValueError(f"tablalpf.csv no tiene las columnas: {faltantes}")

        if len(self.apertura) != 30:
            raise ValueError(f"tablalpf.csv debería tener 30 equipos, tiene {len(self.apertura)}")

        equipos_apertura = set(self.apertura["equipo"])
        equipos_fixture = set(self.fixture["equipo_local"]) | set(self.fixture["equipo_visitante"])
        solo_en_fixture = equipos_fixture - equipos_apertura
        solo_en_apertura = equipos_apertura - equipos_fixture
        if solo_en_fixture or solo_en_apertura:
            raise ValueError(
                "Nombres de equipo no coinciden entre tablalpf.csv y fixture_lpf.csv. "
                f"Solo en fixture: {solo_en_fixture or '-'} | Solo en Apertura: {solo_en_apertura or '-'}. "
                "Agregá el alias que falte a NORMALIZACION_NOMBRES."
            )

        conteo_fixture = pd.concat([self.fixture["equipo_local"], self.fixture["equipo_visitante"]]).value_counts()
        # ANTES: exigía exactamente 16 partidos por equipo. El Clausura
        # real de hoy da 16 porque mezcla equipos de las dos zonas para
        # que las 30 puntas jueguen todas las fechas sin descanso (una
        # zona de 15, impar, necesitaría bye si fuera puramente interna
        # a la zona) -- un algoritmo de scheduling específico que no se
        # puede reconstruir con un round-robin genérico por zona. Lo que
        # realmente hace falta para que el resto del motor funcione es
        # que TODOS los equipos tengan la MISMA cantidad de partidos
        # entre sí (fixture parejo), no que ese número sea 16 en
        # particular -- si se genera una temporada nueva con otra
        # cantidad de fechas, sigue siendo válida mientras sea pareja.
        if conteo_fixture.nunique() > 1:
            # Caso frecuente y confuso: un club asciende con un alias
            # corto sin desambiguar (ver PromotionManager._mover_club,
            # que ahora normaliza esto en el momento del ascenso -- si
            # de todos modos se llega hasta acá, probablemente entró
            # por otro camino, ej. datos cargados a mano o Supabase con
            # el alias corto todavía sin arreglar). El síntoma es
            # SIEMPRE el mismo: un nombre con exactamente el DOBLE de
            # partidos que el resto -- normalizar() fusionó dos clubes
            # distintos en un solo nombre. Se lo señala explícito para
            # no perder tiempo interpretando la tabla de conteos.
            maximo = conteo_fixture.max()
            sospechosos = conteo_fixture[conteo_fixture == maximo].index.tolist()
            pista = ""
            if len(sospechosos) < len(conteo_fixture) and maximo == 2 * conteo_fixture.min():
                pista = (
                    f"\nPinta a colisión de nombres, no a un fixture mal generado: "
                    f"{sospechosos} tiene(n) EXACTAMENTE el doble de partidos que el "
                    f"resto -- normalizar()/NORMALIZACION_NOMBRES probablemente fusionó "
                    f"dos clubes distintos en un solo nombre (típico: un club recién "
                    f"ascendido que llegó con un alias corto sin desambiguar en el "
                    f"origen de datos). Revisar el nombre real de ese club en el origen "
                    f"(Supabase/tablalpf.csv) antes de re-simular."
                )
            raise ValueError(
                f"Los equipos no tienen la misma cantidad de partidos en fixture_lpf.csv "
                f"(debería ser pareja para todos):\n{conteo_fixture}{pista}"
            )

        equipos_promedios = set(self.promedios_historicos["equipo"])
        if equipos_promedios != equipos_apertura:
            raise ValueError(
                "Nombres de equipo no coinciden entre promedios_lpf.csv y tablalpf.csv. "
                f"Solo en promedios: {equipos_promedios - equipos_apertura or '-'} | "
                f"Solo en Apertura: {equipos_apertura - equipos_promedios or '-'}. "
                "Agregá el alias que falte a NORMALIZACION_NOMBRES."
            )

        print("Validación de datos LPF OK.")

    def crear_equipos_lpf(self):
        self.crear_equipos()  # heredado; usa self.tabla (en cero)

    # ------------------------------------------------------------------
    # Ratings iniciales del Clausura
    # ------------------------------------------------------------------
    def calcular_ratings_lpf(self):
        """Si ya hay partidos del Clausura jugados (resultados_lpf.csv no
        vacío), usa calcular_ratings() estándar (idéntico a Nacional, con
        decaimiento por jornada y regresión a la media).

        Si el Clausura todavía no arrancó, no hay de dónde sacar esos
        ratings: se estiman a partir del promedio de goles a favor/en
        contra por partido del Apertura (tablalpf.csv), aplicando la misma
        ventaja de localía que ya usa el motor para separar local/
        visitante (no tenemos el detalle partido a partido del Apertura
        para calcularla con precisión real, esto es una aproximación
        razonable que se autocorrige a medida que el Clausura avanza)."""

        if len(self.resultados) > 0:
            self.calcular_ratings()
            return

        print("\nSin partidos de Clausura jugados: estimando ratings iniciales desde la tabla del Apertura...")

        K_REGRESION = 12
        promedio_liga_neutral = (self.PROMEDIO_GF_LOCAL_LIGA + self.PROMEDIO_GF_VISITANTE_LIGA) / 2
        factor_local = self.PROMEDIO_GF_LOCAL_LIGA / promedio_liga_neutral
        factor_visitante = self.PROMEDIO_GF_VISITANTE_LIGA / promedio_liga_neutral

        gf_prom_liga = (self.apertura["gf"] / self.apertura["partidos_jugados"]).mean()
        gc_prom_liga = (self.apertura["gc"] / self.apertura["partidos_jugados"]).mean()

        for _, fila in self.apertura.iterrows():
            nombre = fila["equipo"]
            equipo = self.equipos[nombre]
            n = int(fila["partidos_jugados"])

            ataque_general = (fila["gf"] / n) / gf_prom_liga
            defensa_general = (fila["gc"] / n) / gc_prom_liga

            equipo.ataque_local = round((n * ataque_general * factor_local + K_REGRESION) / (n + K_REGRESION), 3)
            equipo.ataque_visitante = round((n * ataque_general * factor_visitante + K_REGRESION) / (n + K_REGRESION), 3)
            equipo.defensa_local = round((n * defensa_general * factor_local + K_REGRESION) / (n + K_REGRESION), 3)
            equipo.defensa_visitante = round((n * defensa_general * factor_visitante + K_REGRESION) / (n + K_REGRESION), 3)

        print(f"Ratings iniciales (desde Apertura) calculados para {len(self.equipos)} equipos.")

    def simular_clausura(self):
        """Simula el fixture pendiente del Clausura. Devuelve {"A": df, "B": df}
        con SOLO los puntos/gf/gc del Clausura (arranca de cero)."""
        return self.simular_fase_regular()

    def _simular_clausura_vectorizado(self, n_simulaciones):
        """Igual que simular_clausura() pero para las n_simulaciones de
        Monte Carlo de una sola vez, reusando
        _simular_fase_regular_vectorizado() heredado de Estadisticas (mismo
        modelo, estadísticamente equivalente a simular partido por
        partido). Devuelve el dict {equipo: {puntos, gf, gc}} de arrays
        (n_simulaciones,), SIN armar todavía las tablas por zona (eso se
        arma por-simulación solo donde hace falta, ej. playoffs)."""
        return self._simular_fase_regular_vectorizado(n_simulaciones)

    # ------------------------------------------------------------------
    # Playoffs del Clausura: cruzados entre zonas desde Octavos
    # (Reglamento Art. 14.2 a 14.5)
    # ------------------------------------------------------------------
    def jugar_playoffs(self, tablas_clausura):
        tabla_a, tabla_b = tablas_clausura["A"], tablas_clausura["B"]

        # Listas planas en vez de .iloc[...]["equipo"] repetido (cada
        # llamada arma una Series de pandas entera solo para leer un
        # valor); mismo motivo que en Estadisticas.jugar_reducido().
        equipos_a = tabla_a["equipo"].tolist()
        equipos_b = tabla_b["equipo"].tolist()

        def equipo(lista, posicion):
            return lista[posicion - 1]

        cruces_octavos = [
            (equipo(equipos_a, 1), equipo(equipos_b, 8)),
            (equipo(equipos_b, 1), equipo(equipos_a, 8)),
            (equipo(equipos_a, 2), equipo(equipos_b, 7)),
            (equipo(equipos_b, 2), equipo(equipos_a, 7)),
            (equipo(equipos_a, 3), equipo(equipos_b, 6)),
            (equipo(equipos_b, 3), equipo(equipos_a, 6)),
            (equipo(equipos_a, 4), equipo(equipos_b, 5)),
            (equipo(equipos_b, 4), equipo(equipos_a, 5)),
        ]

        diccionario = {"octavos": [], "cuartos": [], "semis": [], "final": {}}

        ganadores_octavos = []
        for mejor, peor in cruces_octavos:
            ganador, detalle = self.jugar_partido_unico(mejor, peor)
            diccionario["octavos"].append(detalle)
            ganadores_octavos.append(ganador)

        # De Cuartos en adelante, "mejor ubicado" (Art. 14.3.1) se define
        # por la posición en la fase de zonas del Clausura -- usamos la
        # tabla general combinada (ignorando zona) como proxy de eso.
        tabla_general = self._tabla_general(tablas_clausura)
        # Orden ya calculado por _tabla_general(); listas + comprensiones en
        # vez de DataFrame.isin() + reset_index() + iloc para elegir 4-8
        # equipos de una tabla de ~19 filas.
        orden_general = tabla_general["equipo"].tolist()

        ganadores_octavos_set = set(ganadores_octavos)
        seeds_cuartos = [nombre for nombre in orden_general if nombre in ganadores_octavos_set]
        cruces_cuartos = [(0, 7), (1, 6), (2, 5), (3, 4)]
        ganadores_cuartos = []
        for i, j in cruces_cuartos:
            mejor, peor = seeds_cuartos[i], seeds_cuartos[j]
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

        # Final a partido único (no ida y vuelta como el Reducido de
        # Nacional): reusamos jugar_final_ascenso(), que ya tiene cancha
        # neutral + alargue + penales, solo reetiquetando el resultado.
        campeon, subcampeon, detalle_final = self.jugar_final_ascenso(finalistas[0], finalistas[1])
        diccionario["final"] = detalle_final
        diccionario["campeon_clausura"] = campeon
        diccionario["subcampeon_clausura"] = subcampeon

        return campeon, diccionario

    # ------------------------------------------------------------------
    # Playoffs "ilustrativos" del Apertura (Modo Temporada)
    # ------------------------------------------------------------------
    def simular_playoffs_apertura(self):
        """El Apertura 2026 ya se jugó en la realidad y NO tuvo cuadro de
        playoffs -- solo tenemos su tabla final (self.apertura) y el
        campeón real (self.CAMPEON_APERTURA, "Belgrano" por default). No
        hay forma de reconstruir los cruces reales porque ese dato
        simplemente no existe en el proyecto.

        A pedido del usuario, para Modo Temporada se arma un cuadro de
        playoffs FICTICIO del Apertura, simulado con el mismo motor que
        jugar_playoffs() usa para el Clausura (mismo formato de cruces
        desde Octavos), tomando como semillas la tabla final real del
        Apertura por zona. Es puramente ilustrativo: el ganador de este
        cuadro casi seguro NO va a coincidir con self.CAMPEON_APERTURA
        (el campeón real), y el frontend tiene que dejar eso bien claro.
        """
        tablas_apertura = {
            zona: self.apertura[self.apertura["zona"] == zona]
                      .sort_values("posicion")[["equipo", "puntos", "gf", "gc", "dg"]]
                      .reset_index(drop=True)
            for zona in ["A", "B"]
        }

        _, detalle = self.jugar_playoffs(tablas_apertura)

        # jugar_playoffs() devuelve las claves "campeon_clausura" /
        # "subcampeon_clausura" porque ese es su uso normal (Clausura de
        # verdad). Acá se renombran para que quede claro en el JSON que
        # esto es una simulación ficticia del Apertura, y no se pise ni
        # se confunda con self.CAMPEON_APERTURA (el campeón real).
        detalle["campeon_apertura_simulado"] = detalle.pop("campeon_clausura")
        detalle["subcampeon_apertura_simulado"] = detalle.pop("subcampeon_clausura")

        return detalle

    # ------------------------------------------------------------------
    # Tabla Anual, descensos y copas (Reglamento Art. 24, 26, 27, 28)
    # ------------------------------------------------------------------
    def calcular_tabla_anual(self, tablas_clausura):
        """Suma puntos/gf/gc del Apertura (real) + Clausura (simulado) por
        equipo, sin distinguir zona (Art. 24.1)."""
        clausura_combinado = pd.concat(
            [tablas_clausura["A"], tablas_clausura["B"]], ignore_index=True
        )[["equipo", "puntos", "gf", "gc"]].rename(
            columns={"puntos": "puntos_clausura", "gf": "gf_clausura", "gc": "gc_clausura"}
        )

        apertura_base = self.apertura[["equipo", "puntos", "gf", "gc"]].rename(
            columns={"puntos": "puntos_apertura", "gf": "gf_apertura", "gc": "gc_apertura"}
        )

        anual = apertura_base.merge(clausura_combinado, on="equipo", how="outer").fillna(0)
        anual["puntos"] = anual["puntos_apertura"] + anual["puntos_clausura"]
        anual["gf"] = anual["gf_apertura"] + anual["gf_clausura"]
        anual["gc"] = anual["gc_apertura"] + anual["gc_clausura"]
        anual["dg"] = anual["gf"] - anual["gc"]

        anual = anual.sort_values(by=["puntos", "dg", "gf"], ascending=[False, False, False]).reset_index(drop=True)
        anual.index = anual.index + 1
        return anual[["equipo", "puntos", "gf", "gc", "dg"]]

    def _partidos_2026_por_equipo(self):
        """Partidos jugados en la temporada 2026 (Apertura + Clausura) por
        equipo: se suman a los históricos de promedios_lpf.csv. El Clausura
        cuenta los 16 partidos del fixture, ya jugados (resultados_lpf.csv)
        o pendientes (fixture_lpf.csv, se simulan pero cuentan igual)."""
        apertura_pj = self.apertura.set_index("equipo")["partidos_jugados"]
        clausura_pj = pd.concat([
            self.fixture["equipo_local"], self.fixture["equipo_visitante"],
            self.resultados["equipo_local"], self.resultados["equipo_visitante"],
        ]).value_counts()
        return apertura_pj + clausura_pj.reindex(apertura_pj.index).fillna(0)

    def calcular_tabla_promedios(self, tabla_anual):
        """Tabla de promedios (Art. 26 / Estatuto AFA art. 93): puntos por
        partido jugado en las últimas ~3 temporadas. Los recién ascendidos
        (0 históricos en promedios_lpf.csv) solo computan desde su ascenso,
        es decir desde el Apertura 2026 en adelante."""
        partidos_2026 = self._partidos_2026_por_equipo()

        prom = self.promedios_historicos.merge(tabla_anual[["equipo", "puntos"]], on="equipo")
        prom["puntos_totales"] = prom["puntos_historicos"] + prom["puntos"]
        prom["partidos_totales"] = prom["partidos_historicos"] + prom["equipo"].map(partidos_2026)
        prom["promedio"] = prom["puntos_totales"] / prom["partidos_totales"]

        prom = prom.sort_values("promedio", ascending=False).reset_index(drop=True)
        prom.index = prom.index + 1
        return prom[["equipo", "puntos_totales", "partidos_totales", "promedio"]]

    def _calcular_tabla_anual_arrays(self, clausura_tot):
        """Versión vectorizada de calcular_tabla_anual(): en vez de armar
        un DataFrame por simulación, devuelve arrays (n_equipos,
        n_simulaciones) de puntos/gf/gc/dg para TODAS las simulaciones de
        una sola vez. clausura_tot es el dict {equipo: {puntos, gf, gc}}
        de arrays que devuelve _simular_clausura_vectorizado(). El Apertura
        es el mismo para todas las simulaciones (dato real, no se
        simula), así que se suma con broadcasting."""
        nombres = np.array(list(self.equipos.keys()))

        apertura_idx = self.apertura.set_index("equipo")
        puntos_ap = apertura_idx.loc[nombres, "puntos"].to_numpy(dtype=np.float64)
        gf_ap = apertura_idx.loc[nombres, "gf"].to_numpy(dtype=np.float64)
        gc_ap = apertura_idx.loc[nombres, "gc"].to_numpy(dtype=np.float64)

        puntos_cl = np.array([clausura_tot[n]["puntos"] for n in nombres], dtype=np.float64)
        gf_cl = np.array([clausura_tot[n]["gf"] for n in nombres], dtype=np.float64)
        gc_cl = np.array([clausura_tot[n]["gc"] for n in nombres], dtype=np.float64)

        puntos = puntos_ap[:, None] + puntos_cl
        gf = gf_ap[:, None] + gf_cl
        gc = gc_ap[:, None] + gc_cl
        dg = gf - gc

        return {"nombres": nombres, "puntos": puntos, "gf": gf, "gc": gc, "dg": dg}

    def _calcular_tabla_promedios_arrays(self, tabla_anual_arr):
        """Versión vectorizada de calcular_tabla_promedios(): partidos_2026
        es estático (no depende de la simulación), así que solo "puntos"
        varía por simulación -- todo se resuelve con un array (n_equipos,
        n_simulaciones)."""
        nombres = tabla_anual_arr["nombres"]
        hist_idx = self.promedios_historicos.set_index("equipo")
        puntos_hist = hist_idx.loc[nombres, "puntos_historicos"].to_numpy(dtype=np.float64)
        partidos_hist = hist_idx.loc[nombres, "partidos_historicos"].to_numpy(dtype=np.float64)

        partidos_2026 = self._partidos_2026_por_equipo()
        partidos_2026_arr = np.array([partidos_2026.loc[n] for n in nombres], dtype=np.float64)

        puntos_totales = puntos_hist[:, None] + tabla_anual_arr["puntos"]
        partidos_totales = (partidos_hist + partidos_2026_arr)[:, None] * np.ones(
            tabla_anual_arr["puntos"].shape[1]
        )
        promedio = puntos_totales / partidos_totales

        return {
            "nombres": nombres,
            "puntos_totales": puntos_totales,
            "partidos_totales": partidos_totales,
            "promedio": promedio,
        }

    def _calcular_descensos_vectorizado(self, tabla_anual_arr, tabla_promedios_arr):
        """Versión vectorizada de calcular_descensos(): resuelve las
        n_simulaciones de una sola vez para el caso general (sin empates,
        sin coincidencia de descendido), y solo cae a un loop -- llamando
        al calcular_descensos() original sobre un DataFrame armado para
        esa simulación puntual -- en los casos raros de empate real o de
        coincidencia entre el descendido por promedio y el de la tabla
        anual. Esto preserva EXACTAMENTE el mismo comportamiento (incluido
        jugar partidos de desempate) para esos casos, sin pagar el costo
        de por-simulación en el caso común."""
        nombres = tabla_anual_arr["nombres"]
        puntos, gf, gc, dg = (tabla_anual_arr["puntos"], tabla_anual_arr["gf"],
                               tabla_anual_arr["gc"], tabla_anual_arr["dg"])
        promedio = tabla_promedios_arr["promedio"]
        n, S = puntos.shape

        # Clave única ordenable (puntos > dg > gf, todos desc) para rankear
        # las S simulaciones de una sola vez con un solo argsort vectorizado.
        OFFSET_DG = 1000
        key_anual = puntos * 1_000_000_000 + (dg + OFFSET_DG) * 100_000 + gf
        orden_anual = np.argsort(-key_anual, axis=0)  # (n, S), índices de equipo
        idx_ultimo = orden_anual[-1, :]  # peor equipo por sim

        cols = np.arange(S)
        val_puntos_ult = puntos[idx_ultimo, cols]
        val_dg_ult = dg[idx_ultimo, cols]
        val_gf_ult = gf[idx_ultimo, cols]
        empatados_anual = (puntos == val_puntos_ult) & (dg == val_dg_ult) & (gf == val_gf_ult)
        n_empatados_anual = empatados_anual.sum(axis=0)

        idx_peor_prom = np.argmin(promedio, axis=0)
        val_prom_peor = promedio[idx_peor_prom, cols]
        empatados_prom = np.isclose(promedio, val_prom_peor[None, :])
        n_empatados_prom = empatados_prom.sum(axis=0)

        mismo = idx_peor_prom == idx_ultimo
        necesita_fallback = (n_empatados_anual > 1) | (n_empatados_prom > 1) | mismo

        descensos_por_sim = [None] * S
        directos = np.where(~necesita_fallback)[0]
        for s in directos:
            descensos_por_sim[s] = [nombres[idx_peor_prom[s]], nombres[idx_ultimo[s]]]

        for s in np.where(necesita_fallback)[0]:
            tabla_anual_df = pd.DataFrame({
                "equipo": nombres, "puntos": puntos[:, s], "gf": gf[:, s],
                "gc": gc[:, s], "dg": dg[:, s],
            }).sort_values(["puntos", "dg", "gf"], ascending=[False, False, False]).reset_index(drop=True)
            tabla_anual_df.index = tabla_anual_df.index + 1

            tabla_prom_df = pd.DataFrame({
                "equipo": nombres,
                "puntos_totales": tabla_promedios_arr["puntos_totales"][:, s],
                "partidos_totales": tabla_promedios_arr["partidos_totales"][:, s],
                "promedio": promedio[:, s],
            }).sort_values("promedio", ascending=False).reset_index(drop=True)
            tabla_prom_df.index = tabla_prom_df.index + 1

            descensos_por_sim[s] = self.calcular_descensos(tabla_anual_df, tabla_prom_df)

        return descensos_por_sim

    def _definir_por_desempate(self, candidatos):
        """El reglamento no desempata la posición que define un descenso por
        diferencia de gol: se juega un partido de desempate. Con 2 equipos
        empatados alcanza un partido único (cancha neutral, alargue y
        penales si hace falta); con 3+ (caso raro, tipo "cuadrangular")
        aproximamos con desempates sucesivos, cadena de único partido, hasta
        aislar a un solo equipo. Devuelve el PERDEDOR (el que desciende)."""
        if len(candidatos) == 1:
            return candidatos[0]
        peor = candidatos[0]
        for siguiente in candidatos[1:]:
            _, peor, _ = self.jugar_final_ascenso(peor, siguiente)
        return peor

    def calcular_descensos(self, tabla_anual, tabla_promedios):
        """2 descensos (Art. 26 + Estatuto AFA art. 93):
          1) el último de la tabla de promedios.
          2) el último de la Tabla Anual.
        Si es el mismo equipo en ambas, ese cupo lo hereda el penúltimo de
        la Tabla Anual. Los empates en la posición que define un descenso
        se resuelven con partido de desempate, no por diferencia de gol."""
        peor_promedio = tabla_promedios["promedio"].min()
        candidatos_promedios = tabla_promedios.loc[
            tabla_promedios["promedio"] == peor_promedio, "equipo"
        ].tolist()
        descendido_promedios = self._definir_por_desempate(candidatos_promedios)

        def ultimo_de_tabla_anual(tabla):
            ultima = tabla.iloc[-1]
            empatados = tabla.loc[
                (tabla["puntos"] == ultima["puntos"]) &
                (tabla["dg"] == ultima["dg"]) &
                (tabla["gf"] == ultima["gf"]),
                "equipo",
            ].tolist()
            return self._definir_por_desempate(empatados)

        descendido_anual = ultimo_de_tabla_anual(tabla_anual)

        if descendido_promedios == descendido_anual:
            resto = tabla_anual[tabla_anual["equipo"] != descendido_anual]
            segundo_descendido = ultimo_de_tabla_anual(resto)
            return [descendido_promedios, segundo_descendido]

        return [descendido_promedios, descendido_anual]

    def calcular_copas(self, tabla_anual, campeon_clausura):
        """Cupos a Libertadores 2027 (Art. 27) y Sudamericana 2027 (Art. 28).
        No modela Copa Argentina (no está en el alcance de este simulador),
        así que el cupo ARGENTINA 3 (campeón Copa Argentina) queda marcado
        como pendiente en vez de asignado."""
        libertadores = [self.CAMPEON_APERTURA]
        if campeon_clausura != self.CAMPEON_APERTURA:
            libertadores.append(campeon_clausura)
        # ARGENTINA 3 (Copa Argentina): no simulada
        libertadores.append("(Campeón Copa Argentina -- no simulado)")

        ya_clasificados = {self.CAMPEON_APERTURA, campeon_clausura}
        resto_tabla = [e for e in tabla_anual["equipo"] if e not in ya_clasificados]

        libertadores += resto_tabla[:3]  # ARGENTINA 4, 5, 6
        sudamericana = resto_tabla[3:9]  # próximos 6 mejor ubicados

        return {"libertadores_2027": libertadores, "sudamericana_2027": sudamericana}

    # ------------------------------------------------------------------
    # Monte Carlo: corre el Clausura + playoffs + tabla anual n veces.
    # Calcado del patrón de monte_carlo() en Nacional (estadisticas.py).
    # ------------------------------------------------------------------
    def monte_carlo_lpf(self, n_simulaciones=1000):
        print(f"\nCorriendo Monte Carlo LPF ({n_simulaciones} simulaciones)...")

        contador = {
            nombre: {"playoffs": 0, "campeon_clausura": 0, "descenso": 0,
                      "puntos_total": 0, "posicion_total": 0}
            for nombre in self.equipos
        }

        paso_reporte = max(1, n_simulaciones // 10)

        # Igual que en Nacional (ver Estadisticas.monte_carlo()): el Clausura
        # de TODAS las simulaciones se resuelve de una sola vez, vectorizado.
        # Acá además vectorizamos tabla anual, promedios y descensos (que
        # Nacional no tiene) -- ver los docstrings de cada _*_arrays /
        # _calcular_descensos_vectorizado. Lo único que sigue por-simulación
        # es armar la tabla del Clausura (barato, ya no simula partidos) y
        # los playoffs (dependen de la tabla real, no se pueden vectorizar).
        clausura_tot = self._simular_clausura_vectorizado(n_simulaciones)
        tabla_anual_arr = self._calcular_tabla_anual_arrays(clausura_tot)
        tabla_promedios_arr = self._calcular_tabla_promedios_arrays(tabla_anual_arr)
        descensos_por_sim = self._calcular_descensos_vectorizado(tabla_anual_arr, tabla_promedios_arr)

        for i in range(n_simulaciones):
            totales_i = {
                nombre: {
                    "puntos": int(datos["puntos"][i]),
                    "gf": int(datos["gf"][i]),
                    "gc": int(datos["gc"][i]),
                }
                for nombre, datos in clausura_tot.items()
            }
            tablas_clausura = self._armar_tabla_final(totales_i)

            # itertuples() en vez de iterrows(): ver el comentario en
            # Estadisticas.monte_carlo() -- iterrows arma una Series de
            # pandas por fila, mucho más lento que itertuples cuando solo
            # hace falta leer un par de valores, y esto corre una vez por
            # cada una de las 1000+ simulaciones.
            for zona, tabla_zona in tablas_clausura.items():
                for posicion, fila in enumerate(tabla_zona.itertuples(index=False), start=1):
                    contador[fila.equipo]["puntos_total"] += fila.puntos
                    contador[fila.equipo]["posicion_total"] += posicion
                    if posicion <= 8:
                        contador[fila.equipo]["playoffs"] += 1

            campeon_clausura, _ = self.jugar_playoffs(tablas_clausura)
            contador[campeon_clausura]["campeon_clausura"] += 1

            for descendido in descensos_por_sim[i]:
                contador[descendido]["descenso"] += 1

            if (i + 1) % paso_reporte == 0:
                print(f"  {i + 1}/{n_simulaciones} simulaciones...")

        filas = []
        for nombre, datos in contador.items():
            filas.append({
                "equipo": nombre,
                "zona": self.equipos[nombre].zona,
                "%playoffs": round(100 * datos["playoffs"] / n_simulaciones, 1),
                "%campeon_clausura": round(100 * datos["campeon_clausura"] / n_simulaciones, 1),
                "descenso": round(100 * datos["descenso"] / n_simulaciones, 1),
            })
        resumen = pd.DataFrame(filas).sort_values("%playoffs", ascending=False).reset_index(drop=True)
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

        print("Monte Carlo LPF terminado.")
        return resumen, tabla_esperada_por_zona

    def calcular_trofeo_campeones(self, campeon_clausura):
        """Trofeo de Campeones: Apertura vs. Clausura, partido único a
        cancha neutral (Art. 20)."""
        if self.CAMPEON_APERTURA == campeon_clausura:
            # Art. 20.2: mismo equipo campeón de ambos -> el rival sale de
            # un desempate entre subcampeones. No lo simulamos automático.
            return {
                "situacion_especial": True,
                "mensaje": (
                    f"{campeon_clausura} ganó Apertura y Clausura: el rival del Trofeo de "
                    "Campeones sale de un desempate entre los subcampeones de ambos torneos "
                    "(Art. 20.2), no simulado en esta versión."
                ),
            }

        if self.CAMPEON_APERTURA not in self.equipos:
            # El campeón del Apertura ya no está en Primera esta ronda (caso
            # típico de temporadas hipotéticas del Modo Temporada: descendió
            # por promedios/anual pese a haber ganado el Apertura). Sin él no
            # hay final que jugar -- antes esto explotaba con KeyError al
            # buscarlo en self.equipos (jugar_final_ascenso). Se sale
            # limpio en vez de romper la simulación.
            return {
                "situacion_especial": True,
                "mensaje": (
                    f"El campeón del Apertura ({self.CAMPEON_APERTURA}) ya no juega en Primera "
                    "esta temporada (descendió), así que no se disputa el Trofeo de Campeones."
                ),
                "campeon_apertura": self.CAMPEON_APERTURA,
                "campeon_clausura": campeon_clausura,
            }

        ganador, perdedor, detalle = self.jugar_final_ascenso(self.CAMPEON_APERTURA, campeon_clausura)
        detalle["campeon_apertura"] = self.CAMPEON_APERTURA
        detalle["campeon_clausura"] = campeon_clausura
        detalle["campeon_trofeo"] = ganador
        return detalle

    # ------------------------------------------------------------------
    # ETAPA 6 (PLAN_ADDENDUM_ETAPA6_APERTURA_LPF): simular el Apertura de
    # la temporada siguiente en vez de leerlo ya jugado de tablalpf.csv.
    # Ninguno de los métodos de acá abajo toca cargar_datos_lpf(),
    # calcular_ratings_lpf() ni correr_simulacion_lpf() -- el flujo 2026
    # (Clausura desde CSV) sigue exactamente igual.
    # ------------------------------------------------------------------

    def _partidos_jugados_tabla_anual(self, zona_por_club: dict) -> dict:
        """Partidos jugados en la Tabla Anual completa (Apertura +
        Clausura) de la temporada QUE TERMINA, derivados analíticamente
        del tamaño de zona en vez de leerlos de calcular_tabla_anual()
        (que hoy no expone partidos_jugados -- PLAN_ADDENDUM_ETAPA6,
        pendiente explícito resuelto así por decisión del usuario: NO
        tocar calcular_tabla_anual(), derivarlo aparte).

        zona_por_club acá es el reparto de zonas de la temporada QUE
        TERMINA (no el de la temporada siguiente) -- Apertura y
        Clausura de esa temporada comparten esa misma zona (no se
        resortea a mitad de año), así que un club de una zona de
        tamaño n jugó 2*(n-1) partidos en el Apertura y 2*(n-1) en el
        Clausura (todos contra todos ida y vuelta, sin cruces de zona
        en fase regular) -> 4*(n-1) en el año.

        Devuelve {equipo: partidos_jugados}."""
        tamanos_zona: dict = {}
        for zona in zona_por_club.values():
            tamanos_zona[zona] = tamanos_zona.get(zona, 0) + 1
        return {
            club: 4 * (tamanos_zona[zona] - 1)
            for club, zona in zona_por_club.items()
        }

    def ratings_desde_tabla_anual(self, tabla_anual: pd.DataFrame, zona_por_club: dict) -> dict:
        """Ratings iniciales para los clubes que SE QUEDAN en LPF de una
        temporada a la otra (decisión 2a del PLAN_ADDENDUM_ETAPA6):
        misma fórmula de regresión que ya usa calcular_ratings_lpf()
        para bootstrapear el Clausura desde el Apertura (K_REGRESION=12,
        factor_local/visitante contra el promedio de liga), pero
        aplicada sobre la Tabla Anual COMPLETA de la temporada que
        termina (Apertura + Clausura) en vez de sobre self.apertura
        (que ahí es solo el primer torneo). No se factoriza el cálculo
        compartido con calcular_ratings_lpf() para no tocar ese método
        ya validado -- se acepta la duplicación de estas pocas líneas
        de fórmula, documentada acá y ahí.

        tabla_anual: shape de calcular_tabla_anual() -- columnas
            equipo/puntos/gf/gc/dg, SIN partidos_jugados (ver
            _partidos_jugados_tabla_anual).
        zona_por_club: {equipo: "A"|"B"} de la temporada QUE TERMINA
            (para derivar partidos_jugados -- ver
            _partidos_jugados_tabla_anual). Los equipos de tabla_anual
            que no estén acá (ej. quedaron afuera por descenso) se
            ignoran: esta función es solo para los que continúan.

        Devuelve {equipo: {ataque_local, ataque_visitante,
        defensa_local, defensa_visitante}}, solo para los equipos
        presentes en zona_por_club."""
        K_REGRESION = 12
        promedio_liga_neutral = (self.PROMEDIO_GF_LOCAL_LIGA + self.PROMEDIO_GF_VISITANTE_LIGA) / 2
        factor_local = self.PROMEDIO_GF_LOCAL_LIGA / promedio_liga_neutral
        factor_visitante = self.PROMEDIO_GF_VISITANTE_LIGA / promedio_liga_neutral

        partidos_jugados = self._partidos_jugados_tabla_anual(zona_por_club)

        tabla = tabla_anual[tabla_anual["equipo"].isin(zona_por_club.keys())].copy()
        tabla["partidos_jugados"] = tabla["equipo"].map(partidos_jugados)

        gf_prom_liga = (tabla["gf"] / tabla["partidos_jugados"]).mean()
        gc_prom_liga = (tabla["gc"] / tabla["partidos_jugados"]).mean()

        resultado = {}
        for _, fila in tabla.iterrows():
            nombre = fila["equipo"]
            n = fila["partidos_jugados"]

            ataque_general = (fila["gf"] / n) / gf_prom_liga
            defensa_general = (fila["gc"] / n) / gc_prom_liga

            resultado[nombre] = {
                "ataque_local": round((n * ataque_general * factor_local + K_REGRESION) / (n + K_REGRESION), 3),
                "ataque_visitante": round((n * ataque_general * factor_visitante + K_REGRESION) / (n + K_REGRESION), 3),
                "defensa_local": round((n * defensa_general * factor_local + K_REGRESION) / (n + K_REGRESION), 3),
                "defensa_visitante": round((n * defensa_general * factor_visitante + K_REGRESION) / (n + K_REGRESION), 3),
            }
        return resultado

    def simular_apertura_desde_carryover(self, roster: list, zona_por_club: dict, ratings_iniciales: dict):
        """Simula el Apertura de la temporada SIGUIENTE desde cero
        (decisiones 1 y 2 del PLAN_ADDENDUM_ETAPA6_APERTURA_LPF): mismo
        formato que el Clausura -- zonas A/B, todos contra todos ida y
        vuelta, playoffs cruzados desde Octavos (jugar_playoffs()
        heredado, SIN CAMBIOS) -- arrancando de un roster y ratings
        iniciales dados por el caller (season/history_manager.py) en
        vez de leer tablalpf.csv/fixture_lpf.csv/resultados_lpf.csv
        como hace cargar_datos_lpf().

        NO reusa simular_fase_regular() heredado: esa función no
        trackea ganados/empatados/perdidos por equipo (solo puntos/gf/
        gc), y hacen falta para el shape STANDING_COLUMNS completo que
        espera repo.upsert_standings(). Este método arma su propio
        loop sobre self.simular_partido() (mismo motor de partido,
        Dixon-Coles + shock Gamma, sin cambios) con sus propios
        totales W/D/L.

        Pensado para llamarse sobre una instancia NUEVA y dedicada de
        EstadisticasLPF (no la que corrió cargar_datos_lpf()) -- pisa
        self.tabla/self.equipos/self.fixture con los datos del Apertura
        que arranca, no con los del Clausura 2026 en curso.

        roster: list[str], los equipos de LPF de la temporada
            siguiente (después de PromotionManager -- ver
            ClubRegistry.get_by_division("Liga Profesional") en
            history_manager.py).
        zona_por_club: {equipo: "A"|"B"} YA sorteado por
            HistoryManager._sortear_zonas() para la temporada
            siguiente -- Apertura y Clausura de esa temporada van a
            compartir esta misma zona.
        ratings_iniciales: {equipo: {ataque_local, ataque_visitante,
            defensa_local, defensa_visitante}} -- combinación de
            ratings_desde_tabla_anual() (clubes que continúan) +
            RatingCarryoverPolicy.rating_para_recien_llegado()
            (ascendidos), ya armada por el caller. Debe cubrir TODO
            `roster` -- si falta alguno, ValueError (fail-fast: mejor
            eso que arrancar un equipo con el default de
            Equipo.__init__ sin que nadie se entere).

        Devuelve (tabla_standing_por_zona, campeon):
          tabla_standing_por_zona: {"A": list[dict], "B": list[dict]}
            con el shape STANDING_COLUMNS completo (zona/posicion/
            equipo/partidos_jugados/ganados/empatados/perdidos/gf/gc/
            dg/puntos), listo para repo.upsert_standings("lpf", ...).
          campeon: nombre del campeón de los playoffs -- el
            CAMPEON_APERTURA dinámico de la temporada siguiente.
        """
        faltantes = [nombre for nombre in roster if nombre not in ratings_iniciales]
        if faltantes:
            raise ValueError(
                f"Faltan ratings iniciales para: {faltantes} -- "
                "ratings_iniciales debe cubrir TODO el roster."
            )

        # --- armar self.tabla/self.equipos en cero ---
        self.equipos = {}
        self.tabla = pd.DataFrame([
            {
                "zona": zona_por_club[nombre], "posicion": 1, "equipo": nombre,
                "partidos_jugados": 0, "ganados": 0, "empatados": 0,
                "perdidos": 0, "gf": 0, "gc": 0, "dg": 0, "puntos": 0,
            }
            for nombre in roster
        ])
        self.crear_equipos()  # heredado; usa self.tabla (en cero)

        # --- pisar ratings por los del carryover ---
        for nombre, ratings in ratings_iniciales.items():
            equipo = self.equipos[nombre]
            equipo.ataque_local = ratings["ataque_local"]
            equipo.ataque_visitante = ratings["ataque_visitante"]
            equipo.defensa_local = ratings["defensa_local"]
            equipo.defensa_visitante = ratings["defensa_visitante"]

        # --- armar fixture ida y vuelta DENTRO de cada zona ---
        partidos = []
        for zona in sorted(set(zona_por_club.values())):
            clubes_zona = sorted(n for n, z in zona_por_club.items() if z == zona)
            partidos += generar_fixture_ida_vuelta(clubes_zona)

        self.fixture = pd.DataFrame([
            {"fecha": "", "jornada": p.jornada, "equipo_local": p.equipo_local,
             "equipo_visitante": p.equipo_visitante}
            for p in partidos
        ])
        # invalida el cache de _pares_fixture() heredado, por si esta
        # instancia se reusara para otra corrida (no debería, pero es gratis).
        self._pares_fixture_cache = None

        # --- simular partido a partido, con W/D/L propios ---
        totales = {
            nombre: {"pj": 0, "g": 0, "e": 0, "p": 0, "gf": 0, "gc": 0, "puntos": 0}
            for nombre in roster
        }
        for local, visitante in self._pares_fixture():
            gl, gv = self.simular_partido(local, visitante)

            totales[local]["pj"] += 1
            totales[visitante]["pj"] += 1
            totales[local]["gf"] += gl
            totales[local]["gc"] += gv
            totales[visitante]["gf"] += gv
            totales[visitante]["gc"] += gl

            if gl > gv:
                totales[local]["g"] += 1
                totales[local]["puntos"] += 3
                totales[visitante]["p"] += 1
            elif gl < gv:
                totales[visitante]["g"] += 1
                totales[visitante]["puntos"] += 3
                totales[local]["p"] += 1
            else:
                totales[local]["e"] += 1
                totales[visitante]["e"] += 1
                totales[local]["puntos"] += 1
                totales[visitante]["puntos"] += 1

        # --- armar tabla final (shape completo) + shape liviano para playoffs ---
        tabla_standing_por_zona = {}
        tablas_livianas = {}
        for zona in sorted(set(zona_por_club.values())):
            clubes_zona = [n for n, z in zona_por_club.items() if z == zona]
            filas = []
            for nombre in clubes_zona:
                t = totales[nombre]
                filas.append({
                    "equipo": nombre, "partidos_jugados": t["pj"],
                    "ganados": t["g"], "empatados": t["e"], "perdidos": t["p"],
                    "gf": t["gf"], "gc": t["gc"], "dg": t["gf"] - t["gc"],
                    "puntos": t["puntos"],
                })
            # mismo criterio de desempate que _armar_tabla_final(): puntos > dg > gf
            filas.sort(key=lambda f: (-f["puntos"], -f["dg"], -f["gf"]))
            for posicion, fila in enumerate(filas, start=1):
                fila["posicion"] = posicion
                fila["zona"] = zona

            tabla_standing_por_zona[zona] = filas
            tablas_livianas[zona] = pd.DataFrame([
                {"equipo": f["equipo"], "puntos": f["puntos"],
                 "gf": f["gf"], "gc": f["gc"], "dg": f["dg"]}
                for f in filas
            ])

        campeon, _ = self.jugar_playoffs(tablas_livianas)

        return tabla_standing_por_zona, campeon
