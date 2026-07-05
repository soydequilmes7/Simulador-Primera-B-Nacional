# -*- coding: utf-8 -*-
"""
main_federal.py

Orquestador del Torneo Federal A: encadena las fases de EstadisticasFederal
(Primera Fase -> Segunda Fase -> Tercera/Cuarta/Quinta Fase, en paralelo
con la Reválida de 6 Etapas) para una corrida completa, arma el JSON que
consume la web y corre el Monte Carlo.
Mismo rol que main.py/main_lpf.py/main_copa.py/main_bmetro.py para sus
respectivas ligas.
"""
from __future__ import annotations

import datetime
import json

import pandas as pd
import numpy as np

import data_access
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


def _tabla_desde_arrays(nombres_zona: list[str], orden: np.ndarray, puntos: np.ndarray,
                         gf: np.ndarray, gc: np.ndarray, s: int) -> pd.DataFrame:
    """Arma un DataFrame equipo/puntos/gf/gc/dg -- mismo shape que
    _armar_tabla_final() -- ya ordenado de mejor a peor, para la
    repetición `s` de un array vectorizado (orden[:,s] trae los índices
    LOCALES a la zona, ya ordenados)."""
    idx = orden[:, s]
    p, g, c = puntos[idx, s], gf[idx, s], gc[idx, s]
    return pd.DataFrame({
        "equipo": [nombres_zona[i] for i in idx],
        "puntos": p, "gf": g, "gc": c, "dg": g - c,
    })


def _tabla_slots_desde_arrays(nombres_globales: list[str], slots: np.ndarray, puntos: np.ndarray,
                               gf: np.ndarray, gc: np.ndarray, s: int,
                               reales: np.ndarray | None = None) -> pd.DataFrame:
    """Igual que _tabla_desde_arrays() pero para una zona armada por
    slots (Segunda Fase / Reválida 1ª Etapa), donde slots[:,s] ya son
    índices GLOBALES de equipo (no locales a una zona fija) y hay que
    ordenar por (puntos, dg, gf) porque no vienen pre-ordenados como los
    de Primera Fase. `reales` descarta los slots fantasma inactivos en
    esta repetición (Reválida, zonas de 9 en vez de 10)."""
    idx_equipo = slots[:, s]
    p, g, c = puntos[:, s], gf[:, s], gc[:, s]
    if reales is not None:
        activos = reales[:, s]
        idx_equipo, p, g, c = idx_equipo[activos], p[activos], g[activos], c[activos]
    tabla = pd.DataFrame({
        "equipo": [nombres_globales[i] for i in idx_equipo],
        "puntos": p, "gf": g, "gc": c, "dg": g - c,
    })
    return tabla.sort_values(by=["puntos", "dg", "gf"], ascending=False, kind="stable").reset_index(drop=True)


def _extraer_tablas_repeticion(vec: dict, s: int) -> tuple[dict, dict, dict]:
    """A partir del dict que devuelve simular_temporada_vectorizada(),
    arma (tablas_pf, tablas_2f, tablas_r1) para la repetición `s`, en el
    mismo shape que devuelven simular_primera_fase()/
    simular_segunda_fase()/simular_revalida_primera_etapa() -- así
    clasificados_primera_fase()/clasificados_segunda_fase()/
    calcular_descensos()/armar_revalida_segunda_etapa() se usan TAL CUAL,
    sin cambiar ninguna línea de esos métodos."""
    nombres = vec["nombres"]

    tablas_pf = {
        z: _tabla_desde_arrays(vec["zonas_pf"][z], vec["orden_pf"][z], vec["puntos_pf"][z],
                                vec["gf_pf"][z], vec["gc_pf"][z], s)
        for z in ("1", "2", "3", "4")
    }
    tablas_2f = {
        "A": _tabla_slots_desde_arrays(nombres, vec["slots_a"], vec["puntos_a"], vec["gf_a"], vec["gc_a"], s),
        "B": _tabla_slots_desde_arrays(nombres, vec["slots_b"], vec["puntos_b"], vec["gf_b"], vec["gc_b"], s),
    }
    tablas_r1 = {
        "RA": _tabla_slots_desde_arrays(nombres, vec["slots_ra"], vec["puntos_ra"], vec["gf_ra"], vec["gc_ra"], s,
                                         reales=vec["reales_ra"]),
        "RB": _tabla_slots_desde_arrays(nombres, vec["slots_rb"], vec["puntos_rb"], vec["gf_rb"], vec["gc_rb"], s,
                                         reales=vec["reales_rb"]),
    }
    return tablas_pf, tablas_2f, tablas_r1


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

    if imprimir:
        print(f"\nCorriendo Monte Carlo ({n_sims} simulaciones, Primera/Segunda Fase y "
              f"Reválida 1ª Etapa vectorizadas)...")

    vec = e.simular_temporada_vectorizada(n_sims)
    paso = max(1, n_sims // 10)
    for s in range(n_sims):
        tablas_pf, tablas_2f, tablas_r1 = _extraer_tablas_repeticion(vec, s)
        clasif_pf = e.clasificados_primera_fase(tablas_pf)
        clasif_2f = e.clasificados_segunda_fase(tablas_2f)

        resultados_3f = e.jugar_tercera_fase(clasif_2f["tercera_fase"])
        resultados_4f = e.jugar_cuarta_fase(resultados_3f)
        resultado_5f = e.jugar_quinta_fase(resultados_4f)

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

        contador[resultado_5f.ganador]["ascenso_1"] += 1
        contador[resultado_r6.ganador]["ascenso_2"] += 1
        for nombre in descensos:
            contador[nombre]["descenso"] += 1

        if imprimir and (s + 1) % paso == 0:
            print(f"  {s + 1}/{n_sims} simulaciones...")

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
        data_access.save_simulation_output("federal_a", "federal_a", datos_web, n_sims)
        if imprimir:
            print("\nJSON guardado en Supabase")

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
