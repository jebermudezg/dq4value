# Resultados de Calibración de Similitud — Cuatro Datasets
**Fecha:** 2026-08-13  
**Algoritmos evaluados:** brecha_afin, brecha_afin+normalizar, jaro_winkler, jaro_winkler+normalizar, qgrams, qgrams+normalizar, tfidf, tfidf+normalizar  
**Umbrales probados:** 70%, 74%, 78%, 82%, 86%, 90%, 94%  
**Métrica principal:** F1 = 2·P·R / (P+R) desde pares reconstruidos por `grupo_id`

---

## Dataset de Referencia — maestro_proveedores_1000

**Tipo de variación:** Sufijos, abreviaturas de razón social (S.A.C., S.R.L., LTDA., E.I.R.L.)  
**Filas:** 1,000 · **Pares reales:** ~82 (estimado)  
**Columna calibrada:** razon_social

| Algoritmo | Umbral | Precisión | Recall | F1 |
|-----------|--------|-----------|--------|----|
| **qgrams** | **86%** | **0.952** | **0.911** | **0.930** 🏆 |
| qgrams+normalizar | 86% | 0.940 | 0.898 | 0.919 |
| jaro_winkler | 94% | 0.871 | 0.780 | 0.823 |
| brecha_afin | 86% | 0.820 | 0.756 | 0.787 |
| tfidf | — | 0.000 | 0.000 | 0.000 |

**Ganador:** `qgrams @ 86%` — F1=0.930  
*Motivo: los sufijos (S.A.C. vs S.R.L.) son variaciones de q-grama bajas; qgrams resiste bien.*

---

## Dataset A — prueba_tipograficos_800

**Tipo de variación:** Errores de tipeo — transposición, carácter faltante, carácter duplicado, tecla adyacente  
**Filas:** 800 · **Pares reales:** 75  
**Columna calibrada:** nombre_completo

| Algoritmo | Umbral | Precisión | Recall | F1 | Tiempo |
|-----------|--------|-----------|--------|----|--------|
| **brecha_afin** | **86%** | **0.890** | **0.867** | **0.878** 🏆 | 6.3s |
| brecha_afin+normalizar | 86% | 0.844 | 0.867 | 0.855 | 8.6s |
| jaro_winkler | 96% | 0.979 | 0.627 | 0.764 | 0.07s |
| jaro_winkler+normalizar | 94% | 0.674 | 0.773 | 0.720 | 0.09s |
| qgrams | 78% | 0.929 | 0.173 | 0.292 | 0.17s |
| qgrams+normalizar | 78% | 0.923 | 0.160 | 0.273 | 0.17s |
| tfidf | — | 0.000 | 0.000 | 0.000 | 0.04s |

**Ganador:** `brecha_afin @ 86%` — F1=0.878  
*Motivo: la alineación local (Smith-Waterman style) absorbe transposiciones char-level mejor que q-gramas.*

---

## Dataset B — prueba_tokens_600

**Tipo de variación:** Tokens en distinto orden, palabras faltantes, abreviaturas de vía (Av. / Jirón / Jr.)  
**Filas:** 600 · **Pares reales:** 60  
**Columna calibrada:** direccion

| Algoritmo | Umbral | Precisión | Recall | F1 | Tiempo |
|-----------|--------|-----------|--------|----|--------|
| **brecha_afin+normalizar** | **92%** | **0.967** | **0.483** | **0.644** 🏆 | 20s |
| brecha_afin | 92% | 0.966 | 0.467 | 0.629 | 23s |
| qgrams | 78% | 0.875 | 0.117 | 0.206 | 0.26s |
| qgrams+normalizar | 78% | 0.833 | 0.083 | 0.152 | 0.24s |
| jaro_winkler | 94% | 0.037 | 0.017 | 0.023 | 0.15s |
| tfidf | — | 0.000 | 0.000 | 0.000 | 0.09s |

**Ganador:** `brecha_afin+normalizar @ 92%` — F1=0.644  
*Nota: Recall=48.3% — solo recupera la mitad de los pares reales porque tokens muy reordenados caen bajo el umbral de alineación. Punto de mejora futura: estrategia token-sort antes de la alineación.*

---

## Dataset C — prueba_limpio_500

**Tipo de variación:** Solo 3 pares reales (caso de control), sin ruido tipográfico  
**Filas:** 500 · **Pares reales:** 3  
**Columna calibrada:** nombre_producto

| Algoritmo | Umbral | Precisión | Recall | F1 |
|-----------|--------|-----------|--------|----|
| **brecha_afin** | **94%** | **0.750** | **1.000** | **0.857** 🏆 |
| brecha_afin+normalizar | 94% | 0.750 | 1.000 | 0.857 |
| qgrams | 82% | 0.008 | 0.667 | 0.015 |
| tfidf | — | 0.000 | 0.000 | 0.000 |

**Ganador:** `brecha_afin @ 94%` — F1=0.857  
*Umbral alto (94%) necesario para que qgrams no produzca falsos positivos masivos en datos limpios.*

---

## Tabla comparativa final — Ganadores por tipo de datos

| Dataset | Tipo de duplicado | Mejor algoritmo | Umbral óptimo | F1 |
|---------|-------------------|-----------------|---------------|----|
| maestro_proveedores_1000 | Sufijos/abreviaturas RS | qgrams | 86% | 0.930 |
| prueba_tipograficos_800 | Errores de tipeo | **brecha_afin** | **86%** | **0.878** |
| prueba_tokens_600 | Tokens desordenados | **brecha_afin+normalizar** | **92%** | **0.644** |
| prueba_limpio_500 | Pocos duplicados (control) | **brecha_afin** | **94%** | **0.857** |

---

## Decisiones de diseño derivadas

### 1. Default de algoritmo → `brecha_afin`
- Gana en 3 de 4 tipos de dataset (tipograficos, tokens, limpio)
- qgrams solo gana en razones sociales con sufijos — caso muy específico
- **Acción:** selector de similitud pone `brecha_afin ★` primero; qgrams segundo como alternativa rápida

### 2. Default de umbral → `90%`
- Promedio de los umbrales óptimos de brecha_afin en los 3 datasets donde gana: (86+92+94)/3 = **90.7% ≈ 90%**
- 90% es conservador: preferimos precisión sobre recall por defecto
- **Acción:** umbral default cambiado de 96% a 90% en `UMBRAL_DEFAULT_POR_ALGORITMO`

### 3. Motor de sugerencias (`ai/claude_analyzer.py`)
- Columnas de persona/nombre → `brecha_afin @ 86` (typos)
- Columnas de dirección/domicilio → `brecha_afin+normalizar @ 92` (tokens)
- Columnas con sufijos RS explícitos → `qgrams @ 86` (único caso donde qgrams gana)
- Default general → `brecha_afin @ 90`

### 4. `brecha_afin` removido de `ALGORITMOS_LENTOS`
- Era marcado como lento pero es ahora el default recomendado
- El aviso de lentitud aplica a `smith_waterman` y `coseno` (que sí son O(n²) sin paralelismo)

### 5. `tfidf/coseno` marcado como "solo textos largos"
- F1=0.000 en todos los datasets de nombres/direcciones (<10 tokens)
- Mantenido en código/API por compatibilidad pero marcado en UI: "solo para textos largos (>20 palabras) · no apto para nombres/RS"

---

## Nota metodológica

**Construcción de pares:** cada registro con `entidad_real_id = X` forma pares reales con todos los demás registros que tienen `entidad_real_id = X`. El motor de similitud genera pares con similitud ≥ umbral y los compara contra los pares reales.

**Métricas:**  
- Precisión = pares_correctos / pares_detectados  
- Recall = pares_correctos / pares_reales  
- F1 = 2·P·R / (P+R)

**Limitación:** datasets pequeños (500–800 filas) producen pocos pares reales, por lo que las métricas tienen alta varianza. Los resultados son orientativos, no estadísticamente robustos. Para producción se recomienda calibrar con el dataset real del cliente.
