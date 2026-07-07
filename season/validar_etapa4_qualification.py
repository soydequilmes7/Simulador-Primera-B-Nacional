# -*- coding: utf-8 -*-
"""
season/validar_etapa4_qualification.py

Validación de Etapa 4 (QualificationManager). Por diseño, se prueba
con mocks -- objetos con .clasificados_copa, no con LPFAdapter/
CopaAdapter reales corriendo simulaciones (ver
season/qualification_manager.py).

Correrlo desde la raíz del proyecto:

    python -m season.validar_etapa4_qualification
"""
from season.qualification_manager import QualificationManager


class MockResultado:
    def __init__(self, clasificados_copa):
        self.clasificados_copa = clasificados_copa


def main():
    print("=" * 70)
    print("VALIDACIÓN ETAPA 4 -- QualificationManager (mocks)")
    print("=" * 70)

    errores = []
    manager = QualificationManager()

    # ------------------------------------------------------------
    # Caso 1: sin solapamiento -- unión simple
    # ------------------------------------------------------------
    print("\n[Caso 1] Sin solapamiento")
    resultado_lpf = MockResultado(["Club A", "Club B", "Club C"])
    resultado_copa = MockResultado(["Club D"])
    salida = manager.calcular(resultado_lpf, resultado_copa)
    print(f"  clasificados: {salida['clasificados']}")
    print(f"  avisos: {salida['avisos']}")
    esperado = ["Club A", "Club B", "Club C", "Club D"]
    if salida["clasificados"] != esperado:
        errores.append(f"[sin solapamiento] esperado {esperado}, obtenido {salida['clasificados']}")
    if salida["avisos"]:
        errores.append(f"[sin solapamiento] no se esperaban avisos, hubo: {salida['avisos']}")

    # ------------------------------------------------------------
    # Caso 2: con solapamiento -- campeón de copa ya clasificó por LPF
    # ------------------------------------------------------------
    print("\n[Caso 2] Con solapamiento (campeón de Copa ya clasificó por LPF)")
    resultado_lpf = MockResultado(["Club A", "Club B", "Club C"])
    resultado_copa = MockResultado(["Club B"])  # Club B se repite
    salida = manager.calcular(resultado_lpf, resultado_copa)
    print(f"  clasificados: {salida['clasificados']}")
    print(f"  avisos: {salida['avisos']}")
    esperado = ["Club A", "Club B", "Club C"]  # deduplicado, sin cupo extra
    if salida["clasificados"] != esperado:
        errores.append(f"[con solapamiento] esperado {esperado}, obtenido {salida['clasificados']}")
    if not any("Club B" in a and "cascada de cupos" in a for a in salida["avisos"]):
        errores.append("[con solapamiento] se esperaba un aviso mencionando a 'Club B' y 'cascada de cupos'")

    # ------------------------------------------------------------
    # Caso 3: LPF vacío -- caso sospechoso, debe avisar
    # ------------------------------------------------------------
    print("\n[Caso 3] LPF sin clasificados (sospechoso)")
    resultado_lpf = MockResultado([])
    resultado_copa = MockResultado(["Club Campeón Copa"])
    salida = manager.calcular(resultado_lpf, resultado_copa)
    print(f"  clasificados: {salida['clasificados']}")
    print(f"  avisos: {salida['avisos']}")
    if salida["clasificados"] != ["Club Campeón Copa"]:
        errores.append(f"[LPF vacío] esperado ['Club Campeón Copa'], obtenido {salida['clasificados']}")
    if not any("vino vacío" in a for a in salida["avisos"]):
        errores.append("[LPF vacío] se esperaba un aviso sobre LPF sin clasificados")

    # ------------------------------------------------------------
    # Caso 4: trazabilidad -- por_lpf/por_copa se devuelven tal cual
    # ------------------------------------------------------------
    print("\n[Caso 4] Trazabilidad de por_lpf / por_copa")
    resultado_lpf = MockResultado(["Club X", "Club Y"])
    resultado_copa = MockResultado(["Club Z"])
    salida = manager.calcular(resultado_lpf, resultado_copa)
    if salida["por_lpf"] != ["Club X", "Club Y"]:
        errores.append(f"[trazabilidad] por_lpf incorrecto: {salida['por_lpf']}")
    if salida["por_copa"] != ["Club Z"]:
        errores.append(f"[trazabilidad] por_copa incorrecto: {salida['por_copa']}")
    print("  OK" if not errores else "  Hay errores, ver más abajo")

    print("\n" + "=" * 70)
    if errores:
        print("❌ QualificationManager NO pasó todos los chequeos:")
        for e in errores:
            print(f"   - {e}")
    else:
        print("✅ QualificationManager pasó todos los chequeos con mocks.")
        print("   Recordatorio: NO resuelve la cascada de cupos real (ver docstring")
        print("   de season/qualification_manager.py) -- limitación documentada,")
        print("   pendiente si hace falta más adelante.")
    print("=" * 70)


if __name__ == "__main__":
    main()
