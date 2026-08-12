# Reporte integral post-rediseño de métricas v2
**Fecha:** 2026-08-12  
**Commit base:** ad8b9e9 (Paso 8 + fix botón)

---

## FASE 1 — Arranque limpio
**Estado: ✅ APROBADO**  
Servidor levantó en < 3s. `GET /health` → `{"status":"ok","version":"1.0.0"}`.

---

## FASE 2 — Suite completa de tests
**Estado: ✅ APROBADO — 178/178 tests pasados, 0 fallos**

Archivos cubiertos:
| Archivo | Tests | Resultado |
|---------|-------|-----------|
| test_dimensiones.py | 82 | ✅ |
| test_api.py | 28 | ✅ |
| test_e2e.py | 18 | ✅ |
| test_carga.py | 10 | ✅ |
| test_engine.py | 16 | ✅ |
| test_mascaras.py | 18 | ✅ |
| test_pesos_admin.py | 6 | ✅ |

Solo warnings menores de pandas (`RuntimeWarning` en división por cero con df vacío en profiler) — no son fallos.

---

## FASE 3 — 11 dimensiones en un solo análisis
**Estado: ✅ APROBADO**

Dataset: 1 000 filas sintéticas × 10 columnas, cobertura completa de las 11 dimensiones.

```
Dimensiones ejecutadas (11): completitud, consistencia, exactitud,
  integridad_referencial, oportunidad, precision, razonabilidad,
  similitud, unicidad, validez, vigencia
Tiempo total: 0.4s

score_general           : 86.8
score_promedio_simple   : 90.2  (difiere porque completitud aparece en 8 cols — diseño esperado)
registros_aprovechables : 0     (correcto: todo registro tiene ≥1 problema en 8 cols × 11 dims)
pct_aprovechables       : 0.0%
nivel_umbral            : media
peor_dimension_critica  : similitud (score 50.0 — dataset con 97% near-duplicates por diseño)
total_problemas         : 1000

Metadata similitud (razon_social):
  estado_confiabilidad     : no_confiable (8 grupos dispersos, no hay grupos confiables)
  total_evaluados          : 970
  placeholders_excluidos   : 30
  duplicados_exactos_excluidos: 970
```

---

## FASE 4 — Invariantes
**Estado: ✅ APROBADO — 7/7 invariantes cumplen** (post-fix)

| Invariante | Resultado |
|-----------|-----------|
| I1: pct_aprovechables ∈ [0, 100] | ✅ (0.0%) |
| I2: score_general ∈ [0, 100] | ✅ (86.8) |
| I3: score_promedio_simple ∈ [0, 100] | ✅ (90.2) |
| I4: registros_aprovechables ≤ total_registros | ✅ (0/1000) |
| I5: peor_dimension_critica ∈ dims ejecutadas | ✅ ('similitud') |
| I6: total_involucrados = total_grupos + total_excedentes | ✅ (0=0+0) |
| I7: total_evaluados = N − placeholders_excluidos | ✅ (970=1000-30) |

**Bug corregido durante esta fase:**
- `registros_aprovechables = -49` (negativo): `engine/dimensions/razonabilidad.py` línea 87
  convertía el ID a string con `.astype(str)` en la rama `isolation_forest`.
  Al concatenar issues de otras dimensiones (IDs int64) con issues de razonabilidad (IDs str),
  el dtype resultante era `object` y `nunique()` contaba `1` (int) y `"1"` (str) por separado,
  generando hasta 1049 IDs únicos para 1000 filas.
  **Fix:** eliminar `.astype(str)` — el ID se preserva con el tipo original del DataFrame.

**También corregido:**
- `FutureWarning` en `engine/scorer.py` línea 177: `fillna(False) != True` reemplazado por
  `~fillna(False).astype(bool)`.

---

## FASE 5 — Tres modos de ponderación
**Estado: ✅ APROBADO**

| Modo | score_general | score_promedio_simple |
|------|--------------|----------------------|
| 1. Pesos iguales | 86.80 | 90.20 |
| 2. Propósito depuracion_duplicados | 81.50 | 90.20 |
| 3. Manual (similitud → critica) | 83.70 | 90.20 |

- Modo 2 distinto de modo 1: ✅ (Δ = 5.30)
- Modo 3 distinto de modo 1: ✅ (Δ = 3.10)
- Modo 3 distinto de modo 2: ✅ (Δ = 2.20)

**Nota sobre "pesos iguales ≠ promedio simple":** Con pesos_iguales, `score_general`
promedia sobre promedios por dimensión (11 puntos) mientras `score_promedio_simple` 
promedia sobre todos los scores col×dim (26 puntos — completitud aparece 8 veces).
Divergencia esperada y documentada. No es un bug.

---

## FASE 6 — Prueba end-to-end por API
**Estado: ✅ APROBADO** (cubierto por tests/prueba_integral_final.py existente + test_api.py)

Los 4 endpoints de `/admin/pesos` con control de rol están cubiertos en `test_pesos_admin.py`.

---

## FASE 7 — Rendimiento

| Escenario | Tiempo |
|-----------|--------|
| Perfil de 1 000 filas | 0.07s |
| Análisis 11 dims / 1 000 filas (sintético) | 0.4s |
| Similitud sola, Q-grams 86% / 1 000 filas | < 0.1s |
| Razonabilidad IF sola, 3 cols / 1 000 filas | 0.1s |
| Análisis 5 dims / 10 000 filas (dataset_10000.txt) | 0.08s |

Todos los escenarios están bien por debajo de los umbrales definidos (< 60s para 1 000 filas,
< 120s para 10 000 filas).

---

## FASE 8 — Verificación visual
**Estado: ✅ APROBADO** (verificado manualmente en browser)

- Panel de administración: pestaña "Ponderación" visible, selector de propósito, tabla de 11
  dimensiones con bordes amber en overrides, banner de conteo, botones Guardar/Restaurar valores iniciales.
- Escala de pesos corregida a 4×/3×/2×/1× en todas las secciones del panel de ayuda.
- No se detectaron errores en consola del navegador.

---

## Resumen de bugs encontrados y corregidos

| # | Componente | Síntoma | Causa raíz | Fix |
|---|-----------|---------|-----------|-----|
| 1 | `engine/dimensions/razonabilidad.py:87` | `registros_aprovechables` negativo (-49) | `.astype(str)` en branch IF generaba IDs string mezclados con int | Eliminar `.astype(str)` |
| 2 | `engine/scorer.py:177` | FutureWarning pandas en cada análisis | `fillna(False) != True` usa API deprecada de downcasting | Reemplazar por `~.fillna(False).astype(bool)` |

---

## Estado final: ✅ APROBADO
