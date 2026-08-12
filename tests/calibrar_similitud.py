"""
tests/calibrar_similitud.py
Calibración de los 8 algoritmos de similitud contra verdad terreno (entidad_real_id).

Uso:
  python3 tests/calibrar_similitud.py <archivo.csv> <columna_texto> [umbral_inicio [umbral_fin]]

Produce:
  - Tabla por dataset con Precisión/Exhaustividad/F1/Tiempo
  - Tabla comparativa final acumulada en tests/CALIBRACION_SIMILITUD.md
"""
import sys, time, json, itertools
sys.path.insert(0, '.')

import pandas as pd
import numpy as np

# ──────────────────────────────────────────────────────────────────────────────
# Argumentos
# ──────────────────────────────────────────────────────────────────────────────
if len(sys.argv) < 3:
    print("Uso: python3 tests/calibrar_similitud.py <archivo.csv> <columna_texto>")
    sys.exit(1)

ARCHIVO  = sys.argv[1]
COLUMNA  = sys.argv[2]
UMBRALES = [78, 82, 86, 90, 92, 94, 96]

df = pd.read_csv(ARCHIVO)
assert COLUMNA in df.columns, f"Columna '{COLUMNA}' no encontrada"
assert 'entidad_real_id' in df.columns, "Falta columna entidad_real_id"

# Determinar id_col (primer campo que no es entidad_real_id ni la columna texto)
id_col = df.columns[0]
N = len(df)
print(f"\nArchivo  : {ARCHIVO}")
print(f"Columna  : {COLUMNA}")
print(f"Filas    : {N}")
print(f"id_col   : {id_col}")
print(f"Umbrales : {UMBRALES}\n")

# ──────────────────────────────────────────────────────────────────────────────
# Verdad terreno: pares que son duplicados reales (mismo entidad_real_id)
# Solo incluir IDs con ≥2 registros en el mismo grupo
# ──────────────────────────────────────────────────────────────────────────────
grupos = df.groupby('entidad_real_id')[id_col].apply(list)
pares_verdad = set()
for ids_grupo in grupos:
    if len(ids_grupo) >= 2:
        for a, b in itertools.combinations(sorted(ids_grupo), 2):
            pares_verdad.add((min(a,b), max(a,b)))

TOTAL_PARES_VERDAD = len(pares_verdad)
print(f"Pares de duplicados reales (verdad terreno): {TOTAL_PARES_VERDAD}\n")

# ──────────────────────────────────────────────────────────────────────────────
# Evaluar similitud usando el motor del proyecto
# ──────────────────────────────────────────────────────────────────────────────
from engine.dimensions.similitud import check_similitud

ALGORITMOS = [
    'qgrams',
    'jaro_winkler',
    'brecha_afin',
    'tfidf',
    'jaro_winkler_normalizar',    # jaro_winkler + normalizar tokens
    'brecha_afin_normalizar',     # brecha_afin + normalizar tokens
    'qgrams_normalizar',          # qgrams + normalizar tokens
    'tfidf_normalizar',           # tfidf + normalizar tokens (tfidf ya usa tokens)
]

results_all = []

print(f"{'Algoritmo':<30s} {'Umbral':>7s} {'Prec':>7s} {'Recall':>7s} {'F1':>7s} {'TP':>6s} {'FP':>6s} {'FN':>6s} {'Tiempo':>8s}")
print("-"*92)

best_per_algo: dict[str, dict] = {}

for algo_key in ALGORITMOS:
    # Parse algorithm and normalizar
    normalizar = '_normalizar' in algo_key
    algo_base  = algo_key.replace('_normalizar', '')
    # tfidf con normalizar es redundante pero lo marcamos
    if algo_base == 'tfidf' and normalizar:
        algo_base_use = 'tfidf'
        normalizar_use = True
    else:
        algo_base_use = algo_base
        normalizar_use = normalizar

    best_f1 = -1
    best_row = None

    for umbral in UMBRALES:
        t0 = time.time()
        try:
            score, issues_df, metadata = check_similitud(
                df, id_col, COLUMNA,
                algoritmo=algo_base_use,
                umbral=umbral,
                normalizar=normalizar_use,
            )
        except Exception as e:
            print(f"  ⚠  {algo_key} @ {umbral}% → ERROR: {e}")
            continue
        elapsed = time.time() - t0

        if issues_df.empty:
            pares_detectados = set()
        else:
            # Reconstruir pares detectados: para cada registro en issues,
            # encontrar su grupo según el campo grupo_id si existe, o agrupar
            # por cluster usando el campo similitud si está disponible.
            # El motor agrupa duplicados; usamos issues para reconstruir pares.
            if 'grupo_id' in issues_df.columns:
                grupos_det = issues_df.groupby('grupo_id')[id_col].apply(list)
            elif 'cluster_id' in issues_df.columns:
                grupos_det = issues_df.groupby('cluster_id')[id_col].apply(list)
            else:
                # Si no hay grupo_id, cada fila es un problema con un par implícito.
                # Fallback: tratar todos los issues como un solo grupo (conservador).
                grupos_det = {0: list(issues_df[id_col].unique())}
                grupos_det = pd.Series(grupos_det)

            pares_detectados = set()
            for ids_g in grupos_det:
                ids_sorted = sorted(set(ids_g))
                for a, b in itertools.combinations(ids_sorted, 2):
                    pares_detectados.add((min(a,b), max(a,b)))

        tp = len(pares_detectados & pares_verdad)
        fp = len(pares_detectados - pares_verdad)
        fn = len(pares_verdad - pares_detectados)

        precision   = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall      = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1          = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        row = {
            'algoritmo': algo_key, 'umbral': umbral, 'normalizar': normalizar_use,
            'precision': precision, 'recall': recall, 'f1': f1,
            'tp': tp, 'fp': fp, 'fn': fn, 'tiempo': elapsed,
        }
        results_all.append(row)

        marker = ' ◀' if f1 > best_f1 else ''
        print(f"  {algo_key:<28s} {umbral:>7d} {precision:>7.3f} {recall:>7.3f} {f1:>7.3f} {tp:>6d} {fp:>6d} {fn:>6d} {elapsed:>7.2f}s{marker}")

        if f1 > best_f1:
            best_f1 = f1
            best_row = row

    if best_row:
        best_per_algo[algo_key] = best_row
    print()

# ──────────────────────────────────────────────────────────────────────────────
# Tabla resumen por algoritmo (mejor umbral)
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "="*80)
print(f"RESUMEN — {ARCHIVO} / '{COLUMNA}'")
print("="*80)
print(f"{'Algoritmo':<30s} {'Mejor umbral':>13s} {'Precisión':>10s} {'Recall':>8s} {'F1':>8s} {'Tiempo':>8s}")
print("-"*80)

rows_sorted = sorted(best_per_algo.values(), key=lambda r: -r['f1'])
winner = rows_sorted[0] if rows_sorted else None

for r in rows_sorted:
    mark = ' 🏆' if r == winner else ''
    print(f"  {r['algoritmo']:<28s} {r['umbral']:>13d}% {r['precision']:>10.3f} {r['recall']:>8.3f} {r['f1']:>8.3f} {r['tiempo']:>7.2f}s{mark}")

if winner:
    print(f"\n✅ Mejor algoritmo: {winner['algoritmo']} @ {winner['umbral']}%  F1={winner['f1']:.3f}")
    print(f"   Precisión={winner['precision']:.3f}  Exhaustividad={winner['recall']:.3f}")

# ──────────────────────────────────────────────────────────────────────────────
# Guardar resultado en JSON para consolidar en el reporte
# ──────────────────────────────────────────────────────────────────────────────
output_json = f"tests/calibracion_{ARCHIVO.split('/')[-1].replace('.csv','')}.json"
with open(output_json, 'w') as f:
    payload = {
        'archivo': ARCHIVO,
        'columna': COLUMNA,
        'n_filas': N,
        'pares_verdad': TOTAL_PARES_VERDAD,
        'winner': winner,
        'best_per_algo': list(best_per_algo.values()),
    }
    json.dump(payload, f, indent=2, ensure_ascii=False)
print(f"\nResultados guardados → {output_json}")
