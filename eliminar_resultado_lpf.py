# -*- coding: utf-8 -*-
"""
eliminar_resultado_lpf.py

Para corregir un resultado de LPF cargado mal a mano (duplicado, marcador
mal leído de una imagen/fuente, etc.). Elimina de `resultados` la fila
que coincida EXACTO con equipos + marcador (para no arriesgarse a borrar
la fila correcta si hay dos entradas del mismo partido con marcadores
distintos -- ver caso real del 16/08/2026 más abajo).

CASO REAL que motivó esto: Newell's Old Boys vs Deportivo Riestra
(Fecha 5) ya estaba cargado correctamente como 2-0 desde antes -- pero
se cargó una SEGUNDA vez a mano como "2-1" (marcador mal leído de una
captura de pantalla), duplicando el partido con un resultado
incorrecto. cargar_resultado_manual_lpf.py solo evita duplicados
cuando el marcador coincide EXACTO con uno ya cargado -- un marcador
distinto para la misma pareja no se detecta como potencial duplicado
(ver el aviso que se agregó ahí mismo).

Por defecto corre en modo DRY-RUN. Para aplicar de verdad:

    python eliminar_resultado_lpf.py "Newell's Old Boys" "Deportivo Riestra" 2 1 --aplicar

Corre una simulación nueva al final (igual que cargar_resultado_manual_lpf.py)
para que la web refleje la corrección.
"""
from __future__ import annotations

import argparse

from db.repository import transaction
from mapeo_equipos_lpf import resolver_equipo_lpf


def main(equipo_local: str, equipo_visitante: str, goles_local: int, goles_visitante: int,
         aplicar: bool) -> None:
    local = resolver_equipo_lpf(equipo_local) or equipo_local
    visitante = resolver_equipo_lpf(equipo_visitante) or equipo_visitante

    with transaction() as repo:
        pending = repo.match_records("lpf", "pending")
        jugados = repo.match_records("lpf", "played")

    coincidencias = [
        (i, f) for i, f in enumerate(jugados)
        if (resolver_equipo_lpf(f["equipo_local"]) or f["equipo_local"]) == local
        and (resolver_equipo_lpf(f["equipo_visitante"]) or f["equipo_visitante"]) == visitante
        and int(f.get("goles_local", -1)) == goles_local
        and int(f.get("goles_visitante", -1)) == goles_visitante
    ]

    print(f"Buscando: {local} {goles_local}-{goles_visitante} {visitante}")
    print(f"Encontradas {len(coincidencias)} fila(s) EXACTA(S) para borrar.")

    # Mostramos también cualquier OTRO resultado ya cargado para esta
    # pareja (con marcador distinto), para que quede claro cuál se
    # conserva.
    otros = [
        f for f in jugados
        if (resolver_equipo_lpf(f["equipo_local"]) or f["equipo_local"]) == local
        and (resolver_equipo_lpf(f["equipo_visitante"]) or f["equipo_visitante"]) == visitante
        and not (int(f.get("goles_local", -1)) == goles_local and int(f.get("goles_visitante", -1)) == goles_visitante)
    ]
    if otros:
        print(f"\nOtro(s) resultado(s) YA cargado(s) para esta pareja (no se tocan):")
        for f in otros:
            print(f"  jornada {f.get('jornada')}: {f['equipo_local']} {f['goles_local']}-{f['goles_visitante']} {f['equipo_visitante']}")

    if not coincidencias:
        print("\nNada para borrar -- no hay ninguna fila con ese marcador exacto.")
        return

    if not aplicar:
        print("\n(DRY-RUN -- no se tocó Supabase. Correr con --aplicar para borrar de verdad.)")
        return

    indices_a_borrar = {i for i, _ in coincidencias}
    jugados_final = [f for i, f in enumerate(jugados) if i not in indices_a_borrar]

    with transaction() as repo:
        repo.replace_matches("lpf", pending, jugados_final)
    print(f"\n✓ Borrada(s) {len(coincidencias)} fila(s) de Supabase.")

    print("\nCorriendo una simulación para que la web refleje la corrección...")
    from main_lpf import correr_simulacion_lpf
    correr_simulacion_lpf(imprimir=False, guardar_json=True)
    print("✓ Snapshot actualizado -- refrescá la página (Ctrl+F5) para verlo.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("equipo_local")
    parser.add_argument("equipo_visitante")
    parser.add_argument("goles_local", type=int)
    parser.add_argument("goles_visitante", type=int)
    parser.add_argument("--aplicar", action="store_true")
    args = parser.parse_args()
    main(args.equipo_local, args.equipo_visitante, args.goles_local, args.goles_visitante, args.aplicar)
