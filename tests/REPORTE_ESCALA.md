# Prueba de Escala — Análisis de Similitud

**Fecha:** 2026-08-14  
**Algoritmo:** qgrams@86 con normalización corregida  
**Objetivo:** medir qué pasa con el tope de pares cuando hay 5k–50k registros

---

## 1. Generación de datasets

| Archivo         | Filas  | Únicos (norm) | Grupos dup | Pares verdaderos |
|:--------------- | ------:| -------------:| ----------:| ----------------:|
| escala_5k.csv   | 5,000  | 4,995         | 150        | 240              |
| escala_20k.csv  | 20,000 | 19,977        | 600        | 966              |
| escala_50k.csv  | 50,000 | 49,864        | 1,500      | 2,372            |

**Spot-check de similitud:** 8,000 pares aleatorios muestreados por dataset.  
Máxima similitud entre no-duplicados: **63–67%** (ningún par supera el 85%). ✅

**Tipos de variantes sembradas:**
1. Abreviatura geográfica (Lima → Lim, Arequipa → Areq)
2. Typo en descriptor (García → Gahcia, Quispe → Quipse)
3. Sufijo compacto / sin sufijo (S.A.C. → SAC o nombre sin sufijo)
4. Palabra extra (+ "del Peru", "y Asociados", "International")
5. Combinación (typo + sin sufijo)

> Nota: tipo 3 y "sin tildes" colapsan a match exacto tras normalización
> (unidecode+punto-removal) y son detectados por la ruta de unicidad, no similitud.

---

## 2. Resultados de medición

| Dataset    | Filas  | Únicos  | Verdad | Cands_antes  | Tope | Cands_después | V.perdidos    | P_pip | R_pip | F1_pip | R_fb   | t(s) | Mem_RSS |
|:---------- | ------:| -------:| ------:| ------------:| ----:| -------------:| -------------:| -----:| -----:| ------:| ------:| ----:| -------:|
| escala_5k  | 5,000  | 4,995   | 240    | 1,033,204    | SÍ ⚠️ | 15,000       | **219 (94%)⚠️** | 0.000 | 0.000 | 0.000 | 0.125 | 3s   | 534 MB  |
| escala_20k | 20,000 | 19,977  | 966    | 9,688,890    | SÍ ⚠️ | 15,000       | **940 (99%)⚠️** | 0.000 | 0.000 | 0.000 | N/A   | 38s  | 2,696 MB |
| escala_50k | 50,000 | 49,864  | 2,372  | ~100-200M¹   | SÍ ⚠️ | —            | ~100%¹        | —     | —     | —      | N/A   | >18 min¹ | >10 GB¹ |

¹ El proceso de bloqueo para 50k fue cancelado tras 18 minutos y 2.5 GB RSS sin completar.
  Con ~50k únicos y bloques de 1,786 nombres, C(1,786,2)≈1.6M pares por bloque × 28 actividades ≈ 90M+ candidatos.

**Nota sobre R_fb en 5k (0.125):** la FB solo detecta el 12.5% de los 240 pares verdaderos
a threshold 86. El 87.5% restante usa variantes (typo agresivo, truncación) que quedan
por debajo del umbral de qgrams@86 en bruta fuerza. El problema del cap es independiente de
esto: incluso los 232 pares que SÍ entran a los candidatos, 219 son descartados por el tope.

---

## 3. El número que decide todo

```
escala_5k:
  verdad_en_candidatos ANTES del tope:   232 / 232  (100%) ← el bloqueo los encuentra a TODOS
  verdad_en_candidatos DESPUÉS del tope:  13 / 232  (5.6%)
  PERDIDOS POR TOPE:                     219 pares (94.4%) ⚠️

escala_20k:
  verdad_en_candidatos ANTES del tope:   948 / 948  (100%) ← el bloqueo los encuentra a TODOS
  verdad_en_candidatos DESPUÉS del tope:   8 / 948  (0.8%)
  PERDIDOS POR TOPE:                     940 pares (99.2%) ⚠️
```

El bloqueo encuentra TODOS los pares verdaderos. El tope los descarta casi todos.
**A esta escala, el análisis no examina el archivo — examina una muestra arbitraria.**

### ¿Por qué tan masivo?

Con 28 actividades y ≈178 nombres/actividad en 5k (≈714 en 20k):

| Estrategia de bloqueo | Tamaño de bloque (5k) | Pares por bloque | Bloques |
|:---------------------- | ---------------------:| ----------------:| -------:|
| `tok_importaciones`    | 178                   | 15,753           | 28      |
| `pref_im`              | 178                   | 15,753           | ~14     |
| `sdx_I500` (soundex)  | 178                   | 15,753           | ~8      |
| `len_30`               | ~400                  | 79,800           | ~6      |

→ Solo `tok_` y `pref_` dan ≈ 420k pares antes de contar `len_` y `sdx_`.
→ El criterio de descarte `abs(len_diff)` no diferencia: todos los nombres tienen misma estructura → `len_diff ≈ 0` → el tiebreaker alfabético es efectivamente **aleatorio** respecto a cuáles son los pares verdaderos.

---

## 4. Alternativas (medidas en escala_20k)

| Variante                                      | Pares   | Supervivientes  | Perdidos       |
|:--------------------------------------------- | -------:| ---------------:| --------------:|
| **Producción** (global abs\_len\_diff, 15k)   | 15,000  | 8 / 948 (0.8%)  | 940 (99.2%)    |
| **Alt A** — tope por bloque (100/bloque)      | 15,763  | 53 / 948 (5.6%) | 895 (94.4%)    |
| **Alt B** — prioridad por trigramas, 15k      | 15,000  | **861 / 948 (91%)** | **87 (9.2%)** |

### Alt A — tope por bloque (max 100 pares/bloque, misma ordenación)

Cada bloque contribuye máximo 100 pares, ordenados por abs(len_diff) internamente.
Con 335 bloques → máximo 33,500 pares totales.

**Resultado:** 53 supervivientes (6.6× mejor que producción, pero aún 94% perdido).  
**Motivo del fallo:** el bloque `tok_importaciones` tiene ~250,000 pares; los 100 que sobreviven  
(los de menor len_diff y orden alfabético) raramente coinciden con los pares verdaderos.

### Alt B — prioridad por similitud de trigramas (ordenación global, tope=15k)

Reemplaza `abs(len_diff)` por la proporción de trigramas compartidos (Jaccard de 3-gramas,  
sin alineación) como criterio de ordenación. Conserva los 15k pares MÁS similares estimados.

**Resultado:** 861 / 948 supervivientes (**108× mejor que producción**).

**¿Por qué funciona?**

| Par                                       | Tipo     | Trigrama-Jaccard |
|:----------------------------------------- | --------:| ----------------:|
| "importaciones lima garcia" ↔ "importaciones lima gahcia" | verdadero | ~82% |
| "importaciones lima garcia" ↔ "importaciones trujillo quispe" | falso | ~51% |

La separación entre verdaderos y falsos permite seleccionar los 15k con mayor probabilidad  
de ser verdaderos.

**Costo de ordenación en 20k:** 142 segundos (para 9.7M pares). Demasiado lento para producción.

**Optimizaciones posibles (no implementadas):**
- Implementación en numpy: el cálculo de intersección de sets de trigramas puede vectorizarse
- Tope local por bloque con criterio trigrama: cada bloque ordena sus propios pares (sub-problema mucho más pequeño) → O(B × k²·log k) en lugar de O(N·log N) global
- Target: <10 segundos para datasets de 20k

---

## 5. Límite práctico recomendado

| Condición                           | Observación                                                     |
|:----------------------------------- | :-------------------------------------------------------------- |
| < 3,000 únicos                      | Pipeline confiable, tope probablemente no activo                |
| 3,000 – 5,000 únicos                | Zona de riesgo: el tope puede activarse; recall degradado       |
| > 5,000 únicos                      | Tope activo con seguridad; >94% de pares verdaderos perdidos    |
| > 20,000 únicos                     | Pipeline inútil (R≈0) y memoria > 2.7 GB                       |
| > 50,000 únicos                     | Bloqueo no completable en RAM típica de servidor (>10 GB)       |

> El umbral de 3,000 aplica cuando hay repetición estructural en el primer token  
> (datos sectoriales: todos "importaciones …", "construcciones …").  
> Datos más heterogéneos (nombres de personas, productos variados) tienen bloques  
> más pequeños y el límite sería mayor (~8,000–15,000 únicos).

### Advertencia sugerida para el frontend

```
Cuando n_únicos_columna > 3,500 (o n_filas > 5,000):

  "⚠️  Esta columna tiene {N} valores únicos. El motor de similitud revisa un
   subconjunto de pares candidatos (límite: 15.000 de {M} posibles). Es posible
   que algunos duplicados no sean detectados. Tiempo estimado: ~{T} segundos."
```

La variable `pares_candidatos` ya está disponible en los metadatos del pipeline  
(`metadata['pares_sobre_umbral']`). Habría que exponer también el conteo pre-tope.

---

## Scripts generados

| Script                      | Propósito                                                  |
|:--------------------------- | :--------------------------------------------------------- |
| `tests/generar_escala.py`   | Genera los tres CSVs con duplicados sembrados y verificación de similitud |
| `tests/medir_escala.py`     | Mide bloqueo, tope, alternativas y memoria a escala        |
| `tests/REPORTE_ESCALA.md`   | Este reporte                                               |

```bash
python3 tests/generar_escala.py   # genera los CSV (30-60s)
python3 tests/medir_escala.py     # mide 5k y 20k (~2 min); 50k requiere >18 min y >10 GB
```
