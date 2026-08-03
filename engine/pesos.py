"""
Matriz de criticidad por propósito de análisis.
Fuente: marco metodológico de calidad de datos para iniciativas de IA.
Mantener sincronizado con el artículo. Los overrides del admin viven en
la tabla pesos_config y se resuelven en obtener_pesos().
"""

NIVELES = {
    'critica':     4,
    'alta':        3,
    'media':       2,
    'informativa': 1,
}

DIMENSIONES = [
    'completitud', 'unicidad', 'validez', 'consistencia', 'exactitud',
    'vigencia', 'precision', 'oportunidad', 'integridad_referencial',
    'razonabilidad', 'similitud',
]

MATRIZ_PROPOSITOS = {
    'diagnostico_general': {
        'completitud': 'alta', 'unicidad': 'alta', 'validez': 'alta',
        'consistencia': 'alta', 'exactitud': 'alta', 'vigencia': 'alta',
        'precision': 'media', 'oportunidad': 'media',
        'integridad_referencial': 'media', 'razonabilidad': 'media',
        'similitud': 'media',
    },
    'reporteria_bi': {
        'unicidad': 'critica', 'completitud': 'critica',
        'similitud': 'alta', 'consistencia': 'alta', 'validez': 'alta',
        'exactitud': 'media', 'integridad_referencial': 'media',
        'razonabilidad': 'media', 'vigencia': 'media',
        'precision': 'informativa', 'oportunidad': 'informativa',
    },
    'migracion': {
        'integridad_referencial': 'critica', 'completitud': 'critica',
        'validez': 'critica',
        'unicidad': 'alta', 'consistencia': 'alta', 'precision': 'alta',
        'exactitud': 'media', 'vigencia': 'media', 'similitud': 'media',
        'razonabilidad': 'informativa', 'oportunidad': 'informativa',
    },
    'integracion': {
        'consistencia': 'critica', 'validez': 'critica', 'precision': 'critica',
        'integridad_referencial': 'alta', 'completitud': 'alta',
        'unicidad': 'media', 'exactitud': 'media', 'vigencia': 'media',
        'oportunidad': 'media',
        'similitud': 'informativa', 'razonabilidad': 'informativa',
    },
    'auditoria': {
        'exactitud': 'critica', 'completitud': 'critica', 'vigencia': 'critica',
        'integridad_referencial': 'alta', 'validez': 'alta',
        'unicidad': 'alta', 'oportunidad': 'alta',
        'consistencia': 'media', 'precision': 'media',
        'razonabilidad': 'media', 'similitud': 'media',
    },
    'depuracion_duplicados': {
        'similitud': 'critica', 'unicidad': 'critica',
        'completitud': 'alta', 'consistencia': 'alta',
        'validez': 'media', 'precision': 'media',
        'exactitud': 'informativa', 'vigencia': 'informativa',
        'oportunidad': 'informativa', 'integridad_referencial': 'informativa',
        'razonabilidad': 'informativa',
    },
    'campanas': {
        'validez': 'critica', 'completitud': 'critica', 'similitud': 'critica',
        'unicidad': 'alta', 'vigencia': 'alta', 'consistencia': 'alta',
        'oportunidad': 'media', 'precision': 'media',
        'integridad_referencial': 'media',
        'exactitud': 'informativa', 'razonabilidad': 'informativa',
    },
}

MATRIZ_TIPOS_IA = {
    'ml_supervisado': {
        'completitud': 'critica', 'similitud': 'critica', 'exactitud': 'critica',
        'unicidad': 'alta', 'consistencia': 'alta', 'razonabilidad': 'alta',
        'validez': 'alta',
        'integridad_referencial': 'media', 'precision': 'media', 'vigencia': 'media',
        'oportunidad': 'informativa',
    },
    'deteccion_anomalias': {
        'oportunidad': 'critica', 'precision': 'critica', 'exactitud': 'critica',
        'similitud': 'alta', 'completitud': 'alta', 'razonabilidad': 'alta',
        'vigencia': 'alta',
        'consistencia': 'media', 'unicidad': 'media', 'validez': 'media',
        'integridad_referencial': 'informativa',
    },
    'series_tiempo': {
        'oportunidad': 'critica', 'vigencia': 'critica', 'completitud': 'critica',
        'exactitud': 'alta', 'consistencia': 'alta', 'razonabilidad': 'alta',
        'precision': 'media', 'unicidad': 'media', 'validez': 'media',
        'similitud': 'informativa', 'integridad_referencial': 'informativa',
    },
    'segmentacion': {
        'completitud': 'critica', 'consistencia': 'critica',
        'validez': 'alta', 'similitud': 'alta', 'unicidad': 'alta',
        'razonabilidad': 'alta',
        'exactitud': 'media', 'integridad_referencial': 'media', 'precision': 'media',
        'vigencia': 'informativa', 'oportunidad': 'informativa',
    },
    'agente_generativo': {
        'vigencia': 'critica', 'consistencia': 'critica', 'similitud': 'critica',
        'completitud': 'alta', 'validez': 'alta', 'oportunidad': 'alta',
        'exactitud': 'media', 'integridad_referencial': 'media', 'unicidad': 'media',
        'precision': 'informativa', 'razonabilidad': 'informativa',
    },
    'recomendacion': {
        'similitud': 'critica', 'unicidad': 'critica',
        'completitud': 'alta', 'integridad_referencial': 'alta',
        'consistencia': 'alta',
        'validez': 'media', 'vigencia': 'media', 'oportunidad': 'media',
        'exactitud': 'media',
        'precision': 'informativa', 'razonabilidad': 'informativa',
    },
}


def obtener_pesos(proposito, tipo_ia=None, conn=None):
    """
    Resuelve los niveles de criticidad para un propósito.
    Prioridad: override en pesos_config > valor del artículo.
    Retorna dict {dimension: nivel}.
    """
    if proposito == 'iniciativa_ia' and tipo_ia:
        base = dict(MATRIZ_TIPOS_IA.get(tipo_ia, MATRIZ_PROPOSITOS['diagnostico_general']))
    else:
        base = dict(MATRIZ_PROPOSITOS.get(proposito, MATRIZ_PROPOSITOS['diagnostico_general']))

    if conn is not None:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT dimension, nivel FROM pesos_config
                WHERE proposito = ? AND (tipo_ia = ? OR (tipo_ia IS NULL AND ? IS NULL))
            """, (proposito, tipo_ia, tipo_ia))
            for dim, nivel in cursor.fetchall():
                base[dim] = nivel
        except Exception:
            pass  # table may not exist yet on first run

    return base


def pesos_iguales():
    """Todas las dimensiones en nivel media — equivale al promedio simple."""
    return {d: 'media' for d in DIMENSIONES}


def peso_numerico(nivel):
    return NIVELES.get(nivel, 2)
