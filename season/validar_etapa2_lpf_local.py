# -*- coding: utf-8 -*-
"""
season/validar_etapa2_lpf_local.py

Versión LOCAL de la validación de Etapa 2 (LPFAdapter). Mismo espíritu
que validar_etapa2_nacional_local.py: evita depender de
SUPABASE_DB_URL, parcheando data_access ANTES de llamar a
LPFAdapter().run().

DIFERENCIA IMPORTANTE con el caso Nacional: EstadisticasLPF.
cargar_datos_lpf() llama a DOS funciones de data_access, no una:

    self.resultados, self.fixture, self.apertura = data_access.league_data("lpf")
    self.promedios_historicos = data_access.lpf_average_history_df()

Si solo se parchea league_data() (como alcanzaba para Nacional), esto
va a explotar igual pidiendo Supabase en cuanto llegue a
lpf_average_history_df(). Por eso acá se parchean las DOS.

IMPORTANTE -- esto es SOLO para la corrida de validación: no se toca
main_lpf.py, modelos/estadisticas_lpf.py, ni data_access.py. El parche
se aplica sobre el módulo data_access ya importado, confiando en que
estadisticas_lpf.py hace data_access.league_data(...) /
data_access.lpf_average_history_df() (atributos del módulo, resueltos
en tiempo de llamada) y no "from data_access import ...".

RUTAS ASUMIDAS -- ajustar estas 4 constantes si tu repo usa otros
nombres (son las que aparecen citadas en los mensajes de error de
estadisticas_lpf.py: "tablalpf.csv", "fixture_lpf.csv",
"promedios_lpf.csv"; resultados_lpf.csv sigue el mismo patrón):

    RESULTADOS_CSV = "datos/resultados_lpf.csv"
    FIXTURE_CSV    = "datos/fixture_lpf.csv"
    TABLA_CSV      = "datos/tablalpf.csv"
    PROMEDIOS_CSV  = "datos/promedios_lpf.csv"

Correrlo desde la raíz del proyecto:

    python -m season.validar_etapa2_lpf_local
"""
import pandas as pd

RESULTADOS_CSV = "datos/resultados_lpf.csv"
FIXTURE_CSV = "datos/fixture_lpf.csv"
TABLA_CSV = "datos/tablalpf.csv"
PROMEDIOS_CSV = "datos/promedios_lpf.csv"


def _league_data_local(competition_slug):
    """Reemplazo local de data_access.league_data("lpf"). Devuelve
    (resultados, fixture, apertura) -- mismo shape que espera
    EstadisticasLPF.cargar_datos_lpf()."""
    resultados = pd.read_csv(RESULTADOS_CSV, encoding="utf-8")
    fixture = pd.read_csv(FIXTURE_CSV, encoding="utf-8")
    apertura = pd.read_csv(TABLA_CSV, encoding="utf-8")
    return resultados, fixture, apertura


def _lpf_average_history_local():
    """Reemplazo local de data_access.lpf_average_history_df()."""
    return pd.read_csv(PROMEDIOS_CSV, encoding="utf-8")


def _parchear_data_access():
    import data_access
    data_access.league_data = _league_data_local
    data_access.lpf_average_history_df = _lpf_average_history_local
    print("[validación local] data_access parcheado (LPF) para leer:")
    print(f"  resultados: {RESULTADOS_CSV}")
    print(f"  fixture:    {FIXTURE_CSV}")
    print(f"  apertura:   {TABLA_CSV}")
    print(f"  promedios:  {PROMEDIOS_CSV}")


def main():
    print("=" * 70)
    print("VALIDACIÓN ETAPA 2 (LOCAL, sin Supabase) -- LPFAdapter")
    print("=" * 70)

    try:
        _parchear_data_access()
    except FileNotFoundError as e:
        print(f"\n❌ No encontré uno de los CSV esperados: {e}")
        print(
            "Ajustá RESULTADOS_CSV / FIXTURE_CSV / TABLA_CSV / PROMEDIOS_CSV "
            "al inicio de este archivo si tus nombres reales son distintos."
        )
        return

    from season.adapters.lpf_adapter import LPFAdapter, _extraer_clasificados_copa

    adapter = LPFAdapter()
    adapter.setup()
    print("\nCorriendo main_lpf.correr_simulacion_lpf() a través del adaptador (datos locales)...")
    adapter.run(n_sims=300)
    resultado = adapter.result()

    datos_web = resultado.datos_crudos

    campeon_manual = datos_web["campeon_clausura"]
    descensos_manual = datos_web["descensos"]
    clasificados_manual = _extraer_clasificados_copa(datos_web["copas"])

    print(f"\ncampeon_clausura (manual):            {campeon_manual}")
    print(f"descensos (manual):                   {descensos_manual}")
    print(f"clasificados_copa (manual, filtrado):  {clasificados_manual}")
    print(f"\nresult().campeon:                    {resultado.campeon}")
    print(f"result().ascensos:                    {resultado.ascensos}")
    print(f"result().descensos:                   {resultado.descensos}")
    print(f"result().clasificados_copa:           {resultado.clasificados_copa}")

    errores = []
    if resultado.campeon != campeon_manual:
        errores.append(
            f"campeon: adaptador dio '{resultado.campeon}', manual dio '{campeon_manual}'"
        )
    if resultado.ascensos != []:
        errores.append(f"ascensos: esperaba [], adaptador dio {resultado.ascensos}")
    if resultado.descensos != descensos_manual:
        errores.append(
            f"descensos: adaptador dio {resultado.descensos}, manual dio {descensos_manual}"
        )
    if resultado.clasificados_copa != clasificados_manual:
        errores.append(
            f"clasificados_copa: adaptador dio {resultado.clasificados_copa}, "
            f"manual dio {clasificados_manual}"
        )

    print("\n" + "=" * 70)
    if errores:
        print("❌ El adaptador NO coincide con el mapeo manual:")
        for e in errores:
            print(f"   - {e}")
    else:
        print("✅ El adaptador coincide exactamente con el mapeo manual (datos locales).")
        print("   LPFAdapter queda validado para esta corrida.")
        print(
            "\n   Nota: esta corrida usó CSV locales, no Supabase. Cuando tengas "
            "acceso a una conexión real (dev o producción), no está de más correr "
            "también validar_etapa2_lpf.py para confirmar contra los datos que "
            "realmente sirve el backend."
        )
    print("=" * 70)


if __name__ == "__main__":
    main()
