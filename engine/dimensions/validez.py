import re
import pandas as pd


def check_validez(df: pd.DataFrame, id_col: str, target_col: str, **params) -> tuple[float, pd.DataFrame]:
    """
    Valida valores contra una lista permitida (valid_values) o un regex (regex_pattern).
    Si no se pasa ninguno, score = 100.
    """
    valid_values = params.get("valid_values")
    regex_pattern = params.get("regex_pattern")

    total = len(df)
    if total == 0 or (valid_values is None and regex_pattern is None):
        return 100.0, _empty_issues(id_col), {}

    col = df[target_col].astype(str)

    if valid_values is not None:
        valid_set = {str(v) for v in valid_values}
        invalidos_mask = ~col.isin(valid_set) & df[target_col].notna()
    else:
        pattern = re.compile(regex_pattern)
        invalidos_mask = ~col.apply(lambda v: bool(pattern.fullmatch(v))) & df[target_col].notna()

    n_validos = total - invalidos_mask.sum()
    score = (n_validos / total) * 100

    issues_df = df[invalidos_mask][[id_col]].copy()
    issues_df["valor_encontrado"] = df.loc[invalidos_mask, target_col].values
    issues_df["columna"] = target_col
    issues_df["dimension"] = "validez"

    if valid_values is not None:
        issues_df["descripcion"] = issues_df["valor_encontrado"].apply(
            lambda v: f"Valor '{v}' no está en la lista de valores permitidos"
        )
    else:
        issues_df["descripcion"] = issues_df["valor_encontrado"].apply(
            lambda v: f"Formato inválido: {v}"
        )

    return round(score, 2), issues_df.reset_index(drop=True), {}


def _empty_issues(id_col: str) -> pd.DataFrame:
    return pd.DataFrame(columns=[id_col, "columna", "dimension", "descripcion", "valor_encontrado"])
