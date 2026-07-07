# -*- coding: utf-8 -*-
"""
season/validar_etapa4.py

Validación de Etapa 4 (PromotionManager). A diferencia de la primera
versión, esto usa el ClubRegistry REAL (season/club_registry.py, ya
validado en Etapa 0) -- no un mock aparte -- para probar la interfaz
real de una punta a la otra (incluidos agregar_club()/retirar_club(),
agregados en esta misma etapa). Lo único mockeado es CÓMO se llena el
registro (acá con altas manuales vía agregar_club(), no leyendo CSV
reales vía build_from_current_data()) y los ResultadoTorneo de cada
división (MockResultado).

Correrlo desde la raíz del proyecto:

    python -m season.validar_etapa4
"""
import random

from season.club_registry import ClubRegistry, DIVISIONES
from season.promotion_manager import PromotionManager


class MockResultado:
    """Reemplazo mínimo de ResultadoTorneo -- solo lo que
    PromotionManager lee (.ascensos / .descensos)."""

    def __init__(self, ascensos=None, descensos=None):
        self.ascensos = ascensos or []
        self.descensos = descensos or []


def _armar_registry_mockeado() -> ClubRegistry:
    """ClubRegistry REAL, poblado a mano vía agregar_club() (no
    build_from_current_data(), para no depender de CSV/DB reales acá).
    Los nombres de Nacional son los EXACTOS de tabla.csv (columna
    "equipo"), para probar geografia_clubes.py contra los strings
    reales, no contra una versión prolija inventada."""
    registro = ClubRegistry()

    altas = [
        # LPF (2 clubes de prueba, uno desciende)
        ("Club LPF Puntero", "lpf"),
        ("Club LPF Colista", "lpf"),
        # Nacional -- nombres REALES de tabla.csv + 1 inventado a propósito sin clasificar
        ("Godoy Cruz", "nacional"),      # asciende a LPF (ganador directo) -- interior
        ("Colegiales", "nacional"),      # asciende a LPF (reducido) -- amba
        ("Acassuso", "nacional"),        # desciende, amba -> bmetro
        ("San Telmo", "nacional"),       # desciende, amba -> bmetro
        ("Colón", "nacional"),           # desciende, interior -> federal_a
        ("Club Inventado Sin Clasificar", "nacional"),  # desciende, sin clasificar -> random
        # BMetro
        ("Club BMetro Puntero", "bmetro"),
        ("Club BMetro Reducido", "bmetro"),
        ("Club BMetro Descenso 1", "bmetro"),
        ("Club BMetro Descenso 2", "bmetro"),
        # Federal A
        ("Club Federal Ascenso 1", "federal_a"),
        ("Club Federal Ascenso 2", "federal_a"),
        ("Club Federal Descenso 1", "federal_a"),
        ("Club Federal Descenso 2", "federal_a"),
        ("Club Federal Descenso 3", "federal_a"),
        ("Club Federal Descenso 4", "federal_a"),
        # Primera C
        ("Club PrimeraC Ascenso 1", "primerac"),
        ("Club PrimeraC Ascenso 2", "primerac"),
    ]
    for nombre, slug_division in altas:
        registro.agregar_club(nombre, DIVISIONES[slug_division])

    return registro


def main():
    print("=" * 70)
    print("VALIDACIÓN ETAPA 4 -- PromotionManager (ClubRegistry real, altas manuales)")
    print("=" * 70)

    errores = []
    registry = _armar_registry_mockeado()

    resultados = {
        "lpf": MockResultado(descensos=["Club LPF Colista"]),
        "nacional": MockResultado(
            ascensos=["Godoy Cruz", "Colegiales"],
            descensos=["Acassuso", "San Telmo", "Colón", "Club Inventado Sin Clasificar"],
        ),
        "bmetro": MockResultado(
            ascensos=["Club BMetro Puntero", "Club BMetro Reducido"],
            descensos=["Club BMetro Descenso 1", "Club BMetro Descenso 2"],
        ),
        "federal_a": MockResultado(
            ascensos=["Club Federal Ascenso 1", "Club Federal Ascenso 2"],
            descensos=[
                "Club Federal Descenso 1", "Club Federal Descenso 2",
                "Club Federal Descenso 3", "Club Federal Descenso 4",
            ],
        ),
        "primerac": MockResultado(ascensos=["Club PrimeraC Ascenso 1", "Club PrimeraC Ascenso 2"]),
    }

    politica = PromotionManager(rng=random.Random(42))
    resumen = politica.aplicar(resultados, registry, temporada_destino="2027")

    print("\n--- Movimientos aplicados ---")
    for m in resumen["movimientos"]:
        print(f"  {m['club']:35s} {str(m['origen']):12s} -> {str(m['destino']):12s}  ({m['motivo']})")

    print("\n--- Avisos ---")
    for a in resumen["avisos"]:
        print(f"  ! {a}")

    # ------------------------------------------------------------
    # Caso 1: LPF <-> Nacional
    # ------------------------------------------------------------
    print("\n[Caso 1] LPF <-> Nacional")
    if registry.get_by_name("Club LPF Colista").division != DIVISIONES["nacional"]:
        errores.append("Club LPF Colista debería haber bajado a Primera Nacional")
    if registry.get_by_name("Godoy Cruz").division != DIVISIONES["lpf"]:
        errores.append("Godoy Cruz debería haber subido a Liga Profesional")
    if registry.get_by_name("Colegiales").division != DIVISIONES["lpf"]:
        errores.append("Colegiales debería haber subido a Liga Profesional")
    print("  OK" if not errores else "  Hay errores, ver más abajo")

    # ------------------------------------------------------------
    # Caso 2: Nacional -> {bmetro, federal_a} por afiliación real
    # ------------------------------------------------------------
    print("\n[Caso 2] Nacional -> bmetro/federal_a por afiliación geográfica")
    esperado_geografico = {
        "Acassuso": "bmetro",       # amba
        "San Telmo": "bmetro",      # amba
        "Colón": "federal_a",       # interior
    }
    for club, slug_esperado in esperado_geografico.items():
        obtenida = registry.get_by_name(club).division
        if obtenida != DIVISIONES[slug_esperado]:
            errores.append(
                f"{club}: se esperaba {DIVISIONES[slug_esperado]!r}, quedó en {obtenida!r}"
            )
    division_sin_clasificar = registry.get_by_name("Club Inventado Sin Clasificar").division
    if division_sin_clasificar not in (DIVISIONES["bmetro"], DIVISIONES["federal_a"]):
        errores.append(
            f"Club Inventado Sin Clasificar quedó en {division_sin_clasificar!r}, "
            f"se esperaba B Metro o Federal A (fallback al azar)"
        )
    if not any("sin clasificación geográfica" in a for a in resumen["avisos"]):
        errores.append("Se esperaba un aviso por falta de clasificación geográfica, no apareció")
    print("  OK" if not errores else "  Hay errores, ver más abajo")

    # ------------------------------------------------------------
    # Caso 3: {bmetro, federal_a} -> Nacional
    # ------------------------------------------------------------
    print("\n[Caso 3] bmetro/federal_a -> Nacional")
    for club in ["Club BMetro Puntero", "Club BMetro Reducido",
                 "Club Federal Ascenso 1", "Club Federal Ascenso 2"]:
        if registry.get_by_name(club).division != DIVISIONES["nacional"]:
            errores.append(f"{club} debería haber subido a Primera Nacional")
    print("  OK" if not errores else "  Hay errores, ver más abajo")

    # ------------------------------------------------------------
    # Caso 4: bmetro <-> primerac
    # ------------------------------------------------------------
    print("\n[Caso 4] bmetro <-> primerac")
    for club in ["Club BMetro Descenso 1", "Club BMetro Descenso 2"]:
        if registry.get_by_name(club).division != DIVISIONES["primerac"]:
            errores.append(f"{club} debería haber bajado a Primera C")
    for club in ["Club PrimeraC Ascenso 1", "Club PrimeraC Ascenso 2"]:
        if registry.get_by_name(club).division != DIVISIONES["bmetro"]:
            errores.append(f"{club} debería haber subido a B Metro")
    print("  OK" if not errores else "  Hay errores, ver más abajo")

    # ------------------------------------------------------------
    # Caso 5: Federal A -- descensos salen del sistema, se generan rellenos
    # ------------------------------------------------------------
    print("\n[Caso 5] Federal A: descensos fuera del sistema + relleno")
    for club in ["Club Federal Descenso 1", "Club Federal Descenso 2",
                 "Club Federal Descenso 3", "Club Federal Descenso 4"]:
        if registry.get_by_name(club) is not None:
            errores.append(f"{club} debería haber salido del registro, todavía está")

    clubes_federal_a_final = registry.get_by_division(DIVISIONES["federal_a"])
    rellenos = [c for c in clubes_federal_a_final if getattr(c, "es_relleno", False)]
    if len(rellenos) != 4:
        errores.append(
            f"Se esperaban 4 clubes de relleno en Federal A, hay {len(rellenos)}"
        )
    nombres_relleno_esperados = {f"Ingreso Regional 2027-{i}" for i in range(1, 5)}
    nombres_relleno_obtenidos = {c.name for c in rellenos}
    if nombres_relleno_obtenidos != nombres_relleno_esperados:
        errores.append(
            f"Nombres de relleno inesperados: {nombres_relleno_obtenidos} "
            f"(se esperaba {nombres_relleno_esperados})"
        )
    club_sin_clasificar_fue_a_federal = (
        registry.get_by_name("Club Inventado Sin Clasificar").division == DIVISIONES["federal_a"]
    )
    esperado_total_federal_a = 4 + 1 + (1 if club_sin_clasificar_fue_a_federal else 0)  # 4 relleno + Colón (interior, fijo) + random si tocó acá
    obtenido_total_federal_a = len(registry.get_by_division(DIVISIONES["federal_a"]))
    if obtenido_total_federal_a != esperado_total_federal_a:
        errores.append(
            f"Federal A debería tener {esperado_total_federal_a} clubes al final "
            f"(4 relleno + Colón + posible club sin clasificar), tiene "
            f"{obtenido_total_federal_a}"
        )
    print("  OK" if not errores else "  Hay errores, ver más abajo")

    # ------------------------------------------------------------
    # Caso 6: error si falta una división en `resultados`
    # ------------------------------------------------------------
    print("\n[Caso 6] Manejo de errores -- falta una división")
    try:
        politica.aplicar({k: v for k, v in resultados.items() if k != "primerac"}, registry)
        errores.append("Se esperaba ValueError por falta de 'primerac' en resultados, no se lanzó")
    except ValueError as e:
        print(f"  OK -- faltante de división levantó ValueError: {e}")

    # ------------------------------------------------------------
    # Caso 7: club no encontrado en el registro no debe romper nada
    # ------------------------------------------------------------
    print("\n[Caso 7] Club inexistente en el registro no rompe la corrida")
    registry_chico = ClubRegistry()
    registry_chico.agregar_club("Único Club", DIVISIONES["lpf"])
    resultados_chicos = {
        "lpf": MockResultado(descensos=["Club Que No Existe"]),
        "nacional": MockResultado(),
        "bmetro": MockResultado(),
        "federal_a": MockResultado(),
        "primerac": MockResultado(),
    }
    try:
        resumen_chico = politica.aplicar(resultados_chicos, registry_chico)
        if not any("no encontrado" in a for a in resumen_chico["avisos"]):
            errores.append("Se esperaba un aviso de 'club no encontrado', no apareció")
        else:
            print("  OK -- club inexistente generó aviso y no rompió la corrida")
    except Exception as e:
        errores.append(f"Un club inexistente en el registro no debería tirar excepción: {e}")

    # ------------------------------------------------------------
    # Caso 8: agregar_club() rechaza nombres duplicados (regla ya
    # existente en build_from_current_data(), reusada acá)
    # ------------------------------------------------------------
    print("\n[Caso 8] agregar_club() rechaza duplicados")
    try:
        registry.agregar_club("Godoy Cruz", DIVISIONES["nacional"])
        errores.append("Se esperaba ValueError por nombre duplicado en agregar_club(), no se lanzó")
    except ValueError as e:
        print(f"  OK -- nombre duplicado levantó ValueError: {e}")

    print("\n" + "=" * 70)
    if errores:
        print("❌ PromotionManager NO pasó todos los chequeos:")
        for e in errores:
            print(f"   - {e}")
    else:
        print("✅ PromotionManager pasó todos los chequeos contra el ClubRegistry real")
        print("   (poblado a mano, sin tocar CSV/DB reales todavía).")
    print("=" * 70)


if __name__ == "__main__":
    main()
