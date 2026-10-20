"""Tests del modelo relacional."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from src.utils.constants import (
    CLEAN_TABLE,
    DIM_CUSTOMER,
    DIM_DATE,
    DIM_PRODUCT,
    FACT_TABLE,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "data" / "processed" / "revenue.duckdb"


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect(str(DB_PATH), read_only=True)
    yield c
    c.close()


def test_fact_matches_clean(con):
    """fact_sales_line debe tener exactamente las mismas filas que clean_transactions."""
    n_clean = con.execute(f"SELECT COUNT(*) FROM {CLEAN_TABLE}").fetchone()[0]
    n_fact = con.execute(f"SELECT COUNT(*) FROM {FACT_TABLE}").fetchone()[0]
    assert n_clean == n_fact


def test_fact_revenue_totals_match(con):
    """La suma de line_value debe coincidir entre clean y fact."""
    s_clean = con.execute(f"SELECT SUM(line_value) FROM {CLEAN_TABLE}").fetchone()[0]
    s_fact = con.execute(f"SELECT SUM(line_value) FROM {FACT_TABLE}").fetchone()[0]
    assert abs(s_clean - s_fact) < 1e-6


def test_dim_product_excludes_non_products(con):
    """Ningún código no-producto debe estar en dim_product."""
    n_bad = con.execute(f"""
        SELECT COUNT(*) FROM {DIM_PRODUCT}
        WHERE stock_code IN ('POST', 'DOT', 'M', 'BANK CHARGES', 'AMAZONFEE')
    """).fetchone()[0]
    assert n_bad == 0


def test_dim_customer_has_no_nulls(con):
    """dim_customer no debe contener customer_id nulos."""
    n_nulls = con.execute(f"""
        SELECT COUNT(*) FROM {DIM_CUSTOMER} WHERE customer_id IS NULL
    """).fetchone()[0]
    assert n_nulls == 0


def test_dim_date_is_continuous(con):
    """El calendario debe ser continuo: max - min + 1 = número de días."""
    row = con.execute(f"""
        SELECT
            MIN(date) AS d_min,
            MAX(date) AS d_max,
            COUNT(*) AS n
        FROM {DIM_DATE}
    """).fetchone()
    expected = (row[1] - row[0]).days + 1
    assert row[2] == expected, f"Calendario discontinuo: {row[2]} días, se esperaban {expected}"