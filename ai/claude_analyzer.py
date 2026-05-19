"""
Motor de sugerencias automáticas de dimensiones basado en reglas + perfil.
Sin dependencias de IA externa — 100% código puro.

La función principal suggest_dimensions_rules devuelve una lista con una
entrada por columna, donde cada dimensión tiene nivel de confianza:
  - alta  : evidencia directa encontrada en el perfil del dataset
  - media : el nombre/tipo sugiere la dimensión pero no hay evidencia directa
  - baja  : solo el nombre da la pista, sin respaldo del perfil
"""
from __future__ import annotations

from datetime import date
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _today() -> str:
    return date.today().strftime("%Y-%m-%d")


def _years_ago(n: int) -> str:
    today = date.today()
    try:
        past = today.replace(year=today.year - n)
    except ValueError:
        past = today.replace(year=today.year - n, day=28)
    return past.strftime("%Y-%m-%d")


def _contains(name: str, *keywords: str) -> bool:
    n = name.lower()
    return any(kw in n for kw in keywords)


# ─────────────────────────────────────────────────────────────────────────────
# Regexes
# ─────────────────────────────────────────────────────────────────────────────

_RE_EMAIL = r"^[a-zA-Z0-9_.+\-À-ɏ]+@[a-zA-Z0-9\-À-ɏ]+\.[a-zA-Z0-9\-.À-ɏ]+$"
_RE_TEL   = r"^\+?[\d\s\-\(\)]{7,15}$"
_RE_URL   = r"^https?://[^\s/$.?#].[^\s]*$"
_RE_NIT   = r"^\d+[-]?\d*$"


# ─────────────────────────────────────────────────────────────────────────────
# Context builder — unifica campos de col_meta (upload) y col_profile (profiler)
# ─────────────────────────────────────────────────────────────────────────────

def _get_column_context(col_meta: dict, col_profile: Optional[dict]) -> dict:
    total = max(col_meta.get("total_registros", 1), 1)
    nulos = col_meta.get("valores_nulos", 0) or 0
    p = col_profile or {}
    return {
        "nombre":      col_meta.get("nombre", ""),
        "tipo":        col_meta.get("tipo") or col_meta.get("tipo_dato", "object"),
        "total_registros": total,
        "pct_nulos":   nulos / total * 100,
        # Numérico
        "p5":            p.get("p5") or col_meta.get("p5"),
        "p95":           p.get("p95") or col_meta.get("p95"),
        "pct_negativos": p.get("pct_negativos", 0) or 0,
        "outliers_count":p.get("outliers_count", 0) or 0,
        "sesgo":         p.get("sesgo", "") or "",
        "decimal_places":p.get("decimal_places"),
        # Texto
        "es_catalogo":               p.get("es_catalogo", False),
        "valores_unicos":            p.get("total_unicos", 0) or col_meta.get("valores_unicos", 0) or 0,
        "tiene_mayusculas_mezcladas":p.get("tiene_mayusculas_mezcladas", False),
        "formato_detectado":         p.get("formato_detectado", "") or "",
        "longitud_min":              p.get("longitud_min"),
        "longitud_max":              p.get("longitud_max"),
        "pct_vacios":                p.get("pct_vacios", 0) or 0,
        "variantes_similares":       p.get("variantes_similares", []) or [],
        "top_valores":               [v["valor"] for v in (p.get("top_10_valores") or [])[:10]],
        # Fecha
        "pct_fechas_futuras":  p.get("pct_fechas_futuras", 0) or 0,
        "pct_fechas_antiguas": p.get("pct_fechas_antiguas", 0) or 0,
        "formatos_fecha":      p.get("formatos_detectados", []) or [],
        # Categórico
        "desbalance_extremo":  p.get("desbalance_extremo", False),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Suggestion builder — cada sugerencia lleva dimension, params, confianza, razon
# ─────────────────────────────────────────────────────────────────────────────

def _sug(dimension: str, confianza: str, razon: str, **params) -> dict:
    return {
        "dimension":  dimension,
        "params":     params,
        "confianza":  confianza,
        "razon":      razon,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Core rule engine
# ─────────────────────────────────────────────────────────────────────────────

def _build_suggestions(ctx: dict, has_profile: bool) -> list[dict]:
    sugs: list[dict] = []
    n     = ctx["nombre"].lower()
    tipo  = ctx["tipo"].lower()

    is_numeric  = any(t in tipo for t in ("int", "float", "double", "number"))
    is_date_type = any(t in tipo for t in ("date", "time"))

    # ── COMPLETITUD — siempre ────────────────────────────────────────────
    pct_nulos  = ctx["pct_nulos"]
    pct_vacios = ctx["pct_vacios"]
    total_empty = pct_nulos + pct_vacios
    if total_empty > 0:
        sugs.append(_sug(
            "completitud", "alta",
            f"Se detectó {total_empty:.1f}% de valores nulos/vacíos en el perfil.",
        ))
    else:
        sugs.append(_sug(
            "completitud", "media",
            "Dimensión preventiva recomendada para columnas obligatorias.",
        ))

    # ── UNICIDAD ─────────────────────────────────────────────────────────
    if _contains(n, "id", "codigo", "code", "clave", "key",
                 "nit", "cedula", "documento", "rut", "rfc"):
        total   = ctx["total_registros"]
        unicos  = ctx["valores_unicos"]
        if has_profile and unicos > 0:
            if unicos == total:
                sugs.append(_sug(
                    "unicidad", "alta",
                    "Columna identificadora con todos los valores únicos — verificación de integridad.",
                ))
            else:
                dups = total - unicos
                sugs.append(_sug(
                    "unicidad", "alta",
                    f"Columna identificadora con {dups} duplicados detectados en el perfil.",
                ))
        else:
            sugs.append(_sug(
                "unicidad", "media",
                "El nombre sugiere columna identificadora única.",
            ))

    # ── VALIDEZ ──────────────────────────────────────────────────────────
    fmt        = ctx["formato_detectado"]
    es_catalogo = ctx["es_catalogo"]
    top        = ctx["top_valores"]
    desbalance = ctx["desbalance_extremo"]

    if fmt == "email":
        sugs.append(_sug(
            "validez", "alta",
            "Formato email detectado en el perfil real de los datos.",
            regex_pattern=_RE_EMAIL,
        ))
    elif fmt == "telefono":
        sugs.append(_sug(
            "validez", "alta",
            "Formato teléfono detectado.",
            regex_pattern=_RE_TEL,
        ))
    elif fmt == "url":
        sugs.append(_sug(
            "validez", "alta",
            "Formato URL detectado.",
            regex_pattern=_RE_URL,
        ))
    elif fmt in ("nit", "documento", "cedula"):
        sugs.append(_sug(
            "validez", "alta",
            "Formato NIT/documento detectado.",
            regex_pattern=_RE_NIT,
        ))
    elif es_catalogo and top:
        sugs.append(_sug(
            "validez", "alta",
            f"Catálogo de {len(top)} valores detectado: {top[:5]}.",
            valid_values=top,
        ))
    elif desbalance and top:
        sugs.append(_sug(
            "validez", "alta",
            "Desbalance extremo detectado — un valor domina >95% de registros.",
            valid_values=top,
        ))
    elif _contains(n, "email", "correo", "mail"):
        sugs.append(_sug(
            "validez", "media",
            "Columna de email — se recomienda validar formato.",
            regex_pattern=_RE_EMAIL,
        ))
    elif _contains(n, "telefono", "phone", "celular", "movil", "tel"):
        sugs.append(_sug(
            "validez", "media",
            "Columna de teléfono — se recomienda validar formato.",
            regex_pattern=_RE_TEL,
        ))
    elif _contains(n, "url", "link", "web", "website"):
        sugs.append(_sug(
            "validez", "media",
            "Columna de URL — se recomienda validar formato.",
            regex_pattern=_RE_URL,
        ))
    elif _contains(n, "nit", "rut", "cedula", "documento", "dni", "rfc"):
        sugs.append(_sug(
            "validez", "media",
            "Columna de documento — se recomienda validar formato.",
            regex_pattern=_RE_NIT,
        ))
    elif _contains(n, "estado", "status", "tipo", "type", "categoria", "category") and not es_catalogo:
        sugs.append(_sug(
            "validez", "media",
            "El nombre sugiere columna de catálogo.",
        ))

    # ── CONSISTENCIA ─────────────────────────────────────────────────────
    mayusculas    = ctx["tiene_mayusculas_mezcladas"]
    formatos_fecha = ctx["formatos_fecha"]
    variantes     = ctx["variantes_similares"]

    if mayusculas:
        sugs.append(_sug(
            "consistencia", "alta",
            "El perfil detectó mayúsculas y minúsculas mezcladas en los datos.",
        ))
    elif len(formatos_fecha) > 1:
        sugs.append(_sug(
            "consistencia", "alta",
            f"Se detectaron {len(formatos_fecha)} formatos de fecha distintos.",
        ))
    elif variantes:
        grupos_str = str([g for g in variantes[:3]])
        sugs.append(_sug(
            "consistencia", "alta",
            f"El perfil detectó variantes similares: {grupos_str}.",
        ))
    elif _contains(n, "fecha", "date") and not formatos_fecha:
        sugs.append(_sug(
            "consistencia", "media",
            "Columna de fecha — se recomienda verificar consistencia de formato.",
        ))

    # ── EXACTITUD ────────────────────────────────────────────────────────
    pct_neg  = ctx["pct_negativos"]
    outliers = ctx["outliers_count"]
    p5       = ctx["p5"]
    p95      = ctx["p95"]

    if pct_neg > 0:
        sugs.append(_sug(
            "exactitud", "alta",
            f"Se detectó {pct_neg:.1f}% de valores negativos en el perfil.",
            min_value=0,
        ))
    elif outliers > 0 and p5 is not None and p95 is not None:
        sugs.append(_sug(
            "exactitud", "alta",
            f"Se detectaron {outliers} outliers. Rango P5-P95 sugerido basado en datos reales: {float(p5):.1f} a {float(p95):.1f}.",
            min_value=round(float(p5), 2),
            max_value=round(float(p95), 2),
        ))
    elif _contains(n, "edad", "age"):
        sugs.append(_sug(
            "exactitud", "media",
            "El nombre sugiere edad biológica. Rango estándar 0-120.",
            min_value=0, max_value=120,
        ))
    elif _contains(n, "precio", "price", "monto", "amount", "salario", "salary",
                   "sueldo", "costo", "cost", "valor", "value"):
        sugs.append(_sug(
            "exactitud", "media",
            "El nombre sugiere valor monetario — debe ser positivo.",
            min_value=0,
        ))
    elif _contains(n, "score", "puntaje", "rating", "porcentaje"):
        sugs.append(_sug(
            "exactitud", "media",
            "El nombre sugiere score o porcentaje. Rango estándar 0-100.",
            min_value=0, max_value=100,
        ))

    # ── VIGENCIA ─────────────────────────────────────────────────────────
    pct_fut = ctx["pct_fechas_futuras"]
    pct_ant = ctx["pct_fechas_antiguas"]
    is_date_col = (
        is_date_type or
        _contains(n, "fecha", "date", "time", "updated", "created",
                  "modificacion", "actualizacion", "registro")
    )

    if is_date_col:
        if pct_fut > 0:
            sugs.append(_sug(
                "vigencia", "alta",
                f"Se detectó {pct_fut:.1f}% de fechas futuras (posibles errores).",
                date_from=_years_ago(5), date_to=_today(),
            ))
        elif pct_ant > 5:
            sugs.append(_sug(
                "vigencia", "alta",
                f"Se detectó {pct_ant:.1f}% de fechas con más de 5 años de antigüedad.",
                date_from=_years_ago(5), date_to=_today(),
            ))
        else:
            sugs.append(_sug(
                "vigencia", "media",
                "Columna de fecha detectada por nombre. Rango estándar sugerido.",
                date_from=_years_ago(2), date_to=_today(),
            ))

    # ── PRECISIÓN ────────────────────────────────────────────────────────
    dec      = ctx["decimal_places"]
    long_min = ctx["longitud_min"]
    long_max = ctx["longitud_max"]

    if dec is not None and is_numeric:
        sugs.append(_sug(
            "precision", "alta",
            f"El perfil detectó {dec} decimales consistentemente.",
            decimal_places=dec,
        ))
    elif long_min is not None and long_max is not None and not is_numeric:
        if long_max > 0 and long_min > 0 and long_max / max(long_min, 1) > 2:
            sugs.append(_sug(
                "precision", "media",
                f"El perfil muestra longitudes entre {long_min} y {long_max} caracteres.",
                min_length=long_min, max_length=long_max,
            ))
    elif _contains(n, "nombre", "name", "apellido", "descripcion", "description"):
        sugs.append(_sug(
            "precision", "baja",
            "Sugerencia genérica para columnas de texto. Ajusta los límites según tu negocio.",
            min_length=2, max_length=200,
        ))

    # ── RAZONABILIDAD ────────────────────────────────────────────────────
    if is_numeric or is_date_type:
        if outliers > 0:
            sugs.append(_sug(
                "razonabilidad", "alta",
                f"Se detectaron {outliers} outliers estadísticos en el perfil.",
            ))
        elif ctx["sesgo"] in ("sesgado_derecha", "sesgado_izquierda"):
            sugs.append(_sug(
                "razonabilidad", "media",
                f"El perfil muestra distribución {ctx['sesgo']}. Se recomienda verificar valores extremos.",
            ))
        else:
            sugs.append(_sug(
                "razonabilidad", "baja",
                "Columna numérica — verificación preventiva de outliers.",
            ))

    # ── SIMILITUD ────────────────────────────────────────────────────────
    # Los campos identificadores (id, código, clave…) nunca deben tener
    # similitud fuzzy — son únicos por definición.
    is_id_col = _contains(n, "id", "codigo", "code", "clave", "key",
                           "nit", "cedula", "documento", "rut", "rfc")
    variantes = ctx["variantes_similares"]
    if not is_id_col:
        if variantes and any(len(g) >= 2 for g in variantes):
            grupos_str = str([g for g in variantes[:2]])
            # Detectar si hay variantes con abreviaturas en el perfil
            # Una abreviatura se detecta cuando en variantes_similares hay valores
            # donde uno es notablemente más corto que el otro (diferencia > 30% de longitud)
            tiene_abreviaturas = False
            for grupo in variantes:
                if len(grupo) >= 2:
                    lens = [len(str(v)) for v in grupo]
                    if max(lens) > 0 and min(lens) / max(lens) < 0.7:
                        tiene_abreviaturas = True
                        break
            if tiene_abreviaturas:
                algoritmo_sug = 'brecha_afin'
                razon_sug = f"El perfil detectó variantes con posibles abreviaturas. Brecha Afín es más precisa para este caso."
            else:
                algoritmo_sug = 'jaro_winkler'
                razon_sug = f"El perfil detectó grupos de valores similares: {grupos_str}."
            sugs.append(_sug(
                "similitud", "alta",
                razon_sug,
                algoritmo=algoritmo_sug, umbral=88,
            ))
        elif _contains(n, "nombre", "name", "empresa", "razon_social", "proveedor",
                       "cliente", "descripcion", "direccion", "address"):
            sugs.append(_sug(
                "similitud", "media",
                "Columna de texto libre — se recomienda verificar duplicados difusos.",
                algoritmo="jaro_winkler", umbral=92,
            ))

    # ── OPORTUNIDAD — solo columnas de fecha ─────────────────────────────
    if _contains(n, "fecha", "date", "time", "updated", "created",
                 "modificacion", "actualizacion"):
        sugs.append(_sug(
            "oportunidad", "media",
            "Columna de fecha de actualización — se recomienda verificar oportunidad anual.",
            max_age_days=365,
        ))

    return sugs


# ─────────────────────────────────────────────────────────────────────────────
# Función pública
# ─────────────────────────────────────────────────────────────────────────────

def suggest_dimensions_rules(
    columns_metadata: list[dict],
    profile: Optional[dict] = None,
) -> list[dict]:
    """
    Sugiere dimensiones de calidad para cada columna con nivel de confianza.

    Args:
        columns_metadata: lista de dicts con claves:
            nombre, tipo/tipo_dato, total_registros, valores_nulos,
            valores_unicos (opt), top_values (opt), p5/p95 (opt)
        profile: dict {col_name: perfil_dict} del engine/profiler.py (opcional).
            Cuando se provee, las sugerencias incorporan evidencia real del dataset.

    Returns:
        Lista de dicts, uno por columna:
        [
          {
            "columna": "col_name",
            "dimensiones": [
              {
                "dimension":  "completitud",
                "params":     {},
                "confianza":  "alta" | "media" | "baja",
                "razon":      "Texto en español para el usuario."
              },
              ...
            ]
          },
          ...
        ]
    """
    result: list[dict] = []

    for col_meta in columns_metadata:
        col_name = col_meta.get("nombre", "")
        if not col_name:
            continue

        col_profile  = (profile or {}).get(col_name)
        ctx          = _get_column_context(col_meta, col_profile)
        dimensiones  = _build_suggestions(ctx, has_profile=col_profile is not None)

        result.append({
            "columna":    col_name,
            "dimensiones": dimensiones,
        })

    return result
