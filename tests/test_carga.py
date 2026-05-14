"""
FASE 3 — Tests de carga y rendimiento del motor de análisis.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import numpy as np
import pandas as pd

from engine.scorer import DQScorer
from engine.dimensions import DIMENSIONS_MAP


# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────

def _print_report(title: str, n_registros: int, n_dims: int, elapsed: float,
                  score: float, problemas: int) -> None:
    rps = n_registros / elapsed if elapsed > 0 else float("inf")
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    print(f"  Registros            : {n_registros:,}")
    print(f"  Dimensiones totales  : {n_dims}")
    print(f"  Tiempo total         : {elapsed:.3f}s")
    print(f"  Registros/segundo    : {rps:,.0f}")
    print(f"  Score general        : {score:.2f}")
    print(f"  Problemas detectados : {problemas}")
    print(f"{'='*60}")


# ─────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────

class TestRendimiento:

    def test_dataset_1000_bajo_60s(self):
        """Analiza dataset_1000.csv con múltiples dimensiones en menos de 60 s."""
        dataset_path = Path(__file__).parent / "dataset_1000.csv"
        if not dataset_path.exists():
            pytest.skip("dataset_1000.csv no encontrado — ejecuta generar_dataset_grande.py")

        df = pd.read_csv(str(dataset_path))
        id_col = "cliente_id"

        config = {
            "nombre":              {"completitud": {}, "consistencia": {}},
            "email":               {"completitud": {}, "unicidad": {}},
            "edad":                {"completitud": {}, "exactitud": {"min_value": 0, "max_value": 120},
                                    "razonabilidad": {}},
            "salario":             {"completitud": {}, "razonabilidad": {}},
            "ciudad":              {"completitud": {}},
            "estado_cliente":      {"completitud": {},
                                    "validez": {"valid_values": ["Activo", "Inactivo", "Suspendido"]}},
            "fecha_registro":      {"completitud": {},
                                    "vigencia": {"date_from": "2000-01-01", "date_to": "2030-12-31"}},
            "categoria_cliente":   {"completitud": {},
                                    "validez": {"valid_values": ["Premium", "Estándar", "Básico"]}},
            "score_credito":       {"completitud": {},
                                    "exactitud": {"min_value": 300, "max_value": 850}},
        }

        total_dims = sum(len(v) for v in config.values())
        start = time.perf_counter()

        scorer = DQScorer(df, id_col=id_col)
        for col, dims in config.items():
            scorer.configure(col, dims)
        results = scorer.run_analysis()

        elapsed = time.perf_counter() - start
        _print_report("DATASET 1,000 FILAS", len(df), total_dims,
                      elapsed, results["score_general"], results["total_problemas"])

        assert results["total_registros"] == len(df)
        assert 0 <= results["score_general"] <= 100
        assert elapsed < 60, f"Demasiado lento: {elapsed:.1f}s (límite 60s)"

    def test_dataset_10k_generado_bajo_60s(self):
        """Genera 10 000 filas y analiza con múltiples dimensiones en menos de 60 s."""
        n = 10_000
        rng = np.random.default_rng(42)

        df = pd.DataFrame({
            "id":        range(n),
            "valor_num": rng.normal(50, 10, n).round(2),
            "categoria": rng.choice(["ACTIVO", "INACTIVO", "SUSPENDIDO", None], n),
            "codigo":    [f"C{i:06d}" for i in range(n)],
            "fecha":     pd.date_range("2020-01-01", periods=n, freq="h")
                           .strftime("%Y-%m-%d").tolist(),
        })

        config = {
            "valor_num": {"completitud": {}, "razonabilidad": {},
                          "exactitud": {"min_value": 0, "max_value": 200}},
            "categoria": {"completitud": {},
                          "validez": {"valid_values": ["ACTIVO", "INACTIVO", "SUSPENDIDO"]}},
            "codigo":    {"completitud": {}, "unicidad": {}},
            "fecha":     {"completitud": {},
                          "vigencia": {"date_from": "2010-01-01", "date_to": "2035-12-31"}},
        }

        total_dims = sum(len(v) for v in config.values())
        start = time.perf_counter()

        scorer = DQScorer(df, id_col="id")
        for col, dims in config.items():
            scorer.configure(col, dims)
        results = scorer.run_analysis()

        elapsed = time.perf_counter() - start
        _print_report("DATASET 10,000 FILAS", n, total_dims,
                      elapsed, results["score_general"], results["total_problemas"])

        assert results["total_registros"] == n
        assert 0 <= results["score_general"] <= 100
        assert elapsed < 60, f"Demasiado lento: {elapsed:.1f}s (límite 60s)"

    def test_per_dimension_timing(self):
        """Mide el tiempo de cada dimensión individualmente con 1 000 filas."""
        n = 1_000
        rng = np.random.default_rng(0)
        df = pd.DataFrame({
            "id":     range(n),
            "num":    rng.uniform(0, 100, n).round(2),
            "text":   rng.choice(["ACTIVO", "INACTIVO", "SUSPENDIDO"], n),
            "fecha":  pd.date_range("2020-01-01", periods=n, freq="D")
                        .strftime("%Y-%m-%d").tolist(),
            "codigo": [f"K{i:04d}" for i in range(n)],
        })

        cases = [
            ("completitud",          "text",   {}),
            ("unicidad",             "codigo", {}),
            ("razonabilidad",        "num",    {}),
            ("validez",              "text",   {"valid_values": ["ACTIVO", "INACTIVO", "SUSPENDIDO"]}),
            ("exactitud",            "num",    {"min_value": 0, "max_value": 100}),
            ("vigencia",             "fecha",  {"date_from": "2019-01-01", "date_to": "2030-12-31"}),
            ("oportunidad",          "fecha",  {"max_age_days": 9999}),
            ("precision",            "texto",  {"min_length": 5, "max_length": 15}),
            ("consistencia",         "text",   {}),
            ("integridad_referencial","codigo", {"reference_ids": [f"K{i:04d}" for i in range(n)]}),
        ]

        print(f"\n{'='*55}")
        print(f"  TIEMPO POR DIMENSIÓN  (n={n})")
        print(f"{'='*55}")

        for dim_name, col, params in cases:
            if dim_name not in DIMENSIONS_MAP:
                print(f"  {dim_name:<28} OMITIDA (no registrada)")
                continue
            # Use "text" col for precision since we don't have a "texto" col
            actual_col = "text" if col == "texto" else col
            fn = DIMENSIONS_MAP[dim_name]
            t0 = time.perf_counter()
            try:
                fn(df, "id", actual_col, **params)
                t = time.perf_counter() - t0
                print(f"  {dim_name:<28} {t*1000:>8.2f} ms")
            except Exception as exc:
                print(f"  {dim_name:<28} ERROR: {exc}")

        print(f"{'='*55}")

    def test_score_consistent_across_runs(self):
        """El mismo dataset debe dar el mismo score en dos ejecuciones consecutivas."""
        df = pd.DataFrame({
            "id":    range(100),
            "valor": list(range(90)) + [None] * 10,
        })

        def _run():
            s = DQScorer(df, id_col="id")
            s.configure("valor", {"completitud": {}})
            return s.run_analysis()["score_general"]

        assert _run() == _run()

    def test_large_issues_df_no_memory_error(self):
        """Un DataFrame con muchos problemas no debe fallar por memoria."""
        n = 5_000
        # Todos los valores son inválidos
        df = pd.DataFrame({
            "id":    range(n),
            "valor": [None] * n,
        })
        scorer = DQScorer(df, id_col="id")
        scorer.configure("valor", {"completitud": {}})
        results = scorer.run_analysis()
        assert results["total_problemas"] == n
        assert results["score_general"] == 0.0
