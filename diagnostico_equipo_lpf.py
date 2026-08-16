# -*- coding: utf-8 -*-
"""
diagnostico_equipo_lpf.py

Vuelca todos los partidos de un equipo puntual que ya están cargados en
`resultados` (Supabase), para comparar contra fuentes reales cuando los
números no cierran ni agregando el partido que faltaba (caso real:
Instituto, 16/08/2026 -- ni sumando Fecha 3 vs Lanús cerraba contra la
tabla real, señal de que alguno de los otros 3 partidos ya cargados
tiene el marcador mal).

Uso:
    python diagnostico_equipo_lpf.py "Instituto"
"""
import sys

from db.repository import transaction
from mapeo_equipos_lpf import resolver_equipo_lpf

if __name__ == "__main__":
    equipo = resolver_equipo_lpf(sys.argv[1]) or sys.argv[1]
    print(f"Buscando partidos de: {equipo!r}\n")

    with transaction() as repo:
        jugados = repo.match_records("lpf", "played")

    partidos = [
        f for f in jugados
        if (resolver_equipo_lpf(f["equipo_local"]) or f["equipo_local"]) == equipo
        or (resolver_equipo_lpf(f["equipo_visitante"]) or f["equipo_visitante"]) == equipo
    ]
    partidos.sort(key=lambda f: int(f.get("jornada") or 0))

    pts = pj = gf = gc = 0
    for f in partidos:
        local = f["equipo_local"]
        visit = f["equipo_visitante"]
        gl, gv = int(f["goles_local"]), int(f["goles_visitante"])
        es_local = (resolver_equipo_lpf(local) or local) == equipo
        propios, rival_goles = (gl, gv) if es_local else (gv, gl)
        pj += 1
        gf += propios
        gc += rival_goles
        if propios > rival_goles:
            pts += 3
        elif propios == rival_goles:
            pts += 1
        print(f"  jornada {f.get('jornada')}: {local} {gl}-{gv} {visit}")

    print(f"\nTotal cargado: {pj} PJ, {pts} pts, GF{gf}, GC{gc}, DG{gf-gc:+d}")
