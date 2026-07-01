# -*- coding: utf-8 -*-
"""
backfill_goleadores.py

Script de UNA SOLA VEZ. Trae el historial completo de goles por jugador
de TODAS las fechas ya jugadas del torneo (usando scraper_promiedos, que
ya trae el detalle de quién convirtió en cada partido) y arma
datos/goleadores.csv desde cero.

Después de correr esto una vez, no hace falta correrlo de nuevo: el
scraper normal (a través de actualizar_resultados.py) va sumando los
goles de los partidos nuevos a este mismo CSV, fecha a fecha.

Uso:
    python backfill_goleadores.py

Si volvés a correrlo más adelante (por ejemplo si sospechás que
goleadores.csv se desincronizó de algo), pisa el archivo por completo
y lo reconstruye desde cero con todo el historial disponible en
Promiedos a ese momento — no duplica nada.
"""
import csv
from pathlib import Path

from mapeo_equipos import resolver_equipo
from scraper_promiedos import obtener_partidos_jugados

DATOS_DIR = Path(__file__).resolve().parent / "datos"
GOLEADORES_CSV = DATOS_DIR / "goleadores.csv"
CAMPOS = ["jugador", "equipo", "goles"]


def main():
    print("Bajando el historial completo de partidos jugados desde Promiedos...")
    print("(puede tardar bastante más que una actualización normal, son ~35 fechas)")
    partidos = obtener_partidos_jugados()
    print(f"  {len(partidos)} partidos jugados encontrados.")

    conteo = {}
    equipos_sin_matchear = set()

    for p in partidos:
        local = resolver_equipo(p["equipo_local"])
        visitante = resolver_equipo(p["equipo_visitante"])

        if not local:
            equipos_sin_matchear.add(p["equipo_local"])
        if not visitante:
            equipos_sin_matchear.add(p["equipo_visitante"])

        if local:
            for jugador, goles in p.get("goleadores_local", {}).items():
                conteo[(jugador, local)] = conteo.get((jugador, local), 0) + goles
        if visitante:
            for jugador, goles in p.get("goleadores_visitante", {}).items():
                conteo[(jugador, visitante)] = conteo.get((jugador, visitante), 0) + goles

    filas = [
        {"jugador": jugador, "equipo": equipo, "goles": goles}
        for (jugador, equipo), goles in conteo.items()
    ]
    filas.sort(key=lambda f: -f["goles"])

    DATOS_DIR.mkdir(exist_ok=True)
    with open(GOLEADORES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS)
        writer.writeheader()
        writer.writerows(filas)

    print(f"\nGuardado {GOLEADORES_CSV} con {len(filas)} jugadores distintos.")
    if equipos_sin_matchear:
        print(f"\n[aviso] {len(equipos_sin_matchear)} nombres de equipo no matchearon "
              f"(revisar mapeo_equipos.py), sus goles NO se cargaron:")
        for e in sorted(equipos_sin_matchear):
            print(f"    - {e}")

    print("\nListos los primeros del historial:")
    for f in filas[:10]:
        print(f"  {f['jugador']} ({f['equipo']}): {f['goles']}")


if __name__ == "__main__":
    main()
