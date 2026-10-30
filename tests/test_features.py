"""Tests de features sin leakage (D.3)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models.features import FEATURE_COLS, build_features


@pytest.fixture
def synthetic_series():
    """Serie sintética: 80 semanas, patrón claro."""
    weeks = pd.date_range("2010-01-04", periods=80, freq="W-MON").date
    vals = 100 + 10 * np.sin(np.arange(80) * 2 * np.pi / 52)  # estacionalidad anual
    return pd.DataFrame({
        "stock_code": "TEST",
        "week_start": weeks,
        "units_sold": vals,
    })


def test_features_no_leakage(synthetic_series):
    """Las features del corte T no deben usar datos > T."""
    cutoff = synthetic_series["week_start"].iloc[60]
    features, y_true = build_features(synthetic_series, cutoff=cutoff, horizon=4)

    # lag_1 debe ser el valor real de la semana 60
    row = features[features["horizon"] == 1].iloc[0]
    assert abs(row["lag_1"] - synthetic_series["units_sold"].iloc[60]) < 1e-6


def test_features_excludes_insufficient_history():
    """Productos con <52 semanas no deben aparecer."""
    weeks = pd.date_range("2010-01-04", periods=30, freq="W-MON").date
    df = pd.DataFrame({
        "stock_code": "SHORT",
        "week_start": weeks,
        "units_sold": [10] * 30,
    })
    cutoff = df["week_start"].iloc[-1]
    features, y_true = build_features(df, cutoff=cutoff)
    assert features.empty


def test_features_has_all_columns(synthetic_series):
    """Todas las features esperadas deben estar presentes."""
    cutoff = synthetic_series["week_start"].iloc[60]
    features, y_true = build_features(synthetic_series, cutoff=cutoff)
    for c in FEATURE_COLS:
        assert c in features.columns


def test_y_true_has_same_length_as_features(synthetic_series):
    """y_true debe tener la misma longitud que features."""
    cutoff = synthetic_series["week_start"].iloc[60]
    features, y_true = build_features(synthetic_series, cutoff=cutoff, horizon=4)
    assert len(features) == len(y_true)


def test_features_no_y_true_column(synthetic_series):
    """y_true no debe estar en features (separado para evitar leakage)."""
    cutoff = synthetic_series["week_start"].iloc[60]
    features, y_true = build_features(synthetic_series, cutoff=cutoff, horizon=4)
    assert "y_true" not in features.columns


def test_features_horizon_validation(synthetic_series):
    """horizon debe estar entre 1 y 12."""
    cutoff = synthetic_series["week_start"].iloc[60]
    with pytest.raises(ValueError):
        build_features(synthetic_series, cutoff=cutoff, horizon=0)
    with pytest.raises(ValueError):
        build_features(synthetic_series, cutoff=cutoff, horizon=13)


def test_features_return_y_true_false(synthetic_series):
    """return_y_true=False devuelve un solo DataFrame con y_true."""
    cutoff = synthetic_series["week_start"].iloc[60]
    out = build_features(
        synthetic_series, cutoff=cutoff, horizon=4, return_y_true=False
    )
    assert isinstance(out, pd.DataFrame)
    assert "y_true" in out.columns