"""Verifica que todas las métricas son coherentes entre sí."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb

from src.analytics.metrics import (
    get_customer_segments,
    get_product_concentration,
    get_revenue_by_country,
    get_revenue_trend,
    get_top_products,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = ROOT_DIR / "data" / "processed" / "revenue.duckdb"

START = date(2010, 1, 1)
END = date(2011, 11, 30)  # Excluye dic-2011 (parcial)


def main() -> None:
    print("=== Trend mensual ===")
    trend = get_revenue_trend(START, END, group_by="month")
    print(trend.head())
    print(f"Total net_revenue: £{trend['net_revenue'].sum():,.2f}")

    print("\n=== Top 5 productos ===")
    print(get_top_products(START, END, limit=5))

    print("\n=== Top 5 países ===")
    print(get_revenue_by_country(START, END).head())

    print("\n=== Segmentos RFM ===")
    print(get_customer_segments())

    print("\n=== Concentración (top 10) ===")
    print(get_product_concentration(top_n=10))

    print("\n=== Verificación de coherencia ===")
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        v = con.execute("SELECT SUM(net_revenue_line) FROM v_sales_lines").fetchone()[0]
        f = con.execute("SELECT SUM(line_value) FROM fact_sales_line").fetchone()[0]
        print(f"net_revenue en vista: £{v:,.2f}")
        print(f"line_value en fact : £{f:,.2f}")
        print(f"Diferencia          : £{abs(v - f):.10f}")
    finally:
        con.close()


if __name__ == "__main__":
    main()