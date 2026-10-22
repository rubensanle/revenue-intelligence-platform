"""
Módulo B — Funciones analíticas tipadas.

El copiloto NO escribe SQL arbitrario. Llama a estas funciones.
Cada función:
    - Valida sus parámetros con Pydantic.
    - Ejecuta la vista SQL correspondiente.
    - Devuelve un DataFrame con esquema conocido.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import duckdb
import pandas as pd
from pydantic import BaseModel, Field, field_validator

ROOT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = ROOT_DIR / "data" / "processed" / "revenue.duckdb"


def _con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DB_PATH), read_only=True)


# ---------------------------------------------------------------------------
# Modelos de parámetros
# ---------------------------------------------------------------------------

class PeriodParams(BaseModel):
    start_date: date
    end_date: date

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: date, info) -> date:
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date debe ser >= start_date")
        return v


class TopProductsParams(PeriodParams):
    metric: Literal["net_revenue", "units_sold", "units_net"] = "net_revenue"
    limit: int = Field(default=10, ge=1, le=100)


class ForecastParams(BaseModel):
    stock_code: str
    horizon_weeks: int = Field(default=4, ge=1, le=13)


class ScenarioParams(BaseModel):
    demand_multiplier: float = Field(ge=0.5, le=2.0)
    unit_cost: float = Field(ge=0.0)
    holding_cost_per_unit: float = Field(ge=0.0)


# ---------------------------------------------------------------------------
# Funciones analíticas
# ---------------------------------------------------------------------------

def get_revenue_trend(
    start_date: date, end_date: date, group_by: Literal["day", "week", "month"] = "month",
) -> pd.DataFrame:
    """Evolución de ingresos entre dos fechas, agrupado por día, semana o mes."""
    p = PeriodParams(start_date=start_date, end_date=end_date)
    trunc = {"day": "day", "week": "week", "month": "month"}[group_by]

    con = _con()
    try:
        df = con.execute(f"""
            SELECT
                DATE_TRUNC('{trunc}', invoice_date)::DATE AS period,
                ROUND(SUM(net_revenue_line), 2)           AS net_revenue,
                ROUND(SUM(gross_revenue_line), 2)         AS gross_revenue,
                SUM(units_sold_line)                      AS units_sold,
                SUM(returns_line)                         AS returns
            FROM v_sales_lines
            WHERE invoice_date BETWEEN ? AND ?
            GROUP BY 1
            ORDER BY 1
        """, [p.start_date, p.end_date]).df()
        return df
    finally:
        con.close()


def get_top_products(
    start_date: date, end_date: date,
    metric: Literal["net_revenue", "units_sold", "units_net"] = "net_revenue",
    limit: int = 10,
) -> pd.DataFrame:
    """Top productos por la métrica elegida en el período."""
    p = TopProductsParams(
        start_date=start_date, end_date=end_date, metric=metric, limit=limit,
    )
    # Solo permitimos columnas de la lista blanca
    safe_col = {
        "net_revenue": "net_revenue",
        "units_sold": "units_sold",
        "units_net": "units_net",
    }[p.metric]

    con = _con()
    try:
        df = con.execute(f"""
            SELECT
                stock_code,
                MODE(description) AS description,
                ROUND(SUM(net_revenue_line), 2) AS net_revenue,
                SUM(units_sold_line)            AS units_sold,
                SUM(units_net_line)             AS units_net,
                COUNT(DISTINCT invoice_no)      AS n_invoices
            FROM v_sales_lines
            WHERE is_product
              AND invoice_date BETWEEN ? AND ?
            GROUP BY stock_code
            ORDER BY {safe_col} DESC NULLS LAST
            LIMIT ?
        """, [p.start_date, p.end_date, p.limit]).df()
        return df
    finally:
        con.close()


def get_revenue_by_country(start_date: date, end_date: date) -> pd.DataFrame:
    """Ingresos por país en el período."""
    p = PeriodParams(start_date=start_date, end_date=end_date)
    con = _con()
    try:
        return con.execute("""
            SELECT
                country,
                ROUND(SUM(net_revenue_line), 2) AS net_revenue,
                SUM(units_sold_line)            AS units_sold,
                COUNT(DISTINCT customer_id) FILTER (WHERE customer_id IS NOT NULL) AS n_customers
            FROM v_sales_lines
            WHERE invoice_date BETWEEN ? AND ?
            GROUP BY country
            ORDER BY net_revenue DESC
        """, [p.start_date, p.end_date]).df()
    finally:
        con.close()


def get_customer_segments() -> pd.DataFrame:
    """Distribución de clientes por segmento RFM."""
    con = _con()
    try:
        return con.execute("""
            SELECT
                rfm_segment,
                COUNT(*)                          AS n_customers,
                ROUND(AVG(recency_days), 1)       AS avg_recency_days,
                ROUND(AVG(frequency), 1)          AS avg_frequency,
                ROUND(AVG(monetary), 2)           AS avg_monetary,
                ROUND(SUM(monetary), 2)           AS total_revenue
            FROM v_rfm_segments
            GROUP BY rfm_segment
            ORDER BY total_revenue DESC
        """).df()
    finally:
        con.close()


def get_product_concentration(top_n: int = 20) -> pd.DataFrame:
    """Top N productos por contribución acumulada al ingreso."""
    con = _con()
    try:
        return con.execute("""
            SELECT stock_code, net_revenue, rank, cumulative_revenue, cumulative_pct
            FROM v_product_concentration
            WHERE rank <= ?
            ORDER BY rank
        """, [top_n]).df()
    finally:
        con.close()


def get_top_customers_by_revenue(start_date: date, end_date: date, limit: int = 10) -> pd.DataFrame:
    """Top clientes por ingresos netos en el período."""
    p = PeriodParams(start_date=start_date, end_date=end_date)
    con = _con()
    try:
        return con.execute("""
            SELECT
                customer_id,
                MODE(country) AS country,
                ROUND(SUM(net_revenue_line), 2) AS net_revenue,
                SUM(units_sold_line)            AS units_sold,
                COUNT(DISTINCT invoice_no)      AS n_invoices
            FROM v_sales_lines
            WHERE customer_id IS NOT NULL
              AND invoice_date BETWEEN ? AND ?
            GROUP BY customer_id
            ORDER BY net_revenue DESC
            LIMIT ?
        """, [p.start_date, p.end_date, limit]).df()
    finally:
        con.close()

# metrics.py
def get_returns_by_product(limit: int = 10) -> pd.DataFrame:
    """Top productos con más devoluciones."""
    con = _con()
    try:
        return con.execute("""
            SELECT stock_code, description, units_returned_recent,
                   return_rate_recent_pct, return_severity
            FROM v_returns_by_product
            WHERE return_severity = 'high_return_rate'
            ORDER BY units_returned_recent DESC
            LIMIT ?
        """, [limit]).df()
    finally:
        con.close()


def get_returns_by_customer(limit: int = 10) -> pd.DataFrame:
    """Top clientes que más devuelven."""
    con = _con()
    try:
        return con.execute("""
            SELECT customer_id, country, units_returned_recent,
                   revenue_returned_recent, return_rate_units_pct
            FROM v_returns_by_customer
            ORDER BY units_returned_recent DESC
            LIMIT ?
        """, [limit]).df()
    finally:
        con.close()