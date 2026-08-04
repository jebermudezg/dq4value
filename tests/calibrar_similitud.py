"""
Calibración de similitud por F1 con verdad terreno (RUC).

Uso:
  python3 tests/calibrar_similitud.py               # todos los algoritmos
  python3 tests/calibrar_similitud.py monge_elkan   # un algoritmo
"""
import sys
import time
import pandas as pd
from collections import defaultdict

sys.path.insert(0, '.')
from engine.dimensions.similitud import check_similitud

df = pd.read_csv('tests/maestro_proveedores_1000.csv')

# ── Verdad terreno: pares que comparten RUC ──────────────────────────────────
ruc_to_ids = defaultdict(list)
ruc_to_nombres = defaultdict(list)
for _, row in df.iterrows():
    ruc_to_ids[row['ruc']].append(int(row['proveedor_id']))
    ruc_to_nombres[row['ruc']].append(str(row['razon_social']))

verdad = set()
for ruc, ids in ruc_to_ids.items():
    if len(ids) > 1:
        ids_s = sorted(ids)
        for i, a in enumerate(ids_s):
            for b in ids_s[i + 1:]:
                verdad.add((a, b))

# ── Inspección de verdad terreno ─────────────────────────────────────────────
print("Pares con mismo RUC — verificacion de verdad terreno:")
for ruc, grupo in df.groupby('ruc'):
    if len(grupo) > 1:
        nombres = grupo['razon_social'].tolist()
        ids = grupo['proveedor_id'].tolist()
        print(f"  RUC {ruc}: {len(grupo)} registros")
        for i, n in zip(ids, nombres):
            print(f"    {i}: {n}")
print()

print(f"Pares verdaderos (mismo RUC): {len(verdad)}")
print(f"Grupos verdaderos:            {sum(1 for ids in ruc_to_ids.values() if len(ids) > 1)}")
print()


def calibrar(algoritmo: str, umbrales: list) -> list:
    resultados = []
    t0 = time.time()
    for umbral in umbrales:
        score, issues, meta = check_similitud(
            df, 'proveedor_id', 'razon_social',
            algoritmo=algoritmo, umbral=umbral, normalizar=True
        )
        detectados = set()
        if not issues.empty and 'grupo_id' in issues.columns:
            for gid, g in issues.groupby('grupo_id'):
                if g['grupo_disperso'].any():
                    continue
                ids = sorted(g['proveedor_id'].astype(int).tolist())
                for i, a in enumerate(ids):
                    for b in ids[i + 1:]:
                        detectados.add((a, b))

        vp = len(detectados & verdad)
        fp = len(detectados - verdad)
        fn = len(verdad - detectados)
        prec = vp / (vp + fp) if (vp + fp) else 0.0
        exh  = vp / (vp + fn) if (vp + fn) else 0.0
        f1   = 2 * prec * exh / (prec + exh) if (prec + exh) else 0.0
        resultados.append({
            'umbral':  umbral,
            'prec':    prec,
            'exh':     exh,
            'f1':      f1,
            'grupos':  meta.get('total_grupos', 0),
            'disp':    meta.get('grupos_dispersos_excluidos', 0),
            'score':   score,
            'estado':  meta.get('estado_confiabilidad', '—'),
            'rcp':     meta.get('registros_con_algun_par', 0),
        })
    elapsed = time.time() - t0
    return resultados, elapsed


ALGORITMOS = [
    'jaro_winkler', 'brecha_afin', 'monge_elkan', 'levenshtein',
    'qgrams', 'smith_waterman', 'soundex', 'coseno',
]
UMBRALES = [78, 82, 86, 90, 92, 94, 96]

filtro = sys.argv[1] if len(sys.argv) > 1 else None
if filtro:
    ALGORITMOS = [a for a in ALGORITMOS if a == filtro]

resumen = []  # best per algorithm

for algo in ALGORITMOS:
    print(f"\n{'─'*70}")
    print(f"  {algo}")
    print(f"{'─'*70}")
    col_w = 72
    header = (
        f"  {'Umbral':>7} {'Prec':>7} {'Exh':>7} {'F1':>6}  "
        f"{'Grupos':>7} {'Disp':>5} {'Score':>7} {'Estado':>14}  {'Regs/par':>8}"
    )
    print(header)
    print("  " + "-" * (col_w - 2))
    resultados, elapsed = calibrar(algo, UMBRALES)

    best_confiable = None
    for r in resultados:
        marker = ""
        if r['estado'] == 'confiable':
            if best_confiable is None or r['f1'] > best_confiable['f1']:
                best_confiable = r
                marker = " ◀"
        print(
            f"  {r['umbral']:>6}%  {r['prec']:>6.1%}  {r['exh']:>6.1%}  {r['f1']:>5.3f}  "
            f"{r['grupos']:>7}  {r['disp']:>4}  {r['score']:>7.1f}  "
            f"{r['estado']:>14}  {r['rcp']:>8}{marker}"
        )

    if best_confiable:
        resumen.append({
            'algoritmo': algo,
            'umbral':    best_confiable['umbral'],
            'prec':      best_confiable['prec'],
            'exh':       best_confiable['exh'],
            'f1':        best_confiable['f1'],
            'estado':    best_confiable['estado'],
            'tiempo_s':  elapsed,
        })
        print(f"\n  → Mejor confiable: umbral={best_confiable['umbral']}%  "
              f"F1={best_confiable['f1']:.3f}  tiempo={elapsed:.1f}s")
    else:
        resumen.append({
            'algoritmo': algo, 'umbral': '—', 'prec': 0, 'exh': 0,
            'f1': 0, 'estado': 'sin calibrar', 'tiempo_s': elapsed,
        })
        print(f"\n  → Sin umbral confiable en el rango probado  (tiempo={elapsed:.1f}s)")

# ── Tabla resumen ─────────────────────────────────────────────────────────────
print(f"\n\n{'═'*78}")
print("  TABLA RESUMEN — mejor umbral confiable por algoritmo")
print(f"{'═'*78}")
hdr = f"  {'Algoritmo':<20} {'Umbral':>7} {'Prec':>7} {'Exh':>7} {'F1':>6}  {'Estado':<14}  {'Tiempo':>7}"
print(hdr)
print("  " + "─" * 74)
for r in sorted(resumen, key=lambda x: -x['f1']):
    umbral_s = f"{r['umbral']}%" if isinstance(r['umbral'], int) else r['umbral']
    prec_s   = f"{r['prec']:.1%}" if r['prec'] else "—"
    exh_s    = f"{r['exh']:.1%}"  if r['exh']  else "—"
    f1_s     = f"{r['f1']:.3f}"   if r['f1']   else "0.000"
    print(
        f"  {r['algoritmo']:<20} {umbral_s:>7} {prec_s:>7} {exh_s:>7} {f1_s:>6}  "
        f"{r['estado']:<14}  {r['tiempo_s']:>6.1f}s"
    )
print(f"{'═'*78}")
