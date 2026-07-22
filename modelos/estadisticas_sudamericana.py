# -*- coding: utf-8 -*-
"""
modelos/estadisticas_sudamericana.py

Motor de la Copa Sudamericana desde los Playoffs de Octavos: a
diferencia de la Libertadores (donde cada ronda sale 100% de la
anterior, ganador de llave 2k-1 contra ganador de 2k), acá los octavos
mezclan dos orígenes distintos:

    - 8 equipos ya clasificados directo (1° de cada zona de la fase de
      grupos de Sudamericana).
    - 8 ganadores de los Playoffs de Octavos (cruces entre los 2° de
      zona de Sudamericana y los 3° de zona de Libertadores -- ver
      season/libertadores_grupos.py para de dónde salen esos terceros).

Reglamento real 2026 (CONMEBOL, confirmado contra el instructivo
oficial conmebol.com): Playoffs a ida y vuelta, igual que Octavos/
Cuartos/Semis; Final a partido único en sede neutral -- mismo formato
que ya tiene Libertadores, así que se hereda EstadisticasLibertadores
en vez de reescribir jugar_llave_ida_vuelta()/simular_libertadores()
desde cero. Lo único propio de acá es resolver los Playoffs primero y
usar sus 8 ganadores para completar el lado "equipo_ida_local" que
datos/sudamericana_cuadro.csv deja en blanco en cada llave de Octavos
(ver cargar_datos_sudamericana()) -- el 1° de zona de Sudamericana
(ya conocido, va en equipo_vuelta_local) define la vuelta como local,
mejor ranking que un ganador de Playoffs (instructivo oficial: "los
equipos con mejor performance... definirán sus partidos de local").

Sin restricción de país en Playoffs/Octavos (a diferencia de la fase
de grupos): pueden cruzarse dos equipos del mismo país acá, confirmado
por el instructivo oficial y varias coberturas de mayo 2026.

Ronda 1:1, no 2:1: la llave `i` de Playoffs alimenta la llave `i` de
Octavos (mismo cruce que ya sorteó CONMEBOL), NO el esquema 2k-1/2k que
usa el resto del cuadro entre rondas consecutivas -- por eso hace falta
este paso intermedio antes de poder reusar simular_libertadores() tal
cual para Octavos/Cuartos/Semis/Final.
"""
from __future__ import annotations

import csv

import rutas
from modelos.estadisticas_libertadores import EstadisticasLibertadores

RONDA_PLAYOFFS = "playoffs"
LLAVES_PLAYOFFS = 8


class EstadisticasSudamericana(EstadisticasLibertadores):

    def __init__(self):
        super().__init__()
        self.cuadro_playoffs: list[dict] = []
        # Valor ORIGINAL (del CSV) de equipo_ida_local por llave de
        # octavos -- vacío hoy (nadie jugó los Playoffs todavía), pero
        # el día que el CSV se actualice con resultados reales de
        # Playoffs, ese valor real tiene que ganarle siempre al
        # ganador simulado. Sin este snapshot, simular_sudamericana()
        # mutaba self.cuadro la primera vez que corría y las
        # simulaciones siguientes (Monte Carlo) dejaban de jugar los
        # Playoffs de verdad -- quedaban pegadas al resultado de la
        # primera corrida.
        self._octavos_ida_original: dict[int, str] = {}

    # ------------------------------------------------------------------
    # Carga
    # ------------------------------------------------------------------
    def cargar_datos_sudamericana(self):
        """Lee datos/sudamericana_cuadro.csv (playoffs + octavos con el
        lado directo ya conocido + cuartos/semis/final en blanco) y
        datos/sudamericana_elo.csv. Separa las filas de "playoffs" del
        resto (self.cuadro), porque simular_libertadores() heredado
        solo sabe iterar RONDAS = ["octavos", "cuartos", "semis",
        "final"] -- ver docstring del módulo."""
        ruta_cuadro = rutas.datos_dir() / "sudamericana_cuadro.csv"
        with open(ruta_cuadro, encoding="utf-8") as f:
            filas = list(csv.DictReader(f))

        self.cuadro_playoffs = [f for f in filas if f["ronda"] == RONDA_PLAYOFFS]
        self.cuadro = [f for f in filas if f["ronda"] != RONDA_PLAYOFFS]
        self._octavos_ida_original = {
            int(f["llave"]): f["equipo_ida_local"] for f in self.cuadro if f["ronda"] == "octavos"
        }

        ruta_elo = rutas.datos_dir() / "sudamericana_elo.csv"
        with open(ruta_elo, encoding="utf-8") as f:
            self.elo = {fila["equipo"]: float(fila["elo"]) for fila in csv.DictReader(f)}

        print(f"Copa Sudamericana: {len(self.cuadro_playoffs)} llaves de playoffs, "
              f"{len(self.cuadro)} cruces de octavos en adelante, {len(self.elo)} equipos con Elo.")

    def crear_equipos_sudamericana(self):
        """Todos los equipos que pueden llegar a pisar la cancha: los
        16 de playoffs + los 8 directos a octavos (24 en total, aunque
        solo 16 sigan vivos después de playoffs)."""
        nombres = set()
        for cruce in self.cuadro_playoffs:
            nombres.add(cruce["equipo_ida_local"])
            nombres.add(cruce["equipo_vuelta_local"])
        for cruce in self.cuadro:
            if cruce["ronda"] == "octavos":
                nombres.add(cruce["equipo_vuelta_local"])
        self.crear_equipos_desde_elo(nombres, self.elo)

    # ------------------------------------------------------------------
    # Simulación
    # ------------------------------------------------------------------
    def simular_sudamericana(self):
        """Resuelve primero los Playoffs (8 llaves independientes, ida
        y vuelta) y con sus ganadores completa el cuadro de Octavos
        (llave i de Playoffs -> lado "equipo_ida_local" de la llave i
        de Octavos: el ganador de Playoffs abre la serie de visitante,
        el 1° de zona de Sudamericana -- mejor ranking -- define la
        vuelta como local, ver docstring del módulo). De ahí en más
        delega en simular_libertadores() heredado, que ya sabe cablear
        Octavos -> Cuartos -> Semis -> Final solo.

        Devuelve ({"playoffs": [...], "octavos": [...], "cuartos": [...],
        "semis": [...], "final": [...]}, campeón)."""
        detalle_playoffs = []
        ganadores_playoffs: dict[int, str] = {}
        for cruce in self.cuadro_playoffs:
            llave = int(cruce["llave"])
            gl_ida_real = cruce.get("goles_ida_local") or None
            gv_ida_real = cruce.get("goles_ida_visitante") or None
            detalle = self.jugar_llave_ida_vuelta(
                cruce["equipo_ida_local"], cruce["equipo_vuelta_local"],
                gl_ida_real=int(gl_ida_real) if gl_ida_real is not None else None,
                gv_ida_real=int(gv_ida_real) if gv_ida_real is not None else None,
            )
            detalle["jugado"] = False
            detalle_playoffs.append(detalle)
            ganadores_playoffs[llave] = detalle["avanza"]

        for cruce in self.cuadro:
            if cruce["ronda"] == "octavos":
                llave = int(cruce["llave"])
                original = self._octavos_ida_original.get(llave, "")
                # El dato real (si algún día el CSV ya trae el Playoff
                # jugado de verdad) siempre gana; si no, el ganador
                # simulado de ESTA corrida -- nunca el de una corrida
                # anterior (ver comentario en __init__).
                cruce["equipo_ida_local"] = original or ganadores_playoffs[llave]

        rondas_detalle, campeon = self.simular_libertadores()
        return {RONDA_PLAYOFFS: detalle_playoffs, **rondas_detalle}, campeon

    # ------------------------------------------------------------------
    # Monte Carlo
    # ------------------------------------------------------------------
    def monte_carlo_sudamericana(self, n_simulaciones=1000):
        """Corre simular_sudamericana() n veces y cuenta, para cada uno
        de los 24 equipos (16 de Playoffs + 8 directos a Octavos), en
        qué % de las corridas llega a cada instancia y sale campeón.

        A diferencia de monte_carlo_libertadores() (heredado, que NO
        sirve acá -- ver su docstring), esto vuelve a jugar los
        Playoffs en CADA corrida en vez de reusar el resultado de la
        primera: %octavos es la métrica que de verdad aporta acá,
        porque para los 16 equipos de Playoffs "llegar a octavos" NO
        está garantizado (a diferencia de los 8 directos, que van a
        dar 100% ahí -- eso también es información real, no un bug)."""
        print(f"\nCorriendo Monte Carlo Copa Sudamericana ({n_simulaciones} simulaciones)...")

        participantes = {c["equipo_ida_local"] for c in self.cuadro_playoffs} | \
            {c["equipo_vuelta_local"] for c in self.cuadro_playoffs} | \
            {c["equipo_vuelta_local"] for c in self.cuadro if c["ronda"] == "octavos"}
        rondas_contadas = ["octavos", "cuartos", "semis", "final"]
        contador = {nombre: {r: 0 for r in rondas_contadas} | {"campeon": 0} for nombre in participantes}

        paso = max(1, n_simulaciones // 10)
        for i in range(n_simulaciones):
            rondas_detalle, campeon = self.simular_sudamericana()
            for ronda in rondas_contadas:
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
                "%octavos": round(100 * datos["octavos"] / n_simulaciones, 1),
                "%cuartos": round(100 * datos["cuartos"] / n_simulaciones, 1),
                "%semis": round(100 * datos["semis"] / n_simulaciones, 1),
                "%final": round(100 * datos["final"] / n_simulaciones, 1),
                "%campeon": round(100 * datos["campeon"] / n_simulaciones, 1),
            })
        filas.sort(key=lambda f: (-f["%campeon"], -f["%final"], f["equipo"]))
        print("Monte Carlo Sudamericana terminado.")
        return filas
