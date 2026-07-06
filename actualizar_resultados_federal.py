# -*- coding: utf-8 -*-
"""
actualizar_resultados_federal.py

Versión Federal A de actualizar_resultados_bmetro.py, con estas
diferencias:

  1. Usa scraper_promiedos_federal.py (league id "fahi").
  2. calcular_tabla_federal.py SÍ reordena por zona (Federal A tiene 4
     zonas reales; B Metro usa una zona ficticia "Unica").
  3. Si se pasa correr_simulacion_fn, por default es
     main_federal.correr_simulacion_federal.

Uso manual:
    python actualizar_resultados_federal.py

Uso programático:
    from actualizar_resultados_federal import actualizar
    resultado = actualizar()  # sin re-simular
    resultado = actualizar(correr_simulacion_fn=correr_simulacion_federal)
"""
from __future__ import annotations

from datetime import datetime

from db.repository import transaction

from scraper_promiedos_federal import obtener_partidos_federal, obtener_partidos_jugados_federal
from scraper_tabla_promiedos_federal import obtener_tablas_federal
from calcular_tabla_federal import _aplicar_partido, _reordenar_posiciones

CAMPOS_FIXTURE = ["fecha", "jornada", "equipo_local", "equipo_visitante"]
CAMPOS_RESULTADOS = ["fecha", "jornada", "equipo_local", "equipo_visitante",
                      "goles_local", "goles_visitante"]


def _normalizar_jornada(valor) -> str:
    if valor is None or valor == "":
        return ""
    try:
        return str(int(valor))
    except (TypeError, ValueError):
        return str(valor).strip()


def _clave_partido(fila: dict) -> tuple[str, str, str]:
    return (
        _normalizar_jornada(fila.get("jornada")),
        fila["equipo_local"],
        fila["equipo_visitante"],
    )


def _clave_resultado(fila: dict) -> tuple[str, str, str, str, str]:
    return (
        *_clave_partido(fila),
        str(int(fila["goles_local"])),
        str(int(fila["goles_visitante"])),
    )


def _fila_fixture_desde_promiedos(partido: dict) -> dict:
    return {
        "fecha": "",
        "jornada": partido.get("jornada", ""),
        "equipo_local": partido["equipo_local"],
        "equipo_visitante": partido["equipo_visitante"],
    }


def _fila_resultado_desde_promiedos(partido: dict) -> dict:
    return {
        "fecha": "",
        "jornada": partido.get("jornada", ""),
        "equipo_local": partido["equipo_local"],
        "equipo_visitante": partido["equipo_visitante"],
        "goles_local": int(partido["goles_local"]),
        "goles_visitante": int(partido["goles_visitante"]),
    }


def _standing_records_desde_tablas(tablas_por_zona: dict[str, list[dict]]) -> list[dict]:
    filas = []
    for zona in sorted(tablas_por_zona):
        for posicion, fila in enumerate(tablas_por_zona[zona], start=1):
            filas.append({
                "zona": zona,
                "posicion": posicion,
                "equipo": fila["equipo"],
                "partidos_jugados": int(fila["pj"]),
                "ganados": int(fila["g"]),
                "empatados": int(fila["e"]),
                "perdidos": int(fila["p"]),
                "gf": int(fila["gf"]),
                "gc": int(fila["gc"]),
                "dg": int(fila["dg"]),
                "puntos": int(fila["puntos"]),
            })
    return filas


def _obtener_standings_promiedos(imprimir: bool = True) -> list[dict] | None:
    try:
        tablas = obtener_tablas_federal()
    except Exception as e:
        if imprimir:
            print(f"  [aviso] no se pudo refrescar tabla Federal A desde Promiedos ({e}); "
                  "uso actualización incremental.")
        return None

    if len(tablas) != 4:
        if imprimir:
            print(f"  [aviso] Promiedos devolvió {len(tablas)} zona(s) de tabla Federal A; "
                  "uso actualización incremental.")
        return None

    return _standing_records_desde_tablas(tablas)


def _claves_fixture(fixture: list[dict]) -> set[tuple[str, str, str]]:
    return {_clave_partido(f) for f in fixture}


def _claves_resultados(resultados: list[dict]) -> set[tuple[str, str, str, str, str]]:
    return {_clave_resultado(f) for f in resultados}


def _preparar_sync_promiedos(
    partidos_promiedos: list[dict],
    fixture_actual: list[dict],
    resultados_actuales: list[dict],
    standings_actuales: list[dict],
    standings_promiedos: list[dict] | None,
) -> dict:
    equipos_conocidos = {
        fila["equipo"]
        for fila in (standings_promiedos or standings_actuales)
    }
    sin_matchear = [
        p for p in partidos_promiedos
        if p["equipo_local"] not in equipos_conocidos
        or p["equipo_visitante"] not in equipos_conocidos
    ]
    claves_sin_matchear = {_clave_partido(p) for p in sin_matchear}
    partidos_validos = [
        p for p in partidos_promiedos
        if _clave_partido(p) not in claves_sin_matchear
    ]
    fixture_promiedos = [
        _fila_fixture_desde_promiedos(p)
        for p in partidos_validos
        if not p.get("jugado")
    ]
    resultados_promiedos = [
        _fila_resultado_desde_promiedos(p)
        for p in partidos_validos
        if p.get("jugado")
    ]
    resultados_ya_cargados = {_clave_partido(fila) for fila in resultados_actuales}
    cargados = [
        p for p in partidos_validos
        if p.get("jugado") and _clave_partido(p) not in resultados_ya_cargados
    ]

    return {
        "fixture": fixture_promiedos,
        "resultados": resultados_promiedos,
        "cargados": cargados,
        "sin_matchear": sin_matchear,
        "fixture_reparado": _claves_fixture(fixture_actual) != _claves_fixture(fixture_promiedos),
        "resultados_reparados": (
            _claves_resultados(resultados_actuales)
            != _claves_resultados(resultados_promiedos)
        ),
    }


def _clasificar_partidos_jugados(
    partidos_jugados: list[dict],
    fixture: list[dict],
    resultados: list[dict],
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    indice_fixture = {}
    for i, fila in enumerate(fixture):
        indice_fixture[_clave_partido(fila)] = i

    resultados_ya_cargados = {_clave_partido(fila) for fila in resultados}
    resultados_actualizados = list(resultados)
    sin_matchear = []
    cargados = []
    indices_a_borrar = []

    for p in partidos_jugados:
        clave = _clave_partido(p)
        if clave in resultados_ya_cargados:
            continue
        if clave in indice_fixture:
            idx = indice_fixture[clave]
            fila_fixture = fixture[idx]
            resultados_actualizados.append({
                "fecha": fila_fixture.get("fecha", ""),
                "jornada": fila_fixture.get("jornada", ""),
                "equipo_local": p["equipo_local"],
                "equipo_visitante": p["equipo_visitante"],
                "goles_local": p["goles_local"],
                "goles_visitante": p["goles_visitante"],
            })
            indices_a_borrar.append(idx)
            cargados.append(p)
            resultados_ya_cargados.add(clave)
        else:
            sin_matchear.append(p)

    fixture_restante = [f for i, f in enumerate(fixture) if i not in indices_a_borrar]
    return fixture_restante, resultados_actualizados, cargados, sin_matchear


def actualizar(n_sims: int = 500, correr_simulacion_fn=None, imprimir: bool = True) -> dict:
    ahora = datetime.now().isoformat(timespec="seconds")

    with transaction() as repo:
        fixture = repo.match_records("federal_a", "pending")
        resultados = repo.match_records("federal_a", "played")
        standings_actuales = repo.standing_records("federal_a")

    if imprimir:
        print(f"[{ahora}] Scrapeando Promiedos (Federal A)...")

    partidos_promiedos = obtener_partidos_federal()

    if imprimir:
        n_jugados = sum(1 for p in partidos_promiedos if p.get("jugado"))
        n_pendientes = len(partidos_promiedos) - n_jugados
        print(f"  {len(partidos_promiedos)} partidos publicados vistos en Promiedos "
              f"({n_jugados} jugados, {n_pendientes} pendientes)")

    partidos_jugados_fallback = None
    if partidos_promiedos:
        standings_promiedos = _obtener_standings_promiedos(imprimir=imprimir)
        sync = _preparar_sync_promiedos(
            partidos_promiedos,
            fixture,
            resultados,
            standings_actuales,
            standings_promiedos,
        )
        fixture_promiedos = sync["fixture"]
        resultados_promiedos = sync["resultados"]
        cargados = sync["cargados"]
        sin_matchear = sync["sin_matchear"]
        fixture_reparado = sync["fixture_reparado"]
        resultados_reparados = sync["resultados_reparados"]
        backfill_historico_sin_tabla = standings_promiedos is None and len(cargados) > 20

        if backfill_historico_sin_tabla:
            if imprimir:
                print("  [aviso] Promiedos devolvió muchos resultados nuevos pero no se pudo "
                      "refrescar la tabla oficial; evito sincronizar para no doble-contar standings.")
            partidos_jugados_fallback = [p for p in partidos_promiedos if p.get("jugado")]
        elif cargados or fixture_reparado or resultados_reparados:
            with transaction() as repo:
                repo.replace_matches("federal_a", fixture_promiedos, resultados_promiedos)
                if standings_promiedos is not None:
                    repo.upsert_standings("federal_a", standings_promiedos)
                else:
                    filas = repo.standing_records("federal_a")
                    indice = {f["equipo"]: f for f in filas}
                    for p in cargados:
                        _aplicar_partido(
                            indice, p["equipo_local"], p["equipo_visitante"],
                            int(p["goles_local"]), int(p["goles_visitante"]),
                        )
                    repo.upsert_standings("federal_a", _reordenar_posiciones(filas))

        if not backfill_historico_sin_tabla:
            datos = None
            simulacion_corrida = False
            actualizado = bool(cargados or fixture_reparado or resultados_reparados)
            if correr_simulacion_fn is not None:
                if imprimir:
                    if cargados:
                        print(f"  Cargados {len(cargados)} partidos nuevos. Re-simulando...")
                    elif actualizado:
                        print("  Fixture/resultados de Federal A reparados. Re-simulando...")
                datos = correr_simulacion_fn(
                    n_sims=n_sims,
                    imprimir=imprimir if cargados or actualizado else False,
                    guardar_json=actualizado,
                )
                simulacion_corrida = bool(actualizado)
            elif imprimir:
                if cargados:
                    print(f"  Cargados {len(cargados)} partidos nuevos. "
                          f"(sin correr_simulacion_fn -> no se corrió ninguna simulación)")
                elif actualizado:
                    print("  Fixture/resultados de Federal A reparados. "
                          "(sin correr_simulacion_fn -> no se corrió ninguna simulación)")
                else:
                    print("  No hay partidos nuevos para cargar (todo ya estaba al día).")

            _guardar_log(
                ahora,
                cargados,
                sin_matchear,
                simulacion_corrida=simulacion_corrida,
                metadata={
                    "modo": "sync_promiedos_completo",
                    "partidos_promiedos": len(partidos_promiedos),
                    "fixture_reparado": fixture_reparado,
                    "resultados_reparados": resultados_reparados,
                    "tabla_promiedos": standings_promiedos is not None,
                },
            )

            return {
                "actualizado": actualizado,
                "cargados": cargados,
                "sin_matchear": sin_matchear,
                "datos": datos,
                "fixture_reparado": fixture_reparado,
                "resultados_reparados": resultados_reparados,
            }

    # Fallback conservador para mantener el comportamiento anterior si la API
    # no devuelve el calendario completo.
    partidos_jugados = partidos_jugados_fallback or obtener_partidos_jugados_federal()

    if imprimir:
        print(f"  {len(partidos_jugados)} partidos jugados vistos en Promiedos (con zona resuelta)")

    fixture_restante, resultados, cargados, sin_matchear = _clasificar_partidos_jugados(
        partidos_jugados, fixture, resultados,
    )

    if not cargados:
        if imprimir:
            print("  No hay partidos nuevos para cargar (todo ya estaba al día).")
        _guardar_log(ahora, cargados, sin_matchear, simulacion_corrida=False, metadata={"modo": "incremental"})
        # Aunque no haya partidos nuevos, re-simulamos con los datos
        # actuales de Supabase y devolvemos `datos`. El snapshot estático
        # (data_federal_a.json) que sirve la página puede estar más viejo
        # que lo que ya hay cargado en Supabase, así que el frontend usa
        # este `datos` para refrescar tabla/racha en vez de quedarse con el
        # snapshot viejo. Ver correrActualizacionFederal() en index.html.
        datos = None
        if correr_simulacion_fn is not None:
            datos = correr_simulacion_fn(n_sims=n_sims, imprimir=False, guardar_json=False)
        return {
            "actualizado": False,
            "cargados": cargados,
            "sin_matchear": sin_matchear,
            "datos": datos,
            "mensaje": "No había partidos nuevos jugados que coincidan con el fixture pendiente.",
        }

    with transaction() as repo:
        repo.replace_matches("federal_a", fixture_restante, resultados)
        filas = repo.standing_records("federal_a")
        indice = {f["equipo"]: f for f in filas}
        for p in cargados:
            _aplicar_partido(
                indice, p["equipo_local"], p["equipo_visitante"],
                int(p["goles_local"]), int(p["goles_visitante"]),
            )
        repo.upsert_standings("federal_a", _reordenar_posiciones(filas))

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

    _guardar_log(
        ahora,
        cargados,
        sin_matchear,
        simulacion_corrida=simulacion_corrida,
        metadata={"modo": "incremental"},
    )

    return {
        "actualizado": True,
        "cargados": cargados,
        "sin_matchear": sin_matchear,
        "datos": datos,
    }


def _guardar_log(
    timestamp: str,
    cargados: list[dict],
    sin_matchear: list[dict],
    simulacion_corrida: bool,
    metadata: dict | None = None,
) -> None:
    with transaction() as repo:
        repo.log_update(
            "federal_a",
            cargados,
            sin_matchear,
            simulacion_corrida,
            metadata=metadata,
            timestamp=timestamp,
        )


if __name__ == "__main__":
    from main_federal import correr_simulacion_federal
    resultado = actualizar(correr_simulacion_fn=correr_simulacion_federal)
    if resultado["actualizado"]:
        print("\n✓ Actualización completa.")
    else:
        print("\n– Sin cambios.")
