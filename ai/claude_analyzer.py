"""
Motor de sugerencias automáticas de dimensiones basado en reglas.
Sin dependencias de IA externa — 100% código puro.
"""
from __future__ import annotations
from datetime import date
from typing import Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _today() -> str:
    return date.today().strftime("%Y-%m-%d")


def _five_years_ago() -> str:
    today = date.today()
    try:
        past = today.replace(year=today.year - 5)
    except ValueError:
        # Feb 29 en año no bisiesto
        past = today.replace(year=today.year - 5, day=28)
    return past.strftime("%Y-%m-%d")


def _contains(name: str, *keywords: str) -> bool:
    n = name.lower()
    return any(kw in n for kw in keywords)


# ─────────────────────────────────────────────────────────────────────────────
# Reglas por nombre de columna
# Returns (dims_dict, razon) or None si no aplica ninguna regla
# ─────────────────────────────────────────────────────────────────────────────

def _rule_by_name(col_name: str) -> Optional[Tuple[dict, str]]:
    n = col_name.lower()

    # ID / código / clave
    if _contains(n, "id", "codigo", "code", "clave", "key"):
        return (
            {"completitud": {}, "unicidad": {}},
            "Columna identificadora: se verifica completitud y unicidad de valores",
        )

    # Email / correo
    if _contains(n, "email", "correo", "mail"):
        regex = (
            r"^[a-zA-Z0-9_.+\-À-ɏ]+"
            r"@[a-zA-Z0-9\-À-ɏ]+"
            r"\.[a-zA-Z0-9\-.À-ɏ]+$"
        )
        return (
            {"completitud": {}, "unicidad": {}, "validez": {"regex_pattern": regex}},
            "Columna de email: se valida formato y unicidad por cliente",
        )

    # Teléfono / celular
    if _contains(n, "telefono", "phone", "celular", "movil", "tel"):
        return (
            {
                "completitud": {},
                "validez": {"regex_pattern": r"^\+?[\d\s\-\(\)]{7,15}$"},
            },
            "Columna de teléfono: se valida formato numérico internacional",
        )

    # Fecha / datetime
    if _contains(n, "fecha", "date", "time", "created", "updated", "registro",
                 "creacion", "actualizacion", "modificacion"):
        return (
            {
                "completitud": {},
                "vigencia": {"date_from": _five_years_ago(), "date_to": _today()},
                "consistencia": {},
                "oportunidad": {"max_age_days": 365},
            },
            "Columna de fecha: se verifica vigencia y consistencia de formato",
        )

    # Edad / age
    if _contains(n, "edad", "age"):
        return (
            {
                "completitud": {},
                "exactitud": {"min_value": 0, "max_value": 120},
                "razonabilidad": {},
            },
            "Columna de edad: se verifican rango 0–120 y valores atípicos",
        )

    # Precio / monto / salario / costo
    if _contains(n, "precio", "price", "monto", "amount", "valor", "value",
                 "costo", "cost", "salario", "salary", "sueldo"):
        return (
            {
                "completitud": {},
                "exactitud": {"min_value": 0},
                "razonabilidad": {},
                "precision": {"decimal_places": 2},
            },
            "Columna monetaria: se verifican valores positivos, outliers y precisión decimal",
        )

    # Score / puntaje / calificación / rating
    if _contains(n, "score", "puntaje", "calificacion", "rating"):
        return (
            {
                "completitud": {},
                "exactitud": {"min_value": 0, "max_value": 100},
                "razonabilidad": {},
            },
            "Columna de puntaje: se verifica rango 0–100 y distribución estadística",
        )

    # Nombre / razón social / empresa / dirección — candidatas a similitud fuzzy
    if _contains(n, "nombre", "name", "razon_social", "empresa", "company",
                 "proveedor", "cliente", "descripcion", "description", "direccion", "address"):
        return (
            {
                "completitud": {},
                "precision": {"min_length": 2, "max_length": 200},
                "similitud": {"algoritmo": "jaro_winkler", "umbral": 85, "normalizar": True},
            },
            "Columna de texto libre: se verifica completitud, longitud y duplicados aproximados (fuzzy)",
        )

    # Estado / tipo / categoría / género
    if _contains(n, "estado", "status", "tipo", "type", "categoria",
                 "category", "genero", "gender"):
        return (
            {"completitud": {}, "validez": {}, "consistencia": {}},
            "Columna categórica: se validan valores permitidos y consistencia de formato",
        )

    # País / ciudad / región / departamento
    if _contains(n, "pais", "country", "ciudad", "city", "region", "departamento"):
        return (
            {"completitud": {}, "validez": {}, "consistencia": {}},
            "Columna geográfica: se validan valores y consistencia de capitalización",
        )

    # URL / link / web
    if _contains(n, "url", "link", "web", "website"):
        return (
            {
                "completitud": {},
                "validez": {"regex_pattern": r"^https?://[^\s/$.?#].[^\s]*$"},
            },
            "Columna de URL: se valida formato de dirección web válida",
        )

    # NIT / RUT / cédula / documento / DNI / RFC
    if _contains(n, "nit", "rut", "cedula", "documento", "dni", "rfc"):
        return (
            {
                "completitud": {},
                "unicidad": {},
                "validez": {"regex_pattern": r"^\d+[-]?\d*$"},
            },
            "Columna de documento: se verifica unicidad y formato numérico",
        )

    # Código postal / zip
    if _contains(n, "zip", "postal", "codigo_postal"):
        return (
            {
                "completitud": {},
                "validez": {"regex_pattern": r"^\d{4,10}$"},
            },
            "Columna de código postal: se valida formato numérico de 4–10 dígitos",
        )

    return None  # sin regla por nombre


# ─────────────────────────────────────────────────────────────────────────────
# Reglas por tipo de dato
# ─────────────────────────────────────────────────────────────────────────────

def _rule_by_type(col_meta: dict) -> Tuple[dict, str]:
    dtype          = col_meta.get("tipo_dato", "object")
    valores_unicos = col_meta.get("valores_unicos", 999)
    total          = col_meta.get("total_registros", 0)
    top_values     = col_meta.get("top_values", [])

    # Numérico entero
    if "int64" in dtype or "int32" in dtype:
        return (
            {"completitud": {}, "razonabilidad": {}},
            "Columna numérica entera: se verifican valores atípicos estadísticos",
        )

    # Numérico flotante
    if "float" in dtype:
        return (
            {
                "completitud": {},
                "razonabilidad": {},
                "precision": {"decimal_places": 2},
            },
            "Columna decimal: se verifican outliers estadísticos y precisión de decimales",
        )

    # Datetime / date
    if "datetime" in dtype or "date" in dtype:
        return (
            {
                "completitud": {},
                "vigencia": {"date_from": _five_years_ago(), "date_to": _today()},
                "consistencia": {},
            },
            "Columna de fecha: se verifica vigencia y consistencia de formato",
        )

    # Boolean
    if "bool" in dtype:
        return (
            {
                "completitud": {},
                "validez": {"valid_values": ["True", "False", "1", "0"]},
            },
            "Columna booleana: se validan los valores permitidos True/False",
        )

    # Texto (object) — caso general
    dims: dict = {"completitud": {}, "consistencia": {}}
    razon = "Columna de texto: se verifica completitud y consistencia de formato"

    if valores_unicos <= 15 and total >= 50 and top_values:
        dims["validez"] = {"valid_values": top_values}
        razon = (
            f"Pocos valores únicos detectados ({valores_unicos}): "
            "se sugiere lista de valores válidos"
        )

    return dims, razon


# ─────────────────────────────────────────────────────────────────────────────
# Función principal
# ─────────────────────────────────────────────────────────────────────────────

def _enrich_from_profile(dims: dict, col_meta: dict, perfil: dict) -> Tuple[dict, str]:
    """
    Refina las dimensiones sugeridas usando el perfil calculado del dataset.
    El perfil añade evidencia real que el nombre de columna no puede dar.
    """
    extra_razones: list[str] = []
    dims = dict(dims)  # copia para no mutar el original

    pct_nulos        = perfil.get("pct_nulos", 0) or 0
    es_catalogo      = perfil.get("es_catalogo", False)
    top_values       = [v["valor"] for v in (perfil.get("top_10_valores") or perfil.get("valores", []))]
    mayusculas       = perfil.get("tiene_mayusculas_mezcladas", False)
    outliers_count   = perfil.get("outliers_count", 0) or 0
    formato          = perfil.get("formato_detectado", "")
    cardinalidad     = perfil.get("cardinalidad", "")
    variantes        = perfil.get("variantes_similares", [])

    if pct_nulos > 5:
        dims["completitud"] = {}
        extra_razones.append(f"{pct_nulos}% de nulos detectados")

    if es_catalogo and top_values:
        dims["validez"] = {"valid_values": top_values}
        extra_razones.append(f"catálogo con {len(top_values)} valores únicos detectados")

    if mayusculas:
        dims["consistencia"] = {}
        extra_razones.append("mayúsculas mezcladas detectadas")

    if outliers_count > 0:
        dims["razonabilidad"] = {}
        extra_razones.append(f"{outliers_count} outliers estadísticos detectados")

    if formato == "email":
        dims["validez"] = {"regex_pattern": (
            r"^[a-zA-Z0-9_.+\-À-ɏ]+"
            r"@[a-zA-Z0-9\-À-ɏ]+"
            r"\.[a-zA-Z0-9\-.À-ɏ]+$"
        )}
        extra_razones.append("formato email detectado en los datos")

    if formato == "fecha":
        dims["vigencia"] = {"date_from": _five_years_ago(), "date_to": _today()}
        dims["consistencia"] = {}
        extra_razones.append("formato fecha detectado en los datos")

    if cardinalidad == "baja" and variantes:
        dims["consistencia"] = {}
        extra_razones.append(f"{len(variantes)} grupos de variantes similares detectados")

    return dims, extra_razones


def suggest_dimensions_rules(
    columns_metadata: list[dict],
    perfil_columnas: Optional[dict] = None,
) -> dict:
    """
    Sugiere dimensiones de calidad para cada columna basándose en su
    nombre, tipo de dato y (si se provee) perfil calculado del dataset.

    Args:
        columns_metadata: lista de dicts con claves:
            nombre, tipo_dato, total_registros, valores_nulos,
            valores_unicos (opcional), top_values (opcional)
        perfil_columnas: dict {col_name: perfil_dict} del engine/profiler.py (opcional).
            Cuando se provee, las sugerencias son mucho más precisas.

    Returns:
        {
          "sugerencias": {
            "<col_name>": {
              "dimensiones": { "<dim>": {<params>}, ... },
              "razon": "<texto en español>",
              "enriquecido_con_perfil": bool
            }, ...
          },
          "ia_disponible": False,
          "motor": "rules+profile" | "rules"
        }
    """
    sugerencias: dict = {}

    for col_meta in columns_metadata:
        col_name = col_meta.get("nombre", "")
        if not col_name:
            continue

        result = _rule_by_name(col_name)
        if result is None:
            result = _rule_by_type(col_meta)

        dims, razon = result

        # Siempre incluir completitud como mínimo
        if "completitud" not in dims:
            dims = {"completitud": {}, **dims}

        enriquecido = False
        if perfil_columnas and col_name in perfil_columnas:
            perfil = perfil_columnas[col_name]
            dims, extra_razones = _enrich_from_profile(dims, col_meta, perfil)
            if extra_razones:
                razon += " · Perfil real: " + "; ".join(extra_razones)
                enriquecido = True

        sugerencias[col_name] = {
            "dimensiones": dims,
            "razon": razon,
            "enriquecido_con_perfil": enriquecido,
        }

    motor = "rules+profile" if perfil_columnas else "rules"
    return {
        "sugerencias": sugerencias,
        "ia_disponible": False,
        "motor": motor,
        "total_columnas": len(sugerencias),
    }
