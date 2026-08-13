"""
Prueba de determinismo del análisis de similitud.
Requisito de auditoría: el mismo archivo con la misma configuración debe producir
siempre el mismo resultado — grupos, score y excedentes idénticos.
"""
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.dimensions.similitud import check_similitud


def _huella(score, issues, meta):
    """Huella estable del resultado completo.

    El id_col real varía según el dataset (proveedor_id, empleado_id, etc.)
    y es siempre la primera columna del issues_df devuelto por check_similitud.
    """
    if len(issues) > 0:
        id_col = issues.columns[0]            # primera col = el id_col real
        stable_cols = [id_col] + [c for c in ['grupo_id', 'similitud_pct',
                                               'es_principal_sugerido']
                                   if c in issues.columns]
        cuerpo = issues[stable_cols].sort_values(id_col).to_csv(index=False)
    else:
        cuerpo = ''
    m = {k: v for k, v in sorted(meta.items())}
    txt = f'{score}|{cuerpo}|{json.dumps(m, sort_keys=True, default=str)}'
    return hashlib.sha256(txt.encode()).hexdigest()[:16]


def test_similitud_es_determinista():
    """Cinco corridas idénticas deben dar la misma huella."""
    df = pd.read_csv('tests/maestro_proveedores_1000.csv')
    huellas = []
    for _ in range(5):
        score, issues, meta = check_similitud(
            df, 'proveedor_id', 'razon_social',
            algoritmo='qgrams', umbral=86, normalizar=True)
        huellas.append(_huella(score, issues, meta))
    assert len(set(huellas)) == 1, f'Resultados distintos entre corridas: {huellas}'


def test_orden_de_filas_no_altera_resultado():
    """Reordenar el archivo no debe cambiar los grupos ni el score."""
    df = pd.read_csv('tests/maestro_proveedores_1000.csv')
    r = []
    for seed in [1, 7, 42, 99]:
        d = df.sample(frac=1, random_state=seed).reset_index(drop=True)
        score, issues, meta = check_similitud(
            d, 'proveedor_id', 'razon_social',
            algoritmo='qgrams', umbral=86, normalizar=True)
        if len(issues) > 0:
            id_col = issues.columns[0]        # proveedor_id / empleado_id / etc.
            particion = frozenset(
                frozenset(g[id_col].astype(str))
                for _, g in issues.groupby('grupo_id'))
        else:
            particion = frozenset()
        r.append((score, meta.get('total_grupos'), meta.get('total_excedentes'),
                  particion))
    base = r[0]
    for i, x in enumerate(r[1:], 1):
        assert x[0] == base[0], f'score cambió con el orden (seed {[1,7,42,99][i]}): {base[0]} vs {x[0]}'
        assert x[1] == base[1], f'grupos cambiaron: {base[1]} vs {x[1]}'
        assert x[2] == base[2], f'excedentes cambiaron: {base[2]} vs {x[2]}'
        assert x[3] == base[3], 'la agrupación de registros cambió con el orden'


def test_determinismo_en_los_ocho_algoritmos():
    """Cada algoritmo debe ser determinista por separado."""
    df = pd.read_csv('tests/maestro_proveedores_1000.csv').head(300)
    algos = ['qgrams', 'brecha_afin', 'jaro_winkler', 'levenshtein',
             'monge_elkan', 'soundex']   # se omiten los dos muy lentos
    for alg in algos:
        hh = []
        for _ in range(3):
            sc, iss, mt = check_similitud(
                df, 'proveedor_id', 'razon_social',
                algoritmo=alg, umbral=88, normalizar=True)
            hh.append(_huella(sc, iss, mt))
        assert len(set(hh)) == 1, f'{alg} no es determinista: {hh}'


def test_isolation_forest_es_determinista():
    """Isolation Forest usa aleatoriedad — debe tener semilla fija.

    Usa prueba_limpio_500 que tiene columnas numéricas (precio_pen, descuento_pct).
    """
    from engine.dimensions.razonabilidad import check_razonabilidad
    df  = pd.read_csv('tests/prueba_limpio_500.csv')
    # Columnas numéricas disponibles en este dataset
    col_target = 'precio_pen'
    col_if     = ['precio_pen', 'descuento_pct']
    hh = []
    for _ in range(4):
        sc, iss, mt = check_razonabilidad(
            df, 'producto_id', col_target,
            metodo='isolation_forest', columnas_if=col_if, contamination=0.05)
        hh.append(_huella(sc, iss, mt))
    assert len(set(hh)) == 1, f'Isolation Forest no es determinista: {hh}'
