# -*- coding: utf-8 -*-
"""
diagnosticar_equipos_dimayor.py

Corré esto UNA VEZ, en la carpeta del proyecto, para ver EXACTAMENTE
qué nombre de equipo está desincronizado entre la tabla (standings) y
el fixture (matches) de Dimayor en Supabase -- el KeyError 'Junior FC'
significa que self.equipos (armado desde la tabla) no tiene esa key
exacta, aunque el fixture sí la use.

Uso:
    python diagnosticar_equipos_dimayor.py
"""
import data_access

resultados, fixture, tabla = data_access.league_data("dimayor")

equipos_tabla = set(tabla["equipo"])
equipos_fixture = set(fixture["equipo_local"]) | set(fixture["equipo_visitante"])

print(f"Equipos en tabla (standings): {len(equipos_tabla)}")
print(f"Equipos en fixture (matches): {len(equipos_fixture)}")

solo_en_fixture = equipos_fixture - equipos_tabla
solo_en_tabla = equipos_tabla - equipos_fixture

print("\n--- Están en el FIXTURE pero no en la TABLA (causan el KeyError) ---")
for nombre in sorted(solo_en_fixture):
    print(f"  {nombre!r}")

print("\n--- Están en la TABLA pero no en el FIXTURE (equipo 'huérfano') ---")
for nombre in sorted(solo_en_tabla):
    print(f"  {nombre!r}")

if not solo_en_fixture and not solo_en_tabla:
    print("\nNo hay mismatches de string. El problema debe estar en otro lado.")
else:
    print(
        "\nMirá el repr() de arriba con atención: si dos nombres se ven "
        "iguales a simple vista pero uno tiene un espacio de más, un "
        "carácter invisible, o mayúsculas distintas, ahí está el bug -- "
        "no matchean como strings de Python aunque en pantalla parezcan "
        "idénticos."
    )
