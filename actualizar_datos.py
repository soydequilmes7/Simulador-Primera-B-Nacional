"""
actualizar_datos.py

Punto único de entrada para obtener los datos de la temporada
(resultados, fixture y tabla) y dejarlos disponibles en datos/*.csv.

Estado actual: fuente LOCAL/MANUAL.
El usuario carga o edita directamente los archivos en datos/,
y este módulo se limita a validar que existan y tengan las
columnas esperadas antes de que el resto del proyecto los use.

Cuando se incorpore una fuente automática (API o scraping),
solo debe modificarse la implementación interna de las funciones
descargar_*() — el resto del proyecto no debe cambiar.
"""

from pathlib import Path
import pandas as pd
from typing import Final

# --- Configuración de rutas y esquemas esperados -----------------

DATOS_DIR: Final[Path] = Path(__file__).resolve().parent / "datos"

RUTA_RESULTADOS: Final[Path] = DATOS_DIR / "resultados.csv"
RUTA_FIXTURE: Final[Path] = DATOS_DIR / "fixture.csv"
RUTA_TABLA: Final[Path] = DATOS_DIR / "tabla.csv"

COLUMNAS_RESULTADOS: Final[list[str]] = [
    "fecha", "jornada", "equipo_local", "equipo_visitante",
    "goles_local", "goles_visitante",
]

COLUMNAS_FIXTURE: Final[list[str]] = [
    "fecha", "jornada", "equipo_local", "equipo_visitante",
]

COLUMNAS_TABLA: Final[list[str]] = [
    "posicion", "equipo", "partidos_jugados", "ganados",
    "empatados", "perdidos", "gf", "gc", "dg", "puntos",
]


def _validar_csv_existe(ruta: Path) -> None:
    """Lanza un error claro si el archivo de datos no existe."""
    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encontró '{ruta}'. "
            f"Por ahora la fuente de datos es manual: cargá el archivo "
            f"con las columnas correctas antes de continuar."
        )


def _validar_columnas(df: pd.DataFrame, columnas_esperadas: list[str], nombre_archivo: str) -> None:
    """Verifica que el CSV tenga exactamente las columnas esperadas."""
    columnas_faltantes = set(columnas_esperadas) - set(df.columns)
    if columnas_faltantes:
        raise ValueError(
            f"'{nombre_archivo}' no tiene las columnas requeridas. "
            f"Faltan: {sorted(columnas_faltantes)}"
        )


def descargar_resultados() -> pd.DataFrame:
    """
    Obtiene los resultados de la temporada.

    Fuente actual: lectura local de datos/resultados.csv.
    """
    _validar_csv_existe(RUTA_RESULTADOS)
    df = pd.read_csv(RUTA_RESULTADOS)
    _validar_columnas(df, COLUMNAS_RESULTADOS, "resultados.csv")
    return df


def descargar_fixture() -> pd.DataFrame:
    """
    Obtiene el fixture (partidos restantes) de la temporada.

    Fuente actual: lectura local de datos/fixture.csv.
    """
    _validar_csv_existe(RUTA_FIXTURE)
    df = pd.read_csv(RUTA_FIXTURE)
    _validar_columnas(df, COLUMNAS_FIXTURE, "fixture.csv")
    return df


def descargar_tabla() -> pd.DataFrame:
    """
    Obtiene la tabla de posiciones actual.

    Fuente actual: lectura local de datos/tabla.csv.
    """
    _validar_csv_existe(RUTA_TABLA)
    df = pd.read_csv(RUTA_TABLA)
    _validar_columnas(df, COLUMNAS_TABLA, "tabla.csv")
    return df


def actualizar_datos() -> None:
    """
    Punto de entrada principal: valida que los tres archivos de datos
    estén presentes y bien formados.

    Hoy no "descarga" nada externo; simplemente confirma que los CSV
    cargados manualmente sean válidos para el resto del simulador.
    """
    print("Validando datos/resultados.csv...")
    descargar_resultados()

    print("Validando datos/fixture.csv...")
    descargar_fixture()

    print("Validando datos/tabla.csv...")
    descargar_tabla()

    print("Datos OK. Listos para usar en el simulador.")


if __name__ == "__main__":
    actualizar_datos()