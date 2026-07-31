"""
Traducción de nombres técnicos de dimensiones a nombres de negocio.
Solo para capa de presentación — las llaves técnicas nunca cambian.
"""

NOMBRES_NEGOCIO = {
    'completitud':            'Datos faltantes',
    'unicidad':               'Duplicados exactos',
    'validez':                'Valores permitidos',
    'consistencia':           'Formatos uniformes',
    'exactitud':              'Rangos válidos',
    'vigencia':               'Fechas fuera de período',
    'precision':              'Longitud y decimales',
    'oportunidad':            'Datos sin actualizar',
    'integridad_referencial': 'Códigos que no existen',
    'razonabilidad':          'Valores atípicos',
    'similitud':              'Registros parecidos',
}


def nombre_negocio(clave_tecnica: str) -> str:
    """Retorna el nombre de negocio. Si no existe, retorna la clave capitalizada."""
    return NOMBRES_NEGOCIO.get(clave_tecnica, clave_tecnica.replace('_', ' ').capitalize())


def nombre_dual(clave_tecnica: str) -> str:
    """Retorna 'Nombre de negocio (tecnico)' para Excel y reportes."""
    negocio = nombre_negocio(clave_tecnica)
    return f"{negocio} ({clave_tecnica.replace('_', ' ')})"
