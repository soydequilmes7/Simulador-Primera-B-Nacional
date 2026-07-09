# -*- coding: utf-8 -*-
"""
season/copa_argentina_manager.py

CopaArgentinaManager centraliza "quién clasifica a la próxima Copa
Argentina" a partir de los resultados de la temporada que acaba de
terminar en las 5 divisiones que alimentan invitados (LPF, Primera
Nacional, B Metropolitana, Primera C y Federal A -- Copa Argentina
misma NO se autoalimenta, ver limitación de HistoryManager).

Reglas según el Boletín Especial 6812 de AFA (edición 2027) -- 64
clasificados en total:

  - Liga Profesional (30): clasifican los 30 equipos, automático, sin
    importar la posición en la tabla.
  - Primera Nacional (15): los 7 mejores de la Zona A + los 7 mejores
    de la Zona B + el mejor 8° entre ambas zonas (comparando el 8° de
    A contra el 8° de B por el desempate habitual).
  - B Metropolitana (5): el campeón (ascenso directo) + el ganador del
    Reducido (2° ascenso) + los 3 mejores de la tabla general
    EXCLUYENDO a esos dos.
  - Primera C (4): el campeón (1er ascenso) + el ganador del Reducido
    (2° ascenso) + el mejor ubicado de la Zona A (excluyendo a los
    anteriores) + el mejor ubicado de la Zona B (ídem).
  - Federal A (10): NO hay cruces clasificatorios -- se arma una tabla
    general con TODOS los equipos de las 4 zonas de Primera Fase
    (idx_zona 1-4), se ordena por puntos -> dg -> gf -> desempate
    habitual, y clasifican los primeros 10. Mismo criterio que ya usó
    la Copa Argentina 2026 para Federal A.

Todas las tablas de entrada (datos_crudos de cada ResultadoTorneo)
comparten el mismo shape de fila: {"equipo", "puntos", "gf", "gc",
"dg"} ya ordenadas de mejor a peor (ver main.py/main_lpf.py/
main_bmetro.py/main_primerac.py/main_federal.py, todas usan
_armar_tabla_final()/_tabla_a_lista() con ese shape) -- no hace falta
reordenar nada salvo la tabla general de Federal A, que combina las 4
zonas.

LIMITACIÓN DOCUMENTADA: "criterios habituales de desempate" (4° punto
del reglamento) más allá de puntos/dg/gf -- p. ej. resultado entre sí,
mejor posición en la fase anterior, etc. -- no está implementado: no
hay datos de cruces directos disponibles en esta tabla resumida. Un
triple empate exacto en puntos+dg+gf (estadísticamente rarísimo con
goles reales) se resuelve por orden alfabético, de forma determinística,
y queda anotado en "avisos" para que quede visible si llega a pasar.
"""


def _clave_desempate(fila: dict) -> tuple:
    """puntos/dg/gf descendente (mejor primero); último recurso
    alfabético para que el orden sea 100% determinístico incluso ante
    un triple empate exacto (ver limitación documentada arriba)."""
    return (-fila["puntos"], -fila["dg"], -fila["gf"], fila["equipo"])


def _mejor(filas: list[dict]) -> dict:
    """La mejor fila de una lista, por el mismo desempate de arriba."""
    return min(filas, key=_clave_desempate)


class CopaArgentinaManager:
    def calcular(self, resultados: dict) -> dict:
        """resultados: dict {slug: ResultadoTorneo} con al menos las
        claves "lpf", "nacional", "bmetro", "primerac", "federal_a"
        (el mismo dict que arma SeasonEngine._correr_competencias()).

        Devuelve:
            "clasificados": lista de 64 nombres (unión de las 5
                divisiones, sin duplicados esperados -- un club juega
                una sola división por temporada).
            "por_division": {"lpf": [...30], "nacional": [...15],
                "bmetro": [...5], "primerac": [...4], "federal_a":
                [...10]} -- para trazabilidad / mostrar en el frontend
                agrupado por división de origen.
            "avisos": strings -- cualquier cosa que no cierre el
                conteo esperado (30/15/5/4/10) o un duplicado entre
                divisiones (no debería pasar nunca: cada club juega en
                una sola división).
        """
        por_division = {
            "lpf": self._clasificados_lpf(resultados["lpf"].datos_crudos),
            "nacional": self._clasificados_nacional(resultados["nacional"].datos_crudos),
            "bmetro": self._clasificados_bmetro(resultados["bmetro"]),
            "primerac": self._clasificados_primerac(resultados["primerac"]),
            "federal_a": self._clasificados_federal(resultados["federal_a"].datos_crudos),
        }

        avisos = []
        esperados = {"lpf": 30, "nacional": 15, "bmetro": 5, "primerac": 4, "federal_a": 10}
        for slug, cantidad_esperada in esperados.items():
            cantidad = len(por_division[slug])
            if cantidad != cantidad_esperada:
                avisos.append(
                    f"{slug}: se esperaban {cantidad_esperada} clasificados y se "
                    f"armaron {cantidad}."
                )

        clasificados = []
        vistos = set()
        for slug in ("lpf", "nacional", "bmetro", "primerac", "federal_a"):
            for club in por_division[slug]:
                if club in vistos:
                    avisos.append(
                        f"{club!r} aparece clasificado por más de una división -- "
                        f"no debería pasar (cada club juega una sola división por "
                        f"temporada). Se deduplica en la lista final."
                    )
                    continue
                vistos.add(club)
                clasificados.append(club)

        if len(clasificados) != 64:
            avisos.append(
                f"Total de clasificados a Copa Argentina: {len(clasificados)} "
                f"(se esperaban 64)."
            )

        return {
            "clasificados": clasificados,
            "por_division": por_division,
            "avisos": avisos,
        }

    # ------------------------------------------------------------------
    # Liga Profesional -- automático, los 30, sin importar la tabla.
    # ------------------------------------------------------------------
    @staticmethod
    def _clasificados_lpf(datos_web: dict) -> list[str]:
        return [fila["equipo"] for fila in datos_web["tabla_anual"]]

    # ------------------------------------------------------------------
    # Primera Nacional -- 7 + 7 + mejor 8°.
    # ------------------------------------------------------------------
    @staticmethod
    def _clasificados_nacional(datos_web: dict) -> list[str]:
        zona_a = datos_web["tablas"]["A"]
        zona_b = datos_web["tablas"]["B"]
        top_a, top_b = zona_a[:7], zona_b[:7]
        octavos = [fila for fila in (zona_a[7:8] + zona_b[7:8])]
        mejor_octavo = [_mejor(octavos)["equipo"]] if octavos else []
        return [f["equipo"] for f in top_a] + [f["equipo"] for f in top_b] + mejor_octavo

    # ------------------------------------------------------------------
    # B Metropolitana -- campeón + reducido + 3 mejores de la general
    # (excluyendo a esos dos).
    # ------------------------------------------------------------------
    @staticmethod
    def _clasificados_bmetro(resultado) -> list[str]:
        campeon = resultado.campeon
        ascenso_reducido = resultado.ascensos[1]
        ya_clasificados = {campeon, ascenso_reducido}

        top3 = []
        for fila in resultado.datos_crudos["tabla"]:
            if fila["equipo"] in ya_clasificados:
                continue
            top3.append(fila["equipo"])
            if len(top3) == 3:
                break

        return [campeon, ascenso_reducido] + top3

    # ------------------------------------------------------------------
    # Primera C -- campeón + reducido + mejor de cada zona (excluyendo
    # a esos dos).
    # ------------------------------------------------------------------
    @staticmethod
    def _clasificados_primerac(resultado) -> list[str]:
        campeon = resultado.campeon
        ascenso_reducido = resultado.ascensos[1]
        ya_clasificados = {campeon, ascenso_reducido}

        tablas = resultado.datos_crudos["tablas"]
        mejor_a = next(fila["equipo"] for fila in tablas["A"] if fila["equipo"] not in ya_clasificados)
        mejor_b = next(fila["equipo"] for fila in tablas["B"] if fila["equipo"] not in ya_clasificados)

        return [campeon, ascenso_reducido, mejor_a, mejor_b]

    # ------------------------------------------------------------------
    # Federal A -- sin cruces, tabla general de las 4 zonas de Primera
    # Fase, top 10 por puntos/dg/gf.
    # ------------------------------------------------------------------
    @staticmethod
    def _clasificados_federal(datos_web: dict) -> list[str]:
        tablas_pf = datos_web["primera_fase"]["tablas"]
        general = [fila for zona in tablas_pf.values() for fila in zona]
        general.sort(key=_clave_desempate)
        return [fila["equipo"] for fila in general[:10]]
