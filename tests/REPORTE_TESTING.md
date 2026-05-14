# REPORTE DE TESTING — DQ4Value
**Fecha:** 2026-05-14  
**Plataforma:** DQ4Value v1.0.0  
**Python:** 3.9.6 · pytest 8.4.2

---

## Resumen ejecutivo

| Fase | Archivo | Tests | Resultado | Tiempo |
|------|---------|------:|-----------|--------|
| 1 — Unitarios del motor | `test_dimensiones.py` | 79 | ✅ 79 pasaron | 0.44 s |
| 2 — Integración API | `test_api.py` | 27 | ✅ 27 pasaron | 0.64 s |
| 3 — Carga y rendimiento | `test_carga.py` | 5 | ✅ 5 pasaron | 0.33 s |
| 4 — End-to-end | `test_e2e.py` | 4 | ✅ 4 pasaron | 0.69 s |
| **TOTAL** | | **115** | **✅ 115/115** | **~1 s** |

---

## FASE 1 — Tests unitarios del motor

### Cobertura por dimensión

| Dimensión | Tests | Casos cubiertos |
|-----------|------:|-----------------|
| completitud | 8 | happy, nulos parciales, todos nulos, df vacío, 1 registro |
| unicidad | 7 | happy, todos dup, parcial, df vacío, NaN como dup |
| validez | 8 | valid_values, regex, sin params, nulos no marcados |
| exactitud | 7 | rango numérico, reference_list, sólo min, nulos |
| razonabilidad | 7 | outliers extremos, sin variación, iqr_factor custom |
| precision | 7 | decimal_places, min/max_length, sin params |
| vigencia | 7 | date_from/to, obsolete_values, sin params |
| oportunidad | 6 | fechas recientes, fechas viejas, mixto |
| integridad_referencial | 6 | happy, refs rotas, sin reference_ids, nulos |
| consistencia | 8 | formatos fecha, capitalización, df vacío, regresión id_col |
| DQScorer (integración) | 8 | múltiples dims, rename consistencia, error paths |

### Hallazgos en esta fase
- Todos los tests pasaron en la primera ejecución tras la corrección del bug de `consistencia`.

---

## FASE 2 — Tests de integración API

### Endpoints cubiertos

| Endpoint | Test | Resultado |
|----------|------|-----------|
| `GET /health` | 200 + `status: ok` | ✅ |
| `POST /auth/login` — credenciales correctas | 200 + token | ✅ |
| `POST /auth/login` — contraseña incorrecta | 401 | ✅ |
| `POST /auth/login` — email inexistente | 401 | ✅ |
| `GET /auth/me` — con token | 200 + datos usuario | ✅ |
| `GET /auth/me` — sin token | 401 | ✅ |
| `POST /auth/logout` — token invalidado | 401 en siguiente req | ✅ |
| `POST /upload` — sin token | 401 | ✅ |
| `POST /upload` — con token + CSV | 200 + file_id | ✅ |
| `POST /upload` — formato no soportado | 400 | ✅ |
| `POST /analyze` — configuración válida | 200 + scores | ✅ |
| `POST /analyze` — file_id inexistente | 404 | ✅ |
| `POST /analyze` — sin token | 401 | ✅ |
| `GET /analyze/status/{id}` | 200 + pct/done | ✅ |
| `GET /report/{id}` — tras análisis | 200 + Excel | ✅ |
| `GET /report/{id}` — sin analizar | 400 | ✅ |
| `GET /report/{id}` — id inexistente | 404 | ✅ |
| `GET /admin/usuarios` — sin token | 401 | ✅ |
| `GET /admin/usuarios` — rol usuario | 403 | ✅ |
| `GET /admin/usuarios` — admin | 200 + lista | ✅ |
| `POST /admin/usuarios` — crear usuario | 200 + id | ✅ |
| `POST /admin/usuarios` — email duplicado | 400 | ✅ |
| `PUT /admin/usuarios/{id}` — actualizar nombre | 200 | ✅ |
| `PUT /admin/usuarios/{id}` — cambiar contraseña | 200 + login OK | ✅ |
| `PUT /admin/usuarios/{id}` — contraseña corta | 400 | ✅ |
| `DELETE /admin/usuarios/{id}` — auto-eliminación | 400 | ✅ |

---

## FASE 3 — Rendimiento

### Dataset 1,000 filas (real, con errores inyectados)

| Métrica | Valor |
|---------|-------|
| Registros | 1,000 |
| Dimensiones ejecutadas | 18 |
| Tiempo total | **0.025 s** |
| Registros/segundo | ~39,500 |
| Score general | 98.99 |
| Problemas detectados | 149 |

### Dataset 10,000 filas (generado)

| Métrica | Valor |
|---------|-------|
| Registros | 10,000 |
| Dimensiones ejecutadas | 9 |
| Tiempo total | **0.017 s** |
| Registros/segundo | ~586,000 |
| Score general | 97.03 |

### Tiempo por dimensión (n=1,000)

| Dimensión | Tiempo |
|-----------|-------:|
| completitud | 0.86 ms |
| unicidad | 0.73 ms |
| razonabilidad | 1.29 ms |
| validez | 0.91 ms |
| exactitud | 0.89 ms |
| vigencia | 1.72 ms |
| oportunidad | 1.59 ms |
| precision | 1.15 ms |
| consistencia | 2.98 ms _(más lenta — usa iterrows)_ |
| integridad_referencial | 1.15 ms |

> Todas las dimensiones superan con amplio margen el límite de 60 s exigido.

---

## FASE 4 — End-to-end

El flujo completo (login → upload 1,000 filas → análisis 5 cols × 3 dims → reporte Excel → logout) completó en < 1 s:

- Score general: **99.12**  
- Problemas detectados: **100**  
- Pestañas del Excel: Dashboard · Problemas Detallados · Score por Columna ✅  
- Token invalidado tras logout ✅

---

## Bugs encontrados y correcciones

### Bug 1 — `consistencia.py` usaba `id_col_value` en lugar de `id_col`

**Archivo:** `engine/dimensions/consistencia.py`  
**Síntoma:** El `issues_df` retornado por `check_consistencia` tenía columna `id_col_value`
cuando había problemas, pero `id_col` cuando no los había. Esto causaba inconsistencia
con todas las otras dimensiones y fallaba en el test de regresión de columnas estándar.  
**Causa raíz:** La función helper `_issue()` hardcodeaba el key `"id_col_value"` en lugar
de usar el nombre dinámico del parámetro `id_col`.  
**Corrección:** Agregar parámetro `id_col_name` a `_issue()` y usar `{id_col_name: id_val}`
como key del diccionario. Actualizar también el `drop_duplicates(subset=[id_col])`.

### Bug 2 — Login eliminaba TODAS las sesiones activas del usuario

**Archivo:** `api/main.py` — endpoint `POST /auth/login`  
**Síntoma:** Al hacer login una segunda vez con el mismo usuario (e.g. desde otro test),
se invalidaban todos los tokens existentes del usuario, incluyendo los del fixture `admin_token`.
Esto causaba cascada de errores 401 en los tests de integración.  
**Causa raíz:** `DELETE FROM sesiones WHERE usuario_id = ?` eliminaba *todas* las sesiones,
no solo las expiradas.  
**Corrección:** Cambiar a `DELETE FROM sesiones WHERE usuario_id = ? AND fecha_expiracion <= ?`
para eliminar solo las sesiones expiradas y preservar las activas.

### Bug 3 (menor) — FutureWarning en pd.concat con columnas all-NA

**Archivo:** `engine/scorer.py`  
**Síntoma:** Warning de pandas al concatenar issues_df cuando `valor_encontrado` es
todo-None (como en `completitud`).  
**Corrección:** Castear explícitamente `df["valor_encontrado"].astype(object)` antes del
`pd.concat` para mantener dtype consistente.

---

## Casos edge pendientes / notas

1. **`consistencia` usa `iterrows()`** — es la dimensión más lenta. Para datasets > 100k filas
   podría convertirse en cuello de botella. Candidato a refactorizar con operaciones vectorizadas.

2. **Tokens de sesión** — con la corrección del Bug 2, las sesiones expiradas se limpian al
   hacer login. Para producción considerar un job periódico de limpieza de sesiones antiguas.

3. **Timeout de dimensiones** — el `DIMENSION_TIMEOUT = 30s` en `scorer.py` se probó
   implícitamente pero no hay un test unitario que verifique el comportamiento de timeout
   (requeriría inyectar una dimensión que tarde >30s).

4. **Tests con `pytest-anyio`** — los endpoints `async def` se prueban via `TestClient`
   (síncrono). Si en el futuro se necesitan tests de concurrencia real, añadir `anyio` como
   dependencia de testing.
