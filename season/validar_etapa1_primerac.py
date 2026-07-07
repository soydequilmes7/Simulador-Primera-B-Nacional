# -*- coding: utf-8 -*-
"""
season/validar_etapa1_primerac.py

Validación de Etapa 1: corre PrimeraCAdapter y lo compara contra
llamar main_primerac.correr_simulacion() directo y mapear el resultado
a mano, tal como pide el plan para esta etapa. Como Estadisticas() no
es determinística entre corridas (hay Monte Carlo y simulación de
partidos con aleatoriedad), esta validación NO puede simplemente
correr dos veces y comparar resultados -- correr dos veces da
resultados distintos aunque el adaptador esté perfecto.

En cambio: se corre la simulación UNA sola vez a través del adaptador
(que guarda internamente el datos_web crudo en datos_crudos), y se
verifica que el mapeo manual sobre ESE MISMO datos_web coincide con lo
que devolvió result(). Esto aísla el bug que nos importa acá (¿el
adaptador traduce bien el dict?) del ruido de la aleatoriedad del
motor (que no es responsabilidad de esta etapa).

Correrlo desde la raíz del proyecto:

    python -m season.validar_etapa1_primerac
"""
from season.adapters.primerac_adapter import PrimeraCAdapter, _extraer_campeon_reducido


def main():
    print("=" * 70)
    print("VALIDACIÓN ETAPA 1 -- PrimeraCAdapter")
    print("=" * 70)

    adapter = PrimeraCAdapter()
    adapter.setup(clubes=[])  # todavía no se usa, ver docstring del adaptador
    print("\nCorriendo main_primerac.correr_simulacion() a través del adaptador...")
    adapter.run(n_sims=1000)
    resultado = adapter.result()

    datos_web = resultado.datos_crudos

    # --- Mapeo manual, hecho a mano acá mismo sobre el MISMO datos_web ---
    ganador_manual = datos_web["final_ascenso"]["ganador"]
    campeon_reducido_manual = _extraer_campeon_reducido(datos_web["reducido"])

    print(f"\nGanador final_ascenso (manual):     {ganador_manual}")
    print(f"Campeón reducido (manual):           {campeon_reducido_manual}")
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
    if resultado.descensos != []:
        errores.append(f"descensos: esperaba [], adaptador dio {resultado.descensos}")
    if resultado.clasificados_copa != []:
        errores.append(f"clasificados_copa: esperaba [], adaptador dio {resultado.clasificados_copa}")

    print("\n" + "=" * 70)
    if errores:
        print("❌ El adaptador NO coincide con el mapeo manual:")
        for e in errores:
            print(f"   - {e}")
    else:
        print("✅ El adaptador coincide exactamente con el mapeo manual.")
        print("   PrimeraCAdapter queda validado para esta corrida.")
    print("=" * 70)


if __name__ == "__main__":
    main()
