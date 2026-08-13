"""
Mide el costo del tope de pares candidatos comparando fuerza bruta vs pipeline real.

Ejecutar: python3 tests/medir_tope_pares.py
"""
import itertools
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.dimensions.similitud import check_similitud, _normalizar, _calcular_similitud


def medir(algo: str, umbral: int, df: pd.DataFrame, col: str, idc: str, verdad: set):
    print(f"\n{'='*68}")
    print(f"  ALGORITMO={algo.upper()}  UMBRAL={umbral}%")
    print(f"{'='*68}")

    # ── A. Fuerza bruta: sin blocking ni tope ─────────────────────────────
    vals = {}
    for _, r in df.iterrows():
        vals.setdefault(_normalizar(str(r[col])), []).append(r[idc])
    claves = sorted(vals.keys())

    detectados_fb: set = set()
    for a, b in itertools.combinations(claves, 2):
        if _calcular_similitud(a, b, algo) >= umbral:
            for x in vals[a]:
                for y in vals[b]:
                    detectados_fb.add(tuple(sorted((x, y))))
    # pares normalizados-idénticos (distintas formas del mismo valor)
    for ids_list in vals.values():
        if len(ids_list) > 1:
            detectados_fb |= set(itertools.combinations(sorted(ids_list), 2))

    vp_fb = len(detectados_fb & verdad)
    fp_fb = len(detectados_fb - verdad)
    p_fb  = vp_fb / len(detectados_fb) if detectados_fb else 0
    r_fb  = vp_fb / len(verdad)        if verdad else 0
    f1_fb = 2*p_fb*r_fb/(p_fb+r_fb)   if (p_fb+r_fb) else 0

    print(f"\nFUERZA BRUTA (sin blocking, sin tope, {len(claves)} valores únicos)")
    print(f"  pares_únicos_norm×umbral : {len(detectados_fb):,}  "
          f"(VP={vp_fb}, FP={fp_fb})")
    print(f"  P={p_fb:.3f}  R={r_fb:.3f}  F1={f1_fb:.3f}")

    # ── B. Pipeline real ──────────────────────────────────────────────────
    sc, iss, mt = check_similitud(df, idc, col, algoritmo=algo,
                                  umbral=umbral, normalizar=True)
    detectados_real: set = set()
    if len(iss) > 0:
        id_col_real = iss.columns[0]
        for _, g in iss.groupby('grupo_id'):
            ids_g = sorted(g[id_col_real].tolist())
            detectados_real |= set(itertools.combinations(ids_g, 2))

    vp_real = len(detectados_real & verdad)
    fp_real = len(detectados_real - verdad)
    p_real  = vp_real / len(detectados_real) if detectados_real else 0
    r_real  = vp_real / len(verdad)          if verdad else 0
    f1_real = 2*p_real*r_real/(p_real+r_real) if (p_real+r_real) else 0

    print(f"\nPIPELINE REAL (con blocking y tope)")
    print(f"  score={sc}%")
    print(f"  pares_sobre_umbral  : {mt.get('pares_sobre_umbral', '?'):,}")
    print(f"  grupos_formados     : {mt.get('grupos_formados', '?')}")
    print(f"  total_grupos        : {mt.get('total_grupos', '?')}")
    print(f"  total_excedentes    : {mt.get('total_excedentes', '?')}")
    print(f"  detectados_real     : {len(detectados_real):,}  "
          f"(VP={vp_real}, FP={fp_real})")
    print(f"  P={p_real:.3f}  R={r_real:.3f}  F1={f1_real:.3f}")

    # ── C. Diferencia ─────────────────────────────────────────────────────
    perdidos_v = (detectados_fb & verdad) - detectados_real
    ganados_v  = detectados_real & verdad - detectados_fb   # siempre 0
    fp_solo_real = detectados_real - detectados_fb           # debería ser 0

    print(f"\nDIFERENCIA  (FB − Real)")
    print(f"  Pares verdaderos perdidos por pipeline : {len(perdidos_v)}")
    print(f"  FP introducidos solo por pipeline      : {len(fp_solo_real)}")

    if perdidos_v:
        print(f"\n  Detalle de pares verdaderos PERDIDOS (hasta 15):")
        print(f"  {'sim':>7}  {'difLen':>6}  {'val_a':<38}  {'val_b'}")
        print(f"  {'-'*85}")
        for a_id, b_id in sorted(perdidos_v)[:15]:
            na = _normalizar(str(df[df[idc] == a_id][col].iloc[0]))
            nb = _normalizar(str(df[df[idc] == b_id][col].iloc[0]))
            sim = _calcular_similitud(na, nb, algo)
            dif = abs(len(na) - len(nb))
            print(f"  {sim:7.1f}%  {dif:6d}  {na[:38]:<38}  {nb[:38]}")
    else:
        print("  → No hay pares verdaderos perdidos. ✅")

    return {
        'algo': algo, 'umbral': umbral,
        'vp_fb': vp_fb, 'vp_real': vp_real, 'perdidos': len(perdidos_v),
        'p_real': p_real, 'r_real': r_real, 'f1_real': f1_real,
        'p_fb': p_fb, 'r_fb': r_fb, 'f1_fb': f1_fb,
    }


if __name__ == '__main__':
    df  = pd.read_csv('tests/maestro_proveedores_1000.csv')
    COL = 'razon_social'
    IDC = 'proveedor_id'

    # Verdad terreno: mismo RUC = misma empresa
    verdad: set = set()
    for _, g in df.groupby('ruc'):
        if len(g) > 1:
            ids = sorted(g[IDC].tolist())
            verdad |= set(itertools.combinations(ids, 2))

    print(f"Dataset: maestro_proveedores_1000.csv  ({len(df)} filas)")
    print(f"Pares verdaderos (mismo RUC): {len(verdad)}")

    resultados = []
    resultados.append(medir('qgrams',     86, df, COL, IDC, verdad))
    resultados.append(medir('brecha_afin', 96, df, COL, IDC, verdad))

    # Resumen lado a lado
    print(f"\n\n{'='*68}")
    print(f"  RESUMEN COMPARATIVO")
    print(f"{'='*68}")
    print(f"  {'Medida':<30}  {'qgrams@86':>12}  {'brecha_afin@96':>14}")
    print(f"  {'-'*60}")
    for key, label in [
        ('p_fb',     'Precisión FB'),
        ('r_fb',     'Recall FB'),
        ('f1_fb',    'F1 FB'),
        ('p_real',   'Precisión Real'),
        ('r_real',   'Recall Real'),
        ('f1_real',  'F1 Real'),
        ('perdidos', 'VP perdidos por pipeline'),
    ]:
        vals_row = [r[key] for r in resultados]
        fmt_vals = [f"{v:.3f}" if isinstance(v, float) else str(v) for v in vals_row]
        print(f"  {label:<30}  {fmt_vals[0]:>12}  {fmt_vals[1]:>14}")
