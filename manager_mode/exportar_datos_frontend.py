# -*- coding: utf-8 -*-
"""
manager_mode/exportar_datos_frontend.py

Exporta el catálogo REAL de eventos (manager_mode/eventos.py), el banco
narrativo (manager_mode/narrativa.py) y el catálogo de clubes/objetivos/
diálogos de continuidad (manager_mode/dirigencia.py,
manager_mode/ofertas.py) a un JSON estático que consume
public/modo-dt.html. Fuente de verdad única: el frontend de Modo DT no
tiene API todavía (Fase 4 del plan, no arrancó), así que en vez de
duplicar a mano el catálogo en JS -- como se hizo con el pool de clubes
de arranque, que sí es chico -- para los eventos/clubes/diálogos
exportamos el catálogo Python tal cual.

Uso:
    python -m manager_mode.exportar_datos_frontend

Hay que volver a correrlo cada vez que cambie eventos.py, narrativa.py,
dirigencia.py u ofertas.py -- el JSON generado es un snapshot, no se
regenera solo.
"""
from __future__ import annotations

import json

import rutas
from manager_mode.dirigencia import (
    BANCO_CONTINUIDAD,
    BANCO_DECISION_DT,
    CATALOGO_PERFILES_CLUB,
    DESCRIPCION_OBJETIVO,
)
from manager_mode.eventos import CATALOGO_EVENTOS
from manager_mode.narrativa import BANCO_PORTADAS, BANCO_REACCIONES
from manager_mode.ofertas import FACTOR_RAREZA_SELECCION, UMBRAL_REPUTACION_SELECCION


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


def _exportar_clubes() -> list[dict]:
    # Catálogo completo (16 clubes + Selección) de manager_mode/dirigencia.py.
    # El frontend filtra por división (arranque vs. ofertas de fin de
    # temporada) y pondera por reputación -- ver generar_pool_ofertas()/
    # generar_ofertas_iniciales() de manager_mode/ofertas.py, portados a
    # JS en public/modo-dt.html.
    return [
        {
            "nombre": perfil.nombre,
            "escudo": perfil.escudo,
            "division": perfil.division,
            "exigencia": perfil.exigencia,
            "esSeleccion": perfil.es_seleccion,
            "clasificaLibertadores": perfil.clasifica_libertadores,
            "clasificaSudamericana": perfil.clasifica_sudamericana,
            "objetivosPosibles": [tipo.value for tipo in perfil.objetivos_posibles],
        }
        for perfil in CATALOGO_PERFILES_CLUB.values()
    ]


def _exportar_descripcion_objetivo() -> dict[str, str]:
    return {tipo.value: descripcion for tipo, descripcion in DESCRIPCION_OBJETIVO.items()}


def _exportar_continuidad() -> dict[str, list[str]]:
    return {decision.value: frases for decision, frases in BANCO_CONTINUIDAD.items()}


def _exportar_decision_dt() -> dict[str, list[str]]:
    return {decision.value: frases for decision, frases in BANCO_DECISION_DT.items()}


def exportar() -> dict:
    return {
        "eventos": _exportar_eventos(),
        "reacciones": _exportar_reacciones(),
        "portadas": _exportar_portadas(),
        "clubes": _exportar_clubes(),
        "descripcionObjetivo": _exportar_descripcion_objetivo(),
        "continuidad": _exportar_continuidad(),
        "decisionDT": _exportar_decision_dt(),
        "umbralReputacionSeleccion": UMBRAL_REPUTACION_SELECCION,
        "factorRarezaSeleccion": FACTOR_RAREZA_SELECCION,
    }


if __name__ == "__main__":
    datos = exportar()
    destino = rutas.public_dir() / "data_manager_mode.json"
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    print(f"Exportados {len(datos['eventos'])} eventos, "
          f"{len(datos['reacciones'])} combinaciones de reacción, "
          f"{len(datos['portadas'])} bancos de portada, "
          f"{len(datos['clubes'])} clubes/objetivos y "
          f"{len(datos['continuidad'])} + {len(datos['decisionDT'])} bancos de continuidad "
          f"-> {destino}")
