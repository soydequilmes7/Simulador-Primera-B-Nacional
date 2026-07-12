# -*- coding: utf-8 -*-
"""
main_sudamericana.py

Orquestador de la Copa Sudamericana (Playoffs de Octavos en adelante):
corre una simulación del cuadro real (datos/sudamericana_cuadro.csv),
el Monte Carlo de % por ronda (arranca en Playoffs, no en Octavos como
Libertadores -- ver EstadisticasSudamericana.monte_carlo_sudamericana())
y arma public/data_sudamericana.json, que consume la pestaña "Copa
Sudamericana" de la web -- mismo patrón que main_libertadores.py.
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


def armar_datos_web_sudamericana(e, rondas_detalle, campeon, mc, n_sims):
    equipos_vivos = _equipos_vivos(e)
    return {
        "liga": "Copa Sudamericana",
        "generado": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "n_simulaciones": n_sims,
        "rondas": rondas_detalle,
        "campeon": campeon,
        "monte_carlo": mc,
        "equipos_vivos": equipos_vivos,
    }


def _equipos_vivos(e):
    """Equipos que todavía no perdieron ninguna llave resuelta (dato
    real) -- ni en Playoffs ni de Octavos en adelante. Mismo criterio
    que EstadisticasLibertadores.equipos_vivos() (basado en el campo
    "ganador" real del CSV, no en una corrida simulada), adaptado a
    que acá hay dos cuadros separados (self.cuadro_playoffs +
    self.cuadro) -- ver docstring del módulo.

    Antes esto se calculaba a partir del detalle YA SIMULADO de una
    corrida puntual: con el cuadro actual (Playoffs sin jugar, cero
    resultados reales) esa cuenta siempre colapsaba a 1 solo equipo
    (el campeón al azar de esa corrida) en vez de los 24 participantes
    posibles, dejando inservible el selector "elegí un equipo" del
    botón "Simulá hasta que tu equipo salga campeón"."""
    eliminados = set()
    for cruce in e.cuadro_playoffs:
        if cruce.get("ganador"):
            perdedor = (cruce["equipo_vuelta_local"] if cruce["ganador"] == cruce["equipo_ida_local"]
                        else cruce["equipo_ida_local"])
            eliminados.add(perdedor)
    for cruce in e.cuadro:
        if cruce.get("ganador"):
            perdedor = (cruce["equipo_vuelta_local"] if cruce["ganador"] == cruce["equipo_ida_local"]
                        else cruce["equipo_ida_local"])
            eliminados.add(perdedor)
    participantes = {c["equipo_ida_local"] for c in e.cuadro_playoffs} | \
        {c["equipo_vuelta_local"] for c in e.cuadro_playoffs} | \
        {c["equipo_vuelta_local"] for c in e.cuadro if c["ronda"] == "octavos"}
    return sorted(participantes - eliminados)


def guardar_json_sudamericana(datos_web, ruta=None):
    ruta = ruta or RUTA_JSON_SUDAMERICANA
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos_web, f, ensure_ascii=False, indent=2)
    return str(ruta)


def correr_simulacion_sudamericana(imprimir=True, guardar_json=True, n_sims=1000):
    e = _preparar_motor()

    rondas_detalle, campeon = e.simular_sudamericana()
    mc = e.monte_carlo_sudamericana(n_simulaciones=n_sims)

    datos = armar_datos_web_sudamericana(e, rondas_detalle, campeon, mc, n_sims)

    if imprimir:
        print(f"\nCampeón de la Copa Sudamericana en esta corrida: {campeon}")
    if guardar_json:
        ruta = guardar_json_sudamericana(datos)
        if imprimir:
            print(f"JSON guardado en {ruta}")
    return datos


def simular_hasta_campeon_sudamericana(equipo_objetivo, max_intentos=5000, imprimir=True):
    """Repite el cuadro (Playoffs de Octavos en adelante) hasta que
    `equipo_objetivo` salga campeón. Mismo patrón que
    simular_hasta_campeon_libertadores(), adaptado a que acá hay 24
    participantes posibles (16 de Playoffs + 8 directos a Octavos) en
    vez de los 16 que arrancan directo en Octavos de Libertadores --
    ver docstring del módulo en modelos/estadisticas_sudamericana.py.
    Reusa _equipos_vivos(e) (dato real, no la corrida simulada -- ver
    su docstring) tanto para el universo de participantes como para el
    chequeo de "ya quedó eliminado", igual que Libertadores."""
    e = _preparar_motor()

    participantes = {c["equipo_ida_local"] for c in e.cuadro_playoffs} | \
        {c["equipo_vuelta_local"] for c in e.cuadro_playoffs} | \
        {c["equipo_vuelta_local"] for c in e.cuadro if c["ronda"] == "octavos"}
    if equipo_objetivo not in participantes:
        sugerencias = [n for n in sorted(participantes) if equipo_objetivo.lower() in n.lower()]
        mensaje = f"'{equipo_objetivo}' no juega esta instancia de la Copa Sudamericana."
        if sugerencias:
            mensaje += f" ¿Quisiste decir: {', '.join(sugerencias)}?"
        raise ValueError(mensaje)

    if equipo_objetivo not in _equipos_vivos(e):
        raise ValueError(f"{equipo_objetivo} ya quedó eliminado (dato real): no hay simulación que lo salve.")

    for intento in range(1, max_intentos + 1):
        if imprimir and intento % 500 == 0:
            print(f"...intento {intento}, todavía no salió campeón")
        rondas_detalle, campeon = e.simular_sudamericana()
        if campeon == equipo_objetivo:
            if imprimir:
                print(f"\n¡{equipo_objetivo} CAMPEÓN DE LA COPA SUDAMERICANA! (intento {intento})")
            return {"equipo": equipo_objetivo, "intentos": intento, "rondas": rondas_detalle}

    if imprimir:
        print(f"\nNo salió campeón {equipo_objetivo} en {max_intentos} intentos.")
    return None


if __name__ == "__main__":
    correr_simulacion_sudamericana()
