# -*- coding: utf-8 -*-
"""
manager_mode/exportar_datos_frontend.py

Exporta el catálogo REAL de eventos (manager_mode/eventos.py) y el banco
narrativo (manager_mode/narrativa.py) a un JSON estático que consume
public/modo-dt.html. Fuente de verdad única: el frontend de Modo DT no
tiene API todavía (Fase 4 del plan, no arrancó), así que en vez de
duplicar a mano el catálogo en JS -- como se hizo con el pool de clubes
de arranque, que sí es chico -- para los 51 eventos exportamos el
catálogo Python tal cual.

Uso:
    python -m manager_mode.exportar_datos_frontend

Hay que volver a correrlo cada vez que cambie eventos.py o narrativa.py
-- el JSON generado es un snapshot, no se regenera solo.
"""
from __future__ import annotations

import json

import rutas
from manager_mode.eventos import CATALOGO_EVENTOS
from manager_mode.narrativa import BANCO_PORTADAS, BANCO_REACCIONES


def _exportar_eventos() -> list[dict]:
    eventos = []
    for evento in CATALOGO_EVENTOS.values():
        eventos.append({
            "codigo": evento.codigo,
            "categoria": evento.categoria.value,
            "titulo": evento.titulo,
            "descripcion": evento.descripcion,
            "opciones": [
                {
                    "codigo": opcion.codigo,
                    "texto": opcion.texto,
                    "intensidad": opcion.intensidad.value,
                    "tipoReaccion": opcion.tipo_reaccion.value if opcion.tipo_reaccion else None,
                    "efectos": [
                        {"variable": efecto.variable, "delta": efecto.delta}
                        for efecto in opcion.efectos
                    ],
                }
                for opcion in evento.opciones
            ],
        })
    return eventos


def _exportar_reacciones() -> dict[str, list[str]]:
    # Clave "tipo|intensidad" (ej. "prensa|positiva") -- JSON no admite
    # tuplas como clave, así que aplanamos el dict[(TipoReaccion,
    # Intensidad), list[str]] de BANCO_REACCIONES a string.
    return {
        f"{tipo.value}|{intensidad.value}": frases
        for (tipo, intensidad), frases in BANCO_REACCIONES.items()
    }


def _exportar_portadas() -> dict[str, list[str]]:
    return {intensidad.value: frases for intensidad, frases in BANCO_PORTADAS.items()}


def exportar() -> dict:
    return {
        "eventos": _exportar_eventos(),
        "reacciones": _exportar_reacciones(),
        "portadas": _exportar_portadas(),
    }


if __name__ == "__main__":
    datos = exportar()
    destino = rutas.public_dir() / "data_manager_mode.json"
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    print(f"Exportados {len(datos['eventos'])} eventos, "
          f"{len(datos['reacciones'])} combinaciones de reacción y "
          f"{len(datos['portadas'])} bancos de portada -> {destino}")
