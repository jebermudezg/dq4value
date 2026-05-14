"""
FASE 2 — Tests de integración de la API.
Prueba todos los endpoints con token válido, inválido, admin y usuario regular.
"""
import sys
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pandas as pd
from starlette.testclient import TestClient

from api.main import app
from database.db import init_db

# Inicializar DB antes de todos los tests
init_db()

client = TestClient(app)

ADMIN_EMAIL = "admin@dqplatform.com"
ADMIN_PASS  = "Admin123!"
TEST_USER_EMAIL = "test_user_integracion@dqplatform.com"
TEST_USER_PASS  = "IntegPass123!"


# ─────────────────────────────────────────────────────────
# Fixtures de sesión
# ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def admin_token():
    resp = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert resp.status_code == 200, f"Login admin falló: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def regular_user(admin_token):
    """Crea un usuario regular de prueba y lo elimina al terminar."""
    resp = client.post(
        "/admin/usuarios",
        headers={"authorization": f"Bearer {admin_token}"},
        json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASS,
            "nombre": "Test Usuario Integración",
            "rol": "usuario",
            "max_registros": 5000,
        },
    )
    # Si ya existe, continúa de todas formas
    user_id = resp.json().get("id") if resp.status_code == 200 else None
    yield {"email": TEST_USER_EMAIL, "password": TEST_USER_PASS, "id": user_id}
    if user_id:
        client.delete(
            f"/admin/usuarios/{user_id}",
            headers={"authorization": f"Bearer {admin_token}"},
        )


@pytest.fixture(scope="module")
def regular_token(regular_user):
    resp = client.post(
        "/auth/login",
        json={"email": regular_user["email"], "password": regular_user["password"]},
    )
    assert resp.status_code == 200, f"Login regular falló: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def sample_csv():
    df = pd.DataFrame({
        "id":     [1, 2, 3, 4, 5],
        "nombre": ["Alice", "Bob", None, "Dave", "Eve"],
        "edad":   [25, 30, 35, 40, 45],
        "estado": ["activo", "activo", "inactivo", "activo", "inactivo"],
    })
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


@pytest.fixture(scope="module")
def uploaded_file_id(admin_token, sample_csv):
    resp = client.post(
        "/upload",
        headers={"authorization": f"Bearer {admin_token}"},
        files={"file": ("test_integracion.csv", sample_csv, "text/csv")},
    )
    assert resp.status_code == 200, f"Upload falló: {resp.text}"
    return resp.json()["file_id"]


@pytest.fixture(scope="module")
def analyzed_file_id(admin_token, uploaded_file_id):
    resp = client.post(
        "/analyze",
        headers={"authorization": f"Bearer {admin_token}"},
        json={
            "file_id": uploaded_file_id,
            "id_column": "id",
            "columns_config": {
                "nombre": {"completitud": {}},
                "edad":   {"exactitud": {"min_value": 0, "max_value": 120}},
                "estado": {"validez": {"valid_values": ["activo", "inactivo"]}},
            },
        },
    )
    assert resp.status_code == 200, f"Análisis falló: {resp.text}"
    return uploaded_file_id


# ─────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────

def test_health_returns_200():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


# ─────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────

def test_login_correct_credentials():
    resp = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["rol"] == "admin"
    assert data["email"] == ADMIN_EMAIL


def test_login_wrong_password():
    resp = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": "wrongpassword"})
    assert resp.status_code == 401


def test_login_wrong_email():
    resp = client.post("/auth/login", json={"email": "noexiste@test.com", "password": "any"})
    assert resp.status_code == 401


def test_auth_me_with_valid_token(admin_token):
    resp = client.get("/auth/me", headers={"authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == ADMIN_EMAIL
    assert data["rol"] == "admin"


def test_auth_me_without_token():
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_logout_invalidates_token():
    # Crear token fresco para este test
    resp = client.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    fresh_token = resp.json()["token"]

    # Logout
    logout = client.post("/auth/logout", headers={"authorization": f"Bearer {fresh_token}"})
    assert logout.status_code == 200

    # El token ya no debe funcionar
    me = client.get("/auth/me", headers={"authorization": f"Bearer {fresh_token}"})
    assert me.status_code == 401


# ─────────────────────────────────────────────────────────
# Upload
# ─────────────────────────────────────────────────────────

def test_upload_without_token(sample_csv):
    resp = client.post("/upload", files={"file": ("test.csv", sample_csv, "text/csv")})
    assert resp.status_code == 401


def test_upload_with_admin_token(admin_token, sample_csv):
    resp = client.post(
        "/upload",
        headers={"authorization": f"Bearer {admin_token}"},
        files={"file": ("test_upload.csv", sample_csv, "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "file_id" in data
    assert "columnas" in data
    assert data["total_registros"] == 5
    assert data["total_columnas"] == 4


def test_upload_unsupported_format(admin_token):
    resp = client.post(
        "/upload",
        headers={"authorization": f"Bearer {admin_token}"},
        files={"file": ("data.json", b'{"a": 1}', "application/json")},
    )
    assert resp.status_code == 400


def test_upload_returns_column_info(admin_token, sample_csv):
    resp = client.post(
        "/upload",
        headers={"authorization": f"Bearer {admin_token}"},
        files={"file": ("test_colinfo.csv", sample_csv, "text/csv")},
    )
    assert resp.status_code == 200
    columnas = resp.json()["columnas"]
    col_names = [c["nombre"] for c in columnas]
    assert "id" in col_names
    assert "nombre" in col_names


# ─────────────────────────────────────────────────────────
# Analyze
# ─────────────────────────────────────────────────────────

def test_analyze_returns_score(analyzed_file_id, admin_token):
    # El fixture ya realizó el análisis; verificamos que los datos sean válidos
    # Re-hacemos con el mismo file_id para validar estructura
    resp = client.post(
        "/analyze",
        headers={"authorization": f"Bearer {admin_token}"},
        json={
            "file_id": analyzed_file_id,
            "id_column": "id",
            "columns_config": {"nombre": {"completitud": {}}},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert 0 <= data["score_general"] <= 100
    assert data["total_registros"] == 5
    assert "scores_por_columna" in data


def test_analyze_nonexistent_file(admin_token):
    resp = client.post(
        "/analyze",
        headers={"authorization": f"Bearer {admin_token}"},
        json={
            "file_id": "id_que_no_existe_xyz",
            "id_column": "id",
            "columns_config": {"col": {"completitud": {}}},
        },
    )
    assert resp.status_code == 404


def test_analyze_without_token(uploaded_file_id):
    resp = client.post(
        "/analyze",
        json={
            "file_id": uploaded_file_id,
            "id_column": "id",
            "columns_config": {"nombre": {"completitud": {}}},
        },
    )
    assert resp.status_code == 401


def test_analyze_status_endpoint(admin_token, uploaded_file_id):
    resp = client.get(
        f"/analyze/status/{uploaded_file_id}",
        headers={"authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "pct" in data
    assert "done" in data


# ─────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────

def test_get_report_returns_excel(admin_token, analyzed_file_id):
    resp = client.get(
        f"/report/{analyzed_file_id}",
        headers={"authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    content_type = resp.headers.get("content-type", "")
    assert "spreadsheetml" in content_type or "octet-stream" in content_type


def test_get_report_before_analyze(admin_token, sample_csv):
    # Sube un archivo pero NO analiza
    resp = client.post(
        "/upload",
        headers={"authorization": f"Bearer {admin_token}"},
        files={"file": ("orphan.csv", sample_csv, "text/csv")},
    )
    fid = resp.json()["file_id"]
    report = client.get(f"/report/{fid}", headers={"authorization": f"Bearer {admin_token}"})
    assert report.status_code == 400


def test_get_report_nonexistent_file(admin_token):
    resp = client.get(
        "/report/archivo_inexistente_xyz",
        headers={"authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────
# Admin endpoints
# ─────────────────────────────────────────────────────────

def test_admin_list_users_no_token():
    resp = client.get("/admin/usuarios")
    assert resp.status_code == 401


def test_admin_list_users_regular_user(regular_token):
    resp = client.get("/admin/usuarios", headers={"authorization": f"Bearer {regular_token}"})
    assert resp.status_code == 403


def test_admin_list_users_as_admin(admin_token):
    resp = client.get("/admin/usuarios", headers={"authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    users = resp.json()
    assert isinstance(users, list)
    assert any(u["email"] == ADMIN_EMAIL for u in users)


def test_admin_create_user(admin_token):
    unique_email = "temp_create_test@dqplatform.com"
    resp = client.post(
        "/admin/usuarios",
        headers={"authorization": f"Bearer {admin_token}"},
        json={
            "email": unique_email,
            "password": "TempPass999!",
            "nombre": "Temp Create Test",
            "rol": "usuario",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    # Limpieza
    client.delete(
        f"/admin/usuarios/{data['id']}",
        headers={"authorization": f"Bearer {admin_token}"},
    )


def test_admin_create_user_duplicate_email(admin_token):
    resp = client.post(
        "/admin/usuarios",
        headers={"authorization": f"Bearer {admin_token}"},
        json={
            "email": ADMIN_EMAIL,  # ya existe
            "password": "AnyPass123!",
            "nombre": "Duplicado",
            "rol": "usuario",
        },
    )
    assert resp.status_code == 400


def test_admin_update_user(admin_token, regular_user):
    if not regular_user["id"]:
        pytest.skip("Usuario de prueba no disponible")
    resp = client.put(
        f"/admin/usuarios/{regular_user['id']}",
        headers={"authorization": f"Bearer {admin_token}"},
        json={"nombre": "Nombre Actualizado"},
    )
    assert resp.status_code == 200


def test_admin_update_user_password(admin_token, regular_user):
    if not regular_user["id"]:
        pytest.skip("Usuario de prueba no disponible")
    resp = client.put(
        f"/admin/usuarios/{regular_user['id']}",
        headers={"authorization": f"Bearer {admin_token}"},
        json={"password": "NuevaClave123!"},
    )
    assert resp.status_code == 200
    # Verificar que la nueva clave funciona
    login = client.post(
        "/auth/login",
        json={"email": TEST_USER_EMAIL, "password": "NuevaClave123!"},
    )
    assert login.status_code == 200


def test_admin_update_short_password_rejected(admin_token, regular_user):
    if not regular_user["id"]:
        pytest.skip("Usuario de prueba no disponible")
    resp = client.put(
        f"/admin/usuarios/{regular_user['id']}",
        headers={"authorization": f"Bearer {admin_token}"},
        json={"password": "abc"},
    )
    assert resp.status_code == 400


def test_admin_cannot_delete_self(admin_token):
    me = client.get("/auth/me", headers={"authorization": f"Bearer {admin_token}"})
    my_id = me.json()["id"]
    resp = client.delete(
        f"/admin/usuarios/{my_id}",
        headers={"authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400
