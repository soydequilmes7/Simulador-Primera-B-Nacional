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

import rutas
from modelos.estadisticas import Estadisticas


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
        print("Leyendo archivos de LPF...")
        datos_dir = rutas.datos_dir()

        self.apertura = pd.read_csv(datos_dir / "tablalpf.csv")
        self.apertura["equipo"] = self.apertura["equipo"].apply(normalizar)

        self.fixture = pd.read_csv(datos_dir / "fixture_lpf.csv")
        self.resultados = pd.read_csv(datos_dir / "resultados_lpf.csv")

        # Tabla de promedios (Art. 26 / Estatuto AFA art. 93): puntos y
        # partidos jugados ACUMULADOS ANTES del Apertura 2026 (últimas ~3
        # temporadas). Los recién ascendidos arrancan en 0/0 porque solo
        # computan desde su ascenso. Se les suma la 2026 en
        # calcular_tabla_promedios().
        self.promedios_historicos = pd.read_csv(datos_dir / "promedios_lpf.csv")
        self.promedios_historicos["equipo"] = self.promedios_historicos["equipo"].apply(normalizar)

        # self.tabla es lo que usa crear_equipos() (heredado de Estadisticas)
        # para inicializar cada Equipo. Para el Clausura arranca todo en
        # cero: los puntos/gf/gc de ZONA son solo del Clausura. El Apertura
        # se combina aparte, en calcular_tabla_anual().
        self.tabla = self.apertura.copy()
        for col in ["partidos_jugados", "ganados", "empatados", "perdidos", "gf", "gc", "dg", "puntos"]:
            self.tabla[col] = 0

        self._validar_datos_lpf()

        print(f"Apertura (base histórica): {len(self.apertura)} equipos")
        print(f"Fixture Clausura: {len(self.fixture)} partidos pendientes")
        print(f"Resultados Clausura ya jugados: {len(self.resultados)}")

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
        mal_contados = conteo_fixture[conteo_fixture != 16]
        if not mal_contados.empty:
            raise ValueError(f"Estos equipos no tienen exactamente 16 partidos en fixture_lpf.csv:\n{mal_contados}")

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

    # ------------------------------------------------------------------
    # Playoffs del Clausura: cruzados entre zonas desde Octavos
    # (Reglamento Art. 14.2 a 14.5)
    # ------------------------------------------------------------------
    def jugar_playoffs(self, tablas_clausura):
        tabla_a, tabla_b = tablas_clausura["A"], tablas_clausura["B"]

        def equipo(tabla, posicion):
            return tabla.iloc[posicion - 1]["equipo"]

        cruces_octavos = [
            (equipo(tabla_a, 1), equipo(tabla_b, 8)),
            (equipo(tabla_b, 1), equipo(tabla_a, 8)),
            (equipo(tabla_a, 2), equipo(tabla_b, 7)),
            (equipo(tabla_b, 2), equipo(tabla_a, 7)),
            (equipo(tabla_a, 3), equipo(tabla_b, 6)),
            (equipo(tabla_b, 3), equipo(tabla_a, 6)),
            (equipo(tabla_a, 4), equipo(tabla_b, 5)),
            (equipo(tabla_b, 4), equipo(tabla_a, 5)),
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

        seeds_cuartos = tabla_general[tabla_general["equipo"].isin(ganadores_octavos)].reset_index(drop=True)
        cruces_cuartos = [(0, 7), (1, 6), (2, 5), (3, 4)]
        ganadores_cuartos = []
        for i, j in cruces_cuartos:
            mejor, peor = seeds_cuartos.iloc[i]["equipo"], seeds_cuartos.iloc[j]["equipo"]
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

        # Final a partido único (no ida y vuelta como el Reducido de
        # Nacional): reusamos jugar_final_ascenso(), que ya tiene cancha
        # neutral + alargue + penales, solo reetiquetando el resultado.
        campeon, subcampeon, detalle_final = self.jugar_final_ascenso(finalistas[0], finalistas[1])
        diccionario["final"] = detalle_final
        diccionario["campeon_clausura"] = campeon
        diccionario["subcampeon_clausura"] = subcampeon

        return campeon, diccionario

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

        for i in range(n_simulaciones):
            tablas_clausura = self.simular_clausura()

            for zona, tabla_zona in tablas_clausura.items():
                for posicion, fila in tabla_zona.iterrows():
                    contador[fila["equipo"]]["puntos_total"] += fila["puntos"]
                    contador[fila["equipo"]]["posicion_total"] += posicion
                    if posicion <= 8:
                        contador[fila["equipo"]]["playoffs"] += 1

            campeon_clausura, _ = self.jugar_playoffs(tablas_clausura)
            contador[campeon_clausura]["campeon_clausura"] += 1

            tabla_anual = self.calcular_tabla_anual(tablas_clausura)
            tabla_promedios = self.calcular_tabla_promedios(tabla_anual)
            for descendido in self.calcular_descensos(tabla_anual, tabla_promedios):
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

        ganador, perdedor, detalle = self.jugar_final_ascenso(self.CAMPEON_APERTURA, campeon_clausura)
        detalle["campeon_apertura"] = self.CAMPEON_APERTURA
        detalle["campeon_clausura"] = campeon_clausura
        detalle["campeon_trofeo"] = ganador
        return detalle
