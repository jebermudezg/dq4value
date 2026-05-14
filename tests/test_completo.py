import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from engine.scorer import DQScorer
from engine.report_gen import generate_excel_report

# ──────────────────────────────────────────────────────────────────────
# 1. Construcción del DataFrame de prueba
# ──────────────────────────────────────────────────────────────────────

nombres = [
    "Ana García", "Luis Pérez", "María López", "Carlos Ruiz", "Sofía Martínez",
    "Jorge Hernández", "Valentina Torres", "Andrés Flores", "Camila Díaz", "Ricardo Morales",
    "Isabella Castro", "Fernando Jiménez", "Lucía Romero", "Sebastián Vargas", "Paula Gómez",
    "Mateo Navarro", "Daniela Ramos", "Diego Ortega", "Natalia Soto", "Alejandro Medina",
    "Gabriela Reyes", "Nicolás Cruz", "Verónica Herrera", "Emilio Mendoza", "Laura Aguilar",
    None, None, None, None, "Roberto Vega",  # 4 nulos
]

emails = [
    "ana.garcia@mail.com", "luis.perez@gmail.com", "maria.lopez@hotmail.com",
    "carlos.ruiz@empresa.com", "sofia.m@yahoo.com", "jorge.h@correo.org",
    "valentina.t@mail.com", "andres.f@gmail.com", "camila.d@empresa.mx",
    "ricardo.m@mail.com", "isabella.c@yahoo.com", "fernando.j@hotmail.com",
    "lucia.r@correo.com", "sebastian.v@mail.com", "paula.g@gmail.com",
    "mateo.n@empresa.com", "daniela.r@mail.com", "diego.o@correo.org",
    "natalia.s@gmail.com", "alejandro.m@mail.com",
    "gabriela.reyes@mail.com", "nicolas.cruz@gmail.com", "veronica.herrera@mail.com",
    "emilio.mendoza@empresa.com", "laura.aguilar@mail.com",
    "sin_arroba_uno",        # inválido
    "sin_arroba_dos",        # inválido
    "sin_arroba_tres",       # inválido
    "roberto.vega@mail.com", "extra@mail.com",
]

edades = [
    25, 34, 28, 45, 52, 31, 22, 47, 38, 61,
    29, 43, 55, 27, 33, 48, 36, 24, 57, 41,
    -5,   # inválido
    -12,  # inválido
    200,  # inválido
    19, 63, 30, 44, 51, 26, 37,
]

estados = [
    "Activo", "Inactivo", "Activo", "Activo", "Inactivo",
    "Activo", "Inactivo", "Activo", "Inactivo", "Activo",
    "Activo", "Inactivo", "Activo", "Pendiente", "Activo",   # Pendiente inválido
    "Inactivo", "Activo", "Pendiente", "Activo", "Inactivo", # Pendiente inválido
    "Activo", "ACTIVO", "Inactivo", "Activo", "Inactivo",    # ACTIVO inconsistente
    "Activo", "Inactivo", "Activo", "Inactivo", "Activo",
]

fechas = [
    "2024-03-15", "2024-07-22", "2023-11-08", "2024-01-30", "2023-05-17",
    "2024-09-04", "2023-08-19", "2024-04-11", "2023-12-25", "2024-06-03",
    "2015-02-14",  # fuera de rango
    "2024-08-27", "2023-07-06", "2024-02-18", "2023-10-31",
    "2015-06-20",  # fuera de rango
    "2024-05-09", "2023-09-14", "2024-03-28", "2023-06-02",
    "2024-11-15", "2023-04-07",
    "2015-11-30",  # fuera de rango
    "2024-07-01", "2023-03-22", "2024-10-08", "2023-02-14", "2024-12-05",
    "2023-01-19", "2024-08-13",
]

# IDs con duplicados en posiciones 4 y 11 (IDs 5 y 12)
ids = list(range(1, 31))
ids[4]  = 5   # duplicado del ID 5 (índice 4, que ya es 5)
ids[11] = 12  # duplicado del ID 12 (índice 11, que ya es 12)
# Ajuste: los IDs van 1..30 en orden, pero repetimos 5 y 12
ids = list(range(1, 31))
ids[9]  = 5   # el registro 10 también tendrá cliente_id=5
ids[19] = 12  # el registro 20 también tendrá cliente_id=12

def _barra(score: float) -> str:
    filled = int(score / 10)
    return "[" + "█" * filled + "░" * (10 - filled) + "]"


df = pd.DataFrame({
    "cliente_id":      ids,
    "nombre":          nombres,
    "email":           emails,
    "edad":            edades,
    "estado":          estados,
    "fecha_registro":  fechas,
})

# ──────────────────────────────────────────────────────────────────────
# 2. Guardar CSV de prueba
# ──────────────────────────────────────────────────────────────────────

tests_dir = Path(__file__).resolve().parent
csv_path  = tests_dir / "dataset_prueba.csv"
df.to_csv(csv_path, index=False)
print(f"CSV guardado en: {csv_path}\n")

# ──────────────────────────────────────────────────────────────────────
# 3. Configurar y ejecutar análisis
# ──────────────────────────────────────────────────────────────────────

scorer = DQScorer(df, id_col="cliente_id")

scorer.configure("nombre", {
    "completitud": {},
    "precision": {"min_length": 2, "max_length": 50},
})

scorer.configure("email", {
    "completitud": {},
    "validez": {"regex_pattern": r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"},
})

scorer.configure("edad", {
    "completitud": {},
    "exactitud": {"min_value": 0, "max_value": 120},
    "razonabilidad": {},
})

scorer.configure("estado", {
    "completitud": {},
    "validez": {"valid_values": ["Activo", "Inactivo"]},
    "consistencia": {},
})

scorer.configure("fecha_registro", {
    "completitud": {},
    "vigencia": {"date_from": "2020-01-01", "date_to": "2025-12-31"},
})

results = scorer.run_analysis()
summary = scorer.get_summary()

# ──────────────────────────────────────────────────────────────────────
# 4. Imprimir resultados
# ──────────────────────────────────────────────────────────────────────

SEP = "─" * 60

print(SEP)
print(f"  SCORE GENERAL DEL DATASET: {results['score_general']} / 100")
print(SEP)

print("\n📋 SCORE POR COLUMNA Y DIMENSIÓN:")
for col, dim_scores in results["scores_por_columna"].items():
    print(f"\n  {col}")
    for dim, score in dim_scores.items():
        bar = _barra(score)
        print(f"    {dim:<25} {score:>6.1f}  {bar}")

print(f"\n{SEP}")
print(f"  Total registros   : {results['total_registros']}")
print(f"  Total problemas   : {results['total_problemas']}")
print(f"  % Registros limpios: {summary['pct_limpios']}%")
print(f"  Peor dimensión    : {summary['peor_dimension']}")
print(SEP)

issues = results["issues_df"]
print(f"\n🔍 PRIMEROS 10 PROBLEMAS ENCONTRADOS ({len(issues)} en total):")
print(issues.head(10).to_string(index=False))

# ──────────────────────────────────────────────────────────────────────
# 5. Generar reporte Excel
# ──────────────────────────────────────────────────────────────────────

xlsx_path = tests_dir / "reporte_prueba.xlsx"
generate_excel_report(results, str(xlsx_path))
print(f"\nReporte Excel generado en: {xlsx_path}")
