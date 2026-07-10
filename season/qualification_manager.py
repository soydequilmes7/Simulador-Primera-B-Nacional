# -*- coding: utf-8 -*-
"""
season/qualification_manager.py

Etapa 4 del plan (ver PLAN_MODO_TEMPORADA_NACIONAL.txt, sección 4 y 6):
QualificationManager calcula quién clasifica a Copa Libertadores y Copa
Sudamericana, según el reglamento real de AFA:

    Copa Libertadores 2026 (6 cupos):
      Argentina 1: campeón del Torneo Apertura.
      Argentina 2: campeón del Torneo Clausura.
      Argentina 3: campeón de la Copa Argentina.
      Argentina 4/5/6: los mejores ubicados en la Tabla General Anual,
        excluidos los campeones ya clasificados.

    Reglas de cascada:
      - Si el campeón del Apertura también gana el Clausura, el cupo
        Argentina 2 pasa al siguiente mejor ubicado en la tabla anual
        (reordenando el resto de los cupos, Libertadores y Sudamericana,
        para cubrir la totalidad).
      - Si el campeón de Copa Argentina ya clasificó por Apertura o
        Clausura (o no pertenece a Primera División), el cupo Argentina 3
        pasa al siguiente equipo DE PRIMERA mejor ubicado en el propio
        cuadro de Copa Argentina (el finalista perdedor, o si tampoco
        corresponde, el semifinalista perdedor mejor ubicado, etc.).

    Copa Sudamericana 2026 (6 cupos): los 6 siguientes mejor ubicados en
      la tabla anual que no hayan clasificado ya a Libertadores.

    Regla general: todo clasificado a Libertadores o Sudamericana debe
    pertenecer a Primera División al final de la temporada -- un
    campeón (Apertura/Clausura/Copa Argentina) que descienda, o un
    campeón de Copa Argentina que no sea de Primera, no ocupa su cupo
    "especial": ese cupo cascade-a como se describe arriba. Un equipo
    de la tabla anual que haya descendido tampoco ocupa un cupo por
    posición en la tabla.

Fuentes: resultado_lpf (ResultadoTorneo de LPFAdapter, con
datos_crudos["campeon_apertura"/"campeon_clausura"/"tabla_anual"] y
.descensos) y resultado_copa (ResultadoTorneo de CopaAdapter, con
.campeon y datos_crudos["rondas"] para la cascada de Copa Argentina).
"""
from __future__ import annotations

from modelos.estadisticas_copa import RONDAS

CANTIDAD_LIBERTADORES = 6
CANTIDAD_SUDAMERICANA = 6


class QualificationManager:
    def calcular(self, resultado_lpf, resultado_copa) -> dict:
        """Devuelve un dict:
            "libertadores": lista de hasta 6 clubes (Argentina 1..6).
            "sudamericana": lista de hasta 6 clubes.
            "detalle": {"argentina_1": club, "argentina_2": club, ...}
                -- de dónde salió cada cupo especial, para poder
                mostrarlo en el frontend sin adivinar.
            "avisos": strings -- casos raros (cupo no cubierto por
                falta de equipos elegibles, cascadas aplicadas, etc.).
        """
        dc_lpf = resultado_lpf.datos_crudos
        campeon_apertura = dc_lpf.get("campeon_apertura")
        campeon_clausura = dc_lpf.get("campeon_clausura")
        tabla_anual = [fila["equipo"] for fila in dc_lpf.get("tabla_anual", [])]
        descensos_lpf = set(resultado_lpf.descensos)
        # "Pertenece a Primera al final de la temporada" = está en la
        # tabla anual (jugó la temporada en LPF) Y no es uno de los que
        # descienden esta misma temporada.
        primera_al_final = [e for e in tabla_anual if e not in descensos_lpf]
        primera_al_final_set = set(primera_al_final)

        campeon_copa = getattr(resultado_copa, "campeon", None)
        rondas_copa = resultado_copa.datos_crudos.get("rondas", {}) if resultado_copa.datos_crudos else {}

        avisos: list[str] = []
        detalle: dict[str, str] = {}
        libertadores: list[str] = []
        ya_usados: set[str] = set()

        def _agregar(club, etiqueta):
            if not club or club in ya_usados:
                return False
            libertadores.append(club)
            ya_usados.add(club)
            detalle[etiqueta] = club
            return True

        # ---- Argentina 1: campeón del Apertura ----
        if campeon_apertura in primera_al_final_set:
            _agregar(campeon_apertura, "argentina_1")
        elif campeon_apertura:
            avisos.append(
                f"El campeón del Apertura ({campeon_apertura!r}) no pertenece a Primera "
                f"al final de la temporada (descendió) -- no ocupa el cupo Argentina 1, "
                f"cascada a la tabla anual."
            )

        # ---- Argentina 2: campeón del Clausura (salvo que sea el
        # mismo que el Apertura -- ahí cascada a la tabla anual) ----
        if campeon_clausura == campeon_apertura:
            avisos.append(
                f"{campeon_clausura!r} ganó Apertura y Clausura: el cupo Argentina 2 "
                f"pasa al siguiente mejor ubicado de la tabla anual."
            )
        elif campeon_clausura in primera_al_final_set:
            _agregar(campeon_clausura, "argentina_2")
        elif campeon_clausura:
            avisos.append(
                f"El campeón del Clausura ({campeon_clausura!r}) no pertenece a Primera "
                f"al final de la temporada (descendió) -- no ocupa el cupo Argentina 2, "
                f"cascada a la tabla anual."
            )

        # ---- Argentina 3: campeón de Copa Argentina (salvo que ya
        # haya clasificado, o no sea de Primera -- ahí cascada DENTRO
        # del cuadro de Copa Argentina, no a la tabla anual) ----
        if campeon_copa and campeon_copa not in ya_usados and campeon_copa in primera_al_final_set:
            _agregar(campeon_copa, "argentina_3")
        else:
            if campeon_copa in ya_usados:
                avisos.append(
                    f"El campeón de Copa Argentina ({campeon_copa!r}) ya había clasificado "
                    f"por Apertura/Clausura -- el cupo Argentina 3 pasa al siguiente equipo "
                    f"de Primera mejor ubicado en el cuadro de Copa Argentina."
                )
            elif campeon_copa:
                avisos.append(
                    f"El campeón de Copa Argentina ({campeon_copa!r}) no pertenece a Primera "
                    f"-- el cupo Argentina 3 pasa al siguiente equipo de Primera mejor ubicado "
                    f"en el cuadro de Copa Argentina."
                )
            excluir_cascada = set(ya_usados)
            if campeon_copa:
                excluir_cascada.add(campeon_copa)
            siguiente = self._siguiente_de_primera_en_copa(rondas_copa, primera_al_final_set, excluir_cascada)
            if siguiente:
                _agregar(siguiente, "argentina_3_cascada")
            else:
                avisos.append(
                    "No se encontró ningún equipo de Primera disponible en el cuadro de Copa "
                    "Argentina para cubrir el cupo Argentina 3 -- queda sin asignar esta temporada."
                )

        # ---- Argentina 4/5/6: mejor ubicados en la tabla anual,
        # excluyendo a quien ya haya clasificado o haya descendido ----
        for equipo in tabla_anual:
            if len(libertadores) >= CANTIDAD_LIBERTADORES:
                break
            if equipo in ya_usados or equipo in descensos_lpf:
                continue
            _agregar(equipo, f"argentina_{len(libertadores) + 1}")

        if len(libertadores) < CANTIDAD_LIBERTADORES:
            avisos.append(
                f"Solo se pudieron cubrir {len(libertadores)}/{CANTIDAD_LIBERTADORES} cupos "
                f"de Libertadores (no hay suficientes equipos elegibles en la tabla anual)."
            )

        # ---- Sudamericana: los 6 siguientes que no estén ya en Libertadores ----
        sudamericana: list[str] = []
        for equipo in tabla_anual:
            if len(sudamericana) >= CANTIDAD_SUDAMERICANA:
                break
            if equipo in ya_usados or equipo in descensos_lpf:
                continue
            sudamericana.append(equipo)
            ya_usados.add(equipo)

        if len(sudamericana) < CANTIDAD_SUDAMERICANA:
            avisos.append(
                f"Solo se pudieron cubrir {len(sudamericana)}/{CANTIDAD_SUDAMERICANA} cupos "
                f"de Sudamericana (no hay suficientes equipos elegibles en la tabla anual)."
            )

        return {
            "libertadores": libertadores,
            "sudamericana": sudamericana,
            "detalle": detalle,
            "avisos": avisos,
            # Compatibilidad con el shape viejo -- "clasificados" ya no
            # tiene mucho sentido como concepto único (Libertadores y
            # Sudamericana son cupos distintos), se deja como la unión
            # de las dos por si algo todavía lo lee así.
            "clasificados": libertadores + sudamericana,
        }

    @staticmethod
    def _siguiente_de_primera_en_copa(rondas, primera_al_final, excluir):
        """Busca, empezando por la final y retrocediendo ronda por
        ronda (semis, cuartos, ...), el primer equipo DE PRIMERA que
        haya perdido en esa instancia y no esté ya excluido. Perder en
        una instancia más avanzada del cuadro = mejor ubicado, por eso
        se recorre en ese orden (RONDAS ya viene ordenada de 32avos a
        final; acá se usa invertida)."""
        for ronda in reversed(RONDAS):
            partidos = rondas.get(ronda) or []
            for partido in partidos:
                local, visitante = partido.get("local"), partido.get("visitante")
                avanza = partido.get("avanza")
                perdedor = visitante if avanza == local else local
                if perdedor and perdedor in primera_al_final and perdedor not in excluir:
                    return perdedor
        return None
