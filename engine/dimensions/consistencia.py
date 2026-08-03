import re
import pandas as pd


# Patrones para detectar distintos formatos de fecha
_DATE_PATTERNS = {
    "DD/MM/YYYY": re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    "MM/DD/YYYY": re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    "YYYY-MM-DD": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    "DD-MM-YYYY": re.compile(r"^\d{2}-\d{2}-\d{4}$"),
    "DD.MM.YYYY": re.compile(r"^\d{2}\.\d{2}\.\d{4}$"),
}

_CURRENCY_PATTERN = re.compile(r"^[\$€£¥]?\s*[\d,]+(\.\d+)?$")
_PLAIN_NUMBER_PATTERN = re.compile(r"^[\d,]+(\.\d+)?$")


def check_consistencia(df: pd.DataFrame, id_col: str, target_col: str, **params) -> tuple[float, pd.DataFrame]:
    """
    Detecta mezcla de formatos en la misma columna:
    - Fechas en distintos formatos
    - Números con y sin símbolo de moneda
    - Texto con capitalización inconsistente (mayúsculas vs minúsculas mezcladas)
    """
    total = len(df)
    if total == 0:
        return 100.0, _empty_issues(id_col), {}

    col_clean = df[target_col].dropna().astype(str).str.strip()
    if col_clean.empty:
        return 100.0, _empty_issues(id_col), {}

    issues_rows = []

    # --- Detectar mezcla de formatos de fecha ---
    date_format_hits = {name: col_clean.apply(lambda v: bool(p.match(v))).sum()
                        for name, p in _DATE_PATTERNS.items()}
    active_date_formats = [k for k, v in date_format_hits.items() if v > 0]
    # YYYY-MM-DD y DD/MM/YYYY son claramente distintos; los demás solapan dd/mm
    unique_separators = {_separator(fmt) for fmt in active_date_formats}
    if len(unique_separators) > 1:
        mask = df[target_col].notna()
        for _, row in df[mask].iterrows():
            issues_rows.append(_issue(id_col, row[id_col], target_col, "consistencia",
                                      "Mezcla de formatos de fecha en la columna",
                                      str(row[target_col])))

    # --- Detectar mezcla de número con/sin símbolo de moneda ---
    has_currency = col_clean.apply(lambda v: bool(_CURRENCY_PATTERN.match(v)) and not bool(_PLAIN_NUMBER_PATTERN.match(v)))
    has_plain = col_clean.apply(lambda v: bool(_PLAIN_NUMBER_PATTERN.match(v)))
    if has_currency.any() and has_plain.any():
        currency_idx = has_currency[has_currency].index
        for idx in currency_idx:
            row = df.loc[idx]
            issues_rows.append(_issue(id_col, row[id_col], target_col, "consistencia",
                                      "Número con símbolo de moneda mezclado con números sin símbolo",
                                      str(row[target_col])))

    # --- Detectar capitalización inconsistente en texto ---
    text_vals = col_clean[~col_clean.str.match(r"^[\d\$€£¥\.\,\-\/\s]+$")]
    if len(text_vals) > 1:
        has_upper = text_vals.str.isupper().any()
        has_lower = text_vals.str.islower().any()
        has_title = text_vals.apply(lambda v: v.istitle()).any()
        formats_present = sum([has_upper, has_lower, has_title])
        if formats_present > 1:
            for idx in text_vals.index:
                row = df.loc[idx]
                issues_rows.append(_issue(id_col, row[id_col], target_col, "consistencia",
                                          "Capitalización inconsistente (mayúsculas/minúsculas mezcladas)",
                                          str(row[target_col])))

    if not issues_rows:
        return 100.0, _empty_issues(id_col), {}

    issues_df = pd.DataFrame(issues_rows).drop_duplicates(subset=[id_col])
    n_afectados = len(issues_df)
    score = max(0.0, ((total - n_afectados) / total) * 100)

    return round(score, 2), issues_df.reset_index(drop=True), {}


def _separator(fmt: str) -> str:
    for ch in ["/", "-", "."]:
        if ch in fmt:
            return ch
    return "?"


def _issue(id_col_name: str, id_val, col: str, dim: str, desc: str, valor: str) -> dict:
    return {id_col_name: id_val, "columna": col, "dimension": dim,
            "descripcion": desc, "valor_encontrado": valor}


def _empty_issues(id_col: str) -> pd.DataFrame:
    return pd.DataFrame(columns=[id_col, "columna", "dimension", "descripcion", "valor_encontrado"])
