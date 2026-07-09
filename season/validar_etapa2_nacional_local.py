# -*- coding: utf-8 -*-
"""
season/validar_etapa2_nacional_local.py

Versión LOCAL de la validación de Etapa 2 (NacionalAdapter). Igual
espíritu que validar_etapa0_local.py: evita depender de
SUPABASE_DB_URL / db.repository, parcheando data_access.league_data()
para que lea los CSV de datos/ directo con pandas.

IMPORTANTE -- esto es SOLO para la corrida de validación:
  - No se toca main.py, modelos/estadisticas.py, ni data_access.py.
  - El parche se aplica ANTES de llamar a
    NacionalAdapter().run(), sobre el módulo data_access ya importado
    (estadisticas.py hace data_access.league_data(...), así que
    alcanza con reemplazar el atributo del módulo).
  - En un backend real (o en Pyodide) esto NO se usa -- ahí
    data_access.league_data() sigue yendo por su camino normal
    (Supabase o CSV vía Pyodide, según usando_pyodide()).

RUTAS ASUMIDAS (mismo patrón sin sufijo que usa datos/tabla.csv en
validar_etapa0_local.py, porque Nacional es la liga "default"; ver
PLAN_MODO_TEMPORADA_NACIONAL.txt): si tu repo usa otros nombres,
ajustá las tres constantes de abajo, es lo único que hace falta tocar.

    RESULTADOS_CSV = "datos/resultados.csv"
    FIXTURE_CSV    = "datos/fixture.csv"
    TABLA_CSV      = "datos/tabla.csv"

Correrlo desde la raíz del proyecto:

    python -m season.validar_etapa2_nacional_local
"""
import pandas as pd

RESULTADOS_CSV = "datos/resultados.csv"
FIXTURE_CSV = "datos/fixture.csv"
TABLA_CSV = "datos/tabla.csv"


def _league_data_local(competition_slug):
    """Reemplazo local de data_access.league_data(). Ignora
    competition_slug (este script es específico para Nacional) y lee
    los 3 CSV directo, devolviendo el mismo shape (resultados, fixture,
    tabla) que espera Estadisticas.cargar_datos()."""
    resultados = pd.read_csv(RESULTADOS_CSV, encoding="utf-8")
    fixture = pd.read_csv(FIXTURE_CSV, encoding="utf-8")
    tabla = pd.read_csv(TABLA_CSV, encoding="utf-8")
    return resultados, fixture, tabla


def _parchear_data_access():
    import data_access
    data_access.league_data = _league_data_local
    print(f"[validación local] data_access.league_data() parcheado para leer:")
    print(f"  resultados: {RESULTADOS_CSV}")
    print(f"  fixture:    {FIXTURE_CSV}")
    print(f"  tabla:      {TABLA_CSV}")


def main():
    print("=" * 70)
    print("VALIDACIÓN ETAPA 2 (LOCAL, sin Supabase) -- NacionalAdapter")
    print("=" * 70)

    try:
        _parchear_data_access()
    except FileNotFoundError as e:
        print(f"\n❌ No encontré uno de los CSV esperados: {e}")
        print(
            "Ajustá RESULTADOS_CSV / FIXTURE_CSV / TABLA_CSV al inicio de este "
            "archivo si tus nombres reales son distintos."
        )
        return

    # Import DESPUÉS del parche, aunque no es estrictamente necesario acá
    # (estadisticas.py resuelve data_access.league_data en tiempo de
    # llamada, no en tiempo de import) -- se deja explícito para que el
    # orden quede claro y no dependa de un detalle de implementación.
    from season.adapters.nacional_adapter import (
        NacionalAdapter, _extraer_campeon_reducido, _extraer_descendidos,
    )

    adapter = NacionalAdapter()
    adapter.setup()
    print("\nCorriendo main.correr_simulacion() a través del adaptador (datos locales)...")
    adapter.run(n_sims=1000)
    resultado = adapter.result()

    datos_web = resultado.datos_crudos

    ganador_manual = datos_web["final_ascenso"]["ganador"]
    campeon_reducido_manual = _extraer_campeon_reducido(datos_web["reducido"])
    descensos_manual = _extraer_descendidos(datos_web["tablas"])

    print(f"\nGanador final_ascenso (manual):     {ganador_manual}")
    print(f"Campeón reducido (manual):           {campeon_reducido_manual}")
    print(f"Descensos (manual, últimos 2 x zona): {descensos_manual}")
    print(f"\nresult().campeon:                    {resultado.campeon}")
    print(f"result().ascensos:                    {resultado.ascensos}")
    print(f"result().descensos:                   {resultado.descensos}")
    print(f"result().clasificados_copa:           {resultado.clasificados_copa}")

    errores = []
    if resultado.campeon != ganador_manual:
        errores.append(
            f"campeon: adaptador dio '{resultado.campeon}', manual dio '{ganador_manual}'"
        )
    if resultado.ascensos != [ganador_manual, campeon_reducido_manual]:
        errores.append(
            f"ascensos: adaptador dio {resultado.ascensos}, "
            f"manual dio {[ganador_manual, campeon_reducido_manual]}"
        )
    if resultado.descensos != descensos_manual:
        errores.append(
            f"descensos: adaptador dio {resultado.descensos}, manual dio {descensos_manual}"
        )
    if resultado.clasificados_copa != []:
        errores.append(f"clasificados_copa: esperaba [], adaptador dio {resultado.clasificados_copa}")

    print("\n" + "=" * 70)
    if errores:
        print("❌ El adaptador NO coincide con el mapeo manual:")
        for e in errores:
            print(f"   - {e}")
    else:
        print("✅ El adaptador coincide exactamente con el mapeo manual (datos locales).")
        print("   NacionalAdapter queda validado para esta corrida.")
        print(
            "\n   Nota: esta corrida usó CSV locales, no Supabase. Cuando tengas "
            "acceso a una conexión real (dev o producción), no está de más correr "
            "también validar_etapa2_nacional.py para confirmar contra los datos "
            "que realmente sirve el backend."
        )
    print("=" * 70)


if __name__ == "__main__":
    main()
