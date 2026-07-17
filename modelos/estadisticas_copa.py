# -*- coding: utf-8 -*-
"""
estadisticas_copa.py

Motor de simulación de la Copa Argentina: eliminación directa a partido
único en cancha neutral (con alargue y penales), 64 equipos -> 6 rondas.

A diferencia de las ligas acá no hay fixture ni tablas: el estado es un
cuadro (datos/copa_argentina.csv) con los cruces reales ya jugados y los
pendientes. El armado del árbol es implícito: el ganador de la llave
2k-1 y el de la llave 2k de una ronda se cruzan en la llave k de la
siguiente.

Los ratings no se calculan acá: se COSECHAN de los motores que ya los
tienen (EstadisticasLPF para Primera y Estadisticas para la Nacional).
Los equipos de categorías menores (B Metro, Federal A, etc.) reciben un
rating genérico de equipo débil — a esta altura del cuadro ya están casi
todos eliminados, así que solo pesa como respaldo.
"""
import csv

import data_access
import rutas
from modelos.estadisticas import Estadisticas
from modelos.equipo import Equipo

RONDAS = ["32avos", "16avos", "octavos", "cuartos", "semis", "final"]
LLAVES_POR_RONDA = {"32avos": 32, "16avos": 16, "octavos": 8,
                    "cuartos": 4, "semis": 2, "final": 1}

# ---------------------------------------------------------------------
# Calibración entre divisiones
# ---------------------------------------------------------------------
# calcular_ratings() (en estadisticas.py) normaliza el ataque/defensa de
# cada equipo CONTRA EL PROMEDIO DE SU PROPIA LIGA: un equipo con
# ataque=1.0 en LPF es "el promedio de la LPF", y un equipo con
# ataque=1.0 en Nacional es "el promedio de Nacional" -- dos escalas
# distintas que antes se enfrentaban tal cual en la Copa, como si un
# equipo del medio de la tabla de Nacional fuera tan fuerte como uno del
# medio de tabla de Primera. Estos factores devuelven los ratings de
# Nacional a la escala de Primera (que queda como referencia, factor
# 1.0, por ser la liga con más partidos y datos más confiables) antes de
# que entren al motor de la Copa. Los números son una estimación de la
# brecha real de nivel entre ambas divisiones; se pueden recalibrar con
# datos de cruces históricos Primera-vs-Nacional (Copa Argentina, extinta
# Copa de la Superliga, etc.) si se quiere mayor precisión.
FACTOR_ATAQUE_NACIONAL = 0.78    # ~22% menos gol a favor que un equipo equivalente de Primera
FACTOR_DEFENSA_NACIONAL = 1.25   # ~25% más gol en contra que un equipo equivalente de Primera

# Rating genérico para equipos sin datos (categorías menores a Nacional:
# Federal A, Primera C, etc.): deliberadamente por debajo del piso de
# Nacional ya calibrado arriba (0.78/1.25), para conservar el orden
# Primera > Nacional > ascenso. No regalados, pero claramente más
# débiles que el promedio de Primera.
ATAQUE_ASCENSO = 0.70
DEFENSA_ASCENSO = 1.35

# Cómo se llama cada equipo de la Copa en los datasets de liga, cuando el
# nombre de Promiedos difiere.
ALIAS_NACIONAL = {
    "San Martín Tucumán": "San Martín (T)",
    "San Martín San Juan": "San Martín",
    "Gimnasia de Jujuy": "Gimnasia (J)",
    "Deportivo Maipú": "Maipú",
    "Deportivo Madryn": "Dep. Madryn",
    "Ciudad De Bolivar": "Bolivar",
    "Deportivo Morón": "Morón",
    "Atlético Rafaela": "Atlético Rafaela",
}


class EstadisticasCopa(Estadisticas):

    def __init__(self):
        super().__init__()
        self.cuadro = []  # filas del CSV como dicts

    # ------------------------------------------------------------------
    # Carga
    # ------------------------------------------------------------------
    def cargar_datos_copa(self):
        """Lee los cruces reales, jugados y pendientes de Copa Argentina."""
        self.cuadro = data_access.cup_records()
        print(f"Copa Argentina: {len(self.cuadro)} cruces cargados "
              f"({sum(1 for c in self.cuadro if c['ganador'])} resueltos)")

    def crear_equipos_copa(self):
        """Crea un Equipo por participante y le asigna ratings: reales si
        juega en LPF o Nacional, genéricos de ascenso si no."""
        ratings_liga = self._cosechar_ratings_ligas()

        nombres = set()
        for cruce in self.cuadro:
            nombres.add(cruce["equipo_local"])
            nombres.add(cruce["equipo_visitante"])

        self.equipos = {}
        con_datos = 0
        for nombre in sorted(nombres):
            equipo = Equipo(nombre)
            origen = ratings_liga.get(nombre) or ratings_liga.get(ALIAS_NACIONAL.get(nombre, ""))
            if origen is not None:
                equipo.ataque_local = origen.ataque_local
                equipo.ataque_visitante = origen.ataque_visitante
                equipo.defensa_local = origen.defensa_local
                equipo.defensa_visitante = origen.defensa_visitante
                con_datos += 1
            else:
                equipo.ataque_local = equipo.ataque_visitante = ATAQUE_ASCENSO
                equipo.defensa_local = equipo.defensa_visitante = DEFENSA_ASCENSO
            self.equipos[nombre] = equipo

        print(f"Equipos de Copa: {len(self.equipos)} "
              f"({con_datos} con ratings reales de liga, resto genérico)")

    def _cosechar_ratings_ligas(self):
        """Devuelve {nombre: Equipo} con los ratings ya calculados por los
        motores de LPF y Nacional. Si alguna liga falla al cargar, se
        sigue con la otra (la Copa no debe caerse por eso)."""
        ratings = {}

        try:
            from modelos.estadisticas_lpf import EstadisticasLPF
            lpf = EstadisticasLPF()
            lpf.cargar_datos_lpf()
            lpf.crear_equipos_lpf()
            lpf.calcular_ratings_lpf()
            ratings.update(lpf.equipos)
        except Exception as e:
            print(f"  (aviso: no se pudieron cargar ratings de LPF: {e})")

        try:
            nacional = Estadisticas()
            nacional.cargar_datos()
            nacional.crear_equipos()
            nacional.calcular_estadisticas()
            nacional.calcular_ratings()

            # Recalibrar de la escala de Nacional a la escala de Primera
            # (ver comentario de FACTOR_ATAQUE_NACIONAL/FACTOR_DEFENSA_NACIONAL
            # más arriba) antes de que estos ratings se mezclen con los de
            # LPF en el motor de la Copa.
            for equipo in nacional.equipos.values():
                equipo.ataque_local = round(equipo.ataque_local * FACTOR_ATAQUE_NACIONAL, 3)
                equipo.ataque_visitante = round(equipo.ataque_visitante * FACTOR_ATAQUE_NACIONAL, 3)
                equipo.defensa_local = round(equipo.defensa_local * FACTOR_DEFENSA_NACIONAL, 3)
                equipo.defensa_visitante = round(equipo.defensa_visitante * FACTOR_DEFENSA_NACIONAL, 3)

            # No pisamos LPF: si un nombre está en ambas, gana Primera.
            for nombre, equipo in nacional.equipos.items():
                ratings.setdefault(nombre, equipo)
            print(f"  Ratings de Nacional recalibrados a escala de Primera "
                  f"(x{FACTOR_ATAQUE_NACIONAL} ataque, x{FACTOR_DEFENSA_NACIONAL} defensa).")
        except Exception as e:
            print(f"  (aviso: no se pudieron cargar ratings de Nacional: {e})")

        return ratings

    # ------------------------------------------------------------------
    # Simulación del cuadro
    # ------------------------------------------------------------------
    def simular_copa(self):
        """Completa el cuadro: respeta los resultados reales y simula los
        cruces pendientes ronda por ronda (partido único, cancha neutral,
        alargue y penales). Devuelve {ronda: [detalle_cruce, ...]} más el
        campeón."""
        reales = {}
        for cruce in self.cuadro:
            reales[(cruce["ronda"], int(cruce["llave"]))] = cruce

        rondas_detalle = {}
        ganadores_previos = {}  # llave -> ganador de la ronda anterior

        for ronda in RONDAS:
            detalles = []
            ganadores = {}
            for llave in range(1, LLAVES_POR_RONDA[ronda] + 1):
                real = reales.get((ronda, llave))

                if real and real["equipo_local"] and real["equipo_visitante"]:
                    local, visitante = real["equipo_local"], real["equipo_visitante"]
                else:
                    # Cableado del árbol: ganadores de las llaves 2k-1 y 2k.
                    local = ganadores_previos.get(2 * llave - 1)
                    visitante = ganadores_previos.get(2 * llave)

                if not local or not visitante:
                    raise ValueError(f"No se pudo armar {ronda} llave {llave}: falta un clasificado")

                if real and real["ganador"]:
                    detalle = self._detalle_real(real)
                elif real and real["goles_local"] != "" and real["goles_local"] is not None and real["goles_local"] != real["goles_visitante"]:
                    detalle = self._detalle_real(real)
                else:
                    ganador, _, d = self.jugar_final_ascenso(local, visitante)
                    detalle = {
                        "local": local, "visitante": visitante,
                        "golesLocal": d["marcador"][0], "golesVisitante": d["marcador"][1],
                        "avanza": ganador, "jugado": False,
                        "penales": (d["marcador"][0] == d["marcador"][1]) or None,
                    }

                ganadores[llave] = detalle["avanza"]
                detalles.append(detalle)

            rondas_detalle[ronda] = detalles
            ganadores_previos = ganadores

        campeon = rondas_detalle["final"][0]["avanza"]
        return rondas_detalle, campeon

    @staticmethod
    def _detalle_real(cruce):
        goles_local = int(cruce["goles_local"]) if cruce["goles_local"] != "" else None
        goles_visitante = int(cruce["goles_visitante"]) if cruce["goles_visitante"] != "" else None
        ganador = cruce["ganador"]
        if not ganador and goles_local is not None:
            ganador = cruce["equipo_local"] if goles_local > goles_visitante else cruce["equipo_visitante"]
        penales = (goles_local is not None and goles_local == goles_visitante) or None
        return {
            "local": cruce["equipo_local"], "visitante": cruce["equipo_visitante"],
            "golesLocal": goles_local, "golesVisitante": goles_visitante,
            "avanza": ganador, "jugado": True, "penales": penales,
        }

    # ------------------------------------------------------------------
    # Monte Carlo
    # ------------------------------------------------------------------
    def monte_carlo_copa(self, n_simulaciones=1000):
        """Corre el cuadro n veces y cuenta, por equipo todavía vivo, en qué
        porcentaje de corridas alcanza cada ronda y sale campeón."""
        print(f"\nCorriendo Monte Carlo Copa Argentina ({n_simulaciones} simulaciones)...")

        vivos = self._equipos_vivos()
        contador = {nombre: {r: 0 for r in RONDAS[1:]} | {"campeon": 0} for nombre in vivos}

        paso = max(1, n_simulaciones // 10)
        for i in range(n_simulaciones):
            rondas_detalle, campeon = self.simular_copa()
            for ronda in RONDAS[1:]:
                for cruce in rondas_detalle[ronda]:
                    for nombre in (cruce["local"], cruce["visitante"]):
                        if nombre in contador:
                            contador[nombre][ronda] += 1
            if campeon in contador:
                contador[campeon]["campeon"] += 1
            if (i + 1) % paso == 0:
                print(f"  {i + 1}/{n_simulaciones} simulaciones...")

        filas = []
        for nombre, datos in contador.items():
            filas.append({
                "equipo": nombre,
                "%16avos": round(100 * datos["16avos"] / n_simulaciones, 1),
                "%octavos": round(100 * datos["octavos"] / n_simulaciones, 1),
                "%cuartos": round(100 * datos["cuartos"] / n_simulaciones, 1),
                "%semis": round(100 * datos["semis"] / n_simulaciones, 1),
                "%final": round(100 * datos["final"] / n_simulaciones, 1),
                "%campeon": round(100 * datos["campeon"] / n_simulaciones, 1),
            })
        filas.sort(key=lambda f: (-f["%campeon"], -f["%final"], f["equipo"]))
        print("Monte Carlo Copa terminado.")
        return filas

    def _equipos_vivos(self):
        """Equipos que todavía no fueron eliminados en ningún cruce resuelto."""
        eliminados = set()
        for cruce in self.cuadro:
            if cruce["ganador"]:
                perdedor = (cruce["equipo_visitante"] if cruce["ganador"] == cruce["equipo_local"]
                            else cruce["equipo_local"])
                eliminados.add(perdedor)
        participantes = {c["equipo_local"] for c in self.cuadro} | {c["equipo_visitante"] for c in self.cuadro}
        return sorted(participantes - eliminados)
