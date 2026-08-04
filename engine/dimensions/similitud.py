import pandas as pd
import numpy as np
import re
from unidecode import unidecode
import jellyfish
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


PLACEHOLDERS = {
    'n/a', 'na', 'n.a.', '-', '--', '---', 'sin dato', 'sin datos',
    'sin nombre', 's/n', 's/d', 'null', 'none', 'ninguno', '.', '0',
}


def _es_placeholder(valor) -> bool:
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return True
    try:
        if pd.isna(valor):
            return True
    except Exception:
        pass
    v = str(valor).strip().lower()
    return v == '' or v in PLACEHOLDERS


def _normalizar(texto: str) -> str:
    if pd.isna(texto):
        return ''
    texto = unidecode(str(texto).lower().strip())
    texto = re.sub(r'[^a-z0-9\s]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto


def _brecha_afin(a, b, match=2, mismatch=-1, gap_open=-1, gap_extend=-0.1):
    """
    Affine Gap alignment similarity (0-100).
    Penalises gap opening more than extension — good for abbreviations.
    """
    if not a or not b:
        return 0.0
    len_a, len_b = len(a), len(b)
    if min(len_a, len_b) / max(len_a, len_b) < 0.4:
        return 0.0
    a, b = a[:50], b[:50]
    n, m = len(a), len(b)
    INF = float('-inf')
    M = [[INF] * (m + 1) for _ in range(n + 1)]
    X = [[INF] * (m + 1) for _ in range(n + 1)]
    Y = [[INF] * (m + 1) for _ in range(n + 1)]
    M[0][0] = 0.0
    for i in range(1, n + 1):
        X[i][0] = gap_open + (i - 1) * gap_extend
    for j in range(1, m + 1):
        Y[0][j] = gap_open + (j - 1) * gap_extend
    for i in range(1, n + 1):
        ai = a[i - 1]
        Mi1 = M[i - 1]; Xi1 = X[i - 1]; Yi1 = Y[i - 1]
        Mi  = M[i];     Xi  = X[i];     Yi  = Y[i]
        for j in range(1, m + 1):
            sim = match if ai == b[j - 1] else mismatch
            Mi[j]  = sim + max(Mi1[j-1], Xi1[j-1], Yi1[j-1])
            Xi[j]  = max(Mi1[j] + gap_open, Xi1[j] + gap_extend)
            Yi[j]  = max(Mi[j-1] + gap_open, Yi[j-1] + gap_extend)
    score_raw = max(M[n][m], X[n][m], Y[n][m], 0.0)
    score_max = match * min(n, m)
    if score_max <= 0:
        return 0.0
    return min(max(0.0, score_raw / score_max) * 100, 100.0)


def _calcular_similitud(a: str, b: str, algoritmo: str) -> float:
    if not a or not b:
        return 0.0

    if algoritmo == 'jaro_winkler':
        return jellyfish.jaro_winkler_similarity(a, b) * 100

    elif algoritmo == 'jaro':
        return jellyfish.jaro_similarity(a, b) * 100

    elif algoritmo == 'levenshtein':
        max_len = max(len(a), len(b))
        if max_len == 0:
            return 100.0
        return (1 - jellyfish.levenshtein_distance(a, b) / max_len) * 100

    elif algoritmo == 'soundex':
        tokens_a = [jellyfish.soundex(t) for t in a.split() if t]
        tokens_b = [jellyfish.soundex(t) for t in b.split() if t]
        if not tokens_a or not tokens_b:
            return 0.0
        comunes = len(set(tokens_a) & set(tokens_b))
        total   = max(len(set(tokens_a)), len(set(tokens_b)))
        return (comunes / total) * 100 if total > 0 else 0.0

    elif algoritmo == 'monge_elkan':
        tokens_a = a.split()
        tokens_b = b.split()
        if not tokens_a or not tokens_b:
            return 0.0
        scores = [
            max(jellyfish.jaro_winkler_similarity(ta, tb) for tb in tokens_b)
            for ta in tokens_a
        ]
        return (sum(scores) / len(scores)) * 100

    elif algoritmo == 'qgrams':
        def get_qgrams(s, q=3):
            return set(s[i:i + q] for i in range(len(s) - q + 1))
        qa, qb = get_qgrams(a), get_qgrams(b)
        if not qa or not qb:
            return 0.0
        interseccion = len(qa & qb)
        union = len(qa | qb)
        return (interseccion / union) * 100 if union > 0 else 0.0

    elif algoritmo == 'coseno':
        try:
            vectorizer = TfidfVectorizer()
            matriz = vectorizer.fit_transform([a, b])
            return cosine_similarity(matriz[0], matriz[1])[0][0] * 100
        except Exception:
            return 0.0

    elif algoritmo == 'smith_waterman':
        match, mismatch, gap = 2, -1, -1
        n, m = len(a), len(b)
        H = np.zeros((n + 1, m + 1))
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                diag = H[i-1][j-1] + (match if a[i-1] == b[j-1] else mismatch)
                H[i][j] = max(0, diag, H[i-1][j] + gap, H[i][j-1] + gap)
        max_score   = H.max()
        max_posible = match * min(n, m)
        return (max_score / max_posible) * 100 if max_posible > 0 else 0.0

    elif algoritmo == 'brecha_afin':
        return _brecha_afin(a, b)

    return 0.0


def _construir_bloques(indices: list, valores_norm: list) -> dict:
    """Blocking with 4 strategies to cut down comparison count."""
    bloques: dict = {}
    for i in indices:
        v = valores_norm[i]
        if len(v) >= 2:
            bloques.setdefault('pref_' + v[:2], set()).add(i)
        primer_token = v.split()[0] if v.split() else ''
        if primer_token and len(primer_token) >= 2:
            try:
                bloques.setdefault('sdx_' + jellyfish.soundex(primer_token), set()).add(i)
            except Exception:
                pass
        bloques.setdefault(f'len_{(len(v) // 5) * 5}', set()).add(i)
        for token in [t for t in v.split() if len(t) > 3]:
            bloques.setdefault('tok_' + token, set()).add(i)
    return bloques


def _union_find_groups(record_pairs: list, n: int) -> dict:
    """Union-Find over record indices; returns root -> [member indices]."""
    parent = list(range(n))
    rank   = [0] * n

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px == py:
            return
        if rank[px] < rank[py]:
            px, py = py, px
        parent[py] = px
        if rank[px] == rank[py]:
            rank[px] += 1

    involved = set()
    for ri, rj in record_pairs:
        union(ri, rj)
        involved.add(ri)
        involved.add(rj)

    groups: dict = {}
    for ri in involved:
        groups.setdefault(find(ri), []).append(ri)
    return groups


def check_similitud(
    df: pd.DataFrame, id_col: str, target_col: str, **params
) -> tuple:
    """
    Detects near-duplicate records in target_col.

    Returns (score, issues_df, metadata) where:
      - issues_df has one row per involved record (principal + excedentes)
      - metadata contains: total_grupos, total_involucrados, total_excedentes,
        duplicados_exactos_excluidos, placeholders_excluidos, total_evaluados,
        algoritmo, umbral, normalizar, grupos_grandes

    Counting model:
      score = (1 - total_excedentes / total_evaluados) * 100
      total_excedentes = total_involucrados - total_grupos

    Exclusions:
      - Placeholder / null values      (→ completitud, not counted here)
      - Byte-identical raw value pairs (→ unicidad, counted in dup_exactos_excluidos)
      - Different raw but same normalized (100%) → COUNTED (formatting variation)
    """
    umbral         = float(params.get('umbral', 92))
    algoritmo      = str(params.get('algoritmo', 'jaro_winkler'))
    normalizar_txt = params.get('normalizar', True)

    df     = df.reset_index(drop=True)
    valores = df[target_col].tolist()
    ids     = df[id_col].tolist()

    # ── Step 1: exclude placeholders, map unique raw values ──────────────
    unique_vals: dict[str, list] = {}   # raw_str -> [record indices]
    placeholders_excluidos = 0

    for i, v in enumerate(valores):
        if _es_placeholder(v):
            placeholders_excluidos += 1
        else:
            unique_vals.setdefault(str(v), []).append(i)

    # Records sharing an identical raw value with at least one other record
    dup_exactos_excluidos = sum(
        len(idxs) for idxs in unique_vals.values() if len(idxs) > 1
    )

    uniq_raw  = list(unique_vals.keys())
    if normalizar_txt:
        uniq_norm = [_normalizar(v) for v in uniq_raw]
    else:
        uniq_norm = [str(v).lower().strip() for v in uniq_raw]

    total_evaluados = len(df) - placeholders_excluidos

    def _base_meta(total_grupos=0, total_involucrados=0, total_excedentes=0, grupos_grandes=0):
        return {
            'total_grupos':                 total_grupos,
            'total_involucrados':           total_involucrados,
            'total_excedentes':             total_excedentes,
            'duplicados_exactos_excluidos': dup_exactos_excluidos,
            'placeholders_excluidos':       placeholders_excluidos,
            'total_evaluados':              total_evaluados,
            'algoritmo':                    algoritmo,
            'umbral':                       umbral,
            'normalizar':                   bool(normalizar_txt),
            'grupos_grandes':               grupos_grandes,
        }

    # ── Step 2: blocking on unique-value indices ──────────────────────────
    valid_idx = [i for i, nv in enumerate(uniq_norm) if nv]
    if len(valid_idx) < 2:
        return 100.0, _empty_df(id_col), _base_meta()

    bloques = _construir_bloques(valid_idx, uniq_norm)

    max_bloque = 100 if algoritmo == 'brecha_afin' else 200
    pares_cand: set[tuple] = set()

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
                        pares_cand.add((sub_lista[a], sub_lista[b]))
        else:
            for a in range(len(lista)):
                for b in range(a + 1, len(lista)):
                    pares_cand.add((lista[a], lista[b]))

    if algoritmo == 'brecha_afin' and len(pares_cand) > 15_000:
        pares_cand = set(
            sorted(
                pares_cand,
                key=lambda p: abs(len(uniq_norm[p[0]]) - len(uniq_norm[p[1]]))
            )[:15_000]
        )

    # ── Step 3: compare unique-value pairs ───────────────────────────────
    # All pairs here have different raw values (deduplication guarantees
    # uniq_raw[i] != uniq_raw[j] for i != j), so byte-identical exclusion is implicit.
    similar_pares: list[tuple] = []   # (ui, uj, score)

    for ui, uj in pares_cand:
        nv_i, nv_j = uniq_norm[ui], uniq_norm[uj]
        if nv_i == nv_j:
            sim_score = 100.0          # different raw, same normalized → formatting variation
        else:
            sim_score = _calcular_similitud(nv_i, nv_j, algoritmo)
        if sim_score >= umbral:
            similar_pares.append((ui, uj, sim_score))

    if not similar_pares:
        return 100.0, _empty_df(id_col), _base_meta()

    # ── Step 4: expand unique-value pairs to record pairs ────────────────
    record_pairs: list[tuple] = []
    record_max_sim: dict[int, float] = {}

    for ui, uj, sim_score in similar_pares:
        for ri in unique_vals[uniq_raw[ui]]:
            for rj in unique_vals[uniq_raw[uj]]:
                record_pairs.append((ri, rj))
                record_max_sim[ri] = max(record_max_sim.get(ri, 0.0), sim_score)
                record_max_sim[rj] = max(record_max_sim.get(rj, 0.0), sim_score)

    # ── Step 5: transitive closure → groups ──────────────────────────────
    groups = _union_find_groups(record_pairs, len(df))

    total_grupos       = len(groups)
    total_involucrados = sum(len(m) for m in groups.values())
    total_excedentes   = total_involucrados - total_grupos  # per group: len(members) - 1

    # ── Step 6: suggest principal per group ──────────────────────────────
    def _principal(members: list) -> int:
        def null_count(idx):  return int(df.iloc[idx].isna().sum())
        def val_len(idx):
            v = df.iloc[idx][target_col]
            return len(str(v)) if not pd.isna(v) else 0
        def rec_id(idx):      return str(ids[idx])
        return sorted(members, key=lambda i: (null_count(i), -val_len(i), rec_id(i)))[0]

    # ── Step 7: build issues_df — ALL involucrados ────────────────────────
    grupos_grandes = 0
    rows = []
    sorted_groups = sorted(groups.items(), key=lambda kv: min(kv[1]))
    for group_num, (_, members) in enumerate(sorted_groups, start=1):
        grupo_id     = f"G{group_num:03d}"
        grupo_grande = len(members) > 10
        if grupo_grande:
            grupos_grandes += 1
        principal_ri  = _principal(members)
        principal_raw = str(valores[principal_ri])
        group_exc     = len(members) - 1

        desc_base = (
            f"Grupo {grupo_id} · conservar '{principal_raw}' "
            f"({group_exc} de {len(members)} registros a corregir)"
        )
        if grupo_grande:
            desc_base += (
                f" — grupo grande ({len(members)} registros), considera subir el umbral"
            )

        for ri in members:
            es_principal = (ri == principal_ri)
            rows.append({
                id_col:                  ids[ri],
                'columna':               target_col,
                'dimension':             'similitud',
                'descripcion':           desc_base,
                'valor_encontrado':      str(valores[ri]),
                'valor_correcto':        None if es_principal else principal_raw,
                'grupo_id':              grupo_id,
                'similitud_pct':         round(record_max_sim.get(ri, 0.0), 1),
                'es_principal_sugerido': es_principal,
                'grupo_grande':          bool(grupo_grande),
            })

    score = (
        round(max(0.0, min(100.0,
              (1 - total_excedentes / total_evaluados) * 100)), 1)
        if total_evaluados > 0 else 100.0
    )

    metadata = _base_meta(total_grupos, total_involucrados, total_excedentes, grupos_grandes)

    return score, pd.DataFrame(rows), metadata


def _empty_df(id_col: str) -> pd.DataFrame:
    cols = [
        id_col, 'columna', 'dimension', 'descripcion', 'valor_encontrado',
        'valor_correcto', 'grupo_id', 'similitud_pct', 'es_principal_sugerido', 'grupo_grande',
    ]
    return pd.DataFrame(columns=cols)
