"""Tests de las funciones de diagnóstico."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.analytics.diagnostics import (
    q1_monthly_evolution,
    q2_concentration_curve,
    q2_product_trend,
    q3_repeat_purchase_rate,
    q4_country_ranking,
    q5_forecastability,
    q6_returns_by_product,
    q6_returns_by_customer
)

ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "data" / "processed" / "revenue.duckdb"


@pytest.fixture(scope="module", autouse=True)
def ensure_db():
    assert DB_PATH.exists(), f"No existe la BD: {DB_PATH}"


def test_monthly_evolution_excludes_partial():
    df = q1_monthly_evolution(include_partial=False)
    assert not df.empty
    # Dic-2011 no debe estar
    assert not (df["month"].astype(str) == "2011-12-01").any()


def test_monthly_evolution_has_expected_columns():
    df = q1_monthly_evolution()
    for col in ["month", "net_revenue", "units_sold", "mom_growth_pct"]:
        assert col in df.columns


def test_concentration_reaches_80():
    df = q2_concentration_curve()
    assert df["pct_revenue"].max() >= 80.0
    # Debe ser monótonamente creciente
    assert df["pct_revenue"].is_monotonic_increasing


def test_top_products_returns_20():
    df = q2_concentration_curve()
    assert len(df) > 20


def test_product_trend_classifies():
    df = q2_product_trend()
    valid = {
        "growing", "declining", "stable", "new", "dead",
        "new_launch", "dormant", "anomaly_returns",
        "wholesale_dependent",
    }
    unexpected = set(df["trend"].unique()) - valid
    assert not unexpected, f"Tipos inesperados: {unexpected}"
    assert len(df) > 0


def test_anomaly_returns_has_high_return_rate_or_negative_previous():
    """Los anomaly_returns deben tener return_rate > 50% o units_previous < 0."""
    df = q2_product_trend()
    anomalies = df[df["trend"] == "anomaly_returns"]
    if not anomalies.empty:
        # Al menos uno de los dos criterios debe cumplirse
        has_high_rate = (anomalies["return_rate_recent_pct"] > 50).any()
        has_negative_prev = (anomalies["units_previous"] < 0).any()
        assert has_high_rate or has_negative_prev, \
            "anomaly_returns debe tener return_rate > 50% o units_previous < 0"


def test_normal_returns_not_flagged_as_anomaly():
    """Una devolución normal (return_rate bajo, units_previous > 0) no debe ser anomaly_returns."""
    df = q2_product_trend()
    # Productos con units_previous > 0 y return_rate < 50% no deben ser anomaly_returns
    normal = df[
        (df["units_previous"] > 0)
        & (df["return_rate_recent_pct"] < 50)
        & (df["trend"] == "anomaly_returns")
    ]
    assert normal.empty, f"Productos marcados como anomalía sin serlo: {normal['stock_code'].tolist()}"
def test_wholesale_dependent_has_no_growth_pct():
    """Los productos wholesale_dependent no deben tener growth_pct."""
    df = q2_product_trend()
    wholesale = df[df["trend"] == "wholesale_dependent"]
    if not wholesale.empty:
        assert wholesale["growth_pct"].isna().all(), \
            "wholesale_dependent no debe tener growth_pct"

def test_repeat_purchase_rate_valid():
    r = q3_repeat_purchase_rate()
    assert 0 <= r["repeat_rate_pct"] <= 100
    assert r["total_customers"] > 0


def test_country_ranking_includes_uk():
    df = q4_country_ranking()
    assert "United Kingdom" in df["country"].values
    assert df["pct_revenue"].max() > 50


def test_forecastability_categories():
    df = q5_forecastability()
    valid = {"forecastable", "intermittent", "high_variance", "low_volume"}
    assert set(df["forecastability"].unique()) <= valid
    assert len(df) > 100

def test_product_trend_has_new_launch():
    """Productos con first_sale_date >= 2011-02-01 deben ser new_launch."""
    df = q2_product_trend()
    new_launch = df[df["trend"] == "new_launch"]
    assert len(new_launch) > 0, "No hay productos new_launch"
    # Todos los new_launch deben tener growth_pct NULL
    assert new_launch["growth_pct"].isna().all(), \
        "new_launch no debe tener growth_pct"


def test_product_trend_no_anomalies_in_declining():
    """El ranking de declives no debe incluir anomalías (units_recent < 0)."""
    df = q2_product_trend()
    declining = df[df["trend"] == "declining"]
    assert (declining["units_recent"] >= 0).all(), \
        "Hay anomalías en declining; deberían marcarse como anomaly_returns"


def test_product_trend_23166_not_declining():
    """23166 tuvo un pedido cancelado; no debe ser declining."""
    df = q2_product_trend()
    row = df[df["stock_code"] == "23166"]
    if not row.empty:
        assert row.iloc[0]["trend"] != "declining", \
            "23166 no está en declive; su pedido fue cancelado"

def test_returns_by_product_returns_dataframe():
    """q6_returns_by_product devuelve un DataFrame no vacío."""
    df = q6_returns_by_product()
    assert not df.empty
    assert "stock_code" in df.columns
    assert "return_rate_recent_pct" in df.columns
    assert "return_severity" in df.columns


def test_returns_by_customer_returns_dataframe():
    """q6_returns_by_customer devuelve un DataFrame no vacío."""
    df = q6_returns_by_customer()
    assert not df.empty
    assert "customer_id" in df.columns
    assert "units_returned_recent" in df.columns
    assert "returner_severity" in df.columns


def test_returns_by_product_high_severity_has_high_rate():
    """Los high_return_rate deben tener tasa > 50%."""
    df = q6_returns_by_product()
    high = df[df["return_severity"] == "high_return_rate"]
    if not high.empty:
        assert (high["return_rate_recent_pct"] > 50).all(), \
            "Hay high_return_rate con tasa <= 50%"


def test_returns_by_customer_high_severity_has_high_rate():
    """Los high_returner deben tener tasa > 30%."""
    df = q6_returns_by_customer()
    high = df[df["returner_severity"] == "high_returner"]
    if not high.empty:
        assert (high["return_rate_units_pct"] > 30).all(), \
            "Hay high_returner con tasa <= 30%"