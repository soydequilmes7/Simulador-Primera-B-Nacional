# -*- coding: utf-8 -*-
"""
main_federal.py

Orquestador del Torneo Federal A: encadena las fases de EstadisticasFederal
(Primera Fase -> Segunda Fase -> Tercera/Cuarta/Quinta Fase, en paralelo
con la Reválida de 6 Etapas) para una corrida completa, arma el JSON que
consume la web (public/data_federal_a.json) y corre el Monte Carlo.
Mismo rol que main.py/main_lpf.py/main_copa.py/main_bmetro.py para sus
respectivas ligas.
"""
from __future__ import annotations

import datetime
import json

import pandas as pd

import rutas
from modelos.estadisticas_federal import EstadisticasFederal, ResultadoSerie

RUTA_JSON_FEDERAL_DEFAULT = "data_federal_a.json"


def _tabla_a_lista(tabla_df: pd.DataFrame) -> list[dict]:
    """DataFrame de tabla (columnas equipo/puntos/gf/gc/dg) -> lista de
    dicts con posición 1-indexada, mismo shape que usan las otras ligas."""
    filas = []
    for i, fila in enumerate(tabla_df.reset_index(drop=True).itertuples(index=False), start=1):
        filas.append({
            "posicion": i, "equipo": fila.equipo, "puntos": int(fila.puntos),
            "gf": int(fila.gf), "gc": int(fila.gc), "dg": int(fila.dg),
        })
    return filas


def _serie_a_dict(resultado: ResultadoSerie) -> dict:
    """ResultadoSerie -> dict en el shape que YA esperan los renderers
    del frontend (matchHTML/seriesHTML, usados por Nacional/LPF/B Metro),
    para no duplicar lógica de bracket en el HTML:
      - Partido único (Quinta Fase, via jugar_final_ascenso): shape de
        matchHTML -> local/visitante/golesLocal/golesVisitante/avanza.
      - Serie ida y vuelta (Tercera Fase en adelante y toda la
        Reválida, via _jugar_llave_ida_vuelta): shape de seriesHTML ->
        equipo_x/equipo_y/goles_x/goles_y/detalle/campeon.
    """
    d = resultado.detalle
    if "local_ida" in d:
        gl1, gv1 = d["ida"]
        gl2, gv2 = d["vuelta"]
        detalle_str = f"Ida: {gl1}-{gv1} | Vuelta: {gl2}-{gv2}"
        if d.get("definido_por") == "penales":
            detalle_str += " (Penales)"
        elif d.get("definido_por") == "mejor_ubicacion":
            detalle_str += " (por mejor ubicación)"
        return {
            "equipo_x": d["local_ida"], "equipo_y": d["visitante_ida"],
            "goles_x": d["agregado"][0], "goles_y": d["agregado"][1],
            "detalle": detalle_str, "campeon": resultado.ganador,
        }
    # Partido único (jugar_final_ascenso, enriquecido con local/visitante
    # en jugar_quinta_fase): shape de matchHTML.
    gl, gv = d["marcador"]
    return {
        "local": d["local"], "visitante": d["visitante"],
        "golesLocal": gl, "golesVisitante": gv,
        "avanza": resultado.ganador,
    }


def _preparar_motor() -> EstadisticasFederal:
    e = EstadisticasFederal()
    e.cargar_datos_federal()
    e.crear_equipos_federal()
    e.calcular_estadisticas()
    e.calcular_ratings()
    return e


def _correr_torneo_completo(e: EstadisticasFederal) -> dict:
    """Corre las 5 Fases + las 6 Etapas de la Reválida una vez sobre el
    estado actual de `e` (ratings ya calculados). Restaura zonas, fixture
    y tabla vigente de Primera Fase al principio
    (reiniciar_para_nueva_corrida()), así se puede reusar la misma
    instancia de `e` en cada repetición del Monte Carlo.
    Devuelve todos los artefactos intermedios -- los usan tanto la
    corrida de exhibición como simular_hasta_ascenso_federal()."""
    e.reiniciar_para_nueva_corrida()
    tablas_pf = e.simular_primera_fase()
    clasif_pf = e.clasificados_primera_fase(tablas_pf)

    e.armar_segunda_fase(clasif_pf)
    tablas_2f = e.simular_segunda_fase()
    clasif_2f = e.clasificados_segunda_fase(tablas_2f)

    resultados_3f = e.jugar_tercera_fase(clasif_2f["tercera_fase"])
    resultados_4f = e.jugar_cuarta_fase(resultados_3f)
    resultado_5f = e.jugar_quinta_fase(resultados_4f)

    e.armar_revalida_primera_etapa(clasif_pf)
    tablas_r1 = e.simular_revalida_primera_etapa()
    descensos = e.calcular_descensos(tablas_pf, tablas_r1, clasif_pf)

    posiciones_r2 = e.armar_revalida_segunda_etapa(
        resultados_3f, tablas_2f, clasif_2f["revalida_segunda_etapa_2f"], tablas_pf, tablas_r1
    )
    resultados_r2 = e.jugar_revalida_segunda_etapa(posiciones_r2)

    posiciones_r3 = e.armar_revalida_tercera_etapa(resultados_r2, resultados_4f, tablas_2f)
    resultados_r3 = e.jugar_revalida_tercera_etapa(posiciones_r3)

    posiciones_r4 = e.armar_revalida_cuarta_etapa(resultados_r3, resultado_5f)
    resultados_r4 = e.jugar_revalida_cuarta_etapa(posiciones_r4)

    resultados_r5 = e.jugar_revalida_quinta_etapa(resultados_r4)
    resultado_r6 = e.jugar_revalida_sexta_etapa(resultados_r5)

    return {
        "tablas_pf": tablas_pf, "clasif_pf": clasif_pf,
        "tablas_2f": tablas_2f, "clasif_2f": clasif_2f,
        "resultados_3f": resultados_3f, "resultados_4f": resultados_4f, "resultado_5f": resultado_5f,
        "tablas_r1": tablas_r1, "descensos": descensos,
        "posiciones_r2": posiciones_r2, "resultados_r2": resultados_r2,
        "posiciones_r3": posiciones_r3, "resultados_r3": resultados_r3,
        "posiciones_r4": posiciones_r4, "resultados_r4": resultados_r4,
        "resultados_r5": resultados_r5, "resultado_r6": resultado_r6,
        "ascenso_1": resultado_5f.ganador,
        "ascenso_2": resultado_r6.ganador,
    }


def _armar_datos_web(corrida: dict, monte_carlo: list[dict], n_sims: int, equipos: dict | None = None) -> dict:
    return {
        "liga": "federal_a",
        "generado": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "n_simulaciones": n_sims,
        "primera_fase": {
            "tablas": {zona: _tabla_a_lista(tabla) for zona, tabla in corrida["tablas_pf"].items()},
        },
        "segunda_fase": {
            "tablas": {zona: _tabla_a_lista(tabla) for zona, tabla in corrida["tablas_2f"].items()},
        },
        "camino_principal": {
            "tercera_fase": {k: _serie_a_dict(v) for k, v in corrida["resultados_3f"].items()},
            "cuarta_fase": {k: _serie_a_dict(v) for k, v in corrida["resultados_4f"].items()},
            "quinta_fase_final": _serie_a_dict(corrida["resultado_5f"]),
            "ascenso_1": corrida["ascenso_1"],
        },
        "revalida": {
            "primera_etapa": {
                "tablas": {zona: _tabla_a_lista(tabla) for zona, tabla in corrida["tablas_r1"].items()},
            },
            "descensos": corrida["descensos"],
            "segunda_etapa": {
                "posiciones": corrida["posiciones_r2"],
                "resultados": {k: _serie_a_dict(v) for k, v in corrida["resultados_r2"].items()},
            },
            "tercera_etapa": {
                "posiciones": corrida["posiciones_r3"],
                "resultados": {k: _serie_a_dict(v) for k, v in corrida["resultados_r3"].items()},
            },
            "cuarta_etapa": {
                "posiciones": corrida["posiciones_r4"],
                "resultados": {k: _serie_a_dict(v) for k, v in corrida["resultados_r4"].items()},
            },
            "quinta_etapa": {k: _serie_a_dict(v) for k, v in corrida["resultados_r5"].items()},
            "sexta_etapa_final": _serie_a_dict(corrida["resultado_r6"]),
            "ascenso_2": corrida["ascenso_2"],
        },
        "monte_carlo": monte_carlo,
        "rachas": {
            nombre: equipo.ultimos10[-5:]
            for nombre, equipo in (equipos or {}).items()
        },
    }


def correr_simulacion_federal(n_sims: int = 500, imprimir: bool = True, guardar_json: bool = True) -> dict:
    """Corre el Torneo Federal A completo una vez (para mostrar cómo
    terminó esa corrida puntual) + un Monte Carlo de `n_sims` repeticiones
    (para los porcentajes por equipo). Devuelve el dict del JSON web."""
    if imprimir:
        print("=" * 50)
        print("SIMULADOR TORNEO FEDERAL A 2026")
        print("=" * 50)

    e = _preparar_motor()
    corrida = _correr_torneo_completo(e)

    if imprimir:
        print(f"\n1° ASCENSO (camino principal): {corrida['ascenso_1']}")
        print(f"2° ASCENSO (Reválida): {corrida['ascenso_2']}")
        print(f"DESCIENDEN: {', '.join(corrida['descensos'])}")
        print(f"\nCorriendo Monte Carlo ({n_sims} simulaciones)...")

    equipos = list(e.equipos.keys())
    contador = {nombre: {"ascenso_1": 0, "ascenso_2": 0, "descenso": 0} for nombre in equipos}

    paso = max(1, n_sims // 10)
    for i in range(n_sims):
        resultado = _correr_torneo_completo(e)
        contador[resultado["ascenso_1"]]["ascenso_1"] += 1
        contador[resultado["ascenso_2"]]["ascenso_2"] += 1
        for nombre in resultado["descensos"]:
            contador[nombre]["descenso"] += 1
        if imprimir and (i + 1) % paso == 0:
            print(f"  {i + 1}/{n_sims} simulaciones...")

    monte_carlo = []
    for nombre, datos in contador.items():
        pct_asciende = round(100 * (datos["ascenso_1"] + datos["ascenso_2"]) / n_sims, 1)
        monte_carlo.append({
            "equipo": nombre,
            "%ascenso_directo": round(100 * datos["ascenso_1"] / n_sims, 1),
            "%ascenso_revalida": round(100 * datos["ascenso_2"] / n_sims, 1),
            "%asciende": pct_asciende,
            "%descenso": round(100 * datos["descenso"] / n_sims, 1),
        })
    monte_carlo.sort(key=lambda f: (-f["%asciende"], -f["%ascenso_directo"], f["equipo"]))

    datos_web = _armar_datos_web(corrida, monte_carlo, n_sims, equipos=e.equipos)

    if guardar_json:
        ruta = rutas.public_dir() / RUTA_JSON_FEDERAL_DEFAULT
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos_web, f, ensure_ascii=False, indent=2)
        if imprimir:
            print(f"\nJSON guardado en {ruta}")

    return datos_web


def simular_hasta_ascenso_federal(equipo_objetivo: str, max_intentos: int = 3000, imprimir: bool = True) -> dict | None:
    """Repite el torneo completo (camino principal + Reválida) hasta que
    `equipo_objetivo` ascienda, por la vía que sea. Devuelve el detalle
    de esa corrida (incluida la vía: 'directo' o 'revalida') o None si no
    se logró en max_intentos. Levanta ValueError si el equipo no existe."""
    if imprimir:
        print("=" * 50)
        print(f"SIMULANDO HASTA QUE ASCIENDA: {equipo_objetivo}")
        print("=" * 50)

    e = _preparar_motor()
    if equipo_objetivo not in e.equipos:
        sugerencias = [n for n in e.equipos if equipo_objetivo.lower() in n.lower()]
        mensaje = f"'{equipo_objetivo}' no es un equipo válido del Federal A."
        if sugerencias:
            mensaje += f" ¿Quisiste decir: {', '.join(sugerencias)}?"
        raise ValueError(mensaje)

    for intento in range(1, max_intentos + 1):
        if imprimir and intento % 100 == 0:
            print(f"...intento {intento}, todavía no ascendió")

        corrida = _correr_torneo_completo(e)
        via = None
        if corrida["ascenso_1"] == equipo_objetivo:
            via = "directo"
        elif corrida["ascenso_2"] == equipo_objetivo:
            via = "revalida"

        if via:
            if imprimir:
                print(f"\n¡{equipo_objetivo} ASCENDIÓ ({via}) en el intento {intento}!")
            return {"equipo": equipo_objetivo, "intentos": intento, "via": via,
                    **_armar_datos_web(corrida, monte_carlo=[], n_sims=0, equipos=e.equipos)}

    if imprimir:
        print(f"\nNo se logró el ascenso de {equipo_objetivo} en {max_intentos} intentos.")
    return None


if __name__ == "__main__":
    correr_simulacion_federal()
