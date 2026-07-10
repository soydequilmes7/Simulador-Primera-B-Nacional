# -*- coding: utf-8 -*-
"""
season/validar_etapa4_qualification.py

Validación de QualificationManager (reglas reales de AFA para
Libertadores/Sudamericana, con cascada de cupos -- ver docstring de
season/qualification_manager.py). Se prueba con mocks -- objetos con
la misma forma que ResultadoTorneo (datos_crudos, descensos, campeon),
no con LPFAdapter/CopaAdapter reales corriendo simulaciones.

Correrlo desde la raíz del proyecto:

    python -m season.validar_etapa4_qualification
"""
from season.qualification_manager import QualificationManager


class MockResultadoLPF:
    def __init__(self, campeon_apertura, campeon_clausura, tabla_anual, descensos=None):
        self.datos_crudos = {
            "campeon_apertura": campeon_apertura,
            "campeon_clausura": campeon_clausura,
            "tabla_anual": [{"equipo": e} for e in tabla_anual],
        }
        self.descensos = descensos or []


class MockResultadoCopa:
    def __init__(self, campeon, rondas=None):
        self.campeon = campeon
        self.datos_crudos = {"rondas": rondas or {}}


TABLA_TIPICA = [
    "Boca", "River", "Racing", "Independiente", "San Lorenzo", "Vélez",
    "Huracán", "Estudiantes", "Talleres", "Belgrano", "Unión", "Colón",
]


def main():
    print("=" * 70)
    print("VALIDACIÓN QualificationManager -- reglas reales AFA")
    print("=" * 70)

    errores = []
    manager = QualificationManager()

    def check(nombre, cond, detalle=""):
        estado = "OK" if cond else "FALLÓ"
        print(f"  [{estado}] {nombre}" + (f" -- {detalle}" if detalle and not cond else ""))
        if not cond:
            errores.append(f"{nombre}: {detalle}")

    print("\n[Caso 1] Sin cascadas")
    lpf = MockResultadoLPF("Boca", "River", TABLA_TIPICA)
    copa = MockResultadoCopa("Racing")
    salida = manager.calcular(lpf, copa)
    check("Argentina 1 = campeón Apertura", salida["detalle"].get("argentina_1") == "Boca")
    check("Argentina 2 = campeón Clausura", salida["detalle"].get("argentina_2") == "River")
    check("Argentina 3 = campeón Copa", salida["detalle"].get("argentina_3") == "Racing")
    check("6 cupos de Libertadores", len(salida["libertadores"]) == 6, str(salida["libertadores"]))
    check("Sudamericana no repite a nadie de Libertadores",
          not (set(salida["libertadores"]) & set(salida["sudamericana"])))
    check("Sin avisos", not salida["avisos"], str(salida["avisos"]))

    print("\n[Caso 2] Apertura = Clausura (mismo campeón)")
    lpf = MockResultadoLPF("Boca", "Boca", TABLA_TIPICA)
    copa = MockResultadoCopa("Racing")
    salida = manager.calcular(lpf, copa)
    check("Boca aparece una sola vez", salida["libertadores"].count("Boca") == 1)
    check("6 cupos igual se cubren", len(salida["libertadores"]) == 6, str(salida["libertadores"]))
    check("Hay aviso de la cascada", any("Apertura y Clausura" in a for a in salida["avisos"]))

    print("\n[Caso 3] Campeón de Copa Argentina == campeón del Apertura")
    lpf = MockResultadoLPF("Boca", "River", TABLA_TIPICA)
    rondas = {"final": [{"local": "Boca", "visitante": "Vélez", "avanza": "Boca"}]}
    copa = MockResultadoCopa("Boca", rondas=rondas)
    salida = manager.calcular(lpf, copa)
    check("Argentina 3 pasa al finalista perdedor (Vélez)",
          salida["detalle"].get("argentina_3_cascada") == "Vélez", str(salida["detalle"]))
    check("Hay aviso explicando la cascada de Copa", any("ya había clasificado" in a for a in salida["avisos"]))

    print("\n[Caso 4] Campeón de Copa Argentina no es de Primera")
    lpf = MockResultadoLPF("Boca", "River", TABLA_TIPICA)
    rondas = {
        "final": [{"local": "Deportivo Maipú", "visitante": "Racing", "avanza": "Deportivo Maipú"}],
        "semis": [{"local": "Racing", "visitante": "San Lorenzo", "avanza": "Racing"},
                  {"local": "Deportivo Maipú", "visitante": "Talleres", "avanza": "Deportivo Maipú"}],
    }
    copa = MockResultadoCopa("Deportivo Maipú", rondas=rondas)
    salida = manager.calcular(lpf, copa)
    check("Argentina 3 pasa al finalista perdedor de Primera (Racing)",
          salida["detalle"].get("argentina_3_cascada") == "Racing", str(salida["detalle"]))

    print("\n[Caso 5] Campeón del Apertura descendió")
    lpf = MockResultadoLPF("Boca", "River", TABLA_TIPICA, descensos=["Boca", "Colón"])
    copa = MockResultadoCopa("Racing")
    salida = manager.calcular(lpf, copa)
    check("Boca NO está en Libertadores", "Boca" not in salida["libertadores"])
    check("6 cupos igual se cubren (cascada a la tabla)", len(salida["libertadores"]) == 6, str(salida["libertadores"]))
    check("Colón (descendido) tampoco aparece en ningún lado",
          "Colón" not in salida["libertadores"] and "Colón" not in salida["sudamericana"])

    print("\n[Caso 6] Sin nadie de Primera disponible para la cascada de Copa")
    lpf = MockResultadoLPF("Boca", "River", TABLA_TIPICA)
    rondas = {"final": [{"local": "Deportivo Maipú", "visitante": "Estudiantes RC", "avanza": "Deportivo Maipú"}]}
    copa = MockResultadoCopa("Deportivo Maipú", rondas=rondas)
    salida = manager.calcular(lpf, copa)
    check("Aviso de cupo sin cubrir", any("sin asignar" in a for a in salida["avisos"]), str(salida["avisos"]))

    print("\n" + "=" * 70)
    if errores:
        print(f"❌ {len(errores)} chequeo(s) fallaron:")
        for e in errores:
            print(f"   - {e}")
    else:
        print("✅ QualificationManager pasó todos los chequeos (con cascadas reales).")
    print("=" * 70)
    return len(errores) == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
