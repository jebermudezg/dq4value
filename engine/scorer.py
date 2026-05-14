import pandas as pd
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Callable, Optional
from engine.dimensions import DIMENSIONS_MAP

DIMENSION_TIMEOUT = 30  # seconds per dimension


class DQScorer:
    def __init__(
        self,
        df: pd.DataFrame,
        id_col: str,
        progress_callback: Optional[Callable] = None,
    ):
        if id_col not in df.columns:
            raise ValueError(f"La columna ID '{id_col}' no existe en el DataFrame.")
        self.df   = df.copy().reset_index(drop=True)
        self.id_col = id_col
        self._config: dict[str, dict[str, dict]] = {}
        self._progress_cb = progress_callback

    # ------------------------------------------------------------------
    # Configuración
    # ------------------------------------------------------------------

    def configure(self, column_name: str, dimensions_config: dict) -> "DQScorer":
        if column_name not in self.df.columns:
            raise ValueError(f"La columna '{column_name}' no existe en el DataFrame.")

        unknown = set(dimensions_config) - set(DIMENSIONS_MAP)
        if unknown:
            raise ValueError(
                f"Dimensiones desconocidas para '{column_name}': {unknown}. "
                f"Disponibles: {set(DIMENSIONS_MAP)}"
            )

        self._config[column_name] = dimensions_config
        return self

    # ------------------------------------------------------------------
    # Análisis
    # ------------------------------------------------------------------

    def run_analysis(self) -> dict:
        """
        Ejecuta todas las dimensiones configuradas con timeout de 30 s por dimensión.
        Llama a progress_callback(col, dim_name, done, total) antes de cada dimensión.

        Returns dict con:
            scores_por_columna, score_general, issues_df,
            total_registros, total_problemas
        """
        if not self._config:
            raise RuntimeError(
                "No hay columnas configuradas. Llama a configure() antes de run_analysis()."
            )

        total_dims = sum(len(dc) for dc in self._config.values())
        done_dims  = 0

        scores_por_columna: dict[str, dict[str, float]] = {}
        all_issues: list[pd.DataFrame] = []
        all_scores: list[float] = []

        empty_cols = [self.id_col, "columna", "dimension", "descripcion", "valor_encontrado"]

        with ThreadPoolExecutor(max_workers=1) as executor:
            for col, dim_config in self._config.items():
                scores_por_columna[col] = {}

                for dim_name, params in dim_config.items():
                    # Progress notification before running
                    if self._progress_cb:
                        try:
                            self._progress_cb(col, dim_name, done_dims, total_dims)
                        except Exception:
                            pass

                    check_fn = DIMENSIONS_MAP[dim_name]
                    future = executor.submit(check_fn, self.df, self.id_col, col, **params)

                    try:
                        score, issues_df = future.result(timeout=DIMENSION_TIMEOUT)
                    except FuturesTimeout:
                        print(
                            f"[DQScorer] TIMEOUT ({DIMENSION_TIMEOUT}s) — "
                            f"dimensión '{dim_name}' en columna '{col}' omitida."
                        )
                        score     = 0.0
                        issues_df = pd.DataFrame(columns=empty_cols)
                    except Exception as e:
                        raise RuntimeError(
                            f"Error al ejecutar dimensión '{dim_name}' en columna '{col}': {e}"
                        ) from e

                    scores_por_columna[col][dim_name] = score
                    all_scores.append(score)
                    done_dims += 1

                    if not issues_df.empty:
                        if self.id_col not in issues_df.columns:
                            issues_df = issues_df.rename(columns={"id_col_value": self.id_col})
                        all_issues.append(issues_df)

        score_general = round(sum(all_scores) / len(all_scores), 2) if all_scores else 100.0

        if all_issues:
            typed = []
            for df in all_issues:
                df = df.reset_index(drop=True)
                df["valor_encontrado"] = df["valor_encontrado"].astype(object)
                typed.append(df)
            issues_df_final = pd.concat(typed, ignore_index=True)
            std_cols = [self.id_col, "columna", "dimension", "descripcion", "valor_encontrado"]
            for c in std_cols:
                if c not in issues_df_final.columns:
                    issues_df_final[c] = None
            issues_df_final = issues_df_final[std_cols]
        else:
            issues_df_final = pd.DataFrame(columns=empty_cols)

        total_problemas = (
            issues_df_final[self.id_col].nunique() if not issues_df_final.empty else 0
        )

        return {
            "scores_por_columna": scores_por_columna,
            "score_general":      score_general,
            "issues_df":          issues_df_final,
            "total_registros":    len(self.df),
            "total_problemas":    total_problemas,
        }

    # ------------------------------------------------------------------
    # Resumen  (sin rellamar run_analysis)
    # ------------------------------------------------------------------

    @staticmethod
    def compute_summary(results: dict) -> dict:
        """Calcula el resumen a partir del dict devuelto por run_analysis()."""
        dim_scores: dict[str, list[float]] = {}
        for col_scores in results["scores_por_columna"].values():
            for dim, score in col_scores.items():
                dim_scores.setdefault(dim, []).append(score)

        peor_dimension = None
        if dim_scores:
            peor_dimension = min(
                dim_scores, key=lambda d: sum(dim_scores[d]) / len(dim_scores[d])
            )

        total    = results["total_registros"]
        problemas = results["total_problemas"]
        pct_limpios = round(((total - problemas) / total) * 100, 2) if total > 0 else 100.0

        return {
            "total_registros":  total,
            "total_problemas":  problemas,
            "pct_limpios":      pct_limpios,
            "peor_dimension":   peor_dimension,
        }

    def get_summary(self) -> dict:
        """Mantiene compatibilidad — internamente usa compute_summary."""
        return self.compute_summary(self.run_analysis())
