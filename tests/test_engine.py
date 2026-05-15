"""
Tests para engine/profiler.py — Data Profiling Engine.
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.profiler import profile_dataset


# ─────────────────────────────────────────────────────────────────────────────
# Dataset de prueba con los 4 tipos + problemas intencionados
# ─────────────────────────────────────────────────────────────────────────────

def _make_df():
    n = 100
    return pd.DataFrame({
        # Numérico — con outlier y negativo
        "edad": [25] * 80 + [None] * 10 + [-5, 200] + [30] * 8,
        # Texto libre
        "nombre": ["Ana Torres"] * 40 + ["Luis Mendoza"] * 40 + [None] * 10 + [""] * 10,
        # Fecha (string formato ISO)
        "fecha_registro": (
            ["2023-01-15"] * 50
            + ["2024-06-30"] * 30
            + ["2099-12-31"] * 5   # futuras
            + ["2015-01-01"] * 5   # antiguas
            + [None] * 10
        ),
        # Categórico con variantes
        "estado": (
            ["Activo"] * 50
            + ["ACTIVO"] * 20
            + ["Inactivo"] * 20
            + ["inactivo"] * 5
            + [None] * 5
        ),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Test principal
# ─────────────────────────────────────────────────────────────────────────────

def test_profiler_retorna_estructura_completa():
    df = _make_df()
    result = profile_dataset(df)

    assert "resumen" in result
    assert "columnas" in result

    resumen = result["resumen"]
    assert resumen["total_filas"] == 100
    assert resumen["total_columnas"] == 4
    assert 0 <= resumen["completitud_global"] <= 100
    assert isinstance(resumen["filas_duplicadas_exactas"], int)
    assert isinstance(resumen["tamano_memoria_mb"], float)
    assert isinstance(resumen["alertas"], list)


def test_profiler_numerico_metricas():
    df = _make_df()
    p = profile_dataset(df)["columnas"]["edad"]

    assert p["tipo_perfil"] == "numerico"
    assert p["min"] is not None
    assert p["max"] is not None
    assert p["promedio"] is not None
    assert p["mediana"] is not None
    assert p["desviacion_std"] is not None
    assert isinstance(p["outliers_count"], int)
    assert p["outliers_count"] >= 1, "Debe detectar al menos el outlier 200"
    assert p["pct_nulos"] == 10.0
    assert p["pct_negativos"] > 0, "Debe detectar el valor -5"
    assert p["sesgo"] in ("normal", "sesgado_derecha", "sesgado_izquierda")
    assert isinstance(p["histograma"], list)
    assert len(p["histograma"]) == 10


def test_profiler_texto_metricas():
    # Columna con >20 únicos → tipo_perfil = "texto"
    df = pd.DataFrame({
        "descripcion": [f"Producto número {i} con descripción larga" for i in range(50)]
        + [None] * 10
    })
    p = profile_dataset(df)["columnas"]["descripcion"]

    assert p["tipo_perfil"] == "texto"
    assert p["total_unicos"] >= 20
    assert isinstance(p["top_10_valores"], list)
    assert len(p["top_10_valores"]) >= 1
    assert isinstance(p["distribucion_longitudes"], list)
    assert p["pct_nulos"] > 0


def test_profiler_fecha_metricas():
    df = _make_df()
    p = profile_dataset(df)["columnas"]["fecha_registro"]

    assert p["tipo_perfil"] == "fecha"
    assert p["fecha_min"] is not None
    assert p["fecha_max"] is not None
    assert p["rango_dias"] is not None and p["rango_dias"] > 0
    assert p["pct_nulos"] == 10.0
    assert p["pct_fechas_futuras"] > 0, "Debe detectar las fechas del 2099"
    assert p["pct_fechas_antiguas"] > 0, "Debe detectar las fechas del 2015"


def test_profiler_categorico_variantes():
    df = _make_df()
    p = profile_dataset(df)["columnas"]["estado"]

    assert p["tipo_perfil"] == "categorico"
    assert isinstance(p["variantes_similares"], list)
    # Debe agrupar Activo/ACTIVO y Inactivo/inactivo
    grupos_flat = [v for grupo in p["variantes_similares"] for v in grupo]
    assert any(v.lower() == "activo" for v in grupos_flat), \
        "Debe detectar variantes de 'Activo'"
    assert p["entropia"] is not None
    assert p["entropia_label"] in (
        "Muy balanceado", "Balanceado", "Desbalanceado", "Extremadamente desbalanceado"
    )
    assert p["pct_nulos"] == 5.0


def test_profiler_alertas_detecta_problemas():
    df = pd.DataFrame({
        "cliente_id": [1, 2, 2, 3, 4],          # duplicado → alerta
        "constante":  ["X", "X", "X", "X", "X"], # un solo valor → alerta
        "estado":     ["Activo", "ACTIVO", "activo", "Inactivo", "Inactivo"],  # variantes
    })
    alertas = profile_dataset(df)["resumen"]["alertas"]
    textos  = " ".join(alertas).lower()
    assert "cliente_id" in textos or "id" in textos, "Debe alertar sobre duplicados en ID"
    assert "constante" in textos,                    "Debe alertar sobre columna constante"


def test_profiler_dataframe_vacio():
    df = pd.DataFrame({"a": pd.Series([], dtype="float64")})
    result = profile_dataset(df)
    assert result["resumen"]["total_filas"] == 0
    assert result["resumen"]["completitud_global"] == 100.0


def test_profiler_no_explota_con_tipos_raros():
    df = pd.DataFrame({
        "booleano":  [True, False, True, None, True],
        "mixto":     [1, "dos", 3.0, None, "cinco"],
    })
    # No debe lanzar excepción
    result = profile_dataset(df)
    assert "columnas" in result
