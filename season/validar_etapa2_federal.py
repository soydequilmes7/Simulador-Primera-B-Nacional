# -*- coding: utf-8 -*-
"""
season/validar_etapa2_federal.py

Validación de Etapa 2 (FederalAdapter): corre FederalAdapter y lo
compara contra llamar main_federal.correr_simulacion_federal() a mano,
mismo espíritu que los demás validar_etapa2_*.py. Una sola corrida
(Monte Carlo no es determinístico entre llamadas), se compara el
mapeo manual contra el MISMO datos_web que ya corrió el adaptador
(guardado en resultado.datos_crudos).

Ojo: el Federal A es el motor más pesado de los 6 (Primera Fase 4
zonas + Segunda Fase 2 zonas + camino principal + Reválida de 6
etapas, con Monte Carlo vectorizado). Con n_sims=300 puede tardar
bastante más que los validadores de las otras ligas.

Correrlo desde la raíz del proyecto:

    python -m season.validar_etapa2_federal
"""
from season.adapters.federal_adapter import FederalAdapter


def main():
    print("=" * 70)
    print("VALIDACIÓN ETAPA 2 -- FederalAdapter")
    print("=" * 70)

    adapter = FederalAdapter()
    adapter.setup()
    print("\nCorriendo main_federal.correr_simulacion_federal() a través del adaptador...")
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
        print("✅ El adaptador coincide exactamente con el mapeo manual.")
        print("   FederalAdapter queda validado para esta corrida.")
    print("=" * 70)


if __name__ == "__main__":
    main()
