# -*- coding: utf-8 -*-
"""
season/validar_sudamericana.py

Validación end-to-end de EstadisticasSudamericana (ver
modelos/estadisticas_sudamericana.py) contra el cuadro real de
Playoffs + Octavos de la Copa Sudamericana 2026 (datos/
sudamericana_cuadro.csv).

Correrlo desde la raíz del proyecto:

    python -m season.validar_sudamericana
"""
from __future__ import annotations

from modelos.estadisticas_sudamericana import EstadisticasSudamericana

RONDAS_ESPERADAS = {"playoffs": 8, "octavos": 8, "cuartos": 4, "semis": 2, "final": 1}


def validar_cuadro_real() -> list:
    print("\n[Parte A] Cuadro real de Playoffs + Octavos -- cantidad de llaves por ronda")
    fallas = []
    m = EstadisticasSudamericana()
    m.cargar_datos_sudamericana()

    if len(m.cuadro_playoffs) != 8:
        fallas.append(f"cuadro_playoffs tiene {len(m.cuadro_playoffs)} llaves, se esperaban 8")
    cuadro_por_ronda = {}
    for fila in m.cuadro:
        cuadro_por_ronda.setdefault(fila["ronda"], []).append(fila)
    for ronda, cantidad in RONDAS_ESPERADAS.items():
        if ronda == "playoffs":
            continue
        n = len(cuadro_por_ronda.get(ronda, []))
        if n != cantidad:
            fallas.append(f"ronda {ronda}: {n} llaves, se esperaban {cantidad}")

    octavos = cuadro_por_ronda.get("octavos", [])
    sin_directo = [f for f in octavos if not f["equipo_ida_local"]]
    if sin_directo:
        fallas.append(f"Hay llaves de octavos sin el lado directo cargado: {sin_directo}")

    print(f"  {'OK' if not fallas else 'FALLÓ'}")
    return fallas


def validar_simulacion_completa() -> list:
    print("\n[Parte B] simular_sudamericana() -- pipeline completo con el cuadro real")
    fallas = []
    m = EstadisticasSudamericana()
    m.cargar_datos_sudamericana()
    m.crear_equipos_sudamericana()
    rondas, campeon = m.simular_sudamericana()

    for ronda, cantidad in RONDAS_ESPERADAS.items():
        n = len(rondas.get(ronda, []))
        if n != cantidad:
            fallas.append(f"ronda {ronda}: {n} llaves simuladas, se esperaban {cantidad}")

    if not campeon:
        fallas.append("No se determinó campeón")

    # Ningún ganador de playoffs debería faltar como "equipo_vuelta_local"
    # de su llave de octavos correspondiente (bug real posible: mapeo
    # 1:1 playoffs->octavos mal indexado).
    ganadores_playoffs = {i + 1: d["avanza"] for i, d in enumerate(rondas["playoffs"])}
    for i, detalle in enumerate(rondas["octavos"], start=1):
        equipos_llave = set(detalle["agregado"].keys())
        if ganadores_playoffs[i] not in equipos_llave:
            fallas.append(
                f"Octavos llave {i}: el ganador de playoffs llave {i} ({ganadores_playoffs[i]}) "
                f"no aparece en la llave, hay un desfasaje de índices."
            )

    print(f"  Campeón: {campeon}")
    print(f"  {'OK' if not fallas else 'FALLÓ'}")
    return fallas


def main():
    fallas = []
    fallas += validar_cuadro_real()
    fallas += validar_simulacion_completa()

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
