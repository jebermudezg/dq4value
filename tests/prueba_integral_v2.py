"""
tests/prueba_integral_v2.py
Prueba integral post-rediseño — Fases 3, 4, 5 y 7.

Dataset sintético: 1 000 filas con fechas en formato consistente (YYYY-MM-DD) y
50 valores únicos de razón social para evitar saturación artificial por consistencia
y similitud.  Los únicos problemas inyectados son deliberados y acotados.
"""
import sys, time, json, random
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
from engine.scorer import DQScorer
from engine.pesos import obtener_pesos, pesos_iguales
from engine.parsers import parse_file

random.seed(42)
np.random.seed(42)

# ──────────────────────────────────────────────────────────────────────────────
# Dataset sintético — 1 000 filas
# ──────────────────────────────────────────────────────────────────────────────
N = 1000

# 50 razones sociales únicas → similitud no formará grupos dispersos gigantes
RAZONES = [
    f"Empresa {chr(65+i//26)}{chr(65+i%26)} S.A.C." for i in range(26)
] + [
    f"Servicios {chr(65+i)} del Perú S.R.L." for i in range(24)
]  # 50 valores únicos

DEPARTAMENTOS = ['Lima','Arequipa','Trujillo','Chiclayo','Piura',
                 'Cusco','Iquitos','Huancayo','Tacna','Puno']
CATEGORIAS    = ['Alimentos','Bebidas','Limpieza','Tecnología','Logística',
                 'Construcción','Textil','Farmacia','Papelería','Seguridad']

rows = []
for i in range(1, N + 1):
    razon = random.choice(RAZONES)
    # ~3% nulos en razon_social
    if i % 33 == 0:
        razon = None

    ruc = f"20{random.randint(100000000, 999999999)}"
    # ~5% RUC duplicado (introduce unicidad issues)
    if i % 20 == 0 and i > 1:
        ruc = rows[-1]['ruc']
    # ~2% RUC inválido
    if i % 50 == 0:
        ruc = "9" + ruc[1:]

    depto = random.choice(DEPARTAMENTOS)
    # ~5% valor inválido en departamento
    if i % 20 == 0:
        depto = "Atlantida"
    # ~3% nulo
    if i % 35 == 0:
        depto = None

    cat = random.choice(CATEGORIAS)
    # ~5% fuera de referencia
    if i % 20 == 0:
        cat = "Desconocida"
    if i % 40 == 0:
        cat = None

    # ── Fechas en formato CONSISTENTE (YYYY-MM-DD) — sin mezcla ──────────────
    year = random.randint(2015, 2025)
    mon  = random.randint(1, 12)
    day  = random.randint(1, 28)
    fecha_reg = f"{year}-{mon:02d}-{day:02d}"
    if i % 60 == 0:
        fecha_reg = None

    dias_atras = random.randint(0, 1000)
    fecha_ult  = (pd.Timestamp("2026-08-12") - pd.Timedelta(days=dias_atras)).strftime("%Y-%m-%d")
    if i % 70 == 0:
        fecha_ult = None

    monto = round(random.uniform(100, 500_000), 2)
    if i % 50 == 0:
        monto = -100.0       # ~2% fuera de rango
    if i % 70 == 0:
        monto = None

    score = round(random.uniform(0, 100), 1)
    if i % 50 == 0:
        score = 150.0        # ~2% fuera de rango
    if i % 80 == 0:
        score = None

    rows.append({
        'proveedor_id':            i,
        'razon_social':            razon,
        'ruc':                     ruc,
        'departamento':            depto,
        'categoria_producto':      cat,
        'fecha_registro':          fecha_reg,
        'fecha_ultimo_pedido':     fecha_ult,
        'monto_ultimo_pedido_pen': monto,
        'score_calificacion':      score,
        'num_ordenes_historico':   random.randint(1, 200),
    })

df = pd.DataFrame(rows)

# ──────────────────────────────────────────────────────────────────────────────
# Configuración: las 11 dimensiones distribuidas en 8 columnas
# ──────────────────────────────────────────────────────────────────────────────
CONFIG = {
    'razon_social': {
        'completitud': {},
        'similitud': {'algoritmo': 'qgrams', 'umbral': 86, 'normalizar': True},
        'precision': {'min_length': 5, 'max_length': 100},
    },
    'ruc': {
        'completitud': {},
        'unicidad': {},
        'validez': {'regex_pattern': r'^(10|20)\d{9}$'},
    },
    'departamento': {
        'completitud': {},
        'validez': {'valid_values': DEPARTAMENTOS},
        'consistencia': {},
    },
    'categoria_producto': {
        'completitud': {},
        'integridad_referencial': {'valores_referencia': CATEGORIAS},
    },
    'fecha_registro': {
        'completitud': {},
        'vigencia': {'date_from': '2010-01-01', 'date_to': '2026-12-31'},
    },
    'fecha_ultimo_pedido': {
        'completitud': {},
        'oportunidad': {'max_age_days': 730},
    },
    'monto_ultimo_pedido_pen': {
        'completitud': {},
        'exactitud': {'min_value': 0, 'max_value': 1_000_000},
        'razonabilidad': {'metodo': 'iqr'},
    },
    'score_calificacion': {
        'completitud': {},
        'exactitud': {'min_value': 0, 'max_value': 100},
        'razonabilidad': {
            'metodo': 'isolation_forest',
            'columnas_if': ['score_calificacion', 'monto_ultimo_pedido_pen', 'num_ordenes_historico'],
            'contamination': 0.05,
        },
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# FASE 3 — Ejecutar las 11 dimensiones
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("FASE 3 — 11 DIMENSIONES EN UN SOLO ANÁLISIS")
print("="*60)
print(f"Dataset: {len(df)} filas, {len(df.columns)} columnas\n")

t0 = time.time()
scorer = DQScorer(df, 'proveedor_id')
for col, dims in CONFIG.items():
    if col in df.columns:
        scorer.configure(col, dims)
res = scorer.run_analysis()
t3 = time.time() - t0

dims_ejecutadas = set()
for col_scores in res.get('scores_por_columna', {}).values():
    for dim in col_scores.keys():
        dims_ejecutadas.add(dim)

ESPERADAS = {'completitud','unicidad','validez','consistencia','exactitud',
             'vigencia','precision','oportunidad','integridad_referencial',
             'razonabilidad','similitud'}

print(f"Tiempo total: {t3:.1f}s")
print(f"Dimensiones ejecutadas ({len(dims_ejecutadas)}): {sorted(dims_ejecutadas)}")
faltantes = ESPERADAS - dims_ejecutadas
if faltantes:
    print(f"\n⚠  FALTAN: {faltantes}")
else:
    print("\n✅  Las 11 dimensiones ejecutaron correctamente")

print("\nMétricas principales:")
for k in ['score_general','score_promedio_simple','registros_aprovechables',
          'pct_aprovechables','nivel_umbral','peor_dimension_critica',
          'total_problemas']:
    print(f"  {k:32s}: {res.get(k)}")

# Coherencia score vs aprovechables
sg   = res.get('score_general', 0)
apro = res.get('registros_aprovechables', 0)
pct  = res.get('pct_aprovechables', 0)
print(f"\n  Coherencia score ({sg:.1f}) vs aprovechables ({pct:.1f}%):")
if apro >= 0:
    print(f"  ✅ registros_aprovechables no es negativo ({apro})")
else:
    print(f"  ❌ registros_aprovechables negativo — revisar tipos de id_col")

print("\nProblemas por dimensión (IDs únicos / 1000):")
issues = res['issues_df']
ID_COL = 'proveedor_id'
for d in sorted(issues['dimension'].unique()):
    n = issues[issues['dimension'] == d][ID_COL].nunique()
    print(f"  {d:30s}: {n:4d} ({n/N*100:.1f}%)")

print(f"\nRegistros con ≥1 problema: {issues[ID_COL].nunique()} / {N}")
print(f"Registros sin ningún problema: {N - issues[ID_COL].nunique()} / {N}")

print("\nMetadata de similitud:")
for k, v in res.get('metadata_dimensiones', {}).items():
    if 'similitud' in str(k) and v:
        for mk, mv in v.items():
            print(f"  {mk}: {mv}")

# ──────────────────────────────────────────────────────────────────────────────
# FASE 4 — Invariantes
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("FASE 4 — INVARIANTES")
print("="*60)

errors = []

def inv(label, ok, detail=""):
    sym = "✅" if ok else "❌"
    print(f"  {sym} {label}{' — ' + detail if detail else ''}")
    if not ok:
        errors.append(label)

inv("pct_aprovechables ∈ [0, 100]",
    0 <= res.get('pct_aprovechables', -1) <= 100,
    f"{res.get('pct_aprovechables')}%")

inv("score_general ∈ [0, 100]",
    0 <= res.get('score_general', -1) <= 100,
    str(res.get('score_general')))

inv("score_promedio_simple ∈ [0, 100]",
    0 <= res.get('score_promedio_simple', -1) <= 100,
    str(res.get('score_promedio_simple')))

tr = res.get('total_registros', 0)
ra = res.get('registros_aprovechables', -1)
inv(f"registros_aprovechables ∈ [0, N]",
    0 <= ra <= tr,
    f"{ra}/{tr}")

pdc = res.get('peor_dimension_critica')
inv("peor_dimension_critica ∈ dims ejecutadas",
    pdc is None or pdc in dims_ejecutadas,
    repr(pdc))

for k, v in res.get('metadata_dimensiones', {}).items():
    if 'similitud' in str(k) and v:
        ti = v.get('total_involucrados', None)
        tg = v.get('total_grupos', 0)
        tx = v.get('total_excedentes', 0)
        if ti is not None:
            inv("total_involucrados = grupos + excedentes",
                ti == tg + tx, f"{ti}=={tg}+{tx}")
        tev = v.get('total_evaluados', None)
        ph  = v.get('placeholders_excluidos', 0)
        if tev is not None:
            inv("total_evaluados = N − placeholders",
                tev == tr - ph, f"{tev}=={tr}−{ph}")

# Tipo de id_col en issues_df
id_dtype = issues[ID_COL].dtype
inv("id_col dtype = int64 (sin mezcla de tipos)",
    str(id_dtype) == 'int64', str(id_dtype))

ids_problema = set(issues[ID_COL])
ids_dataset  = set(df[ID_COL])
inv("IDs en issues ⊆ IDs del dataset",
    len(ids_problema - ids_dataset) == 0,
    f"{len(ids_problema - ids_dataset)} IDs fuera del dataset")

if errors:
    print(f"\n⚠  {len(errors)} invariante(s) fallaron: {errors}")
else:
    print("\n✅  Todas las invariantes cumplen")

# ──────────────────────────────────────────────────────────────────────────────
# FASE 5 — Tres modos de ponderación
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("FASE 5 — TRES MODOS DE PONDERACIÓN")
print("="*60)

from database.db import get_connection

def run_with_niveles(niveles_dict):
    s = DQScorer(df, 'proveedor_id')
    for col, dims in CONFIG.items():
        if col in df.columns:
            s.configure(col, dims)
    return s.run_analysis(niveles=niveles_dict)

n_ig   = pesos_iguales()
conn = get_connection(); conn.execute("DELETE FROM pesos_config"); conn.commit(); conn.close()
n_prop = obtener_pesos('depuracion_duplicados')
n_man  = dict(n_ig); n_man['similitud'] = 'critica'

r1 = run_with_niveles(n_ig)
r2 = run_with_niveles(n_prop)
r3 = run_with_niveles(n_man)

print(f"  {'Modo':<40s} {'score_general':>14s}  {'pct_aprovechables':>18s}")
print(f"  {'-'*76}")
for label, r in [("1. Pesos iguales", r1),
                  ("2. Propósito depuracion_duplicados", r2),
                  ("3. Manual (similitud → critica)", r3)]:
    print(f"  {label:<40s} {r['score_general']:>14.2f}  {r['pct_aprovechables']:>17.1f}%")

print()
print(f"  Modo 2 ≠ Modo 1: {'✅' if abs(r1['score_general']-r2['score_general'])>0.01 else '⚠  iguales'}"
      f"  (Δ={abs(r1['score_general']-r2['score_general']):.2f})")
print(f"  Modo 3 ≠ Modo 1: {'✅' if abs(r1['score_general']-r3['score_general'])>0.01 else '⚠  iguales'}"
      f"  (Δ={abs(r1['score_general']-r3['score_general']):.2f})")
print(f"  Modo 3 ≠ Modo 2: {'✅' if abs(r2['score_general']-r3['score_general'])>0.01 else '⚠  iguales'}"
      f"  (Δ={abs(r2['score_general']-r3['score_general']):.2f})")

print("\n  Nota: score_general ≠ score_promedio_simple con pesos_iguales es ESPERADO")
print("  cuando una dimensión aparece en más de una columna. score_general promedia")
print("  los 11 promedios por dimensión; score_promedio_simple promedia los 26 scores")
print("  col×dim (completitud aparece 8 veces).")

# ──────────────────────────────────────────────────────────────────────────────
# FASE 7 — Rendimiento con columnas reales de dataset_10000.txt
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("FASE 7 — RENDIMIENTO")
print("="*60)

# 7a: perfil 1 000 filas
from engine.profiler import profile_dataset
df1k, _ = parse_file('tests/dataset_1000.csv')
t = time.time(); profile_dataset(df1k); t_perf = time.time() - t
print(f"  Perfil 1 000 filas:                    {t_perf:.2f}s")

# 7b: análisis 11 dims / 1 000 filas (ya medido en Fase 3)
print(f"  Análisis 11 dims / 1 000 filas:        {t3:.1f}s")

# 7c: similitud sola / 1 000 filas
t = time.time()
s_sim = DQScorer(df, 'proveedor_id')
s_sim.configure('razon_social', {'similitud': {'algoritmo': 'qgrams', 'umbral': 86, 'normalizar': True}})
s_sim.run_analysis()
t_sim = time.time() - t
print(f"  Similitud sola Q-grams 86% / 1 000:    {t_sim:.2f}s")

# 7d: razonabilidad IF sola / 1 000 filas
t = time.time()
s_if = DQScorer(df, 'proveedor_id')
s_if.configure('score_calificacion', {'razonabilidad': {
    'metodo': 'isolation_forest',
    'columnas_if': ['score_calificacion', 'monto_ultimo_pedido_pen', 'num_ordenes_historico'],
    'contamination': 0.05,
}})
s_if.run_analysis()
t_if = time.time() - t
print(f"  Razonabilidad IF sola 3 cols / 1 000:  {t_if:.2f}s")

# 7e: análisis 5 dims / 10 000 filas con columnas REALES
df10, _ = parse_file('tests/dataset_10000.txt')
print(f"\n  dataset_10000.txt: {len(df10)} filas × {len(df10.columns)} columnas")
print(f"  Columnas: {list(df10.columns)}")
t = time.time()
s10 = DQScorer(df10, 'cliente_id')
s10.configure('nombre',             {'completitud': {}, 'precision': {'min_length': 2, 'max_length': 80}})
s10.configure('email',              {'completitud': {}, 'validez': {'regex_pattern': r'^[^@]+@[^@]+\.[^@]+$'}, 'unicidad': {}})
s10.configure('salario',            {'exactitud': {'min_value': 0, 'max_value': 500_000}})
s10.configure('fecha_registro',     {'vigencia': {'date_from': '2015-01-01', 'date_to': '2026-12-31'}})
res10 = s10.run_analysis()
t_10k = time.time() - t

dims10 = set()
for cs in res10.get('scores_por_columna', {}).values():
    for d in cs: dims10.add(d)
print(f"  Dimensiones ejecutadas ({len(dims10)}): {sorted(dims10)}")
print(f"  Análisis 5 dims / 10 000 filas:        {t_10k:.2f}s")
print(f"  score_general: {res10['score_general']}, aprovechables: {res10['pct_aprovechables']}%")

# 7f: similitud sobre 10 000 filas (escenario más costoso)
t = time.time()
s10_sim = DQScorer(df10, 'cliente_id')
s10_sim.configure('nombre', {'similitud': {'algoritmo': 'qgrams', 'umbral': 86, 'normalizar': True}})
res10_sim = s10_sim.run_analysis()
t_10k_sim = time.time() - t
meta_sim = {}
for k, v in res10_sim.get('metadata_dimensiones', {}).items():
    if 'similitud' in str(k) and v:
        meta_sim = v
print(f"  Similitud Q-grams 86% / 10 000 filas:  {t_10k_sim:.1f}s")
print(f"    grupos={meta_sim.get('total_grupos',0)}, involucrados={meta_sim.get('total_involucrados',0)}, estado={meta_sim.get('estado_confiabilidad','?')}")

print()
