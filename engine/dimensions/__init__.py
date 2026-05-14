from .completitud import check_completitud
from .unicidad import check_unicidad
from .validez import check_validez
from .consistencia import check_consistencia
from .exactitud import check_exactitud
from .vigencia import check_vigencia
from .precision import check_precision
from .oportunidad import check_oportunidad
from .integridad_referencial import check_integridad_referencial
from .razonabilidad import check_razonabilidad

DIMENSIONS_MAP = {
    "completitud": check_completitud,
    "unicidad": check_unicidad,
    "validez": check_validez,
    "consistencia": check_consistencia,
    "exactitud": check_exactitud,
    "vigencia": check_vigencia,
    "precision": check_precision,
    "oportunidad": check_oportunidad,
    "integridad_referencial": check_integridad_referencial,
    "razonabilidad": check_razonabilidad,
}
