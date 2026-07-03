# -*- coding: utf-8 -*-
"""
main_copa.py

Orquestador de la Copa Argentina: corre una simulación del cuadro
(respetando resultados reales), el Monte Carlo de % por ronda, y arma el
JSON que consume la pestaña "Copa Argentina" de la web
(public/data_copa.json). Mismo patrón que main.py y main_lpf.py.
"""
import json
from datetime import datetime

import rutas
from modelos.estadisticas_copa import EstadisticasCopa, RONDAS

RUTA_JSON_COPA = rutas.public_dir() / "data_copa.json"


def _preparar_motor():
    e = EstadisticasCopa()
    e.cargar_datos_copa()
    e.crear_equipos_copa()
    return e


def armar_datos_web_copa(e, rondas_detalle, campeon, mc, n_sims):
    return {
        "liga": "Copa Argentina",
        "generado": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "n_simulaciones": n_sims,
        "rondas": rondas_detalle,
        "campeon": campeon,
        "monte_carlo": mc,
        "equipos_vivos": e._equipos_vivos(),
    }


def guardar_json_copa(datos_web, ruta=None):
    ruta = ruta or RUTA_JSON_COPA
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos_web, f, ensure_ascii=False, indent=2)
    return ruta


def correr_simulacion_copa(imprimir=True, guardar_json=True, n_sims=1000):
    """Simula el cuadro completo una vez (para mostrar) + Monte Carlo de
    n_sims corridas (para los %). Devuelve el dict del JSON."""
    e = _preparar_motor()

    rondas_detalle, campeon = e.simular_copa()
    mc = e.monte_carlo_copa(n_simulaciones=n_sims)

    datos = armar_datos_web_copa(e, rondas_detalle, campeon, mc, n_sims)

    if imprimir:
        print(f"\nCampeón de la Copa Argentina en esta corrida: {campeon}")
    if guardar_json:
        ruta = guardar_json_copa(datos)
        if imprimir:
            print(f"JSON guardado en {ruta}")
    return datos


def simular_hasta_campeon_copa(equipo_objetivo, max_intentos=5000, imprimir=True):
    """Repite el cuadro hasta que `equipo_objetivo` salga campeón. Devuelve
    el detalle de esa corrida o None si no se logró. ValueError si el
    equipo no participa o ya está eliminado."""
    e = _preparar_motor()

    participantes = {c["equipo_local"] for c in e.cuadro} | {c["equipo_visitante"] for c in e.cuadro}
    if equipo_objetivo not in participantes:
        sugerencias = [n for n in sorted(participantes) if equipo_objetivo.lower() in n.lower()]
        mensaje = f"'{equipo_objetivo}' no juega la Copa Argentina."
        if sugerencias:
            mensaje += f" ¿Quisiste decir: {', '.join(sugerencias)}?"
        raise ValueError(mensaje)

    if equipo_objetivo not in e._equipos_vivos():
        raise ValueError(f"{equipo_objetivo} ya quedó eliminado de la Copa (dato real): "
                         "no hay simulación que lo salve.")

    for intento in range(1, max_intentos + 1):
        if imprimir and intento % 500 == 0:
            print(f"...intento {intento}, todavía no salió campeón")

        rondas_detalle, campeon = e.simular_copa()
        if campeon == equipo_objetivo:
            if imprimir:
                print(f"\n¡{equipo_objetivo} CAMPEÓN DE LA COPA ARGENTINA! (intento {intento})")
            return {
                "equipo": equipo_objetivo,
                "intentos": intento,
                "rondas": rondas_detalle,
            }

    if imprimir:
        print(f"\nNo salió campeón {equipo_objetivo} en {max_intentos} intentos.")
    return None


if __name__ == "__main__":
    correr_simulacion_copa()
