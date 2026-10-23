"""
Módulo D.2 — Baselines de forecasting.

Cinco baselines triviales pero competitivos:
    - Mean: media histórica.
    - Naive: última observación.
    - Seasonal naive: misma semana del año anterior (52 semanas atrás).
    - Moving average 4: media de las últimas 4 semanas.
    - Drift: última observación + tendencia lineal.

Se usan como referencia. Si LightGBM no les gana, no merece la pena.

Todos operan sobre un DataFrame con columnas:
    stock_code, week_start, units_sold

Y devuelven un DataFrame con columnas:
    stock_code, week_start, y_pred

Nota: devuelven una fila por (stock_code, week_start) para el horizonte
indicado. Si quieres evaluar con evaluate_forecast, agrega por producto.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Asegura el tipo de week_start y ordena."""
    df = df.copy()
    df["week_start"] = pd.to_datetime(df["week_start"])
    df = df.sort_values(["stock_code", "week_start"]).reset_index(drop=True)
    return df


def _future_weeks(last_week: pd.Timestamp, horizon: int) -> list[pd.Timestamp]:
    """Genera las próximas `horizon` semanas después de `last_week`."""
    return [last_week + pd.Timedelta(weeks=h) for h in range(1, horizon + 1)]


def _safe_mean(arr: np.ndarray) -> float:
    """Media robusta: ignora NaN, devuelve 0 si todo es NaN."""
    if len(arr) == 0:
        return 0.0
    if np.all(np.isnan(arr)):
        return 0.0
    return float(np.nanmean(arr))


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------

def mean_forecast(df: pd.DataFrame, horizon: int = 4) -> pd.DataFrame:
    """
    Mean: ŷ(t+h) = mean(y) para todo h.
    Trivial, pero útil como referencia.
    """
    df = _prepare(df)
    out_rows = []
    for sc, g in df.groupby("stock_code"):
        g = g.sort_values("week_start").reset_index(drop=True)
        val = _safe_mean(g["units_sold"].values)
        last_week = g["week_start"].iloc[-1]
        for week in _future_weeks(last_week, horizon):
            out_rows.append({"stock_code": sc, "week_start": week, "y_pred": val})
    return pd.DataFrame(out_rows)


def naive_forecast(df: pd.DataFrame, horizon: int = 4) -> pd.DataFrame:
    """
    Naive: ŷ(t+h) = y(t) para todo h.
    Aplana la última observación hacia el futuro.
    """
    df = _prepare(df)
    out_rows = []
    for sc, g in df.groupby("stock_code"):
        g = g.sort_values("week_start").reset_index(drop=True)
        val = float(g["units_sold"].iloc[-1]) if len(g) > 0 else 0.0
        last_week = g["week_start"].iloc[-1]
        for week in _future_weeks(last_week, horizon):
            out_rows.append({"stock_code": sc, "week_start": week, "y_pred": val})
    return pd.DataFrame(out_rows)


def seasonal_naive_forecast(
    df: pd.DataFrame, horizon: int = 4, seasonality: int = 52,
) -> pd.DataFrame:
    """
    Seasonal naive: ŷ(t+h) = y(t + h - seasonality).
    Con seasonality=52 en semanal, es "misma semana del año anterior".

    Si no hay historia suficiente, fallback a naive.
    Si horizon > seasonality, repite el patrón de las últimas `seasonality`
    semanas del año anterior (con np.tile).
    """
    df = _prepare(df)
    out_rows = []
    for sc, g in df.groupby("stock_code"):
        g = g.sort_values("week_start").reset_index(drop=True)
        n = len(g)
        last_week = g["week_start"].iloc[-1]
        future = _future_weeks(last_week, horizon)

        if n < seasonality:
            # Sin historia suficiente: fallback a naive (última observación)
            val = float(g["units_sold"].iloc[-1]) if n > 0 else 0.0
            for week in future:
                out_rows.append({"stock_code": sc, "week_start": week, "y_pred": val})
        else:
            # Semanas de hace `seasonality` semanas: y(t + h - seasonality)
            # Son las semanas en posición [-seasonality : -seasonality + horizon]
            base = g["units_sold"].iloc[-seasonality:-seasonality + horizon].values
            if horizon <= seasonality:
                preds = base
            else:
                # Repetir el patrón si horizon > seasonality
                preds = np.tile(base, int(np.ceil(horizon / seasonality)))[:horizon]
            for week, val in zip(future, preds):
                out_rows.append({
                    "stock_code": sc,
                    "week_start": week,
                    "y_pred": float(val),
                })
    return pd.DataFrame(out_rows)


def moving_average_forecast(
    df: pd.DataFrame, window: int = 4, horizon: int = 4,
) -> pd.DataFrame:
    """
    Moving average: ŷ(t+h) = mean(y(t-window+1 .. t)).
    Aplana la media móvil hacia el futuro.
    """
    df = _prepare(df)
    out_rows = []
    for sc, g in df.groupby("stock_code"):
        g = g.sort_values("week_start").reset_index(drop=True)
        n = len(g)
        last_week = g["week_start"].iloc[-1]
        future = _future_weeks(last_week, horizon)

        if n < window:
            val = _safe_mean(g["units_sold"].values)
        else:
            val = _safe_mean(g["units_sold"].iloc[-window:].values)
        for week in future:
            out_rows.append({"stock_code": sc, "week_start": week, "y_pred": val})
    return pd.DataFrame(out_rows)


def drift_forecast(df: pd.DataFrame, horizon: int = 4) -> pd.DataFrame:
    """
    Drift: ŷ(t+h) = y(t) + h * (y(t) - y(t-1)).
    Última observación + tendencia lineal.

    Si no hay 2 observaciones, fallback a naive.
    """
    df = _prepare(df)
    out_rows = []
    for sc, g in df.groupby("stock_code"):
        g = g.sort_values("week_start").reset_index(drop=True)
        n = len(g)
        last_week = g["week_start"].iloc[-1]
        future = _future_weeks(last_week, horizon)

        if n < 2:
            val = float(g["units_sold"].iloc[-1]) if n > 0 else 0.0
            for week in future:
                out_rows.append({"stock_code": sc, "week_start": week, "y_pred": val})
        else:
            y_t = float(g["units_sold"].iloc[-1])
            y_prev = float(g["units_sold"].iloc[-2])
            slope = y_t - y_prev
            for h, week in enumerate(future, start=1):
                pred = y_t + h * slope
                out_rows.append({
                    "stock_code": sc,
                    "week_start": week,
                    "y_pred": max(0.0, pred),  # no predecir negativo
                })
    return pd.DataFrame(out_rows)