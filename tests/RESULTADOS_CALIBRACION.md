# Resultados de calibración — Similitud

**Fecha:** 2026-08-13  
**Condición:** normalización corregida (puntos eliminados, no convertidos a espacio)  
**Cobertura:** 7 algoritmos × 4 datasets × 8 umbrales (80, 83, 86, 88, 90, 92, 94, 96)  
**Nueva columna:** FB (Fuerza Bruta) — techo teórico del algoritmo sin bloqueo ni tope de pares.  
GapR = R\_pip − R\_fb (negativo = pipeline pierde recall vs FB; ⚠️ si gap < −0.15)

> brecha\_afin y monge\_elkan están marcados `FB=N/A` — su FB es O(n²×longitud) y tarda varios minutos.

---

## maestro\_proveedores\_1000 (razon\_social · verdad = ruc · 38 pares)

| Algoritmo      |  U | P\_fb | R\_fb | F1\_fb | P\_pip | R\_pip | F1\_pip | GapR   |  t(s) |
|:-------------- | --:|------:|------:|-------:|-------:|-------:|--------:|-------:|------:|
| **qgrams** 🏆  | 86 | 1.000 | 0.868 |  0.930 |  1.000 |  0.868 |   0.930 | **0.000** |   0.4 |
| brecha\_afin   | 94 |   N/A |   N/A |    N/A |  1.000 |  0.816 |   0.899 |    N/A |  28.4 |
| jaro           | 96 | 0.971 | 0.868 |  0.917 |  1.000 |  0.868 |   0.930 | 0.000  |   0.2 |
| levenshtein    | 94 | 1.000 | 0.868 |  0.930 |  1.000 |  0.868 |   0.930 | 0.000  |   0.3 |
| jaro\_winkler  | 96 | 0.717 | 0.868 |  0.786 |  0.767 |  0.868 |   0.815 | 0.000  |   0.3 |
| soundex        | 80 | 0.974 | 1.000 |  0.987 |  1.000 |  0.868 |   0.930 | −0.132 |   0.3 |
| monge\_elkan   | 96 |   N/A |   N/A |    N/A |  0.800 |  0.526 |   0.635 |    N/A |   1.1 |

**Veredicto:** qgrams@86 es óptimo. Recall del pipeline = techo de FB (GapR = 0): la corrección de puntos eliminó el gap que había. ✅ Sugerencia vigente confirmada.

### Comparación vs tabla anterior (sin corrección de puntos)

| Métrica       | Antes  | Ahora  | Δ       |
|:------------- | ------:| ------:| -------:|
| qgrams R\_pip | 0.395  | 0.868  | **+0.473** |
| qgrams F1\_pip| 0.566  | 0.930  | **+0.364** |
| GapR          | −0.473 | 0.000  | **+0.473** |

---

## prueba\_tipograficos\_800 (nombre\_completo · verdad = entidad\_real\_id · 75 pares)

| Algoritmo         |  U | P\_fb | R\_fb | F1\_fb | P\_pip | R\_pip | F1\_pip | GapR   |  t(s) |
|:----------------- | --:|------:|------:|-------:|-------:|-------:|--------:|-------:|------:|
| **brecha\_afin** 🏆 | 88 |   N/A |   N/A |    N/A |  0.954 |  0.827 |   0.886 |    N/A |   9.8 |
| monge\_elkan      | 94 |   N/A |   N/A |    N/A |  0.802 |  0.920 |   0.857 |    N/A |   0.5 |
| levenshtein       | 86 | 0.315 | 0.707 |  0.436 |  0.929 |  0.693 |   0.794 | −0.013 |   0.1 |
| jaro\_winkler     | 96 | 0.270 | 0.547 |  0.361 |  0.953 |  0.547 |   0.695 | 0.000  |   0.1 |
| jaro              | 94 | 0.277 | 0.573 |  0.374 |  0.952 |  0.533 |   0.684 | −0.040 |   0.1 |
| soundex           | 80 | 0.237 | 0.493 |  0.320 |  0.756 |  0.413 |   0.534 | −0.080 |   0.1 |
| qgrams            | 80 | 0.092 | 0.147 |  0.113 |  1.000 |  0.120 |   0.214 | −0.027 |   0.2 |

**Veredicto:** brecha\_afin@**88** (era @90). A umbral 90: P=1.00, R=0.59, F1=0.74 — pierde el 29% del recall por exceso de umbral. ⚡ **Cambio: umbral 90 → 88** (F1: +0.146).

### Detalle brecha\_afin a distintos umbrales

| U  | P\_pip | R\_pip | F1\_pip |
|---:|-------:|-------:|--------:|
| 80 |  0.480 |  1.000 |   0.649 |
| 83 |  0.727 |  0.920 |   0.812 |
| 86 |  0.843 |  0.867 |   0.854 |
| **88** |  **0.954** |  **0.827** |   **0.886** ← nuevo umbral |
| 90 |  1.000 |  0.587 |   0.740 |
| 92 |  1.000 |  0.387 |   0.558 |

---

## prueba\_tokens\_600 (direccion · verdad = entidad\_real\_id · 60 pares)

| Algoritmo         |  U | P\_fb | R\_fb | F1\_fb | P\_pip | R\_pip | F1\_pip | GapR   |  t(s) |
|:----------------- | --:|------:|------:|-------:|-------:|-------:|--------:|-------:|------:|
| **monge\_elkan** 🏆 | 92 |   N/A |   N/A |    N/A |  0.893 |  0.833 |   0.862 |    N/A |   1.2 |
| brecha\_afin      | 92 |   N/A |   N/A |    N/A |  0.967 |  0.483 |   0.644 |    N/A |  20.4 |
| soundex           | 90 | 0.300 | 0.300 |  0.300 |  0.647 |  0.183 |   0.286 | −0.117 |   0.2 |
| qgrams            | 80 | 0.413 | 0.433 |  0.423 |  0.833 |  0.083 |   0.152 | **−0.350** ⚠️ |  0.3 |
| jaro\_winkler     | 80 | 0.013 | 0.600 |  0.025 |  0.000 |  0.067 |   0.000 | **−0.533** ⚠️ |  0.2 |
| jaro              | 80 | 0.046 | 0.517 |  0.085 |  0.001 |  0.017 |   0.002 | **−0.500** ⚠️ |  0.2 |
| levenshtein       | 80 | 0.216 | 0.483 |  0.299 |  0.000 |  0.000 |   0.000 | **−0.483** ⚠️ |  0.2 |

**Veredicto:** monge\_elkan@92 supera a brecha\_afin por margen amplio (R=0.83 vs 0.48, F1=0.86 vs 0.64). Y es más rápido en el pipeline (1.2s vs 20.4s). ⚡ **Cambio: via≥15% → monge\_elkan@92** (era brecha\_afin@90).

---

## prueba\_limpio\_500 (nombre\_producto · verdad = entidad\_real\_id · 3 pares)

| Algoritmo         |  U | P\_fb | R\_fb | F1\_fb | P\_pip | R\_pip | F1\_pip | GapR  |  t(s) |
|:----------------- | --:|------:|------:|-------:|-------:|-------:|--------:|------:|------:|
| **brecha\_afin** 🏆 | 94 |   N/A |   N/A |    N/A |  0.750 |  1.000 |   0.857 |   N/A |   4.6 |
| levenshtein       | 96 | 0.075 | 1.000 |  0.140 |  0.750 |  1.000 |   0.857 | 0.000 |   0.1 |
| qgrams            | 80 | 0.007 | 0.667 |  0.013 |  0.007 |  0.667 |   0.014 | 0.000 |   0.2 |
| jaro\_winkler     | 96 | 0.006 | 0.667 |  0.011 |  0.004 |  0.667 |   0.007 | 0.000 |   0.1 |
| jaro              | 96 | 0.005 | 0.333 |  0.011 |  0.005 |  0.333 |   0.010 | 0.000 |   0.1 |
| soundex           | 80 | 0.043 | 1.000 |  0.082 |  0.081 |  1.000 |   0.150 | 0.000 |   0.1 |
| monge\_elkan      | 96 |   N/A |   N/A |    N/A |  0.011 |  1.000 |   0.022 |   N/A |   0.3 |

> Nota: solo 3 pares verdaderos — resultados con alta varianza estadística.

**Veredicto:** brecha\_afin@**94** (era @90). A umbral 90: P=0.01, R=1.00, F1=0.02 — prácticamente inútil por falsos positivos masivos. A @94: P=0.75, R=1.00, F1=0.857. ⚡ **Cambio: dig≥40% → brecha\_afin@94** (era @90).

### Detalle brecha\_afin a distintos umbrales (limpio\_500)

| U  | P\_pip | R\_pip | F1\_pip |
|---:|-------:|-------:|--------:|
| 80 |  0.000 |  1.000 |   0.001 |
| 86 |  0.001 |  1.000 |   0.003 |
| 90 |  0.010 |  1.000 |   0.020 |
| 92 |  0.050 |  1.000 |   0.095 |
| **94** |  **0.750** |  **1.000** |   **0.857** ← nuevo umbral |
| 96 |  1.000 |  0.333 |   0.500 |

---

## Tabla resumen — mejor umbral confiable (P ≥ 0.75) por dataset

| Dataset                   | Algoritmo    | U  | P\_fb | R\_fb | F1\_fb | P\_pip | R\_pip | F1\_pip | GapR   |
|:------------------------- |:------------ | --:|------:|------:|-------:|-------:|-------:|--------:|-------:|
| maestro\_proveedores\_1000 | **qgrams** ✅ | 86 | 1.000 | 0.868 |  0.930 |  1.000 |  0.868 |   0.930 | 0.000  |
| maestro\_proveedores\_1000 | brecha\_afin | 94 |   N/A |   N/A |    N/A |  1.000 |  0.816 |   0.899 |    N/A |
| prueba\_tipograficos\_800  | **brecha\_afin ✅⚡** | 88 | N/A | N/A | N/A | 0.954 | 0.827 | 0.886 | N/A |
| prueba\_tipograficos\_800  | monge\_elkan | 94 |   N/A |   N/A |    N/A |  0.802 |  0.920 |   0.857 |    N/A |
| prueba\_tokens\_600        | **monge\_elkan ✅⚡** | 92 | N/A | N/A | N/A | 0.893 | 0.833 | 0.862 | N/A |
| prueba\_tokens\_600        | brecha\_afin | 92 |   N/A |   N/A |    N/A |  0.967 |  0.483 |   0.644 |    N/A |
| prueba\_limpio\_500        | **brecha\_afin ✅⚡** | 94 | N/A | N/A | N/A | 0.750 | 1.000 | 0.857 | N/A |

⚡ = cambio respecto a la calibración anterior

---

## Cambios en `sugerir_algoritmo_similitud`

| Caso              | Antes             | Ahora               | Δ F1   |
|:----------------- |:----------------- |:------------------- |-------:|
| suf ≥ 15 %        | qgrams@86 ✅      | qgrams@86 ✅        | —      |
| via ≥ 15 %        | brecha\_afin@90   | **monge\_elkan@92** | +0.218 |
| dig ≥ 40 % (sin via) | brecha\_afin@90 | **brecha\_afin@94** | +0.837 |
| persona (2–4 tok) | brecha\_afin@90   | **brecha\_afin@88** | +0.146 |
| default           | qgrams@86 ✅      | qgrams@86 ✅        | —      |

---

## Metodología

- **Verdad**: pares de IDs con el mismo valor en la columna de verdad (ruc o entidad\_real\_id)
- **Pipeline**: métricas del flujo completo con bloqueo + tope de pares
- **FB**: O(n²) comparación directa — techo teórico del algoritmo
- **GapR < −0.15**: la etapa de bloqueo/tope pierde recall significativo
- **Umbral óptimo**: mejor F1 entre umbrales con P ≥ 0.75
- Ejecutar: `python3 tests/calibrar_algoritmos.py`
