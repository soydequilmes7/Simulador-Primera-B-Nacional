# -*- coding: utf-8 -*-
"""
season/validar_etapa2_copa.py

Validación de Etapa 2 (CopaAdapter): corre CopaAdapter y lo compara
contra llamar main_copa.correr_simulacion_copa() a mano, mismo
espíritu que los demás validar_etapa2_*.py. Una sola corrida (Monte
Carlo no es determinístico entre llamadas), se compara el mapeo
manual contra el MISMO datos_web que ya corrió el adaptador (guardado
en resultado.datos_crudos).

Correrlo desde la raíz del proyecto:

    python -m season.validar_etapa2_copa
"""
from season.adapters.copa_adapter import CopaAdapter


def main():
    print("=" * 70)
    print("VALIDACIÓN ETAPA 2 -- CopaAdapter")
    print("=" * 70)

    adapter = CopaAdapter()
    adapter.setup()
    print("\nCorriendo main_copa.correr_simulacion_copa() a través del adaptador...")
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
        print("✅ El adaptador coincide exactamente con el mapeo manual.")
        print("   CopaAdapter queda validado para esta corrida.")
    print("=" * 70)


if __name__ == "__main__":
    main()
