"""Tests de métricas y baselines (D.2)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.models.backtest import rolling_origin_splits
from src.models.baselines import (
    drift_forecast,
    mean_forecast,
    moving_average_forecast,
    naive_forecast,
    seasonal_naive_forecast,
)
from src.models.metrics import (
    bias,
    coverage,
    evaluate_forecast,
    mae,
    mase,
    wape,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tiny_df():
    """DataFrame de juguete con dos productos, 6 semanas."""
    rows = []
    weeks = pd.date_range("2010-01-04", periods=6, freq="W-MON").date
    for sc, vals in [("A", [1, 2, 3, 4, 5, 6]), ("B", [10, 20, 30, 40, 50, 60])]:
        for w, v in zip(weeks, vals):
            rows.append({"stock_code": sc, "week_start": w, "units_sold": v})
    return pd.DataFrame(rows)


@pytest.fixture
def seasonal_df():
    """DataFrame con 60 semanas y patrón estacional (1..52, 1..8)."""
    weeks = pd.date_range("2010-01-04", periods=60, freq="W-MON").date
    values = [(i % 52) + 1 for i in range(60)]
    return pd.DataFrame({
        "stock_code": "A",
        "week_start": weeks,
        "units_sold": values,
    })


# ---------------------------------------------------------------------------
# Métricas: MAE
# ---------------------------------------------------------------------------

def test_mae_perfect():
    """MAE con predicción perfecta = 0."""
    assert mae(np.array([1, 2, 3]), np.array([1, 2, 3])) == 0.0


def test_mae_known():
    """MAE con error conocido = 0.5."""
    assert mae(np.array([1, 2, 3]), np.array([1.5, 2.5, 3.5])) == pytest.approx(0.5)


def test_mae_empty_returns_nan():
    """MAE con arrays vacíos → NaN (no excepción)."""
    result = mae(np.array([]), np.array([]))
    assert np.isnan(result)


# ---------------------------------------------------------------------------
# Métricas: WAPE
# ---------------------------------------------------------------------------

def test_wape_known():
    """WAPE con error conocido = 0.25."""
    assert wape(np.array([1, 2, 3]), np.array([1.5, 2.5, 3.5])) == pytest.approx(0.25)


def test_wape_zero_true():
    """WAPE con y_true todo ceros → NaN (no división por cero)."""
    assert np.isnan(wape(np.array([0, 0]), np.array([0, 0])))


def test_wape_perfect():
    """WAPE con predicción perfecta = 0."""
    assert wape(np.array([1, 2, 3]), np.array([1, 2, 3])) == 0.0


# ---------------------------------------------------------------------------
# Métricas: Bias
# ---------------------------------------------------------------------------

def test_bias_positive():
    """Bias positivo cuando sobre-predice."""
    assert bias(np.array([1, 2, 3]), np.array([1.5, 2.5, 3.5])) == pytest.approx(0.5)


def test_bias_negative():
    """Bias negativo cuando infra-predice."""
    assert bias(np.array([1.5, 2.5, 3.5]), np.array([1, 2, 3])) == pytest.approx(-0.5)


def test_bias_zero():
    """Bias cero cuando predicción perfecta."""
    assert bias(np.array([1, 2, 3]), np.array([1, 2, 3])) == 0.0


# ---------------------------------------------------------------------------
# Métricas: MASE
# ---------------------------------------------------------------------------

def test_mase_perfect_is_zero():
    """MASE con predicción perfecta = 0."""
    y_train = np.array([1, 2, 3, 4, 5, 6, 7, 8])
    assert mase(y_train, y_train, y_train, seasonality=1) == pytest.approx(0.0)


def test_mase_insufficient_history():
    """MASE con historia insuficiente → NaN."""
    assert np.isnan(mase(
        np.array([1, 2]), np.array([1, 2]),
        np.array([1, 2]), seasonality=52,
    ))


def test_mase_seasonal():
    """MASE con seasonality=2 y serie no perfectamente periódica."""
    y_train = np.array([1, 2, 3, 4, 1, 2, 3, 4])  # no perfectamente periódica con seasonality=2
    y_true = np.array([1, 2])
    y_pred = np.array([1, 2])
    result = mase(y_true, y_pred, y_train, seasonality=2)
    assert result == pytest.approx(0.0)


def test_mase_zero_scale():
    """MASE con serie constante (escala 0) → NaN."""
    y_train = np.array([5, 5, 5, 5])
    result = mase(np.array([5]), np.array([5]), y_train, seasonality=1)
    assert np.isnan(result)


def test_mase_worse_than_naive():
    """MASE > 1 si el modelo es peor que el naive."""
    y_train = np.array([1, 2, 3, 4, 5, 6])
    # Naive in-sample: errores = [1, 1, 1, 1, 1], escala = 1
    # Modelo predice 0 cuando real es 10 → error = 10 → MASE = 10
    result = mase(np.array([10]), np.array([0]), y_train, seasonality=1)
    assert result > 1.0


# ---------------------------------------------------------------------------
# Métricas: Coverage
# ---------------------------------------------------------------------------

def test_coverage_perfect():
    """Todos los valores dentro del intervalo → cobertura 100%."""
    y_true = np.array([1, 2, 3])
    lower = np.array([0, 0, 0])
    upper = np.array([5, 5, 5])
    assert coverage(y_true, lower, upper) == 1.0


def test_coverage_partial():
    """Solo 2 de 3 dentro → cobertura 2/3."""
    y_true = np.array([1, 2, 10])
    lower = np.array([0, 0, 0])
    upper = np.array([5, 5, 5])
    assert coverage(y_true, lower, upper) == pytest.approx(2 / 3)


def test_coverage_zero():
    """Ninguno dentro → cobertura 0%."""
    y_true = np.array([10, 20, 30])
    lower = np.array([0, 0, 0])
    upper = np.array([5, 5, 5])
    assert coverage(y_true, lower, upper) == 0.0


def test_coverage_at_boundary():
    """Valores exactamente en los límites → dentro."""
    y_true = np.array([0, 5])
    lower = np.array([0, 0])
    upper = np.array([5, 5])
    assert coverage(y_true, lower, upper) == 1.0


# ---------------------------------------------------------------------------
# evaluate_forecast
# ---------------------------------------------------------------------------

def test_evaluate_forecast_single_group():
    """evaluate_forecast con un solo grupo (sin group_cols)."""
    df = pd.DataFrame({
        "units_sold": [100, 120, 80],
        "y_pred": [110, 115, 90],
    })
    result = evaluate_forecast(df)
    assert len(result) == 1
    assert result["n_obs"].iloc[0] == 3
    assert result["mae"].iloc[0] == pytest.approx(8.33, abs=0.01)
    assert "wape" in result.columns
    assert "bias" in result.columns


def test_evaluate_forecast_grouped():
    """evaluate_forecast agrupado por producto."""
    df = pd.DataFrame({
        "stock_code": ["A", "A", "A", "B", "B", "B"],
        "units_sold": [100, 120, 80, 200, 180, 220],
        "y_pred": [110, 115, 90, 190, 200, 210],
    })
    result = evaluate_forecast(df, group_cols=["stock_code"])
    assert len(result) == 2
    assert set(result["stock_code"]) == {"A", "B"}
    assert "mae" in result.columns
    assert "wape" in result.columns
    assert "bias" in result.columns


def test_evaluate_forecast_with_coverage():
    """evaluate_forecast calcula cobertura si hay lower/upper."""
    df = pd.DataFrame({
        "units_sold": [100, 120, 80],
        "y_pred": [110, 115, 90],
        "lower": [90, 110, 70],
        "upper": [130, 130, 100],
    })
    result = evaluate_forecast(df, lower_col="lower", upper_col="upper")
    assert "coverage" in result.columns
    assert result["coverage"].iloc[0] == 1.0


# ---------------------------------------------------------------------------
# Baseline: Mean
# ---------------------------------------------------------------------------

def test_mean_forecast(tiny_df):
    """Mean: predice la media histórica."""
    out = mean_forecast(tiny_df)
    # A: media de [1,2,3,4,5,6] = 3.5
    assert out.loc[out["stock_code"] == "A", "y_pred"].iloc[0] == pytest.approx(3.5)
    # B: media de [10,20,30,40,50,60] = 35.0
    assert out.loc[out["stock_code"] == "B", "y_pred"].iloc[0] == pytest.approx(35.0)


def test_mean_forecast_horizon(tiny_df):
    """Mean devuelve `horizon` filas por producto."""
    out = mean_forecast(tiny_df, horizon=3)
    # 2 productos × 3 horizontes = 6 filas
    assert len(out) == 6
    assert "week_start" in out.columns


# ---------------------------------------------------------------------------
# Baseline: Naive
# ---------------------------------------------------------------------------

def test_naive_forecast(tiny_df):
    """Naive: predice la última observación."""
    out = naive_forecast(tiny_df)
    assert set(out["stock_code"]) == {"A", "B"}
    assert out.loc[out["stock_code"] == "A", "y_pred"].iloc[0] == 6.0
    assert out.loc[out["stock_code"] == "B", "y_pred"].iloc[0] == 60.0


def test_naive_forecast_horizon(tiny_df):
    """Naive devuelve `horizon` filas por producto."""
    out = naive_forecast(tiny_df, horizon=3)
    assert len(out) == 6
    a_preds = out[out["stock_code"] == "A"]
    assert (a_preds["y_pred"] == 6.0).all()
    assert a_preds["week_start"].nunique() == 3


# ---------------------------------------------------------------------------
# Baseline: Seasonal naive
# ---------------------------------------------------------------------------

def test_seasonal_naive_fallback(tiny_df):
    """Sin historia suficiente → fallback a naive."""
    out = seasonal_naive_forecast(tiny_df, seasonality=52)
    assert out.loc[out["stock_code"] == "A", "y_pred"].iloc[0] == 6.0


def test_seasonal_naive_with_full_history(seasonal_df):
    """Seasonal naive con 52+ semanas → predicciones de hace 52 semanas."""
    out = seasonal_naive_forecast(seasonal_df, horizon=4, seasonality=52)
    assert len(out) == 4
    # seasonal_df: 60 semanas, values = [(i % 52) + 1]
    # base = iloc[-52:-48] = iloc[8:12] = [9, 10, 11, 12]
    preds = out.sort_values("week_start")["y_pred"].values
    assert preds[0] == pytest.approx(9.0)
    assert preds[1] == pytest.approx(10.0)
    assert preds[2] == pytest.approx(11.0)
    assert preds[3] == pytest.approx(12.0)

# ---------------------------------------------------------------------------
# Baseline: Moving average
# ---------------------------------------------------------------------------

def test_moving_average_forecast(tiny_df):
    """Moving average: media de las últimas `window` semanas."""
    out = moving_average_forecast(tiny_df, window=4)
    # A: media de [3,4,5,6] = 4.5
    assert out.loc[out["stock_code"] == "A", "y_pred"].iloc[0] == pytest.approx(4.5)


def test_moving_average_window_greater_than_history(tiny_df):
    """Si window > historia, media de todo."""
    out = moving_average_forecast(tiny_df, window=10)
    # A: media de [1,2,3,4,5,6] = 3.5
    assert out.loc[out["stock_code"] == "A", "y_pred"].iloc[0] == pytest.approx(3.5)


# ---------------------------------------------------------------------------
# Baseline: Drift
# ---------------------------------------------------------------------------

def test_drift_forecast_positive_trend(tiny_df):
    """Drift captura tendencia positiva."""
    out = drift_forecast(tiny_df, horizon=1)
    # A: última = 6, anterior = 5 → slope = 1 → h=1: 6 + 1 = 7
    assert out.loc[out["stock_code"] == "A", "y_pred"].iloc[0] == pytest.approx(7.0)
    # B: última = 60, anterior = 50 → slope = 10 → h=1: 60 + 10 = 70
    assert out.loc[out["stock_code"] == "B", "y_pred"].iloc[0] == pytest.approx(70.0)


def test_drift_forecast_multiple_horizons(tiny_df):
    """Drift con horizon=3 → predicciones lineales."""
    out = drift_forecast(tiny_df, horizon=3)
    a_preds = out[out["stock_code"] == "A"].sort_values("week_start")
    # slope = 1, última = 6 → h=1:7, h=2:8, h=3:9
    assert a_preds["y_pred"].iloc[0] == pytest.approx(7.0)
    assert a_preds["y_pred"].iloc[1] == pytest.approx(8.0)
    assert a_preds["y_pred"].iloc[2] == pytest.approx(9.0)


def test_drift_forecast_no_negative():
    """Drift no debe predecir valores negativos."""
    df = pd.DataFrame({
        "stock_code": ["A"] * 5,
        "week_start": pd.date_range("2010-01-04", periods=5, freq="W-MON"),
        "units_sold": [100, 50, 20, 5, 1],
    })
    out = drift_forecast(df, horizon=4)
    assert (out["y_pred"] >= 0).all()


def test_drift_forecast_insufficient_history(tiny_df):
    """Con < 2 observaciones, fallback a naive."""
    df = tiny_df[tiny_df["stock_code"] == "A"].head(1).copy()
    out = drift_forecast(df, horizon=2)
    assert (out["y_pred"] == 1.0).all()


# ---------------------------------------------------------------------------
# Backtesting splitter
# ---------------------------------------------------------------------------

def test_rolling_origin_splits():
    """Genera n_splits cortes que avanzan en el tiempo."""
    weeks = [date(2010, 1, 4) + pd.Timedelta(weeks=i) for i in range(120)]
    splits = rolling_origin_splits(weeks, horizon=4, n_splits=5)
    assert len(splits) == 5
    # Los cortes deben avanzar
    for a, b in zip(splits, splits[1:]):
        assert a.cutoff < b.cutoff
    # Los test no se solapan
    for a, b in zip(splits, splits[1:]):
        assert a.test_end < b.test_start


def test_rolling_origin_splits_with_step():
    """Con step > horizon, los tests tienen huecos."""
    weeks = [date(2010, 1, 4) + pd.Timedelta(weeks=i) for i in range(120)]
    splits = rolling_origin_splits(weeks, horizon=4, n_splits=3, step=8)
    assert len(splits) == 3
    # Tests separados 8 semanas, horizon 4 → huecos de 4 semanas
    for a, b in zip(splits, splits[1:]):
        gap = (b.test_start - a.test_end).days // 7
        assert gap > 1


def test_rolling_origin_insufficient_data():
    """Con pocas semanas → ValueError."""
    weeks = [date(2010, 1, 4)] * 10
    with pytest.raises(ValueError):
        rolling_origin_splits(weeks, horizon=4, n_splits=8)


def test_rolling_origin_train_has_52_weeks():
    """El train debe tener al menos 53 semanas."""
    weeks = [date(2010, 1, 4) + pd.Timedelta(weeks=i) for i in range(120)]
    splits = rolling_origin_splits(weeks, horizon=4, n_splits=3)
    for s in splits:
        n_train_weeks = (s.train_end - s.train_start).days // 7 + 1
        assert n_train_weeks >= 53