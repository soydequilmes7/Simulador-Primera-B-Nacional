# -*- coding: utf-8 -*-
"""
actualizar_resultados.py

Orquesta la actualización automática:
  1. Trae los resultados actuales desde la API de Promiedos (scraper_promiedos.py)
  2. Traduce los nombres de equipo al formato local (mapeo_equipos.py)
  3. Busca esos partidos dentro de fixture.csv (los pendientes)
  4. Si los encuentra, los mueve a resultados.csv con sus goles
     y los borra de fixture.csv
  5. Suma los goles de esos partidos a datos/goleadores.csv (acumulado
     histórico de goles por jugador). NOTA: goleadores.csv tiene que
     existir de antes — correr backfill_goleadores.py una sola vez
     antes de la primera actualización, si todavía no lo hiciste.
  6. Si hubo al menos un partido nuevo, corre la simulación
     (correr_simulacion, de main.py) para regenerar data.json
  7. Guarda un log en log_actualizaciones.json con fecha/hora
     y el detalle de qué se cargó

Uso manual:
    python actualizar_resultados.py

Se puede llamar también programáticamente:
    from actualizar_resultados import actualizar
    resultado = actualizar()
"""
from datetime import datetime

from db.repository import transaction
from mapeo_equipos import resolver_equipo
from scraper_promiedos import obtener_partidos_jugados
from calcular_tabla import aplicar_partidos

CAMPOS_FIXTURE = ["fecha", "jornada", "equipo_local", "equipo_visitante"]
CAMPOS_RESULTADOS = ["fecha", "jornada", "equipo_local", "equipo_visitante",
                      "goles_local", "goles_visitante"]
CAMPOS_GOLEADORES = ["jugador", "equipo", "goles"]


def _traducir_partidos(partidos_promiedos):
    """
    Devuelve (partidos_traducidos, sin_matchear).
    partidos_traducidos ya tiene los nombres en formato local.
    """
    traducidos = []
    sin_matchear = []
    for p in partidos_promiedos:
        local = resolver_equipo(p["equipo_local"])
        visitante = resolver_equipo(p["equipo_visitante"])
        if local and visitante:
            traducidos.append({
                "equipo_local": local,
                "equipo_visitante": visitante,
                "goles_local": p["goles_local"],
                "goles_visitante": p["goles_visitante"],
                # Nombres de jugador tal cual, no necesitan traducción de
                # equipo (ya van con el nombre local en la clave de arriba).
                "goleadores_local": p.get("goleadores_local", {}),
                "goleadores_visitante": p.get("goleadores_visitante", {}),
            })
        else:
            sin_matchear.append(p)
    return traducidos, sin_matchear


def _actualizar_goleadores(cargados, imprimir=True):
    """
    Suma los goles de los partidos recién cargados a datos/goleadores.csv
    (acumulado histórico por jugador+equipo). Solo se llama con los
    partidos que efectivamente se cargaron (evita duplicar si se corre
    varias veces sin partidos nuevos).
    """
    with transaction() as repo:
        goles_sumados = repo.add_scorer_goals(cargados, "nacional")
    if imprimir:
        print(f"  {goles_sumados} goles de jugador sumados a goleadores.csv.")


def actualizar(n_sims=1000, imprimir=True):
    """
    Corre todo el proceso. Devuelve un dict con el resultado, pensado
    para poder loguearse o devolverse como JSON desde el servidor web.
    """
    ahora = datetime.now().isoformat(timespec="seconds")

    with transaction() as repo:
        fixture = repo.match_records("nacional", "pending")
        resultados = repo.match_records("nacional", "played")

    if imprimir:
        print(f"[{ahora}] Scrapeando Promiedos...")

    partidos_promiedos = obtener_partidos_jugados()
    traducidos, sin_matchear = _traducir_partidos(partidos_promiedos)

    if imprimir:
        print(f"  {len(partidos_promiedos)} partidos jugados vistos en Promiedos")
        print(f"  {len(traducidos)} matchearon con nombres locales")
        if sin_matchear:
            print(f"  {len(sin_matchear)} NO matchearon (revisar mapeo_equipos.py):")
            for p in sin_matchear:
                print(f"    - {p['equipo_local']} vs {p['equipo_visitante']}")

    # Indexamos el fixture pendiente por (equipo_local, equipo_visitante)
    # jornada no se usa como clave porque puede haber partidos reprogramados
    # que en tu fixture.csv siguen etiquetados con la jornada original.
    indice_fixture = {}
    for i, fila in enumerate(fixture):
        clave = (fila["equipo_local"], fila["equipo_visitante"])
        indice_fixture[clave] = i

    cargados = []
    indices_a_borrar = []

    for p in traducidos:
        clave = (p["equipo_local"], p["equipo_visitante"])
        if clave in indice_fixture:
            idx = indice_fixture[clave]
            fila_fixture = fixture[idx]
            resultados.append({
                "fecha": fila_fixture.get("fecha", ""),
                "jornada": fila_fixture.get("jornada", ""),
                "equipo_local": p["equipo_local"],
                "equipo_visitante": p["equipo_visitante"],
                "goles_local": p["goles_local"],
                "goles_visitante": p["goles_visitante"],
            })
            indices_a_borrar.append(idx)
            cargados.append(p)

    if not cargados:
        if imprimir:
            print("  No hay partidos nuevos para cargar (todo ya estaba al día).")
        _guardar_log(ahora, cargados, sin_matchear, simulacion_corrida=False)
        # Aunque no haya partidos nuevos, re-simulamos con los datos
        # actuales de Supabase y devolvemos `datos`. El snapshot estático
        # (data.json) que sirve la página puede estar más viejo que lo que
        # ya hay cargado en Supabase, así que el frontend usa este `datos`
        # para refrescar tabla/promedios/racha en vez de quedarse con el
        # snapshot viejo. Ver correrActualizacion() en public/index.html.
        from main import correr_simulacion
        datos = correr_simulacion(n_sims=n_sims, imprimir=False, guardar_json=False)
        return {
            "actualizado": False,
            "cargados": cargados,
            "sin_matchear": sin_matchear,
            "datos": datos,
            "mensaje": "No había partidos nuevos jugados que coincidan con el fixture pendiente.",
        }

    # Sacamos del fixture los que ya se jugaron
    fixture_restante = [f for i, f in enumerate(fixture) if i not in indices_a_borrar]

    with transaction() as repo:
        repo.replace_matches("nacional", fixture_restante, resultados)
        goles_sumados = repo.add_scorer_goals(cargados, "nacional")
        tabla_nueva = aplicar_partidos(repo.standing_records("nacional"), cargados)
        repo.upsert_standings("nacional", tabla_nueva)
        if imprimir:
            print(f"  {goles_sumados} goles de jugador sumados a goleadores.csv.")
            print(f"  tabla.csv actualizada con {len(cargados)} partido(s) nuevo(s).")

    if imprimir:
        print(f"  Cargados {len(cargados)} partidos nuevos. Re-simulando...")

    # Importa aquí para evitar import circular si este módulo se usa antes
    # de que main.py esté disponible en el path.
    from main import correr_simulacion
    datos = correr_simulacion(n_sims=n_sims, imprimir=imprimir, guardar_json=True)

    _guardar_log(ahora, cargados, sin_matchear, simulacion_corrida=True)

    return {
        "actualizado": True,
        "cargados": cargados,
        "sin_matchear": sin_matchear,
        "datos": datos,
    }


def _guardar_log(timestamp, cargados, sin_matchear, simulacion_corrida):
    with transaction() as repo:
        repo.log_update("nacional", cargados, sin_matchear, simulacion_corrida, timestamp=timestamp)


if __name__ == "__main__":
    resultado = actualizar()
    if resultado["actualizado"]:
        print("\n✓ Actualización completa.")
    else:
        print("\n– Sin cambios.")
