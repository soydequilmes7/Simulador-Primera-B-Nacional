# -*- coding: utf-8 -*-
"""
diagnostico_sin_identificar_lpf.py

Diagnóstico de uso único para los partidos que actualizar_resultados_lpf.py
reporta como "sin identificar". Para cada pareja de equipos que le pases,
muestra:
  1. La fila EXACTA que devolvió Promiedos (nombres tal cual, sin resolver).
  2. A qué nombre canónico resuelve cada lado (o None si el resolver no
     lo reconoce -- eso ya es la causa más probable).
  3. Si hay una fila pendiente en el fixture para esa pareja, en cualquiera
     de los dos órdenes (local/visitante puede estar invertido respecto a
     lo que jugó Promiedos -- reprogramaciones de cancha, etc.).

No escribe nada. Es de solo lectura.

Uso:
    python diagnostico_sin_identificar_lpf.py "Estudiantes RC" "Sarmiento Junín"
    python diagnostico_sin_identificar_lpf.py "Belgrano" "Huracán"
    python diagnostico_sin_identificar_lpf.py "Platense" "Deportivo Riestra"
"""
import sys

import data_access
from mapeo_equipos_lpf import resolver_equipo_lpf
from scraper_promiedos_lpf import obtener_partidos_jugados_lpf


def normalizar_suelto(nombre):
    return (nombre or "").strip().lower()


def main():
    if len(sys.argv) != 3:
        print('Uso: python diagnostico_sin_identificar_lpf.py "Equipo A" "Equipo B"')
        raise SystemExit(1)

    a, b = sys.argv[1], sys.argv[2]
    a_resuelto = resolver_equipo_lpf(a)
    b_resuelto = resolver_equipo_lpf(b)

    print(f"'{a}' resuelve a: {a_resuelto!r}")
    print(f"'{b}' resuelve a: {b_resuelto!r}")
    if a_resuelto is None or b_resuelto is None:
        print(">>> AHÍ ESTÁ: el resolver no reconoce uno de los dos nombres tal como se lo pasaste.")
        print("    (esto prueba el nombre que le pasaste a mano, no necesariamente el que")
        print("     devolvió Promiedos -- seguí leyendo para ver el nombre real)")
    print()

    print("Buscando en lo que devuelve Promiedos ahora mismo...")
    partidos = obtener_partidos_jugados_lpf()
    encontrados = [
        p for p in partidos
        if normalizar_suelto(p["equipo_local"]) in (normalizar_suelto(a), normalizar_suelto(b))
        or normalizar_suelto(p["equipo_visitante"]) in (normalizar_suelto(a), normalizar_suelto(b))
    ]
    if not encontrados:
        print(f"  No aparece ningún partido de '{a}' ni '{b}' en la ventana actual de Promiedos "
              f"(puede que ya haya salido de la ventana de últimos ~100 -- normal si pasó tiempo).")
    for p in encontrados:
        rl = resolver_equipo_lpf(p["equipo_local"])
        rv = resolver_equipo_lpf(p["equipo_visitante"])
        print(f"  Promiedos: {p['equipo_local']!r} vs {p['equipo_visitante']!r} "
              f"({p['goles_local']}-{p['goles_visitante']})")
        print(f"    -> resuelve a: {rl!r} vs {rv!r}"
              + ("  <-- alguno de los dos da None, ese es el problema" if None in (rl, rv) else ""))
    print()

    print("Buscando en el fixture pendiente (Supabase)...")
    _, fixture, _ = data_access.league_data("lpf")
    fixture = fixture.to_dict("records") if hasattr(fixture, "to_dict") else fixture
    for fila in fixture:
        rl = resolver_equipo_lpf(fila["equipo_local"]) or fila["equipo_local"]
        rv = resolver_equipo_lpf(fila["equipo_visitante"]) or fila["equipo_visitante"]
        if {rl, rv} == {a_resuelto or a, b_resuelto or b}:
            orden = "MISMO orden (local/visitante)" if rl == (a_resuelto or a) else "ORDEN INVERTIDO respecto al que pasaste"
            print(f"  Fixture pendiente: {fila['equipo_local']!r} vs {fila['equipo_visitante']!r} "
                  f"(jornada {fila.get('jornada')}) -- {orden}")
            break
    else:
        print(f"  No hay ninguna fila pendiente en el fixture para {a!r} vs {b!r} "
              f"(en ningún orden) -- puede que el fixture no esté sincronizado para esta fecha.")


if __name__ == "__main__":
    main()
