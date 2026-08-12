"""
tests/test_pesos_admin.py
Paso 8 — cobertura de los endpoints de administración de pesos y de la
congelación de overrides en el análisis.
"""
import json
import pytest
from fastapi.testclient import TestClient

from api.main import app
from database.db import get_connection, init_db

# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_pesos():
    """Elimina cualquier override residual antes y después de cada test."""
    conn = get_connection()
    conn.execute("DELETE FROM pesos_config")
    conn.commit()
    conn.close()
    yield
    conn = get_connection()
    conn.execute("DELETE FROM pesos_config")
    conn.commit()
    conn.close()


@pytest.fixture
def client():
    init_db()
    return TestClient(app)


@pytest.fixture
def admin_token(client):
    r = client.post("/auth/login", json={"email": "admin@dqplatform.com", "password": "Admin123!"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ── Test 1: GET /admin/pesos/{proposito} devuelve 11 dimensiones ─────────────

def test_get_pesos_returns_11_dimensions(client, auth):
    r = client.get("/admin/pesos/reporteria_bi", headers=auth)
    assert r.status_code == 200
    data = r.json()
    assert data["proposito"] == "reporteria_bi"
    assert len(data["dimensiones"]) == 11
    dims = {d["dimension"] for d in data["dimensiones"]}
    assert "completitud" in dims
    assert "similitud" in dims


# ── Test 2: GET devuelve nivel_articulo correcto para reporteria_bi ──────────

def test_get_pesos_nivel_articulo_correcto(client, auth):
    r = client.get("/admin/pesos/reporteria_bi", headers=auth)
    assert r.status_code == 200
    by_dim = {d["dimension"]: d for d in r.json()["dimensiones"]}
    assert by_dim["unicidad"]["nivel_articulo"] == "critica"
    assert by_dim["completitud"]["nivel_articulo"] == "critica"
    assert by_dim["precision"]["nivel_articulo"] == "informativa"
    # Sin overrides: nivel_actual == nivel_articulo
    for d in r.json()["dimensiones"]:
        assert d["nivel_actual"] == d["nivel_articulo"]
        assert d["modificado"] is False


# ── Test 3: PUT guarda override y GET lo refleja ─────────────────────────────

def test_put_override_persiste(client, auth):
    r = client.put(
        "/admin/pesos/reporteria_bi",
        json={"dimension": "precision", "nivel": "critica"},
        headers=auth,
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True

    r2 = client.get("/admin/pesos/reporteria_bi", headers=auth)
    by_dim = {d["dimension"]: d for d in r2.json()["dimensiones"]}
    assert by_dim["precision"]["nivel_actual"] == "critica"
    assert by_dim["precision"]["nivel_articulo"] == "informativa"
    assert by_dim["precision"]["modificado"] is True


# ── Test 4: PUT con valor == nivel_articulo elimina el override ──────────────

def test_put_valor_articulo_elimina_override(client, auth):
    # Crea override
    client.put(
        "/admin/pesos/reporteria_bi",
        json={"dimension": "precision", "nivel": "critica"},
        headers=auth,
    )
    # Restaura al valor del artículo
    r = client.put(
        "/admin/pesos/reporteria_bi",
        json={"dimension": "precision", "nivel": "informativa"},
        headers=auth,
    )
    assert r.status_code == 200
    assert r.json()["removed_override"] is True

    r2 = client.get("/admin/pesos/reporteria_bi", headers=auth)
    by_dim = {d["dimension"]: d for d in r2.json()["dimensiones"]}
    assert by_dim["precision"]["modificado"] is False


# ── Test 5: DELETE elimina todos los overrides del propósito ─────────────────

def test_delete_restaura_propósito(client, auth):
    # Crea dos overrides
    client.put("/admin/pesos/migracion", json={"dimension": "exactitud", "nivel": "critica"}, headers=auth)
    client.put("/admin/pesos/migracion", json={"dimension": "oportunidad", "nivel": "alta"}, headers=auth)

    r = client.delete("/admin/pesos/migracion", headers=auth)
    assert r.status_code == 200
    assert r.json()["eliminados"] == 2

    r2 = client.get("/admin/pesos/migracion", headers=auth)
    for d in r2.json()["dimensiones"]:
        assert d["modificado"] is False


# ── Test 6: los overrides se congelan en pesos_usados al analizar ────────────

def test_analisis_conserva_pesos_historicos(client, auth):
    """
    El análisis debe congelar los pesos vigentes en el momento de ejecutarse,
    de modo que un override posterior no altere el registro histórico.
    """
    import io, csv
    # Sube un CSV mínimo
    csv_content = "id,nombre\n1,Alice\n2,Bob\n3,Charlie\n"
    upload_r = client.post(
        "/upload",
        files={"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        headers=auth,
    )
    assert upload_r.status_code == 200, upload_r.text
    file_id = upload_r.json()["file_id"]

    # Aplica override ANTES del análisis: completitud → critica (reporteria_bi ya es critica,
    # usamos diagnostico_general donde es media por defecto)
    client.put(
        "/admin/pesos/diagnostico_general",
        json={"dimension": "completitud", "nivel": "critica"},
        headers=auth,
    )

    # Lanza análisis con propósito diagnostico_general
    analyze_r = client.post(
        "/analyze",
        json={
            "file_id": file_id,
            "id_column": "id",
            "columns_config": {"nombre": {"completitud": {}}},
            "proposito_analisis": "diagnostico_general",
            "pesos_modo": "proposito",
        },
        headers=auth,
    )
    assert analyze_r.status_code == 200, analyze_r.text
    resultado = analyze_r.json()

    # El análisis debe reportar al menos 1 override aplicado
    assert resultado.get("overrides_aplicados", 0) >= 1, (
        "Se esperaba overrides_aplicados >= 1 en la respuesta del análisis"
    )

    # Verifica que los pesos congelados en BD tienen el override
    conn = get_connection()
    row = conn.execute(
        "SELECT pesos_usados FROM analisis WHERE file_id = ? ORDER BY id DESC LIMIT 1",
        (file_id,),
    ).fetchone()
    conn.close()
    assert row is not None
    pesos_frozen = json.loads(row["pesos_usados"])
    assert pesos_frozen["niveles"]["completitud"] == "critica", (
        "El nivel de completitud debería ser 'critica' en los pesos congelados"
    )
    assert pesos_frozen.get("overrides_aplicados", 0) >= 1, (
        "overrides_aplicados debería estar congelado en pesos_usados"
    )
