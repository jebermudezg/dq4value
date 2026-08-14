"""
Mide el comportamiento del tope de pares a escala real (5k, 20k, 50k).

Para cada dataset con qgrams@86 + normalización:
  - Valores únicos
  - Pares candidatos antes y después del tope
  - Si el tope se activó
  - Pares verdaderos perdidos por el tope
  - Precisión, Recall, F1 del pipeline
  - Recall de Fuerza Bruta (solo 5k)
  - Tiempo total
  - Memoria pico

Si el tope pierde pares verdaderos, simula dos alternativas en 20k:
  Alternativa A — tope por bloque (N pares máx. por bloque, no global)
  Alternativa B — priorizar por similitud estimada (proporción de trigramas compartidos)

Ejecutar: python3 tests/medir_escala.py
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
    _calcular_similitud,
    _construir_bloques,
    _normalizar,
    check_similitud,
)

ALGORITMO = 'qgrams'
UMBRAL    = 86

# ── Helpers ────────────────────────────────────────────────────────────────────

def verdad_desde_df(df, id_col, verdad_col):
    pares = set()
    for _, g in df.groupby(verdad_col):
        if len(g) > 1:
            ids = sorted(g[id_col].tolist())
            pares |= set(itertools.combinations(ids, 2))
    return pares


def _pares_mem_pico_mb():
    """Pico de memoria RSS (MB). macOS retorna bytes; Linux, KB."""
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() == 'Darwin':   # macOS → bytes
        return usage / 1_048_576
    else:                               # Linux  → KB
        return usage / 1_024


def _pre_cap_stats(df, id_col, target_col, verdad, algoritmo, umbral):
    """
    Replica el paso de bloqueo + sub-agrupación de similitud.py para capturar
    el estado ANTES y DESPUÉS del tope de pares.
    Devuelve un dict con todas las métricas del bloqueo.
    """
    # Construir las mismas estructuras que check_similitud ──────────────────
    df = df.reset_index(drop=True)
    valores = df[target_col].tolist()
    ids     = df[id_col].tolist()

    unique_vals = {}
    for i, v in enumerate(valores):
        if pd.notna(v) and str(v).strip().lower() not in {'', 'nan'}:
            unique_vals.setdefault(str(v), []).append(i)

    uniq_raw  = list(unique_vals.keys())
    uniq_norm = [_normalizar(v) for v in uniq_raw]

    # Mapeo id_col → índice único (para convertir verdad a pares de índices)
    raw_to_uniq = {raw: i for i, raw in enumerate(uniq_raw)}
    id_to_raw   = {}
    for i, v in enumerate(valores):
        id_val = ids[i]
        if pd.notna(v):
            id_to_raw[id_val] = str(v)

    # Verdad en espacio de índices únicos (excluye pares con mismo norm — exactos)
    verdad_uniq = set()
    for id_a, id_b in verdad:
        raw_a = id_to_raw.get(id_a)
        raw_b = id_to_raw.get(id_b)
        if raw_a is None or raw_b is None:
            continue
        ui_a = raw_to_uniq.get(raw_a)
        ui_b = raw_to_uniq.get(raw_b)
        if ui_a is None or ui_b is None:
            continue
        if ui_a == ui_b:
            continue   # exactos normalizados — detectados por otra vía
        verdad_uniq.add((min(ui_a, ui_b), max(ui_a, ui_b)))

    # Bloqueo ────────────────────────────────────────────────────────────────
    valid_idx = [i for i, nv in enumerate(uniq_norm) if nv]
    bloques   = _construir_bloques(valid_idx, uniq_norm)

    max_bloque   = 100 if algoritmo == 'brecha_afin' else 200
    ratio_minimo = 0.25 if algoritmo in ALGORITMOS_TOLERANTES_LONGITUD else 0.0
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
                        if na and nb and min(len(na), len(nb)) / max(len(na), len(nb)) < ratio_minimo:
                            continue
                        pares_cand.add((min(sub_lista[a], sub_lista[b]),
                                        max(sub_lista[a], sub_lista[b])))
        else:
            for a in range(len(lista)):
                for b in range(a + 1, len(lista)):
                    na, nb = uniq_norm[lista[a]], uniq_norm[lista[b]]
                    if na and nb and min(len(na), len(nb)) / max(len(na), len(nb)) < ratio_minimo:
                        continue
                    pares_cand.add((min(lista[a], lista[b]),
                                    max(lista[a], lista[b])))

    n_antes = len(pares_cand)
    verd_antes = len(verdad_uniq & pares_cand)

    # Aplicar tope (igual que producción) ────────────────────────────────────
    tope_activado = False
    if algoritmo not in ALGORITMOS_TOLERANTES_LONGITUD and len(pares_cand) > 15_000:
        tope_activado = True
        pares_cand = set(
            sorted(
                pares_cand,
                key=lambda p: (
                    abs(len(uniq_norm[p[0]]) - len(uniq_norm[p[1]])),
                    uniq_norm[p[0]],
                    uniq_norm[p[1]],
                )
            )[:15_000]
        )
    elif algoritmo in ALGORITMOS_TOLERANTES_LONGITUD and len(pares_cand) > 50_000:
        tope_activado = True
        pares_cand = set(
            sorted(pares_cand,
                   key=lambda p: (uniq_norm[p[0]], uniq_norm[p[1]]))[:50_000]
        )

    n_despues  = len(pares_cand)
    verd_despues = len(verdad_uniq & pares_cand)

    return {
        'n_unicos':          len(uniq_raw),
        'n_bloques':         len(bloques),
        'n_antes':           n_antes,
        'tope_activado':     tope_activado,
        'n_despues':         n_despues,
        'descartados':       n_antes - n_despues,
        'verdad_uniq':       len(verdad_uniq),
        'verd_antes':        verd_antes,
        'verd_despues':      verd_despues,
        'verd_perdidos':     verd_antes - verd_despues,
        # Para alternativas
        '_uniq_norm':        uniq_norm,
        '_bloques':          bloques,
        '_verdad_uniq':      verdad_uniq,
        '_max_bloque':       max_bloque,
        '_ratio_minimo':     ratio_minimo,
    }


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
        vp = 0
        p, r, f1 = 0.0, 0.0, 0.0
    else:
        vp = len(det & verdad)
        p  = vp / len(det)
        r  = vp / len(verdad)
        f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1, elapsed


def recall_fb(df, id_col, target_col, verdad, algoritmo, umbral):
    """Recall de Fuerza Bruta — solo viable en ≤5k filas."""
    vals: dict = {}
    for _, row in df.iterrows():
        k = _normalizar(str(row[target_col]))
        vals.setdefault(k, []).append(row[id_col])
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


# ── Alternativas de recorte (solo evaluar si tope pierde pares) ───────────────

def _trigrama_jaccard(a, b):
    """Estimación barata de similitud por proporción de trigramas compartidos."""
    if len(a) < 3 or len(b) < 3:
        return 0.0
    qa = set(a[i:i+3] for i in range(len(a) - 2))
    qb = set(b[i:i+3] for i in range(len(b) - 2))
    inter = len(qa & qb)
    union = len(qa | qb)
    return inter / union if union else 0.0


def alternativa_a_tope_por_bloque(stats, max_por_bloque=100):
    """
    Alternativa A: tope POR BLOQUE en lugar de global.
    Cada bloque contribuye como máximo max_por_bloque pares.
    """
    uniq_norm    = stats['_uniq_norm']
    bloques      = stats['_bloques']
    verdad_uniq  = stats['_verdad_uniq']
    max_bloque   = stats['_max_bloque']
    ratio_minimo = stats['_ratio_minimo']

    pares_cand: set = set()
    for grupo in bloques.values():
        lista = sorted(grupo)
        pares_bloque = []

        if len(lista) > max_bloque:
            subgrupos: dict = {}
            for i in lista:
                sub = uniq_norm[i][:3] if len(uniq_norm[i]) >= 3 else uniq_norm[i]
                subgrupos.setdefault(sub, []).append(i)
            for sub_lista in subgrupos.values():
                for a in range(len(sub_lista)):
                    for b in range(a + 1, len(sub_lista)):
                        na, nb = uniq_norm[sub_lista[a]], uniq_norm[sub_lista[b]]
                        if na and nb and min(len(na), len(nb)) / max(len(na), len(nb)) < ratio_minimo:
                            continue
                        pares_bloque.append((min(sub_lista[a], sub_lista[b]),
                                             max(sub_lista[a], sub_lista[b])))
        else:
            for a in range(len(lista)):
                for b in range(a + 1, len(lista)):
                    na, nb = uniq_norm[lista[a]], uniq_norm[lista[b]]
                    if na and nb and min(len(na), len(nb)) / max(len(na), len(nb)) < ratio_minimo:
                        continue
                    pares_bloque.append((min(lista[a], lista[b]),
                                         max(lista[a], lista[b])))

        # Aplicar tope por bloque
        if len(pares_bloque) > max_por_bloque:
            pares_bloque = sorted(
                pares_bloque,
                key=lambda p: (
                    abs(len(uniq_norm[p[0]]) - len(uniq_norm[p[1]])),
                    uniq_norm[p[0]], uniq_norm[p[1]]
                )
            )[:max_por_bloque]

        pares_cand.update(pares_bloque)

    verd_alt = len(verdad_uniq & pares_cand)
    return {
        'nombre':         f'Alt A  (tope_bloque={max_por_bloque})',
        'n_pares':        len(pares_cand),
        'verd_supervivientes': verd_alt,
        'verd_perdidos':  len(verdad_uniq) - verd_alt,
    }


def alternativa_b_prioridad_trigrama(stats, tope_global=15_000):
    """
    Alternativa B: reemplaza el criterio abs(len_diff) por similitud estimada
    de trigramas (estimación barata) y selecciona los pares MÁS prometedores.
    """
    uniq_norm   = stats['_uniq_norm']
    verdad_uniq = stats['_verdad_uniq']
    n_antes     = stats['n_antes']

    # Re-construir pares sin tope (igual que _pre_cap_stats pero guardando la lista)
    bloques      = stats['_bloques']
    max_bloque   = stats['_max_bloque']
    ratio_minimo = stats['_ratio_minimo']

    pares_todos = []
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
                        if na and nb and min(len(na), len(nb)) / max(len(na), len(nb)) < ratio_minimo:
                            continue
                        pares_todos.append((min(sub_lista[a], sub_lista[b]),
                                            max(sub_lista[a], sub_lista[b])))
        else:
            for a in range(len(lista)):
                for b in range(a + 1, len(lista)):
                    na, nb = uniq_norm[lista[a]], uniq_norm[lista[b]]
                    if na and nb and min(len(na), len(nb)) / max(len(na), len(nb)) < ratio_minimo:
                        continue
                    pares_todos.append((min(lista[a], lista[b]),
                                        max(lista[a], lista[b])))

    # Deduplicar
    pares_todos = list(set(pares_todos))

    if len(pares_todos) <= tope_global:
        pares_cand = set(pares_todos)
    else:
        # Ordenar por trigrama Jaccard desc → seleccionar los top-tope_global
        pares_scored = sorted(
            pares_todos,
            key=lambda p: -_trigrama_jaccard(uniq_norm[p[0]], uniq_norm[p[1]])
        )
        pares_cand = set(pares_scored[:tope_global])

    verd_alt = len(verdad_uniq & pares_cand)
    return {
        'nombre':         f'Alt B  (trigrama_jaccard, tope={tope_global})',
        'n_pares':        len(pares_cand),
        'verd_supervivientes': verd_alt,
        'verd_perdidos':  len(verdad_uniq) - verd_alt,
    }


# ── Medición ──────────────────────────────────────────────────────────────────

DATASETS = [
    {'nombre': 'escala_5k',   'archivo': 'tests/escala_5k.csv',
     'id_col': 'empresa_id', 'target_col': 'razon_social', 'verdad_col': 'entidad_real_id',
     'fb': True},
    {'nombre': 'escala_20k',  'archivo': 'tests/escala_20k.csv',
     'id_col': 'empresa_id', 'target_col': 'razon_social', 'verdad_col': 'entidad_real_id',
     'fb': False},
    {'nombre': 'escala_50k',  'archivo': 'tests/escala_50k.csv',
     'id_col': 'empresa_id', 'target_col': 'razon_social', 'verdad_col': 'entidad_real_id',
     'fb': False},
]

resultados = []
hay_perdida_en_20k = False
stats_20k = None

for ds in DATASETS:
    print(f'\n{"="*78}')
    print(f'  Dataset: {ds["nombre"]}  (algoritmo={ALGORITMO}@{UMBRAL})')
    print(f'{"="*78}')

    try:
        df = pd.read_csv(ds['archivo'])
    except FileNotFoundError:
        print(f'  ⚠️  Archivo no encontrado: {ds["archivo"]}')
        print('     Ejecutar primero: python3 tests/generar_escala.py')
        continue

    verdad = verdad_desde_df(df, ds['id_col'], ds['verdad_col'])
    print(f'  Filas: {len(df)}  |  Pares verdaderos: {len(verdad)}')

    # ── Bloqueo + pre/post tope ──────────────────────────────────────────
    print('  Analizando bloqueo...')
    gc.collect()
    tracemalloc.start()
    mem_rss_antes = _pares_mem_pico_mb()
    t_bloqueo = time.time()

    stats = _pre_cap_stats(df, ds['id_col'], ds['target_col'],
                            verdad, ALGORITMO, UMBRAL)
    t_bloqueo = time.time() - t_bloqueo
    _, mem_pico_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    mem_pico_mb = mem_pico_bytes / 1_048_576
    mem_rss_pico = _pares_mem_pico_mb()

    print(f'  Únicos normalizados:   {stats["n_unicos"]:,}')
    print(f'  Bloques generados:     {stats["n_bloques"]:,}')
    print(f'  Pares candidatos:')
    print(f'    Antes del tope:      {stats["n_antes"]:,}')
    print(f'    Tope activado:       {"SÍ ⚠️" if stats["tope_activado"] else "no"}')
    if stats['tope_activado']:
        print(f'    Después del tope:   {stats["n_despues"]:,}  '
              f'(descartados: {stats["descartados"]:,})')
    print(f'  Verdaderos en cands:')
    print(f'    Antes del tope:      {stats["verd_antes"]} / {stats["verdad_uniq"]}')
    print(f'    Después del tope:    {stats["verd_despues"]} / {stats["verdad_uniq"]}')
    print(f'    PERDIDOS por tope:   {stats["verd_perdidos"]}', end='')
    if stats['verd_perdidos'] > 0:
        pct = stats["verd_perdidos"] / stats["verdad_uniq"] * 100
        print(f'  ({pct:.1f}%) ⚠️')
    else:
        print(' ✅')
    print(f'  Memoria tracemalloc pico: {mem_pico_mb:.1f} MB')
    print(f'  Memoria RSS pico:         {mem_rss_pico:.0f} MB')

    # ── Pipeline completo (P / R / F1 / tiempo) ──────────────────────────
    print('  Ejecutando pipeline completo...')
    gc.collect()
    mem_rss_antes2 = _pares_mem_pico_mb()
    p_pip, r_pip, f1_pip, t_pip = metricas_pipeline(
        df, ds['id_col'], ds['target_col'], verdad, ALGORITMO, UMBRAL
    )
    mem_rss_post2 = _pares_mem_pico_mb()
    print(f'  Pipeline P={p_pip:.3f} R={r_pip:.3f} F1={f1_pip:.3f}  t={t_pip:.1f}s')
    print(f'  Memoria RSS post-pipeline: {mem_rss_post2:.0f} MB')

    # ── Fuerza Bruta (solo 5k) ───────────────────────────────────────────
    p_fb = r_fb = f1_fb = None
    if ds['fb']:
        print('  Calculando Fuerza Bruta...')
        p_fb, r_fb, f1_fb = recall_fb(
            df, ds['id_col'], ds['target_col'], verdad, ALGORITMO, UMBRAL
        )
        print(f'  FB       P={p_fb:.3f} R={r_fb:.3f} F1={f1_fb:.3f}')

    # Guardar para tabla resumen
    resultados.append({
        'dataset':        ds['nombre'],
        'filas':          len(df),
        'n_unicos':       stats['n_unicos'],
        'verdad':         len(verdad),
        'n_antes':        stats['n_antes'],
        'tope':           stats['tope_activado'],
        'n_despues':      stats['n_despues'],
        'verd_perdidos':  stats['verd_perdidos'],
        'p_pip':          p_pip,
        'r_pip':          r_pip,
        'f1_pip':         f1_pip,
        'p_fb':           p_fb,
        'r_fb':           r_fb,
        'f1_fb':          f1_fb,
        't_pip':          t_pip,
        'mem_mb':         mem_rss_post2,
    })

    if ds['nombre'] == 'escala_20k' and stats['verd_perdidos'] > 0:
        hay_perdida_en_20k = True
        stats_20k = stats

# ── Tabla resumen ─────────────────────────────────────────────────────────────
print(f'\n\n{"="*100}')
print(f'  TABLA RESUMEN — Escala de similitud con {ALGORITMO}@{UMBRAL}')
print(f'{"="*100}')
hdr = (f'  {"Dataset":<14} {"Filas":>7} {"Únicos":>7} {"Verdad":>7} '
       f'{"Cands":>10} {"Tope":>5} {"V.perd":>7} '
       f'{"P_pip":>6} {"R_pip":>6} {"F1_pip":>7} '
       f'{"R_fb":>6} {"t(s)":>6} {"Mem(MB)":>8}')
print(hdr)
print(f'  {"-"*95}')
for r in resultados:
    tope_s  = 'SÍ⚠️' if r['tope'] else 'no'
    cands_s = f'{r["n_despues"]:,}' if r['tope'] else f'{r["n_antes"]:,}'
    r_fb_s  = f'{r["r_fb"]:.3f}' if r['r_fb'] is not None else '  N/A '
    verd_p_s = f'{r["verd_perdidos"]}⚠️' if r["verd_perdidos"] > 0 else '0 ✅'
    print(f'  {r["dataset"]:<14} {r["filas"]:>7,} {r["n_unicos"]:>7,} {r["verdad"]:>7} '
          f'{cands_s:>10} {tope_s:>5} {verd_p_s:>7} '
          f'{r["p_pip"]:>6.3f} {r["r_pip"]:>6.3f} {r["f1_pip"]:>7.3f} '
          f'{r_fb_s:>6} {r["t_pip"]:>6.1f} {r["mem_mb"]:>8.0f}')

print(f'\n  Cands = pares candidatos tras el tope  |  V.perd = pares verdaderos perdidos')
print(f'  R_fb = recall de Fuerza Bruta (solo 5k)')

# ── Alternativas (solo si 20k tiene pérdidas) ─────────────────────────────────
if hay_perdida_en_20k and stats_20k is not None:
    print(f'\n\n{"="*78}')
    print(f'  ALTERNATIVAS DE RECORTE — escala_20k  (punto 4)')
    print(f'{"="*78}')
    print(f'  Verdad total en espacio único: {stats_20k["verdad_uniq"]}')
    print(f'  Producción actual: {stats_20k["verd_despues"]} supervivientes '
          f'({stats_20k["verd_perdidos"]} perdidos)\n')

    print('  Calculando Alternativa A (tope por bloque = 100)...')
    alt_a = alternativa_a_tope_por_bloque(stats_20k, max_por_bloque=100)
    print('  Calculando Alternativa B (prioridad por trigramas)...')
    alt_b = alternativa_b_prioridad_trigrama(stats_20k, tope_global=15_000)

    print(f'\n  {"Variante":<40} {"Pares":>8} {"Superviv.":>10} {"Perdidos":>9}')
    print(f'  {"-"*68}')
    print(f'  {"Producción actual (global abs_len_diff)":<40} '
          f'{stats_20k["n_despues"]:>8,} '
          f'{stats_20k["verd_despues"]:>10} '
          f'{stats_20k["verd_perdidos"]:>9}')
    for alt in [alt_a, alt_b]:
        print(f'  {alt["nombre"]:<40} '
              f'{alt["n_pares"]:>8,} '
              f'{alt["verd_supervivientes"]:>10} '
              f'{alt["verd_perdidos"]:>9}')
    print()
    print('  Nota: las alternativas NO ejecutan el pipeline completo — solo miden')
    print('  cuántos pares verdaderos sobreviven al recorte (recall potencial máximo).')

elif not hay_perdida_en_20k:
    print('\n  ✅  El tope no pierde pares verdaderos en escala 20k.')
    print('     No se requiere comparar alternativas (punto 4 no aplica).')

# ── Límite práctico ──────────────────────────────────────────────────────────
print(f'\n\n{"="*78}')
print(f'  LÍMITE PRÁCTICO RECOMENDADO')
print(f'{"="*78}')
for r in resultados:
    if r['tope'] and r['verd_perdidos'] > 0:
        pct_perdido = r['verd_perdidos'] / r['verdad'] * 100 if r['verdad'] else 0
        print(f'  ⚠️  En {r["dataset"]} ({r["n_unicos"]:,} únicos): '
              f'{pct_perdido:.0f}% de pares verdaderos perdidos por tope.')
        print(f'     Tiempo: {r["t_pip"]:.0f}s  |  Memoria: {r["mem_mb"]:.0f} MB')
    elif r['tope']:
        print(f'  ✅  En {r["dataset"]} ({r["n_unicos"]:,} únicos): '
              f'tope activado pero sin pérdida de pares verdaderos.')
    else:
        print(f'  ✅  En {r["dataset"]} ({r["n_unicos"]:,} únicos): '
              f'tope NO activado. t={r["t_pip"]:.1f}s  mem={r["mem_mb"]:.0f}MB')

# Umbral donde el tope empieza a ser problemático
primero_con_perdida = next(
    (r for r in resultados if r['tope'] and r['verd_perdidos'] > 0), None
)
if primero_con_perdida:
    n_uniq = primero_con_perdida['n_unicos']
    t_pip  = primero_con_perdida['t_pip']
    print(f'\n  → Umbral de confiabilidad: < {n_uniq:,} valores únicos.')
    print(f'    Con {n_uniq:,} únicos el análisis ya NO es confiable.')
    print(f'    Sugerencia frontend: advertir cuando N_únicos > 15.000 '
          f'(tope activo → muestra parcial).')
    print(f'    Tiempo estimado: ~{t_pip:.0f}s para {primero_con_perdida["filas"]:,} filas.')
else:
    ultimo = resultados[-1] if resultados else None
    if ultimo:
        n_uniq = ultimo['n_unicos']
        print(f'\n  → El tope no pierde pares verdaderos en ninguna escala probada.')
        print(f'    Máximo probado: {n_uniq:,} únicos en {ultimo["dataset"]}.')
