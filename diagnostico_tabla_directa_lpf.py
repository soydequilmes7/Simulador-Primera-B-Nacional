# -*- coding: utf-8 -*-
"""
diagnostico_tabla_directa_lpf.py

Pablo preguntó: en vez de reconstruir la tabla actual del Clausura
sumando partido por partido (limitado por la ventana de ~100 "últimos"
de Promiedos), ¿no se puede pedir directamente la tabla de posiciones
ya armada, como la que se ve en la web de Promiedos?

Ya se sabía que /league/tables_and_fixtures/{LEAGUE_ID} viene con
"games.filters" vacío para LPF (ver scraper_promiedos_lpf.py) -- pero
eso solo se chequeó buscando fechas navegables (games.filters). Nunca
se miró si esa MISMA respuesta trae, en otra clave (por ejemplo
"tables" o "standings"), la tabla de posiciones ya calculada por
Promiedos. Este script pide ese endpoint y vuelca TODAS las claves de
primer nivel de la respuesta, más un vistazo a cualquier clave que
suene a tabla/standings, para confirmar si hay algo ahí aprovechable.

También prueba un par de variantes de endpoint que a veces existen en
APIs de Promiedos para otras ligas (standings/table), por las dudas.

No modifica nada -- solo imprime. No hace falta SUPABASE_DB_URL (no
toca la base de datos).

Uso:
    python diagnostico_tabla_directa_lpf.py
"""
import json

from scraper_promiedos_lpf import BASE_URL, LEAGUE_ID, _get_json


def _resumen(data, nombre):
    print(f"\n=== {nombre} ===")
    if data is None:
        print("  (falló, ver error arriba)")
        return
    if not isinstance(data, dict):
        print(f"  Respuesta no es un dict: {type(data)}")
        return
    print(f"  Claves de primer nivel: {list(data.keys())}")
    for clave in data.keys():
        if any(palabra in clave.lower() for palabra in ("table", "standing", "posic", "tabla")):
            print(f"\n  --- Contenido de '{clave}' (pinta a tabla de posiciones) ---")
            print(json.dumps(data[clave], ensure_ascii=False, indent=2)[:3000])


def _probar(path, nombre):
    try:
        data = _get_json(path)
        _resumen(data, nombre)
        return data
    except Exception as e:
        print(f"\n=== {nombre} ===\n  ERROR: {e}")
        return None


if __name__ == "__main__":
    print(f"Liga: {LEAGUE_ID} ({BASE_URL})")

    data_tf = _probar(f"/league/tables_and_fixtures/{LEAGUE_ID}", f"/league/tables_and_fixtures/{LEAGUE_ID}")

    # Variantes que a veces existen en la API de Promiedos para otras
    # ligas -- probamos por las dudas, cada una en un try/except propio
    # para que un 404 no frene a las demás.
    for variante in ["table", "tables", "standing", "standings"]:
        _probar(f"/league/{variante}/{LEAGUE_ID}", f"/league/{variante}/{LEAGUE_ID}")

    print("\n\nSi ninguna de las de arriba mostró una tabla de posiciones real, "
          "confirmamos que no hay atajo -- toca seguir por partido a partido. "
          "Si SÍ apareció algo en 'tables_and_fixtures' bajo alguna clave nueva, "
          "avisame el contenido y armamos un scraper de tabla directa para LPF.")
