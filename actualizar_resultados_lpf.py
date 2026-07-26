# -*- coding: utf-8 -*-
"""
actualizar_resultados_lpf.py

Versión LPF de actualizar_resultados.py. Diferencias a propósito con el
original (Nacional):

  1. Usa scraper_promiedos_lpf.py en vez de scraper_promiedos.py.
  2. Lee/escribe fixture_lpf.csv, resultados_lpf.csv y tabla_lpf.csv
     (no pisa los archivos de Nacional).
  3. Los nombres de equipo de Promiedos NO siempre coinciden tal cual
     con fixture_lpf.csv/resultados_lpf.csv -- Promiedos usa nombre
     completo o corto según la sección/endpoint (ver
     mapeo_equipos_lpf.py). El matcheo contra el fixture pendiente
     (más abajo) resuelve ambos lados a su nombre canónico antes de
     comparar.
  4. NO toca goleadores: esta API de Promiedos no expone goleadores
     para la LPF, así que ese paso queda salteado (a diferencia de
     Nacional, que sí lo hace).
  5. NO corre una simulación al final por default. main.py/estadisticas.py
     están armados para el modelo de ascenso/descenso de la Nacional y
     todavía no hay un equivalente para la LPF (2 zonas + fase
     interzonal, sin promedios de descenso todavía definidos acá). Si
     ya tenés (o armamos) un correr_simulacion_lpf(), pasalo por el
     parámetro correr_simulacion_fn y se llama solo cuando haya
     partidos nuevos, igual que en Nacional.
  6. NO toca `standings` en Supabase (repo.upsert_standings). ¡OJO,
     ESTO ES A PROPÓSITO Y NO UN OLVIDO! `standings` para "lpf" es
     self.apertura en modelos/estadisticas_lpf.py: la tabla FINAL y
     CONGELADA del Apertura 2026 (30 equipos, se valida que no cambie
     de tamaño), usada solo como base histórica para ratings iniciales
     y para la Tabla Anual (que suma puntos_apertura + puntos_clausura
     por separado, ver EstadisticasLPF líneas ~390-414). La tabla real
     del Clausura NO vive en `standings`: se recalcula desde cero cada
     vez a partir de resultados_lpf.csv (ver main_lpf._tabla_actual_
     clausura() y EstadisticasLPF.cargar_datos_lpf(), self.tabla =
     self.apertura.copy() con las columnas puestas en 0).
     Versión anterior de este archivo SÍ llamaba _aplicar_partido() +
     repo.upsert_standings("lpf", ...) sobre esa misma fila -- eso
     sumaba cada partido del Clausura ARRIBA de la tabla del Apertura,
     corrompiendo la base histórica (partidos_jugados subía de 16 a 17,
     etc.) y haciendo que la Tabla Anual contara esos partidos DOS
     VECES (una vía Apertura contaminado, otra vía Clausura real). Si
     en algún momento hace falta persistir la tabla del Clausura en
     Supabase para otra cosa, tiene que ser en una fila/tabla distinta
     a la de "standings" de LPF -- nunca pisando self.apertura.
     (Ver revertir_standings_lpf_apertura.py para deshacer el daño ya
     hecho por la versión vieja de este archivo.)
  7. Auto-sincroniza el fixture pendiente en cada corrida (ver
     sincronizar_fixture_clausura_lpf.calcular_filas_nuevas(), importada
     acá). Promiedos reusa "Fecha N" para cada torneo/fase nueva
     (Apertura, Clausura, playoffs, el próximo Apertura...) sin
     distinguir cuál es -- sin este paso, cada transición de fase
     volvería a generar partidos "sin identificar" hasta que alguien se
     acuerde de correr el script de sync a mano. El offset de jornada
     que usa evita pisar resultados ya jugados de la fase anterior (ver
     el docstring de ese módulo para el detalle completo).

Uso manual:
    python actualizar_resultados_lpf.py

Uso programático (por ejemplo desde servidor.py):
    from actualizar_resultados_lpf import actualizar
    resultado = actualizar()
    # o, cuando exista el simulador de LPF:
    resultado = actualizar(correr_simulacion_fn=correr_simulacion_lpf)
"""
from datetime import datetime

from db.repository import transaction

from scraper_promiedos_lpf import obtener_partidos_jugados_lpf
from mapeo_equipos_lpf import resolver_equipo_lpf
from sincronizar_fixture_clausura_lpf import calcular_filas_nuevas

CAMPOS_FIXTURE = ["fecha", "jornada", "equipo_local", "equipo_visitante"]
CAMPOS_RESULTADOS = ["fecha", "jornada", "equipo_local", "equipo_visitante",
                      "goles_local", "goles_visitante"]


def actualizar(n_sims=1000, correr_simulacion_fn=None, imprimir=True):
    """
    Corre todo el proceso para la LPF. Devuelve un dict con el resultado,
    pensado para poder loguearse o devolverse como JSON desde el
    servidor web (igual que la versión Nacional).

    correr_simulacion_fn: función opcional tipo
        correr_simulacion_fn(n_sims=..., imprimir=..., guardar_json=...)
    Se llama solo si hay partidos nuevos cargados. Si no se pasa nada,
    se saltea el paso de simulación (ver docstring del módulo).
    """
    ahora = datetime.now().isoformat(timespec="seconds")

    with transaction() as repo:
        fixture = repo.match_records("lpf", "pending")
        resultados = repo.match_records("lpf", "played")

    # Auto-sincronización del fixture: cada vez que Promiedos arranca un
    # torneo/fase nueva (Clausura, playoffs, el próximo Apertura...) vuelve
    # a numerar "Fecha 1, 2, 3..." desde cero SIN avisar de qué torneo es
    # (ver docstring de sincronizar_fixture_clausura_lpf.py). El fixture
    # pendiente de la fase anterior para esa jornada ya se consumió, así
    # que sin este paso esos partidos quedarían "sin identificar" cada vez
    # que arranca una fase nueva -- exactamente el bug real reportado por
    # Pablo (26/07/2026, transición Apertura -> Clausura). En vez de que
    # alguien tenga que acordarse de correr el script aparte a mano, se
    # corre automáticamente ACÁ, siempre, con el mismo offset de jornada
    # (jornada máxima ya usada) para no pisar resultados ya jugados.
    filas_nuevas_fixture, _jornada_offset = calcular_filas_nuevas(fixture, resultados)
    if filas_nuevas_fixture:
        if imprimir:
            print(f"  [auto-sync] {len(filas_nuevas_fixture)} partido(s) nuevo(s) de fixture "
                  f"detectado(s) en Promiedos (torneo/fase nueva) -- agregados al fixture pendiente.")
        fixture = fixture + filas_nuevas_fixture

    if imprimir:
        print(f"[{ahora}] Scrapeando Promiedos (LPF)...")

    partidos_jugados = obtener_partidos_jugados_lpf()

    if imprimir:
        print(f"  {len(partidos_jugados)} partidos jugados vistos en Promiedos")

    # El fixture pendiente y lo que devuelve Promiedos pueden venir con
    # distinto formato de nombre para el mismo club (nombre completo vs.
    # corto -- Promiedos usa ambos según la sección, ver
    # mapeo_equipos_lpf.py). Se resuelve cada nombre a su forma canónica
    # ANTES de armar la clave de matcheo, así no importa qué formato haya
    # usado cada lado. Si un nombre no resuelve (equipo desconocido), se
    # deja tal cual -- no va a matchear nada y va a caer a sin_matchear,
    # que es lo correcto (no ocultar un problema real).
    def _clave(equipo_local, equipo_visitante):
        return (
            resolver_equipo_lpf(equipo_local) or equipo_local,
            resolver_equipo_lpf(equipo_visitante) or equipo_visitante,
        )

    indice_fixture = {}
    for i, fila in enumerate(fixture):
        clave = _clave(fila["equipo_local"], fila["equipo_visitante"])
        indice_fixture[clave] = i

    sin_matchear = []
    cargados = []
    elo_cargados = []
    indices_a_borrar = []

    for p in partidos_jugados:
        clave = _clave(p["equipo_local"], p["equipo_visitante"])
        if clave in indice_fixture:
            idx = indice_fixture[clave]
            fila_fixture = fixture[idx]
            resultado_cargado = {
                "fecha": fila_fixture.get("fecha", ""),
                "jornada": fila_fixture.get("jornada", ""),
                # Se guarda el nombre TAL COMO ESTABA en el fixture
                # pendiente (no el que trajo Promiedos), para no
                # introducir una tercera variante de nombre más allá de
                # las que ya conviven en el sistema.
                "equipo_local": fila_fixture["equipo_local"],
                "equipo_visitante": fila_fixture["equipo_visitante"],
                "goles_local": p["goles_local"],
                "goles_visitante": p["goles_visitante"],
            }
            resultados.append(resultado_cargado)
            indices_a_borrar.append(idx)
            cargados.append(p)
            elo_cargados.append(resultado_cargado)
        else:
            # O ya estaba cargado de una corrida anterior, o el nombre
            # no matchea con fixture_lpf.csv por algún motivo raro.
            sin_matchear.append(p)

    if not cargados:
        if filas_nuevas_fixture:
            # No hay resultados nuevos para cargar todavía, pero sí
            # apareció fixture nuevo (fase que arrancó pero sin partidos
            # jugados aún) -- lo guardamos igual para que quede reflejado
            # ya mismo, no recién en la próxima corrida que traiga resultados.
            with transaction() as repo:
                repo.replace_matches("lpf", fixture, resultados)
            if imprimir:
                print(f"  Fixture sincronizado ({len(filas_nuevas_fixture)} partido(s) nuevo(s)), "
                      f"pero todavía no hay resultados nuevos para cargar.")
        elif imprimir:
            print("  No hay partidos nuevos para cargar (todo ya estaba al día).")
        _guardar_log(ahora, cargados, sin_matchear, simulacion_corrida=False)
        # Aunque no haya partidos nuevos, re-simulamos con los datos
        # actuales de Supabase y devolvemos `datos`, para que el frontend
        # refresque en vez de quedarse con el snapshot estático viejo.
        datos = None
        if correr_simulacion_fn is not None:
            datos = correr_simulacion_fn(n_sims=n_sims, imprimir=False, guardar_json=False)
        return {
            "actualizado": False,
            "cargados": cargados,
            "sin_matchear": sin_matchear,
            "fixture_sincronizado": len(filas_nuevas_fixture),
            "datos": datos,
            "mensaje": "No había partidos nuevos jugados que coincidan con el fixture pendiente.",
        }

    fixture_restante = [f for i, f in enumerate(fixture) if i not in indices_a_borrar]

    with transaction() as repo:
        # OJO: acá NO se toca repo.standing_records("lpf") / no se
        # llama repo.upsert_standings("lpf", ...). Ver punto 6 del
        # docstring del módulo -- esa tabla es el Apertura congelado,
        # no la tabla del Clausura. Solo se reemplazan los partidos
        # (fixture pendiente / resultados jugados).
        repo.replace_matches("lpf", fixture_restante, resultados)
        elo_actualizados = repo.apply_club_rating_events(
            "lpf", elo_cargados, source="real_results", metadata={"origen": "actualizar_resultados_lpf.py"}
        )
        if imprimir:
            print(f"  ELO persistente actualizado con {elo_actualizados} partido(s).")

    datos = None
    simulacion_corrida = False
    if correr_simulacion_fn is not None:
        if imprimir:
            print(f"  Cargados {len(cargados)} partidos nuevos. Re-simulando...")
        datos = correr_simulacion_fn(n_sims=n_sims, imprimir=imprimir, guardar_json=True)
        simulacion_corrida = True
    elif imprimir:
        print(f"  Cargados {len(cargados)} partidos nuevos. "
              f"(sin correr_simulacion_fn -> no se corrió ninguna simulación)")

    _guardar_log(ahora, cargados, sin_matchear, simulacion_corrida=simulacion_corrida)

    return {
        "actualizado": True,
        "cargados": cargados,
        "sin_matchear": sin_matchear,
        "fixture_sincronizado": len(filas_nuevas_fixture),
        "datos": datos,
    }


def _guardar_log(timestamp, cargados, sin_matchear, simulacion_corrida):
    with transaction() as repo:
        repo.log_update("lpf", cargados, sin_matchear, simulacion_corrida, timestamp=timestamp)


if __name__ == "__main__":
    resultado = actualizar()
    if resultado["actualizado"]:
        print("\n✓ Actualización completa.")
    else:
        print("\n– Sin cambios.")
