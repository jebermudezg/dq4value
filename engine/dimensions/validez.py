import re
import pandas as pd


# ─── Motivo helpers ──────────────────────────────────────────────────────────

_VOCALES_ACENTUADAS = set('áéíóúàèìòùâêîôûäëïöüÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÄËÏÖÜ')


def _motivo_email(valor: str) -> str:
    """Devuelve una descripción precisa de por qué el correo es inválido."""
    v = str(valor).strip()
    if not v:
        return "está vacío"
    if " " in v:
        return "contiene espacios"
    if "@" not in v:
        return "no contiene @"
    if v.count("@") > 1:
        return "contiene más de un @"
    local, _, dom = v.rpartition("@")
    if not local:
        return "falta el usuario antes del @"
    if not dom:
        return "falta el dominio después del @"
    if "." not in dom:
        return "el dominio no tiene punto"
    if ".." in v:
        return "contiene dos puntos seguidos"
    if any(c in _VOCALES_ACENTUADAS for c in v):
        return "contiene vocales con tilde — probable error de captura"
    return "no cumple el formato de correo"


def _motivo_telefono(valor: str) -> str:
    """Devuelve una descripción precisa de por qué el teléfono es inválido."""
    v = str(valor).strip()
    if not v:
        return "está vacío"
    # Solo dígitos, espacios, +, -, (, )
    letras = [c for c in v if c.isalpha()]
    if letras:
        return f"contiene letras ('{letras[0]}')"
    invalidos = [c for c in v if c not in "0123456789 +-()"]
    if invalidos:
        return f"contiene el carácter no permitido '{invalidos[0]}'"
    solo_digitos = re.sub(r"[^\d]", "", v)
    if len(solo_digitos) < 7:
        return f"tiene solo {len(solo_digitos)} dígitos — mínimo 7"
    if len(v) > 15:
        return f"tiene {len(v)} caracteres — máximo 15"
    return "no cumple el formato de teléfono"


def _motivo_url(valor: str) -> str:
    """Devuelve una descripción precisa de por qué la URL es inválida."""
    v = str(valor).strip()
    if not v:
        return "está vacía"
    if " " in v:
        return "contiene espacios"
    if not v.startswith(("http://", "https://")):
        return "no empieza con http:// o https://"
    return "no cumple el formato de URL"


def _motivo_nit(valor: str) -> str:
    """Devuelve una descripción precisa de por qué el NIT/RUC es inválido."""
    v = str(valor).strip()
    if not v:
        return "está vacío"
    letras = [c for c in v if c.isalpha()]
    if letras:
        return f"contiene letras ('{letras[0]}') — solo se permiten dígitos y guion"
    invalidos = [c for c in v if c not in "0123456789-"]
    if invalidos:
        return f"contiene el carácter no permitido '{invalidos[0]}'"
    return "no cumple el formato de NIT/RUC (dígitos con guion opcional)"


# Mapa de formato_tipo → función motivo
_MOTIVO_POR_TIPO = {
    "email":    _motivo_email,
    "telefono": _motivo_telefono,
    "url":      _motivo_url,
    "nit":      _motivo_nit,
}


# ─── Dimensión principal ─────────────────────────────────────────────────────

def check_validez(df: pd.DataFrame, id_col: str, target_col: str, **params) -> tuple[float, pd.DataFrame]:
    """
    Valida valores contra una lista permitida (valid_values) o un regex (regex_pattern).
    Si no se pasa ninguno, score = 100.

    Parámetros opcionales:
        valid_values  : list[str] — valores permitidos
        regex_pattern : str       — expresión regular
        formato_tipo  : str       — "email" | "telefono" | "url" | "nit"
                        Habilita mensajes de error precisos en lugar del genérico
                        "Formato inválido: {valor}".
    """
    valid_values  = params.get("valid_values")
    regex_pattern = params.get("regex_pattern")
    formato_tipo  = params.get("formato_tipo")

    total = len(df)
    if total == 0 or (valid_values is None and regex_pattern is None):
        return 100.0, _empty_issues(id_col), {}

    col = df[target_col].astype(str)

    if valid_values is not None:
        valid_set = {str(v) for v in valid_values}
        invalidos_mask = ~col.isin(valid_set) & df[target_col].notna()
    else:
        pattern = re.compile(regex_pattern)
        invalidos_mask = ~col.apply(lambda v: bool(pattern.fullmatch(v))) & df[target_col].notna()

    n_validos = total - invalidos_mask.sum()
    score = (n_validos / total) * 100

    issues_df = df[invalidos_mask][[id_col]].copy()
    issues_df["valor_encontrado"] = df.loc[invalidos_mask, target_col].values
    issues_df["columna"]   = target_col
    issues_df["dimension"] = "validez"

    if valid_values is not None:
        valores_str = ", ".join(str(v) for v in valid_values[:10])
        if len(valid_values) > 10:
            valores_str += f" … (y {len(valid_values) - 10} más)"
        issues_df["descripcion"] = issues_df["valor_encontrado"].apply(
            lambda v: (
                f"Valor '{v}' no está en la lista de valores permitidos. "
                f"Valores válidos: {valores_str}"
            )
        )
    else:
        motivo_fn = _MOTIVO_POR_TIPO.get(formato_tipo) if formato_tipo else None
        if motivo_fn is not None:
            prefix = {
                "email":    "Correo inválido",
                "telefono": "Teléfono inválido",
                "url":      "URL inválida",
                "nit":      "NIT/RUC inválido",
            }.get(formato_tipo, "Valor inválido")
            issues_df["descripcion"] = issues_df["valor_encontrado"].apply(
                lambda v: f"{prefix} ({motivo_fn(str(v))}): {v}"
            )
        else:
            issues_df["descripcion"] = issues_df["valor_encontrado"].apply(
                lambda v: f"Formato inválido: {v}"
            )

    return round(score, 2), issues_df.reset_index(drop=True), {}


def _empty_issues(id_col: str) -> pd.DataFrame:
    return pd.DataFrame(columns=[id_col, "columna", "dimension", "descripcion", "valor_encontrado"])
