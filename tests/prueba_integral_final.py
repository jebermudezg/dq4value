import requests, time, json

BASE = "http://127.0.0.1:8000"
errores = []

def ok(n): print(f"  ✅ {n}")
def fail(n, d=""): print(f"  ❌ {n} — {d}"); errores.append(n)
def check(n, c, d=""): ok(n) if c else fail(n, d)

print("\n=== PRUEBA INTEGRAL FINAL ===\n")

# Auth
print("1. Autenticación")
r = requests.post(f"{BASE}/auth/login", json={"email":"admin@dqplatform.com","password":"Admin123!"})
check("Login admin", r.status_code==200)
token = r.json().get("token","")
h = {"Authorization": f"Bearer {token}"}

# Upload
print("\n2. Upload")
with open("tests/dataset_1000.csv","rb") as f:
    r = requests.post(f"{BASE}/upload", files={"file":("dataset_1000.csv",f,"text/csv")}, headers=h)
check("Upload CSV", r.status_code==200, r.text[:100])
fid = r.json().get("file_id","")
check("file_id recibido", bool(fid))

# Perfil
print("\n3. Perfil")
r = requests.get(f"{BASE}/profile/{fid}", headers=h)
check("Perfil generado", r.status_code==200)
perfil = r.json()
total_filas = perfil.get("total_filas") or perfil.get("resumen",{}).get("total_filas",0)
check("1000 registros", total_filas==1000, str(total_filas))
check("Tiene columnas", len(perfil.get("columnas",{}))>0)
alertas_key = "alertas" in perfil or "alertas" in perfil.get("resumen",{})
check("Tiene alertas", alertas_key)

# Sugerencias
print("\n4. Sugerencias")
r = requests.post(f"{BASE}/ai/suggest", json={"file_id":fid}, headers=h)
check("Sugerencias generadas", r.status_code==200)
body = r.json()
sugs = body.get("columnas", body.get("sugerencias", []))
check("Hay sugerencias", len(sugs)>0)
if sugs and sugs[0].get("dimensiones"):
    check("Tiene campo confianza", "confianza" in sugs[0]["dimensiones"][0])
    check("Tiene campo razon", "razon" in sugs[0]["dimensiones"][0])

# Análisis completo
print("\n5. Análisis")
config = {
    "file_id": fid, "id_column": "cliente_id",
    "descripcion": "Prueba integral final", "etiqueta": "Maestro",
    "columns_config": {
        "nombre": {"completitud":{},"similitud":{"algoritmo":"jaro_winkler","umbral":92}},
        "email": {"completitud":{},"validez":{"regex_pattern":"^[\\w.+-]+@[\\w-]+\\.[\\w.]+$"}},
        "edad": {"completitud":{},"exactitud":{"min_value":0,"max_value":120},"razonabilidad":{}},
        "estado_cliente": {"completitud":{},"validez":{"valid_values":["Activo","Inactivo","Suspendido"]},"consistencia":{}},
        "fecha_registro": {"completitud":{},"vigencia":{"date_from":"2020-01-01","date_to":"2025-12-31"}},
        "salario": {"completitud":{},"razonabilidad":{}}
    }
}
t0 = time.time()
r = requests.post(f"{BASE}/analyze", json=config, headers=h)
t = time.time()-t0
check("Análisis completado", r.status_code==200, r.text[:200])
res = r.json()
score = res.get("score_general",-1)
problemas = res.get("total_problemas",-1)
check("Score entre 0-100", 0<=score<=100, f"score={score}")
check("Hay problemas detectados", problemas>0, f"problemas={problemas}")
check(f"Tiempo <60s", t<60, f"{t:.1f}s")
print(f"     Score: {score:.1f} | Problemas: {problemas} | Tiempo: {t:.1f}s")

# Issues
print("\n6. Issues detallados")
r = requests.get(f"{BASE}/issues/{fid}", headers=h)
check("Issues retornados", r.status_code==200)
issues = r.json().get("issues",[])
check("Issues no vacíos", len(issues)>0, f"count={len(issues)}")
if issues:
    check("Tiene id_registro", any(k in issues[0] for k in ["id_registro","cliente_id"]))
    check("Tiene dimension", "dimension" in issues[0])
    check("Tiene descripcion", "descripcion" in issues[0])
    dims = set(i.get("dimension","") for i in issues)
    check("Similitud en issues", "similitud" in dims, str(dims))
    print(f"     Dimensiones con problemas: {', '.join(sorted(dims))}")

# Reporte Excel
print("\n7. Reporte Excel")
r = requests.get(f"{BASE}/report/{fid}", headers=h)
check("Reporte generado", r.status_code==200)
check("Es Excel", "spreadsheet" in r.headers.get("content-type","") or "octet" in r.headers.get("content-type",""))
check("Tiene contenido", len(r.content)>1000, f"bytes={len(r.content)}")

# Dashboard HTML
print("\n8. Dashboard HTML")
r = requests.get(f"{BASE}/historial", headers=h)
check("Historial retornado", r.status_code==200)
hist = r.json() if isinstance(r.json(),list) else r.json().get("analisis",[])
check("Análisis en historial", len(hist)>0)
if hist:
    aid = hist[0].get("id")
    r = requests.get(f"{BASE}/historial/{aid}/dashboard", headers=h)
    check("Dashboard HTML generado", r.status_code in [200,404], f"status={r.status_code}")
    if r.status_code==200:
        check("Es HTML", "text/html" in r.headers.get("content-type",""))
        check("Contiene DQ4Value", "DQ4Value" in r.text)
        check("Sin interpretación automática", "Análisis de resultados" not in r.text)
        check("Sin donut chart canvas", 'id="dqDonut"' not in r.text)
        check("Sin badges de escala", "80 Buena" not in r.text and "Atenci" not in r.text.replace("atenci","X"))
        check("Paleta ámbar unificada", "#D97706" not in r.text and "#FEF9C3" not in r.text)
        check("Barras de issues presentes", "issuesBars" in r.text or "Distribuci" in r.text)

# Historial stats
print("\n9. Historial stats")
r = requests.get(f"{BASE}/historial/stats", headers=h)
check("Stats retornados", r.status_code==200)

# Segundo análisis
print("\n10. Segundo análisis")
with open("tests/dataset_1000.csv","rb") as f:
    r = requests.post(f"{BASE}/upload", files={"file":("segundo.csv",f,"text/csv")}, headers=h)
check("Segundo upload exitoso", r.status_code==200)
fid2 = r.json().get("file_id","")
check("file_id diferente", fid2!=fid, f"{fid} vs {fid2}")
r = requests.get(f"{BASE}/profile/{fid2}", headers=h)
check("Perfil segundo archivo", r.status_code==200)
tf2 = r.json().get("total_filas") or r.json().get("resumen",{}).get("total_filas",0)
check("Datos del segundo archivo", tf2>0, str(tf2))

# Admin
print("\n11. Administración")
r = requests.get(f"{BASE}/admin/usuarios", headers=h)
check("Lista usuarios", r.status_code==200)
check("Admin en lista", any(u.get("email")=="admin@dqplatform.com" for u in r.json()))

# Logout
print("\n12. Logout")
r = requests.post(f"{BASE}/auth/logout", headers=h)
check("Logout exitoso", r.status_code==200)
r = requests.get(f"{BASE}/historial", headers=h)
check("Token inválido post-logout", r.status_code==401)

# Resumen
total = 36
passed = total - len(errores)
print(f"\n{'='*45}")
print(f"RESULTADO: {passed}/{total} pruebas pasadas")
if errores:
    print(f"❌ {len(errores)} ERRORES ENCONTRADOS:")
    for e in errores: print(f"   • {e}")
    print("\nCorrige todos los errores antes de continuar.")
else:
    print("🎉 TODAS LAS PRUEBAS PASARON — SISTEMA LISTO")
print('='*45)
