"""
Medición de escala con el criterio nuevo (trigramas + heap).

Tablas:
  1. Resultados por escala (5k / 20k / 50k) — criterio NUEVO
  2. Comparación lado a lado: criterio anterior vs. nuevo (5k y 20k)
  3. Calibración de los cuatro datasets originales (verificación 2.6)

Ejecutar: python3 tests/medir_escala_v2.py
"""
import gc
import itertools
import platform
import resource
import sys
import time
import tracemalloc
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.dimensions.similitud import (
    ALGORITMOS_TOLERANTES_LONGITUD,
    _construir_bloques,
    _indice_trigramas,
    _jaccard_est,
    _normalizar,
    _seleccion_por_heap,
    check_similitud,
)

ALGORITMO = 'qgrams'
UMBRAL    = 86


# ── Helpers comunes ────────────────────────────────────────────────────────────

def _rss_mb():
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return usage / 1_048_576 if platform.system() == 'Darwin' else usage / 1_024


def verdad_desde_df(df, id_col, verdad_col):
    pares = set()
    for _, g in df.groupby(verdad_col):
        if len(g) > 1:
            ids = sorted(g[id_col].tolist())
            pares |= set(itertools.combinations(ids, 2))
    return pares


def metricas_pipeline(df, id_col, target_col, verdad):
    gc.collect()
    t0 = time.perf_counter()
    sc, iss, mt = check_similitud(
        df, id_col, target_col, algoritmo=ALGORITMO, umbral=UMBRAL, normalizar=True
    )
    elapsed = time.perf_counter() - t0
    det: set = set()
    if len(iss) > 0:
        ic = iss.columns[0]
        for _, g in iss.groupby('grupo_id'):
            ids_g = sorted(g[ic].tolist())
            det |= set(itertools.combinations(ids_g, 2))
    if not verdad or not det:
        p, r, f1 = 0.0, 0.0, 0.0
    else:
        vp = len(det & verdad)
        p  = vp / len(det)
        r  = vp / len(verdad)
        f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1, elapsed, sc, mt


def _blocking_stats(df, target_col):
    """Replica el blocking para obtener pares antes/después del tope."""
    df = df.reset_index(drop=True)
    valores   = df[target_col].tolist()
    uniq_vals = {}
    for v in valores:
        if pd.notna(v) and str(v).strip().lower() not in {'', 'nan'}:
            uniq_vals.setdefault(str(v), [])
    uniq_raw  = list(uniq_vals.keys())
    uniq_norm = [_normalizar(v) for v in uniq_raw]
    valid_idx = [i for i, nv in enumerate(uniq_norm) if nv]
    bloques   = _construir_bloques(valid_idx, uniq_norm)
    max_bloque = 100 if ALGORITMO == 'brecha_afin' else 200
    ratio_min  = 0.25 if ALGORITMO in ALGORITMOS_TOLERANTES_LONGITUD else 0.0
    pares_cand: set = set()
    for grupo in bloques.values():
        lista = sorted(grupo)
        if len(lista) > max_bloque:
            subgrupos: dict = {}
            for i in lista:
                sub = uniq_norm[i][:3] if len(uniq_norm[i]) >= 3 else uniq_norm[i]
                subgrupos.setdefault(sub, []).append(i)
            for sub_lista in subgrupos.values():
                for a in range(len(sub_lista)):
                    for b in range(a + 1, len(sub_lista)):
                        na, nb = uniq_norm[sub_lista[a]], uniq_norm[sub_lista[b]]
                        if na and nb and ratio_min > 0 and min(len(na), len(nb)) / max(len(na), len(nb)) < ratio_min:
                            continue
                        pares_cand.add((min(sub_lista[a], sub_lista[b]),
                                        max(sub_lista[a], sub_lista[b])))
        else:
            for a in range(len(lista)):
                for b in range(a + 1, len(lista)):
                    na, nb = uniq_norm[lista[a]], uniq_norm[lista[b]]
                    if na and nb and ratio_min > 0 and min(len(na), len(nb)) / max(len(na), len(nb)) < ratio_min:
                        continue
                    pares_cand.add((min(lista[a], lista[b]), max(lista[a], lista[b])))
    return pares_cand, uniq_norm


def _verdad_en_uniq(df, id_col, target_col, verdad):
    df = df.reset_index(drop=True)
    valores = df[target_col].tolist()
    ids     = df[id_col].tolist()
    uniq_vals = {}
    for v in valores:
        if pd.notna(v):
            uniq_vals.setdefault(str(v), [])
    uniq_raw = list(uniq_vals.keys())
    uniq_norm = [_normalizar(v) for v in uniq_raw]
    raw_to_ui  = {r: i for i, r in enumerate(uniq_raw)}
    norm_to_ui = {n: i for i, n in enumerate(uniq_norm)}
    id_to_raw  = {}
    for i, v in enumerate(valores):
        id_to_raw[ids[i]] = str(v)
    verdad_uniq = set()
    for id_a, id_b in verdad:
        ra = id_to_raw.get(id_a)
        rb = id_to_raw.get(id_b)
        if ra is None or rb is None:
            continue
        ui_a = raw_to_ui.get(ra)
        ui_b = raw_to_ui.get(rb)
        if ui_a is None or ui_b is None:
            continue
        na, nb = uniq_norm[ui_a], uniq_norm[ui_b]
        if na == nb:
            continue   # exactos — detectados por otra ruta
        verdad_uniq.add((min(ui_a, ui_b), max(ui_a, ui_b)))
    return verdad_uniq, uniq_norm


def medir_dataset(nombre, csv_path, id_col, target_col, verdad_col, skip_50k_blocking=True):
    """Mide el dataset con el criterio NUEVO (trigramas + heap)."""
    if not csv_path.exists():
        print(f"  ⚠️  {csv_path.name} no encontrado — saltando")
        return None

    print(f"\n{'='*68}")
    print(f"  {nombre}")
    print(f"{'='*68}")
    df = pd.read_csv(csv_path)
    n_filas = len(df)
    n_uniq  = df[target_col].apply(_normalizar).nunique()
    verdad  = verdad_desde_df(df, id_col, verdad_col)
    print(f"  Filas: {n_filas:,}  |  Únicos norm.: {n_uniq:,}  |  Pares verdaderos: {len(verdad):,}")

    # Stats de blocking (para ver cuántos pares hay antes/después del tope)
    if n_filas <= 20_000 or not skip_50k_blocking:
        pares_cand, uniq_norm = _blocking_stats(df, target_col)
        n_antes = len(pares_cand)
        verdad_uniq, _ = _verdad_en_uniq(df, id_col, target_col, verdad)
        verd_antes = len(verdad_uniq & pares_cand)

        # Aplicar tope con criterio NUEVO
        TOPE = 15_000
        if n_antes > TOPE:
            tri = _indice_trigramas(uniq_norm)
            pares_nuevo = _seleccion_por_heap(pares_cand, tri, uniq_norm, TOPE)
            # Y criterio ANTIGUO para comparación
            pares_viejo = set(
                sorted(pares_cand, key=lambda p: (
                    abs(len(uniq_norm[p[0]]) - len(uniq_norm[p[1]])),
                    uniq_norm[p[0]], uniq_norm[p[1]],
                ))[:TOPE]
            )
            verd_nuevo = len(verdad_uniq & pares_nuevo)
            verd_viejo = len(verdad_uniq & pares_viejo)
            perdidos_nuevo = verd_antes - verd_nuevo
            perdidos_viejo = verd_antes - verd_viejo
            pct_perdidos_nuevo = perdidos_nuevo / verd_antes * 100 if verd_antes else 0
            pct_perdidos_viejo = perdidos_viejo / verd_antes * 100 if verd_antes else 0
            print(f"  Candidatos antes del tope: {n_antes:,}")
            print(f"  Verdad en candidatos pre-tope: {verd_antes} / {len(verdad_uniq)}")
            print(f"  Criterio VIEJO → verdad tras tope: {verd_viejo}  ({perdidos_viejo} perdidos = {pct_perdidos_viejo:.1f}%)")
            print(f"  Criterio NUEVO → verdad tras tope: {verd_nuevo}  ({perdidos_nuevo} perdidos = {pct_perdidos_nuevo:.1f}%)")
        else:
            print(f"  Candidatos: {n_antes:,}  (tope no activado)")
            verd_nuevo_pct = 0.0
            perdidos_nuevo = 0
    else:
        print(f"  Skipping blocking stats para 50k (demasiado tiempo/memoria)")

    # Pipeline completo con criterio nuevo
    gc.collect()
    rss_antes = _rss_mb()
    tracemalloc.start()
    p, r, f1, elapsed, sc, mt = metricas_pipeline(df, id_col, target_col, verdad)
    _, mem_pico = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    rss_despues = _rss_mb()

    print(f"\n  Pipeline (criterio NUEVO):")
    print(f"    P={p:.3f}  R={r:.3f}  F1={f1:.3f}  score={sc}")
    print(f"    Tiempo: {elapsed:.1f} s")
    print(f"    Memoria tracemalloc pico: {mem_pico/1e6:.1f} MB")
    print(f"    Memoria RSS: antes={rss_antes:.0f} MB  después={rss_despues:.0f} MB")
    print(f"    tope_activado: {mt.get('tope_activado')}  "
          f"candidatos: {mt.get('candidatos_generados',0):,} → {mt.get('candidatos_evaluados',0):,}  "
          f"descartados: {mt.get('pct_candidatos_descartados',0):.1f}%")

    return {
        'nombre': nombre,
        'n_filas': n_filas,
        'n_uniq': n_uniq,
        'n_verdad': len(verdad),
        'p': p, 'r': r, 'f1': f1, 'sc': sc,
        'elapsed': elapsed,
        'mem_mb': mem_pico / 1e6,
        'rss_mb': rss_despues,
        'tope': mt.get('tope_activado', False),
        'gen': mt.get('candidatos_generados', 0),
        'eval': mt.get('candidatos_evaluados', 0),
        'pct_desc': mt.get('pct_candidatos_descartados', 0.0),
    }


# ── 2.6: calibración de los cuatro datasets originales ────────────────────────

DATASETS_CALIBRACION = [
    ('tests/maestro_proveedores_1000.csv',  'proveedor_id',   'razon_social',   'qgrams',      86),
    ('tests/prueba_tipograficos_800.csv',   'entidad_real_id','nombre_entidad', 'qgrams',      86),
    ('tests/prueba_tokens_600.csv',         'entidad_real_id','nombre_entidad', 'qgrams',      86),
    ('tests/prueba_limpio_500.csv',         'entidad_real_id','nombre_entidad', 'qgrams',      86),
]

CALIBRACION_REFERENCIA = {
    'maestro_proveedores_1000.csv': {'p': None, 'r': None, 'f1': None},  # se miden en vivo
    'prueba_tipograficos_800.csv':  {'p': None, 'r': None, 'f1': None},
    'prueba_tokens_600.csv':        {'p': None, 'r': None, 'f1': None},
    'prueba_limpio_500.csv':        {'p': None, 'r': None, 'f1': None},
}


def medir_calibracion():
    """Mide los cuatro datasets originales y verifica que el tope NO se activa."""
    print(f"\n{'='*68}")
    print("  2.6 — VERIFICACIÓN DE DATASETS DE CALIBRACIÓN (1k o menos)")
    print("  El tope no debe activarse — P/R/F1 no deben cambiar")
    print(f"{'='*68}")

    base = Path(__file__).resolve().parent
    rows = []
    for csv_rel, id_col, target_col, alg, umb in DATASETS_CALIBRACION:
        csv_path = base / csv_rel
        name = Path(csv_rel).name
        if not csv_path.exists():
            print(f"  ⚠️  {name} no encontrado — saltando")
            continue
        df = pd.read_csv(csv_path)
        # Para estos datasets no hay columna verdad estándar — medir el pipeline directamente
        t0 = time.perf_counter()
        sc, iss, mt = check_similitud(
            df, id_col, target_col, algoritmo=alg, umbral=umb, normalizar=True
        )
        elapsed = time.perf_counter() - t0
        tope = mt.get('tope_activado', False)
        n_grupos = mt.get('total_grupos', 0)
        n_inv    = mt.get('total_involucrados', 0)
        n_exc    = mt.get('total_excedentes', 0)
        estado   = mt.get('estado_confiabilidad', '?')
        rows.append((name, alg, umb, sc, n_grupos, n_inv, n_exc, estado, tope, round(elapsed, 1)))
        flag = '✅' if not tope else '⚠️  TOPE'
        print(f"  {name:<35} score={sc:5.1f}  grupos={n_grupos:3d}  estado={estado:<12}  {flag}  t={elapsed:.1f}s")

    topes_activos = sum(1 for r in rows if r[8])
    print()
    if topes_activos == 0:
        print("  ✅ Ningún tope activado — los resultados de calibración son comparables")
    else:
        print(f"  ⚠️  {topes_activos} dataset(s) con tope activo — revisar")
    return rows


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    base = Path(__file__).resolve().parent

    resultados = []

    for nombre, csv_name, skip50k in [
        ('escala_5k  (5.000 filas)',  'escala_5k.csv',  False),
        ('escala_20k (20.000 filas)', 'escala_20k.csv', False),
        ('escala_50k (50.000 filas)', 'escala_50k.csv', True),
    ]:
        r = medir_dataset(
            nombre,
            base / csv_name,
            'empresa_id', 'razon_social', 'entidad_real_id',
            skip_50k_blocking=skip50k,
        )
        if r:
            resultados.append(r)

    # Tabla resumen
    print(f"\n{'='*68}")
    print("  TABLA RESUMEN — criterio NUEVO (trigramas + heap)")
    print(f"{'='*68}")
    header = f"{'Dataset':<10} {'Filas':>7} {'Únicos':>7} {'P':>6} {'R':>6} {'F1':>6} {'t(s)':>6} {'Mem MB':>7} {'Tope':>5}"
    print(header)
    print('-' * len(header))
    for r in resultados:
        tope_str = 'SÍ⚠️' if r['tope'] else 'No'
        pct = r['pct_desc']
        name = r['nombre'].split('(')[0].strip()
        print(f"{name:<10} {r['n_filas']:>7,} {r['n_uniq']:>7,} "
              f"{r['p']:>6.3f} {r['r']:>6.3f} {r['f1']:>6.3f} "
              f"{r['elapsed']:>6.1f} {r['mem_mb']:>7.0f} {tope_str:>5}")

    # Calibración
    medir_calibracion()

    print(f"\n{'='*68}")
    print("  FIN")
    print(f"{'='*68}")
