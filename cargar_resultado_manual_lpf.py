# -*- coding: utf-8 -*-
"""
cargar_resultado_manual_lpf.py

Para partidos de LPF que YA se jugaron pero se cayeron de la ventana de
~100 "últimos" que expone Promiedos para esta liga (hc) -- no hay forma
de recuperarlos por scraping (ver docstring de scraper_promiedos_lpf.py:
sin paginación, sin endpoint de fechas por separado). Hay que cargarlos
a mano, mirando el resultado real en https://www.promiedos.com.ar (o
donde Pablo lo tenga) y pasándolo acá.

Busca primero si hay una fila pendiente en el fixture que matchee
(mismos equipos) para sacarla de pending al cargar el resultado; si no
la encuentra, carga el resultado igual (puede pasar si esa fila
pendiente tampoco llegó a existir nunca por el mismo problema de
ventana).

Por defecto corre en modo DRY-RUN. Para aplicar de verdad, pasar --aplicar.

Uso:
    python cargar_resultado_manual_lpf.py "Instituto" "Talleres de Córdoba" 2 1 --jornada 18
    python cargar_resultado_manual_lpf.py "Instituto" "Talleres de Córdoba" 2 1 --jornada 18 --aplicar

El nombre de cada equipo tiene que ser el CANÓNICO tal como aparece en
la tabla del simulador (si no estás seguro, correlo primero sin
--aplicar: si el nombre no resuelve, el resultado te lo muestra pero
avisa que no matcheó ningún equipo conocido).
"""
from __future__ import annotations

import argparse

from db.repository import transaction
from mapeo_equipos_lpf import resolver_equipo_lpf


def main(equipo_local: str, equipo_visitante: str, goles_local: int, goles_visitante: int,
         jornada: int, aplicar: bool) -> None:
    local = resolver_equipo_lpf(equipo_local) or equipo_local
    visitante = resolver_equipo_lpf(equipo_visitante) or equipo_visitante

    if local == equipo_local and resolver_equipo_lpf(equipo_local) is None:
        print(f"[aviso] '{equipo_local}' no resolvió contra ningún equipo conocido de LPF -- "
              f"revisá el nombre antes de aplicar.")
    if visitante == equipo_visitante and resolver_equipo_lpf(equipo_visitante) is None:
        print(f"[aviso] '{equipo_visitante}' no resolvió contra ningún equipo conocido de LPF -- "
              f"revisá el nombre antes de aplicar.")

    print(f"\nA cargar: {local} {goles_local}-{goles_visitante} {visitante} (jornada {jornada})")

    with transaction() as repo:
        pending = repo.match_records("lpf", "pending")
        jugados = repo.match_records("lpf", "played")

    ya_cargado = any(
        (resolver_equipo_lpf(f["equipo_local"]) or f["equipo_local"]) == local
        and (resolver_equipo_lpf(f["equipo_visitante"]) or f["equipo_visitante"]) == visitante
        and int(f.get("goles_local", -1)) == goles_local
        and int(f.get("goles_visitante", -1)) == goles_visitante
        for f in jugados
    )
    if ya_cargado:
        print("Este resultado (mismos equipos y mismo marcador) YA está cargado -- no se hace nada.")
        return

    idx_pendiente = next(
        (i for i, f in enumerate(pending)
         if (resolver_equipo_lpf(f["equipo_local"]) or f["equipo_local"]) == local
         and (resolver_equipo_lpf(f["equipo_visitante"]) or f["equipo_visitante"]) == visitante),
        None,
    )

    if idx_pendiente is not None:
        fila_fixture = pending[idx_pendiente]
        print(f"Encontrada fila pendiente (jornada {fila_fixture.get('jornada')}) -- se va a consumir.")
        jornada_final = fila_fixture.get("jornada", jornada)
        pending_final = [f for i, f in enumerate(pending) if i != idx_pendiente]
    else:
        # Mismo offset que calcular_filas_nuevas() (sincronizar_fixture_
        # clausura_lpf.py): la jornada que puso Pablo es la del Clausura
        # tal como la muestra Promiedos (reinicia en 1), pero acá adentro
        # las jornadas ya cargadas van todas por encima de eso para no
        # chocar con el Apertura -- si le pusiéramos la jornada cruda,
        # este partido quedaría mal ubicado en la evolución de posiciones
        # (que ordena por jornada).
        jornada_offset = max((int(f.get("jornada") or 0) for f in pending + jugados), default=0)
        # Si la jornada cruda que pasó Pablo ya es mayor al offset actual
        # (algo ya se cargó con esa numeración "final"), no le sumamos
        # el offset de nuevo -- asumimos que ya viene en la numeración
        # correcta.
        jornada_final = jornada if jornada > jornada_offset else jornada_offset + jornada
        print(f"No hay fila pendiente para esta pareja -- se carga el resultado directo, sin consumir "
              f"fixture, con jornada {jornada_final} (offset {jornada_offset} + fecha {jornada} de Promiedos).")
        pending_final = pending

    resultado_nuevo = {
        "fecha": "", "jornada": jornada_final,
        "equipo_local": local, "equipo_visitante": visitante,
        "goles_local": goles_local, "goles_visitante": goles_visitante,
    }
    jugados_final = jugados + [resultado_nuevo]

    if not aplicar:
        print("\n(DRY-RUN -- no se tocó Supabase. Correr con --aplicar para guardar de verdad.)")
        return

    with transaction() as repo:
        repo.replace_matches("lpf", pending_final, jugados_final)
    print("\n✓ Guardado en Supabase.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("equipo_local")
    parser.add_argument("equipo_visitante")
    parser.add_argument("goles_local", type=int)
    parser.add_argument("goles_visitante", type=int)
    parser.add_argument("--jornada", type=int, required=True,
                         help="Número de fecha del Clausura (1, 2, 3... el mismo que muestra Promiedos)")
    parser.add_argument("--aplicar", action="store_true")
    args = parser.parse_args()
    main(args.equipo_local, args.equipo_visitante, args.goles_local, args.goles_visitante,
         args.jornada, args.aplicar)
