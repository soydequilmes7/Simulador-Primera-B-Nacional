# -*- coding: utf-8 -*-
"""
season/validar_libertadores_grupos.py

Validación end-to-end de la fase de grupos de Libertadores en Modo
Temporada: LibertadoresManager (cupos + rotación) -> sortear_grupos()
(8 zonas de 4, sin repetir país) -> jugar_fase_de_grupos() (12 fechas
por zona con desempates reales) -> armar_cuadro_octavos() (16
clasificados listos para el motor de octavos ya existente).

Correrlo desde la raíz del proyecto:

    python -m season.validar_libertadores_grupos
"""
from __future__ import annotations

import random

from season.libertadores_manager import LibertadoresManager, CANTIDAD_TOTAL
from season.libertadores_sorteo import sortear_grupos, CANTIDAD_ZONAS, EQUIPOS_POR_ZONA
from season.libertadores_grupos import jugar_fase_de_grupos, armar_bombos_octavos, armar_cuadro_octavos

CLASIFICADOS_ARGENTINOS_EJEMPLO = [
    "Boca Juniors", "River Plate", "Racing Club", "Talleres", "Vélez Sarsfield", "Estudiantes de la Plata",
]


def validar_armado_clasificacion() -> list:
    print("\n[Parte A] LibertadoresManager -- 32 clasificados con cuotas por país")
    fallas = []
    manager = LibertadoresManager()
    rng = random.Random(42)
    clasificacion = manager.armar_clasificacion(CLASIFICADOS_ARGENTINOS_EJEMPLO, rng=rng)

    if len(clasificacion.equipos) != CANTIDAD_TOTAL:
        fallas.append(f"Se esperaban {CANTIDAD_TOTAL} clasificados, se armaron {len(clasificacion.equipos)}")
    nombres = [c.equipo for c in clasificacion.equipos]
    if len(nombres) != len(set(nombres)):
        fallas.append("Hay nombres de equipo repetidos en la clasificación (colisión no desambiguada)")
    if clasificacion.avisos:
        print(f"  avisos: {clasificacion.avisos}")

    print(f"  {len(clasificacion.equipos)} equipos armados, {len(set(nombres))} nombres únicos. "
          f"{'OK' if not fallas else 'FALLÓ'}")
    return fallas


def validar_sorteo_sin_repetir_pais() -> list:
    print("\n[Parte B] sortear_grupos() -- 8 zonas de 4, sin repetir país por zona")
    fallas = []
    manager = LibertadoresManager()
    rng = random.Random(7)
    clasificacion = manager.armar_clasificacion(CLASIFICADOS_ARGENTINOS_EJEMPLO, rng=rng)
    zonas = sortear_grupos(clasificacion, rng=rng)

    if len(zonas) != CANTIDAD_ZONAS:
        fallas.append(f"Se esperaban {CANTIDAD_ZONAS} zonas, se armaron {len(zonas)}")

    pais_por_equipo = {c.equipo: c.pais for c in clasificacion.equipos}
    todos_los_equipos = []
    for zona in zonas:
        if len(zona.equipos) != EQUIPOS_POR_ZONA:
            fallas.append(f"Zona {zona.letra} tiene {len(zona.equipos)} equipos, se esperaban {EQUIPOS_POR_ZONA}")
        paises_zona = [pais_por_equipo[e] for e in zona.equipos]
        if len(paises_zona) != len(set(paises_zona)):
            fallas.append(f"Zona {zona.letra} tiene dos equipos del mismo país: {paises_zona}")
        todos_los_equipos.extend(zona.equipos)

    if len(todos_los_equipos) != len(set(todos_los_equipos)):
        fallas.append("Un mismo equipo aparece en más de una zona")

    print(f"  Zona A ejemplo: {zonas[0].equipos} ({[pais_por_equipo[e] for e in zonas[0].equipos]})")
    print(f"  {'OK' if not fallas else 'FALLÓ'}")
    return fallas


def validar_fase_de_grupos_y_octavos() -> list:
    print("\n[Parte C] jugar_fase_de_grupos() + armar_cuadro_octavos()")
    fallas = []
    manager = LibertadoresManager()
    rng = random.Random(123)
    clasificacion = manager.armar_clasificacion(CLASIFICADOS_ARGENTINOS_EJEMPLO, rng=rng)
    zonas = sortear_grupos(clasificacion, rng=rng)

    elo_por_equipo = clasificacion.elo_por_equipo()
    pais_por_equipo = {c.equipo: c.pais for c in clasificacion.equipos}
    zonas_jugadas = jugar_fase_de_grupos(zonas, elo_por_equipo, pais_por_equipo, rng=rng)

    for zona in zonas_jugadas:
        if len(zona.partidos) != 12:
            fallas.append(f"Zona {zona.letra} jugó {len(zona.partidos)} partidos, se esperaban 12")
        if len(zona.tabla) != 4:
            fallas.append(f"Zona {zona.letra} tiene {len(zona.tabla)} filas en la tabla, se esperaban 4")
        pj_totales = sum(f.pj for f in zona.tabla)
        if pj_totales != 24:  # 12 partidos * 2 equipos
            fallas.append(f"Zona {zona.letra}: suma de PJ = {pj_totales}, se esperaban 24")

    zona_a = zonas_jugadas[0]
    print(f"  Tabla zona A: {[(f.equipo, f.puntos, f.dg) for f in zona_a.tabla]}")

    primeros, segundos = armar_bombos_octavos(zonas_jugadas)
    if len(primeros) != 8 or len(segundos) != 8:
        fallas.append(f"Bombos de octavos: {len(primeros)} primeros / {len(segundos)} segundos, se esperaban 8/8")

    cuadro = armar_cuadro_octavos(primeros, segundos, pais_por_equipo)
    if len(cuadro) != 8:
        fallas.append(f"Cuadro de octavos armado con {len(cuadro)} llaves, se esperaban 8")
    for fila in cuadro:
        if pais_por_equipo[fila["equipo_ida_local"]] == pais_por_equipo[fila["equipo_vuelta_local"]]:
            fallas.append(f"Llave {fila['llave']} enfrenta a dos equipos del mismo país: {fila}")

    print(f"  Cuadro de octavos: {[(f['equipo_ida_local'], f['equipo_vuelta_local']) for f in cuadro]}")
    print(f"  {'OK' if not fallas else 'FALLÓ'}")
    return fallas


def main():
    fallas = []
    fallas += validar_armado_clasificacion()
    fallas += validar_sorteo_sin_repetir_pais()
    fallas += validar_fase_de_grupos_y_octavos()

    print("\n" + "=" * 60)
    if fallas:
        print(f"FALLÓ ({len(fallas)} problema/s):")
        for f in fallas:
            print(f"  - {f}")
    else:
        print("TODO OK")
    print("=" * 60)


if __name__ == "__main__":
    main()
