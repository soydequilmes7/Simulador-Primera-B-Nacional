# -*- coding: utf-8 -*-
"""
main_sudamericana.py

Orquestador de la Copa Sudamericana (Playoffs de Octavos en adelante):
corre una simulación del cuadro real (datos/sudamericana_cuadro.csv) y
arma public/data_sudamericana.json, que consume la pestaña "Copa
Sudamericana" de la web -- mismo patrón que main_libertadores.py, pero
sin Monte Carlo todavía (EstadisticasLibertadores.monte_carlo_
libertadores() solo cuenta participantes de self.cuadro, que acá
arranca en Octavos -- no contempla los 16 de Playoffs; se deja para
una vuelta siguiente en vez de dar un % incompleto/engañoso).
"""
import json
from datetime import datetime

import rutas
from modelos.estadisticas_sudamericana import EstadisticasSudamericana

RUTA_JSON_SUDAMERICANA = rutas.public_dir() / "data_sudamericana.json"


def _preparar_motor():
    e = EstadisticasSudamericana()
    e.cargar_datos_sudamericana()
    e.crear_equipos_sudamericana()
    return e


def armar_datos_web_sudamericana(e, rondas_detalle, campeon):
    equipos_vivos = _equipos_vivos(rondas_detalle)
    return {
        "liga": "Copa Sudamericana",
        "generado": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "rondas": rondas_detalle,
        "campeon": campeon,
        "equipos_vivos": equipos_vivos,
    }


def _equipos_vivos(rondas_detalle):
    """Mismo criterio que EstadisticasLibertadores.equipos_vivos(), pero
    a partir del detalle YA SIMULADO (necesario acá porque self.cuadro
    del motor no incluye Playoffs -- ver docstring del módulo)."""
    eliminados = set()
    participantes = set()
    for ronda, llaves in rondas_detalle.items():
        for d in llaves:
            equipos = [d["local"], d["visitante"]] if ronda == "final" else list(d["agregado"].keys())
            participantes.update(equipos)
            perdedor = next((eq for eq in equipos if eq != d["avanza"]), None)
            if perdedor:
                eliminados.add(perdedor)
    return sorted(participantes - eliminados)


def guardar_json_sudamericana(datos_web, ruta=None):
    ruta = ruta or RUTA_JSON_SUDAMERICANA
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos_web, f, ensure_ascii=False, indent=2)
    return str(ruta)


def correr_simulacion_sudamericana(imprimir=True, guardar_json=True):
    e = _preparar_motor()
    rondas_detalle, campeon = e.simular_sudamericana()
    datos = armar_datos_web_sudamericana(e, rondas_detalle, campeon)

    if imprimir:
        print(f"\nCampeón de la Copa Sudamericana en esta corrida: {campeon}")
    if guardar_json:
        ruta = guardar_json_sudamericana(datos)
        if imprimir:
            print(f"JSON guardado en {ruta}")
    return datos


if __name__ == "__main__":
    correr_simulacion_sudamericana()
