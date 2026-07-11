# -*- coding: utf-8 -*-
"""
main_libertadores.py

Orquestador de la Copa Libertadores (fase eliminatoria desde octavos):
corre una simulación del cuadro (respetando resultados reales), el
Monte Carlo de % por ronda, y arma public/data_libertadores.json que
consume la pestaña "Copa Libertadores" de la web.

A diferencia de main_copa.py, esto NO pasa por Supabase (db.repository):
escribe el JSON directo a disco, mismo criterio simple que se usa para
correr esto de forma local o como paso de build. El botón "Correr nueva
simulación" en vivo desde la web llama a correr_simulacion_libertadores()
a través de POST /api/simular-libertadores en servidor.py, con el mismo
patrón que main_copa.py/correr_simulacion_copa().
"""
import json
from datetime import datetime

import rutas
from modelos.estadisticas_libertadores import EstadisticasLibertadores, RONDAS

RUTA_JSON_LIBERTADORES = rutas.public_dir() / "data_libertadores.json"


def _preparar_motor():
    e = EstadisticasLibertadores()
    e.cargar_datos_libertadores()
    e.crear_equipos_libertadores()
    return e


def armar_datos_web_libertadores(e, rondas_detalle, campeon, mc, n_sims):
    return {
        "liga": "Copa Libertadores",
        "generado": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "n_simulaciones": n_sims,
        "rondas": rondas_detalle,
        "campeon": campeon,
        "monte_carlo": mc,
        "equipos_vivos": e.equipos_vivos(),
    }


def guardar_json_libertadores(datos_web, ruta=None):
    ruta = ruta or RUTA_JSON_LIBERTADORES
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos_web, f, ensure_ascii=False, indent=2)
    return str(ruta)


def correr_simulacion_libertadores(imprimir=True, guardar_json=True, n_sims=1000):
    e = _preparar_motor()

    rondas_detalle, campeon = e.simular_libertadores()
    mc = e.monte_carlo_libertadores(n_simulaciones=n_sims)

    datos = armar_datos_web_libertadores(e, rondas_detalle, campeon, mc, n_sims)

    if imprimir:
        print(f"\nCampeón de la Copa Libertadores en esta corrida: {campeon}")
    if guardar_json:
        ruta = guardar_json_libertadores(datos)
        if imprimir:
            print(f"JSON guardado en {ruta}")
    return datos


def simular_hasta_campeon_libertadores(equipo_objetivo, max_intentos=5000, imprimir=True):
    """Repite el cuadro hasta que `equipo_objetivo` salga campeón."""
    e = _preparar_motor()

    participantes = {c["equipo_ida_local"] for c in e.cuadro} | {c["equipo_vuelta_local"] for c in e.cuadro}
    if equipo_objetivo not in participantes:
        sugerencias = [n for n in sorted(participantes) if equipo_objetivo.lower() in n.lower()]
        mensaje = f"'{equipo_objetivo}' no juega esta instancia de la Copa Libertadores."
        if sugerencias:
            mensaje += f" ¿Quisiste decir: {', '.join(sugerencias)}?"
        raise ValueError(mensaje)

    if equipo_objetivo not in e.equipos_vivos():
        raise ValueError(f"{equipo_objetivo} ya quedó eliminado (dato real): no hay simulación que lo salve.")

    for intento in range(1, max_intentos + 1):
        if imprimir and intento % 500 == 0:
            print(f"...intento {intento}, todavía no salió campeón")
        rondas_detalle, campeon = e.simular_libertadores()
        if campeon == equipo_objetivo:
            if imprimir:
                print(f"\n¡{equipo_objetivo} CAMPEÓN DE LA COPA LIBERTADORES! (intento {intento})")
            return {"equipo": equipo_objetivo, "intentos": intento, "rondas": rondas_detalle}

    if imprimir:
        print(f"\nNo salió campeón {equipo_objetivo} en {max_intentos} intentos.")
    return None


if __name__ == "__main__":
    correr_simulacion_libertadores()
