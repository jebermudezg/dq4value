import pandas as pd
import re
import numpy as np
from unidecode import unidecode
import jellyfish
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _normalizar(texto):
    if pd.isna(texto):
        return ''
    texto = unidecode(str(texto).lower().strip())
    texto = re.sub(r'[^a-z0-9\s]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto


def _brecha_afin(a, b, match=2, mismatch=-1, gap_open=-1, gap_extend=-0.1):
    """
    Similitud de Brecha Afín (Affine Gap).
    Penaliza abrir una brecha más que extenderla.
    Ideal para abreviaturas y tokens faltantes.
    Retorna score normalizado 0-100.
    """
    if not a or not b:
        return 0.0
    n, m = len(a), len(b)
    # Tres matrices:
    # M[i][j] = mejor score cuando a[i-1] y b[j-1] están alineados
    # X[i][j] = mejor score cuando a[i-1] está en una brecha (gap en b)
    # Y[i][j] = mejor score cuando b[j-1] está en una brecha (gap en a)
    NEG_INF = float('-inf')
    M = [[NEG_INF] * (m + 1) for _ in range(n + 1)]
    X = [[NEG_INF] * (m + 1) for _ in range(n + 1)]
    Y = [[NEG_INF] * (m + 1) for _ in range(n + 1)]
    M[0][0] = 0
    for i in range(1, n + 1):
        X[i][0] = gap_open + (i - 1) * gap_extend
    for j in range(1, m + 1):
        Y[0][j] = gap_open + (j - 1) * gap_extend
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            sim = match if a[i-1] == b[j-1] else mismatch
            M[i][j] = sim + max(
                M[i-1][j-1] if M[i-1][j-1] != NEG_INF else NEG_INF,
                X[i-1][j-1] if X[i-1][j-1] != NEG_INF else NEG_INF,
                Y[i-1][j-1] if Y[i-1][j-1] != NEG_INF else NEG_INF
            )
            X[i][j] = max(
                M[i-1][j] + gap_open if M[i-1][j] != NEG_INF else NEG_INF,
                X[i-1][j] + gap_extend if X[i-1][j] != NEG_INF else NEG_INF
            )
            Y[i][j] = max(
                M[i][j-1] + gap_open if M[i][j-1] != NEG_INF else NEG_INF,
                Y[i][j-1] + gap_extend if Y[i][j-1] != NEG_INF else NEG_INF
            )
    score_raw = max(
        M[n][m] if M[n][m] != NEG_INF else 0,
        X[n][m] if X[n][m] != NEG_INF else 0,
        Y[n][m] if Y[n][m] != NEG_INF else 0
    )
    # Normalizar: score máximo posible = match * min(n, m)
    score_max = match * min(n, m)
    if score_max <= 0:
        return 0.0
    score_norm = max(0.0, score_raw / score_max) * 100
    return min(score_norm, 100.0)


def _calcular_similitud(a, b, algoritmo):
    """Calcula similitud entre dos strings usando el algoritmo especificado."""
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
        dist = jellyfish.levenshtein_distance(a, b)
        return (1 - dist / max_len) * 100

    elif algoritmo == 'soundex':
        tokens_a = [jellyfish.soundex(t) for t in a.split() if t]
        tokens_b = [jellyfish.soundex(t) for t in b.split() if t]
        if not tokens_a or not tokens_b:
            return 0.0
        comunes = len(set(tokens_a) & set(tokens_b))
        total = max(len(set(tokens_a)), len(set(tokens_b)))
        return (comunes / total) * 100 if total > 0 else 0.0

    elif algoritmo == 'monge_elkan':
        tokens_a = a.split()
        tokens_b = b.split()
        if not tokens_a or not tokens_b:
            return 0.0
        scores = []
        for ta in tokens_a:
            mejor = max(jellyfish.jaro_winkler_similarity(ta, tb) for tb in tokens_b)
            scores.append(mejor)
        return (sum(scores) / len(scores)) * 100

    elif algoritmo == 'qgrams':
        def get_qgrams(s, q=3):
            return set(s[i:i + q] for i in range(len(s) - q + 1))
        qa = get_qgrams(a)
        qb = get_qgrams(b)
        if not qa or not qb:
            return 0.0
        interseccion = len(qa & qb)
        union = len(qa | qb)
        return (interseccion / union) * 100 if union > 0 else 0.0

    elif algoritmo == 'coseno':
        try:
            vectorizer = TfidfVectorizer()
            matriz = vectorizer.fit_transform([a, b])
            score = cosine_similarity(matriz[0], matriz[1])[0][0]
            return score * 100
        except Exception:
            return 0.0

    elif algoritmo == 'brecha_afin':
        return _brecha_afin(a, b)

    elif algoritmo == 'smith_waterman':
        match = 2
        mismatch = -1
        gap = -1
        n, m = len(a), len(b)
        H = np.zeros((n + 1, m + 1))
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                diag = H[i - 1][j - 1] + (match if a[i - 1] == b[j - 1] else mismatch)
                up = H[i - 1][j] + gap
                left = H[i][j - 1] + gap
                H[i][j] = max(0, diag, up, left)
        max_score = H.max()
        max_posible = match * min(n, m)
        return (max_score / max_posible) * 100 if max_posible > 0 else 0.0

    return 0.0


def _construir_bloques(indices, valores_norm):
    """Blocking inteligente con 4 estrategias para reducir comparaciones."""
    bloques = {}

    for i in indices:
        v = valores_norm[i]

        if len(v) >= 2:
            bloques.setdefault('pref_' + v[:2], set()).add(i)

        primer_token = v.split()[0] if v.split() else ''
        if primer_token and len(primer_token) >= 2:
            try:
                sx = jellyfish.soundex(primer_token)
                bloques.setdefault('sdx_' + sx, set()).add(i)
            except Exception:
                pass

        grupo_len = (len(v) // 5) * 5
        bloques.setdefault(f'len_{grupo_len}', set()).add(i)

        tokens = [t for t in v.split() if len(t) > 3]
        for token in tokens:
            bloques.setdefault('tok_' + token, set()).add(i)

    return bloques


def check_similitud(df, id_col, target_col, **params):
    umbral = float(params.get('umbral', 92))
    algoritmo = params.get('algoritmo', 'jaro_winkler')
    normalizar_texto = params.get('normalizar', True)

    df = df.reset_index(drop=True)
    valores = df[target_col].tolist()
    ids = df[id_col].tolist()

    if normalizar_texto:
        valores_norm = [_normalizar(v) for v in valores]
    else:
        valores_norm = [str(v).lower().strip() if not pd.isna(v) else '' for v in valores]

    indices_validos = [i for i, v in enumerate(valores_norm) if v]
    bloques = _construir_bloques(indices_validos, valores_norm)

    pares_candidatos = set()
    for llave, grupo in bloques.items():
        lista = sorted(grupo)
        if len(lista) > 200:
            subgrupos = {}
            for i in lista:
                sub = valores_norm[i][:3] if len(valores_norm[i]) >= 3 else valores_norm[i]
                subgrupos.setdefault(sub, []).append(i)
            for sub_lista in subgrupos.values():
                for a in range(len(sub_lista)):
                    for b in range(a + 1, len(sub_lista)):
                        pares_candidatos.add((sub_lista[a], sub_lista[b]))
        else:
            for a in range(len(lista)):
                for b in range(a + 1, len(lista)):
                    pares_candidatos.add((lista[a], lista[b]))

    total_pares = len(pares_candidatos)
    warning = f' | Pares comparados: {total_pares:,}' if total_pares > 10000 else ''

    similares: dict = {}
    for i, j in pares_candidatos:
        score = _calcular_similitud(valores_norm[i], valores_norm[j], algoritmo)
        if score >= umbral:
            similares.setdefault(i, []).append((j, score, valores[j]))
            similares.setdefault(j, []).append((i, score, valores[i]))

    issues_rows = []
    for idx, parecidos in similares.items():
        mejor = max(parecidos, key=lambda x: x[1])
        idx_similar, score_sim, val_similar = mejor
        issues_rows.append({
            id_col: ids[idx],
            'columna': target_col,
            'dimension': 'similitud',
            'descripcion': (
                f"Similar a [ID: {ids[idx_similar]}] '{valores[idx_similar]}' — "
                f"{score_sim:.1f}% similitud ({algoritmo})"
            ),
            'valor_encontrado': f"[ID: {ids[idx]}] {str(valores[idx])}",
        })

    issues_df = (
        pd.DataFrame(issues_rows)
        if issues_rows
        else pd.DataFrame(columns=[id_col, 'columna', 'dimension', 'descripcion', 'valor_encontrado'])
    )

    score = round((1 - len(similares) / len(df)) * 100, 2) if len(df) > 0 else 100.0
    return score, issues_df
