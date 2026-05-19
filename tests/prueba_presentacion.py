import requests
import json
import time

BASE = "http://127.0.0.1:8000"
errores = []
advertencias = []

def ok(nombre):
    print(f"  ✅ {nombre}")

def fail(nombre, detalle=""):
    print(f"  ❌ {nombre} — {detalle}")
    errores.append(f"{nombre}: {detalle}")

def warn(nombre, detalle=""):
    print(f"  ⚠️  {nombre} — {detalle}")
    advertencias.append(f"{nombre}: {detalle}")

def check(nombre, cond, detalle=""):
    if cond: ok(nombre)
    else: fail(nombre, detalle)

print("\n" + "="*50)
print("PRUEBA INTEGRAL — PREPARACIÓN PRESENTACIÓN")
print("="*50 + "\n")

# 1. Health
print("1. Servidor")
r = requests.get(f"{BASE}/health")
check("Health check", r.status_code == 200)
check("Versión presente", "version" in r.json())

# 2. Auth
print("\n2. Autenticación")
r = requests.post(f"{BASE}/auth/login",
    json={"email": "admin@dqplatform.com", "password": "Admin123!"})
check("Login admin", r.status_code == 200, r.text[:100])
token = r.json().get("token", "")
nombre_usuario = r.json().get("nombre", "")
check("Token recibido", bool(token))
check("Nombre usuario recibido", bool(nombre_usuario))
headers = {"Authorization": f"Bearer {token}"}

r = requests.post(f"{BASE}/auth/login",
    json={"email": "malo@test.com", "password": "wrong"})
check("Login inválido retorna 401", r.status_code == 401)

r = requests.get(f"{BASE}/auth/me", headers=headers)
check("GET /auth/me funciona", r.status_code == 200)
check("Rol admin correcto", r.json().get("rol") == "admin")

# 3. Protección endpoints
# FastAPI valida campos requeridos (file, JSON body) antes de ejecutar la función,
# así que hay que enviar un payload válido sin header Authorization para que llegue
# al check de auth y retorne 401.
print("\n3. Seguridad")
import io
dummy_csv = b"id,nombre\r\n1,Juan\r\n"
r = requests.post(f"{BASE}/upload",
    files={"file": ("dummy.csv", io.BytesIO(dummy_csv), "text/csv")})
check("POST /upload sin token → 401", r.status_code == 401)
r = requests.post(f"{BASE}/analyze",
    json={"file_id": "x", "id_column": "id", "columns_config": {"nombre": {"completitud": {}}}})
check("POST /analyze sin token → 401", r.status_code == 401)
for endpoint, method in [("/historial", "GET"), ("/admin/usuarios", "GET")]:
    r = requests.request(method, f"{BASE}{endpoint}")
    check(f"{method} {endpoint} sin token → 401", r.status_code == 401)

# 4. Upload — dataset 1000
print("\n4. Upload y Perfil (dataset_1000.csv)")
with open("tests/dataset_1000.csv", "rb") as f:
    r = requests.post(f"{BASE}/upload",
        files={"file": ("dataset_1000.csv", f, "text/csv")},
        headers=headers)
check("Upload CSV exitoso", r.status_code == 200, r.text[:200])
file_id = r.json().get("file_id", "")
columnas = r.json().get("columnas", [])
check("file_id recibido", bool(file_id))
check("Columnas detectadas correctamente", len(columnas) >= 10,
      f"detectadas: {len(columnas)}")

# 5. Perfil
t0 = time.time()
r = requests.get(f"{BASE}/profile/{file_id}", headers=headers)
t_perfil = time.time() - t0
check("Perfil generado", r.status_code == 200, r.text[:100])
perfil = r.json()
resumen = perfil.get("resumen", perfil)
total_filas = resumen.get("total_filas", perfil.get("total_filas", 0))
check("Perfil tiene total_filas=1000", total_filas == 1000,
      f"filas={total_filas}")
check("Perfil tiene columnas", len(perfil.get("columnas", {})) >= 10)
check("Perfil tiene alertas", "alertas" in resumen)
check(f"Perfil rápido (<10s)", t_perfil < 10, f"{t_perfil:.1f}s")

# 5b. Perfil Excel — debe llamarse ANTES de /analyze (que limpia _file_store)
print("\n9. Perfil Excel (antes del análisis)")
r = requests.get(f"{BASE}/profile/{file_id}/export", headers=headers)
check("Perfil Excel generado", r.status_code == 200, r.text[:100])

# 6. Sugerencias
print("\n5. Sugerencias de dimensiones")
r = requests.post(f"{BASE}/ai/suggest",
    json={"file_id": file_id}, headers=headers)
check("Sugerencias generadas", r.status_code == 200, r.text[:100])
body_sug = r.json()
# accept either "columnas" or "sugerencias" key
sugs = body_sug.get("sugerencias", body_sug.get("columnas", []))
check("Hay sugerencias para columnas", len(sugs) > 0)
if sugs:
    dims_primera = sugs[0].get("dimensiones", [])
    if dims_primera:
        check("Sugerencias tienen confianza", "confianza" in dims_primera[0])
        check("Sugerencias tienen razon", "razon" in dims_primera[0])
        altas = sum(1 for s in sugs for d in s.get("dimensiones", [])
                   if d.get("confianza") == "alta")
        check(f"Hay dimensiones con alta confianza ({altas})", altas > 0)

# 7. Análisis con todas las dimensiones principales
print("\n6. Análisis de calidad (11 dimensiones)")
config = {
    "file_id": file_id,
    "id_column": "cliente_id",
    "descripcion": "Prueba integral para presentación",
    "etiqueta": "Maestro",
    "columns_config": {
        "nombre": {
            "completitud": {},
            "precision": {"min_length": 2, "max_length": 100},
            "similitud": {"algoritmo": "jaro_winkler", "umbral": 92}
        },
        "email": {
            "completitud": {},
            "validez": {"regex_pattern": "^[a-zA-Z0-9_.+\\-\\u00C0-\\u024F]+@[a-zA-Z0-9\\-\\u00C0-\\u024F]+\\.[a-zA-Z0-9\\-.\\u00C0-\\u024F]+$"},
            "unicidad": {}
        },
        "edad": {
            "completitud": {},
            "exactitud": {"min_value": 0, "max_value": 120},
            "razonabilidad": {}
        },
        "estado_cliente": {
            "completitud": {},
            "validez": {"valid_values": ["Activo", "Inactivo", "Suspendido"]},
            "consistencia": {}
        },
        "fecha_registro": {
            "completitud": {},
            "vigencia": {"date_from": "2020-01-01", "date_to": "2025-12-31"},
            "consistencia": {}
        },
        "salario": {
            "completitud": {},
            "exactitud": {"min_value": 0, "max_value": 20000},
            "razonabilidad": {}
        }
    }
}
t0 = time.time()
r = requests.post(f"{BASE}/analyze", json=config, headers=headers)
t_analisis = time.time() - t0
check("Análisis completado", r.status_code == 200, r.text[:200])
resultado = r.json()
score = resultado.get("score_general", -1)
total_problemas = resultado.get("total_problemas", -1)
check("Score entre 0 y 100", 0 <= score <= 100, f"score={score}")
check("Score calculado correctamente", score > 0, f"score={score}")
check("Total problemas detectados", total_problemas > 0,
      f"problemas={total_problemas}")
check(f"Análisis rápido (<60s)", t_analisis < 60, f"{t_analisis:.1f}s")
print(f"     📊 Score: {score:.1f} | Problemas: {total_problemas} | Tiempo: {t_analisis:.1f}s")

# 8. Issues detallados
print("\n7. Problemas detallados")
r = requests.get(f"{BASE}/issues/{file_id}", headers=headers)
check("Issues retornados", r.status_code == 200)
issues = r.json().get("issues", [])
check("Issues no vacíos", len(issues) > 0, f"issues={len(issues)}")
if issues:
    check("Issues tienen id_registro", any(
        k in issues[0] for k in ['id_registro', 'cliente_id']),
        str(list(issues[0].keys())))
    check("Issues tienen dimension", "dimension" in issues[0])
    check("Issues tienen descripcion", "descripcion" in issues[0])
    check("Issues tienen valor_encontrado", "valor_encontrado" in issues[0])
    dims_en_issues = set(i.get("dimension", "") for i in issues)
    print(f"     📋 Dimensiones con problemas: {', '.join(sorted(dims_en_issues))}")
    check("Similitud aparece en issues",
          "similitud" in dims_en_issues,
          f"dimensiones: {dims_en_issues}")

# 9. Reporte Excel
print("\n8. Reporte Excel")
r = requests.get(f"{BASE}/report/{file_id}", headers=headers)
check("Reporte generado", r.status_code == 200, r.text[:100])
check("Es archivo Excel",
      "spreadsheet" in r.headers.get("content-type", "") or
      "octet" in r.headers.get("content-type", ""),
      r.headers.get("content-type", ""))
check("Tiene contenido", len(r.content) > 1000,
      f"tamaño={len(r.content)} bytes")

# 11. Historial
print("\n10. Historial")
r = requests.get(f"{BASE}/historial", headers=headers)
check("Historial retornado", r.status_code == 200)
raw = r.json()
historial = raw if isinstance(raw, list) else raw.get("analisis", [])
check("Análisis guardado en historial", len(historial) > 0)
if historial:
    ultimo = historial[0]
    check("Historial tiene score", "score_general" in ultimo)
    check("Historial tiene fecha", "fecha" in ultimo,
          f"campos disponibles: {list(ultimo.keys())}")
    check("Historial tiene nombre dataset", "nombre_archivo" in ultimo,
          f"campos disponibles: {list(ultimo.keys())}")

r = requests.get(f"{BASE}/historial/stats", headers=headers)
check("Stats del historial", r.status_code == 200)

# 12. Descarga desde historial
if historial:
    analisis_id = historial[0].get("id")
    if analisis_id:
        r = requests.get(f"{BASE}/historial/{analisis_id}/reporte",
                        headers=headers)
        check("Descarga reporte desde historial",
              r.status_code in [200, 404],
              f"status={r.status_code}")

# 13. Admin
print("\n11. Administración")
r = requests.get(f"{BASE}/admin/usuarios", headers=headers)
check("Lista usuarios admin", r.status_code == 200)
usuarios = r.json()
check("Admin en lista", any(u.get("email") == "admin@dqplatform.com"
                            for u in usuarios))

nuevo = {"email": "test_presentacion@demo.com",
         "password": "Demo123!", "nombre": "Usuario Demo",
         "rol": "usuario", "max_registros": 5000}
r = requests.post(f"{BASE}/admin/usuarios", json=nuevo, headers=headers)
check("Crear usuario demo", r.status_code in [200, 201])
demo_id = r.json().get("id") if r.status_code in [200, 201] else None

if demo_id:
    r = requests.post(f"{BASE}/auth/login",
        json={"email": "test_presentacion@demo.com",
              "password": "Demo123!"})
    check("Login usuario demo", r.status_code == 200)
    token_demo = r.json().get("token", "")
    headers_demo = {"Authorization": f"Bearer {token_demo}"}

    r = requests.get(f"{BASE}/admin/usuarios", headers=headers_demo)
    check("Usuario sin admin no accede a /admin/usuarios",
          r.status_code == 403)

    r = requests.delete(f"{BASE}/admin/usuarios/{demo_id}",
                        headers=headers)
    check("Eliminar usuario demo", r.status_code == 200)

# 14. Upload segundo archivo (prueba flujo múltiple)
print("\n12. Flujo múltiple — segundo análisis")
with open("tests/dataset_1000.csv", "rb") as f:
    r = requests.post(f"{BASE}/upload",
        files={"file": ("segundo_dataset.csv", f, "text/csv")},
        headers=headers)
check("Segundo upload exitoso", r.status_code == 200)
file_id2 = r.json().get("file_id", "")
check("Segundo file_id diferente al primero", file_id2 != file_id,
      f"ids: {file_id} vs {file_id2}")

r = requests.get(f"{BASE}/profile/{file_id2}", headers=headers)
check("Perfil segundo archivo generado", r.status_code == 200)
check("Perfil segundo archivo tiene datos",
      r.json().get("resumen", r.json()).get("total_filas", r.json().get("total_filas", 0)) > 0)

# 15. Logout
print("\n13. Logout")
r = requests.post(f"{BASE}/auth/logout", headers=headers)
check("Logout exitoso", r.status_code == 200)
r = requests.get(f"{BASE}/historial", headers=headers)
check("Token inválido post-logout", r.status_code == 401)

# RESUMEN FINAL
print("\n" + "="*50)
checks_ok = 40 - len(errores)
print(f"RESULTADO FINAL:")
print(f"  ✅ Todo correcto: {checks_ok} pruebas")
if errores:
    print(f"  ❌ Errores: {len(errores)}")
    for e in errores:
        print(f"     • {e}")
if advertencias:
    print(f"  ⚠️  Advertencias: {len(advertencias)}")
    for a in advertencias:
        print(f"     • {a}")
if not errores:
    print("\n🎉 SISTEMA LISTO PARA PRESENTACIÓN")
else:
    print("\n⚠️  HAY ERRORES — CORREGIR ANTES DE PRESENTAR")
print("="*50)
