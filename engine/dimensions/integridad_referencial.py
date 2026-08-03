import pandas as pd


def check_integridad_referencial(df: pd.DataFrame, id_col: str, target_col: str, **params) -> tuple[float, pd.DataFrame]:
    """
    Verifica que los valores de target_col existan en reference_ids.
    Score = % de valores que sí existen en la referencia.
    Requiere parámetro: reference_ids (list).
    """
    reference_ids = params.get("reference_ids")

    total = len(df)
    if total == 0 or reference_ids is None:
        return 100.0, _empty_issues(id_col), {}

    ref_set = {str(v) for v in reference_ids}
    col_str = df[target_col].astype(str)
    invalidos_mask = ~col_str.isin(ref_set) & df[target_col].notna()

    n_validos = total - invalidos_mask.sum()
    score = (n_validos / total) * 100

    issues_df = df[invalidos_mask][[id_col]].copy()
    issues_df["valor_encontrado"] = df.loc[invalidos_mask, target_col].values
    issues_df["columna"] = target_col
    issues_df["dimension"] = "integridad_referencial"
    issues_df["descripcion"] = "Valor no encontrado en la tabla de referencia"

    return round(score, 2), issues_df.reset_index(drop=True), {}


def _empty_issues(id_col: str) -> pd.DataFrame:
    return pd.DataFrame(columns=[id_col, "columna", "dimension", "descripcion", "valor_encontrado"])
