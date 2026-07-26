# -*- coding: utf-8 -*-
"""Diagnóstico puntual: por qué siguen "sin identificar" los partidos de
LPF después del fix de auto-sync. No modifica nada más allá de lo que
actualizar() haría normalmente (si hay resultados nuevos matcheables,
los carga -- es el mismo actualizar() de siempre, solo con más prints).

Uso:
    python diagnostico_lpf_verbose.py
"""
from actualizar_resultados_lpf import actualizar
from sincronizar_fixture_clausura_lpf import calcular_filas_nuevas
from db.repository import transaction

with transaction() as repo:
    pending_actual = repo.match_records("lpf", "pending")
    jugados_actual = repo.match_records("lpf", "played")

print(f"Fixture pendiente en Supabase ANTES: {len(pending_actual)}")
print(f"Resultados jugados en Supabase ANTES: {len(jugados_actual)}")

filas_nuevas, offset = calcular_filas_nuevas(pending_actual, jugados_actual)
print(f"\ncalcular_filas_nuevas() detectó: {len(filas_nuevas)} fila(s) nueva(s) (offset={offset})")
for f in filas_nuevas[:15]:
    print(f"  Jornada {f['jornada']}: {f['equipo_local']} vs {f['equipo_visitante']}")

print("\n--- Corriendo actualizar() completo ---")
r = actualizar(imprimir=True)

print("\n--- RESUMEN ---")
print("cargados:", len(r["cargados"]))
print("sin_matchear:", len(r["sin_matchear"]))
print("fixture_sincronizado:", r.get("fixture_sincronizado"))

# Reconstruimos indice_fixture EXACTAMENTE como actualizar_resultados_lpf.py,
# y probamos membership DIRECTO (no substring) para cada partido sin
# matchear. Si calcular_filas_nuevas() dice "ya existe" pero el matcheo
# principal dice "sin_matchear" usando la MISMA función de resolución,
# tiene que haber una diferencia invisible (espacio, unicode, etc.) en
# algún lado -- repr() la va a mostrar.
from mapeo_equipos_lpf import resolver_equipo_lpf

with transaction() as repo2:
    pending_ahora = repo2.match_records("lpf", "pending")

def _clave(local, visit):
    return (resolver_equipo_lpf(local) or local, resolver_equipo_lpf(visit) or visit)

indice_fixture = {}
for i, fila in enumerate(pending_ahora):
    clave = _clave(fila["equipo_local"], fila["equipo_visitante"])
    indice_fixture.setdefault(clave, []).append((i, fila))

print(f"\n--- Membership EXACTO para cada partido sin matchear (indice_fixture tiene {len(indice_fixture)} claves únicas) ---")
for p in r["sin_matchear"]:
    clave = _clave(p["equipo_local"], p["equipo_visitante"])
    print(f"\nPromiedos: {p['equipo_local']!r} vs {p['equipo_visitante']!r} -> clave resuelta: {clave!r}")
    if clave in indice_fixture:
        print(f"  ENCONTRADO en indice_fixture ({len(indice_fixture[clave])} fila(s)):")
        for i, fila in indice_fixture[clave]:
            print(f"    fila #{i}, jornada {fila.get('jornada')}: "
                  f"equipo_local={fila['equipo_local']!r} equipo_visitante={fila['equipo_visitante']!r}")
    else:
        print("  NO encontrado en indice_fixture -- buscando la clave INVERTIDA (posible swap local/visitante):")
        clave_invertida = (clave[1], clave[0])
        if clave_invertida in indice_fixture:
            for i, fila in indice_fixture[clave_invertida]:
                print(f"    SWAP encontrado -- fila #{i}, jornada {fila.get('jornada')}: "
                      f"equipo_local={fila['equipo_local']!r} equipo_visitante={fila['equipo_visitante']!r}")
        else:
            print("    Tampoco está invertida. Buscando por nombre de cada equipo por separado:")
            for nombre in (clave[0], clave[1]):
                filas_con_ese_equipo = [
                    (i, f) for i, f in enumerate(pending_ahora)
                    if _clave(f["equipo_local"], f["equipo_visitante"])[0] == nombre
                    or _clave(f["equipo_local"], f["equipo_visitante"])[1] == nombre
                ]
                print(f"    {nombre!r} aparece en {len(filas_con_ese_equipo)} fila(s) de pending:")
                for i, f in filas_con_ese_equipo[:5]:
                    print(f"      fila #{i}, jornada {f.get('jornada')}: "
                          f"{f['equipo_local']!r} vs {f['equipo_visitante']!r}")
