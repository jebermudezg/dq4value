"""
Calibración completa — 6 algoritmos × 4 datasets × umbrales.
Incluye columna de recall de Fuerza Bruta (techo del algoritmo).

FB se salta para brecha_afin en datasets > 600 filas (demasiado lento).
Ejecutar: python3 tests/calibrar_algoritmos.py
"""
import itertools
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.dimensions.similitud import _normalizar, _calcular_similitud, check_similitud

# ── Configuración ──────────────────────────────────────────────────────────────
# Nota: los resultados de maestro_proveedores_1000 ya están medidos.
# Solo correr los tres faltantes para no repetir los 8 umbrales×7 algoritmos.
DATASETS = [
    {
        'nombre':     'maestro_proveedores_1000',
        'archivo':    'tests/maestro_proveedores_1000.csv',
        'id_col':     'proveedor_id',
        'target_col': 'razon_social',
        'verdad_col': 'ruc',
    },
    {
        'nombre':     'prueba_tipograficos_800',
        'archivo':    'tests/prueba_tipograficos_800.csv',
        'id_col':     'empleado_id',
        'target_col': 'nombre_completo',
        'verdad_col': 'entidad_real_id',
    },
    {
        'nombre':     'prueba_tokens_600',
        'archivo':    'tests/prueba_tokens_600.csv',
        'id_col':     'predio_id',
        'target_col': 'direccion',
        'verdad_col': 'entidad_real_id',
    },
    {
        'nombre':     'prueba_limpio_500',
        'archivo':    'tests/prueba_limpio_500.csv',
        'id_col':     'producto_id',
        'target_col': 'nombre_producto',
        'verdad_col': 'entidad_real_id',
    },
]

# Algoritmos principales (excluye coseno y smith_waterman — demasiado lentos)
ALGORITMOS = ['qgrams', 'brecha_afin', 'jaro_winkler', 'jaro',
              'levenshtein', 'soundex', 'monge_elkan']

# brecha_afin/monge_elkan FB es O(n²×longitud_string) — muy lento incluso en 500 filas
SLOW_ALGOS = {'brecha_afin', 'monge_elkan'}
FB_MAX_FILAS = 0   # nunca correr FB para algoritmos lentos

UMBRALES = [80, 83, 86, 88, 90, 92, 94, 96]


# ── Helpers ────────────────────────────────────────────────────────────────────
def verdad_desde_df(df, id_col, verdad_col):
    pares: set = set()
    for _, g in df.groupby(verdad_col):
        if len(g) > 1:
            ids = sorted(g[id_col].tolist())
            pares |= set(itertools.combinations(ids, 2))
    return pares


def recall_fb(df, id_col, target_col, verdad, algoritmo, umbral):
    vals: dict = {}
    for _, r in df.iterrows():
        k = _normalizar(str(r[target_col]))
        vals.setdefault(k, []).append(r[id_col])
    claves = sorted(vals)
    det: set = set()
    for a, b in itertools.combinations(claves, 2):
        if _calcular_similitud(a, b, algoritmo) >= umbral:
            for x in vals[a]:
                for y in vals[b]:
                    det.add(tuple(sorted((x, y))))
    for ids_l in vals.values():
        if len(ids_l) > 1:
            det |= set(itertools.combinations(sorted(ids_l), 2))
    if not verdad or not det:
        return 0.0, 0.0, 0.0
    vp = len(det & verdad)
    p  = vp / len(det)
    r  = vp / len(verdad)
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1


def metricas_pipeline(df, id_col, target_col, verdad, algoritmo, umbral):
    t0 = time.time()
    sc, iss, mt = check_similitud(
        df, id_col, target_col, algoritmo=algoritmo, umbral=umbral, normalizar=True
    )
    elapsed = time.time() - t0
    det: set = set()
    if len(iss) > 0:
        ic = iss.columns[0]
        for _, g in iss.groupby('grupo_id'):
            ids_g = sorted(g[ic].tolist())
            det |= set(itertools.combinations(ids_g, 2))
    if not verdad or not det:
        return 0.0, 0.0, 0.0, elapsed
    vp = len(det & verdad)
    p  = vp / len(det)
    r  = vp / len(verdad)
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1, elapsed


def mejor_umbral_confiable(pip_cache):
    """Umbral con mejor F1 entre los que tienen Precisión ≥ 0.75."""
    confiables = [(u, d['f1_pip']) for u, d in pip_cache.items()
                  if d['p_pip'] >= 0.75]
    if not confiables:
        return max(pip_cache, key=lambda u: pip_cache[u]['f1_pip'])
    return max(confiables, key=lambda x: x[1])[0]


# ── Calibración ────────────────────────────────────────────────────────────────
resultados: list = []

for ds in DATASETS:
    print(f"\n{'='*78}")
    print(f"  Dataset: {ds['nombre']}")
    print(f"{'='*78}")

    try:
        df = pd.read_csv(ds['archivo'])
    except FileNotFoundError:
        print(f"  ⚠️  Archivo no encontrado: {ds['archivo']}")
        continue

    verdad = verdad_desde_df(df, ds['id_col'], ds['verdad_col'])
    n_filas = len(df)
    print(f"  Filas: {n_filas}  |  Pares verdaderos: {len(verdad)}")

    for algo in ALGORITMOS:
        usar_fb = not (algo in SLOW_ALGOS and n_filas > FB_MAX_FILAS)
        print(f"\n  [{algo}]  FB={'sí' if usar_fb else 'no (demasiado lento)'}")

        pip_cache: dict = {}
        fb_cache:  dict = {}

        for umbral in UMBRALES:
            try:
                p_pip, r_pip, f1_pip, t = metricas_pipeline(
                    df, ds['id_col'], ds['target_col'], verdad, algo, umbral)
                pip_cache[umbral] = {'p_pip': p_pip, 'r_pip': r_pip,
                                     'f1_pip': f1_pip, 't': t}

                if usar_fb:
                    p_fb, r_fb, f1_fb = recall_fb(
                        df, ds['id_col'], ds['target_col'], verdad, algo, umbral)
                    fb_cache[umbral] = (p_fb, r_fb, f1_fb)
                    print(f"    u={umbral}  FB P={p_fb:.2f} R={r_fb:.2f} F1={f1_fb:.2f}"
                          f"  Pip P={p_pip:.2f} R={r_pip:.2f} F1={f1_pip:.2f}"
                          f"  t={t:.1f}s")
                else:
                    fb_cache[umbral] = (None, None, None)
                    print(f"    u={umbral}  FB=N/A"
                          f"  Pip P={p_pip:.2f} R={r_pip:.2f} F1={f1_pip:.2f}"
                          f"  t={t:.1f}s")
            except Exception as e:
                print(f"    u={umbral}  ERROR: {e}")
                pip_cache[umbral] = {'p_pip': 0, 'r_pip': 0, 'f1_pip': 0, 't': 0}
                fb_cache[umbral]  = (0, 0, 0)

        if not pip_cache:
            continue

        u_m = mejor_umbral_confiable(pip_cache)
        d   = pip_cache[u_m]
        p_fb_m, r_fb_m, f1_fb_m = fb_cache[u_m]

        gap_r = (d['r_pip'] - r_fb_m) if r_fb_m is not None else None
        resultados.append({
            'dataset':   ds['nombre'],
            'algoritmo': algo,
            'u_mejor':   u_m,
            'P_fb':      p_fb_m,
            'R_fb':      r_fb_m,
            'F1_fb':     f1_fb_m,
            'P_pip':     d['p_pip'],
            'R_pip':     d['r_pip'],
            'F1_pip':    d['f1_pip'],
            'gap_R':     gap_r,
            'tiempo_s':  d['t'],
        })

# ── Tabla de resumen ───────────────────────────────────────────────────────────
print(f"\n\n{'='*105}")
print(f"  TABLA RESUMEN — Calibración (normalización corregida)")
print(f"{'='*105}")

def fmt(v, decimales=3):
    if v is None: return '  N/A'
    return f'{v:.{decimales}f}'

hdr = (f"  {'Dataset':<30} {'Algo':<13} {'U':>4}  "
       f"{'P_fb':>5} {'R_fb':>5} {'F1_fb':>6}  "
       f"{'P_pip':>5} {'R_pip':>5} {'F1_pip':>6}  "
       f"{'GapR':>6}  {'t(s)':>5}")
print(hdr)
print(f"  {'-'*101}")

prev_ds = None
for r in resultados:
    if r['dataset'] != prev_ds:
        if prev_ds is not None:
            print()
        prev_ds = r['dataset']
    gap_s = fmt(r['gap_R']) if r['gap_R'] is not None else '  N/A'
    flag  = ' ⚠️' if r['gap_R'] is not None and r['gap_R'] < -0.15 else ''
    print(f"  {r['dataset']:<30} {r['algoritmo']:<13} {r['u_mejor']:>4}  "
          f"{fmt(r['P_fb']):>5} {fmt(r['R_fb']):>5} {fmt(r['F1_fb']):>6}  "
          f"{fmt(r['P_pip']):>5} {fmt(r['R_pip']):>5} {fmt(r['F1_pip']):>6}  "
          f"{gap_s:>6}{flag}  {r['tiempo_s']:5.1f}")

print(f"\n  GapR = R_pip − R_fb  (negativo: pipeline pierde recall vs FB)")
print(f"  ⚠️  gap < −0.15 merece atención")
