import pandas as pd


def check_exactitud(df: pd.DataFrame, id_col: str, target_col: str, **params) -> tuple[float, pd.DataFrame]:
    """
    Compara valores contra:
    - Rango numérico: parámetros min_value y/o max_value
    - Lista de referencia: parámetro reference_list
    Si no se pasa ninguno, score = 100.
    """
    min_value = params.get("min_value")
    max_value = params.get("max_value")
    reference_list = params.get("reference_list")

    total = len(df)
    if total == 0 or (min_value is None and max_value is None and reference_list is None):
        return 100.0, _empty_issues(id_col), {}

    invalidos_mask = pd.Series(False, index=df.index)
    descripcion = ""

    if reference_list is not None:
        ref_set = {str(v) for v in reference_list}
        invalidos_mask = ~df[target_col].astype(str).isin(ref_set) & df[target_col].notna()
        descripcion = "Valor no encontrado en la lista de referencia"
    else:
        col_num = pd.to_numeric(df[target_col], errors="coerce")
        fuera_de_rango = pd.Series(False, index=df.index)
        partes = []
        if min_value is not None:
            fuera_de_rango |= col_num < min_value
            partes.append(f"mínimo={min_value}")
        if max_value is not None:
            fuera_de_rango |= col_num > max_value
            partes.append(f"máximo={max_value}")
        invalidos_mask = fuera_de_rango & df[target_col].notna()
        descripcion = f"Valor fuera del rango permitido ({', '.join(partes)})"

    n_validos = total - invalidos_mask.sum()
    score = (n_validos / total) * 100

    issues_df = df[invalidos_mask][[id_col]].copy()
    issues_df["valor_encontrado"] = df.loc[invalidos_mask, target_col].values
    issues_df["columna"] = target_col
    issues_df["dimension"] = "exactitud"
    issues_df["descripcion"] = descripcion

    return round(score, 2), issues_df.reset_index(drop=True), {}


def _empty_issues(id_col: str) -> pd.DataFrame:
    return pd.DataFrame(columns=[id_col, "columna", "dimension", "descripcion", "valor_encontrado"])
