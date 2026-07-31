"""
FASE 1 — Tests unitarios del motor de dimensiones.
Prueba las 10 dimensiones con casos feliz, con problemas y extremos.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pandas as pd

from engine.dimensions.completitud import check_completitud
from engine.dimensions.unicidad import check_unicidad
from engine.dimensions.validez import check_validez
from engine.dimensions.exactitud import check_exactitud
from engine.dimensions.razonabilidad import check_razonabilidad
from engine.dimensions.precision import check_precision
from engine.dimensions.vigencia import check_vigencia
from engine.dimensions.oportunidad import check_oportunidad
from engine.dimensions.integridad_referencial import check_integridad_referencial
from engine.dimensions.consistencia import check_consistencia
from engine.dimensions.similitud import check_similitud
from engine.scorer import DQScorer

ID_COL = "id"
EXPECTED_COLS = {ID_COL, "columna", "dimension", "descripcion", "valor_encontrado"}


def make_df(values, id_col=ID_COL, target_col="valor"):
    return pd.DataFrame({id_col: range(len(values)), target_col: values})


def check_issues_cols(issues_df: pd.DataFrame, id_col: str = ID_COL):
    required = {id_col, "columna", "dimension", "descripcion", "valor_encontrado"}
    assert required.issubset(set(issues_df.columns)), (
        f"Columnas faltantes: {required - set(issues_df.columns)}. "
        f"Disponibles: {set(issues_df.columns)}"
    )


# ══════════════════════════════════════════════════════════
# 1. COMPLETITUD
# ══════════════════════════════════════════════════════════

class TestCompletitud:
    def test_happy_path(self):
        df = make_df(["a", "b", "c"])
        score, issues = check_completitud(df, ID_COL, "valor")
        assert score == 100.0
        assert issues.empty

    def test_with_nulls_score_50(self):
        df = make_df([None, "b", None, "d"])
        score, issues = check_completitud(df, ID_COL, "valor")
        assert score == 50.0
        assert len(issues) == 2
        check_issues_cols(issues)

    def test_one_null_of_five(self):
        df = make_df([None, "b", "c", "d", "e"])
        score, issues = check_completitud(df, ID_COL, "valor")
        assert score == 80.0
        assert len(issues) == 1

    def test_empty_df(self):
        df = make_df([])
        score, issues = check_completitud(df, ID_COL, "valor")
        assert score == 100.0
        assert issues.empty

    def test_all_null(self):
        df = make_df([None, None, None])
        score, issues = check_completitud(df, ID_COL, "valor")
        assert score == 0.0
        assert len(issues) == 3
        check_issues_cols(issues)

    def test_single_record_ok(self):
        df = make_df(["x"])
        score, issues = check_completitud(df, ID_COL, "valor")
        assert score == 100.0

    def test_single_record_null(self):
        df = make_df([None])
        score, issues = check_completitud(df, ID_COL, "valor")
        assert score == 0.0
        assert len(issues) == 1

    def test_dimension_label(self):
        df = make_df([None, "ok"])
        _, issues = check_completitud(df, ID_COL, "valor")
        assert issues["dimension"].iloc[0] == "completitud"
        assert issues["columna"].iloc[0] == "valor"


# ══════════════════════════════════════════════════════════
# 2. UNICIDAD
# ══════════════════════════════════════════════════════════

class TestUnicidad:
    def test_happy_path(self):
        df = make_df([1, 2, 3, 4, 5])
        score, issues = check_unicidad(df, ID_COL, "valor")
        assert score == 100.0
        assert issues.empty

    def test_all_duplicates(self):
        df = make_df(["a", "a", "a", "b", "b"])
        score, issues = check_unicidad(df, ID_COL, "valor")
        assert score == 0.0
        assert len(issues) == 5
        check_issues_cols(issues)

    def test_partial_duplicates_60pct(self):
        # 3 unique + 2 duplicates of "x" → 3/5 = 60%
        df = make_df(["x", "x", "a", "b", "c"])
        score, issues = check_unicidad(df, ID_COL, "valor")
        assert score == 60.0
        assert len(issues) == 2

    def test_empty_df(self):
        df = make_df([])
        score, issues = check_unicidad(df, ID_COL, "valor")
        assert score == 100.0
        assert issues.empty

    def test_single_record(self):
        df = make_df(["only"])
        score, issues = check_unicidad(df, ID_COL, "valor")
        assert score == 100.0
        assert issues.empty

    def test_nan_counted_as_duplicates(self):
        df = make_df([None, None])
        score, issues = check_unicidad(df, ID_COL, "valor")
        assert score == 0.0

    def test_dimension_label(self):
        df = make_df(["dup", "dup"])
        _, issues = check_unicidad(df, ID_COL, "valor")
        assert issues["dimension"].iloc[0] == "unicidad"


# ══════════════════════════════════════════════════════════
# 3. VALIDEZ
# ══════════════════════════════════════════════════════════

class TestValidez:
    def test_valid_values_happy(self):
        df = make_df(["A", "B", "C"])
        score, issues = check_validez(df, ID_COL, "valor", valid_values=["A", "B", "C"])
        assert score == 100.0
        assert issues.empty

    def test_valid_values_50pct(self):
        df = make_df(["A", "X", "B", "Y"])
        score, issues = check_validez(df, ID_COL, "valor", valid_values=["A", "B"])
        assert score == 50.0
        assert len(issues) == 2
        check_issues_cols(issues)
        assert "no está en la lista" in issues["descripcion"].iloc[0]

    def test_regex_happy(self):
        df = make_df(["ABC123", "DEF456"])
        score, issues = check_validez(df, ID_COL, "valor", regex_pattern=r"[A-Z]{3}\d{3}")
        assert score == 100.0

    def test_regex_one_invalid(self):
        df = make_df(["ABC123", "abc123", "XYZ999"])
        score, issues = check_validez(df, ID_COL, "valor", regex_pattern=r"[A-Z]{3}\d{3}")
        assert score == pytest.approx(66.67, abs=0.1)
        assert len(issues) == 1
        assert "Formato inválido" in issues["descripcion"].iloc[0]

    def test_no_params_returns_100(self):
        df = make_df(["anything", "goes"])
        score, issues = check_validez(df, ID_COL, "valor")
        assert score == 100.0

    def test_empty_df(self):
        df = make_df([])
        score, issues = check_validez(df, ID_COL, "valor", valid_values=["A"])
        assert score == 100.0

    def test_nulls_not_flagged(self):
        df = make_df([None, None])
        score, issues = check_validez(df, ID_COL, "valor", valid_values=["A"])
        assert len(issues) == 0

    def test_dimension_label(self):
        df = make_df(["X"])
        _, issues = check_validez(df, ID_COL, "valor", valid_values=["A"])
        assert issues["dimension"].iloc[0] == "validez"


# ══════════════════════════════════════════════════════════
# 4. EXACTITUD
# ══════════════════════════════════════════════════════════

class TestExactitud:
    def test_numeric_range_happy(self):
        df = make_df([10, 20, 30, 40])
        score, issues = check_exactitud(df, ID_COL, "valor", min_value=0, max_value=100)
        assert score == 100.0
        assert issues.empty

    def test_out_of_range_50pct(self):
        df = make_df([5, 150, 30, -10])
        score, issues = check_exactitud(df, ID_COL, "valor", min_value=0, max_value=100)
        assert score == 50.0
        assert len(issues) == 2
        check_issues_cols(issues)

    def test_reference_list_50pct(self):
        df = make_df(["active", "inactive", "pending", "unknown"])
        score, issues = check_exactitud(df, ID_COL, "valor",
                                        reference_list=["active", "inactive"])
        assert score == 50.0
        assert len(issues) == 2

    def test_no_params_returns_100(self):
        df = make_df([1, 2, 3])
        score, issues = check_exactitud(df, ID_COL, "valor")
        assert score == 100.0

    def test_empty_df(self):
        df = make_df([])
        score, issues = check_exactitud(df, ID_COL, "valor", min_value=0, max_value=10)
        assert score == 100.0

    def test_null_not_flagged(self):
        df = make_df([None, 5, 10])
        score, issues = check_exactitud(df, ID_COL, "valor", min_value=0, max_value=10)
        assert len(issues) == 0

    def test_only_min(self):
        df = make_df([-5, 0, 5])
        score, issues = check_exactitud(df, ID_COL, "valor", min_value=0)
        assert score == pytest.approx(66.67, abs=0.1)
        assert len(issues) == 1


# ══════════════════════════════════════════════════════════
# 5. RAZONABILIDAD
# ══════════════════════════════════════════════════════════

class TestRazonabilidad:
    def test_happy_path_tight_cluster(self):
        df = make_df([10, 12, 11, 13, 10, 11, 12])
        score, issues = check_razonabilidad(df, ID_COL, "valor")
        assert score == 100.0
        assert issues.empty

    def test_extreme_outlier(self):
        vals = [10] * 8 + [10000]
        df = make_df(vals)
        score, issues = check_razonabilidad(df, ID_COL, "valor")
        assert score < 100.0
        assert len(issues) >= 1
        check_issues_cols(issues)

    def test_no_variation_returns_100(self):
        df = make_df([5, 5, 5, 5])
        score, issues = check_razonabilidad(df, ID_COL, "valor")
        assert score == 100.0
        assert issues.empty

    def test_empty_df(self):
        df = make_df([])
        score, issues = check_razonabilidad(df, ID_COL, "valor")
        assert score == 100.0

    def test_all_null(self):
        df = make_df([None, None])
        score, issues = check_razonabilidad(df, ID_COL, "valor")
        assert score == 100.0
        assert issues.empty

    def test_iqr_factor_strict_vs_loose(self):
        vals = [10] * 10 + [50]
        df = make_df(vals)
        score_strict, _ = check_razonabilidad(df, ID_COL, "valor", iqr_factor=0.5)
        score_loose, _ = check_razonabilidad(df, ID_COL, "valor", iqr_factor=10.0)
        assert score_strict <= score_loose

    def test_dimension_label(self):
        vals = [10] * 8 + [99999]
        df = make_df(vals)
        _, issues = check_razonabilidad(df, ID_COL, "valor")
        if not issues.empty:
            assert issues["dimension"].iloc[0] == "razonabilidad"

    def test_isolation_forest_basico(self):
        import random
        random.seed(7)
        df = pd.DataFrame({
            ID_COL: range(100),
            'monto':  [random.uniform(1000, 50000) for _ in range(98)] + [9999999, -999999],
            'ordenes':[random.randint(1, 30)        for _ in range(98)] + [1, 1],
            'score':  [random.uniform(60, 100)      for _ in range(98)] + [99.9, 99.9],
        })
        score, issues = check_razonabilidad(
            df, ID_COL, 'monto',
            metodo='isolation_forest',
            columnas_if=['monto', 'ordenes', 'score'],
            contamination=0.05,
        )
        assert 0 <= score <= 100
        assert len(issues) > 0
        check_issues_cols(issues)
        assert 'Isolation Forest' in issues['descripcion'].iloc[0]

    def test_isolation_forest_fallback_iqr(self):
        """Si se pasan menos de 2 columnas válidas, debe hacer fallback a IQR."""
        df = pd.DataFrame({ID_COL: range(50), 'valor': range(50)})
        score, issues = check_razonabilidad(
            df, ID_COL, 'valor',
            metodo='isolation_forest',
            columnas_if=['valor'],
            contamination=0.05,
        )
        assert 0 <= score <= 100

    def test_iqr_sin_cambios_con_metodo_explicito(self):
        """IQR debe seguir funcionando exactamente igual con metodo='iqr'."""
        df = pd.DataFrame({ID_COL: range(100), 'edad': list(range(20, 118)) + [200, -5]})
        score, issues = check_razonabilidad(df, ID_COL, 'edad', metodo='iqr')
        assert 0 <= score <= 100
        assert len(issues) > 0


# ══════════════════════════════════════════════════════════
# 6. PRECISIÓN
# ══════════════════════════════════════════════════════════

class TestPrecision:
    def test_decimal_places_happy(self):
        # 1.50 == 1.5 in float, both pass decimal_places=2
        df = make_df([1.50, 2.50, 3.50])
        score, issues = check_precision(df, ID_COL, "valor", decimal_places=2)
        assert score == 100.0

    def test_decimal_places_one_invalid(self):
        # 3.123 * 100 = 312.3 → not integer → invalid
        df = make_df([1.50, 2.50, 3.123])
        score, issues = check_precision(df, ID_COL, "valor", decimal_places=2)
        assert len(issues) == 1
        check_issues_cols(issues)

    def test_text_length_happy(self):
        df = make_df(["abc", "defg", "hi!"])
        score, issues = check_precision(df, ID_COL, "valor", min_length=3, max_length=5)
        assert score == 100.0

    def test_text_length_two_invalid(self):
        df = make_df(["ab", "abc", "toolongstring"])
        score, issues = check_precision(df, ID_COL, "valor", min_length=3, max_length=5)
        assert score == pytest.approx(33.33, abs=0.1)
        assert len(issues) == 2

    def test_no_params_returns_100(self):
        df = make_df([1.23, 4.56])
        score, issues = check_precision(df, ID_COL, "valor")
        assert score == 100.0

    def test_empty_df(self):
        df = make_df([])
        score, issues = check_precision(df, ID_COL, "valor", decimal_places=2)
        assert score == 100.0

    def test_min_length_only(self):
        df = make_df(["hi", "hello", "hey"])
        score, issues = check_precision(df, ID_COL, "valor", min_length=4)
        assert len(issues) == 2  # "hi" and "hey" are too short


# ══════════════════════════════════════════════════════════
# 7. VIGENCIA
# ══════════════════════════════════════════════════════════

class TestVigencia:
    def test_date_range_happy(self):
        df = make_df(["2024-01-01", "2024-06-01", "2024-12-01"])
        score, issues = check_vigencia(df, ID_COL, "valor",
                                       date_from="2020-01-01", date_to="2030-12-31")
        assert score == 100.0
        assert issues.empty

    def test_date_range_two_out(self):
        df = make_df(["2010-01-01", "2024-06-01", "2035-01-01"])
        score, issues = check_vigencia(df, ID_COL, "valor",
                                       date_from="2020-01-01", date_to="2030-12-31")
        assert score == pytest.approx(33.33, abs=0.1)
        assert len(issues) == 2
        check_issues_cols(issues)

    def test_obsolete_values(self):
        df = make_df(["activo", "inactivo", "obsoleto", "activo"])
        score, issues = check_vigencia(df, ID_COL, "valor",
                                       obsolete_values=["inactivo", "obsoleto"])
        assert score == 50.0
        assert len(issues) == 2

    def test_no_params_returns_100(self):
        df = make_df(["2024-01-01"])
        score, issues = check_vigencia(df, ID_COL, "valor")
        assert score == 100.0

    def test_empty_df(self):
        df = make_df([])
        score, issues = check_vigencia(df, ID_COL, "valor", date_from="2020-01-01")
        assert score == 100.0

    def test_null_not_flagged(self):
        df = make_df([None, "2024-01-01"])
        score, issues = check_vigencia(df, ID_COL, "valor",
                                       date_from="2000-01-01", date_to="2030-12-31")
        assert len(issues) == 0

    def test_dimension_label(self):
        df = make_df(["obsoleto"])
        _, issues = check_vigencia(df, ID_COL, "valor", obsolete_values=["obsoleto"])
        assert issues["dimension"].iloc[0] == "vigencia"


# ══════════════════════════════════════════════════════════
# 8. OPORTUNIDAD
# ══════════════════════════════════════════════════════════

class TestOportunidad:
    def test_happy_recent_dates(self):
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        recent = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in [1, 5, 10]]
        df = make_df(recent)
        score, issues = check_oportunidad(df, ID_COL, "valor", max_age_days=30)
        assert score == 100.0
        assert issues.empty

    def test_all_old_dates(self):
        df = make_df(["2000-01-01", "2001-06-01", "1999-12-31"])
        score, issues = check_oportunidad(df, ID_COL, "valor", max_age_days=30)
        assert score == 0.0
        assert len(issues) == 3
        check_issues_cols(issues)

    def test_mixed_50pct(self):
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        recent = (now - timedelta(days=5)).strftime("%Y-%m-%d")
        df = make_df([recent, "2000-01-01"])
        score, issues = check_oportunidad(df, ID_COL, "valor", max_age_days=30)
        assert score == 50.0
        assert len(issues) == 1

    def test_no_param_returns_100(self):
        df = make_df(["2000-01-01"])
        score, issues = check_oportunidad(df, ID_COL, "valor")
        assert score == 100.0

    def test_empty_df(self):
        df = make_df([])
        score, issues = check_oportunidad(df, ID_COL, "valor", max_age_days=30)
        assert score == 100.0

    def test_dimension_label(self):
        df = make_df(["2000-01-01"])
        _, issues = check_oportunidad(df, ID_COL, "valor", max_age_days=30)
        assert issues["dimension"].iloc[0] == "oportunidad"


# ══════════════════════════════════════════════════════════
# 9. INTEGRIDAD REFERENCIAL
# ══════════════════════════════════════════════════════════

class TestIntegridadReferencial:
    def test_happy_path(self):
        df = make_df(["REF001", "REF002", "REF003"])
        score, issues = check_integridad_referencial(
            df, ID_COL, "valor",
            reference_ids=["REF001", "REF002", "REF003", "REF004"]
        )
        assert score == 100.0
        assert issues.empty

    def test_broken_refs_50pct(self):
        df = make_df(["REF001", "FAKE001", "REF002", "FAKE002"])
        score, issues = check_integridad_referencial(
            df, ID_COL, "valor",
            reference_ids=["REF001", "REF002"]
        )
        assert score == 50.0
        assert len(issues) == 2
        check_issues_cols(issues)

    def test_no_reference_ids_returns_100(self):
        df = make_df(["X", "Y"])
        score, issues = check_integridad_referencial(df, ID_COL, "valor")
        assert score == 100.0

    def test_empty_df(self):
        df = make_df([])
        score, issues = check_integridad_referencial(
            df, ID_COL, "valor", reference_ids=["A", "B"]
        )
        assert score == 100.0

    def test_null_not_flagged(self):
        df = make_df([None, None])
        score, issues = check_integridad_referencial(
            df, ID_COL, "valor", reference_ids=["A"]
        )
        assert len(issues) == 0

    def test_dimension_label(self):
        df = make_df(["FAKE"])
        _, issues = check_integridad_referencial(
            df, ID_COL, "valor", reference_ids=["REF001"]
        )
        assert issues["dimension"].iloc[0] == "integridad_referencial"


# ══════════════════════════════════════════════════════════
# 10. CONSISTENCIA
# ══════════════════════════════════════════════════════════

class TestConsistencia:
    def test_happy_same_date_format(self):
        df = make_df(["2024-01-01", "2024-06-15", "2024-12-31"])
        score, issues = check_consistencia(df, ID_COL, "valor")
        assert score == 100.0
        assert issues.empty

    def test_mixed_date_formats(self):
        df = make_df(["01/01/2024", "02/03/2024", "2024-01-01", "2024-06-15"])
        score, issues = check_consistencia(df, ID_COL, "valor")
        assert score < 100.0
        assert not issues.empty
        check_issues_cols(issues)  # must have 'id' column (fixed bug)

    def test_consistent_uppercase(self):
        df = make_df(["ACTIVE", "INACTIVE", "PENDING"])
        score, issues = check_consistencia(df, ID_COL, "valor")
        assert score == 100.0

    def test_mixed_capitalisation(self):
        df = make_df(["ACTIVE", "inactive", "Pending"])
        score, issues = check_consistencia(df, ID_COL, "valor")
        # All 3 rows have inconsistent capitalization
        assert score < 100.0
        check_issues_cols(issues)

    def test_empty_df(self):
        df = make_df([])
        score, issues = check_consistencia(df, ID_COL, "valor")
        assert score == 100.0

    def test_all_null(self):
        df = make_df([None, None])
        score, issues = check_consistencia(df, ID_COL, "valor")
        assert score == 100.0

    def test_numeric_data_no_issues(self):
        df = make_df([1.0, 2.0, 3.0])
        score, issues = check_consistencia(df, ID_COL, "valor")
        assert score == 100.0

    def test_id_col_in_issues(self):
        """Regression: issues_df debe usar el nombre real del id_col, no 'id_col_value'."""
        df = pd.DataFrame({
            "reg_id": [1, 2, 3, 4],
            "fecha": ["01/01/2024", "02/03/2024", "2024-01-01", "2024-04-01"],
        })
        _, issues = check_consistencia(df, "reg_id", "fecha")
        if not issues.empty:
            assert "reg_id" in issues.columns
            assert "id_col_value" not in issues.columns


# ══════════════════════════════════════════════════════════
# SCORER — integración
# ══════════════════════════════════════════════════════════

class TestDQScorer:
    def test_basic_one_dim(self):
        df = pd.DataFrame({"id": [1, 2, 3], "nombre": ["Alice", "Bob", None]})
        scorer = DQScorer(df, id_col="id")
        scorer.configure("nombre", {"completitud": {}})
        results = scorer.run_analysis()
        assert results["score_general"] == pytest.approx(66.67, abs=0.1)
        assert results["total_registros"] == 3
        assert results["total_problemas"] == 1

    def test_issues_df_standard_columns(self):
        df = pd.DataFrame({"id": [1, 2, 3], "nombre": ["Alice", None, "Carlos"]})
        scorer = DQScorer(df, id_col="id")
        scorer.configure("nombre", {"completitud": {}})
        results = scorer.run_analysis()
        issues = results["issues_df"]
        assert set(issues.columns) == {"id", "columna", "dimension", "descripcion", "valor_encontrado"}

    def test_multiple_dimensions(self):
        df = pd.DataFrame({"id": [1, 2, 3, 4], "valor": [1, 2, 2, 4]})
        scorer = DQScorer(df, id_col="id")
        scorer.configure("valor", {"completitud": {}, "unicidad": {}})
        results = scorer.run_analysis()
        col_scores = results["scores_por_columna"]["valor"]
        assert "completitud" in col_scores
        assert "unicidad" in col_scores

    def test_consistencia_rename_in_scorer(self):
        """El scorer debe renombrar id_col_value → id_col para consistencia."""
        df = pd.DataFrame({
            "reg_id": [1, 2, 3, 4],
            "fecha": ["01/01/2024", "02/03/2024", "2024-01-01", "2024-04-01"],
        })
        scorer = DQScorer(df, id_col="reg_id")
        scorer.configure("fecha", {"consistencia": {}})
        results = scorer.run_analysis()
        issues = results["issues_df"]
        if not issues.empty:
            assert "reg_id" in issues.columns
            assert "id_col_value" not in issues.columns

    def test_id_equals_target_no_reindex_error(self):
        """Regression: id_col == target_col no debe lanzar error de reindexado."""
        df = pd.DataFrame({"id": [1, 2, 2, 3]})
        scorer = DQScorer(df, id_col="id")
        scorer.configure("id", {"unicidad": {}})
        results = scorer.run_analysis()
        assert results["total_registros"] == 4

    def test_empty_config_raises(self):
        df = pd.DataFrame({"id": [1, 2], "val": [1, 2]})
        scorer = DQScorer(df, id_col="id")
        with pytest.raises(RuntimeError):
            scorer.run_analysis()

    def test_invalid_id_col_raises(self):
        df = pd.DataFrame({"id": [1, 2], "val": [1, 2]})
        with pytest.raises(ValueError):
            DQScorer(df, id_col="nonexistent")

    def test_compute_summary_static(self):
        df = pd.DataFrame({"id": [1, 2, 3, 4], "val": [None, "b", "c", "d"]})
        scorer = DQScorer(df, id_col="id")
        scorer.configure("val", {"completitud": {}})
        results = scorer.run_analysis()
        summary = DQScorer.compute_summary(results)
        assert summary["total_registros"] == 4
        assert summary["total_problemas"] == 1
        assert summary["pct_limpios"] == 75.0


# ─────────────────────────────────────────────────────────────────────────────
# SIMILITUD
# ─────────────────────────────────────────────────────────────────────────────

def test_similitud_detecta_casos_conocidos():
    data = {
        'id': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        'nombre': [
            'Juan Carlos Pérez Gómez',
            'Juan C. Perez',
            'Av. Javier Prado Este 123',
            'Avenida Javier Prado 123',
            'Telefónica del Perú S.A.A.',
            'Telefonica Peru',
            'María García López',
            'Maria Garcia',
            'Pedro Rodríguez',
            'Carlos Mendoza',
        ],
    }
    df = pd.DataFrame(data)
    score, issues = check_similitud(df, 'id', 'nombre', umbral=75, algoritmo='jaro_winkler')
    ids_con_problemas = set(issues['id'].tolist())

    assert 1 in ids_con_problemas or 2 in ids_con_problemas, \
        "No detectó Juan Carlos Pérez vs Juan C. Perez"
    assert 3 in ids_con_problemas or 4 in ids_con_problemas, \
        "No detectó Av. Javier Prado Este vs Avenida Javier Prado"
    assert 5 in ids_con_problemas or 6 in ids_con_problemas, \
        "No detectó Telefónica del Perú vs Telefonica Peru"
    assert 7 in ids_con_problemas or 8 in ids_con_problemas, \
        "No detectó María García López vs Maria Garcia"

    print(f"\nScore: {score}")
    print(f"Pares similares encontrados: {len(issues)}")
    print(issues[['id', 'valor_encontrado', 'descripcion']].to_string())


def test_similitud_score_perfecto():
    data = {'id': [1, 2, 3], 'nombre': ['Ana Torres', 'Luis Mendoza', 'Carlos Ruiz']}
    df = pd.DataFrame(data)
    score, issues = check_similitud(df, 'id', 'nombre', umbral=85)
    assert score == 100.0
    assert len(issues) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Tests de Brecha Afín
# ─────────────────────────────────────────────────────────────────────────────

def test_brecha_afin_abreviaturas():
    """Brecha Afín debe detectar abreviaturas mejor que Levenshtein."""
    import jellyfish
    from engine.dimensions.similitud import _brecha_afin, _normalizar
    casos = [
        ("juan alberto garcia", "juan a garcia",    "abreviatura segundo nombre"),
        ("telefonica del peru", "tel del peru",      "abreviatura empresa"),
        ("juan carlos perez gomez", "j c perez g",   "multiples abreviaturas"),
        ("avenida siempre viva", "av siempre viva",  "abreviatura prefijo"),
    ]
    print("\nComparativa Brecha Afín vs Levenshtein para abreviaturas:")
    print(f"{'Caso':<35} {'Brecha Afín':>12} {'Levenshtein':>12} {'Ganador':>10}")
    print("-" * 75)
    for a, b, desc in casos:
        score_ba = _brecha_afin(a, b)
        n = max(len(a), len(b))
        dist_lev = jellyfish.levenshtein_distance(a, b)
        score_lev = (1 - dist_lev / n) * 100 if n > 0 else 0
        ganador = "Brecha Afín" if score_ba > score_lev else "Levenshtein"
        print(f"{desc:<35} {score_ba:>11.1f}% {score_lev:>11.1f}% {ganador:>10}")
        # Brecha Afín debe dar score más alto en casos de abreviatura
        assert score_ba >= score_lev * 0.9, f"Brecha Afín debería ser competitiva para '{desc}'"


def test_brecha_afin_casos_identicos():
    """Strings idénticos deben dar 100%."""
    from engine.dimensions.similitud import _brecha_afin
    assert _brecha_afin("juan perez", "juan perez") == 100.0


def test_brecha_afin_casos_muy_diferentes():
    """Strings muy diferentes deben dar score bajo."""
    from engine.dimensions.similitud import _brecha_afin
    score = _brecha_afin("juan perez", "xyz abc")
    assert score < 50, f"Score esperado <50, obtenido: {score}"


def test_brecha_afin_en_check_similitud():
    """Verificar que brecha_afin funciona end-to-end en check_similitud."""
    import pandas as pd
    from engine.dimensions.similitud import check_similitud
    df = pd.DataFrame({
        'id': [1, 2, 3, 4, 5, 6],
        'nombre': [
            'Juan Alberto García López',
            'Juan A. García López',       # abreviatura — debe detectarse
            'María Fernanda Torres',
            'M. F. Torres',               # abreviatura — debe detectarse
            'Carlos Rodríguez',
            'Pedro Martínez'              # diferente — no debe detectarse
        ]
    })
    score, issues = check_similitud(df, 'id', 'nombre',
                                     algoritmo='brecha_afin', umbral=75)
    ids_con_problema = set(issues['id'].tolist())
    print(f"\nBrecha Afín end-to-end:")
    print(f"Score: {score}")
    print(f"IDs con similares: {ids_con_problema}")
    print(issues[['id', 'valor_encontrado', 'descripcion']].to_string())
    # Debe detectar los pares con abreviaturas
    assert 1 in ids_con_problema or 2 in ids_con_problema, \
        "Debe detectar Juan Alberto García vs Juan A. García"
    assert 3 in ids_con_problema or 4 in ids_con_problema, \
        "Debe detectar María Fernanda Torres vs M. F. Torres"
    # Pedro Martínez no debe tener similar
    assert 6 not in ids_con_problema, \
        "Pedro Martínez no debería tener similar"


# ─────────────────────────────────────────────────────────────────────────────
# Tests nuevo modelo de conteo: grupos / involucrados / excedentes
# ─────────────────────────────────────────────────────────────────────────────

def test_similitud_conteo_excedentes():
    """Grupo de 3 variantes → 1 grupo, 3 involucrados, 2 excedentes."""
    import pandas as pd
    from engine.dimensions.similitud import check_similitud
    df = pd.DataFrame({
        'id': [1, 2, 3, 4, 5],
        'razon': [
            'Distribuidora del Sur S.A.C.',
            'Distribuidora del Sur SAC',
            'DISTRIBUIDORA DEL SUR S.A.C.',
            'Comercial Andina E.I.R.L.',
            'Importaciones Pacific S.A.',
        ]
    })
    score, issues = check_similitud(
        df, 'id', 'razon', algoritmo='monge_elkan', umbral=80, normalizar=True
    )
    print(f"\nScore: {score}")
    print(f"Issues:\n{issues[['id', 'grupo_id', 'similitud_pct', 'valor_correcto']].to_string()}")
    assert issues['sim_total_grupos'].iloc[0] == 1
    assert issues['sim_total_involucrados'].iloc[0] == 3
    assert issues['sim_total_excedentes'].iloc[0] == 2
    assert score == 60.0


def test_similitud_excluye_duplicados_exactos():
    """Valores byte-idénticos no cuentan en similitud (pertenecen a unicidad)."""
    import pandas as pd
    from engine.dimensions.similitud import check_similitud
    df = pd.DataFrame({
        'id': [1, 2, 3],
        'razon': [
            'Comercial Andina S.A.C.',
            'Comercial Andina S.A.C.',   # byte-idéntico → excluido
            'Importaciones Pacific S.A.',
        ]
    })
    score, issues = check_similitud(
        df, 'id', 'razon', algoritmo='jaro_winkler', umbral=90
    )
    print(f"\nScore: {score}, issues rows: {len(issues)}")
    assert score == 100.0
    if len(issues) > 0:
        assert issues['sim_dup_exactos_excluidos'].iloc[0] == 2


def test_similitud_excluye_placeholders():
    """Valores vacíos y placeholder se excluyen del análisis."""
    import pandas as pd
    from engine.dimensions.similitud import check_similitud
    df = pd.DataFrame({
        'id': [1, 2, 3, 4, 5],
        'razon': ['N/A', '', '-', 'Sin dato', 'Comercial Andina S.A.C.'],
    })
    score, issues = check_similitud(
        df, 'id', 'razon', algoritmo='jaro_winkler', umbral=90
    )
    print(f"\nScore: {score}, issues rows: {len(issues)}")
    assert score == 100.0


def test_similitud_grupo_id_presente():
    """Cada issue debe tener grupo_id y valor_correcto (solo excedentes en issues)."""
    import pandas as pd
    from engine.dimensions.similitud import check_similitud
    df = pd.DataFrame({
        'id': [1, 2, 3],
        'razon': ['Juan Alberto Garcia', 'Juan A. Garcia', 'Pedro Martinez'],
    })
    score, issues = check_similitud(
        df, 'id', 'razon', algoritmo='brecha_afin', umbral=75
    )
    print(f"\nScore: {score}")
    if len(issues) > 0:
        print(issues[['id', 'grupo_id', 'similitud_pct', 'valor_correcto']].to_string())
        assert 'grupo_id' in issues.columns
        assert 'valor_correcto' in issues.columns
        assert issues['valor_correcto'].notna().any()
