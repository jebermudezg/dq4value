import pandas as pd
import numpy as np


def _isolation_forest(df, columnas, contamination=0.05):
    """
    Detecta anomalías multivariables usando Isolation Forest.
    Analiza varias columnas numéricas en conjunto.
    contamination: proporción esperada de anomalías (0.01 a 0.20)
    Retorna una máscara booleana: True = anomalía
    """
    from sklearn.ensemble import IsolationForest
    datos = df[columnas].copy()
    idx_originales = datos.index
    datos_limpios = datos.dropna()
    if len(datos_limpios) < 10:
        return pd.Series(False, index=idx_originales)
    modelo = IsolationForest(
        contamination=contamination,
        random_state=42,
        n_estimators=100
    )
    predicciones = modelo.fit_predict(datos_limpios)
    mascara = pd.Series(False, index=idx_originales)
    mascara[datos_limpios.index] = predicciones == -1
    return mascara


def check_razonabilidad(df: pd.DataFrame, id_col: str, target_col: str, **params) -> tuple[float, pd.DataFrame]:
    """
    Detecta valores estadísticamente anómalos.
    metodo='iqr'               → univariable, solo target_col (default)
    metodo='isolation_forest'  → multivariable, analiza columnas_if en conjunto
    """
    metodo = params.get('metodo', 'iqr')

    if metodo == 'isolation_forest':
        columnas_if = params.get('columnas_if') or []
        contamination = float(params.get('contamination', 0.05))

        if not columnas_if or len(columnas_if) < 2:
            return check_razonabilidad(df, id_col, target_col, metodo='iqr')

        # Columnas para el modelo IF (las seleccionadas por el usuario, validadas)
        cols_para_analisis = [c for c in columnas_if
                              if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        if len(cols_para_analisis) < 2:
            return check_razonabilidad(df, id_col, target_col, metodo='iqr')

        # Columnas para mostrar en valor_encontrado: target_col siempre primero, sin duplicados
        cols_para_mostrar = list(dict.fromkeys([target_col] + cols_para_analisis))

        mascara_anomalias = _isolation_forest(df, cols_para_analisis, contamination)
        issues = df[mascara_anomalias].copy()

        if len(issues) == 0:
            return 100.0, _empty_issues(id_col), {}

        import json

        # Stats IQR para todas las columnas que se muestran
        cols_para_stats = list(set(cols_para_analisis + [target_col]))
        stats = {}
        for col in cols_para_stats:
            if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
                stats[col] = {
                    'p10': df[col].quantile(0.10),
                    'p90': df[col].quantile(0.90),
                }

        def _construir_valor_if(row):
            campos = []
            for col in cols_para_mostrar:
                val = row[col] if col in row.index else None
                es_inusual = (
                    val is not None and not pd.isna(val) and col in stats and
                    (val < stats[col]['p10'] or val > stats[col]['p90'])
                )
                campos.append({
                    'campo': col,
                    'valor': round(float(val), 2) if val is not None and not pd.isna(val) else None,
                    'inusual': bool(es_inusual),
                })
            return json.dumps(campos, ensure_ascii=False)

        issues_df = pd.DataFrame({
            id_col: issues[id_col].astype(str),
            'columna': target_col,
            'dimension': 'razonabilidad',
            'descripcion': 'Anomalía multivariable — combinación inusual de valores detectada por Isolation Forest',
            'valor_encontrado': [_construir_valor_if(row) for _, row in issues.iterrows()],
        })

        total = len(df.dropna(subset=[target_col]))
        score = round((1 - len(issues) / total) * 100, 1) if total > 0 else 100.0
        return score, issues_df.reset_index(drop=True), {}

    # ── IQR original ───────────────────────────────────────────────────
    iqr_factor = float(params.get("iqr_factor", 1.5))

    total = len(df)
    if total == 0:
        return 100.0, _empty_issues(id_col), {}

    col_num = pd.to_numeric(df[target_col], errors="coerce")
    col_valida = col_num.dropna()

    if col_valida.empty or col_valida.nunique() <= 1:
        return 100.0, _empty_issues(id_col), {}

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

    return round(score, 2), issues_df.reset_index(drop=True), {}


def _empty_issues(id_col: str) -> pd.DataFrame:
    return pd.DataFrame(columns=[id_col, "columna", "dimension", "descripcion", "valor_encontrado"])
