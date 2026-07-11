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

Reglamento real 2026 (CONMEBOL, confirmado): Playoffs a ida y vuelta,
igual que Octavos/Cuartos/Semis; Final a partido único en sede neutral
-- mismo formato que ya tiene Libertadores, así que se hereda
EstadisticasLibertadores en vez de reescribir jugar_llave_ida_vuelta()/
simular_libertadores() desde cero. Lo único propio de acá es resolver
los Playoffs primero y usar sus 8 ganadores para completar el lado
"equipo_vuelta_local" que datos/sudamericana_cuadro.csv deja en blanco
en cada llave de Octavos (ver cargar_datos_sudamericana()).

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
                nombres.add(cruce["equipo_ida_local"])
        self.crear_equipos_desde_elo(nombres, self.elo)

    # ------------------------------------------------------------------
    # Simulación
    # ------------------------------------------------------------------
    def simular_sudamericana(self):
        """Resuelve primero los Playoffs (8 llaves independientes, ida
        y vuelta) y con sus ganadores completa el cuadro de Octavos
        (llave i de Playoffs -> lado "equipo_vuelta_local" de la llave
        i de Octavos, ver docstring del módulo). De ahí en más delega
        en simular_libertadores() heredado, que ya sabe cablear
        Octavos -> Cuartos -> Semis -> Final solo.

        Devuelve ({"playoffs": [...], "octavos": [...], "cuartos": [...],
        "semis": [...], "final": [...]}, campeón)."""
        detalle_playoffs = []
        ganadores_playoffs: dict[int, str] = {}
        for cruce in self.cuadro_playoffs:
            llave = int(cruce["llave"])
            detalle = self.jugar_llave_ida_vuelta(cruce["equipo_ida_local"], cruce["equipo_vuelta_local"])
            detalle["jugado"] = False
            detalle_playoffs.append(detalle)
            ganadores_playoffs[llave] = detalle["avanza"]

        for cruce in self.cuadro:
            if cruce["ronda"] == "octavos" and not cruce["equipo_vuelta_local"]:
                cruce["equipo_vuelta_local"] = ganadores_playoffs[int(cruce["llave"])]

        rondas_detalle, campeon = self.simular_libertadores()
        return {RONDA_PLAYOFFS: detalle_playoffs, **rondas_detalle}, campeon
