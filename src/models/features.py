"""
Módulo D.3 — Construcción de features temporales sin leakage.

Principio:
    Todas las features de un corte T se calculan usando SOLO datos ≤ T.

Estructura de la salida (una fila por producto × horizonte):
    stock_code, week_start, horizon, y_true, <features...>

Uso:
    features, y_true = build_features(df_weekly, cutoff_date, horizon=4)

Notas:
    - Los lags se calculan siempre respecto a t (última semana del cutoff).
      Para h>1, el lag k es y(t-k), no y(t+h-k). Es una simplificación
      que evita leakage pero no distingue entre horizontes.
    - y_true se devuelve separado para evitar usarlo como feature por error.
    - week_of_year se trata como categórica (LightGBM la maneja así).
"""

from __future__ import annotations

from datetime import date
from typing import Literal

import numpy as np
import pandas as pd


# Columnas de features (el orden importa para LightGBM)
FEATURE_COLS = [
    "lag_1",
    "lag_2",
    "lag_4",
    "lag_8",
    "lag_13",
    "lag_52",
    "rolling_mean_4",
    "rolling_mean_13",
    "rolling_std_4",
    "week_of_year",
    "month",
    "horizon",
    "product_mean",
]
CATEGORICAL_COLS = ["stock_code", "week_of_year"]


def _week_of_year(dt: pd.Timestamp) -> int:
    return int(dt.isocalendar().week)


def build_features(
    df: pd.DataFrame,
    cutoff: date,
    horizon: int = 4,
    min_history_weeks: int = 52,
    return_y_true: bool = True,
) -> pd.DataFrame | tuple[pd.DataFrame, pd.Series]:
    """
    Construye el dataset de features para un corte concreto.

    Parámetros
    ----------
    df : DataFrame con columnas [stock_code, week_start, units_sold].
    cutoff : última semana con datos observados.
    horizon : horizontes a generar (1..horizon). Máximo recomendado: 12.
    min_history_weeks : semanas mínimas de historia por producto.
    return_y_true : si True, devuelve (features, y_true) separados.
                    Si False, devuelve un solo DataFrame con y_true incluido.

    Devuelve
    --------
    - Si return_y_true=True: (features_df, y_true_series)
    - Si return_y_true=False: DataFrame con y_true incluido.

    En ambos casos, se excluyen filas sin y_true (futuro no observado).
    """
    if horizon < 1:
        raise ValueError("horizon debe ser >= 1")
    if horizon > 12:
        raise ValueError("horizon > 12 no está soportado (necesitas más datos)")

    df = df.copy()
    df["week_start"] = pd.to_datetime(df["week_start"])
    df = df.sort_values(["stock_code", "week_start"]).reset_index(drop=True)

    cutoff_ts = pd.Timestamp(cutoff)
    out_rows: list[dict] = []

    for sc, g in df.groupby("stock_code"):
        g = g.sort_values("week_start").reset_index(drop=True)

        # Filtrar datos hasta el corte (sin leakage)
        g_train = g[g["week_start"] <= cutoff_ts].reset_index(drop=True)
        if len(g_train) < min_history_weeks:
            continue

        y = g_train["units_sold"].to_numpy(dtype=float)
        weeks = g_train["week_start"].to_numpy()

        last_week = pd.Timestamp(weeks[-1])
        product_mean = float(np.nanmean(y))

        if len(y) < 52:
            continue

        # Calcular lags/rolling una sola vez por producto (son iguales para todos los h)
        lag_1 = float(y[-1]) if len(y) >= 1 else np.nan
        lag_2 = float(y[-2]) if len(y) >= 2 else np.nan
        lag_4 = float(y[-4]) if len(y) >= 4 else np.nan
        lag_8 = float(y[-8]) if len(y) >= 8 else np.nan
        lag_13 = float(y[-13]) if len(y) >= 13 else np.nan
        lag_52 = float(y[-52]) if len(y) >= 52 else np.nan
        rolling_mean_4 = float(np.nanmean(y[-4:]))
        rolling_mean_13 = float(np.nanmean(y[-13:]))
        rolling_std_4 = float(np.nanstd(y[-4:]))

        for h in range(1, horizon + 1):
            target_week = last_week + pd.Timedelta(weeks=h)

            row = {
                "stock_code": sc,
                "week_start": target_week,
                "horizon": h,
                "y_true": np.nan,  # se rellena fuera
                "lag_1": lag_1,
                "lag_2": lag_2,
                "lag_4": lag_4,
                "lag_8": lag_8,
                "lag_13": lag_13,
                "lag_52": lag_52,
                "rolling_mean_4": rolling_mean_4,
                "rolling_mean_13": rolling_mean_13,
                "rolling_std_4": rolling_std_4,
                "week_of_year": _week_of_year(target_week),
                "month": int(target_week.month),
                "product_mean": product_mean,
            }
            out_rows.append(row)

    out = pd.DataFrame(out_rows)
    if out.empty:
        empty_feat = pd.DataFrame(columns=["stock_code", "week_start", "horizon"] + FEATURE_COLS)
        empty_y = pd.Series(dtype=float)
        return (empty_feat, empty_y) if return_y_true else pd.DataFrame()

    # Rellenar y_true desde el dataset original (para backtesting)
    y_true_df = df[["stock_code", "week_start", "units_sold"]].rename(
        columns={"units_sold": "y_true"}
    )
    out = out.drop(columns=["y_true"]).merge(
        y_true_df, on=["stock_code", "week_start"], how="left"
    )
    out = out.dropna(subset=["y_true"]).reset_index(drop=True)

    if return_y_true:
        features = out.drop(columns=["y_true"])
        y_true = out["y_true"].reset_index(drop=True)
        return features, y_true

    return out