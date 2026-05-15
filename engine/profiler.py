"""
Data Profiling Engine — calcula métricas detalladas por columna y del dataset.
Cada cálculo individual está envuelto en try/except para que ningún fallo parcial
rompa el perfil completo.
"""
from __future__ import annotations

import math
import re
import sys
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# Regex para detección de formato
# ─────────────────────────────────────────────────────────────────────────────

_RE_EMAIL  = re.compile(r"^[a-zA-Z0-9_.+\-À-ɏ]+@[a-zA-Z0-9\-À-ɏ]+\.[a-zA-Z0-9\-.À-ɏ]+$")
_RE_FECHA  = re.compile(r"^\d{1,4}[-/]\d{1,2}[-/]\d{1,4}$")
_RE_NIT    = re.compile(r"^\d{6,12}[-]?\d?$")
_RE_TEL    = re.compile(r"^\+?[\d\s\-\(\)]{7,15}$")
_RE_URL    = re.compile(r"^https?://[^\s/$.?#].[^\s]*$")


def _detect_format(series: pd.Series) -> str:
    sample = series.dropna().astype(str).head(50)
    if len(sample) == 0:
        return "texto_libre"
    counts: dict[str, int] = {"email": 0, "fecha": 0, "nit": 0, "telefono": 0, "url": 0}
    for v in sample:
        v = v.strip()
        if _RE_EMAIL.match(v):
            counts["email"] += 1
        elif _RE_FECHA.match(v):
            counts["fecha"] += 1
        elif _RE_URL.match(v):
            counts["url"] += 1
        elif _RE_NIT.match(v):
            counts["nit"] += 1
        elif _RE_TEL.match(v):
            counts["telefono"] += 1
    best = max(counts, key=counts.get)
    threshold = max(3, len(sample) * 0.5)
    return best if counts[best] >= threshold else "texto_libre"


def _variantes_similares(values: list[str]) -> list[list[str]]:
    """Agrupa strings que son iguales al normalizar (strip + lower)."""
    groups: dict[str, list[str]] = {}
    for v in values:
        key = str(v).strip().lower()
        groups.setdefault(key, []).append(str(v))
    return [sorted(set(g)) for g in groups.values() if len(set(g)) > 1]


def _histogram_num(series: pd.Series, bins: int = 10) -> list[dict]:
    """Genera histograma de 10 buckets para columna numérica."""
    try:
        clean = series.dropna()
        if len(clean) == 0:
            return []
        counts, edges = np.histogram(clean, bins=bins)
        result = []
        for i in range(len(counts)):
            result.append({
                "rango": f"{edges[i]:.2f}–{edges[i+1]:.2f}",
                "conteo": int(counts[i]),
            })
        return result
    except Exception:
        return []


def _dist_longitudes(series: pd.Series, bins: int = 5) -> list[dict]:
    """Distribución de longitudes para columna de texto."""
    try:
        lens = series.dropna().astype(str).map(len)
        if len(lens) == 0:
            return []
        counts, edges = np.histogram(lens, bins=bins)
        result = []
        for i in range(len(counts)):
            result.append({
                "rango_chars": f"{int(edges[i])}–{int(edges[i+1])}",
                "conteo": int(counts[i]),
            })
        return result
    except Exception:
        return []


def _safe(fn, default=None):
    try:
        result = fn()
        if result is None:
            return default
        if isinstance(result, float) and (math.isnan(result) or math.isinf(result)):
            return default
        return result
    except Exception:
        return default


# ─────────────────────────────────────────────────────────────────────────────
# Perfiles por tipo
# ─────────────────────────────────────────────────────────────────────────────

def _profile_numeric(col: str, series: pd.Series, total: int) -> dict:
    clean = series.dropna()
    n = len(clean)
    pct_nulos = _safe(lambda: round(series.isna().sum() / total * 100, 2), 0.0)

    q1  = _safe(lambda: float(clean.quantile(0.25)))
    q3  = _safe(lambda: float(clean.quantile(0.75)))
    iqr = (q3 - q1) if (q1 is not None and q3 is not None) else None
    outliers = _safe(
        lambda: int(((clean < q1 - 1.5 * iqr) | (clean > q3 + 1.5 * iqr)).sum())
        if iqr is not None else 0,
        0,
    )

    mean = _safe(lambda: float(clean.mean()))
    std  = _safe(lambda: float(clean.std()))
    cv   = _safe(lambda: round(abs(std / mean) * 100, 2) if mean and mean != 0 else None)

    skew = _safe(lambda: float(clean.skew()))
    if skew is not None:
        if abs(skew) < 0.5:
            sesgo = "normal"
        elif skew > 0.5:
            sesgo = "sesgado_derecha"
        else:
            sesgo = "sesgado_izquierda"
    else:
        sesgo = None

    return {
        "tipo_perfil": "numerico",
        "min": _safe(lambda: float(clean.min())),
        "max": _safe(lambda: float(clean.max())),
        "promedio": _safe(lambda: round(float(clean.mean()), 4)),
        "mediana": _safe(lambda: round(float(clean.median()), 4)),
        "desviacion_std": _safe(lambda: round(float(clean.std()), 4)),
        "suma": _safe(lambda: round(float(clean.sum()), 4)),
        "percentiles": {
            "p5":  _safe(lambda: round(float(clean.quantile(0.05)), 4)),
            "p25": _safe(lambda: round(float(q1), 4)),
            "p75": _safe(lambda: round(float(q3), 4)),
            "p95": _safe(lambda: round(float(clean.quantile(0.95)), 4)),
        },
        "coeficiente_variacion": cv,
        "pct_nulos":     pct_nulos,
        "pct_ceros":     _safe(lambda: round((clean == 0).sum() / total * 100, 2), 0.0),
        "pct_negativos": _safe(lambda: round((clean < 0).sum() / total * 100, 2), 0.0),
        "outliers_count": outliers,
        "sesgo": sesgo,
        "histograma": _histogram_num(series),
    }


def _profile_text(col: str, series: pd.Series, total: int) -> dict:
    pct_nulos = _safe(lambda: round(series.isna().sum() / total * 100, 2), 0.0)
    no_nulos  = series.dropna()
    str_series = no_nulos.astype(str)

    unicos = _safe(lambda: int(series.nunique(dropna=True)), 0)
    ratio  = unicos / total if total > 0 else 0
    if ratio > 0.50:
        cardinalidad = "alta"
    elif ratio >= 0.05:
        cardinalidad = "media"
    else:
        cardinalidad = "baja"

    es_catalogo = unicos <= 20

    top10_vc  = series.value_counts().head(10)
    top10 = [
        {"valor": str(v), "frecuencia": int(c), "porcentaje": round(c / total * 100, 2)}
        for v, c in top10_vc.items()
    ]

    lens = str_series.map(len)
    formato = _detect_format(series)

    tiene_mayusculas = _safe(lambda: bool(
        str_series.str.strip().str.len().gt(0) &
        str_series.str.contains(r'[A-Z]') &
        str_series.str.contains(r'[a-z]')
    ).any())

    variantes = _variantes_similares(top10_vc.index.tolist()) if es_catalogo else []

    return {
        "tipo_perfil": "texto",
        "total_unicos": unicos,
        "cardinalidad": cardinalidad,
        "es_catalogo": es_catalogo,
        "longitud_min": _safe(lambda: int(lens.min())),
        "longitud_max": _safe(lambda: int(lens.max())),
        "longitud_promedio": _safe(lambda: round(float(lens.mean()), 2)),
        "pct_nulos": pct_nulos,
        "pct_vacios": _safe(lambda: round((str_series.str.strip() == "").sum() / total * 100, 2), 0.0),
        "pct_solo_espacios": _safe(lambda: round(
            ((no_nulos.astype(str).str.strip() == "") & (no_nulos.astype(str) != "")).sum() / total * 100, 2
        ), 0.0),
        "tiene_mayusculas_mezcladas": tiene_mayusculas,
        "formato_detectado": formato,
        "top_10_valores": top10,
        "variantes_similares": variantes,
        "distribucion_longitudes": _dist_longitudes(series),
    }


def _profile_fecha(col: str, series: pd.Series, total: int) -> dict:
    pct_nulos = _safe(lambda: round(series.isna().sum() / total * 100, 2), 0.0)

    parsed = pd.to_datetime(series, errors="coerce")
    validas = parsed.dropna()
    ahora = pd.Timestamp.now()
    cinco_anios = ahora - pd.DateOffset(years=5)

    formatos: list[str] = []
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y%m%d"]:
        try:
            n_ok = pd.to_datetime(series.dropna(), format=fmt, errors="coerce").notna().sum()
            if n_ok > 0:
                formatos.append(fmt)
        except Exception:
            pass

    dist_anio = {}
    dist_mes  = {}
    if len(validas) > 0:
        dist_anio = {str(k): int(v) for k, v in validas.dt.year.value_counts().sort_index().items()}
        dist_mes  = {str(k): int(v) for k, v in validas.dt.month.value_counts().sort_index().items()}

    return {
        "tipo_perfil": "fecha",
        "fecha_min": _safe(lambda: str(validas.min().date())),
        "fecha_max": _safe(lambda: str(validas.max().date())),
        "rango_dias": _safe(lambda: int((validas.max() - validas.min()).days)),
        "fecha_mas_frecuente": _safe(lambda: str(validas.dt.date.value_counts().idxmax())),
        "pct_nulos": pct_nulos,
        "pct_fechas_futuras": _safe(lambda: round((validas > ahora).sum() / total * 100, 2), 0.0),
        "pct_fechas_antiguas": _safe(lambda: round((validas < cinco_anios).sum() / total * 100, 2), 0.0),
        "formatos_detectados": formatos,
        "distribucion_por_anio": dist_anio,
        "distribucion_por_mes": dist_mes,
    }


def _profile_categorico(col: str, series: pd.Series, total: int) -> dict:
    pct_nulos = _safe(lambda: round(series.isna().sum() / total * 100, 2), 0.0)
    vc = series.value_counts()

    valores = [
        {"valor": str(v), "frecuencia": int(c), "porcentaje": round(c / total * 100, 2)}
        for v, c in vc.items()
    ]

    # Entropía de Shannon normalizada
    probs = vc / vc.sum()
    n_cats = len(probs)
    entropia_raw = _safe(lambda: float(-(probs * np.log2(probs + 1e-12)).sum()), 0.0)
    entropia_max = math.log2(n_cats) if n_cats > 1 else 1
    entropia = _safe(lambda: round(entropia_raw / entropia_max, 3) if entropia_max > 0 else 0.0, 0.0)

    if entropia is not None:
        if entropia >= 0.9:
            entropia_label = "Muy balanceado"
        elif entropia >= 0.7:
            entropia_label = "Balanceado"
        elif entropia >= 0.4:
            entropia_label = "Desbalanceado"
        else:
            entropia_label = "Extremadamente desbalanceado"
    else:
        entropia_label = "N/A"

    desbalance = _safe(lambda: bool((vc.iloc[0] / total) >= 0.95), False)
    variantes  = _variantes_similares(vc.index.tolist())

    return {
        "tipo_perfil": "categorico",
        "total_unicos": int(series.nunique(dropna=True)),
        "pct_nulos": pct_nulos,
        "valores": valores,
        "valor_mas_frecuente": _safe(lambda: str(vc.index[0])),
        "valor_menos_frecuente": _safe(lambda: str(vc.index[-1])),
        "entropia": entropia,
        "entropia_label": entropia_label,
        "desbalance_extremo": desbalance,
        "variantes_similares": variantes,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Función principal
# ─────────────────────────────────────────────────────────────────────────────

def profile_dataset(df: pd.DataFrame) -> dict:
    """
    Calcula el perfil completo de un DataFrame.

    Returns:
        {
          "resumen": { total_filas, total_columnas, completitud_global,
                       filas_duplicadas_exactas, tamano_memoria_mb, alertas },
          "columnas": { "<col>": { tipo_perfil, ...métricas } }
        }
    """
    total_filas   = len(df)
    total_columnas = len(df.columns)

    # ── Resumen global ───────────────────────────────────────────────────────
    total_cells    = total_filas * total_columnas
    nulos_total    = int(df.isna().sum().sum())
    completitud_global = round((1 - nulos_total / total_cells) * 100, 2) if total_cells > 0 else 100.0

    try:
        filas_dup = int(df.duplicated().sum())
    except Exception:
        filas_dup = 0

    try:
        mem_mb = round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2)
    except Exception:
        mem_mb = 0.0

    # ── Alertas globales ─────────────────────────────────────────────────────
    alertas: list[str] = []
    for col in df.columns:
        try:
            n_unicos = df[col].nunique(dropna=True)
            n_nulos  = df[col].isna().sum()

            # Posible ID con duplicados
            id_keywords = ["id", "codigo", "code", "clave", "key", "nit", "dni", "rut"]
            if any(kw in col.lower() for kw in id_keywords):
                n_dup = int(df[col].duplicated(keep=False).sum())
                if n_dup > 0:
                    alertas.append(
                        f"La columna '{col}' parece un ID pero tiene {n_dup} valores duplicados"
                    )

            # Variantes en texto corto
            if df[col].dtype == object and n_unicos <= 20 and n_unicos >= 2:
                variantes = _variantes_similares(
                    df[col].dropna().astype(str).unique().tolist()
                )
                if variantes:
                    ejemplo = variantes[0]
                    alertas.append(
                        f"La columna '{col}' tiene variantes del mismo valor: "
                        + ", ".join(f'"{v}"' for v in ejemplo[:4])
                    )

            # Constante (un solo valor)
            if n_unicos == 1 and total_filas > 1:
                alertas.append(
                    f"La columna '{col}' tiene un solo valor único — podría ser una constante"
                )

            # Alta nulidad
            if total_filas > 0 and n_nulos / total_filas > 0.3:
                alertas.append(
                    f"La columna '{col}' tiene {round(n_nulos/total_filas*100,1)}% de valores nulos"
                )

        except Exception:
            continue

    # ── Perfil por columna ───────────────────────────────────────────────────
    columnas: dict[str, dict] = {}

    for col in df.columns:
        series = df[col]
        try:
            dtype_str = str(series.dtype)
            n_unicos  = series.nunique(dropna=True)

            if dtype_str in ("int64", "int32", "float64", "float32") or \
               pd.api.types.is_numeric_dtype(series):
                perfil = _profile_numeric(col, series, total_filas)

            elif "datetime" in dtype_str or "date" in dtype_str:
                perfil = _profile_fecha(col, series, total_filas)

            elif dtype_str == "object":
                fmt = _detect_format(series)
                if fmt == "fecha":
                    perfil = _profile_fecha(col, series, total_filas)
                elif n_unicos <= 20:
                    perfil = _profile_categorico(col, series, total_filas)
                else:
                    perfil = _profile_text(col, series, total_filas)

            elif dtype_str == "bool":
                perfil = _profile_categorico(col, series.astype(str), total_filas)

            else:
                perfil = _profile_text(col, series, total_filas)

        except Exception as exc:
            perfil = {"tipo_perfil": "error", "error": str(exc)}

        # Siempre añadir pct_nulos al nivel superior para el badge del acordeón
        if "pct_nulos" not in perfil:
            perfil["pct_nulos"] = _safe(
                lambda: round(series.isna().sum() / total_filas * 100, 2), 0.0
            )

        columnas[col] = perfil

    return {
        "resumen": {
            "total_filas": total_filas,
            "total_columnas": total_columnas,
            "completitud_global": completitud_global,
            "filas_duplicadas_exactas": filas_dup,
            "tamano_memoria_mb": mem_mb,
            "alertas": alertas,
        },
        "columnas": columnas,
    }
