import pandas as pd


def check_precision(df: pd.DataFrame, id_col: str, target_col: str, **params) -> tuple[float, pd.DataFrame]:
    """
    Para números: verifica que tengan exactamente decimal_places decimales.
    Para texto: verifica que la longitud esté entre min_length y max_length.
    Si no se pasan parámetros, score = 100.
    """
    decimal_places = params.get("decimal_places")
    min_length = params.get("min_length")
    max_length = params.get("max_length")

    total = len(df)
    if total == 0 or (decimal_places is None and min_length is None and max_length is None):
        return 100.0, _empty_issues(id_col), {}

    col_notnull = df[target_col].notna()
    invalidos_mask = pd.Series(False, index=df.index)
    descripcion = ""

    if decimal_places is not None:
        col_num = pd.to_numeric(df[target_col], errors="coerce")
        # Contar decimales reales multiplicando y verificando parte entera
        factor = 10 ** decimal_places
        invalidos_mask = ((col_num * factor) % 1 != 0) & col_notnull
        descripcion = f"Número no tiene exactamente {decimal_places} decimal(es)"
    else:
        col_str = df[target_col].astype(str)
        lengths = col_str.str.len()
        fuera = pd.Series(False, index=df.index)
        partes = []
        if min_length is not None:
            fuera |= lengths < min_length
            partes.append(f"mínimo {min_length} caracteres")
        if max_length is not None:
            fuera |= lengths > max_length
            partes.append(f"máximo {max_length} caracteres")
        invalidos_mask = fuera & col_notnull
        descripcion = f"Longitud de texto fuera del rango ({', '.join(partes)})"

    n_validos = total - invalidos_mask.sum()
    score = (n_validos / total) * 100

    issues_df = df[invalidos_mask][[id_col]].copy()
    issues_df["valor_encontrado"] = df.loc[invalidos_mask, target_col].values
    issues_df["columna"] = target_col
    issues_df["dimension"] = "precision"
    issues_df["descripcion"] = descripcion

    return round(score, 2), issues_df.reset_index(drop=True), {}


def _empty_issues(id_col: str) -> pd.DataFrame:
    return pd.DataFrame(columns=[id_col, "columna", "dimension", "descripcion", "valor_encontrado"])
