"""Tests de persistencia de forecast (D.4)."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "data" / "processed" / "revenue.duckdb"


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect(str(DB_PATH), read_only=True)
    yield c
    c.close()


def test_forecast_weekly_exists(con):
    n = con.execute("SELECT COUNT(*) FROM forecast_weekly").fetchone()[0]
    assert n > 0


def test_forecast_weekly_4_weeks(con):
    weeks = con.execute(
        "SELECT DISTINCT week_start FROM forecast_weekly ORDER BY 1"
    ).fetchall()
    assert len(weeks) == 4


def test_forecast_weekly_intervals_valid(con):
    """lower <= y_pred <= upper en todas las filas."""
    n_bad = con.execute("""
        SELECT COUNT(*) FROM forecast_weekly
        WHERE lower > y_pred OR y_pred > upper OR lower < 0
    """).fetchone()[0]
    assert n_bad == 0


def test_forecast_weekly_products_match(con):
    """
    El número de productos en forecast_weekly debe ser menor o igual
    que los forecastable (algunos no tienen historia suficiente).
    """
    n_fc = con.execute(
        "SELECT COUNT(DISTINCT stock_code) FROM forecast_weekly"
    ).fetchone()[0]
    n_fp = con.execute("""
        SELECT COUNT(*) FROM v_forecastable_products
        WHERE forecastability = 'forecastable'
    """).fetchone()[0]
    assert n_fc > 0, "forecast_weekly está vacía"
    assert n_fc <= n_fp, f"forecast_weekly tiene más productos ({n_fc}) que forecastable ({n_fp})"
    # Al menos el 80% de los forecastable deberían tener forecast
    assert n_fc >= 0.8 * n_fp, f"Solo {n_fc}/{n_fp} productos tienen forecast"