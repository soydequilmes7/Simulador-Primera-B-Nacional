# -*- coding: utf-8 -*-
"""
season/validar_etapa2_lpf.py

Validación de Etapa 2 (LPFAdapter): corre LPFAdapter y lo compara
contra llamar main_lpf.correr_simulacion_lpf() a mano, mismo espíritu
que validar_etapa2_nacional.py. Una sola corrida (Monte Carlo no es
determinístico entre llamadas), se compara el mapeo manual contra el
MISMO datos_web que ya corrió el adaptador (guardado en
resultado.datos_crudos).

Correrlo desde la raíz del proyecto:

    python -m season.validar_etapa2_lpf
"""
from season.adapters.lpf_adapter import LPFAdapter, _extraer_clasificados_copa


def main():
    print("=" * 70)
    print("VALIDACIÓN ETAPA 2 -- LPFAdapter")
    print("=" * 70)

    adapter = LPFAdapter()
    adapter.setup()
    print("\nCorriendo main_lpf.correr_simulacion_lpf() a través del adaptador...")
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
        print("✅ El adaptador coincide exactamente con el mapeo manual.")
        print("   LPFAdapter queda validado para esta corrida.")
    print("=" * 70)


if __name__ == "__main__":
    main()
