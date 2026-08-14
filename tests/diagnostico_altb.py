"""
2.1 — Diagnóstico del costo de Alt B en escala_20k.csv

Mide por separado:
  Fase 1: generación de candidatos por blocking
  Fase 2: cálculo de la clave de ordenamiento (jaccard por par)
  Fase 3: el sorted() en sí / el heap en sí

Demuestra que el cuello de botella es el recálculo de trigramas por par,
y estima la mejora esperada con índice precalculado + heap.
"""
import itertools
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.dimensions.similitud import (
    ALGORITMOS_TOLERANTES_LONGITUD,
    _construir_bloques,
    _normalizar,
)

CSV = Path(__file__).parent / 'escala_20k.csv'
ALGORITMO = 'qgrams'
TOPE = 15_000

# ── Helpers ────────────────────────────────────────────────────────────────────

def _trigramas(v, q=3):
    """Frozenset de q-gramas para un valor normalizado (recálculo por llamada)."""
    pad = '#' * (q - 1)
    s = pad + v + pad
    return frozenset(s[i:i+q] for i in range(len(s) - q + 1))


def _jaccard_on_the_fly(a, b):
    ta = _trigramas(a)
    tb = _trigramas(b)
    inter = len(ta & tb)
    union = len(ta) + len(tb) - inter
    return inter / union if union else 0.0


def _jaccard_precomputed(tri, i, j):
    ta, tb = tri.get(i), tri.get(j)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta) + len(tb) - inter
    return inter / union if union else 0.0


# ── Fase 1: generar candidatos ─────────────────────────────────────────────────

def fase1_blocking(df, target_col):
    df = df.reset_index(drop=True)
    valores = df[target_col].tolist()
    unique_vals = {}
    for v in valores:
        if pd.notna(v) and str(v).strip().lower() not in {'', 'nan'}:
            unique_vals.setdefault(str(v), [])
    uniq_raw  = list(unique_vals.keys())
    uniq_norm = [_normalizar(v) for v in uniq_raw]

    valid_idx  = [i for i, nv in enumerate(uniq_norm) if nv]
    bloques    = _construir_bloques(valid_idx, uniq_norm)
    max_bloque = 100 if ALGORITMO == 'brecha_afin' else 200
    ratio_min  = 0.25 if ALGORITMO in ALGORITMOS_TOLERANTES_LONGITUD else 0.0

    t0 = time.perf_counter()
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
                    pares_cand.add((min(lista[a], lista[b]),
                                    max(lista[a], lista[b])))
    t1 = time.perf_counter()
    return pares_cand, uniq_norm, t1 - t0


# ── Fase 2+3: clave + sorted (Alt B original, sin precálculo) ──────────────────

def fase23_sort_on_the_fly(pares_cand, uniq_norm, n_muestra=500_000):
    """Mide el costo de calcular la clave de trigramas on-the-fly.
    Para evitar esperar 142s, usa una muestra de pares."""
    muestra = list(itertools.islice(iter(pares_cand), n_muestra))
    t0 = time.perf_counter()
    # Solo el cálculo de la clave (sin sorted, para aislar el costo)
    keys = [(_jaccard_on_the_fly(uniq_norm[p[0]], uniq_norm[p[1]]), p)
            for p in muestra]
    t2 = time.perf_counter()
    # El sorted en sí (con las claves ya calculadas — costo mínimo)
    _ = sorted(keys, key=lambda x: -x[0])
    t3 = time.perf_counter()
    return t2 - t0, t3 - t2, len(muestra)


# ── Fase 2+3: precálculo + heap ────────────────────────────────────────────────

def fase23_heap_precomputed(pares_cand, uniq_norm, n_muestra=500_000):
    """Mide el costo con trigramas precalculados + heap de tamaño fijo."""
    import heapq
    muestra = list(itertools.islice(iter(pares_cand), n_muestra))

    # Precalcular índice de trigramas (costo único)
    t0 = time.perf_counter()
    tri = {}
    for i, v in enumerate(uniq_norm):
        if v:
            pad = '##'
            s = pad + v + pad
            tri[i] = frozenset(s[k:k+3] for k in range(len(s) - 2))
    t1 = time.perf_counter()

    # Heap de tamaño fijo
    h = []
    for p in muestra:
        s = _jaccard_precomputed(tri, p[0], p[1])
        item = (s, uniq_norm[p[0]], uniq_norm[p[1]], p)
        if len(h) < TOPE:
            heapq.heappush(h, item)
        elif item > h[0]:
            heapq.heapreplace(h, item)
    t2 = time.perf_counter()

    return t1 - t0, t2 - t1, len(muestra), tri


# ── Extrapolación ──────────────────────────────────────────────────────────────

def extrapolar(t_muestra, n_muestra, n_total):
    return t_muestra / n_muestra * n_total


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if not CSV.exists():
        print(f"No se encontró {CSV}. Ejecutar tests/generar_escala.py primero.")
        sys.exit(1)

    print(f"Cargando {CSV.name}…")
    df = pd.read_csv(CSV)
    print(f"  {len(df)} filas  |  {df['razon_social'].nunique()} valores únicos\n")

    print("=" * 65)
    print("  FASE 1 — Generación de candidatos por blocking")
    print("=" * 65)
    pares_cand, uniq_norm, t_bloqueo = fase1_blocking(df, 'razon_social')
    n_pares = len(pares_cand)
    print(f"  Pares generados: {n_pares:,}")
    print(f"  Tiempo:          {t_bloqueo:.1f} s\n")

    N_MUESTRA = min(500_000, n_pares)
    pct_muestra = N_MUESTRA / n_pares * 100

    print("=" * 65)
    print(f"  FASE 2+3 — Clave on-the-fly + sorted  (muestra {N_MUESTRA:,} pares = {pct_muestra:.0f}%)")
    print("=" * 65)
    t_clave, t_sort, n = fase23_sort_on_the_fly(pares_cand, uniq_norm, N_MUESTRA)
    t_clave_total = extrapolar(t_clave, n, n_pares)
    t_sort_total  = extrapolar(t_sort,  n, n_pares)
    print(f"  Cálculo de clave (trigramas on-the-fly):  {t_clave:.2f} s × {n_pares/n:.0f}x  →  {t_clave_total:.0f} s estimado total")
    print(f"  sorted() sobre claves ya calculadas:       {t_sort:.3f} s × {n_pares/n:.0f}x  →  {t_sort_total:.0f} s estimado total")
    print(f"  Total estimado Alt B original:             {t_bloqueo + t_clave_total + t_sort_total:.0f} s")

    print()
    print("=" * 65)
    print(f"  FASE 2+3 — Pre-calculado + heap  (muestra {N_MUESTRA:,} pares)")
    print("=" * 65)
    t_precomp, t_heap, n, tri = fase23_heap_precomputed(pares_cand, uniq_norm, N_MUESTRA)
    t_heap_total    = extrapolar(t_heap, n, n_pares)
    print(f"  Precálculo de trigramas ({len(uniq_norm):,} valores):   {t_precomp:.2f} s  (pago único)")
    print(f"  Heap sobre muestra de {n:,} pares:                 {t_heap:.2f} s × {n_pares/n:.0f}x  →  {t_heap_total:.0f} s estimado total")
    print(f"  Total estimado Alt B optimizado:           {t_bloqueo + t_precomp + t_heap_total:.0f} s")

    print()
    print("=" * 65)
    print("  RESUMEN")
    print("=" * 65)
    print(f"  Fase 1  — Blocking:                    {t_bloqueo:.1f} s")
    print(f"  Fase 2  — Clave on-the-fly (estimado): {t_clave_total:.0f} s  ← cuello de botella")
    print(f"  Fase 3  — sorted() (estimado):         {t_sort_total:.0f} s")
    print(f"  Alt B original (estimado total):       {t_bloqueo + t_clave_total + t_sort_total:.0f} s")
    print()
    print(f"  Con precálculo + heap (estimado total):{t_bloqueo + t_precomp + t_heap_total:.0f} s")
    print(f"  Mejora esperada: {(t_bloqueo + t_clave_total + t_sort_total) / (t_bloqueo + t_precomp + t_heap_total):.1f}×")
    print()
    print(f"  Objetivo: < 60 s para 20k")
    if t_bloqueo + t_precomp + t_heap_total < 60:
        print("  ✅ Objetivo alcanzable con precálculo + heap")
    else:
        print("  ⚠️  Puede requerir el enfoque por bloque (2.4)")
