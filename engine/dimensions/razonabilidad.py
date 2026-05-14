import pandas as pd


def check_razonabilidad(df: pd.DataFrame, id_col: str, target_col: str, **params) -> tuple[float, pd.DataFrame]:
    """
    Detecta outliers estadísticos usando el método IQR.
    Marca como sospechosos los valores fuera de [Q1 - 1.5*IQR, Q3 + 1.5*IQR].
    Score = % de valores dentro del rango razonable.
    El multiplicador IQR es configurable con el parámetro iqr_factor (default 1.5).
    """
    iqr_factor = float(params.get("iqr_factor", 1.5))

    total = len(df)
    if total == 0:
        return 100.0, _empty_issues(id_col)

    col_num = pd.to_numeric(df[target_col], errors="coerce")
    col_valida = col_num.dropna()

    if col_valida.empty or col_valida.nunique() <= 1:
        # Sin variación no hay outliers definibles
        return 100.0, _empty_issues(id_col)

    q1 = col_valida.quantile(0.25)
    q3 = col_valida.quantile(0.75)
    iqr = q3 - q1

    limite_inferior = q1 - iqr_factor * iqr
    limite_superior = q3 + iqr_factor * iqr

    outlier_mask = ((col_num < limite_inferior) | (col_num > limite_superior)) & df[target_col].notna()
    n_normales = total - outlier_mask.sum()
    score = (n_normales / total) * 100

    issues_df = df[outlier_mask][[id_col]].copy()
    issues_df["valor_encontrado"] = df.loc[outlier_mask, target_col].values
    issues_df["columna"] = target_col
    issues_df["dimension"] = "razonabilidad"
    issues_df["descripcion"] = (
        f"Valor fuera del rango IQR (rango razonable: "
        f"[{limite_inferior:.2f}, {limite_superior:.2f}])"
    )

    return round(score, 2), issues_df.reset_index(drop=True)


def _empty_issues(id_col: str) -> pd.DataFrame:
    return pd.DataFrame(columns=[id_col, "columna", "dimension", "descripcion", "valor_encontrado"])
