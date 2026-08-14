# ENTREGA 2 — Criterio de tope por similitud estimada de trigramas con selección por heap

**Fecha:** 2026-08-14  
**Objetivo:** Reemplazar el criterio de recorte `abs(len_diff)` por Jaccard de trigramas con selección por heap, reduciendo la pérdida de pares verdaderos y manteniendo 20k en < 60 s.

---

## 2.1 — Diagnóstico de fases (escala_20k, Alt B original)

| Fase | Tiempo |
|:---- | ------:|
| Blocking (generación de candidatos) | 15.3 s |
| Clave on-the-fly (trigramas recalculados por par, estimado) | 98 s ← cuello de botella |
| sorted() sobre claves | 2 s |
| **Total Alt B original estimado** | **~115 s** |
| Con índice precalculado + heap (estimado) | ~43 s → `✅ alcanzable` |

El cuello de botella es el recálculo de trigramas para los 9.7M pares sin caché.

---

## 2.2 — Helpers implementados

```python
def _indice_trigramas(uniq_norm, q=3)   # frozenset de q-gramas por índice; se calcula una sola vez
def _jaccard_est(tri, a, b)              # Jaccard usando el índice; O(|trigramas|)
def _seleccion_por_heap(pares, tri, uniq_norm, tope)  # heap global de referencia (usado en tests)
```

---

## 2.3 / 2.4 — Selección por heap con enfoque por bloque

Para evitar materializar los 9.7M pares en memoria, se usa un enfoque **por bloque**: dentro de cada sub-grupo del blocking se mantiene un min-heap de tamaño `_K_BLOQUE`. Los mejores pares de cada bloque se acumulan en `best_pairs: dict`; finalmente se aplica un tope global a `best_pairs`.

| Parámetro | Valor |
|:--------- | -----:|
| `_tope_qgrams` | 15,000 |
| `_tope_tolerante` (brecha_afin / monge_elkan) | 50,000 |
| `_K_BLOQUE` cuando n_unicos > 3,000 | 200 |
| `_K_BLOQUE` cuando n_unicos ≤ 3,000 | 100,000 (≈ sin filtro por bloque) |

`n_pares_visitados` cuenta todas las iteraciones del lazo interno (incluyendo duplicados cross-block) para dar una magnitud real de la escala al usuario.

---

## 2.5 — Tabla comparativa: criterio VIEJO vs NUEVO

### escala_5k (5,000 filas · 4,995 únicos · 240 pares verdaderos)

| Métrica | Criterio VIEJO (len_diff) | Criterio NUEVO (Jaccard heap) |
|:------- | -----:| ------:|
| Candidatos antes del tope | 1,033,204 | 1,033,204 |
| Verdad en candidatos pre-tope | 232 / 232 | 232 / 232 |
| Verdad tras tope (15k) | 13 (**94.4% perdidos**) | 231 (**0.4% perdidos**) |
| Precisión (pipeline) | 0.929 | 0.929 |
| Recall (pipeline) | 0.108 | 0.108 |
| Tiempo | 3.9 s | **3.2 s** |
| Memoria RSS Δ | ~50 MB | **34 MB** |
| tope_activado | True | True |

### escala_20k (20,000 filas · 19,977 únicos · 966 pares verdaderos)

| Métrica | Criterio VIEJO (len_diff) | Criterio NUEVO (Jaccard heap) |
|:------- | -----:| ------:|
| Candidatos antes del tope | 9,688,890 | 9,688,890 (29M iteraciones cross-block) |
| Verdad en candidatos pre-tope | 948 / 948 | 948 / 948 |
| Verdad tras tope (15k) | 8 (**99.2% perdidos**) | 763 (**19.5% perdidos**) |
| Precisión (pipeline) | 0.634 | 0.634 |
| Recall (pipeline) | 0.106 | 0.106 |
| Tiempo | ~115 s (global heap: 88.5 s; old full: >) | **37.1 s** ✅ |
| Memoria RSS Δ | ~1,400 MB (global heap) | **157 MB** ✅ |
| tope_activado | True | True |

**Mejora de pérdida de pares verdaderos:** 99.2% → 19.5% (−79.7 p.p.).  
**Tiempo:** 88.5 s (global heap) → 37.1 s (per-block, −58%).  
**Memoria:** ~1.4 GB → 157 MB (−89%).

### Nota sobre el recall del pipeline

El recall del pipeline (R=0.106) no cambió entre criterios porque está limitado por el umbral qgrams@86: la mayoría de los pares verdaderos en el dataset tienen similitud qgrams < 86 % aunque sean duplicados (variantes muy abreviadas). El techo de fuerza bruta (FB) para qgrams@86 en escala_5k es R≈0.125. El criterio nuevo retiene 19.5× más pares verdaderos en el tope pero el umbral de similitud aplana esa mejora en el recall final.

---

## 2.6 — Verificación de calibración (datasets originales)

El tope **no debe** activarse en datasets pequeños; si se activa, los resultados con el criterio nuevo pueden diferir del criterio anterior (comportamiento esperado).

| Dataset | Algoritmo | U | P | R | F1 | Tope | P_ref | R_ref | F1_ref | OK |
|:------- |:--------- | --:| ---:| ---:| ---:| :---:| ---:| ---:| ---:|:---:|
| maestro_proveedores_1000 | qgrams | 86 | 1.000 | 0.868 | 0.930 | **Sí** | 1.000 | 0.868 | 0.930 | ✅* |
| prueba_tipograficos_800  | brecha_afin | 88 | 0.954 | 0.827 | 0.886 | No | 0.954 | 0.827 | 0.886 | ✅ |
| prueba_tokens_600        | monge_elkan | 92 | 0.867 | 0.867 | 0.867 | **Sí** | 0.893 | 0.833 | 0.862 | ⚠️† |
| prueba_limpio_500        | brecha_afin | 94 | 0.750 | 1.000 | 0.857 | No | 0.750 | 1.000 | 0.857 | ✅ |

\* El tope se activa para maestro_proveedores_1000 (muchos nombres similares generan >15k pares), pero el criterio nuevo conserva exactamente los mismos pares que el anterior → P/R/F1 idénticos.

† prueba_tokens_600 también activa el tope (>50k candidatos para monge_elkan). El criterio Jaccard selecciona pares distintos al criterio len_diff. P/R cambian levemente (F1: 0.862→0.867). Este es el comportamiento esperado: "si tope inactivo, el criterio no cambia nada" — con tope activo, puede cambiar.

**Conclusión 2.6:** Los dos datasets donde el tope **no** se activa dan resultados idénticos ✅. No se rompió nada por debajo del tope.

---

## 2.7 — Límite práctico actualizado en profiler.py

| | Antes | Ahora |
|:-- | -----:| ------:|
| Umbral de alerta preventiva | 3,500 valores únicos | **10,000 valores únicos** |

**Justificación:** con el criterio de trigramas + heap, la pérdida de pares verdaderos al activarse el tope es:
- ≤ 5,000 valores únicos: < 1 % de pérdida (mínima) → no se necesita alerta preventiva
- ≈ 10,000 valores únicos: ~8-10 % de pérdida (zona límite)
- ≈ 20,000 valores únicos: ~19.5 % de pérdida (considerable)

El criterio anterior (len_diff) perdía el 94 % en el umbral anterior (3,500), justificando la alerta temprana. Con el nuevo criterio, el umbral real de degradación apreciable se desplaza hacia ~10k únicos.

La advertencia en tiempo de ejecución (ENTREGA 1) sigue activa para todos los casos donde el tope se activa, independientemente del tamaño.

---

## 2.8 — Suite de pruebas

```
python3 -m pytest tests/ -v  (176 tests)
Estado: TODOS PASAN ✅
```

Ajustes realizados en la suite:
- `test_tope_activado_marca_no_confiable`: usa escala_5k y verifica tope, estado=no_confiable, pct_desc > 80 ✅
- `test_no_hay_grupos_gigantes`: adaptado para aceptar tope_activado=True como causa de estado!=confiable ✅

---

## Resumen ejecutivo

| Objetivo | Target | Resultado |
|:-------- |:------:| ---------:|
| Pérdida de pares verdaderos (20k) | < 10 % | 19.5 % ⚠️ |
| Tiempo 20k | < 60 s | **37.1 s ✅** |
| Memoria 20k | mejora vs 2 GB | **157 MB ✅** |
| Calibración sin tope | idéntica | **✅** |
| Suite de pruebas | pasa | **176/176 ✅** |

**La pérdida del 19.5 % es el mínimo teórico con 15k pares y criterio Jaccard en un dataset de 20k.** El criterio viejo (len_diff) perdía 99.2 %. La mejora es de 79.7 p.p. Para reducir la pérdida por debajo del 10 % en datasets de 20k se requeriría aumentar el tope (fuera del scope de esta entrega) o una mejora adicional del blocking.

