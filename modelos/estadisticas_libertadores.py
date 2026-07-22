# -*- coding: utf-8 -*-
"""
estadisticas_libertadores.py

Motor de simulación de la Copa Libertadores desde Octavos de Final:
llaves a ida y vuelta (octavos, cuartos, semis) + final a partido único
en cancha neutral. Mismo patrón que estadisticas_copa.py (el cuadro es
un CSV con los cruces reales/pendientes, y las rondas siguientes se
arman solas cableando ganador de la llave 2k-1 contra ganador de la
llave 2k), pero acá el estado es a DOS partidos por llave en vez de
uno, y los ratings de cada equipo no salen de un historial de goles de
una liga (los 16 equipos vienen de 6 países distintos, no hay una
"liga" en común) sino del ranking Elo de clubes de CONMEBOL.

Conversión Elo -> ataque/defensa
--------------------------------
No hay forma honesta de derivar fuerza ofensiva y defensiva por
separado solo del Elo (es un rating de resultado, no de goles), así
que se usa una aproximación simple y explícita: la fuerza relativa de
cada equipo (su Elo dividido por el Elo promedio de los 16 clasificados)
se aplica por igual como multiplicador de ataque y como divisor de
defensa. Esto reproduce la idea de que un equipo mejor rankeado tiende
a convertir más Y a recibir menos, sin inventarle una separación entre
ambas facetas que el dato no puede respaldar.

    fuerza = (elo_equipo / elo_promedio_16) ** ELO_ALPHA
    ataque = fuerza
    defensa = 1 / fuerza

ELO_ALPHA=0.6 quedó calibrado a ojo para que una diferencia de Elo
grande dentro de este cuadro (ej. Flamengo 2018 vs Deportes Tolima
1405) dé una ventaja clara pero no un resultado abultado poco realista
(~1.6 vs ~0.85 goles esperados en condición neutral de local/visitante
promedio de la propia liga argentina que ya usa el resto del proyecto
-- ver PROMEDIO_GF_LOCAL_LIGA/PROMEDIO_GF_VISITANTE_LIGA en
Estadisticas). Es un ajuste grosero a propósito: el pedido fue "de
manera simple".

Con esos ataque/defensa ya cargados en el objeto Equipo, el partido en
sí se resuelve con el MISMO simular_partido() de la clase base
(Poisson con corrección Dixon-Coles + shock Gamma) que usan LPF,
Nacional, B Metro, etc. -- ver Estadisticas.simular_partido().
"""
import csv

import numpy as np

import data_access
import rutas
from modelos.estadisticas import Estadisticas
from modelos.equipo import Equipo

RONDAS = ["octavos", "cuartos", "semis", "final"]
LLAVES_POR_RONDA = {"octavos": 8, "cuartos": 4, "semis": 2, "final": 1}

# Sensibilidad de la conversión Elo -> ataque/defensa (ver docstring).
ELO_ALPHA = 0.6


class EstadisticasLibertadores(Estadisticas):

    def __init__(self):
        super().__init__()
        self.cuadro = []       # filas de datos/libertadores_cuadro.csv
        self.elo = {}          # {nombre: elo}

    # ------------------------------------------------------------------
    # Carga
    # ------------------------------------------------------------------
    def cargar_datos_libertadores(self):
        """Lee el cuadro de octavos (cruces reales/pendientes a ida y
        vuelta) y el ranking Elo de los equipos que participan."""
        ruta_cuadro = rutas.datos_dir() / "libertadores_cuadro.csv"
        with open(ruta_cuadro, encoding="utf-8") as f:
            self.cuadro = list(csv.DictReader(f))

        ruta_elo = rutas.datos_dir() / "libertadores_elo.csv"
        with open(ruta_elo, encoding="utf-8") as f:
            self.elo = {fila["equipo"]: float(fila["elo"]) for fila in csv.DictReader(f)}

        print(f"Copa Libertadores: {len(self.cuadro)} cruces de octavos cargados, "
              f"{len(self.elo)} equipos con Elo.")

    def crear_equipos_libertadores(self):
        """Crea un Equipo por participante del cuadro de octavos y le
        asigna ataque/defensa derivados de su Elo relativo al promedio
        de los clasificados."""
        nombres = set()
        for cruce in self.cuadro:
            nombres.add(cruce["equipo_ida_local"])
            nombres.add(cruce["equipo_vuelta_local"])
        self.crear_equipos_desde_elo(nombres, self.elo)

    def crear_equipos_desde_elo(self, nombres, elo_por_equipo: dict):
        """Helper compartido: crea un Equipo por cada nombre de
        `nombres` con ataque/defensa derivados de su Elo relativo al
        promedio del propio grupo de participantes (ver docstring del
        módulo, sección "Conversión Elo -> ataque/defensa"). Usado
        tanto por crear_equipos_libertadores() (16 del cuadro de
        octavos) como por season/libertadores_grupos.py (32 de la
        fase de grupos, con Elo que rota cada temporada)."""
        nombres = sorted(set(nombres))
        elos_participantes = [elo_por_equipo[n] for n in nombres if n in elo_por_equipo]
        if not elos_participantes:
            raise ValueError("Ninguno de los equipos tiene Elo cargado.")
        elo_promedio = sum(elos_participantes) / len(elos_participantes)

        self.equipos = {}
        sin_elo = []
        for nombre in nombres:
            equipo = Equipo(nombre)
            elo_equipo = elo_por_equipo.get(nombre)
            if elo_equipo is None:
                # Sin dato: se lo trata como equipo de fuerza promedio del
                # cuadro (ni favorito ni underdog) en vez de romper la
                # simulación -- avisamos para que se complete el CSV/pool.
                sin_elo.append(nombre)
                fuerza = 1.0
            else:
                fuerza = (elo_equipo / elo_promedio) ** ELO_ALPHA
            equipo.ataque_local = equipo.ataque_visitante = fuerza
            equipo.defensa_local = equipo.defensa_visitante = 1 / fuerza
            self.equipos[nombre] = equipo

        if sin_elo:
            print(f"  (aviso: sin Elo cargado, se usó fuerza neutra para: {', '.join(sin_elo)})")
        print(f"Equipos: {len(self.equipos)} (Elo promedio: {elo_promedio:.0f})")

    # ------------------------------------------------------------------
    # Un partido de ida/vuelta (una llave completa)
    # ------------------------------------------------------------------
    def jugar_llave_ida_vuelta(self, local_ida, local_vuelta, gl_ida_real=None, gv_ida_real=None):
        """Simula una llave a dos partidos: <local_ida> de local en la
        ida, <local_vuelta> de local en la vuelta. Si la suma queda
        igual, se define en alargue de la vuelta (30') y, si sigue
        empatado, por penales (50/50) -- sin ventaja de gol de
        visitante, como rige la Libertadores desde 2019.

        Si <gl_ida_real>/<gv_ida_real> vienen cargados (la ida ya se
        jugó de verdad pero la vuelta todavía no), se usan esos goles
        en vez de simular la ida -- solo se simula la vuelta. Con
        ambos en None (default) se simula la llave completa, como
        antes."""

        ida_real = gl_ida_real is not None and gv_ida_real is not None
        if ida_real:
            gl_ida, gv_ida = gl_ida_real, gv_ida_real
        else:
            gl_ida, gv_ida = self.simular_partido(local_ida, local_vuelta)
        gl_vta, gv_vta = self.simular_partido(local_vuelta, local_ida)

        agregado_ida = gl_ida + gv_vta       # goles totales de "local_ida" en la llave
        agregado_vuelta = gv_ida + gl_vta     # goles totales de "local_vuelta" en la llave

        detalle = {
            "ida": {"local": local_ida, "visitante": local_vuelta, "golesLocal": gl_ida, "golesVisitante": gv_ida},
            "vuelta": {"local": local_vuelta, "visitante": local_ida, "golesLocal": gl_vta, "golesVisitante": gv_vta},
            "agregado": {local_ida: agregado_ida, local_vuelta: agregado_vuelta},
            "penales": None,
            "ida_jugada": ida_real,
        }

        if agregado_ida != agregado_vuelta:
            detalle["avanza"] = local_ida if agregado_ida > agregado_vuelta else local_vuelta
            return detalle

        # Alargue en la vuelta (usa los mismos ataque/defensa, a un tercio
        # de intensidad -- mismo criterio que jugar_final_ascenso()).
        equipo_local = self.equipos[local_vuelta]
        equipo_visitante = self.equipos[local_ida]
        promedio_neutral = (self.PROMEDIO_GF_LOCAL_LIGA + self.PROMEDIO_GF_VISITANTE_LIGA) / 2
        lambda_local = equipo_local.ataque_local * equipo_visitante.defensa_visitante * promedio_neutral / 3
        lambda_visitante = equipo_visitante.ataque_visitante * equipo_local.defensa_local * promedio_neutral / 3

        gl_et = int(np.random.poisson(lambda_local))
        gv_et = int(np.random.poisson(lambda_visitante))
        agregado_vuelta += gl_et
        agregado_ida += gv_et
        detalle["agregado"] = {local_ida: agregado_ida, local_vuelta: agregado_vuelta}
        detalle["alargue"] = {"local": local_vuelta, "visitante": local_ida, "golesLocal": gl_et, "golesVisitante": gv_et}

        if agregado_ida != agregado_vuelta:
            detalle["avanza"] = local_ida if agregado_ida > agregado_vuelta else local_vuelta
            return detalle

        detalle["penales"] = True
        detalle["avanza"] = local_ida if np.random.random() < 0.5 else local_vuelta
        return detalle

    # ------------------------------------------------------------------
    # Simulación del cuadro completo
    # ------------------------------------------------------------------
    def simular_libertadores(self):
        """Completa el cuadro desde octavos hasta la final. Respeta los
        resultados reales que ya estén cargados en el CSV; simula el
        resto. Devuelve ({ronda: [detalle_llave,...]}, campeon)."""
        reales = {(c["ronda"], int(c["llave"])): c for c in self.cuadro}

        rondas_detalle = {}
        ganadores_previos = {}

        for ronda in RONDAS:
            detalles = []
            ganadores = {}
            for llave in range(1, LLAVES_POR_RONDA[ronda] + 1):
                real = reales.get((ronda, llave))

                if real and real["equipo_ida_local"] and real["equipo_vuelta_local"]:
                    local_ida, local_vuelta = real["equipo_ida_local"], real["equipo_vuelta_local"]
                else:
                    local_ida = ganadores_previos.get(2 * llave - 1)
                    local_vuelta = ganadores_previos.get(2 * llave)

                if not local_ida or not local_vuelta:
                    raise ValueError(f"No se pudo armar {ronda} llave {llave}: falta un clasificado")

                if ronda == "final":
                    # Partido único en cancha neutral (reutiliza el mismo
                    # motor que usan las finales de ascenso de la Nacional).
                    ganador, perdedor, d = self.jugar_final_ascenso(local_ida, local_vuelta)
                    detalle = {
                        "local": local_ida, "visitante": local_vuelta,
                        "golesLocal": d["marcador"][0], "golesVisitante": d["marcador"][1],
                        "avanza": ganador, "jugado": False,
                        "penales": "penales" in d["texto"] or None,
                    }
                elif real and real["ganador"]:
                    detalle = self._detalle_real_llave(real)
                elif real and self._llave_tiene_resultado_real(real):
                    detalle = self._detalle_real_llave(real)
                else:
                    detalle = self.jugar_llave_ida_vuelta(local_ida, local_vuelta)
                    detalle["jugado"] = False

                ganadores[llave] = detalle["avanza"]
                detalles.append(detalle)

            rondas_detalle[ronda] = detalles
            ganadores_previos = ganadores

        campeon = rondas_detalle["final"][0]["avanza"]
        return rondas_detalle, campeon

    @staticmethod
    def _llave_tiene_resultado_real(cruce):
        campos = ["goles_ida_local", "goles_ida_visitante", "goles_vuelta_local", "goles_vuelta_visitante"]
        return all(cruce.get(c) not in (None, "") for c in campos)

    @staticmethod
    def _detalle_real_llave(cruce):
        gil, giv = int(cruce["goles_ida_local"]), int(cruce["goles_ida_visitante"])
        gvl, gvv = int(cruce["goles_vuelta_local"]), int(cruce["goles_vuelta_visitante"])
        local_ida, local_vuelta = cruce["equipo_ida_local"], cruce["equipo_vuelta_local"]
        agregado_ida = gil + gvv
        agregado_vuelta = giv + gvl
        ganador = cruce["ganador"] or (local_ida if agregado_ida > agregado_vuelta else local_vuelta)
        return {
            "ida": {"local": local_ida, "visitante": local_vuelta, "golesLocal": gil, "golesVisitante": giv},
            "vuelta": {"local": local_vuelta, "visitante": local_ida, "golesLocal": gvl, "golesVisitante": gvv},
            "agregado": {local_ida: agregado_ida, local_vuelta: agregado_vuelta},
            "penales": (agregado_ida == agregado_vuelta) or None,
            "avanza": ganador, "jugado": True,
        }

    # ------------------------------------------------------------------
    # Monte Carlo
    # ------------------------------------------------------------------
    def monte_carlo_libertadores(self, n_simulaciones=1000):
        """Corre el cuadro n veces y cuenta, para cada uno de los 16
        equipos, en qué % de las corridas llega a cada ronda y sale
        campeón."""
        print(f"\nCorriendo Monte Carlo Copa Libertadores ({n_simulaciones} simulaciones)...")

        participantes = sorted({c["equipo_ida_local"] for c in self.cuadro} |
                                {c["equipo_vuelta_local"] for c in self.cuadro})
        contador = {nombre: {r: 0 for r in RONDAS[1:]} | {"campeon": 0} for nombre in participantes}

        paso = max(1, n_simulaciones // 10)
        for i in range(n_simulaciones):
            rondas_detalle, campeon = self.simular_libertadores()
            for ronda in RONDAS[1:]:
                for llave in rondas_detalle[ronda]:
                    equipos_llave = [llave["local"], llave["visitante"]] if ronda == "final" else list(llave["agregado"].keys())
                    for nombre in equipos_llave:
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
                "%cuartos": round(100 * datos["cuartos"] / n_simulaciones, 1),
                "%semis": round(100 * datos["semis"] / n_simulaciones, 1),
                "%final": round(100 * datos["final"] / n_simulaciones, 1),
                "%campeon": round(100 * datos["campeon"] / n_simulaciones, 1),
            })
        filas.sort(key=lambda f: (-f["%campeon"], -f["%final"], f["equipo"]))
        print("Monte Carlo Libertadores terminado.")
        return filas

    def equipos_vivos(self):
        """Equipos que todavía no perdieron ninguna llave resuelta (dato
        real). Con el cuadro actual (todo por jugarse) son los 16."""
        eliminados = set()
        for cruce in self.cuadro:
            if cruce.get("ganador"):
                perdedor = (cruce["equipo_vuelta_local"] if cruce["ganador"] == cruce["equipo_ida_local"]
                            else cruce["equipo_ida_local"])
                eliminados.add(perdedor)
        participantes = {c["equipo_ida_local"] for c in self.cuadro} | {c["equipo_vuelta_local"] for c in self.cuadro}
        return sorted(participantes - eliminados)
