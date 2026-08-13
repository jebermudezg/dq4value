import pandas as pd
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Callable, Optional
from engine.dimensions import DIMENSIONS_MAP
from engine.pesos import peso_numerico, pesos_iguales

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

    def run_analysis(self, niveles: dict = None) -> dict:
        """
        Ejecuta todas las dimensiones configuradas con timeout de 30 s por dimensión.
        Llama a progress_callback(col, dim_name, done, total) antes de cada dimensión.

        niveles: dict {dimension: nivel} de engine.pesos. None → pesos iguales (promedio simple).

        Returns dict con:
            scores_por_columna, score_general, score_promedio_simple, issues_df,
            total_registros, total_problemas, scores_por_dimension, niveles_dimensiones,
            nivel_umbral, dimensiones_umbral, registros_aprovechables, pct_aprovechables,
            peor_dimension_critica, peor_dimension_critica_score
        """
        if not self._config:
            raise RuntimeError(
                "No hay columnas configuradas. Llama a configure() antes de run_analysis()."
            )

        if niveles is None:
            niveles = pesos_iguales()

        total_dims = sum(len(dc) for dc in self._config.values())
        done_dims  = 0

        scores_por_columna: dict[str, dict[str, float]] = {}
        all_issues: list[pd.DataFrame] = []
        all_scores: list[float] = []
        metadata_dimensiones: dict = {}

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
                        resultado = future.result(timeout=DIMENSION_TIMEOUT)
                        if len(resultado) == 3:
                            score, issues_df, metadata = resultado
                        else:
                            score, issues_df = resultado
                            metadata = {}
                    except FuturesTimeout:
                        print(
                            f"[DQScorer] TIMEOUT ({DIMENSION_TIMEOUT}s) — "
                            f"dimensión '{dim_name}' en columna '{col}' omitida."
                        )
                        score     = 0.0
                        issues_df = pd.DataFrame(columns=empty_cols)
                        metadata  = {}
                    except Exception as e:
                        raise RuntimeError(
                            f"Error al ejecutar dimensión '{dim_name}' en columna '{col}': {e}"
                        ) from e

                    scores_por_columna[col][dim_name] = score
                    all_scores.append(score)
                    metadata_dimensiones[(col, dim_name)] = metadata
                    done_dims += 1

                    if not issues_df.empty:
                        if self.id_col not in issues_df.columns:
                            issues_df = issues_df.rename(columns={"id_col_value": self.id_col})
                        all_issues.append(issues_df)

        # score_promedio_simple = old unweighted average (kept for comparison)
        score_promedio_simple = round(sum(all_scores) / len(all_scores), 1) if all_scores else 100.0

        # scores_por_dimension: per-dim average across all columns where it was applied
        dim_to_scores: dict[str, list[float]] = {}
        for col, col_scores in scores_por_columna.items():
            for dim, s in col_scores.items():
                dim_to_scores.setdefault(dim, []).append(s)
        scores_por_dimension = {d: sum(vs) / len(vs) for d, vs in dim_to_scores.items()}

        # weighted score_general — only dimensions actually applied
        numerador = 0.0
        denominador = 0.0
        for dim, score_dim in scores_por_dimension.items():
            peso = peso_numerico(niveles.get(dim, 'media'))
            numerador += score_dim * peso
            denominador += peso
        score_general = round(numerador / denominador, 1) if denominador > 0 else 100.0

        # nivel_umbral = highest nivel present among applied dimensions
        _orden = ['critica', 'alta', 'media', 'informativa']
        niveles_dimensiones = {d: niveles.get(d, 'media') for d in scores_por_dimension}
        niveles_presentes = set(niveles_dimensiones.values())
        nivel_umbral = next((n for n in _orden if n in niveles_presentes), 'media')

        dimensiones_umbral = {d for d, n in niveles_dimensiones.items() if n == nivel_umbral}

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
            # Preserve extra columns (e.g. similitud metadata) — keep std_cols first
            extra_cols = [c for c in issues_df_final.columns if c not in std_cols]
            issues_df_final = issues_df_final[std_cols + extra_cols]
        else:
            issues_df_final = pd.DataFrame(columns=empty_cols)

        total_registros = len(self.df)
        total_problemas = (
            issues_df_final[self.id_col].nunique() if not issues_df_final.empty else 0
        )

        # registros_aprovechables: records without issues in nivel_umbral dimensions
        # principals suggested by similitud are NOT counted as problematic
        if not issues_df_final.empty and dimensiones_umbral:
            issues_umbral = issues_df_final[issues_df_final['dimension'].isin(dimensiones_umbral)]
            if 'es_principal_sugerido' in issues_umbral.columns:
                # Use map(lambda) to avoid pandas FutureWarning on object-dtype fillna
                issues_umbral = issues_umbral[
                    issues_umbral['es_principal_sugerido'].map(lambda x: x is not True)
                ]
            ids_con_problema_umbral = set(issues_umbral[self.id_col])
        else:
            ids_con_problema_umbral = set()
        registros_aprovechables = total_registros - len(ids_con_problema_umbral)
        pct_aprovechables = round(registros_aprovechables / total_registros * 100, 1) if total_registros > 0 else 100.0

        # peor_dimension_critica = lowest-scoring dim within nivel_umbral dims
        umbral_scores = [(d, scores_por_dimension[d]) for d in dimensiones_umbral if d in scores_por_dimension]
        if umbral_scores:
            peor_dimension_critica, peor_dimension_critica_score = min(umbral_scores, key=lambda x: x[1])
            peor_dimension_critica_score = round(peor_dimension_critica_score, 1)
        else:
            peor_dimension_critica = None
            peor_dimension_critica_score = None

        # veredicto: based on lowest score among nivel_umbral dimensions
        peor_umbral_score = peor_dimension_critica_score if peor_dimension_critica_score is not None else 100.0
        if peor_umbral_score < 60:
            veredicto = 'no_listo'
        elif peor_umbral_score < 80:
            veredicto = 'con_riesgos'
        else:
            veredicto = 'listo'

        return {
            "scores_por_columna":           scores_por_columna,
            "score_general":                score_general,
            "score_promedio_simple":        score_promedio_simple,
            "issues_df":                    issues_df_final,
            "total_registros":              total_registros,
            "total_problemas":              total_problemas,
            "metadata_dimensiones":         metadata_dimensiones,
            "scores_por_dimension":         scores_por_dimension,
            "niveles_dimensiones":          niveles_dimensiones,
            "nivel_umbral":                 nivel_umbral,
            "dimensiones_umbral":           sorted(dimensiones_umbral),
            "registros_aprovechables":      registros_aprovechables,
            "pct_aprovechables":            pct_aprovechables,
            "peor_dimension_critica":       peor_dimension_critica,
            "peor_dimension_critica_score": peor_dimension_critica_score,
            "veredicto":                    veredicto,
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
