import pandas as pd


def check_unicidad(df: pd.DataFrame, id_col: str, target_col: str, **params) -> tuple[float, pd.DataFrame, dict]:
    """
    Mide si hay valores duplicados en target_col.
    Score = (registros únicos / total) × 100.

    Reporta todos los involucrados marcando cuál conservar:
      - es_principal_sugerido=True  → conservar (menos campos nulos; desempate por menor id)
      - es_principal_sugerido=False → eliminar o unificar con el principal
    """
    total = len(df)
    if total == 0:
        return 100.0, _empty_issues(id_col), {}

    duplicados_mask = df[target_col].duplicated(keep=False)
    n_unicos = (~duplicados_mask).sum()
    score = round((n_unicos / total) * 100, 2)

    if not duplicados_mask.any():
        return score, _empty_issues(id_col), {}

    dupes = df[duplicados_mask].copy()

    # ── Selección del principal de cada grupo ──────────────────────────────
    # Criterio: menor cantidad de campos nulos en la fila completa;
    # desempate por el menor valor del id_col (convertido a str).
    dupes['_nulos'] = dupes.isnull().sum(axis=1)

    principal_set: set = set()
    for _, grupo in dupes.groupby(target_col, sort=False, dropna=False):
        try:
            # Ordena por (nulos asc, id_col asc como string)
            ordenado = grupo.sort_values(
                by=['_nulos', id_col],
                key=lambda s: s.astype(str),
            )
        except Exception:
            ordenado = grupo
        principal_set.add(ordenado.index[0])

    # ── Construir issues_df ────────────────────────────────────────────────
    es_principal = [idx in principal_set for idx in dupes.index]

    issues_df = pd.DataFrame({
        id_col:                  dupes[id_col].values,
        'valor_encontrado':      dupes[target_col].values,
        'columna':               target_col,
        'dimension':             'unicidad',
        'es_principal_sugerido': es_principal,
    })
    issues_df['descripcion'] = [
        'Valor duplicado — conservar este registro (tiene menos campos vacíos)'
        if p else
        'Valor duplicado — eliminar o unificar con el registro principal'
        for p in es_principal
    ]

    return score, issues_df.reset_index(drop=True), {}


def _empty_issues(id_col: str) -> pd.DataFrame:
    return pd.DataFrame(columns=[
        id_col, 'columna', 'dimension', 'descripcion', 'valor_encontrado',
        'es_principal_sugerido',
    ])
