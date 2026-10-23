"""
Módulo D.2 — Métricas de forecasting.

Implementa las métricas del documento:
    - MAE: error medio en unidades.
    - WAPE: error absoluto agregado / volumen real.
    - MASE: error escalado vs. naive in-sample.
    - Sesgo: tendencia a sobre/infra-predecir.
    - Cobertura: % de valores reales dentro del intervalo.

Todas las funciones aceptan arrays 1D (una serie) o DataFrames agrupados.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Métricas base
# ---------------------------------------------------------------------------

def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Error absoluto medio."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.mean(np.abs(y_true - y_pred)))


def wape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Weighted Absolute Percentage Error: sum(|y - ŷ|) / sum(y).
    Robusto a ceros y a outliers. Comparable entre productos.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denom = np.sum(np.abs(y_true))
    if denom == 0:
        return np.nan
    return float(np.sum(np.abs(y_true - y_pred)) / denom)


def mase(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_train: np.ndarray,
    seasonality: int = 1,
) -> float:
    """
    Mean Absolute Scaled Error.

    Se escala por el MAE del naive in-sample (seasonality=1) o
    seasonal naive in-sample (seasonality=52).

    Parámetros
    ----------
    y_true, y_pred : arrays del período de test.
    y_train : array del período de entrenamiento (para calcular el naive in-sample).
    seasonality : 1 para naive, 52 para seasonal naive (semanal anual).

    Devuelve nan si no hay suficiente historia.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    y_train = np.asarray(y_train, dtype=float)

    if len(y_train) <= seasonality:
        return np.nan

    naive_errors = np.abs(y_train[seasonality:] - y_train[:-seasonality])
    scale = np.mean(naive_errors)
    if scale == 0 or np.isnan(scale):
        return np.nan
    return float(np.mean(np.abs(y_true - y_pred)) / scale)


def bias(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Sesgo medio: mean(ŷ - y).
    > 0 = sobre-predice, < 0 = infra-predice.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.mean(y_pred - y_true))


def coverage(
    y_true: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
) -> float:
    """% de valores reales dentro del intervalo [lower, upper]."""
    y_true = np.asarray(y_true, dtype=float)
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    inside = (y_true >= lower) & (y_true <= upper)
    return float(np.mean(inside))


# ---------------------------------------------------------------------------
# Función agregada para evaluar un modelo completo
# ---------------------------------------------------------------------------

def evaluate_forecast(
    df: pd.DataFrame,
    y_true_col: str = "units_sold",
    y_pred_col: str = "y_pred",
    y_train_col: str | None = None,
    group_cols: list[str] | None = None,
    seasonality: int = 1,
    lower_col: str | None = None,
    upper_col: str | None = None,
) -> pd.DataFrame:
    """
    Evalúa un forecast agrupado por producto (y opcionalmente otras columnas).

    Parámetros
    ----------
    df : DataFrame con columnas y_true, y_pred, y opcionalmente y_train.
    y_true_col : columna con valores reales.
    y_pred_col : columna con predicciones.
    y_train_col : si se especifica, se usa para MASE. Debe contener,
                  por cada fila, el array de entrenamiento. Usar con cuidado.
    group_cols : columnas para agrupar (ej: ['stock_code']).
    seasonality : 1 para naive, 52 para seasonal naive.
    lower_col, upper_col : si se especifican, se calcula cobertura.

    Devuelve
    --------
    DataFrame con métricas por grupo (o una sola fila si group_cols=None).
    """
    if group_cols is None:
        group_cols = []

    def _metrics(g: pd.DataFrame) -> pd.Series:
        y_true = g[y_true_col].values
        y_pred = g[y_pred_col].values
        out = {
            "n_obs": len(g),
            "mae": mae(y_true, y_pred),
            "wape": wape(y_true, y_pred),
            "bias": bias(y_true, y_pred),
        }
        if y_train_col and y_train_col in g.columns:
            y_train = g[y_train_col].iloc[0]  # asumimos igual para todo el grupo
            if isinstance(y_train, (list, np.ndarray)):
                out["mase"] = mase(y_true, y_pred, np.asarray(y_train), seasonality)
        if lower_col and upper_col:
            out["coverage"] = coverage(y_true, g[lower_col].values, g[upper_col].values)
        return pd.Series(out)

    if group_cols:
        return df.groupby(group_cols, dropna=False).apply(_metrics, include_groups=False).reset_index()
    return pd.DataFrame([_metrics(df)])