"""
Validación manual de NacionalAdapter (Etapa 2).

Corre main.correr_simulacion() UNA sola vez, y compara:
  (a) lo que arma el adaptador (NacionalAdapter().run().result())
  (b) el mapeo hecho a mano leyendo el mismo dict devuelto

Si ambos coinciden, el adaptador queda validado contra datos reales
(no mockeados). Correr desde la raíz del proyecto:

    python -m season.validar_etapa2_nacional
"""

import main as main_nacional
from season.adapters.nacional_adapter import NacionalAdapter


def main():
    print("=" * 50)
    print("VALIDACIÓN ETAPA 2 -- NacionalAdapter")
    print("=" * 50)

    print("\nCorriendo main.correr_simulacion() directo (mapeo manual)...")
    datos_web = main_nacional.correr_simulacion(n_sims=1000, imprimir=True, guardar_json=False)

    ganador_manual = datos_web["final_ascenso"]["ganador"]
    campeon_reducido_manual = datos_web["reducido"]["final"]["campeon"]

    print("\nCorriendo main.correr_simulacion() a través del adaptador...")
    motor = NacionalAdapter()
    motor.setup()
    motor.run(n_sims=1000)
    resultado = motor.result()

    print(f"\nGanador final_ascenso (manual):     {ganador_manual}")
    print(f"Campeón reducido (manual):           {campeon_reducido_manual}")
    print(f"result().campeon:                    {resultado.campeon}")
    print(f"result().ascensos:                    {resultado.ascensos}")
    print(f"result().descensos:                   {resultado.descensos}")
    print(f"result().clasificados_copa:           {resultado.clasificados_copa}")

    ok = (
        resultado.campeon == ganador_manual
        and resultado.ascensos == [ganador_manual, campeon_reducido_manual]
    )

    if ok:
        print("\n✅ El adaptador coincide exactamente con el mapeo manual.")
        print("   NacionalAdapter queda validado para esta corrida.")
    else:
        print("\n❌ El adaptador NO coincide con el mapeo manual. Revisar.")


if __name__ == "__main__":
    main()
