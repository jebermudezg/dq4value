import pandas as pd


def check_vigencia(df: pd.DataFrame, id_col: str, target_col: str, **params) -> tuple[float, pd.DataFrame]:
    """
    Para columnas de fecha: detecta registros fuera del rango (date_from, date_to).
    Para otros campos: detecta valores que coincidan con obsolete_values (lista).
    Si no se pasan parámetros relevantes, score = 100.
    """
    date_from = params.get("date_from")
    date_to = params.get("date_to")
    obsolete_values = params.get("obsolete_values")

    total = len(df)
    if total == 0:
        return 100.0, _empty_issues(id_col)

    # --- Modo fecha ---
    if date_from is not None or date_to is not None:
        col_dt = pd.to_datetime(df[target_col], errors="coerce")
        invalidos_mask = pd.Series(False, index=df.index)
        partes = []

        if date_from is not None:
            dt_from = pd.to_datetime(date_from)
            invalidos_mask |= col_dt < dt_from
            partes.append(f"desde {date_from}")
        if date_to is not None:
            dt_to = pd.to_datetime(date_to)
            invalidos_mask |= col_dt > dt_to
            partes.append(f"hasta {date_to}")

        # Excluir nulos del conteo de inválidos (la completitud los cubre)
        invalidos_mask &= df[target_col].notna()
        descripcion = f"Fecha fuera del rango vigente ({', '.join(partes)})"

    # --- Modo valores obsoletos ---
    elif obsolete_values is not None:
        obs_set = {str(v) for v in obsolete_values}
        invalidos_mask = df[target_col].astype(str).isin(obs_set) & df[target_col].notna()
        descripcion = "Valor marcado como obsoleto"

    else:
        return 100.0, _empty_issues(id_col)

    n_validos = total - invalidos_mask.sum()
    score = (n_validos / total) * 100

    issues_df = df[invalidos_mask][[id_col]].copy()
    issues_df["valor_encontrado"] = df.loc[invalidos_mask, target_col].values
    issues_df["columna"] = target_col
    issues_df["dimension"] = "vigencia"
    issues_df["descripcion"] = descripcion

    return round(score, 2), issues_df.reset_index(drop=True)


def _empty_issues(id_col: str) -> pd.DataFrame:
    return pd.DataFrame(columns=[id_col, "columna", "dimension", "descripcion", "valor_encontrado"])
