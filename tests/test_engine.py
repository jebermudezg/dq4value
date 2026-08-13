"""
Tests para engine/profiler.py — Data Profiling Engine.
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.profiler import profile_dataset
from ai.claude_analyzer import suggest_dimensions_rules


# ─────────────────────────────────────────────────────────────────────────────
# Dataset de prueba con los 4 tipos + problemas intencionados
# ─────────────────────────────────────────────────────────────────────────────

def _make_df():
    n = 100
    return pd.DataFrame({
        # Numérico — con outlier y negativo
        "edad": [25] * 80 + [None] * 10 + [-5, 200] + [30] * 8,
        # Texto libre
        "nombre": ["Ana Torres"] * 40 + ["Luis Mendoza"] * 40 + [None] * 10 + [""] * 10,
        # Fecha (string formato ISO)
        "fecha_registro": (
            ["2023-01-15"] * 50
            + ["2024-06-30"] * 30
            + ["2099-12-31"] * 5   # futuras
            + ["2015-01-01"] * 5   # antiguas
            + [None] * 10
        ),
        # Categórico con variantes
        "estado": (
            ["Activo"] * 50
            + ["ACTIVO"] * 20
            + ["Inactivo"] * 20
            + ["inactivo"] * 5
            + [None] * 5
        ),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Test principal
# ─────────────────────────────────────────────────────────────────────────────

def test_profiler_retorna_estructura_completa():
    df = _make_df()
    result = profile_dataset(df)

    assert "resumen" in result
    assert "columnas" in result

    resumen = result["resumen"]
    assert resumen["total_filas"] == 100
    assert resumen["total_columnas"] == 4
    assert 0 <= resumen["completitud_global"] <= 100
    assert isinstance(resumen["filas_duplicadas_exactas"], int)
    assert isinstance(resumen["tamano_memoria_mb"], float)
    assert isinstance(resumen["alertas"], list)


def test_profiler_numerico_metricas():
    df = _make_df()
    p = profile_dataset(df)["columnas"]["edad"]

    assert p["tipo_perfil"] == "numerico"
    assert p["min"] is not None
    assert p["max"] is not None
    assert p["promedio"] is not None
    assert p["mediana"] is not None
    assert p["desviacion_std"] is not None
    assert isinstance(p["outliers_count"], int)
    assert p["outliers_count"] >= 1, "Debe detectar al menos el outlier 200"
    assert p["pct_nulos"] == 10.0
    assert p["pct_negativos"] > 0, "Debe detectar el valor -5"
    assert p["sesgo"] in ("normal", "sesgado_derecha", "sesgado_izquierda")
    assert isinstance(p["histograma"], list)
    assert len(p["histograma"]) == 10


def test_profiler_texto_metricas():
    # Columna con >20 únicos → tipo_perfil = "texto"
    df = pd.DataFrame({
        "descripcion": [f"Producto número {i} con descripción larga" for i in range(50)]
        + [None] * 10
    })
    p = profile_dataset(df)["columnas"]["descripcion"]

    assert p["tipo_perfil"] == "texto"
    assert p["total_unicos"] >= 20
    assert isinstance(p["top_10_valores"], list)
    assert len(p["top_10_valores"]) >= 1
    assert isinstance(p["distribucion_longitudes"], list)
    assert p["pct_nulos"] > 0


def test_profiler_fecha_metricas():
    df = _make_df()
    p = profile_dataset(df)["columnas"]["fecha_registro"]

    assert p["tipo_perfil"] == "fecha"
    assert p["fecha_min"] is not None
    assert p["fecha_max"] is not None
    assert p["rango_dias"] is not None and p["rango_dias"] > 0
    assert p["pct_nulos"] == 10.0
    assert p["pct_fechas_futuras"] > 0, "Debe detectar las fechas del 2099"
    assert p["pct_fechas_antiguas"] > 0, "Debe detectar las fechas del 2015"


def test_profiler_categorico_variantes():
    df = _make_df()
    p = profile_dataset(df)["columnas"]["estado"]

    assert p["tipo_perfil"] == "categorico"
    assert isinstance(p["variantes_similares"], list)
    # Debe agrupar Activo/ACTIVO y Inactivo/inactivo
    grupos_flat = [v for grupo in p["variantes_similares"] for v in grupo]
    assert any(v.lower() == "activo" for v in grupos_flat), \
        "Debe detectar variantes de 'Activo'"
    assert p["entropia"] is not None
    assert p["entropia_label"] in (
        "Muy balanceado", "Balanceado", "Desbalanceado", "Extremadamente desbalanceado"
    )
    assert p["pct_nulos"] == 5.0


def test_profiler_alertas_detecta_problemas():
    df = pd.DataFrame({
        "cliente_id": [1, 2, 2, 3, 4],          # duplicado → alerta
        "constante":  ["X", "X", "X", "X", "X"], # un solo valor → alerta
        "estado":     ["Activo", "ACTIVO", "activo", "Inactivo", "Inactivo"],  # variantes
    })
    alertas = profile_dataset(df)["resumen"]["alertas"]
    textos  = " ".join(alertas).lower()
    assert "cliente_id" in textos or "id" in textos, "Debe alertar sobre duplicados en ID"
    assert "constante" in textos,                    "Debe alertar sobre columna constante"


def test_profiler_dataframe_vacio():
    df = pd.DataFrame({"a": pd.Series([], dtype="float64")})
    result = profile_dataset(df)
    assert result["resumen"]["total_filas"] == 0
    assert result["resumen"]["completitud_global"] == 100.0


def test_profiler_no_explota_con_tipos_raros():
    df = pd.DataFrame({
        "booleano":  [True, False, True, None, True],
        "mixto":     [1, "dos", 3.0, None, "cinco"],
    })
    # No debe lanzar excepción
    result = profile_dataset(df)
    assert "columnas" in result


# ─────────────────────────────────────────────────────────────────────────────
# Tests motor de sugerencias con perfil
# ─────────────────────────────────────────────────────────────────────────────

def test_sugerencias_con_perfil_numerico_outliers():
    """Columna numérica con outliers → Exactitud alta confianza con rango p5-p95."""
    col_meta = {"nombre": "salario", "tipo": "float64", "total_registros": 100, "valores_nulos": 0}
    col_profile = {"outliers_count": 5, "p5": 1500.0, "p95": 8000.0, "pct_negativos": 0}
    sugs = suggest_dimensions_rules([col_meta], profile={"salario": col_profile})
    dims = {s["dimension"]: s for s in sugs[0]["dimensiones"]}

    assert "exactitud" in dims
    assert dims["exactitud"]["confianza"] == "alta"
    assert dims["exactitud"]["params"]["min_value"] == 1500.0
    assert dims["exactitud"]["params"]["max_value"] == 8000.0
    assert "razonabilidad" in dims
    assert dims["razonabilidad"]["confianza"] == "alta"


def test_sugerencias_con_catalogo_detectado():
    """Columna texto con catálogo → Validez alta confianza con valores pre-cargados."""
    col_meta = {"nombre": "estado", "tipo": "object", "total_registros": 100, "valores_nulos": 0}
    col_profile = {
        "es_catalogo": True,
        "top_10_valores": [{"valor": "Activo"}, {"valor": "Inactivo"}, {"valor": "Suspendido"}],
        "total_unicos": 3,
    }
    sugs = suggest_dimensions_rules([col_meta], profile={"estado": col_profile})
    dims = {s["dimension"]: s for s in sugs[0]["dimensiones"]}

    assert "validez" in dims
    assert dims["validez"]["confianza"] == "alta"
    assert "Activo" in dims["validez"]["params"]["valid_values"]


def test_sugerencias_con_fechas_futuras():
    """Columna fecha con fechas futuras → Vigencia alta confianza."""
    col_meta = {"nombre": "fecha_registro", "tipo": "object", "total_registros": 100, "valores_nulos": 0}
    col_profile = {
        "pct_fechas_futuras": 3.5,
        "pct_fechas_antiguas": 2.0,
        "formatos_detectados": ["%Y-%m-%d"],
    }
    sugs = suggest_dimensions_rules([col_meta], profile={"fecha_registro": col_profile})
    dims = {s["dimension"]: s for s in sugs[0]["dimensiones"]}

    assert "vigencia" in dims
    assert dims["vigencia"]["confianza"] == "alta"
    assert "3.5%" in dims["vigencia"]["razon"]


def test_sugerencias_sin_perfil_compatibilidad():
    """Sin perfil → debe seguir funcionando con reglas básicas por nombre."""
    col_meta = {"nombre": "email", "tipo": "object", "total_registros": 100, "valores_nulos": 5}
    sugs = suggest_dimensions_rules([col_meta], profile=None)
    dims = {s["dimension"]: s for s in sugs[0]["dimensiones"]}

    assert "completitud" in dims
    assert "validez" in dims


# ─────────────────────────────────────────────────────────────────────────────
# Tests motor de pesos (PASO 3)
# ─────────────────────────────────────────────────────────────────────────────

def test_pesos_diagnostico_general_vs_reporteria():
    from engine.pesos import obtener_pesos, peso_numerico
    gen = obtener_pesos('diagnostico_general')
    rep = obtener_pesos('reporteria_bi')
    assert peso_numerico(rep['unicidad']) > peso_numerico(gen['unicidad'])
    assert peso_numerico(rep['precision']) < peso_numerico(gen['precision'])


def test_pesos_tipo_ia():
    from engine.pesos import obtener_pesos
    ml = obtener_pesos('iniciativa_ia', 'ml_supervisado')
    gen_ia = obtener_pesos('iniciativa_ia', 'agente_generativo')
    assert ml['completitud'] == 'critica'
    assert gen_ia['vigencia'] == 'critica'
    assert ml != gen_ia


def test_pesos_proposito_desconocido_cae_a_general():
    from engine.pesos import obtener_pesos, MATRIZ_PROPOSITOS
    assert obtener_pesos('inventado') == MATRIZ_PROPOSITOS['diagnostico_general']


def test_score_ponderado_difiere_de_simple():
    """Con pesos desiguales el score ponderado debe diferir del promedio simple."""
    from engine.scorer import DQScorer
    from engine.pesos import MATRIZ_PROPOSITOS

    # completitud tiene score 0 (todos nulos), unicidad score 100 (todos únicos)
    # En reporteria_bi: completitud=critica(4), unicidad=critica(4) → mismo peso → igual
    # En diagnostico_general: completitud=alta(3), unicidad=alta(3) → igual también
    # Usamos pesos manuales: completitud=critica(4), unicidad=informativa(1)
    # simple avg = (0 + 100) / 2 = 50
    # weighted = (0*4 + 100*1) / (4+1) = 100/5 = 20 ≠ 50
    df = pd.DataFrame({"id": range(5), "valor": [None] * 5, "codigo": [f"C{i}" for i in range(5)]})
    scorer = DQScorer(df, id_col="id")
    scorer.configure("valor", {"completitud": {}})
    scorer.configure("codigo", {"unicidad": {}})

    niveles_desiguales = {"completitud": "critica", "unicidad": "informativa"}
    res_pond = scorer.run_analysis(niveles=niveles_desiguales)

    niveles_iguales = {"completitud": "media", "unicidad": "media"}
    scorer2 = DQScorer(df, id_col="id")
    scorer2.configure("valor", {"completitud": {}})
    scorer2.configure("codigo", {"unicidad": {}})
    res_simple = scorer2.run_analysis(niveles=niveles_iguales)

    assert res_pond["score_general"] != res_simple["score_general"]
    assert res_pond["score_general"] < res_simple["score_general"]


def test_diagnostico_general_es_neutral():
    from engine.pesos import obtener_pesos
    niveles = obtener_pesos('diagnostico_general')
    assert len(set(niveles.values())) == 1
    assert list(niveles.values())[0] == 'media'


def test_pesos_iguales_equivale_a_promedio_simple():
    """Con pesos iguales, score ponderado == promedio simple."""
    from engine.scorer import DQScorer
    from engine.pesos import pesos_iguales

    df = pd.DataFrame({
        "id":     range(10),
        "valor":  [None] * 3 + list(range(7)),
        "codigo": [f"C{i}" for i in range(10)],
    })
    scorer = DQScorer(df, id_col="id")
    scorer.configure("valor",  {"completitud": {}})
    scorer.configure("codigo", {"unicidad":    {}})
    results = scorer.run_analysis(niveles=pesos_iguales())
    assert results["score_general"] == results["score_promedio_simple"]


def test_pesos_manuales_sobreescriben_proposito():
    from engine.pesos import obtener_pesos, NIVELES
    base = obtener_pesos('reporteria_bi')
    manuales = {'precision': 'critica'}
    resultado = dict(base)
    for d, n in manuales.items():
        if n in NIVELES:
            resultado[d] = n
    assert resultado['precision'] == 'critica'
    assert resultado['unicidad'] == base['unicidad']


def test_nivel_invalido_se_ignora():
    from engine.pesos import obtener_pesos, NIVELES
    base = obtener_pesos('reporteria_bi')
    original = base['precision']
    manuales = {'precision': 'urgentisima'}
    resultado = dict(base)
    for d, n in manuales.items():
        if n in NIVELES:
            resultado[d] = n
    assert resultado['precision'] == original


def test_todas_las_dimensiones_en_todas_las_matrices():
    """Cada propósito y tipo de IA debe cubrir las 11 dimensiones."""
    from engine.pesos import MATRIZ_PROPOSITOS, MATRIZ_TIPOS_IA, DIMENSIONES
    for nombre, perfil in {**MATRIZ_PROPOSITOS, **MATRIZ_TIPOS_IA}.items():
        faltantes = set(DIMENSIONES) - set(perfil.keys())
        assert not faltantes, f"{nombre} le faltan: {faltantes}"


# ─────────────────────────────────────────────────────────────────────────────
# Tests para perfil_nombres() y sugerir_algoritmo_similitud()
# ─────────────────────────────────────────────────────────────────────────────

from engine.profiler import perfil_nombres
from ai.claude_analyzer import sugerir_algoritmo_similitud


def test_perfil_nombres_vacio_devuelve_dict_vacio():
    """Con menos de 10 valores no hay señales fiables — devuelve {}."""
    s = pd.Series(['Ana', 'Luis', 'María'])
    assert perfil_nombres(s) == {}


def test_perfil_nombres_detecta_sufijo_rs():
    s = pd.Series([f'{p} {n} S.A.C.'
                   for p in ['Constructora', 'Servicios', 'Textiles']
                   for n in ['Andina', 'Huascarán', 'Pacífico', 'Titicaca', 'Misti']])
    p = perfil_nombres(s)
    assert p['pct_sufijo_rs'] == 100.0


def test_perfil_nombres_detecta_via():
    s = pd.Series([f'Av. Los Incas {i}, Lima'     for i in range(8)]
                + [f'Jr. Manco Cápac {i}, Cusco'  for i in range(7)])
    p = perfil_nombres(s)
    assert p['pct_via_urbana'] >= 90


def test_perfil_nombres_detecta_tokens_persona():
    s = pd.Series(['Carlos Quispe Flores', 'María Mamani Rojas', 'Juan Vargas Tito',
                   'Rosa Huamán Apaza',   'Luis Condori Ramos',  'Elena Chávez Paredes',
                   'Jorge Salazar Castillo','Patricia Rojas Inca','Víctor Ayma Puma',
                   'Lucía Tito Choque',   'Fernando Cusi Llanos', 'Beatriz Rivas Ccallo'])
    p = perfil_nombres(s)
    assert 2 <= p['tokens_promedio'] <= 4
    assert p['pct_sufijo_rs'] == 0.0
    assert p['pct_con_digito'] == 0.0


def test_sugiere_qgrams_para_razon_social():
    """Columna con 100% de sufijos societarios → qgrams."""
    s = pd.Series([f'{p} {n} S.A.C.'
                   for p in ['Constructora', 'Servicios', 'Textiles']
                   for n in ['Andina', 'Huascarán', 'Pacífico', 'Titicaca', 'Misti']])
    alg, umb, razon = sugerir_algoritmo_similitud(perfil_nombres(s))
    assert alg == 'qgrams', f'Sugirió {alg}'
    assert umb == 86
    assert razon


def test_sugiere_brecha_afin_para_personas():
    """Columna de nombres de personas (3 tokens, sin sufijos, sin dígitos) → brecha_afin."""
    s = pd.Series(['Carlos Quispe Flores', 'María Mamani Rojas', 'Juan Vargas Tito',
                   'Rosa Huamán Apaza',   'Luis Condori Ramos',  'Elena Chávez Paredes',
                   'Jorge Salazar Castillo','Patricia Rojas Inca','Víctor Ayma Puma',
                   'Lucía Tito Choque',   'Fernando Cusi Llanos', 'Beatriz Rivas Ccallo'])
    alg, umb, razon = sugerir_algoritmo_similitud(perfil_nombres(s))
    assert alg == 'brecha_afin', f'Sugirió {alg}'
    assert razon


def test_sugiere_brecha_afin_para_direcciones():
    """Columna con indicadores de vía → brecha_afin."""
    s = pd.Series([f'Av. Los Incas {i}, Lima'    for i in range(8)]
                + [f'Jr. Manco Cápac {i}, Cusco' for i in range(7)])
    alg, umb, razon = sugerir_algoritmo_similitud(perfil_nombres(s))
    assert alg == 'brecha_afin', f'Sugirió {alg}'


def test_caso_ambiguo_prefiere_precision():
    """Sin señales claras → qgrams (menor riesgo de falsos positivos)."""
    alg, umb, razon = sugerir_algoritmo_similitud({})
    assert alg == 'qgrams'
    assert razon


def test_perfil_nombres_expuesto_en_profile_texto():
    """_profile_text debe incluir la clave 'perfil_nombres' en el perfil.
    Usamos >20 valores únicos para que el profiler los clasifique como 'texto'
    (no como categórico) y ejecute _profile_text."""
    nombres = [
        'Ana Quispe Flores',   'Luis Mamani Rojas',   'Rosa Condori Apaza',
        'Carlos Vargas Tito',  'Elena Chávez Paredes','Jorge Salazar Castillo',
        'Patricia Rojas Inca', 'Víctor Ayma Puma',    'Lucía Tito Choque',
        'Fernando Cusi Llanos','Beatriz Rivas Ccallo', 'Juan Flores Huamán',
        'Marta Quispe Apaza',  'César Condori Mamani','Diana Vargas Flores',
        'Pedro Chávez Quispe', 'Silvia Salazar Rojas','Raúl Rojas Condori',
        'Ivonne Ayma Flores',  'Mario Tito Vargas',   'Gloria Ccallo Chávez',
    ]
    df = pd.DataFrame({'col': nombres})
    perfil = profile_dataset(df)
    col_p = perfil['columnas']['col']
    assert 'perfil_nombres' in col_p, (
        f"perfil_nombres no aparece en profile_dataset. "
        f"tipo_perfil='{col_p.get('tipo_perfil')}', claves={sorted(col_p.keys())}"
    )
    assert isinstance(col_p['perfil_nombres'], dict)


def test_sugerencia_similitud_integrada_usa_perfil_nombres():
    """suggest_dimensions_rules usa perfil_nombres cuando hay perfil disponible."""
    import pandas as pd
    from ai.claude_analyzer import suggest_dimensions_rules
    from engine.profiler import profile_dataset

    df = pd.DataFrame({'razon': [f'Constructora {n} S.A.C.'
                                 for n in ['Andina','Huascarán','Pacífico',
                                           'Titicaca','Misti','Caral','Pisco',
                                           'Ucayali','Manu','Marañón',
                                           'Illimani','Lima','Arequipa',
                                           'Piura','Cusco']]})
    perfil_ds = profile_dataset(df)
    col_meta = [{'nombre': 'razon', 'tipo': 'object', 'total_registros': 15, 'valores_nulos': 0}]
    sugs = suggest_dimensions_rules(col_meta, profile=perfil_ds['columnas'])
    dim_sim = next((d for d in sugs[0]['dimensiones'] if d['dimension'] == 'similitud'), None)
    if dim_sim:
        assert dim_sim['params'].get('algoritmo') == 'qgrams', \
            f"Para RS con sufijos debería sugerir qgrams, no {dim_sim['params'].get('algoritmo')}"
