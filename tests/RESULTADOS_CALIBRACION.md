# Resultados de Calibración — Dimensión Similitud

**Dataset:** `tests/maestro_proveedores_1000.csv`  
**Registros:** 1 000  
**Pares verdaderos (mismo RUC):** 38  
**Grupos verdaderos:** 15  
**Fecha:** 2026-08-04

**Alcance:** Solo variaciones de formato del mismo nombre (sufijos societarios como "S.A.C." vs "SAC",
tildes, mayúsculas, abreviaturas como "Repres.", "Exportac."). Errores tipográficos, reordenamientos
de palabras o palabras faltantes no están representados — para esos casos pueden favorecer otros
algoritmos. Un F1 perfecto aquí es señal de ajuste óptimo al tipo de dato, pero puede no generalizar
a otros tipos de variación.

---

## Tabla resumen — mejor umbral confiable por algoritmo

| Algoritmo       | Umbral | Precisión | Recall | F1    | Estado    | Tiempo/1k | Notas |
|----------------|--------|-----------|--------|-------|-----------|-----------|-------|
| qgrams          |   86%  |  100.0%   |  86.8% | 0.930 | confiable |   0.9 s   | ★ **Default recomendado** |
| smith_waterman  |   94%  |  100.0%   |  86.8% | 0.930 | confiable | 436 s   ⚠ | Mismo F1; muy lento |
| monge_elkan     |   96%  |   83.7%   |  94.7% | 0.889 | confiable |   6.7 s   | Precisión < 100% → no default |
| levenshtein     |   92%  |   91.2%   |  81.6% | 0.861 | confiable |   5.2 s   | Precisión < 100% → no default |
| jaro_winkler    |   96%  |   75.0%   |  86.8% | 0.805 | confiable |   2.7 s   | Precisión < 100% → no default |
| brecha_afin     |   96%  |  100.0%   |  94.7% | 0.973 | confiable |  28.6 s ⚠ | Ver sección abreviaturas |
| soundex         |   86%  |   92.3%   |  31.6% | 0.471 | confiable |   2.8 s   | No recomendado para RS |
| coseno TF-IDF   |   78%  |  100.0%   |  23.7% | 0.383 | confiable | 337 s   ⚠ | No recomendado para RS |

---

## Decisión de default — criterio explícito

**Requisito 1 — Precisión = 100%** (un FP lleva al analista a fusionar dos empresas distintas).  
Algoritmos que pasan: qgrams@86, smith_waterman@94, brecha_afin@96, coseno@78, levenshtein@96, jaro_winkler@96.  
Monge-Elkan, levenshtein@92, jaro_winkler@96 no alcanzan P=100% en sus mejores umbrales → descartados.

**Requisito 2 — Mayor recall entre los que cumplen P=100%.**  
brecha_afin@96: R=94.7% > qgrams@86: R=86.8% → brecha_afin ganaría... pero:

**Regla 4 — Si la alternativa es > 20× más lenta Y la diferencia de recall es < 15 pts: elegir el rápido.**
- Δrecall = 94.7% − 86.8% = **7.9 pts** < 15 pts ✓
- Velocidad: 28.6s / 0.9s = **31.8×** > 20× ✓
- **→ qgrams@86 es el default.**

**Nota de sobreajuste en brecha_afin@94:** a umbral 94% obtiene F1=1.000 (P=100%, R=100%). Un F1
perfecto en calibración indica que el umbral está ajustado exactamente al dataset. Se prefiere 96%
como default de brecha_afin: P=100%, R=94.7%, F1=0.973 — menos ajustado y con el mismo cero de
falsos positivos.

---

## Brecha Afín — pre y post corrección de blocking

El blocking original tenía dos bugs que descartaban pares con diferencias de longitud grandes:
1. Cota de 15 000 pares ordenados por diferencia de longitud ascendente (descartaba pares con abreviaturas)
2. Early-return en `_brecha_afin` si ratio < 0.4 (bloqueaba casos extremos como "Repres." solo)

**Pares candidatos en dataset 1k:**
- Raw total generado por blocking: 60 333 pares
- Antes del fix: truncado a 15 000 por cota de longitud → se descartaban 45 333 pares con abreviaturas
- Post-fix: ratio_minimo=0.25, sin truncación por longitud → se comparan los 60 333 pares

### Antes de la corrección

| Umbral | Precisión | Recall | F1    | Tiempo |
|--------|-----------|--------|-------|--------|
|   86%  |   56.7%   |  44.7% | 0.500 |  ~8.6s |
|   90%  |   81.0%   |  44.7% | 0.576 |  ~8.6s |
|   92%  |   94.4%   |  44.7% | 0.607 |  ~8.6s |
|   94%  |  100.0%   |  44.7% | 0.618 |  ~8.6s |

Recall estancado en 44.7%: los pares con abreviaturas eran descartados antes de la comparación.

### Después de la corrección

| Umbral | Precisión | Recall | F1    | Tiempo |
|--------|-----------|--------|-------|--------|
|   86%  |   47.5%   | 100.0% | 0.644 | 28.6s  |
|   90%  |   79.2%   | 100.0% | 0.884 | 28.6s  |
|   92%  |   90.5%   | 100.0% | 0.950 | 28.6s  |
|   94%  |  100.0%   | 100.0% | 1.000 | 28.6s  | ← sobreajuste sospechoso |
| **96%**|**100.0%** | **94.7%**|**0.973**|**28.6s**| ← default elegido |

**Recall saltó de 44.7% → 94.7–100.0%.** Los 3 pares de abreviatura verificados:
- "Repres. del Pacifico S.A.C." vs "Representaciones…" → **96.2%** ✅
- "Dist. del Sur S.A.C." vs "Distribuidora…" → **95.0%** ✅
- "Inv. San Marcos E.I.R.L." vs "Inversiones…" → **96.1%** ✅

### Escalamiento

| Dataset       | Valores únicos | Pares candidatos | qgrams@86 | brecha_afin@96 |
|---------------|---------------|-----------------|-----------|----------------|
| 1 000 filas   | ~1 000        | 60 333          | 0.9 s     | 28.6 s         |
| 5 000 filas*  | ~1 000        | 60 333          | 0.3 s     | 29.6 s         |

*Dataset duplicado 5× — mismos valores únicos, solo más registros por valor. El tiempo de brecha_afin
escala sobre valores únicos (pair comparison), no sobre registros totales. Con 5 000 registros
verdaderamente diversos el cap de 50 000 pares limitaría el tiempo a ~23s adicionales de comparación.
brecha_afin se mantiene bajo el umbral de 120s para este tipo de dato.

---

## Monge-Elkan — post-fix (blocking con ratio_minimo = 0.25)

| Umbral | Precisión | Recall | F1    | Grupos | Disp. | Estado    |
|--------|-----------|--------|-------|--------|-------|-----------|
|   86%  |    7.1%   |  28.9% | 0.113 |     78 |    27 | no_conf.  |
|   90%  |   29.7%   | 100.0% | 0.458 |     67 |     1 | parcial   |
|   92%  |   47.5%   | 100.0% | 0.644 |     38 |     0 | confiable |
|   94%  |   74.5%   | 100.0% | 0.854 |     22 |     0 | confiable |
| **96%**|  **83.7%**|**94.7%**|**0.889**|16  |     0 | **confiable** |

Pre-fix: F1=0.867 (P=80%, R=94.7%). Post-fix: F1=0.889 (P=83.7%, R=94.7%).  
Mejora marginal. Monge-Elkan no alcanza P=100% en ningún umbral de este dataset → no cumple
el requisito de default. Útil cuando se toleran algunos falsos positivos a cambio de recall alto.

---

## Coherencia motor de sugerencias ↔ frontend

| Caso | `claude_analyzer.py` | Frontend ★ | Umbral sugerido |
|------|---------------------|-----------|-----------------|
| RS sin abreviaturas | `qgrams` | `qgrams ★` | 86% |
| RS con abreviaturas explícitas | `brecha_afin` | `brecha_afin ⚠` | 96% |

✓ Coherentes: el motor sugiere qgrams como default, la UI lo marca con ★. Brecha Afín lleva
⚠ (algoritmo lento) porque qgrams es el default — no hay contradicción.

---

## Defaults finales en `UMBRAL_DEFAULT_POR_ALGORITMO`

```javascript
const UMBRAL_DEFAULT_POR_ALGORITMO = {
  qgrams:         86,   // F1=0.930, P=100%, R=86.8%  ★ default RS
  jaro_winkler:   96,   // F1=0.805
  monge_elkan:    96,   // F1=0.889  (P<100%)
  levenshtein:    92,   // F1=0.861  (P<100%)
  brecha_afin:    96,   // P=100% R=94.7%  (94% sobreajustado)
  smith_waterman: 94,   // F1=0.930  ⚠ lento
  soundex:        86,   // F1=0.471  no recomendado RS
  coseno:         78,   // F1=0.383  ⚠ lento, no recomendado RS
};
```
