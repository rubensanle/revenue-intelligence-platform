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
    }
    assert set(df["trend"].unique()) <= valid, \
        f"Tipos inesperados: {set(df['trend'].unique()) - valid}"
    assert len(df) > 0

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