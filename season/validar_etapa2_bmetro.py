# -*- coding: utf-8 -*-
"""
season/validar_etapa2_bmetro.py

Validación de Etapa 2 (BMetroAdapter): corre BMetroAdapter y lo
compara contra llamar main_bmetro.correr_simulacion_bmetro() a mano,
mismo espíritu que validar_etapa2_nacional.py / validar_etapa2_lpf.py.
Una sola corrida (Monte Carlo no es determinístico entre llamadas), se
compara el mapeo manual contra el MISMO datos_web que ya corrió el
adaptador (guardado en resultado.datos_crudos).

Correrlo desde la raíz del proyecto:

    python -m season.validar_etapa2_bmetro
"""
from season.adapters.bmetro_adapter import BMetroAdapter


def main():
    print("=" * 70)
    print("VALIDACIÓN ETAPA 2 -- BMetroAdapter")
    print("=" * 70)

    adapter = BMetroAdapter()
    adapter.setup()
    print("\nCorriendo main_bmetro.correr_simulacion_bmetro() a través del adaptador...")
    adapter.run(n_sims=300)
    resultado = adapter.result()

    datos_web = resultado.datos_crudos

    ascenso_directo_manual = datos_web["puntero_ascenso_directo"]
    ascenso_reducido_manual = datos_web["campeon_reducido"]
    descensos_manual = datos_web["descensos"]

    print(f"\npuntero_ascenso_directo (manual): {ascenso_directo_manual}")
    print(f"campeon_reducido (manual):        {ascenso_reducido_manual}")
    print(f"descensos (manual):                {descensos_manual}")
    print(f"\nresult().campeon:                 {resultado.campeon}")
    print(f"result().ascensos:                 {resultado.ascensos}")
    print(f"result().descensos:                {resultado.descensos}")
    print(f"result().clasificados_copa:        {resultado.clasificados_copa}")

    errores = []
    if resultado.campeon != ascenso_directo_manual:
        errores.append(
            f"campeon: adaptador dio '{resultado.campeon}', "
            f"manual (puntero_ascenso_directo) dio '{ascenso_directo_manual}'"
        )
    if resultado.ascensos != [ascenso_directo_manual, ascenso_reducido_manual]:
        errores.append(
            f"ascensos: adaptador dio {resultado.ascensos}, "
            f"manual dio [{ascenso_directo_manual}, {ascenso_reducido_manual}]"
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
        print("✅ El adaptador coincide exactamente con el mapeo manual.")
        print("   BMetroAdapter queda validado para esta corrida.")
    print("=" * 70)


if __name__ == "__main__":
    main()
