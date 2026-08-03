import pandas as pd
from datetime import datetime, timezone


def check_oportunidad(df: pd.DataFrame, id_col: str, target_col: str, **params) -> tuple[float, pd.DataFrame]:
    """
    Calcula cuántos registros tienen una fecha más antigua que max_age_days días.
    Score = % de registros cuya fecha está dentro del rango esperado.
    Requiere parámetro: max_age_days (int).
    """
    max_age_days = params.get("max_age_days")

    total = len(df)
    if total == 0 or max_age_days is None:
        return 100.0, _empty_issues(id_col), {}

    col_dt = pd.to_datetime(df[target_col], errors="coerce")
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    limite = ahora - pd.Timedelta(days=int(max_age_days))

    # Registros con fecha anterior al límite son "no oportunos"
    no_oportunos_mask = (col_dt < limite) & df[target_col].notna()
    n_oportunos = total - no_oportunos_mask.sum()
    score = (n_oportunos / total) * 100

    issues_df = df[no_oportunos_mask][[id_col]].copy()
    issues_df["valor_encontrado"] = df.loc[no_oportunos_mask, target_col].values
    issues_df["columna"] = target_col
    issues_df["dimension"] = "oportunidad"
    issues_df["descripcion"] = f"Fecha más antigua que {max_age_days} días (límite: {limite.date()})"

    return round(score, 2), issues_df.reset_index(drop=True), {}


def _empty_issues(id_col: str) -> pd.DataFrame:
    return pd.DataFrame(columns=[id_col, "columna", "dimension", "descripcion", "valor_encontrado"])
