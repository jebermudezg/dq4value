import pandas as pd


def check_completitud(df: pd.DataFrame, id_col: str, target_col: str, **params) -> tuple[float, pd.DataFrame]:
    """
    Mide el porcentaje de valores no nulos en target_col.
    Score = (registros no nulos / total) * 100
    """
    total = len(df)
    if total == 0:
        return 100.0, _empty_issues(id_col)

    nulos = df[target_col].isna()
    score = (nulos.value_counts().get(False, 0) / total) * 100

    issues_df = df[nulos][[id_col]].copy()
    issues_df["columna"] = target_col
    issues_df["dimension"] = "completitud"
    issues_df["descripcion"] = "Valor nulo o ausente"
    issues_df["valor_encontrado"] = None

    return round(score, 2), issues_df.reset_index(drop=True)


def _empty_issues(id_col: str) -> pd.DataFrame:
    return pd.DataFrame(columns=[id_col, "columna", "dimension", "descripcion", "valor_encontrado"])
