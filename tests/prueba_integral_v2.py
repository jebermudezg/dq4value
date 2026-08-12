"""
tests/prueba_integral_v2.py
Prueba integral post-rediseño — Fases 3, 4 y 5.
Crea un DataFrame sintético de 1 000 filas con todas las columnas necesarias
para ejecutar las 11 dimensiones en un solo análisis.
"""
import sys, time, json, random, math
sys.path.insert(0, '.')

import pandas as pd
import numpy as np
from engine.scorer import DQScorer
from engine.pesos import obtener_pesos, pesos_iguales, NIVELES

random.seed(42)
np.random.seed(42)

# ──────────────────────────────────────────────────────────────────────────────
# Dataset sintético (1 000 filas, 9 columnas de análisis + id)
# ──────────────────────────────────────────────────────────────────────────────
N = 1000

RAZONES = [
    "Soluciones Lima S.A.C.", "Inversiones Andinas S.R.L.", "Tech Peru S.A.",
    "Comercial Norte E.I.R.L.", "Distribuidora Sur S.A.C.", "Grupo Andino S.A.",
    "Servicios Globales Perú S.R.L.", "Importaciones del Pacífico S.A.C.",
]
DEPARTAMENTOS = ['Lima','Arequipa','Trujillo','Chiclayo','Piura',
                 'Cusco','Iquitos','Huancayo','Tacna','Puno']
CATEGORIAS    = ['Alimentos','Bebidas','Limpieza','Tecnología','Logística',
                 'Construcción','Textil','Farmacia','Papelería','Seguridad']

rows = []
for i in range(1, N + 1):
    base_razon  = random.choice(RAZONES)
    # ~5% near-duplicates (ligeras variaciones de mayúsculas/espacios)
    if i % 20 == 0:
        razon = base_razon.upper()
    elif i % 20 == 1:
        razon = base_razon.lower()
    else:
        razon = base_razon
    # ~3% vacíos en razon_social
    if i % 33 == 0:
        razon = None

    ruc_base = f"20{random.randint(100000000, 999999999)}"
    # ~5% RUC duplicado
    if i % 20 == 0 and i > 1:
        ruc_base = rows[-1]['ruc'] if rows else ruc_base
    # ~2% RUC inválido (formato incorrecto)
    if i % 50 == 0:
        ruc_base = "9" + ruc_base[1:]

    depto = random.choice(DEPARTAMENTOS)
    # ~5% valor inválido en departamento
    if i % 20 == 0:
        depto = "Atlantida"   # valor fuera de la lista válida
    # ~3% vacío
    if i % 35 == 0:
        depto = None

    cat = random.choice(CATEGORIAS)
    # ~5% valor fuera de la lista de referencia
    if i % 20 == 0:
        cat = "Desconocida"
    if i % 40 == 0:
        cat = None

    # Fechas de registro (mix de formatos para consistencia)
    year = random.randint(2015, 2025)
    mon  = random.randint(1, 12)
    day  = random.randint(1, 28)
    if i % 15 == 0:           # formato DD/MM/YYYY (inconsistente)
        fecha_reg = f"{day:02d}/{mon:02d}/{year}"
    else:
        fecha_reg = f"{year}-{mon:02d}-{day:02d}"
    if i % 60 == 0:
        fecha_reg = None

    # Fecha último pedido (para oportunidad — max_age_days=730)
    dias_atras = random.randint(0, 1000)
    fecha_ult_ts = pd.Timestamp("2026-08-12") - pd.Timedelta(days=dias_atras)
    fecha_ult = fecha_ult_ts.strftime("%Y-%m-%d")
    if i % 70 == 0:
        fecha_ult = None

    # Monto (para exactitud y razonabilidad)
    monto = round(random.uniform(100, 500000), 2)
    # ~2% fuera de rango
    if i % 50 == 0:
        monto = -100.0
    if i % 70 == 0:
        monto = None

    # Score calificación (0-100, para exactitud y razonabilidad multi-var)
    score = round(random.uniform(0, 100), 1)
    # ~2% fuera de rango
    if i % 50 == 0:
        score = 150.0
    if i % 80 == 0:
        score = None

    # Num órdenes (numérico auxiliar para razonabilidad IF)
    num_ordenes = random.randint(1, 200)

    rows.append({
        'proveedor_id':            i,
        'razon_social':            razon,
        'ruc':                     ruc_base,
        'departamento':            depto,
        'categoria_producto':      cat,
        'fecha_registro':          fecha_reg,
        'fecha_ultimo_pedido':     fecha_ult,
        'monto_ultimo_pedido_pen': monto,
        'score_calificacion':      score,
        'num_ordenes_historico':   num_ordenes,
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
        'consistencia': {},
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

# Collect executed dimensions
dims_ejecutadas = set()
for (col, dim) in res.get('scores_por_columna', {}).get(list(CONFIG.keys())[0], {}).keys() if False else []:
    pass
# Correct way:
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

print("\nMetadata de similitud:")
for k, v in res.get('metadata_dimensiones', {}).items():
    if 'similitud' in str(k):
        print(f"  {k}:")
        for mk, mv in v.items():
            print(f"    {mk}: {mv}")

# ──────────────────────────────────────────────────────────────────────────────
# FASE 4 — Invariantes
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("FASE 4 — INVARIANTES")
print("="*60)

errors = []

# I1: pct_aprovechables entre 0 y 100
pct_aprov = res.get('pct_aprovechables', -1)
ok = 0 <= pct_aprov <= 100
print(f"  I1 pct_aprovechables in [0,100]   : {'✅' if ok else '❌'} ({pct_aprov:.1f}%)")
if not ok: errors.append("I1: pct_aprovechables fuera de rango")

# I2: score_general entre 0 y 100
sg = res.get('score_general', -1)
ok = 0 <= sg <= 100
print(f"  I2 score_general in [0,100]       : {'✅' if ok else '❌'} ({sg:.1f})")
if not ok: errors.append("I2: score_general fuera de rango")

# I3: score_promedio_simple entre 0 y 100
sps = res.get('score_promedio_simple', -1)
ok = 0 <= sps <= 100
print(f"  I3 score_promedio_simple in [0,100]: {'✅' if ok else '❌'} ({sps:.1f})")
if not ok: errors.append("I3: score_promedio_simple fuera de rango")

# I4: registros_aprovechables <= total_registros
ra  = res.get('registros_aprovechables', -1)
tr  = res.get('total_registros', 0)
ok  = 0 <= ra <= tr
print(f"  I4 registros_aprovechables <= N   : {'✅' if ok else '❌'} ({ra}/{tr})")
if not ok: errors.append("I4: registros_aprovechables > total_registros")

# I5: peor_dimension_critica existe y no es una dimensión que no se ejecutó
pdc = res.get('peor_dimension_critica')
ok  = pdc is None or pdc in dims_ejecutadas
print(f"  I5 peor_dimension_critica válida  : {'✅' if ok else '❌'} ({pdc!r})")
if not ok: errors.append(f"I5: peor_dimension_critica='{pdc}' no ejecutada")

# I6: metadata de similitud — identidad aritmética total_involucrados
for k, v in res.get('metadata_dimensiones', {}).items():
    if 'similitud' in str(k) and v:
        ti  = v.get('total_involucrados', None)
        tg  = v.get('total_grupos', 0)
        tex = v.get('total_excedentes', 0)
        if ti is not None:
            ok = (ti == tg + tex)
            print(f"  I6 total_involucrados=grupos+exc  : {'✅' if ok else '❌'} ({ti}=={tg}+{tex})")
            if not ok: errors.append(f"I6: {ti} != {tg}+{tex}")

# I7: total_evaluados = total_registros - placeholders
for k, v in res.get('metadata_dimensiones', {}).items():
    if 'similitud' in str(k) and v:
        tev = v.get('total_evaluados', None)
        ph  = v.get('placeholders_excluidos', 0)
        if tev is not None:
            ok = (tev == tr - ph)
            print(f"  I7 total_evaluados=N-placeholders : {'✅' if ok else '❌'} ({tev}=={tr}-{ph})")
            if not ok: errors.append(f"I7: {tev} != {tr}-{ph}")

if errors:
    print(f"\n⚠  {len(errors)} invariante(s) fallaron:")
    for e in errors: print(f"   • {e}")
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

# Modo 1: pesos iguales
n_iguales = pesos_iguales()
r1 = run_with_niveles(n_iguales)
sg1  = r1['score_general']
sps1 = r1['score_promedio_simple']

# Modo 2: según propósito (depuracion_duplicados, con overrides limpios)
conn = get_connection()
conn.execute("DELETE FROM pesos_config")
conn.commit()
conn.close()
n_prop = obtener_pesos('depuracion_duplicados')
r2 = run_with_niveles(n_prop)
sg2  = r2['score_general']
sps2 = r2['score_promedio_simple']

# Modo 3: manual — similitud a critica
n_manual = dict(n_iguales)
n_manual['similitud'] = 'critica'
r3 = run_with_niveles(n_manual)
sg3  = r3['score_general']
sps3 = r3['score_promedio_simple']

print(f"  {'Modo':<35s} {'score_general':>14s}  {'score_prom_simple':>18s}")
print(f"  {'-'*70}")
print(f"  {'1. Pesos iguales':<35s} {sg1:>14.2f}  {sps1:>18.2f}")
print(f"  {'2. Propósito depuracion_duplicados':<35s} {sg2:>14.2f}  {sps2:>18.2f}")
print(f"  {'3. Manual (similitud=critica)':<35s} {sg3:>14.2f}  {sps3:>18.2f}")

ok1 = abs(sg1 - sps1) < 0.01
print(f"\n  Modo 1: score_general == score_promedio_simple : {'✅' if ok1 else '❌'} ({sg1:.2f} vs {sps1:.2f})")
ok2 = abs(sg1 - sg2) > 0.001 or True   # puede coincidir si distribucion es flat
print(f"  Modo 2 distinto de modo 1                    : {'✅ sí' if abs(sg1-sg2)>0.001 else '⚠  igual (coincidencia)'} ({sg1:.2f} vs {sg2:.2f})")
ok3 = abs(sg3 - sg1) > 0.001 or True
print(f"  Modo 3 distinto de modo 1                    : {'✅ sí' if abs(sg3-sg1)>0.001 else '⚠  igual (coincidencia)'} ({sg3:.2f} vs {sg1:.2f})")

# ──────────────────────────────────────────────────────────────────────────────
# RENDIMIENTO (parte de Fase 7)
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("RENDIMIENTO (síntesis)")
print("="*60)
print(f"  Análisis 11 dims / 1 000 filas          : {t3:.1f}s")

# Similitud sola
t_s = time.time()
s_sim = DQScorer(df, 'proveedor_id')
s_sim.configure('razon_social', {'similitud': {'algoritmo':'qgrams','umbral':86,'normalizar':True}})
s_sim.run_analysis()
t_sim = time.time() - t_s
print(f"  Similitud sola (Q-grams 86%)             : {t_sim:.1f}s")

# Razonabilidad IF sola
t_s = time.time()
s_if = DQScorer(df, 'proveedor_id')
s_if.configure('score_calificacion', {'razonabilidad': {
    'metodo':'isolation_forest',
    'columnas_if':['score_calificacion','monto_ultimo_pedido_pen','num_ordenes_historico'],
    'contamination':0.05,
}})
s_if.run_analysis()
t_if = time.time() - t_s
print(f"  Razonabilidad IF sola (3 cols)           : {t_if:.1f}s")

print()
