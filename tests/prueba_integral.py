"""
Prueba integral end-to-end de DQ4Value via API HTTP real.
Cubre: health, auth, upload, profile, suggest, analyze, issues, report, historial, admin.
"""
import json
import subprocess
import sys
from pathlib import Path

BASE = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parent.parent
errores: list[str] = []
total_checks = 0


def check(nombre: str, condicion: bool, detalle: str = "") -> None:
    global total_checks
    total_checks += 1
    if condicion:
        print(f"  ✅ {nombre}")
    else:
        msg = f"  ❌ {nombre}"
        if detalle:
            msg += f"  —  {detalle}"
        print(msg)
        errores.append(nombre)


def curl_json(*args):
    r = subprocess.run(["curl", "-s", "-w", "\n%{http_code}", *args], capture_output=True)
    lines = r.stdout.decode("utf-8", errors="replace").strip().rsplit("\n", 1)
    body_text = lines[0] if len(lines) == 2 else ""
    status = int(lines[-1]) if lines[-1].isdigit() else 0
    try:
        body = json.loads(body_text)
    except Exception:
        body = {"_raw": body_text[:300]}
    return status, body


print("\n=== PRUEBA INTEGRAL DQ4Value ===\n")

# ── 1. Health ──────────────────────────────────────────────────────────────
print("1. Health check")
st, body = curl_json("http://127.0.0.1:8000/health")
check("GET /health retorna 200", st == 200, f"status={st}")
check("Respuesta tiene status ok", body.get("status") == "ok", str(body))

# ── 2. Auth ───────────────────────────────────────────────────────────────
print("\n2. Autenticación")
st, body = curl_json("-X", "POST", f"{BASE}/auth/login",
    "-H", "Content-Type: application/json",
    "-d", '{"email":"admin@dqplatform.com","password":"Admin123!"}')
check("Login admin exitoso", st == 200, str(body)[:200])
token = body.get("token", "")
check("Token recibido", bool(token))
auth = f"Bearer {token}"

st, _ = curl_json("-X", "POST", f"{BASE}/auth/login",
    "-H", "Content-Type: application/json",
    "-d", '{"email":"malo@test.com","password":"wrongpass"}')
check("Login incorrecto retorna 401", st == 401)

# ── 3. Protección ─────────────────────────────────────────────────────────
# FastAPI valida los params requeridos (file, JSON body) antes de ejecutar la función.
# Sin payload → 422. Hay que enviar un payload válido pero sin Authorization para
# que llegue al check de auth y retorne 401.
print("\n3. Protección de endpoints")
_csv_path = str(ROOT / "tests" / "dataset_1000.csv")
r_prot = subprocess.run(["curl", "-s", "-w", "\n%{http_code}",
    "-X", "POST", f"{BASE}/upload",
    "-F", f"file=@{_csv_path}"],   # sin Authorization
    capture_output=True)
lines_p = r_prot.stdout.decode().strip().rsplit("\n", 1)
st = int(lines_p[-1]) if lines_p[-1].isdigit() else 0
check("Upload sin token retorna 401", st == 401, f"status={st}")

st, _ = curl_json("-X", "POST", f"{BASE}/analyze",
    "-H", "Content-Type: application/json",
    "-d", '{"file_id":"x","id_column":"id","columns_config":{"c":{"completitud":{}}}}')
check("Analyze sin token retorna 401", st == 401, f"status={st}")

# ── 4. Upload ─────────────────────────────────────────────────────────────
print("\n4. Upload de archivo")
csv_path = str(ROOT / "tests" / "dataset_1000.csv")
r = subprocess.run(["curl", "-s", "-w", "\n%{http_code}",
    "-X", "POST", f"{BASE}/upload",
    "-H", f"Authorization: {auth}",
    "-F", f"file=@{csv_path}"], capture_output=True)
lines = r.stdout.decode().strip().rsplit("\n", 1)
st = int(lines[-1]) if lines[-1].isdigit() else 0
body = json.loads(lines[0]) if lines[0] else {}
check("Upload retorna 200", st == 200, str(body)[:200])
file_id = body.get("file_id", "")
check("file_id recibido", bool(file_id))
check("Columnas detectadas (≥10)", len(body.get("columnas", [])) >= 10,
      f"detectadas: {len(body.get('columnas', []))}")
check("total_registros == 1000", body.get("total_registros") == 1000,
      f"filas={body.get('total_registros')}")

# ── 5. Perfil ─────────────────────────────────────────────────────────────
print("\n5. Data Profiling")
st, perfil = curl_json(f"{BASE}/profile/{file_id}", "-H", f"Authorization: {auth}")
check("GET /profile retorna 200", st == 200, str(perfil)[:200])
check("Perfil tiene resumen", "resumen" in perfil, str(list(perfil.keys()))[:100])
check("Perfil tiene columnas", "columnas" in perfil)
resumen = perfil.get("resumen", {})
check("total_filas == 1000", resumen.get("total_filas") == 1000,
      f"total_filas={resumen.get('total_filas')}")
check("Perfil tiene alertas", "alertas" in resumen)

# ── 6. Sugerencias ────────────────────────────────────────────────────────
print("\n6. Sugerencias de dimensiones")
st, sug_data = curl_json("-X", "POST", f"{BASE}/ai/suggest",
    "-H", f"Authorization: {auth}",
    "-H", "Content-Type: application/json",
    "-d", json.dumps({"file_id": file_id}))
check("POST /ai/suggest retorna 200", st == 200, str(sug_data)[:200])
sugs = sug_data.get("sugerencias", [])
check("Sugerencias generadas (≥10 cols)", len(sugs) >= 10, f"cols={len(sugs)}")
if sugs:
    primera_dim = sugs[0].get("dimensiones", [])
    if primera_dim:
        check("Sugerencias tienen campo confianza", "confianza" in primera_dim[0], str(primera_dim[0]))
        check("Sugerencias tienen campo razon", "razon" in primera_dim[0])
        check("Sugerencias tienen campo params", "params" in primera_dim[0])
    check("cliente_id no tiene similitud",
          not any(d["dimension"] == "similitud"
                  for s in sugs if s["columna"] == "cliente_id"
                  for d in s["dimensiones"]),
          "cliente_id tiene similitud incorrectamente")

# ── 7. Análisis completo ──────────────────────────────────────────────────
print("\n7. Análisis de calidad")
config = {
    "file_id": file_id,
    "id_column": "cliente_id",
    "descripcion": "Prueba integral automatizada",
    "etiqueta": "Maestro",
    "columns_config": {
        "nombre":         {"completitud": {}, "unicidad": {}},
        "email":          {"completitud": {}, "unicidad": {}},
        "edad":           {"completitud": {}, "exactitud": {"min_value": 0, "max_value": 120}, "razonabilidad": {}},
        "estado_cliente": {"completitud": {}, "consistencia": {}},
        "fecha_registro": {"completitud": {}, "vigencia": {"date_from": "2020-01-01", "date_to": "2025-12-31"}},
    },
}
st, resultado = curl_json("-X", "POST", f"{BASE}/analyze",
    "-H", f"Authorization: {auth}",
    "-H", "Content-Type: application/json",
    "-d", json.dumps(config))
check("POST /analyze retorna 200", st == 200, str(resultado)[:300])
score = resultado.get("score_general", -1)
check("Score entre 0 y 100", 0 <= score <= 100, f"score={score}")
check("total_problemas presente", "total_problemas" in resultado)
check("scores_por_columna presente", "scores_por_columna" in resultado)
check("total_registros == 1000", resultado.get("total_registros") == 1000,
      f"registros={resultado.get('total_registros')}")

# ── 8. Issues ─────────────────────────────────────────────────────────────
print("\n8. Problemas detallados")
st, issues_body = curl_json(f"{BASE}/issues/{file_id}",
    "-H", f"Authorization: {auth}")
check("GET /issues retorna 200", st == 200, str(issues_body)[:200])
issues = issues_body.get("issues", [])
check("Issues es lista", isinstance(issues, list))
check("Hay problemas detectados (>0)", len(issues) > 0, f"issues={len(issues)}")
if issues:
    check("Issues tienen id_registro",  "id_registro"  in issues[0], str(list(issues[0].keys())))
    check("Issues tienen dimension",    "dimension"    in issues[0])
    check("Issues tienen descripcion",  "descripcion"  in issues[0])

# ── 9. Reporte Excel ──────────────────────────────────────────────────────
print("\n9. Reporte Excel")
r2 = subprocess.run(["curl", "-s", "-w", "\n%{http_code}",
    "-o", "/tmp/test_report.xlsx",
    f"{BASE}/report/{file_id}",
    "-H", f"Authorization: {auth}"], capture_output=True)
st_report_line = r2.stdout.decode().strip().split("\n")[-1]
st_report = int(st_report_line) if st_report_line.isdigit() else 0
check("GET /report retorna 200", st_report == 200, f"status={st_report}")
from pathlib import Path as _P
xlsx = _P("/tmp/test_report.xlsx")
check("Reporte tiene tamaño > 0", xlsx.exists() and xlsx.stat().st_size > 0,
      f"size={xlsx.stat().st_size if xlsx.exists() else 'missing'}")
# XLSX = ZIP, magic bytes = PK\x03\x04
if xlsx.exists():
    magic = xlsx.read_bytes()[:4]
    check("Reporte tiene firma XLSX (ZIP)", magic == b"PK\x03\x04",
          f"magic={magic.hex()}")

# ── 10. Historial ─────────────────────────────────────────────────────────
print("\n10. Historial de análisis")
st, hist = curl_json(f"{BASE}/historial", "-H", f"Authorization: {auth}")
check("GET /historial retorna 200", st == 200, str(hist)[:100])
check("Historial es lista", isinstance(hist, list), type(hist).__name__)
check("Al menos 1 análisis en historial", len(hist) >= 1, f"registros={len(hist)}")
if hist:
    h0 = hist[0]
    check("Historial tiene score_general",     "score_general"    in h0)
    check("Historial tiene ruta_reporte",      "ruta_reporte"     in h0)
    check("Historial tiene dimensiones_aplicadas", "dimensiones_aplicadas" in h0)

st, stats = curl_json(f"{BASE}/historial/stats", "-H", f"Authorization: {auth}")
check("GET /historial/stats retorna 200", st == 200, str(stats)[:100])
check("Stats tienen total_analisis",    "total_analisis"            in stats)
check("Stats tienen score_promedio",    "score_promedio"            in stats)
check("Stats tienen total_registros",   "total_registros_evaluados" in stats)

# ── 11. Admin ─────────────────────────────────────────────────────────────
print("\n11. Panel de administración")
st, usuarios = curl_json(f"{BASE}/admin/usuarios", "-H", f"Authorization: {auth}")
check("GET /admin/usuarios retorna 200", st == 200)
check("Lista de usuarios retornada", isinstance(usuarios, list))
check("Admin en la lista",
      any(u.get("email") == "admin@dqplatform.com" for u in usuarios))

nuevo = json.dumps({"email": "prueba_integral@test.com", "password": "Test123!",
                    "nombre": "Usuario Prueba", "rol": "usuario", "max_registros": 5000})
st, cr = curl_json("-X", "POST", f"{BASE}/admin/usuarios",
    "-H", f"Authorization: {auth}",
    "-H", "Content-Type: application/json", "-d", nuevo)
check("POST /admin/usuarios crea usuario", st in (200, 201), str(cr)[:100])
nuevo_id = cr.get("id")

st, lr = curl_json("-X", "POST", f"{BASE}/auth/login",
    "-H", "Content-Type: application/json",
    "-d", '{"email":"prueba_integral@test.com","password":"Test123!"}')
check("Nuevo usuario hace login", st == 200, str(lr)[:100])
utoken = lr.get("token", "")
st, _ = curl_json(f"{BASE}/admin/usuarios",
    "-H", f"Authorization: Bearer {utoken}")
check("Usuario normal no accede a /admin (403)", st == 403, f"status={st}")

if nuevo_id:
    st, _ = curl_json("-X", "DELETE", f"{BASE}/admin/usuarios/{nuevo_id}",
        "-H", f"Authorization: {auth}")
    check("DELETE /admin/usuarios elimina usuario", st == 200)

# ── 12. Auth/me y logout ──────────────────────────────────────────────────
print("\n12. Auth/me y logout")
st, me = curl_json(f"{BASE}/auth/me", "-H", f"Authorization: {auth}")
check("GET /auth/me retorna 200", st == 200)
check("auth/me retorna email correcto",
      me.get("email") == "admin@dqplatform.com", str(me))

st, _ = curl_json("-X", "POST", f"{BASE}/auth/logout", "-H", f"Authorization: {auth}")
check("POST /auth/logout exitoso", st == 200)
st, _ = curl_json(f"{BASE}/auth/me", "-H", f"Authorization: {auth}")
check("Token invalidado tras logout", st == 401, f"status={st}")

# ── Resumen ───────────────────────────────────────────────────────────────
print(f"\n{'='*45}")
ok = total_checks - len(errores)
print(f"RESULTADO FINAL: {ok}/{total_checks} pruebas pasaron")
if errores:
    print(f"\nErrores encontrados ({len(errores)}):")
    for e in errores:
        print(f"  ❌ {e}")
    sys.exit(1)
else:
    print("✅ TODAS LAS PRUEBAS PASARON")
    sys.exit(0)
