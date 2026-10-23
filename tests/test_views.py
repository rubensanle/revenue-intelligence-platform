"""Tests de la capa semántica (vistas SQL)."""

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


def test_net_revenue_matches_fact(con):
    """La suma de net_revenue en la vista debe coincidir con fact_sales_line."""
    v = con.execute("SELECT SUM(net_revenue_line) FROM v_sales_lines").fetchone()[0]
    f = con.execute("SELECT SUM(line_value) FROM fact_sales_line").fetchone()[0]
    assert abs(v - f) < 1, f"Descuadre: vista={v}, fact={f}"


def test_net_revenue_never_exceeds_gross(con):
    """net_revenue ≤ gross_revenue porque excluye devoluciones y precios 0."""
    row = con.execute("""
        SELECT
            SUM(gross_revenue_line) AS g,
            SUM(net_revenue_line)   AS n
        FROM v_sales_lines
    """).fetchone()
    assert row[1] <= row[0], f"gross ({row[1]}) > net ({row[0]})"


def test_units_reconciliation(con):
    """units_net = units_sold - returns."""
    row = con.execute("""
        SELECT
            SUM(units_net_line)  AS net,
            SUM(units_sold_line) AS sold,
            SUM(returns_line)    AS ret
        FROM v_sales_lines
    """).fetchone()
    assert row[0] == row[1] - row[2], f"Descuadre: net={row[0]}, sold={row[1]}, returns={row[2]}"


def test_daily_aggregation_totals_match(con):
    """v_revenue_daily debe sumar lo mismo que v_sales_lines."""
    total_daily = con.execute("SELECT SUM(net_revenue) FROM v_revenue_daily").fetchone()[0]
    total_lines = con.execute("SELECT SUM(net_revenue_line) FROM v_sales_lines").fetchone()[0]
    assert abs(total_daily - total_lines) < 1
    f"Descuadre: daily={total_daily}, lines={total_lines}, diff={abs(total_daily - total_lines)}"


def test_product_aggregation_excludes_non_products(con):
    """v_revenue_by_product no debe tener códigos no-producto."""
    n_bad = con.execute("""
        SELECT COUNT(*) FROM v_revenue_by_product
        WHERE stock_code IN ('POST', 'DOT', 'M', 'BANK CHARGES', 'AMAZONFEE')
    """).fetchone()[0]
    assert n_bad == 0


def test_rfm_covers_all_identified_customers(con):
    """v_rfm_segments debe tener tantos clientes como dim_customer."""
    rfm = con.execute("SELECT COUNT(*) FROM v_rfm_segments").fetchone()[0]
    dim = con.execute("SELECT COUNT(*) FROM dim_customer").fetchone()[0]
    assert rfm == dim


def test_rfm_scores_in_range(con):
    """Los scores RFM deben estar entre 1 y 5."""
    row = con.execute("""
        SELECT
            MIN(r_score), MAX(r_score),
            MIN(f_score), MAX(f_score),
            MIN(m_score), MAX(m_score)
        FROM v_rfm_segments
    """).fetchone()
    assert row[0] >= 1 and row[1] <= 5
    assert row[2] >= 1 and row[3] <= 5
    assert row[4] >= 1 and row[5] <= 5


def test_concentration_reaches_100(con):
    """El % acumulado final debe llegar a ~100%."""
    max_pct = con.execute("SELECT MAX(cumulative_pct) FROM v_product_concentration").fetchone()[0]
    assert 99.0 <= max_pct <= 101.0, f"Concentración final: {max_pct}%"


def test_growth_has_data(con):
    """v_monthly_growth debe tener ~24 meses (excluyendo el parcial puede ser 23–24)."""
    n = con.execute("SELECT COUNT(*) FROM v_monthly_growth").fetchone()[0]
    assert 20 <= n <= 26, f"Meses inesperados: {n}"

def test_net_revenue_matches_fact(con):
    """La suma de net_revenue en la vista debe coincidir con fact_sales_line."""
    v = con.execute("SELECT SUM(net_revenue_line) FROM v_sales_lines").fetchone()[0]
    f = con.execute("SELECT SUM(line_value) FROM fact_sales_line").fetchone()[0]
    assert abs(v - f) < 0.01, f"Descuadre: vista={v}, fact={f}"

def test_rfm_semantics(con):
    """Los champion deben tener menor recencia y mayor gasto que los lost."""
    champ = con.execute("""
        SELECT AVG(recency_days), AVG(monetary) FROM v_rfm_segments
        WHERE rfm_segment = 'champion'
    """).fetchone()
    lost = con.execute("""
        SELECT AVG(recency_days), AVG(monetary) FROM v_rfm_segments
        WHERE rfm_segment = 'lost'
    """).fetchone()

    assert champ[0] < lost[0], "Champion debería tener menor recencia que lost"
    assert champ[1] > lost[1], "Champion debería tener mayor gasto que lost"


def test_returns_by_product_has_data(con):
    """v_returns_by_product debe tener datos."""
    n = con.execute("SELECT COUNT(*) FROM v_returns_by_product").fetchone()[0]
    assert n > 0, "v_returns_by_product está vacía"


def test_returns_by_product_rates_in_range(con):
    """Las tasas de devolución deben estar entre 0 y 100."""
    row = con.execute("""
        SELECT MIN(return_rate_recent_pct), MAX(return_rate_recent_pct)
        FROM v_returns_by_product
        WHERE return_rate_recent_pct IS NOT NULL
    """).fetchone()
    assert row[0] >= 0, f"Tasa mínima negativa: {row[0]}"
    assert row[1] <= 100, f"Tasa máxima > 100: {row[1]}"


def test_returns_by_product_severity_valid(con):
    """Las severidades deben ser válidas."""
    valid = {"no_returns", "no_sales", "high_return_rate", "medium_return_rate", "low_return_rate"}
    rows = con.execute("SELECT DISTINCT return_severity FROM v_returns_by_product").fetchall()
    actual = {r[0] for r in rows}
    assert actual <= valid, f"Severidades inválidas: {actual - valid}"


def test_returns_by_customer_has_data(con):
    """v_returns_by_customer debe tener datos."""
    n = con.execute("SELECT COUNT(*) FROM v_returns_by_customer").fetchone()[0]
    assert n > 0, "v_returns_by_customer está vacía"


def test_returns_by_customer_severity_valid(con):
    """Las severidades de cliente deben ser válidas."""
    valid = {"no_returns", "high_returner", "medium_returner", "low_returner"}
    rows = con.execute("SELECT DISTINCT returner_severity FROM v_returns_by_customer").fetchall()
    actual = {r[0] for r in rows}
    assert actual <= valid, f"Severidades inválidas: {actual - valid}"


def test_returns_by_customer_no_null_customer_id(con):
    """No debe haber customer_id nulos."""
    n = con.execute("""
        SELECT COUNT(*) FROM v_returns_by_customer WHERE customer_id IS NULL
    """).fetchone()[0]
    assert n == 0, f"Hay {n} customer_id nulos"


def test_returns_by_product_severity_valid(con):
    """Las severidades deben ser válidas (incluye no_sales_but_returns)."""
    valid = {
        "no_returns", "no_sales_but_returns",
        "high_return_rate", "medium_return_rate", "low_return_rate",
    }
    rows = con.execute("SELECT DISTINCT return_severity FROM v_returns_by_product").fetchall()
    actual = {r[0] for r in rows}
    assert actual <= valid, f"Severidades inválidas: {actual - valid}"


def test_no_sales_but_returns_has_null_rate(con):
    """Los no_sales_but_returns deben tener return_rate NULL."""
    n_bad = con.execute("""
        SELECT COUNT(*) FROM v_returns_by_product
        WHERE return_severity = 'no_sales_but_returns'
          AND return_rate_recent_pct IS NOT NULL
    """).fetchone()[0]
    assert n_bad == 0, f"Hay {n_bad} no_sales_but_returns con return_rate no nulo"


def test_returns_by_product_rates_in_range(con):
    """Las tasas de devolución deben estar entre 0 y 100 (si no son NULL)."""
    row = con.execute("""
        SELECT MIN(return_rate_recent_pct), MAX(return_rate_recent_pct)
        FROM v_returns_by_product
        WHERE return_rate_recent_pct IS NOT NULL
    """).fetchone()
    assert row[0] >= 0, f"Tasa mínima negativa: {row[0]}"
    assert row[1] <= 100, f"Tasa máxima > 100: {row[1]}"


def test_week_start_is_monday(con):
    """Todas las semanas deben empezar en lunes (dow = 1 en ISO, o 0 en DuckDB)."""
    n_bad = con.execute("""
        SELECT COUNT(*) FROM (
            SELECT DISTINCT week_start FROM v_weekly_sales
            WHERE EXTRACT(DOW FROM week_start) != 1
        )
    """).fetchone()[0]
    assert n_bad == 0, f"{n_bad} semanas no empiezan en lunes"


def test_weekly_totals_match_sales_lines(con):
    """La suma de units_sold en v_weekly_sales debe coincidir con v_sales_lines."""
    weekly = con.execute("SELECT SUM(units_sold) FROM v_weekly_sales").fetchone()[0]
    lines = con.execute("""
        SELECT SUM(units_sold_line) FROM v_sales_lines
        WHERE is_product AND NOT is_partial_month
    """).fetchone()[0]
    assert abs(weekly - lines) < 1


def test_forecastable_count_around_1000(con):
    """Debe haber ~1.085 productos forecastable (según EDA)."""
    n = con.execute("""
        SELECT COUNT(*) FROM v_forecastable_products
        WHERE forecastability = 'forecastable'
    """).fetchone()[0]
    assert 1000 <= n <= 1200, f"Se esperaban ~1085 forecastable, hay {n}"


def test_all_products_classified(con):
    """Todos los productos de v_weekly_sales deben aparecer en v_forecastable_products."""
    n_weekly = con.execute("SELECT COUNT(DISTINCT stock_code) FROM v_weekly_sales").fetchone()[0]
    n_class = con.execute("SELECT COUNT(*) FROM v_forecastable_products").fetchone()[0]
    assert n_weekly == n_class


def test_no_partial_month_data(con):
    """No debe haber semanas que empiecen después del 2011-12-01."""
    max_week = con.execute("SELECT MAX(week_start) FROM v_weekly_sales").fetchone()[0]
    from datetime import date
    assert max_week < date(2011, 12, 1), f"Semanas posteriores a dic-2011: {max_week}"