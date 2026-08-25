# -*- coding: utf-8 -*-
"""
subir_tabla_espn_lpf.py

Trae la tabla del Clausura de LPF desde ESPN (scraper_espn_lpf.py) y la
sube a Supabase (data_access.guardar_tabla_espn_lpf()), para que
main_lpf._tabla_actual_clausura() la use en vez de reconstruirla desde
resultados_lpf.csv.

⚠️ ESTE SCRIPT TIENE QUE CORRER DESDE TU PC, NO DESDE RENDER.
Confirmado real (25/08/2026): ESPN le devuelve 403 Forbidden al
tráfico que sale desde el rango de IP de datacenter de Render, headers
de navegador aparte (ver scraper_espn_lpf.py -- el mismo pedido, mismos
headers, funciona corriendo local y falla corriendo en el server). Por
eso el flujo quedó separado en dos partes:

  1. Este script (subir_tabla_espn_lpf.py) -- corre en tu PC, le pega a
     ESPN (que a vos sí te deja pasar) y deja el resultado en Supabase.
  2. main_lpf._tabla_actual_clausura() -- corre en Render, lee lo que
     este script dejó en Supabase. Nunca le pega a ESPN directo.

Si este script deja de correrse por más de 48hs (ver
UMBRAL_HORAS_SNAPSHOT_ESPN en main_lpf.py), la tabla cae sola al
fallback de siempre (reconstruida desde resultados_lpf.csv) -- no
rompe nada, simplemente deja de estar tan al día.

Uso manual:
    python subir_tabla_espn_lpf.py

Para dejarlo automático con el Programador de tareas de Windows: una
corrida cada 1-3 horas alcanza y sobra (el margen de 48hs perdona
sobra que se salte alguna). Mismo patrón que ya usás para el pipeline
de YouTube -- acordate de setear SUPABASE_DB_URL en el entorno de la
tarea programada (no se hereda solo de tu sesión de PowerShell).
"""
from datetime import datetime

import data_access
from scraper_espn_lpf import obtener_tabla_clausura_espn


def main():
    ahora = datetime.now().isoformat(timespec="seconds")
    print(f"[{ahora}] Pidiendo la tabla del Clausura a ESPN...")

    try:
        tabla = obtener_tabla_clausura_espn()
    except Exception as e:
        print(f"ERROR -- no se pudo traer la tabla de ESPN: {e}")
        raise SystemExit(1)

    data_access.guardar_tabla_espn_lpf(tabla)

    total = len(tabla["A"]) + len(tabla["B"])
    print(f"OK -- snapshot subido a Supabase ({total} equipos, Zona A + Zona B). "
          f"main_lpf._tabla_actual_clausura() lo va a usar en la próxima simulación.")


if __name__ == "__main__":
    main()
