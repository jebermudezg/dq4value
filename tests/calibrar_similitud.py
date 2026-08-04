"""
Calibración de similitud por F1 con verdad terreno (RUC).

Uso: python3 tests/calibrar_similitud.py
"""
import sys
import pandas as pd
from collections import defaultdict
sys.path.insert(0, '.')
from engine.dimensions.similitud import check_similitud

df = pd.read_csv('tests/maestro_proveedores_1000.csv')

# ── Verdad terreno: pares que comparten RUC ──────────────────────────────────
ruc_to_ids = defaultdict(list)
for _, row in df.iterrows():
    ruc_to_ids[row['ruc']].append(int(row['proveedor_id']))

verdad = set()
for ruc, ids in ruc_to_ids.items():
    if len(ids) > 1:
        ids_s = sorted(ids)
        for i, a in enumerate(ids_s):
            for b in ids_s[i + 1:]:
                verdad.add((a, b))

print(f"Pares verdaderos (mismo RUC): {len(verdad)}")
print(f"Grupos verdaderos:            {sum(1 for ids in ruc_to_ids.values() if len(ids) > 1)}")
print()

header = (
    f"{'Umbral':>7} {'Prec':>7} {'Exh':>7} {'F1':>6}  "
    f"{'Grupos':>7} {'Disp':>5} {'Score':>7} {'Estado':>14} "
    f"{'Regs/par':>9}"
)
print(header)
print("-" * len(header))

for umbral in [70, 74, 78, 82, 86, 90, 94]:
    score, issues, meta = check_similitud(
        df, 'proveedor_id', 'razon_social',
        algoritmo='monge_elkan', umbral=umbral, normalizar=True
    )

    # Pares detectados desde los grupos confiables
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

    rcp = meta.get('registros_con_algun_par', 0)
    print(
        f"{umbral:>6}%  {prec:>6.1%}  {exh:>6.1%}  {f1:>5.3f}  "
        f"{meta.get('total_grupos', 0):>7}  "
        f"{meta.get('grupos_dispersos_excluidos', 0):>4}  "
        f"{score:>7.1f}  "
        f"{meta.get('estado_confiabilidad', '—'):>14}  "
        f"{rcp:>8}"
    )
