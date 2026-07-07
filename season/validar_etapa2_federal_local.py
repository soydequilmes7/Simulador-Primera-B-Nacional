# -*- coding: utf-8 -*-
"""
season/validar_etapa2_federal_local.py

Versión LOCAL de la validación de Etapa 2 (FederalAdapter). Mismo
espíritu que validar_etapa2_bmetro_local.py: evita depender de
SUPABASE_DB_URL, parcheando data_access ANTES de llamar a
FederalAdapter().run().

Confirmado leyendo estadisticas_federal.py (no supuesto):
cargar_datos_federal() llama a UNA sola función de data_access --
data_access.league_data("federal_a") -- que devuelve (resultados,
fixture, tabla). No hay una segunda función tipo
lpf_average_history_df() para Federal A.

IMPORTANTE -- esto es SOLO para la corrida de validación: no se toca
main_federal.py, modelos/estadisticas_federal.py, ni data_access.py.
El parche se aplica sobre el módulo data_access ya importado,
confiando en que estadisticas_federal.py hace
data_access.league_data(...) (atributo del módulo, resuelto en tiempo
de llamada) y no "from data_access import ...".

NOTA sobre la TABLA: a diferencia de LPF/Nacional/BMetro, la tabla del
Federal A tiene 4 zonas (columna "zona", ver
EstadisticasFederal.cargar_datos_federal(): self.tabla["zona"] =
self.tabla["zona"].astype(str)). El CSV de tabla debe traer esa
columna poblada con las 4 zonas reales, o crear_equipos_federal()
va a fallar al agrupar.

RUTAS CONFIRMADAS por el usuario (dir datos | findstr federal):

    RESULTADOS_CSV = "datos/resultados_federal_a.csv"
    FIXTURE_CSV    = "datos/fixture_federal_a.csv"
    TABLA_CSV      = "datos/tabla_federal_a.csv"

Correrlo desde la raíz del proyecto:

    python -m season.validar_etapa2_federal_local
"""
import pandas as pd

RESULTADOS_CSV = "datos/resultados_federal_a.csv"
FIXTURE_CSV = "datos/fixture_federal_a.csv"
TABLA_CSV = "datos/tabla_federal_a.csv"


def _league_data_local(competition_slug):
    """Reemplazo local de data_access.league_data("federal_a").
    Devuelve (resultados, fixture, tabla) -- mismo shape que espera
    EstadisticasFederal.cargar_datos_federal()."""
    resultados = pd.read_csv(RESULTADOS_CSV, encoding="utf-8")
    fixture = pd.read_csv(FIXTURE_CSV, encoding="utf-8")
    tabla = pd.read_csv(TABLA_CSV, encoding="utf-8")
    return resultados, fixture, tabla


def _parchear_data_access():
    import data_access
    data_access.league_data = _league_data_local
    print("[validación local] data_access parcheado (Federal A) para leer:")
    print(f"  resultados: {RESULTADOS_CSV}")
    print(f"  fixture:    {FIXTURE_CSV}")
    print(f"  tabla:      {TABLA_CSV}")


def main():
    print("=" * 70)
    print("VALIDACIÓN ETAPA 2 (LOCAL, sin Supabase) -- FederalAdapter")
    print("=" * 70)

    try:
        _parchear_data_access()
    except FileNotFoundError as e:
        print(f"\n❌ No encontré uno de los CSV esperados: {e}")
        print(
            "Ajustá RESULTADOS_CSV / FIXTURE_CSV / TABLA_CSV al inicio de "
            "este archivo si tus nombres reales son distintos."
        )
        return

    from season.adapters.federal_adapter import FederalAdapter

    adapter = FederalAdapter()
    adapter.setup()
    print("\nCorriendo main_federal.correr_simulacion_federal() a través del adaptador (datos locales)...")
    print("(el motor Federal A es el más pesado de los 6 -- puede tardar un rato)")
    adapter.run(n_sims=300)
    resultado = adapter.result()

    datos_web = resultado.datos_crudos

    ascenso_1_manual = datos_web["camino_principal"]["ascenso_1"]
    ascenso_2_manual = datos_web["revalida"]["ascenso_2"]
    descensos_manual = datos_web["revalida"]["descensos"]

    print(f"\ncamino_principal.ascenso_1 (manual): {ascenso_1_manual}")
    print(f"revalida.ascenso_2 (manual):          {ascenso_2_manual}")
    print(f"revalida.descensos (manual):          {descensos_manual}")
    print(f"\nresult().campeon:                    {resultado.campeon}")
    print(f"result().ascensos:                    {resultado.ascensos}")
    print(f"result().descensos:                   {resultado.descensos}")
    print(f"result().clasificados_copa:           {resultado.clasificados_copa}")

    errores = []
    if resultado.campeon != ascenso_1_manual:
        errores.append(
            f"campeon: adaptador dio '{resultado.campeon}', "
            f"manual (ascenso_1) dio '{ascenso_1_manual}'"
        )
    if resultado.ascensos != [ascenso_1_manual, ascenso_2_manual]:
        errores.append(
            f"ascensos: adaptador dio {resultado.ascensos}, "
            f"manual dio [{ascenso_1_manual}, {ascenso_2_manual}]"
        )
    if resultado.descensos != descensos_manual:
        errores.append(
            f"descensos: adaptador dio {resultado.descensos}, manual dio {descensos_manual}"
        )
    if resultado.clasificados_copa != []:
        errores.append(
            f"clasificados_copa: esperaba [], adaptador dio {resultado.clasificados_copa}"
        )

    print("\n" + "=" * 70)
    if errores:
        print("❌ El adaptador NO coincide con el mapeo manual:")
        for e in errores:
            print(f"   - {e}")
    else:
        print("✅ El adaptador coincide exactamente con el mapeo manual (datos locales).")
        print("   FederalAdapter queda validado para esta corrida.")
        print(
            "\n   Nota: esta corrida usó CSV locales, no Supabase. Cuando tengas "
            "acceso a una conexión real (dev o producción), no está de más correr "
            "también validar_etapa2_federal.py para confirmar contra los datos que "
            "realmente sirve el backend."
        )
    print("=" * 70)


if __name__ == "__main__":
    main()
