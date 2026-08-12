"""
tests/prueba_integral_v3.py
Fases 4, 5 y 6 de la prueba integral v3.
"""
import sys, time
sys.path.insert(0, '.')

import pandas as pd
from engine.scorer import DQScorer
from engine.pesos import obtener_pesos, pesos_iguales
from engine.profiler import profile_dataset
from database.db import get_connection

# ──────────────────────────────────────────────────────────────────────────────
# Cargar los tres datasets
# ──────────────────────────────────────────────────────────────────────────────
df_a = pd.read_csv('tests/prueba_tipograficos_800.csv')
df_b = pd.read_csv('tests/prueba_tokens_600.csv')
df_c = pd.read_csv('tests/prueba_limpio_500.csv')

CARGOS_VAL    = ['Analista','Coordinador','Jefe de área','Supervisor','Asistente',
                 'Gerente','Técnico','Especialista','Director','Auditor']
AREAS_VAL     = ['Finanzas','Recursos Humanos','Operaciones','Ventas','Logística',
                 'Tecnología','Legal','Contabilidad']
NIVEL_VAL     = ['Secundaria','Técnico','Bachiller','Titulado','Maestría']
ESTADOS_A_VAL = ['Activo','Inactivo','Licencia','Retirado']

USOS_B_VAL     = ['Residencial','Comercial','Industrial','Mixto','Institucional']
ESTADOS_B_VAL  = ['Activo','Inactivo','En litigio']

CATEGORIAS_C_VAL = ['Electrónica','Ropa','Alimentos','Hogar','Deporte',
                    'Libros','Juguetes','Herramientas','Farmacia','Automotriz']
CANALES_C_VAL = ['Web','App móvil','Tienda física','Teléfono','Email']
REGIONES_C_VAL = ['Lima','Arequipa','Trujillo','Piura','Cusco']

CONFIG_A = {
    'nombre_completo': {
        'completitud': {},
        'similitud': {'algoritmo': 'brecha_afin', 'umbral': 86, 'normalizar': False},
        'precision': {'min_length': 5, 'max_length': 80},
    },
    'dni': {
        'completitud': {},
        'unicidad': {},
        'validez': {'regex_pattern': r'^\d{8}$'},
    },
    'cargo': {
        'completitud': {},
        'integridad_referencial': {'valores_referencia': CARGOS_VAL},
    },
    'area': {
        'completitud': {},
        'validez': {'valid_values': AREAS_VAL},
    },
    'salario_pen': {
        'completitud': {},
        'exactitud': {'min_value': 0, 'max_value': 100_000},
        'razonabilidad': {'metodo': 'iqr'},
    },
    'fecha_ingreso': {
        'completitud': {},
        'consistencia': {},
        'vigencia': {'date_from': '2000-01-01', 'date_to': '2026-12-31'},
    },
    'estado_laboral': {
        'completitud': {},
        'validez': {'valid_values': ESTADOS_A_VAL},
    },
}

CONFIG_B = {
    'direccion': {
        'completitud': {},
        'similitud': {'algoritmo': 'brecha_afin', 'umbral': 92, 'normalizar': True},
        'precision': {'min_length': 5, 'max_length': 150},
    },
    'area_m2': {
        'completitud': {},
        'exactitud': {'min_value': 0, 'max_value': 50_000},
        'razonabilidad': {'metodo': 'iqr'},
    },
    'fecha_registro': {
        'completitud': {},
        'consistencia': {},
        'vigencia': {'date_from': '2005-01-01', 'date_to': '2026-12-31'},
    },
    'valor_tasacion_pen': {
        'completitud': {},
        'exactitud': {'min_value': 0, 'max_value': 5_000_000},
        'razonabilidad': {'metodo': 'iqr'},
    },
    'uso': {
        'completitud': {},
        'validez': {'valid_values': USOS_B_VAL},
    },
    'estado_predio': {
        'completitud': {},
        'validez': {'valid_values': ESTADOS_B_VAL},
    },
}

CONFIG_C = {
    'nombre_producto': {
        'completitud': {},
        'similitud': {'algoritmo': 'brecha_afin', 'umbral': 94, 'normalizar': False},
        'precision': {'min_length': 3, 'max_length': 100},
    },
    'precio_pen': {
        'completitud': {},
        'exactitud': {'min_value': 0, 'max_value': 20_000},
        'razonabilidad': {'metodo': 'iqr'},
    },
    'descuento_pct': {
        'completitud': {},
        'exactitud': {'min_value': 0, 'max_value': 100},
    },
    'categoria': {
        'completitud': {},
        'integridad_referencial': {'valores_referencia': CATEGORIAS_C_VAL},
    },
    'fecha_compra': {
        'completitud': {},
        'vigencia': {'date_from': '2020-01-01', 'date_to': '2026-12-31'},
    },
}

DATASETS = [
    ('Dataset A — Tipográficos', df_a, 'empleado_id', CONFIG_A),
    ('Dataset B — Tokens', df_b, 'predio_id', CONFIG_B),
    ('Dataset C — Limpio', df_c, 'producto_id', CONFIG_C),
]

# ──────────────────────────────────────────────────────────────────────────────
# FASE 4 — Las 11 dimensiones sobre cada dataset
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("FASE 4 — LAS 11 DIMENSIONES SOBRE CADA DATASET")
print("="*70)

resultados_f4 = {}
for label, df, id_col, config in DATASETS:
    print(f"\n{'─'*60}")
    print(f"  {label}  ({len(df)} filas × {len(df.columns)} cols)")
    print(f"{'─'*60}")

    t0 = time.time()
    scorer = DQScorer(df, id_col)
    for col, dims in config.items():
        if col in df.columns:
            scorer.configure(col, dims)
    res = scorer.run_analysis()
    elapsed = time.time() - t0

    dims_exec = set()
    for cs in res['scores_por_columna'].values():
        for d in cs: dims_exec.add(d)

    print(f"  Tiempo:                {elapsed:.1f}s")
    print(f"  Dims ejecutadas ({len(dims_exec)}): {sorted(dims_exec)}")
    print(f"  score_general:         {res['score_general']}")
    print(f"  score_promedio_simple: {res['score_promedio_simple']}")
    print(f"  registros_aprovechables: {res['registros_aprovechables']} / {len(df)} ({res['pct_aprovechables']}%)")
    print(f"  veredicto:             {res['veredicto']}")
    print(f"  nivel_umbral:          {res['nivel_umbral']}")
    print(f"  peor_dim_critica:      {res['peor_dimension_critica']} (score {res['peor_dimension_critica_score']})")
    print(f"  total_problemas:       {res['total_problemas']}")

    issues = res['issues_df']
    print(f"\n  Problemas por dimensión:")
    for d in sorted(issues['dimension'].unique()):
        n = issues[issues['dimension'] == d][id_col].nunique()
        print(f"    {d:30s}: {n:4d} ({n/len(df)*100:.1f}%)")

    # Invariantes
    errs = []
    def inv(label, ok, detail=""):
        if not ok: errs.append(label)
    inv("aprovechables ≥ 0",         res['registros_aprovechables'] >= 0)
    inv("aprovechables ≤ N",          res['registros_aprovechables'] <= len(df))
    inv("score_general ∈ [0,100]",    0 <= res['score_general'] <= 100)
    inv("id_col dtype preservada",    str(issues[id_col].dtype) != 'object' if not issues.empty else True)
    ids_out = set(issues[id_col]) - set(df[id_col]) if not issues.empty else set()
    inv("IDs en issues ⊆ dataset",    len(ids_out) == 0)
    meta_s = {k:v for k,v in res['metadata_dimensiones'].items() if 'similitud' in str(k) and v}
    for k, v in meta_s.items():
        ti = v.get('total_involucrados',0)
        tg = v.get('total_grupos',0)
        tx = v.get('total_excedentes',0)
        inv("involucrados=grupos+excedentes", ti == tg + tx, f"{ti}=={tg}+{tx}")
    if errs:
        print(f"\n  ⚠  INVARIANTES FALLIDAS: {errs}")
    else:
        print(f"\n  ✅ Todas las invariantes cumplen")

    resultados_f4[label] = {
        'elapsed': elapsed, 'dims': len(dims_exec),
        'score': res['score_general'], 'aprovechables_pct': res['pct_aprovechables'],
        'veredicto': res['veredicto'], 'peor_dim': res['peor_dimension_critica'],
        'tiempo': elapsed, 'res': res,
    }

# Tabla resumen
print("\n" + "="*70)
print("TABLA RESUMEN FASE 4")
print("="*70)
print(f"  {'Dataset':<30s} {'Dims':>5s} {'Score':>7s} {'Aprove%':>8s} {'Veredicto':>12s} {'Peor dim':>22s} {'Tiempo':>7s}")
print(f"  {'-'*96}")
for label, d in resultados_f4.items():
    print(f"  {label:<30s} {d['dims']:>5d} {d['score']:>7.1f} {d['aprovechables_pct']:>7.1f}% {d['veredicto']:>12s} {str(d['peor_dim']):>22s} {d['elapsed']:>6.1f}s")

# ── Dataset C detalle ─────────────────────────────────────────────────────────
print("\n" + "="*70)
print("DATASET C — VERIFICACIÓN CRÍTICA (datos casi limpios)")
print("="*70)
res_c = resultados_f4['Dataset C — Limpio']['res']
print(f"  score_general:          {res_c['score_general']}")
print(f"  pct_aprovechables:      {res_c['pct_aprovechables']}%")
print(f"  veredicto:              {res_c['veredicto']}")
if res_c['pct_aprovechables'] >= 95:
    print(f"  ✅ aprovechables ≥ 95% — el motor NO inventa problemas donde no los hay")
else:
    print(f"  ⚠  aprovechables < 95% — revisar over-reporting (esperado ≥ 95%)")

if res_c['veredicto'] == 'listo':
    print(f"  ✅ veredicto = 'listo' — sistema reconoce datos buenos como buenos")
else:
    print(f"  ⚠  veredicto = '{res_c['veredicto']}' — se esperaba 'listo'")

# ──────────────────────────────────────────────────────────────────────────────
# FASE 5 — Tres modos de ponderación sobre Dataset A
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("FASE 5 — TRES MODOS DE PONDERACIÓN (Dataset A)")
print("="*70)

conn = get_connection(); conn.execute("DELETE FROM pesos_config"); conn.commit(); conn.close()

def analizar_con_niveles(df, id_col, config, niveles_dict):
    s = DQScorer(df, id_col)
    for col, dims in config.items():
        if col in df.columns:
            s.configure(col, dims)
    return s.run_analysis(niveles=niveles_dict)

n_ig   = pesos_iguales()
n_prop = obtener_pesos('depuracion_duplicados')
n_man  = dict(n_ig); n_man['similitud'] = 'critica'; n_man['unicidad'] = 'critica'

r1 = analizar_con_niveles(df_a, 'empleado_id', CONFIG_A, n_ig)
r2 = analizar_con_niveles(df_a, 'empleado_id', CONFIG_A, n_prop)
r3 = analizar_con_niveles(df_a, 'empleado_id', CONFIG_A, n_man)

# Propósito "iniciativa_ia"
n_ia = obtener_pesos('iniciativa_ia')
r4 = analizar_con_niveles(df_a, 'empleado_id', CONFIG_A, n_ia)

print(f"  {'Modo':<45s} {'Score':>7s} {'Aprov%':>7s} {'Nivel umbral':>13s}")
print(f"  {'-'*77}")
for label, r in [
    ("1. Pesos iguales",          r1),
    ("2. depuracion_duplicados",  r2),
    ("3. Manual (sim+uni=critica)",r3),
    ("4. iniciativa_ia",           r4),
]:
    print(f"  {label:<45s} {r['score_general']:>7.2f} {r['pct_aprovechables']:>6.1f}% {r['nivel_umbral']:>13s}")

print(f"\n  Modo 2 ≠ Modo 1: {'✅' if abs(r1['score_general']-r2['score_general'])>0.01 else '⚠'}"
      f"  Δ={abs(r1['score_general']-r2['score_general']):.2f}")
print(f"  Modo 3 ≠ Modo 1: {'✅' if abs(r1['score_general']-r3['score_general'])>0.01 else '⚠'}"
      f"  Δ={abs(r1['score_general']-r3['score_general']):.2f}")
print(f"  Modo 4 ≠ Modo 1: {'✅' if abs(r1['score_general']-r4['score_general'])>0.01 else '⚠'}"
      f"  Δ={abs(r1['score_general']-r4['score_general']):.2f}")

# ──────────────────────────────────────────────────────────────────────────────
# FASE 6 — Rendimiento
# ──────────────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("FASE 6 — RENDIMIENTO")
print("="*70)

perf_rows = []

for label, df, id_col in [
    ('Dataset A (800 filas)', df_a, 'empleado_id'),
    ('Dataset B (600 filas)', df_b, 'predio_id'),
    ('Dataset C (500 filas)', df_c, 'producto_id'),
]:
    t = time.time(); profile_dataset(df); tp = time.time()-t
    perf_rows.append((f"Perfil {label}", tp))
    print(f"  Perfil {label}: {tp:.2f}s")

# Análisis 11 dims
for label, elapsed in [(k, v['elapsed']) for k,v in resultados_f4.items()]:
    perf_rows.append((f"11 dims {label}", elapsed))
    print(f"  11 dims {label}: {elapsed:.1f}s")

# Similitud sola — dataset A, brecha_afin vs qgrams
from engine.dimensions.similitud import check_similitud

t = time.time()
check_similitud(df_a, 'empleado_id', 'nombre_completo', algoritmo='brecha_afin', umbral=86, normalizar=False)
t_ba = time.time()-t
print(f"  Similitud brecha_afin/86%/Dataset A: {t_ba:.2f}s")

t = time.time()
check_similitud(df_a, 'empleado_id', 'nombre_completo', algoritmo='qgrams', umbral=86, normalizar=True)
t_qg = time.time()-t
print(f"  Similitud qgrams/86%/Dataset A:      {t_qg:.2f}s")

# Isolation Forest con 3 columnas sobre Dataset A
from engine.dimensions.razonabilidad import check_razonabilidad
t = time.time()
check_razonabilidad(df_a, 'empleado_id', 'salario_pen',
                    metodo='isolation_forest',
                    columnas_if=['salario_pen'],
                    contamination=0.05)
t_if = time.time()-t
print(f"  Razonabilidad IF/Dataset A:           {t_if:.2f}s")

print(f"\n  {'Escenario':<45s} {'Tiempo':>8s}")
print(f"  {'-'*55}")
for label, t in perf_rows:
    print(f"  {label:<45s} {t:>7.2f}s")
print(f"  {'Similitud brecha_afin 86% Dataset A':<45s} {t_ba:>7.2f}s")
print(f"  {'Similitud qgrams 86% Dataset A':<45s} {t_qg:>7.2f}s")
print(f"  {'Isolation Forest Dataset A':<45s} {t_if:>7.2f}s")

print("\n✅ Fases 4, 5 y 6 completadas.")
