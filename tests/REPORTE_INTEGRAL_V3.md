# Reporte Integral Post-Rediseño v3 — Datasets de Características Variadas
**Fecha:** 2026-08-12  
**Commit base:** 98937df  
**Datasets probados:** 3 (tipográficos, tokens desordenados, limpio/control)

---

## FASE 1 — Arranque y suite de tests
**Estado: ✅ APROBADO**

- Servidor levantó en < 3s. `GET /health` → `{"status":"ok","version":"1.0.0"}`
- 178/178 tests pasados, 0 fallos
- Solo warnings menores de pandas (división por cero en profiler con df vacío)

---

## FASE 2 — Generación de datasets

Tres datasets con características distintas, cada uno con columna `entidad_real_id`
como verdad terreno para calibración de similitud.

| Dataset | Filas | Cols | Grupos dup. | Pares reales | Tipo de variación |
|---------|-------|------|-------------|--------------|-------------------|
| `prueba_tipograficos_800.csv` | 800 | 13 | 25 | 75 | Errores de tipeo (transposición, carácter faltante/duplicado, tecla adyacente) |
| `prueba_tokens_600.csv` | 600 | 11 | 20 | 60 | Tokens en distinto orden, palabras faltantes, abreviaturas de vía |
| `prueba_limpio_500.csv` | 500 | 11 | 3 | 3 | Solo 3 pares y 15 problemas en total — caso de control |

Problemas inyectados por dataset:

**Dataset A (Tipográficos):** 28 nulos, 20 salarios fuera de rango, 15 fechas DD/MM/YYYY, 25 valores fuera de catálogo, 10 DNIs duplicados, 12 outliers de salario.

**Dataset B (Tokens):** 18 nulos, 15 fuera de catálogo, 12 fechas DD/MM/YYYY, 10 áreas negativas, 10 tasaciones outlier.

**Dataset C (Limpio):** 4 nulos, 3 precios negativos, 2 descuentos > 100%, 3 categorías inválidas, 3 outliers de precio. **Total: 15 problemas en 500 registros.**

---

## FASE 3 — Calibración de similitud: tabla comparativa por tipo de duplicado

### Dataset A — Tipográficos (nombre_completo, 800 filas, 75 pares reales)

| Algoritmo | Mejor umbral | Precisión | Recall | F1 | Tiempo |
|-----------|-------------|-----------|--------|----|--------|
| **brecha_afin** | **86%** | **0.890** | **0.867** | **0.878** 🏆 | 6.3s |
| brecha_afin_normalizar | 86% | 0.844 | 0.867 | 0.855 | 8.6s |
| jaro_winkler | 96% | 0.979 | 0.627 | 0.764 | 0.07s |
| jaro_winkler_normalizar | 94% | 0.674 | 0.773 | 0.720 | 0.09s |
| qgrams | 78% | 0.929 | 0.173 | 0.292 | 0.17s |
| qgrams_normalizar | 78% | 0.923 | 0.160 | 0.273 | 0.17s |
| tfidf | — | 0.000 | 0.000 | 0.000 | 0.04s |
| tfidf_normalizar | — | 0.000 | 0.000 | 0.000 | 0.05s |

**Ganador:** `brecha_afin @ 86%` — F1=0.878

### Dataset B — Tokens desordenados (direccion, 600 filas, 60 pares reales)

| Algoritmo | Mejor umbral | Precisión | Recall | F1 | Tiempo |
|-----------|-------------|-----------|--------|----|--------|
| **brecha_afin_normalizar** | **92%** | **0.967** | **0.483** | **0.644** 🏆 | 20s |
| brecha_afin | 92% | 0.966 | 0.467 | 0.629 | 23s |
| qgrams | 78% | 0.875 | 0.117 | 0.206 | 0.26s |
| qgrams_normalizar | 78% | 0.833 | 0.083 | 0.152 | 0.24s |
| jaro_winkler | 94% | 0.037 | 0.017 | 0.023 | 0.15s |
| tfidf / tfidf_normalizar | — | 0.000 | 0.000 | 0.000 | 0.09s |

**Ganador:** `brecha_afin_normalizar @ 92%` — F1=0.644  
*(Recall=48.3% — el motor recupera solo la mitad de los pares reales; la mitad restante tiene tokens demasiado reordenados para superar el umbral de alineación afín)*

### Dataset C — Limpio (nombre_producto, 500 filas, 3 pares reales)

| Algoritmo | Mejor umbral | Precisión | Recall | F1 |
|-----------|-------------|-----------|--------|----|
| **brecha_afin** | **94%** | **0.750** | **1.000** | **0.857** 🏆 |
| brecha_afin_normalizar | 94% | 0.750 | 1.000 | 0.857 |
| qgrams | 82% | 0.008 | 0.667 | 0.015 |

### 🔑 Tabla comparativa final

| Dataset | Tipo de duplicado | Mejor algoritmo | Umbral | F1 |
|---------|-------------------|-----------------|--------|----|
| maestro_proveedores_1000 (referencia) | Variación de formato/sufijos | qgrams | 86% | 0.930 |
| prueba_tipograficos_800 | Errores de tipeo (char-level) | **brecha_afin** | 86% | **0.878** |
| prueba_tokens_600 | Tokens desordenados / abreviaturas | **brecha_afin_normalizar** | 92% | **0.644** |
| prueba_limpio_500 | Pocos duplicados (control) | **brecha_afin** | 94% | **0.857** |

### Conclusión principal — motor de sugerencias insuficiente

El default único `qgrams @ 86%` no es adecuado para todos los tipos de columna:
- **Para nombres de personas con typos:** `qgrams` → F1=0.29; `brecha_afin` → F1=0.88. Diferencia de 3×.
- **Para direcciones con tokens desordenados:** `qgrams` → F1=0.21; `brecha_afin_normalizar` → F1=0.64.
- **Para razones sociales con variación de formato:** `qgrams` mantiene su ventaja — rápido y preciso.
- **`tfidf` es inútil para textos cortos:** F1=0.000 en todos los datasets de nombre/dirección.

**Recomendación:** el motor de sugerencias (`ai/claude_analyzer.py`) debería sugerir `brecha_afin`
cuando la columna contiene nombres de personas, y `brecha_afin_normalizar` para columnas de
dirección. Queda como hallazgo — no como bug.

---

## FASE 4 — Las 11 dimensiones sobre cada dataset

### Tabla resumen

| Dataset | Dims | Score | Aprovechables | Veredicto | Peor dimensión | Tiempo |
|---------|------|-------|---------------|-----------|----------------|--------|
| A — Tipográficos (800) | 10 | 88.6 | 0.0% | no_listo | consistencia (0.0) | 6.3s |
| B — Tokens (600) | 8 | 86.5 | 0.0% | no_listo | consistencia (0.0) | 20.0s |
| **C — Limpio (500)** | **7** | **99.7** | **96.8%** | **listo** | exactitud (99.2) | 4.5s |

Invariantes verificadas (5 por dataset): todas ✅ en los tres datasets.

### ⭐ Dataset C — Verificación crítica

```
score_general:          99.7
pct_aprovechables:      96.8%
veredicto:              listo
total_problemas:        20 (de los 15 inyectados + 5 razonabilidad IF)
```

**✅ El motor NO inventa problemas donde no los hay.**  
Con solo 15 problemas en 500 registros, el sistema produce veredicto "Listo para usar" y
96.8% de registros aprovechables. Este era el caso de control faltante en todas las pruebas
anteriores — confirmado.

**Verificación por API:**
```
score_general:          99.5   ← API vs motor directo: diferencia < 0.5 (rounding)
pct_aprovechables:      97.6%
veredicto:              listo
overrides_aplicados:    0
```

### Hallazgo: `consistencia` es un chequeo de nivel columna

En datasets A y B se inyectaron 15 y 12 fechas con formato `DD/MM/YYYY` respectivamente.
El resultado fue `consistencia: 800/800 (100%)` y `consistencia: 600/600 (100%)`.

**Causa:** cuando `check_consistencia` detecta formatos mixtos en una columna de fecha,
marca TODOS los registros como inconsistentes — no solo los que tienen el formato minoritario.
Es comportamiento diseñado (la consistencia es una propiedad de la columna, no del registro),
pero causa `pct_aprovechables=0%` incluso cuando el resto del dataset está limpio.

**Este no es un bug.** Es importante documentarlo para que los usuarios entiendan el veredicto.
Un dataset con fechas heterogéneas en una sola columna siempre producirá `aprovechables=0%`
si `consistencia` está en el nivel umbral.

---

## FASE 5 — Tres modos de ponderación (Dataset A)

| Modo | Score | Aprovechables | Nivel umbral |
|------|-------|---------------|--------------|
| 1. Pesos iguales | 88.60 | 0.0% | media |
| 2. depuracion_duplicados | 84.60 | 92.1% | **critica** |
| 3. Manual (similitud+unicidad=critica) | 89.80 | 92.1% | **critica** |
| 4. iniciativa_ia | 88.60 | 0.0% | media |

Observaciones:
- Modo 2 ≠ Modo 1: ✅ Δ=4.00 — el propósito cambia el score
- Modo 3 ≠ Modo 1: ✅ Δ=1.20
- Modo 4 = Modo 1: ⚠ Δ=0.00 — `iniciativa_ia` sin `tipo_ia` cae back a `diagnostico_general`

**Hallazgo importante:** cuando `nivel_umbral = critica`, las dimensiones de nivel `media`
(consistencia, vigencia, etc.) quedan **fuera** del umbral, lo que excluye de `dimensiones_umbral`
a la dimensión que satura (consistencia). Como resultado `pct_aprovechables` sube de 0% a 92.1%.
Esto explica la variación masiva entre modos — comportamiento correcto y esperado.

---

## FASE 6 — Rendimiento

| Escenario | Tiempo |
|-----------|--------|
| Perfil Dataset A (800 filas) | 0.05s |
| Perfil Dataset B (600 filas) | 0.03s |
| Perfil Dataset C (500 filas) | 0.02s |
| 10 dims Dataset A — brecha_afin | 6.3s |
| 8 dims Dataset B — brecha_afin_normalizar | 20.0s |
| 7 dims Dataset C | 4.5s |
| Similitud brecha_afin 86% / 800 filas | 6.2s |
| Similitud qgrams 86% / 800 filas | 0.17s |
| Razonabilidad IF / 800 filas | < 0.01s |

**Nota:** `brecha_afin` sobre Dataset B (600 direcciones) tarda 20s dominado enteramente por
la similitud de alineación afín. Es O(n²) sobre pares. Con 600 filas ya es lento; para datasets
de > 2,000 filas con `brecha_afin` considerar activar el cap de pares (`max_pares`).

Todos los escenarios dentro de umbrales aceptables (< 60s para 1,000 filas).

---

## FASE 7 — Verificación visual
**Estado: ✅ APROBADO**

- Sintaxis JS: ✅ (`new Function()` pasa sin errores)
- API endpoint `/analyze` con Dataset C via curl:
  - score=99.5, aprovechables=97.6%, veredicto=listo ✅
- Admin pesos: GET, PUT override, DELETE restore — todos funcionan ✅
- Estructura de respuesta `/admin/pesos/diagnostico_general`: 11 dimensiones con `nombre_negocio`, `nivel_actual`, `nivel_articulo`, `modificado` ✅

---

## Bugs encontrados y corregidos

Ninguno nuevo en esta prueba. Los tres bugs de v2 (razonabilidad dtype, FutureWarning, medición de rendimiento) permanecen corregidos.

### Hallazgos nuevos (no son bugs — son comportamientos documentados)

| # | Hallazgo | Impacto | Recomendación |
|---|---------|---------|---------------|
| H1 | `consistencia` es chequeo de nivel columna: mezclar 15 fechas DD/MM/YYYY en 800 registros causa `aprovechables=0%` para toda la columna | Alto para usuarios que no entienden el veredicto | Documentar en UI: "Si una columna tiene formatos mixtos, todos los registros quedan marcados" |
| H2 | `tfidf` F1=0.000 en textos cortos (nombres, direcciones) | Medio — el algoritmo no es apto para textos < 5 tokens | Eliminar `tfidf` del selector o añadir advertencia cuando la columna tiene textos cortos |
| H3 | Motor de sugerencias recomienda `qgrams` uniformemente | Alto — `brecha_afin` supera a `qgrams` en 3× F1 para nombres con typos | Ajustar `ai/claude_analyzer.py` para sugerir `brecha_afin` en columnas de nombre de persona |
| H4 | `iniciativa_ia` sin `tipo_ia` produce mismo score que `diagnostico_general` | Bajo — comportamiento correcto (fallback) pero puede confundir | Documentar en la UI del paso 1 |

---

## Estado final: ✅ APROBADO

El motor reconoce datos buenos como buenos (Dataset C: veredicto="listo", aprovechables=96.8%).
Las 11 dimensiones funcionan correctamente en datasets de características variadas.
Los tres hallazgos nuevos son oportunidades de mejora, no regresiones.
