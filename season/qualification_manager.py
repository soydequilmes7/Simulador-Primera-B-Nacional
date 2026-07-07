# -*- coding: utf-8 -*-
"""
season/qualification_manager.py

Etapa 4 del plan (ver PLAN_MODO_TEMPORADA_NACIONAL.txt, sección 4 y
6): QualificationManager centraliza "quién clasifica a Libertadores/
Sudamericana", hoy calculado en dos lugares separados:

    - calcular_copas() de estadisticas_lpf.py (ya arma
      libertadores_2027/sudamericana_2027 a partir de la tabla de LPF)
    - el campeón de Copa Argentina (main_copa.py), que por reglamento
      real de AFA clasifica a Copa Libertadores.

Por diseño de la Etapa 4, esto se prueba CONTRA MOCKS -- objetos con
.clasificados_copa (típicamente ResultadoTorneo, ver
season/tournament_adapter.py), no contra LPFAdapter/CopaAdapter reales
corriendo simulaciones.

--------------------------------------------------------------------
LIMITACIÓN DOCUMENTADA: NO HAY CASCADA DE CUPOS
--------------------------------------------------------------------
En el reglamento real de AFA, si el campeón de Copa Argentina YA
clasificó a una copa internacional por su posición en la tabla de
LPF, ese cupo de Copa Argentina se libera y pasa al SIGUIENTE equipo
mejor ubicado en la tabla de LPF que todavía no haya clasificado
("cascada de cupos").

Este módulo NO resuelve esa cascada. Motivo concreto: ResultadoTorneo.
clasificados_copa (tal como está definido en el plan, sección 4) es
una lista PLANA de nombres, sin el orden de tabla de LPF necesario
para saber "quién sigue" si se libera un cupo. Resolver esto bien
necesitaría acceso a la tabla completa de LPF (vía datos_crudos del
ResultadoTorneo, si el adaptador lo expone) -- no confirmado todavía
contra season/adapters/lpf_adapter.py real.

Por ahora: si hay solapamiento (mismo club clasifica por LPF y por
Copa), este módulo lo detecta, lo deduplica en la lista final (un
club no aparece dos veces) y deja un aviso explícito -- no inventa un
cupo extra para nadie. Si más adelante hace falta la cascada real,
hay que extender esto con la tabla de LPF como input adicional.
"""


class QualificationManager:
    def calcular(self, resultado_lpf, resultado_copa) -> dict:
        """
        resultado_lpf, resultado_copa: objetos con atributo
            .clasificados_copa (lista de nombres de club) --
            típicamente ResultadoTorneo de LPFAdapter/CopaAdapter, o
            cualquier mock con ese atributo (ver
            season/validar_etapa4_qualification.py).

        Devuelve un dict:
            "clasificados": lista deduplicada de todos los clubes que
                clasifican a copas internacionales esta temporada
                (unión de LPF + Copa, orden estable: primero LPF,
                después Copa, sin repetidos).
            "por_lpf": lista tal cual vino de resultado_lpf (para
                trazabilidad).
            "por_copa": lista tal cual vino de resultado_copa (para
                trazabilidad).
            "avisos": strings -- solapamientos detectados (ver
                limitación documentada arriba) y cualquier otra cosa
                rara (ej. clasificados_copa vacío en LPF, lo cual
                sería sospechoso pero no es un error).
        """
        por_lpf = list(resultado_lpf.clasificados_copa)
        por_copa = list(resultado_copa.clasificados_copa)

        avisos = []

        if not por_lpf:
            avisos.append(
                "resultado_lpf.clasificados_copa vino vacío -- revisar si "
                "LPFAdapter corrió calcular_copas() correctamente, LPF "
                "siempre debería aportar clasificados."
            )

        solapados = set(por_lpf) & set(por_copa)
        for club in sorted(solapados):
            avisos.append(
                f"{club!r} clasifica tanto por LPF como por Copa Argentina. "
                f"Por reglamento real esto liberaría un cupo adicional para "
                f"el siguiente equipo de la tabla de LPF ('cascada de "
                f"cupos'), pero este módulo no tiene el orden de tabla "
                f"necesario para resolverlo -- se deduplica sin generar "
                f"cupo extra (limitación documentada, ver docstring del "
                f"módulo)."
            )

        clasificados = []
        for club in por_lpf + por_copa:
            if club not in clasificados:
                clasificados.append(club)

        return {
            "clasificados": clasificados,
            "por_lpf": por_lpf,
            "por_copa": por_copa,
            "avisos": avisos,
        }
