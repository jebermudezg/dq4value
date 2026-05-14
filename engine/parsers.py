# Parsers para leer archivos CSV, Excel (.xlsx, .xls) y convertirlos a DataFrames de pandas

import pandas as pd
from pathlib import Path


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".txt"}
CHUNK_ROW_THRESHOLD   = 50_000
CHUNK_SIZE            = 10_000


def parse_file(file_path: str) -> tuple[pd.DataFrame, list[str]]:
    """
    Lee un archivo CSV, Excel o TXT y lo convierte en un DataFrame.
    Para CSV/TXT con más de 50 000 filas usa lectura en chunks de 10 000 filas.

    Returns:
        (DataFrame, lista de nombres de columnas)

    Raises:
        ValueError: si el formato no es compatible o el archivo está vacío
        FileNotFoundError: si la ruta no existe
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {file_path}")

    if not path.is_file():
        raise ValueError(f"La ruta proporcionada no es un archivo: {file_path}")

    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Formato '{extension}' no compatible. "
            f"Formatos aceptados: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    try:
        if extension == ".xlsx":
            df = _parse_excel(path, engine="openpyxl")
        elif extension == ".xls":
            df = _parse_excel(path, engine="xlrd")
        elif extension in {".csv", ".txt"}:
            row_estimate = _count_lines(path)
            use_chunks   = row_estimate > CHUNK_ROW_THRESHOLD
            df = _parse_text(path, chunksize=CHUNK_SIZE if use_chunks else None)
        else:
            raise ValueError(f"Formato inesperado: {extension}")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"No se pudo leer el archivo '{path.name}': {e}") from e

    if df.empty:
        raise ValueError(f"El archivo '{path.name}' está vacío o no contiene datos válidos.")

    df.columns = [str(col).strip() for col in df.columns]
    df = df.reset_index(drop=True)

    return df, list(df.columns)


def _count_lines(path: Path) -> int:
    """Cuenta líneas del archivo restando la cabecera; rápido (lee bytes)."""
    count = 0
    with open(path, "rb") as f:
        for _ in f:
            count += 1
    return max(0, count - 1)


def _detect_sep(path: Path) -> str:
    """Detecta el separador leyendo solo la primera línea del archivo."""
    separators = [",", "\t", ";"]
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            first_line = f.readline()
        counts = {sep: first_line.count(sep) for sep in separators}
        best = max(counts, key=counts.get)
        return best if counts[best] > 0 else ","
    except Exception:
        return ","


def _parse_excel(path: Path, engine: str) -> pd.DataFrame:
    try:
        df = pd.read_excel(path, engine=engine)
    except Exception as e:
        raise ValueError(f"Error al leer el archivo Excel '{path.name}': {e}") from e
    return df


def _parse_text(path: Path, chunksize: int = None) -> pd.DataFrame:
    """
    Detecta el separador y lee el archivo. Si chunksize está definido,
    lee en bloques y los concatena para evitar cargar todo en RAM de una vez.
    """
    sep = _detect_sep(path)

    try:
        if chunksize:
            chunks = pd.read_csv(path, sep=sep, engine="python", chunksize=chunksize)
            df = pd.concat(chunks, ignore_index=True)
        else:
            df = pd.read_csv(path, sep=sep, engine="python")

        # Si solo produjo una columna puede que el separador sea incorrecto
        if len(df.columns) == 1:
            for alt_sep in [",", "\t", ";"]:
                if alt_sep == sep:
                    continue
                try:
                    if chunksize:
                        chunks = pd.read_csv(path, sep=alt_sep, engine="python", chunksize=chunksize)
                        alt_df = pd.concat(chunks, ignore_index=True)
                    else:
                        alt_df = pd.read_csv(path, sep=alt_sep, engine="python")
                    if len(alt_df.columns) > 1:
                        return alt_df
                except Exception:
                    continue
        return df

    except Exception as e:
        raise ValueError(
            f"No se pudo leer el archivo '{path.name}'. "
            f"Asegúrate de que usa coma, tabulación o punto y coma. Detalle: {e}"
        ) from e


def get_column_info(df: pd.DataFrame) -> list[dict]:
    """
    Devuelve metadatos básicos de cada columna del DataFrame.

    Returns:
        Lista de dicts con: nombre, tipo_dato, total_registros, valores_nulos
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("El argumento debe ser un DataFrame de pandas.")

    total_rows = len(df)
    info = []

    for col in df.columns:
        null_count = int(df[col].isna().sum())
        entry: dict = {
            "nombre": col,
            "tipo_dato": str(df[col].dtype),
            "total_registros": total_rows,
            "valores_nulos": null_count,
        }
        if pd.api.types.is_numeric_dtype(df[col]):
            col_data = df[col].dropna()
            if len(col_data) > 0:
                entry["min_val"] = round(float(col_data.min()), 4)
                entry["max_val"] = round(float(col_data.max()), 4)
                entry["p5"]  = round(float(col_data.quantile(0.05)), 4)
                entry["p95"] = round(float(col_data.quantile(0.95)), 4)
        info.append(entry)

    return info
