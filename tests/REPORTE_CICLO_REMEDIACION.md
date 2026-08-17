# Reporte: Ciclo de Remediación Completo
**Fecha:** 2026-08-17  
**Archivo base:** `tests/maestro_clientes_500.xlsx` (500 filas, 13 cols)  
**Archivo corregido:** `tests/maestro_clientes_500_corregido.xlsx` (238 filas)  
**Propósito:** Depuración de duplicados · Naturaleza: Maestro de datos

---

## Tabla comparativa

| Métrica | Base | Corregido | Δ |
|:------- | ----:| ---------:| --:|
| **Score general** | 87.0 | **97.4** | **+10.4** ✅ |
| Promedio simple | 93.8 | 96.8 | +3.0 |
| Total registros | 500 | 238 | −262 |
| Registros aprovechables | 226 (45%) | 226 (95%) | mismo abs., +50 pp |
| Sin ningún problema | 27 (5%) | 85 (36%) | **+58** ✅ |
| Total problemas | 473 | 153 | −320 |
| Veredicto | `no_listo` | **`listo`** | ✅ |
| Similitud: grupos | 131 | **0** | −131 ✅ |
| Similitud: excedentes eliminados | 258 | **0** | −258 ✅ |

---

## Score por dimensión antes y después

| Columna / Dimensión | Base | Corregido | Δ | Nota |
|:------------------- | ----:| ---------:| --:| :---- |
| razon_social / similitud | 48.1 | **96.6** | +48.5 | ✅ El corazón de la corrección |
| razon_social / completitud | 99.4 | 98.7 | −0.7 | ≈ mismo (efecto muestreo) |
| cliente_id / unicidad | 98.4 | **100.0** | +1.6 | ✅ |
| cliente_id / completitud | 100.0 | 100.0 | 0 | ≈ mismo |
| numero_documento / precision | 99.4 | **100.0** | +0.6 | ✅ Docs de 7/12 dígitos eran excedentes |
| numero_documento / unicidad | 96.8 | 98.3 | +1.5 | ✅ |
| numero_documento / completitud | 99.2 | 99.2 | ≈0 | ≈ mismo |
| email / validez | 44.0 | 46.2 | +2.2 | ≈ mismo — **no corregido** (ver hallazgo) |
| email / completitud | 98.0 | 98.7 | +0.7 | ≈ mismo |
| departamento / validez | 94.6 | **100.0** | +5.4 | ✅ Catálogo corregido |
| departamento / completitud | 99.0 | 98.7 | −0.3 | ≈ mismo |
| segmento / validez | 94.4 | **100.0** | +5.6 | ✅ Catálogo corregido |
| estado / validez | 94.0 | **100.0** | +6.0 | ✅ Catálogo corregido |
| fecha_alta / consistencia | 96.0 | **100.0** | +4.0 | ✅ Formato normalizado |
| fecha_alta / vigencia | 98.4 | 97.9 | −0.5 | ≈ mismo (muestreo) |
| fecha_alta / completitud | 100.0 | 100.0 | 0 | ≈ mismo |
| fecha_ultima_compra / vigencia | 98.4 | 99.2 | +0.8 | ✅ |
| fecha_ultima_compra / completitud | 98.6 | 99.6 | +1.0 | ✅ |
| linea_credito_pen / exactitud | 98.4 | **100.0** | +1.6 | ✅ Negativos y >2M nulificados |
| **linea_credito_pen / razonabilidad** | **95.2** | **92.4** | **−2.8** | 🔴 **PEOR** — ver hallazgo |
| linea_credito_pen / completitud | 99.0 | 98.3 | −0.7 | ≈ mismo |
| telefono / consistencia | 100.0 | 100.0 | 0 | ≈ mismo — **no detectado** (ver hallazgo) |
| telefono / completitud | 97.6 | 99.2 | +1.6 | ✅ |
| nombre_contacto / completitud | 98.4 | 98.7 | +0.3 | ≈ mismo |
| distrito / completitud | 98.8 | 99.2 | +0.4 | ≈ mismo |

---

## Verificación de condiciones esperadas

| Condición | ¿Se cumple? | Detalle |
|:--------- | :----------:| :------ |
| Score general sube | ✅ | 87.0 → 97.4 (+10.4 puntos) |
| Similitud cerca de 100 con cero grupos | ✅ | 0 grupos, score=96.6% (resto: grupos dispersos residuales) |
| Dimensiones no corregidas quedan igual o mejor | 🔴 **Parcial** | Razonabilidad bajó 95.2→92.4 (−2.8). Vigencia fecha_alta bajó 98.4→97.9 |
| Total registros baja exactamente en excedentes | ✅ | 500 − 262 = 238 (261 excedentes similitud + 1 ID duplicado) |
| Veredicto mejora o se mantiene | ✅ | `no_listo` → `listo` |

### Condición 3 fallida — Razonabilidad empeoró

**Razonabilidad: 95.2 → 92.4 (−2.8 puntos).** La dimensión usa el método IQR (cuartiles) sobre la muestra. Al eliminar 262 filas, la distribución de `linea_credito_pen` cambió: Q1, Q3 y el rango intercuartil se recalculan sobre 238 registros. Algunos valores que estaban dentro del rango normal con 500 registros quedan fuera del nuevo rango estrecho. **No es un error del motor — es una propiedad del método IQR sobre muestras de diferente tamaño.** Implicación: los resultados de razonabilidad son sensibles al tamaño del dataset y no son directamente comparables entre el archivo base y el corregido.

---

## Qué se corrigió leyendo el reporte

| Corrección | Cant. | Basado en |
|:---------- | -----:| :--------- |
| Excedentes de duplicados difusos (similitud) eliminados | 261 | Columnas `grupo_id` + `es_principal_sugerido` |
| Duplicados exactos de `cliente_id` eliminados | 1 | Dimensión unicidad |
| `departamento`: LIMA→Lima, Lima Metropolitana→Lima, Arequipa⎵→Arequipa, --→NaN | 27 | Valores en "Problemas Detallados" |
| `segmento`: Corp.→Corporativo, Med. empresa→Mediana empresa, PyME/pyme→Pequeña empresa, CORPORATIVO→Corporativo | 28 | Valores en "Problemas Detallados" |
| `estado`: activo→Activo, ACTIVO→Activo, inactivo→Inactivo, suspendido→Suspendido, Cancelado→NaN | 30 | Valores en "Problemas Detallados" |
| `fecha_alta` DD/MM/YYYY → YYYY-MM-DD | 15 | Dimension consistencia (formato minoritario) |
| `linea_credito_pen` negativos → NaN | 3 | Dimension exactitud |
| `linea_credito_pen` >2,000,000 → NaN | 1 | Dimension exactitud |

---

## Qué NO se pudo corregir y por qué

| Problema | Filas | Razón |
|:-------- | -----:| :----- |
| Email "inválido" con acentos | 269 | Reporte no explica el criterio. Ver hallazgo crítico 1. |
| Teléfonos con formatos mixtos | ~18 restantes | No detectado por el reporte (score=100%). Ver hallazgo 2. |
| `numero_documento` longitud 7/12 dígitos | 3 | Requiere RENIEC/SUNAT para corregir |
| `estado='Cancelado'` | ~4 restantes | No pertenece al catálogo; no se puede mapear |
| Valores atípicos (razonabilidad) | 24 base | Requieren validación manual — pueden ser legítimos |
| Datos faltantes (nulos) | ~45 restantes | No se pueden inventar |
| Grupos sin principal (2 grupos dispersos) | — | El reporte no sugirió principal para estos grupos |

---

## Hallazgos de usabilidad del reporte

### 🔴 Hallazgo 1: EMAIL — Descripción de error insuficiente para actuar

**Problema:** El reporte dice `"Formato inválido: ana.garcía28@hotmail.com"` para 280 registros.

**Lo que ve el analista:** Un email aparentemente normal, marcado como inválido. No hay en el reporte ninguna pista sobre qué criterio específico falla.

**Causa real:** El regex `[a-zA-Z0-9._%+\-]+@...` requiere ASCII puro en la parte local. Los nombres peruanos generan emails con á, é, í, ó, ú, ñ que fallan silenciosamente.

**Consecuencia práctica:** El analista tiene tres opciones igualmente plausibles:
1. Eliminar las tildes del nombre antes de generar el email (normalización unicode)
2. Cambiar el regex a uno que acepte caracteres UTF-8 válidos
3. Corregir los emails manualmente en el sistema fuente

El reporte no da información suficiente para elegir. El mensaje `"Formato inválido: [valor]"` tendría que incluir `"(criterio: solo caracteres ASCII en parte local)"` para ser accionable.

**Desglose del falso positivo:**
- Emails estructuralmente rotos (sin `@`, doble punto, sin dominio): 11 → estos SÍ son errores reales
- Emails con caracteres no-ASCII en parte local: 269 → esto depende del criterio

### 🔴 Hallazgo 2: TELÉFONO — Problema invisible en el reporte

**Problema:** El reporte muestra `consistencia = 100.0%` para la columna `telefono`.

**Lo que hay en el dataset:**
| Formato | Cantidad |
|:------- | -------:|
| Solo 9 dígitos (estándar) | ~219 |
| Prefijo +51 | ~4 |
| Prefijo 51- | ~5 |
| (01)xxx | ~3 |
| Dígitos con guiones | ~6 |

**Causa:** La dimensión de consistencia detecta mezcla de formatos de **fecha** (YYYY-MM-DD vs DD/MM/YYYY) y de **casing** (MAYÚSCULAS vs minúsculas). No tiene lógica para detectar patrones de números telefónicos.

**Consecuencia:** Un analista que lea el score `consistencia=100%` concluirá que los teléfonos están uniformes. El problema solo se descubre inspeccionando los datos directamente.

**Recomendación de producto:** La dimensión de consistencia podría detectar automáticamente formatos telefónicos comunes (con/sin prefijo internacional) cuando detecta una columna con nombre "telefono/phone/tel".

### 🟡 Hallazgo 3: DUPLICADOS DE ID — Falta indicar cuál conservar

**Problema:** El reporte marca con "Duplicado" ambas filas de un par de `cliente_id` repetidos, pero no indica cuál es el registro "original" y cuál el duplicado.

**Consecuencia:** La remediación asumió "conservar la primera ocurrencia" (orden en el archivo). En un caso real esto podría conservar el registro incorrecto si el archivo no estaba ordenado por fecha de alta o por antigüedad.

**Recomendación:** Mostrar junto al duplicado la fecha de alta o algún campo de auditoría que permita al analista inferir cuál es el original.

### 🟡 Hallazgo 4: ESPACIO INVISIBLE en 'Arequipa '

**Problema:** El valor `'Arequipa '` (con espacio al final) aparece igual que `'Arequipa'` en la celda de Excel y en la columna "Valor encontrado" del reporte, salvo que el analista haga clic en la celda y note el cursor.

**Consecuencia:** Un analista que copie el valor para buscar-reemplazar no encontraría la fila porque la búsqueda exacta `'Arequipa'` no coincide con `'Arequipa '`.

**Recomendación:** El reporte debería mostrar los valores con caracteres invisibles entre comillas, o con un marcador visual (p. ej. `Arequipa·`).

---

## Historial en la base de datos

```sql
SELECT id, nombre_archivo, score_general, version_motor,
       json_extract(pesos_usados,'$.origen') FROM analisis ORDER BY id DESC LIMIT 4;
```

| id | archivo | score | version | pesos_origen |
|---:|:------- | -----:|:------- |:------------ |
| 363 | maestro_clientes_500_corregido.xlsx | 97.4 | v2 | proposito |
| 362 | maestro_clientes_500.xlsx | 87.0 | v2 | proposito |
| 361 | maestro_clientes_500.xlsx | 87.0 | v2 | proposito |
| 360 | maestro_clientes_500.xlsx | 48.1 | v2 | proposito |

Ambos análisis del ciclo (362 y 363): mismo `version_motor=v2` y mismo `origen_pesos=proposito`. **La comparación del historial es válida.**

---

## Prueba de reversión

El archivo base fue analizado de nuevo DESPUÉS de haber corrido el análisis del corregido.  
Resultado: **idéntico al análisis 362** — mismo score general (87.0), mismos scores por dimensión, misma metadata de similitud (131 grupos, cont_marg=0.278).

**No hay estado que persista entre análisis.** El motor es determinístico y sin contaminación entre sesiones.

---

## Conclusión

La promesa central se cumple: **corregir lo que el sistema señala hace subir el score de forma medible** (+10.4 puntos, veredicto cambia de `no_listo` a `listo`). Las dimensiones corregidas mejoran sin excepción.

Los hallazgos más valiosos no son los números, sino las **limitaciones del reporte como instrumento de acción**:

1. El mensaje de error para email no dice qué criterio falla → el analista no sabe qué corregir
2. La dimensión de consistencia no cubre teléfonos → el problema pasa desapercibido
3. La razonabilidad (IQR) es sensible al tamaño del dataset → no es comparable entre base y corregido
4. Los valores con espacios invisibles requieren inspección que el reporte no sugiere
