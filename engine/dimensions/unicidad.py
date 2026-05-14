import pandas as pd


def check_unicidad(df: pd.DataFrame, id_col: str, target_col: str, **params) -> tuple[float, pd.DataFrame]:
    """
    Mide si hay valores duplicados en target_col.
    Score = (registros únicos / total) * 100
    Reporta los IDs cuyo valor en target_col está duplicado.
    """
    total = len(df)
    if total == 0:
        return 100.0, _empty_issues(id_col)

    duplicados_mask = df[target_col].duplicated(keep=False)
    n_unicos = (~duplicados_mask).sum()
    score = (n_unicos / total) * 100

    issues_df = df[duplicados_mask][[id_col]].copy()
    issues_df["valor_encontrado"] = df.loc[duplicados_mask, target_col].values
    issues_df["columna"] = target_col
    issues_df["dimension"] = "unicidad"
    issues_df["descripcion"] = "Valor duplicado en la columna"

    return round(score, 2), issues_df.reset_index(drop=True)


def _empty_issues(id_col: str) -> pd.DataFrame:
    return pd.DataFrame(columns=[id_col, "columna", "dimension", "descripcion", "valor_encontrado"])
