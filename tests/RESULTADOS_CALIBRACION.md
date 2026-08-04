# Resultados de Calibración — Dimensión Similitud

**Dataset:** `tests/maestro_proveedores_1000.csv`  
**Registros:** 1 000  
**Pares verdaderos (mismo RUC):** 38  
**Grupos verdaderos:** 15  
**Fecha:** 2026-08-04

**Alcance:** Solo variaciones de formato del mismo nombre (sufijos societarios como "S.A.C." vs "SAC", tildes, mayúsculas, abreviaturas como "Repres.", "Exportac.").  
Errores tipográficos, reordenamientos de palabras o palabras faltantes no están representados en este dataset — para esos casos pueden favorecer otros algoritmos.

---

## Tabla resumen — mejor umbral confiable por algoritmo

| Algoritmo       | Umbral | Precisión | Recall | F1    | Estado    | Tiempo (1k) | Notas |
|----------------|--------|-----------|--------|-------|-----------|-------------|-------|
| qgrams          |   86%  |  100.0%   |  86.8% | 0.930 | confiable |   6 s       | ★ Mejor para razones sociales |
| smith_waterman  |   94%  |  100.0%   |  86.8% | 0.930 | confiable | 436 s       | Mismo F1 que Q-grams; muy lento |
| monge_elkan     |   96%  |   80.0%   |  94.7% | 0.867 | confiable |   9 s       | Mejor recall, algo de FP |
| levenshtein     |   92%  |   91.2%   |  81.6% | 0.861 | confiable |   5 s       | Rápido y preciso |
| jaro_winkler    |   96%  |   75.0%   |  86.8% | 0.805 | confiable |   3 s       | Para nombres cortos/personas |
| brecha_afin     |   94%  |  100.0%   | 100.0% | 1.000 | confiable | 200 s       | ★ Perfecto para abreviaturas; ver nota |
| soundex         |   86%  |   92.3%   |  31.6% | 0.471 | confiable |   3 s       | No recomendado para RS |
| coseno TF-IDF   |   78%  |  100.0%   |  23.7% | 0.383 | confiable | 337 s       | No recomendado para RS |

---

## Brecha Afín — calibración pre y post corrección de blocking

El blocking original usaba una cota de 15 000 pares ordenados por diferencia de longitud (ascendente), lo que descartaba pares con diferencias de longitud grandes — exactamente las abreviaturas.

### Antes de la corrección (blocking con cota por longitud)

| Umbral | Precisión | Recall | F1    | Grupos | Disp. | Score | Estado    |
|--------|-----------|--------|-------|--------|-------|-------|-----------|
|   78%  |   12.6%   |  44.7% | 0.197 |     94 |     6 |  88.7 | parcial   |
|   82%  |   23.9%   |  44.7% | 0.312 |     54 |     1 |  93.8 | parcial   |
|   86%  |   56.7%   |  44.7% | 0.500 |     22 |     0 |  97.4 | confiable |
|   90%  |   81.0%   |  44.7% | 0.576 |     13 |     0 |  98.3 | confiable |
|   92%  |   94.4%   |  44.7% | 0.607 |     10 |     0 |  98.6 | confiable |
|   94%  |  100.0%   |  44.7% | 0.618 |      9 |     0 |  98.7 | confiable |

Recall estancado en 44.7%: los pares con abreviaturas ("Repres." vs "Representaciones") eran descartados antes de la comparación.

### Después de la corrección (ratio_minimo = 0.25, sin cota por longitud)

| Umbral | Precisión | Recall | F1    | Grupos | Disp. | Score | Estado    |
|--------|-----------|--------|-------|--------|-------|-------|-----------|
|   78%  |   14.8%   |  92.1% | 0.255 |    123 |    26 |  82.5 | parcial   |
|   82%  |   23.8%   | 100.0% | 0.384 |     93 |     7 |  87.5 | parcial   |
|   86%  |   47.5%   | 100.0% | 0.644 |     53 |     0 |  93.4 | confiable |
|   90%  |   79.2%   | 100.0% | 0.884 |     23 |     0 |  96.5 | confiable |
|   92%  |   90.5%   | 100.0% | 0.950 |     19 |     0 |  97.0 | confiable |
|   94%  |  **100.0%** | **100.0%** | **1.000** | 15 | 0 | 97.4 | **confiable** |
|   96%  |  100.0%   |  94.7% | 0.973 |     13 |     0 |  97.6 | confiable |

**Recall saltó de 44.7% → 100.0%. F1 de 0.618 → 1.000.** Todos los pares verdaderos detectados.  
Tiempo: ~200s/1000 registros (~3.3 min). Para >5000 registros puede tardar 30+ min.

Verificación directa de pares con abreviatura:

| Par | Score Brecha Afín | ¿Supera umbral 94%? |
|-----|-------------------|---------------------|
| "Representaciones del Pacifico S.A.C." vs "Repres. del Pacifico S.A.C." | 96.2 | ✅ |
| "Distribuidora del Sur S.A.C." vs "Dist. del Sur S.A.C." | 95.0 | ✅ |
| "Inversiones San Marcos E.I.R.L." vs "Inv. San Marcos E.I.R.L." | 96.1 | ✅ |

---

## Defaults calibrados (frontend)

```javascript
const UMBRAL_DEFAULT_POR_ALGORITMO = {
  jaro_winkler:   96,   // F1=0.805
  brecha_afin:    94,   // F1=1.000 post-fix (200s/1000 rows)
  monge_elkan:    96,   // F1=0.867
  levenshtein:    92,   // F1=0.861
  qgrams:         86,   // F1=0.930 ★
  smith_waterman: 94,   // F1=0.930 (lento ~436s/1000 rows)
  soundex:        86,   // F1=0.471 (no recomendado para RS)
  coseno:         78,   // F1=0.383 (no recomendado para RS, lento ~337s/1000 rows)
};
```

---

## Notas metodológicas

- **Verdad terreno:** pares de registros que comparten el mismo RUC (campo `ruc` del dataset).
- **Precisión:** fracción de pares detectados que son verdaderos positivos.
- **Recall (Exhaustividad):** fracción de pares verdaderos que fueron detectados.
- **F1:** media armónica de precisión y recall.
- **Estado "confiable":** ningún grupo disperso excluido del score (densidad interna ≥ 0.6).
- **Grupos dispersos:** grupos con densidad < UMBRAL_DENSIDAD=0.6 — probablemente encadenamiento transitivo, excluidos del score de calidad.
- Los tiempos son aproximados para 1 000 registros en hardware de desarrollo (Apple Silicon M-series).
- Para datasets > 5 000 registros, smith_waterman y coseno pueden tardar proporciones cuadráticas.
