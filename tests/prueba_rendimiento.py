"""
Prueba de rendimiento de DQ4Value.
Mide tiempos de parse, profiling, sugerencias y análisis sobre datasets reales y sintéticos.
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ai.claude_analyzer import suggest_dimensions_rules
from engine.parsers import parse_file
from engine.profiler import profile_dataset
from engine.scorer import DQScorer

print("\n=== PRUEBA DE RENDIMIENTO ===\n")

# ── 1. Parse 1 000 registros ───────────────────────────────────────────────
t0 = time.time()
df, cols = parse_file("tests/dataset_1000.csv")
t_parse = (time.time() - t0) * 1000
status = "✅" if t_parse < 2000 else "⚠️"
print(f"{status} Parse 1 000 registros:           {t_parse:6.0f} ms")

# ── 2. Profiling 1 000 registros ──────────────────────────────────────────
t0 = time.time()
perfil = profile_dataset(df)
t_profile = (time.time() - t0) * 1000
status = "✅" if t_profile < 5000 else "⚠️"
print(f"{status} Profiling 1 000 registros:       {t_profile:6.0f} ms")

# ── 3. Sugerencias 15 columnas ────────────────────────────────────────────
t0 = time.time()
cols_meta = [
    {
        "nombre": c,
        "tipo": str(df[c].dtype),
        "total_registros": len(df),
        "valores_nulos": int(df[c].isnull().sum()),
    }
    for c in df.columns
]
sugs = suggest_dimensions_rules(
    cols_meta,
    profile={c: perfil["columnas"].get(c, {}) for c in df.columns},
)
t_sugs = (time.time() - t0) * 1000
status = "✅" if t_sugs < 500 else "⚠️"
print(f"{status} Sugerencias {len(df.columns)} columnas:          {t_sugs:6.0f} ms")

# ── 4. Análisis 5 columnas × 2 dimensiones (1 000 reg) ───────────────────
t0 = time.time()
scorer = DQScorer(df, "cliente_id")
for col in ["nombre", "email", "edad", "estado_cliente", "fecha_registro"]:
    if col in df.columns:
        scorer.configure(col, {"completitud": {}, "consistencia": {}})
results = scorer.run_analysis()
t_analisis = time.time() - t0
velocidad = 1000 / t_analisis
status = "✅" if t_analisis < 30 else "⚠️"
print(f"{status} Análisis 5 cols × 2 dims (1k):   {t_analisis*1000:6.0f} ms  "
      f"({velocidad:,.0f} reg/s)")

# ── 5. Dataset 10 000 registros sintético ─────────────────────────────────
np.random.seed(42)
df_grande = pd.DataFrame({
    "id":     range(10_000),
    "nombre": [f"Nombre {i}" for i in range(10_000)],
    "valor":  np.random.normal(100, 15, 10_000),
    "estado": np.random.choice(["Activo", "Inactivo", "activo"], 10_000),
})
t0 = time.time()
scorer2 = DQScorer(df_grande, "id")
scorer2.configure("nombre", {"completitud": {}, "consistencia": {}})
scorer2.configure("valor",  {"completitud": {}, "razonabilidad": {}})
scorer2.configure("estado", {"completitud": {}, "validez": {"valid_values": ["Activo", "Inactivo"]}})
r2 = scorer2.run_analysis()
t_grande = time.time() - t0
vel_grande = 10_000 / t_grande
status = "✅" if t_grande < 60 else "⚠️"
print(f"{status} Análisis 3 cols × 2 dims (10k):  {t_grande*1000:6.0f} ms  "
      f"({vel_grande:,.0f} reg/s)")

# ── 6. Profiling dataset 10 000 ───────────────────────────────────────────
t0 = time.time()
perfil2 = profile_dataset(df_grande)
t_prof2 = (time.time() - t0) * 1000
status = "✅" if t_prof2 < 15000 else "⚠️"
print(f"{status} Profiling 10 000 registros:      {t_prof2:6.0f} ms")

# ── Resumen ───────────────────────────────────────────────────────────────
print()
print("  Métricas de calidad del análisis (1k):")
print(f"    score_general  : {results['score_general']:.1f}")
print(f"    total_problemas: {results['total_problemas']}")
print(f"    columnas eval. : {len(results['scores_por_columna'])}")

print("\n✅ Prueba de rendimiento completada")
