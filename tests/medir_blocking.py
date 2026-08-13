"""
Mide la contribución de cada estrategia de blocking y detecta pares huérfanos.
Ejecutar: python3 tests/medir_blocking.py
"""
import itertools
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.dimensions.similitud import _normalizar, _calcular_similitud

df = pd.read_csv('tests/maestro_proveedores_1000.csv')
COL, IDC = 'razon_social', 'proveedor_id'

verdad: set = set()
for _, g in df.groupby('ruc'):
    if len(g) > 1:
        verdad |= set(itertools.combinations(sorted(g[IDC].tolist()), 2))

vals: dict = {}
for _, r in df.iterrows():
    vals.setdefault(_normalizar(str(r[COL])), []).append(r[IDC])

claves = sorted(vals)

# Pares verdaderos expresados sobre valores normalizados (distintos)
verdad_norm: set = set()
for a, b in verdad:
    na = _normalizar(str(df[df[IDC] == a][COL].iloc[0]))
    nb = _normalizar(str(df[df[IDC] == b][COL].iloc[0]))
    if na != nb:
        verdad_norm.add(tuple(sorted((na, nb))))

print(f'Pares verdaderos entre valores distintos: {len(verdad_norm)}\n')


# ── Reproducir cada estrategia por separado ────────────────────
def est_prefijo(ks, n=3):
    g: dict = {}
    for k in ks:
        g.setdefault(k[:n], []).append(k)
    p: set = set()
    for v in g.values():
        p |= set(itertools.combinations(sorted(v), 2))
    return p


def est_tokens(ks, minlen=3):
    g: dict = {}
    for k in ks:
        for t in set(k.split()):
            if len(t) >= minlen:
                g.setdefault(t, []).append(k)
    p: set = set()
    for v in g.values():
        if len(v) <= 200:
            p |= set(itertools.combinations(sorted(set(v)), 2))
    return p


def est_longitud(ks, ratio_min):
    p: set = set()
    orden = sorted(ks, key=len)
    for i, a in enumerate(orden):
        for b in orden[i + 1:]:
            if len(a) / len(b) < ratio_min:
                break
            p.add(tuple(sorted((a, b))))
    return p


ests = {
    'prefijo 3 letras':   est_prefijo(claves),
    'tokens compartidos': est_tokens(claves),
    'longitud 0.70':      est_longitud(claves, 0.70),
    'longitud 0.25':      est_longitud(claves, 0.25),
}

print(f'{"Estrategia":<22}{"Pares":>10}{"Verdaderos que propone":>26}')
print('-' * 58)
for nom, p in ests.items():
    cubre = len({x for x in verdad_norm if x in p})
    print(f'{nom:<22}{len(p):>10,}{cubre:>18} / {len(verdad_norm)}')

union = ests['prefijo 3 letras'] | ests['tokens compartidos'] | ests['longitud 0.25']
cubre_u = len({x for x in verdad_norm if x in union})
print(f'\n{"UNIÓN de las tres":<22}{len(union):>10,}{cubre_u:>18} / {len(verdad_norm)}')

# ── Los que ninguna estrategia propone ────────────────────────
huerfanos = [x for x in verdad_norm if x not in union]
print(f'\nPARES VERDADEROS QUE NINGUNA ESTRATEGIA PROPONE: {len(huerfanos)}')
for a, b in sorted(huerfanos)[:15]:
    s = _calcular_similitud(a, b, 'qgrams')
    pre = 'sí' if a[:3] == b[:3] else 'no'
    tk = 'sí' if set(a.split()) & set(b.split()) else 'no'
    # también mostrar tokens por separado para diagnóstico
    toks_a = {t for t in a.split() if len(t) >= 3}
    toks_b = {t for t in b.split() if len(t) >= 3}
    shared_toks = toks_a & toks_b
    print(f'  sim={s:5.1f}%  pref3={pre}  tokens={tk}  difLong={abs(len(a) - len(b)):2}  '
          f'shared_toks={sorted(shared_toks)}')
    print(f'      {a}')
    print(f'      {b}')

# ── Detalle de la estrategia de tokens en los pares perdidos ──
print('\n── DETALLE TOKENS en pares huérfanos ──')
print(f'  (minlen=3, igual que _construir_bloques que usa len(t) > 3 → minlen=4)')
for a, b in sorted(huerfanos)[:15]:
    toks_a3 = {t for t in a.split() if len(t) >= 3}
    toks_b3 = {t for t in b.split() if len(t) >= 3}
    toks_a4 = {t for t in a.split() if len(t) > 3}
    toks_b4 = {t for t in b.split() if len(t) > 3}
    print(f'  A tok≥3={sorted(toks_a3)}')
    print(f'  B tok≥3={sorted(toks_b3)}')
    print(f'  A tok>3={sorted(toks_a4)}')
    print(f'  B tok>3={sorted(toks_b4)}')
    print(f'  ∩ tok>3={sorted(toks_a4 & toks_b4)}')
    print()
