# -*- coding: utf-8 -*-
"""
scraper_espn_lpf.py

Fuente ALTERNATIVA a Promiedos para la tabla de posiciones de la LPF:
en vez de reconstruir la tabla partido a partido desde resultados_lpf.csv
(lo que se rompe cuando a Promiedos se le cae un partido de la ventana de
"últimos" que expone -- ver scraper_promiedos_lpf.py y el problema de
"sin identificar"), este scraper trae la tabla YA CALCULADA por ESPN,
directo de su API oculta:

    https://site.api.espn.com/apis/v2/sports/soccer/arg.1/standings

Esa respuesta trae la LPF partida en "Group A"/"Group B" (2026), cada
grupo con su propio "standings.entries": un dict por equipo con id,
nombre, y una lista de stats (gamesPlayed, wins, ties, losses, pointsFor,
pointsAgainst, pointDifferential, points, rank -- rank es la posición
DENTRO del grupo, confirmado con datos reales: 1..15 en cada uno).

⚠️ OJO -- esto es la tabla del CLAUSURA (temporada en curso), NO la del
Apertura. NUNCA hay que volcar esto en datos/tablalpf.csv ni pasarlo a
db.repository.upsert_standings("lpf", ...): esa tabla es la base
HISTÓRICA y CONGELADA del Apertura 2026 que usa EstadisticasLPF como
self.apertura (ver el comentario grande en actualizar_resultados_lpf.py,
punto 6, y revertir_standings_lpf_apertura.py -- ya pasó una vez que se
pisó por error y hubo que deshacerlo a mano). Esta tabla del Clausura
vive únicamente en memoria / se compara contra main_lpf._tabla_actual_
clausura(), que es la reconstrucción real que ve el frontend.

Mapeo de equipos: por ID numérico de ESPN (más robusto que por nombre --
ESPN usa variantes con paréntesis para desambiguar, ej. "Talleres
(Córdoba)", "Unión (Santa Fe)", que no coinciden ni con el nombre
canónico del proyecto ni con ningún alias ya cargado en
mapeo_equipos_lpf.py). Los 30 IDs de abajo están confirmados contra la
respuesta real de la API (ver ESPN_ID_A_EQUIPO). Si ESPN alguna vez
suma/saca un equipo (ascenso/descenso), va a aparecer como "sin
mapear" en vez de fallar en silencio -- ver `_mapear_entrada`.

Uso:
    python scraper_espn_lpf.py                    # pide la API y muestra la tabla
    python scraper_espn_lpf.py ruta/al/archivo.json  # parsea un JSON ya guardado (sin red)

Uso programático:
    from scraper_espn_lpf import obtener_tabla_clausura_espn
    tabla = obtener_tabla_clausura_espn()  # {"A": [...], "B": [...]}
"""
import json
import sys
import urllib.error
import urllib.request

BASE_URL = "https://site.api.espn.com/apis/v2/sports/soccer/arg.1/standings"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-AR,es;q=0.9,en-US;q=0.8,en;q=0.7",
    # ESPN devolvía 403 solo con User-Agent + Accept -- agregando estos
    # (Referer/Origin apuntando a la página real de posiciones, más los
    # sec-fetch-* que manda cualquier navegador en un pedido "fetch" del
    # mismo sitio) es lo que suele destrabar el bloqueo de bot básico de
    # su API oculta. Si con esto SIGUE dando 403, no es un tema de
    # headers sino de fingerprinting a nivel TLS (Akamai/similares
    # detectan que no es un navegador real más allá de los headers que
    # mandes) -- en ese caso no hay arreglo simple del lado de
    # urllib/requests, ver el aviso que imprime `_get_json_desde_red`.
    "Referer": "https://www.espn.com/soccer/standings/_/league/arg.1",
    "Origin": "https://www.espn.com",
    "sec-fetch-site": "same-site",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
}
TIMEOUT = 20

# id ESPN (team.id) -> nombre CANÓNICO LARGO del proyecto (el mismo que
# devuelve mapeo_equipos_lpf.resolver_equipo_lpf() / EQUIPOS_LPF, y el
# mismo que queda en e.apertura["equipo"] después de normalizar() en
# modelos/estadisticas_lpf.py -- así el resultado de este scraper se
# puede comparar 1 a 1 contra main_lpf._tabla_actual_clausura() sin
# ninguna conversión adicional).
ESPN_ID_A_EQUIPO = {
    # --- Group A / Zona A ---
    "5": "Boca Juniors",
    "8": "Estudiantes de La Plata",
    "11": "Independiente",
    "12": "Lanús",
    "14": "Newell's Old Boys",
    "18": "San Lorenzo",
    "19": "Talleres de Córdoba",
    "20": "Unión de Santa Fe",
    "21": "Vélez Sarsfield",
    "2975": "Instituto",
    "7764": "Platense",
    "8950": "Defensa y Justicia",
    "11972": "Gimnasia de Mendoza",
    "11989": "Central Córdoba SdE",
    "17702": "Deportivo Riestra",
    # --- Group B / Zona B ---
    "3": "Argentinos Juniors",
    "4": "Belgrano",
    "9": "Gimnasia La Plata",
    "10": "Huracán",
    "15": "Racing Club",
    "16": "River Plate",
    "17": "Rosario Central",
    "235": "Banfield",
    "7767": "Tigre",
    "9739": "Aldosivi",
    "9744": "Independiente Rivadavia",
    "9785": "Atlético Tucumán",
    "10060": "Barracas Central",
    "10158": "Sarmiento Junín",
    "19685": "Estudiantes RC",
}

# Nombre de grupo de ESPN -> zona del proyecto. Confirmado que la
# composición de cada grupo coincide 1 a 1 con la zona A/B ya cargada en
# datos/tablalpf.csv (mismos 15+15 equipos) -- así que esto no debería
# cambiar nunca salvo que ESPN reordene los grupos, cosa que este script
# igual detectaría (rompería el chequeo de 15+15 en `_validar`).
GRUPO_A_ZONA = {
    "Group A": "A",
    "Group B": "B",
}

CAMPOS_STAT = {
    "gamesPlayed": "partidos_jugados",
    "wins": "ganados",
    "ties": "empatados",
    "losses": "perdidos",
    "pointsFor": "gf",
    "pointsAgainst": "gc",
    "pointDifferential": "dg",
    "points": "puntos",
    "rank": "posicion",
}


def _get_json_desde_red():
    req = urllib.request.Request(BASE_URL, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        # Se loguea el cuerpo del error (si trae algo) para poder
        # distinguir un bloqueo de bot genérico de otra cosa (rate
        # limit, geo-bloqueo, etc.) sin tener que reproducirlo a mano.
        detalle = ""
        try:
            detalle = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        print(f"  [scraper_espn_lpf] HTTP {e.code} de ESPN. Cuerpo (primeros 500 chars): "
              f"{detalle!r}" if detalle else f"  [scraper_espn_lpf] HTTP {e.code} de ESPN, sin cuerpo legible.")
        raise
    return json.loads(body)


def _mapear_entrada(entrada, zona, sin_mapear):
    team = entrada["team"]
    espn_id = str(team["id"])
    equipo = ESPN_ID_A_EQUIPO.get(espn_id)
    if equipo is None:
        sin_mapear.append((espn_id, team.get("displayName", "?")))
        return None

    fila = {"equipo": equipo, "zona": zona}
    for stat in entrada.get("stats", []):
        campo = CAMPOS_STAT.get(stat.get("name"))
        if campo:
            fila[campo] = int(stat["value"])

    faltantes = set(CAMPOS_STAT.values()) - set(fila.keys())
    if faltantes:
        raise ValueError(f"'{equipo}': faltan stats {faltantes} en la respuesta de ESPN")

    return fila


def parsear_standings_espn_lpf(data):
    """data: el JSON crudo devuelto por la API de ESPN (el que arranca
    con "uid": "s:600~l:745", "children": [...]).
    Devuelve {"A": [...], "B": [...]}, cada lista ordenada por posición,
    con el mismo shape de fila que main_lpf._tabla_actual_clausura():
    equipo/zona/partidos_jugados/puntos/gf/gc/dg/posicion, más
    ganados/empatados/perdidos (que _tabla_actual_clausura no trae, pero
    no está de más tenerlos para el diagnóstico).
    """
    tabla = {"A": [], "B": []}
    sin_mapear = []

    for grupo in data.get("children", []):
        nombre_grupo = grupo.get("name", "")
        zona = GRUPO_A_ZONA.get(nombre_grupo)
        if zona is None:
            raise ValueError(
                f"Grupo de ESPN sin mapeo a zona: '{nombre_grupo}' -- "
                f"revisá GRUPO_A_ZONA (¿ESPN cambió el nombre del grupo?)."
            )
        entries = grupo.get("standings", {}).get("entries", [])
        for entrada in entries:
            fila = _mapear_entrada(entrada, zona, sin_mapear)
            if fila is not None:
                tabla[zona].append(fila)

    if sin_mapear:
        detalle = ", ".join(f"{nombre} (id={eid})" for eid, nombre in sin_mapear)
        raise ValueError(
            f"{len(sin_mapear)} equipo(s) de la respuesta de ESPN no tienen mapeo en "
            f"ESPN_ID_A_EQUIPO: {detalle}. Agregalos antes de confiar en esta tabla "
            f"(posible ascenso/descenso o cambio de ID de ESPN)."
        )

    for zona in ("A", "B"):
        if len(tabla[zona]) != 15:
            raise ValueError(
                f"Zona {zona}: se esperaban 15 equipos, se mapearon {len(tabla[zona])}. "
                f"Revisar antes de usar esta tabla."
            )
        tabla[zona].sort(key=lambda f: f["posicion"])

    return tabla


def obtener_tabla_clausura_espn(ruta_json=None):
    """Si `ruta_json` viene, parsea ese archivo (sin red -- útil para
    pruebas offline). Si no, pide la API de ESPN en vivo."""
    if ruta_json:
        with open(ruta_json, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = _get_json_desde_red()
    return parsear_standings_espn_lpf(data)


def _imprimir_tabla(tabla):
    for zona in ("A", "B"):
        print(f"\n=== Zona {zona} (ESPN, Clausura) ===")
        print(f"{'Pos':>3} {'Equipo':<28} {'PJ':>3} {'G':>2} {'E':>2} {'P':>2} {'GF':>3} {'GC':>3} {'DG':>4} {'Pts':>4}")
        for f in tabla[zona]:
            print(f"{f['posicion']:>3} {f['equipo']:<28} {f['partidos_jugados']:>3} "
                  f"{f['ganados']:>2} {f['empatados']:>2} {f['perdidos']:>2} "
                  f"{f['gf']:>3} {f['gc']:>3} {f['dg']:>4} {f['puntos']:>4}")


def main():
    ruta_json = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        if ruta_json:
            print(f"Parseando {ruta_json} (sin red)...")
        else:
            print(f"Pidiendo {BASE_URL} ...")
        tabla = obtener_tabla_clausura_espn(ruta_json)
    except (urllib.error.URLError, ValueError, KeyError) as e:
        print(f"ERROR: {e}")
        return

    _imprimir_tabla(tabla)
    print(f"\nOK -- 30 equipos (15+15), tabla del Clausura según ESPN. "
          f"Para comparar contra la tabla real (resultados_lpf.csv), correr "
          f"comparar_tabla_espn_lpf.py.")


if __name__ == "__main__":
    main()
