import re
from typing import Optional
import pandas as pd


# ── Detectores de formato de fecha ────────────────────────────────────────────
# Orden importa: poner el más específico primero para evitar ambigüedades.
_DATE_PATTERNS = [
    ("YYYY-MM-DD", re.compile(r"^\d{4}-\d{2}-\d{2}$")),
    ("DD-MM-YYYY", re.compile(r"^\d{2}-\d{2}-\d{4}$")),
    ("DD/MM/YYYY", re.compile(r"^\d{2}/\d{2}/\d{4}$")),   # cubre MM/DD/YYYY también
    ("DD.MM.YYYY", re.compile(r"^\d{2}\.\d{2}\.\d{4}$")),
]

_CURRENCY_RE  = re.compile(r"^[\$€£¥]\s*[\d,]+(\.\d+)?$")
_PLAIN_NUM_RE = re.compile(r"^[\d,]+(\.\d+)?$")


def _detect_date_fmt(v: str) -> Optional[str]:
    """Devuelve el nombre del patrón de fecha que coincide, o None."""
    for name, p in _DATE_PATTERNS:
        if p.match(v):
            return name
    return None


def _detect_casing(v: str) -> str:
    if v.isupper():   return "UPPER"
    if v.islower():   return "lower"
    if v.istitle():   return "Title"
    return "mixed"


def check_consistencia(
    df: pd.DataFrame, id_col: str, target_col: str, **params
) -> tuple[float, pd.DataFrame, dict]:
    """
    Detecta mezcla de formatos en la misma columna.

    Lógica de mayoría/minoría:
    - Identifica el patrón más frecuente (fecha, moneda, capitalización).
    - Reporta SOLO los registros que pertenecen al patrón minoritario.
    - Score = (registros con patrón mayoritario / total evaluados) × 100.

    Tipos detectados:
      1. Fechas en distintos formatos (ej: YYYY-MM-DD vs DD/MM/YYYY)
      2. Números con y sin símbolo de moneda
      3. Capitalización inconsistente (solo si la minoría es < 10%)
    """
    total = len(df)
    if total == 0:
        return 100.0, _empty_issues(id_col), {}

    valid = df[df[target_col].notna()].copy()
    col_str = valid[target_col].astype(str).str.strip()

    if col_str.empty:
        return 100.0, _empty_issues(id_col), {}

    # Índices del df original donde hay issues (set para deduplicar)
    minority_idx: dict[int, str] = {}   # original-index → descripción

    # ── 1. Formatos de fecha ───────────────────────────────────────────────────
    date_labels = col_str.map(_detect_date_fmt)      # NaN cuando no es fecha
    dated = date_labels.dropna()

    # Solo aplica cuando ≥ 30 % de los valores no-nulos parecen fechas
    if len(dated) >= len(col_str) * 0.30:
        counts = dated.value_counts()
        if len(counts) > 1:
            majority_fmt = counts.index[0]
            for idx in dated[dated != majority_fmt].index:
                minority_idx[idx] = (
                    f"Formato de fecha inconsistente — "
                    f"el patrón mayoritario de la columna es '{majority_fmt}'"
                )

    # ── 2. Símbolo de moneda ───────────────────────────────────────────────────
    # Solo evalúa columnas sin fechas (< 5 % de fechas detectadas)
    if len(dated) < len(col_str) * 0.05:
        currency_mask = col_str.map(lambda v: bool(_CURRENCY_RE.match(v)))
        plain_mask    = col_str.map(lambda v: bool(_PLAIN_NUM_RE.match(v)))
        n_currency    = currency_mask.sum()
        n_plain       = plain_mask.sum()
        if n_currency > 0 and n_plain > 0:
            if n_currency <= n_plain:
                for idx in col_str[currency_mask].index:
                    minority_idx.setdefault(
                        idx, "Número con símbolo de moneda mezclado con números sin símbolo"
                    )
            else:
                for idx in col_str[plain_mask].index:
                    minority_idx.setdefault(
                        idx, "Número sin símbolo de moneda mezclado con números con símbolo"
                    )

    # ── 3. Capitalización ──────────────────────────────────────────────────────
    # Solo en columnas de texto puro. Requiere ≥ 3 valores para evitar ruido.
    # Reporta los valores cuyo estilo difiere del mayoritario.
    text_mask = ~col_str.str.match(r"^[\d\$€£¥\.\,\-\/\s]+$")
    text_vals = col_str[text_mask]
    if len(text_vals) >= 3:
        casing = text_vals.map(_detect_casing)
        casing_counts = casing.value_counts()
        if len(casing_counts) > 1:
            majority_case = casing_counts.index[0]
            for idx in text_vals[casing != majority_case].index:
                minority_idx.setdefault(
                    idx,
                    f"Capitalización inconsistente — el estilo mayoritario es '{majority_case}'"
                )

    if not minority_idx:
        return 100.0, _empty_issues(id_col), {}

    # ── Construir issues_df ───────────────────────────────────────────────────
    rows = []
    for orig_idx, desc in minority_idx.items():
        row = df.loc[orig_idx]
        rows.append({
            id_col:             row[id_col],
            "columna":          target_col,
            "dimension":        "consistencia",
            "descripcion":      desc,
            "valor_encontrado": str(row[target_col]),
        })

    issues_df = (
        pd.DataFrame(rows)
        .drop_duplicates(subset=[id_col])
        .reset_index(drop=True)
    )
    n_minority = len(issues_df)
    score = max(0.0, round((total - n_minority) / total * 100, 2))
    return score, issues_df, {}


def _empty_issues(id_col: str) -> pd.DataFrame:
    return pd.DataFrame(
        columns=[id_col, "columna", "dimension", "descripcion", "valor_encontrado"]
    )
