# -*- coding: utf-8 -*-
"""
season/validar_etapa0.py

Script manual de validación de la Etapa 0. No conecta nada nuevo ni
escribe nada -- solo confirma que ClubRegistry.build_from_current_data()
reproduce fielmente lo que ya hay hoy en cada división, antes de construir
cualquier cosa encima (Etapa 1 en adelante).

Correrlo desde la raíz del proyecto:

    python -m season.validar_etapa0

Qué chequea:
  1. Que el conteo de clubes por división coincida con len(tabla) de
     cada data_access.league_data(slug) (debería ser trivialmente
     cierto, pero confirma que ClubRegistry no perdió ni duplicó nada
     al armarse).
  2. Nombres duplicados entre divisiones: si los hay, build_from_current_data
     ya lanza ValueError antes de llegar a imprimir nada -- este script
     deja ese error legible en vez de un traceback crudo.
  3. Imprime un resumen para inspección visual rápida (primeros clubes
     de cada división).
"""
import data_access

from season.club_registry import ClubRegistry, DIVISIONES


def main():
    print("=" * 60)
    print("VALIDACIÓN ETAPA 0 -- ClubRegistry de solo lectura")
    print("=" * 60)

    try:
        registro = ClubRegistry.build_from_current_data()
    except ValueError as e:
        print(f"\n❌ FALLÓ la construcción del registro: {e}")
        return

    print(f"\nTotal de clubes registrados: {len(registro)}")
    print("\nPor división (esperado = len(tabla) real vs. registrado = ClubRegistry):")

    todo_ok = True
    for slug, nombre_division in DIVISIONES.items():
        _resultados, _fixture, tabla = data_access.league_data(slug)
        esperado = len(tabla)
        real = len(registro.get_by_division(nombre_division))
        ok = esperado == real
        todo_ok = todo_ok and ok
        estado = "OK" if ok else "MISMATCH"
        print(f"  {nombre_division:30s} esperado={esperado:3d}  registrado={real:3d}  [{estado}]")

    print("\nEjemplo (primeros 3 clubes de cada división):")
    for nombre_division in DIVISIONES.values():
        clubes = registro.get_by_division(nombre_division)[:3]
        print(f"  {nombre_division}: {[c.name for c in clubes]}")

    print("\n" + "=" * 60)
    if todo_ok:
        print("Todos los conteos coinciden. Etapa 0 lista para pasar a la")
        print("Etapa 1 (primer TournamentEngine adaptador, Primera C).")
    else:
        print("Hay al menos un MISMATCH -- revisar antes de seguir.")
    print("=" * 60)


if __name__ == "__main__":
    main()
