NATURALEZA_DATO = {
    'maestro': {
        'label': 'Maestro de datos',
        'desc': 'Entidades únicas del negocio: clientes, proveedores, productos, empleados. Cada fila representa una entidad distinta.'
    },
    'transaccional': {
        'label': 'Dataset transaccional',
        'desc': 'Movimientos u operaciones: órdenes, facturas, pagos, despachos. Una misma entidad puede aparecer en muchas filas.'
    },
    'sin_especificar': {
        'label': 'Sin especificar',
        'desc': 'Si no aplica ninguna de las anteriores o prefieres no clasificar el dataset.'
    },
}

PROPOSITO_ANALISIS = {
    'diagnostico_general': {
        'label': 'Diagnóstico general',
        'desc': 'Revisión de calidad sin un objetivo específico. Todas las dimensiones se evalúan con la misma importancia.'
    },
    'iniciativa_ia': {
        'label': 'Iniciativa de IA',
        'desc': 'Los datos alimentarán un modelo predictivo, un agente o una automatización. Requiere especificar el tipo de iniciativa.'
    },
    'reporteria_bi': {
        'label': 'Reportería y BI',
        'desc': 'Los datos irán a tableros o informes de gestión. Un duplicado infla cifras que se presentan a la dirección.'
    },
    'migracion': {
        'label': 'Migración de sistema',
        'desc': 'Los datos se cargarán en otro sistema. Las claves huérfanas y los formatos inválidos bloquean la carga.'
    },
    'integracion': {
        'label': 'Integración entre sistemas',
        'desc': 'Los datos fluyen automáticamente entre aplicaciones. Los formatos mezclados rompen el flujo o lo procesan mal en silencio.'
    },
    'auditoria': {
        'label': 'Auditoría y cumplimiento',
        'desc': 'Los datos serán revisados por auditoría interna o un regulador. La exactitud y la trazabilidad temporal son lo que se revisa.'
    },
    'depuracion_duplicados': {
        'label': 'Depuración de duplicados',
        'desc': 'El objetivo principal es encontrar registros repetidos o variantes de la misma entidad para consolidarlos.'
    },
    'campanas': {
        'label': 'Campañas comerciales',
        'desc': 'Los datos se usarán para contactar clientes. Un correo inválido es dinero perdido; un duplicado molesta al cliente.'
    },
}

TIPOS_IA = {
    'ml_supervisado': {
        'label': 'ML supervisado',
        'desc': 'Clasificación, regresión o scoring. El modelo aprende de datos históricos etiquetados.'
    },
    'deteccion_anomalias': {
        'label': 'Detección de anomalías',
        'desc': 'Fraude, comportamiento inusual o valores fuera de patrón.'
    },
    'series_tiempo': {
        'label': 'Series de tiempo',
        'desc': 'Pronóstico de demanda, proyecciones o cualquier predicción basada en secuencia temporal.'
    },
    'segmentacion': {
        'label': 'Segmentación',
        'desc': 'Clustering o perfilamiento de clientes sin etiquetas previas.'
    },
    'agente_generativo': {
        'label': 'Agente generativo',
        'desc': 'RAG, asistentes conversacionales o automatización con modelos de lenguaje.'
    },
    'recomendacion': {
        'label': 'Sistema de recomendación',
        'desc': 'Cross-sell, personalización o sugerencia de productos.'
    },
}
