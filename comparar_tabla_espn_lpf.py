# -*- coding: utf-8 -*-
"""
comparar_tabla_espn_lpf.py

Desde que main_lpf._tabla_actual_clausura() prioriza ESPN como fuente
(ver ese módulo), la tabla que muestra el sitio YA no depende de
resultados_lpf.csv estando completo. Pero resultados_lpf.csv sigue
siendo la fuente real para todo lo demás del motor (rachas, ratings,
ELO, simulación) -- así que si le siguen faltando partidos por la
ventana de Promiedos, ESO sigue siendo un problema real aunque la
tabla visible ya no lo muestre.

Este script compara la reconstrucción vieja (main_lpf.
_tabla_actual_clausura_desde_resultados(), el fallback -- NO la
función con prioridad ESPN) contra la tabla de ESPN, equipo por
equipo, para seguir detectando esos partidos faltantes.

NO escribe nada -- es de solo lectura, pensado para correr después de
actualizar_resultados_lpf.py (que además lo corre solo, ver el punto 8
de ese docstring) y antes de confiar en que el motor de simulación
tiene todos los resultados reales.

Uso:
    python comparar_tabla_espn_lpf.py                     # ESPN en vivo
    python comparar_tabla_espn_lpf.py ruta/al/archivo.json  # ESPN desde un JSON ya guardado
"""
import sys

import data_access
from modelos.estadisticas_lpf import normalizar
from main_lpf import _tabla_actual_clausura_desde_resultados
from scraper_espn_lpf import obtener_tabla_clausura_espn

CAMPOS_COMPARADOS = ["partidos_jugados", "puntos", "gf", "gc", "dg"]


class _DatosLPF:
    """Objeto mínimo con .apertura/.resultados normalizados, el único
    contrato que necesita _tabla_actual_clausura() -- evita instanciar
    EstadisticasLPF completo (que además corre validaciones y prints de
    más para lo que hace falta acá)."""

    def __init__(self):
        self.resultados, self.fixture, self.apertura = data_access.league_data("lpf")
        self.apertura["equipo"] = self.apertura["equipo"].apply(normalizar)
        for col in ["equipo_local", "equipo_visitante"]:
            self.resultados[col] = self.resultados[col].apply(normalizar)


def _tabla_real_como_indice():
    e = _DatosLPF()
    tabla = _tabla_actual_clausura_desde_resultados(e)
    indice = {}
    for zona in ("A", "B"):
        for fila in tabla[zona]:
            indice[fila["equipo"]] = fila
    return indice


def _tabla_espn_como_indice(ruta_json):
    tabla = obtener_tabla_clausura_espn(ruta_json)
    indice = {}
    for zona in ("A", "B"):
        for fila in tabla[zona]:
            indice[fila["equipo"]] = fila
    return indice


def comparar(ruta_json=None):
    real = _tabla_real_como_indice()
    espn = _tabla_espn_como_indice(ruta_json)

    equipos = sorted(set(real) | set(espn))
    diferencias = []

    for equipo in equipos:
        fila_real = real.get(equipo)
        fila_espn = espn.get(equipo)
        if fila_real is None or fila_espn is None:
            diferencias.append((equipo, "falta en " + ("ESPN" if fila_real else "la tabla real"), None, None))
            continue
        for campo in CAMPOS_COMPARADOS:
            if fila_real[campo] != fila_espn[campo]:
                diferencias.append((equipo, campo, fila_real[campo], fila_espn[campo]))

    return diferencias


def formatear_diferencias(diferencias):
    """Arma el texto de aviso (multilínea) para las diferencias que
    devuelve comparar(). Separado de main() para que
    actualizar_resultados_lpf.py pueda reusar exactamente el mismo
    formato al avisar automáticamente."""
    lineas = [f"Se encontraron {len(diferencias)} diferencia(s) entre la tabla real y la de ESPN:",
              "", f"{'Equipo':<28} {'Campo':<18} {'Real':>8} {'ESPN':>8}"]
    for equipo, campo, real, espn in diferencias:
        lineas.append(f"{equipo:<28} {campo:<18} {str(real):>8} {str(espn):>8}")
    lineas.append("")
    lineas.append("Un 'partidos_jugados' de menos en 'Real' suele indicar un partido que se cayó de "
                   "la ventana de Promiedos -- cargalo con cargar_resultado_manual_lpf.py.")
    return "\n".join(lineas)


def main():
    ruta_json = sys.argv[1] if len(sys.argv) > 1 else None
    diferencias = comparar(ruta_json)

    if not diferencias:
        print("OK -- la tabla real (resultados_lpf.csv) coincide exactamente con la de ESPN. "
              "No hay partidos faltantes ni desalineados.")
        return

    print(formatear_diferencias(diferencias))


if __name__ == "__main__":
    main()
