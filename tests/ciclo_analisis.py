"""
ciclo_analisis.py — Análisis base para la prueba del ciclo de remediación.

Corre el análisis sobre maestro_clientes_500.xlsx via TestClient y guarda:
  - tests/ciclo_base.json con todos los resultados
  - Ruta del Excel de reporte generado

Uso:
    python3 tests/ciclo_analisis.py [--archivo tests/maestro_clientes_500.xlsx] [--output tests/ciclo_base.json]
"""
import sys, io, json, argparse, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from starlette.testclient import TestClient
from database.db import init_db
from api.main import app

# ─── Config por defecto ──────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).parent.parent
TESTS_DIR = Path(__file__).parent

parser = argparse.ArgumentParser()
parser.add_argument('--archivo', default=str(TESTS_DIR / 'maestro_clientes_500.xlsx'))
parser.add_argument('--output',  default=str(TESTS_DIR / 'ciclo_base.json'))
parser.add_argument('--algoritmo', default=None,  help='Algoritmo para similitud (auto-detectado si omitido)')
parser.add_argument('--umbral',    default=None,  type=int)
args = parser.parse_args()

ARCHIVO  = Path(args.archivo)
OUTPUT   = Path(args.output)
ADMIN_EMAIL = "admin@dqplatform.com"
ADMIN_PASS  = "Admin123!"

# Configuración exacta pedida por el usuario
COLUMNS_CONFIG = {
    "razon_social": {
        "completitud": {},
        "similitud": {
            "algoritmo": "qgrams",
            "umbral":    86,
            "normalizar": True,
        },
    },
    "cliente_id": {
        "completitud": {},
        "unicidad": {},
    },
    "numero_documento": {
        "completitud": {},
        "unicidad": {},
        "precision": {"min_length": 8, "max_length": 11},
    },
    "nombre_contacto": {
        "completitud": {},
    },
    "distrito": {
        "completitud": {},
    },
    "email": {
        "completitud": {},
        "validez": {
            # ñ/Ñ permitidos (dominios peruanos); vocales acentuadas rechazadas
            "regex_pattern": r"^[a-zA-Z0-9._+\-ñÑ]+@[a-zA-Z0-9\-ñÑ]+(\.[a-zA-Z0-9\-ñÑ]+)+$",
            "formato_tipo": "email",
        },
    },
    "telefono": {
        "completitud": {},
        "consistencia": {},
    },
    "departamento": {
        "completitud": {},
        "validez": {
            "valid_values": [
                "Lima", "Arequipa", "La Libertad", "Piura", "Cusco",
                "Lambayeque", "Junín", "Ancash", "Ica", "Tacna"
            ]
        },
    },
    "segmento": {
        "validez": {
            "valid_values": ["Corporativo", "Mediana empresa", "Pequeña empresa", "Persona natural"]
        },
    },
    "estado": {
        "validez": {
            "valid_values": ["Activo", "Inactivo", "Suspendido"]
        },
    },
    "fecha_alta": {
        "completitud": {},
        "consistencia": {},
        "vigencia": {"date_from": "2015-01-01", "date_to": "2026-08-17"},
    },
    "fecha_ultima_compra": {
        "completitud": {},
        "vigencia": {"date_from": "2019-01-01", "date_to": "2026-08-17"},
    },
    "linea_credito_pen": {
        "completitud": {},
        "exactitud": {"min_value": 0, "max_value": 2000000},
        "razonabilidad": {"metodo": "iqr"},
    },
}

ANALYZE_REQUEST = {
    "file_id":           None,   # se llena después
    "id_column":         "cliente_id",
    "columns_config":    COLUMNS_CONFIG,
    "naturaleza_dato":   "maestro",
    "proposito_analisis":"depuracion_duplicados",
    "descripcion":       "Ciclo remediación — análisis base",
    "pesos_modo":        "proposito",
}

# ─── Main ────────────────────────────────────────────────────────────────────
print("Inicializando DB y TestClient...")
init_db()
client = TestClient(app, raise_server_exceptions=True)

# Login
resp = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
assert resp.status_code == 200, f"Login falló: {resp.text}"
token = resp.json()["token"]
headers = {"authorization": f"Bearer {token}"}
print(f"✅ Login OK")

# Upload
if not ARCHIVO.exists():
    print(f"❌ Archivo no encontrado: {ARCHIVO}")
    sys.exit(1)

with open(ARCHIVO, "rb") as f:
    resp = client.post(
        "/upload",
        files={"file": (ARCHIVO.name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
assert resp.status_code == 200, f"Upload falló: {resp.text}"
_updata = resp.json()
file_id = _updata["file_id"]
cols    = _updata.get("columnas", [])   # API returns "columnas" not "columns"
total   = _updata.get("total_registros", "?")
print(f"✅ Upload OK — file_id={file_id}, {total} registros, {len(cols)} columnas")

# Si el usuario pasó algoritmo/umbral, sustituir en la config
if args.algoritmo:
    COLUMNS_CONFIG["razon_social"]["similitud"]["algoritmo"] = args.algoritmo
if args.umbral:
    COLUMNS_CONFIG["razon_social"]["similitud"]["umbral"] = args.umbral

# Analyze
ANALYZE_REQUEST["file_id"] = file_id
print(f"\nIniciando análisis ({len(COLUMNS_CONFIG)} columnas, {sum(len(v) for v in COLUMNS_CONFIG.values())} dimensiones)...")
t0 = time.perf_counter()

resp = client.post("/analyze", json=ANALYZE_REQUEST, headers=headers, timeout=300)
if resp.status_code != 200:
    print(f"❌ Analyze falló {resp.status_code}: {resp.text[:500]}")
    sys.exit(1)

elapsed = time.perf_counter() - t0
data = resp.json()
print(f"✅ Análisis completado en {elapsed:.1f}s")

# ─── Extraer resultados clave ─────────────────────────────────────────────────
# scores_por_columna: {col: {dim: score_float}}
# metadata_dimensiones: {"col|dim": metadata_dict}
score_general  = data.get("score_general", "?")
promedio_simple= data.get("score_promedio_simple", "?")
nivel_umbral   = data.get("nivel_umbral", "?")
scores_col     = data.get("scores_por_columna", {})
meta_dims      = data.get("metadata_dimensiones", {})
total_reg      = data.get("total_registros", "?")
total_prob     = data.get("total_problemas", "?")
ruta_reporte   = data.get("ruta_reporte", "")
ruta_dashboard = data.get("ruta_dashboard", "")
pct_limpios    = data.get("pct_limpios", "?")
peor_dim       = data.get("peor_dimension", "?")
veredicto      = data.get("veredicto", "?")
aprovechables  = data.get("registros_aprovechables", "?")
sin_problema   = round(pct_limpios * total_reg / 100) if isinstance(pct_limpios, (int,float)) and isinstance(total_reg, int) else "?"

# Metadata de similitud (clave "razon_social|similitud")
sim_meta = meta_dims.get("razon_social|similitud", {})

# ─── Imprimir resumen ─────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  ANÁLISIS BASE — {ARCHIVO.name}")
print(f"{'='*60}")
print(f"  Score general       : {score_general}")
print(f"  Promedio simple     : {promedio_simple}")
print(f"  Registros           : {total_reg}")
print(f"  Aprovechables       : {aprovechables}")
print(f"  Sin ningún problema : {sin_problema}")
print(f"  Veredicto           : {veredicto}")
print(f"  Peor dimensión      : {peor_dim}")
print(f"  Nivel umbral        : {nivel_umbral}")
print(f"  Total problemas     : {total_prob}")
print(f"\n  Scores por columna y dimensión:")
for col_name, col_data in sorted(scores_col.items()):
    col_scores = [f"{d}={v}" for d, v in col_data.items()]
    print(f"    {col_name:<25}: {', '.join(col_scores)}")

if sim_meta:
    print(f"\n  Metadata similitud:")
    print(f"    algoritmo          : {sim_meta.get('algoritmo')}")
    print(f"    umbral             : {sim_meta.get('umbral')}")
    print(f"    total_grupos       : {sim_meta.get('total_grupos')}")
    print(f"    total_involucrados : {sim_meta.get('total_involucrados')}")
    print(f"    tope_activado      : {sim_meta.get('tope_activado')}")
    print(f"    contencion_marginal: {sim_meta.get('contencion_marginal')}")
    print(f"    analisis_parcial   : {sim_meta.get('analisis_parcial_significativo')}")
    print(f"    estado_confiabilidad: {sim_meta.get('estado_confiabilidad')}")

# ─── Obtener ruta del reporte desde la DB ─────────────────────────────────────
from database.db import get_connection as _gc
_conn = _gc()
_row  = _conn.execute(
    "SELECT ruta_reporte, ruta_dashboard FROM analisis WHERE file_id=? ORDER BY id DESC LIMIT 1",
    (file_id,)
).fetchone()
_conn.close()
if _row:
    ruta_reporte   = _row["ruta_reporte"]   or ""
    ruta_dashboard = _row["ruta_dashboard"] or ""
else:
    ruta_reporte = ruta_dashboard = ""

print(f"\n  Reporte Excel       : {ruta_reporte}")
print(f"  Dashboard           : {ruta_dashboard}")

# ─── Guardar JSON ─────────────────────────────────────────────────────────────
output_data = {
    "archivo_analizado":    str(ARCHIVO.name),
    "score_general":        score_general,
    "promedio_simple":      promedio_simple,
    "registros_aprovechables": aprovechables,
    "registros_sin_ningun_problema": sin_problema,
    "veredicto":            veredicto,
    "peor_dimension":       peor_dim,
    "nivel_umbral":         nivel_umbral,
    "total_registros":      total_reg,
    "total_problemas":      total_prob,
    "ruta_reporte":         ruta_reporte,
    "ruta_dashboard":       ruta_dashboard,
    "scores_por_columna":   scores_col,  # {col: {dim: score_float}}
    "metadata_similitud":   sim_meta,
    "tiempo_analisis_s":    round(elapsed, 1),
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n✅ Resultados guardados en: {OUTPUT}")
print(f"\n   RUTA_REPORTE_EXCEL={ruta_reporte}")
