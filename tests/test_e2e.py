"""
FASE 4 — Test end-to-end del flujo completo del usuario real.
Login → Upload → Análisis → Verificación → Reporte Excel → Logout
"""
import sys
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import openpyxl
from starlette.testclient import TestClient

from api.main import app
from database.db import init_db

init_db()
client = TestClient(app)

DATASET_PATH = Path(__file__).parent / "dataset_1000.csv"


def test_full_user_flow():
    """
    Flujo completo del usuario real:
    1. Login con admin
    2. Subir dataset_1000.csv
    3. Configurar 5 columnas con ≥3 dimensiones cada una
    4. Ejecutar análisis
    5. Verificar score general y problemas
    6. Descargar reporte Excel con 3 pestañas
    7. Logout y verificar invalidación del token
    """
    if not DATASET_PATH.exists():
        pytest.skip("dataset_1000.csv no encontrado — ejecuta generar_dataset_grande.py")

    # ── 1. LOGIN ──────────────────────────────────────────
    login_resp = client.post("/auth/login", json={
        "email": "admin@dqplatform.com",
        "password": "Admin123!",
    })
    assert login_resp.status_code == 200, f"Login falló: {login_resp.text}"
    token = login_resp.json()["token"]
    headers = {"authorization": f"Bearer {token}"}

    # ── 2. UPLOAD ─────────────────────────────────────────
    with open(DATASET_PATH, "rb") as f:
        upload_resp = client.post(
            "/upload",
            headers=headers,
            files={"file": ("dataset_1000.csv", f, "text/csv")},
        )
    assert upload_resp.status_code == 200, f"Upload falló: {upload_resp.text}"
    upload_data = upload_resp.json()
    file_id = upload_data["file_id"]
    assert upload_data["total_registros"] == 1000
    col_names = [c["nombre"] for c in upload_data["columnas"]]
    assert "cliente_id" in col_names
    assert len(col_names) >= 5

    # ── 3 & 4. ANÁLISIS con 5 columnas y ≥3 dims cada una ─
    analyze_resp = client.post(
        "/analyze",
        headers=headers,
        json={
            "file_id": file_id,
            "id_column": "cliente_id",
            "columns_config": {
                "nombre": {
                    "completitud": {},
                    "precision": {"min_length": 2, "max_length": 80},
                    "consistencia": {},
                },
                "email": {
                    "completitud": {},
                    "validez": {"regex_pattern": r"[^@]+@[^@]+\.[^@]+"},
                    "unicidad": {},
                },
                "edad": {
                    "completitud": {},
                    "exactitud": {"min_value": 0, "max_value": 120},
                    "razonabilidad": {},
                },
                "estado_cliente": {
                    "completitud": {},
                    "validez": {"valid_values": ["Activo", "Inactivo", "Suspendido",
                                                  "activo", "inactivo", "suspendido"]},
                    "vigencia": {"obsolete_values": ["eliminado", "cancelado"]},
                },
                "fecha_registro": {
                    "completitud": {},
                    "vigencia": {"date_from": "2000-01-01", "date_to": "2030-12-31"},
                    "oportunidad": {"max_age_days": 9999},
                },
            },
        },
    )
    assert analyze_resp.status_code == 200, f"Análisis falló: {analyze_resp.text}"
    analyze_data = analyze_resp.json()

    # ── 5. VERIFICACIÓN de resultados ─────────────────────
    score = analyze_data["score_general"]
    assert 0 <= score <= 100, f"Score fuera de rango: {score}"
    assert analyze_data["total_registros"] == 1000
    assert "scores_por_columna" in analyze_data

    # El dataset tiene errores inyectados → deben detectarse problemas
    assert analyze_data["total_problemas"] > 0, (
        "Se esperaban problemas detectados en el dataset de prueba"
    )

    # Verificar las 5 columnas configuradas
    scores_col = analyze_data["scores_por_columna"]
    for expected_col in ["nombre", "email", "edad", "estado_cliente", "fecha_registro"]:
        assert expected_col in scores_col, f"Columna '{expected_col}' no encontrada en scores"

    # Cada columna debe tener al menos 3 dimensiones
    for col_name, dims in scores_col.items():
        assert len(dims) >= 3, f"Columna '{col_name}' tiene menos de 3 dimensiones: {dims}"

    print(f"\n  Score general        : {score:.2f}")
    print(f"  Problemas detectados : {analyze_data['total_problemas']}")

    # ── 6. REPORTE EXCEL con 3 pestañas ───────────────────
    report_resp = client.get(f"/report/{file_id}", headers=headers)
    assert report_resp.status_code == 200, f"Reporte falló: {report_resp.text}"

    wb = openpyxl.load_workbook(io.BytesIO(report_resp.content))
    sheet_names = wb.sheetnames
    assert "Dashboard" in sheet_names, f"Falta 'Dashboard'. Hojas: {sheet_names}"
    assert "Problemas Detallados" in sheet_names, \
        f"Falta 'Problemas Detallados'. Hojas: {sheet_names}"
    assert "Score por Columna" in sheet_names, \
        f"Falta 'Score por Columna'. Hojas: {sheet_names}"

    # Verificar que el Dashboard tiene datos
    ws_dash = wb["Dashboard"]
    assert ws_dash["A1"].value is not None, "Dashboard vacío"

    print(f"  Pestañas del reporte : {sheet_names}")

    # ── 7. LOGOUT ─────────────────────────────────────────
    logout_resp = client.post("/auth/logout", headers=headers)
    assert logout_resp.status_code == 200

    me_resp = client.get("/auth/me", headers=headers)
    assert me_resp.status_code == 401, "Token debe invalidarse tras logout"

    print("  ✓ Flujo E2E completado exitosamente")


def test_issues_endpoint_after_analysis():
    """Verifica el endpoint /issues/{file_id} devuelve estructura correcta."""
    if not DATASET_PATH.exists():
        pytest.skip("dataset_1000.csv no encontrado")

    # Login
    token = client.post("/auth/login", json={
        "email": "admin@dqplatform.com", "password": "Admin123!"
    }).json()["token"]
    headers = {"authorization": f"Bearer {token}"}

    # Upload
    with open(DATASET_PATH, "rb") as f:
        fid = client.post("/upload", headers=headers,
                          files={"file": ("ds.csv", f, "text/csv")}).json()["file_id"]

    # Analyze
    client.post("/analyze", headers=headers, json={
        "file_id": fid,
        "id_column": "cliente_id",
        "columns_config": {"nombre": {"completitud": {}}, "email": {"unicidad": {}}},
    })

    # Issues
    resp = client.get(f"/issues/{fid}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "issues" in data
    assert isinstance(data["issues"], list)


def test_analyze_invalid_id_column():
    """El análisis debe fallar con 400 si id_column no existe."""
    import io, pandas as pd
    token = client.post("/auth/login", json={
        "email": "admin@dqplatform.com", "password": "Admin123!"
    }).json()["token"]
    headers = {"authorization": f"Bearer {token}"}

    df = pd.DataFrame({"col_a": [1, 2, 3], "col_b": ["x", "y", "z"]})
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)

    fid = client.post("/upload", headers=headers,
                      files={"file": ("tmp.csv", buf.getvalue(), "text/csv")}).json()["file_id"]

    resp = client.post("/analyze", headers=headers, json={
        "file_id": fid,
        "id_column": "columna_que_no_existe",
        "columns_config": {"col_a": {"completitud": {}}},
    })
    assert resp.status_code == 400


def test_analyze_invalid_dimension_name():
    """El análisis debe fallar si se usa un nombre de dimensión desconocido."""
    import io, pandas as pd
    token = client.post("/auth/login", json={
        "email": "admin@dqplatform.com", "password": "Admin123!"
    }).json()["token"]
    headers = {"authorization": f"Bearer {token}"}

    df = pd.DataFrame({"id": [1, 2], "val": ["a", "b"]})
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)

    fid = client.post("/upload", headers=headers,
                      files={"file": ("tmp2.csv", buf.getvalue(), "text/csv")}).json()["file_id"]

    resp = client.post("/analyze", headers=headers, json={
        "file_id": fid,
        "id_column": "id",
        "columns_config": {"val": {"dimension_falsa": {}}},
    })
    assert resp.status_code in (400, 422, 500)
