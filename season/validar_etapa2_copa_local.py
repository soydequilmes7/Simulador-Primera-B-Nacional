# -*- coding: utf-8 -*-
"""
season/validar_etapa2_copa_local.py

Versión LOCAL de la validación de Etapa 2 (CopaAdapter). Mismo
espíritu que los demás validar_etapa2_*_local.py: evita depender de
SUPABASE_DB_URL, parcheando data_access ANTES de llamar a
CopaAdapter().run().

DIFERENCIA IMPORTANTE con el resto de las ligas: EstadisticasCopa NO
usa data_access.league_data() para su propio cuadro -- usa
data_access.cup_records(), que lee el cuadro de cruces (real +
pendientes) de la Copa Argentina. Ese parche es OBLIGATORIO: sin él,
cargar_datos_copa() explota pidiendo Supabase.

Además, EstadisticasCopa.crear_equipos_copa() llama a
_cosechar_ratings_ligas(), que internamente intenta cargar
EstadisticasLPF (league_data("lpf") + lpf_average_history_df()) y
Estadisticas/Nacional (league_data("nacional")) para heredar ratings
reales. A diferencia de cargar_datos_copa(), acá el código YA atrapa
las excepciones por separado (try/except Exception con aviso
impreso) -- si no parchamos también "lpf"/"nacional", el script NO
va a explotar, pero TODOS los equipos van a quedar con el rating
genérico de ATAQUE_ASCENSO/DEFENSA_ASCENSO en vez de ratings reales.
Para una validación más representativa, este script parchea también
esas dos rutas si los CSV correspondientes existen; si no los tenés
a mano, comentá esas líneas en _parchear_data_access() y el script
igual corre (con ratings genéricos para todos).

IMPORTANTE -- esto es SOLO para la corrida de validación: no se toca
main_copa.py, modelos/estadisticas_copa.py, modelos/estadisticas_lpf.py,
modelos/estadisticas.py, ni data_access.py.

RUTAS ASUMIDAS -- ajustar estas constantes si tu repo usa otros
nombres:

    CUADRO_CSV = "datos/copa_argentina.csv"              (obligatorio)
    # Para ratings reales de LPF/Nacional (opcional):
    RESULTADOS_LPF_CSV = "datos/resultados_lpf.csv"
    FIXTURE_LPF_CSV = "datos/fixture_lpf.csv"
    TABLA_LPF_CSV = "datos/tablalpf.csv"
    PROMEDIOS_LPF_CSV = "datos/promedios_lpf.csv"
    RESULTADOS_NACIONAL_CSV = "datos/resultados.csv"
    FIXTURE_NACIONAL_CSV = "datos/fixture.csv"
    TABLA_NACIONAL_CSV = "datos/tabla.csv"

Correrlo desde la raíz del proyecto:

    python -m season.validar_etapa2_copa_local
"""
import csv

import pandas as pd

CUADRO_CSV = "datos/copa_argentina.csv"

RESULTADOS_LPF_CSV = "datos/resultados_lpf.csv"
FIXTURE_LPF_CSV = "datos/fixture_lpf.csv"
TABLA_LPF_CSV = "datos/tablalpf.csv"
PROMEDIOS_LPF_CSV = "datos/promedios_lpf.csv"

RESULTADOS_NACIONAL_CSV = "datos/resultados.csv"
FIXTURE_NACIONAL_CSV = "datos/fixture.csv"
TABLA_NACIONAL_CSV = "datos/tabla.csv"


def _cup_records_local():
    """Reemplazo local de data_access.cup_records(). Devuelve una
    lista de dicts (mismo shape que espera EstadisticasCopa: cada
    fila con equipo_local/equipo_visitante/ronda/llave/ganador/
    goles_local/goles_visitante como STRINGS -- el código de
    estadisticas_copa.py compara contra "" para detectar celdas
    vacías, no None)."""
    with open(CUADRO_CSV, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _league_data_local(competition_slug):
    """Reemplazo local de data_access.league_data(), soporta "lpf" y
    "nacional" -- las dos ligas que _cosechar_ratings_ligas() intenta
    cargar. Cualquier otro slug no debería pedirse desde acá."""
    if competition_slug == "lpf":
        resultados = pd.read_csv(RESULTADOS_LPF_CSV, encoding="utf-8")
        fixture = pd.read_csv(FIXTURE_LPF_CSV, encoding="utf-8")
        tabla = pd.read_csv(TABLA_LPF_CSV, encoding="utf-8")
        return resultados, fixture, tabla
    if competition_slug == "nacional":
        resultados = pd.read_csv(RESULTADOS_NACIONAL_CSV, encoding="utf-8")
        fixture = pd.read_csv(FIXTURE_NACIONAL_CSV, encoding="utf-8")
        tabla = pd.read_csv(TABLA_NACIONAL_CSV, encoding="utf-8")
        return resultados, fixture, tabla
    raise FileNotFoundError(f"slug inesperado en validación local de Copa: {competition_slug!r}")


def _lpf_average_history_local():
    """Reemplazo local de data_access.lpf_average_history_df()."""
    return pd.read_csv(PROMEDIOS_LPF_CSV, encoding="utf-8")


def _parchear_data_access():
    import data_access

    # Obligatorio: sin esto, cargar_datos_copa() explota siempre.
    data_access.cup_records = _cup_records_local
    print("[validación local] data_access.cup_records parcheado (Copa) para leer:")
    print(f"  cuadro: {CUADRO_CSV}")

    # Opcional: para ratings reales de LPF/Nacional en vez de genérico.
    # Si tus CSV de LPF/Nacional no están a mano, comentá este bloque
    # -- el script igual corre, con rating genérico para todos.
    try:
        pd.read_csv(RESULTADOS_LPF_CSV, nrows=1)
        pd.read_csv(TABLA_LPF_CSV, nrows=1)
        pd.read_csv(RESULTADOS_NACIONAL_CSV, nrows=1)
        pd.read_csv(TABLA_NACIONAL_CSV, nrows=1)
        data_access.league_data = _league_data_local
        data_access.lpf_average_history_df = _lpf_average_history_local
        print("[validación local] data_access.league_data/lpf_average_history_df "
              "también parcheados (ratings reales de LPF/Nacional).")
    except FileNotFoundError:
        print("[validación local] No encontré los CSV de LPF/Nacional -- "
              "sigo sin parchear league_data(). _cosechar_ratings_ligas() "
              "atrapa esa falta internamente, así que la corrida NO se cae, "
              "pero todos los equipos van a quedar con rating genérico "
              "(ATAQUE_ASCENSO/DEFENSA_ASCENSO).")


def main():
    print("=" * 70)
    print("VALIDACIÓN ETAPA 2 (LOCAL, sin Supabase) -- CopaAdapter")
    print("=" * 70)

    try:
        _parchear_data_access()
    except FileNotFoundError as e:
        print(f"\n❌ No encontré el CSV del cuadro: {e}")
        print("Ajustá CUADRO_CSV al inicio de este archivo si tu nombre real es distinto.")
        return

    from season.adapters.copa_adapter import CopaAdapter

    adapter = CopaAdapter()
    adapter.setup()
    print("\nCorriendo main_copa.correr_simulacion_copa() a través del adaptador (datos locales)...")
    adapter.run(n_sims=300)
    resultado = adapter.result()

    datos_web = resultado.datos_crudos
    campeon_manual = datos_web["campeon"]

    print(f"\ncampeon (manual):            {campeon_manual}")
    print(f"result().campeon:            {resultado.campeon}")
    print(f"result().ascensos:           {resultado.ascensos}")
    print(f"result().descensos:          {resultado.descensos}")
    print(f"result().clasificados_copa:  {resultado.clasificados_copa}")

    errores = []
    if resultado.campeon != campeon_manual:
        errores.append(
            f"campeon: adaptador dio '{resultado.campeon}', manual dio '{campeon_manual}'"
        )
    if resultado.ascensos != []:
        errores.append(f"ascensos: esperaba [], adaptador dio {resultado.ascensos}")
    if resultado.descensos != []:
        errores.append(f"descensos: esperaba [], adaptador dio {resultado.descensos}")
    if resultado.clasificados_copa != [campeon_manual]:
        errores.append(
            f"clasificados_copa: adaptador dio {resultado.clasificados_copa}, "
            f"esperaba [{campeon_manual}]"
        )

    print("\n" + "=" * 70)
    if errores:
        print("❌ El adaptador NO coincide con el mapeo manual:")
        for e in errores:
            print(f"   - {e}")
    else:
        print("✅ El adaptador coincide exactamente con el mapeo manual (datos locales).")
        print("   CopaAdapter queda validado para esta corrida.")
        print(
            "\n   Nota: esta corrida usó CSV locales, no Supabase. Cuando tengas "
            "acceso a una conexión real (dev o producción), no está de más correr "
            "también validar_etapa2_copa.py para confirmar contra los datos que "
            "realmente sirve el backend."
        )
    print("=" * 70)


if __name__ == "__main__":
    main()
