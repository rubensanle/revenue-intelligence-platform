"""
Módulo A.3 — Construcción del modelo relacional.

Crea las tablas analíticas:
    - fact_sales_line  (hechos, una fila por línea de factura)
    - dim_product      (solo productos reales)
    - dim_customer     (solo clientes identificados)
    - dim_date         (calendario completo)

Principio: una sola fuente de verdad. fact_sales_line conserva TODO
(incluidas cancelaciones, devoluciones y no-productos) para que el
ingreso total cuadre. Las dimensiones filtran lo que no es analizable.
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

from src.utils.constants import (
    CLEAN_TABLE,
    DIM_CUSTOMER,
    DIM_DATE,
    DIM_PRODUCT,
    FACT_TABLE,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = ROOT_DIR / "data" / "processed" / "revenue.duckdb"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def build_fact(con: duckdb.DuckDBPyConnection) -> None:
    """Tabla de hechos: una fila por línea de factura, con todas las flags."""
    logger.info("Construyendo '%s'...", FACT_TABLE)
    con.execute(f"DROP TABLE IF EXISTS {FACT_TABLE}")
    con.execute(f"""
        CREATE TABLE {FACT_TABLE} AS
        SELECT
            ROW_NUMBER() OVER () AS sales_line_id,
            invoice_no,
            stock_code,
            description,
            quantity,
            invoice_ts,
            invoice_date,
            year, month, week, day_of_week, hour,
            unit_price,
            customer_id,
            country,
            is_cancellation,
            is_return,
            is_product,
            has_valid_price,
            line_value,
            gross_value,
            is_partial_month
        FROM {CLEAN_TABLE}
    """)
    n = con.execute(f"SELECT COUNT(*) FROM {FACT_TABLE}").fetchone()[0]
    logger.info("  %s filas.", f"{n:,}")


def build_dim_product(con: duckdb.DuckDBPyConnection) -> None:
    """Dimensión de producto: solo productos reales (is_product = TRUE)."""
    logger.info("Construyendo '%s'...", DIM_PRODUCT)
    con.execute(f"DROP TABLE IF EXISTS {DIM_PRODUCT}")
    con.execute(f"""
        CREATE TABLE {DIM_PRODUCT} AS
        SELECT
            stock_code,
            -- Descripción más frecuente para cada código
            MODE(description) AS description,
            MIN(invoice_date) AS first_seen,
            MAX(invoice_date) AS last_seen
        FROM {FACT_TABLE}
        WHERE is_product
        GROUP BY stock_code
    """)
    n = con.execute(f"SELECT COUNT(*) FROM {DIM_PRODUCT}").fetchone()[0]
    logger.info("  %s productos únicos.", f"{n:,}")


def build_dim_customer(con: duckdb.DuckDBPyConnection) -> None:
    """Dimensión de cliente: solo clientes identificados."""
    logger.info("Construyendo '%s'...", DIM_CUSTOMER)
    con.execute(f"DROP TABLE IF EXISTS {DIM_CUSTOMER}")
    con.execute(f"""
        CREATE TABLE {DIM_CUSTOMER} AS
        SELECT
            customer_id,
            MODE(country) AS country,
            MIN(invoice_date) AS first_purchase,
            MAX(invoice_date) AS last_purchase,
            COUNT(DISTINCT invoice_no) AS n_invoices
        FROM {FACT_TABLE}
        WHERE customer_id IS NOT NULL
        GROUP BY customer_id
    """)
    n = con.execute(f"SELECT COUNT(*) FROM {DIM_CUSTOMER}").fetchone()[0]
    logger.info("  %s clientes identificados.", f"{n:,}")


def build_dim_date(con: duckdb.DuckDBPyConnection) -> None:
    """Calendario completo desde el primer al último día del dataset."""
    logger.info("Construyendo '%s'...", DIM_DATE)
    con.execute(f"DROP TABLE IF EXISTS {DIM_DATE}")
    con.execute(f"""
        CREATE TABLE {DIM_DATE} AS
        WITH bounds AS (
            SELECT MIN(invoice_date) AS d_min, MAX(invoice_date) AS d_max
            FROM {FACT_TABLE}
        ),
        series AS (
            SELECT UNNEST(
                GENERATE_SERIES(
                    (SELECT d_min FROM bounds),
                    (SELECT d_max FROM bounds),
                    INTERVAL 1 DAY
                )
            )::DATE AS date
        )
        SELECT
            date,
            EXTRACT(YEAR FROM date) AS year,
            EXTRACT(MONTH FROM date) AS month,
            EXTRACT(WEEK FROM date) AS week,
            EXTRACT(DOW FROM date) AS day_of_week,
            EXTRACT(DOY FROM date) AS day_of_year,
            (EXTRACT(DOW FROM date) IN (0, 6)) AS is_weekend,
            (date >= DATE '2011-12-01') AS is_partial_month
        FROM series
    """)
    n = con.execute(f"SELECT COUNT(*) FROM {DIM_DATE}").fetchone()[0]
    logger.info("  %s días en el calendario.", f"{n:,}")


def main() -> None:
    logger.info("=== Construyendo modelo relacional ===")
    con = duckdb.connect(str(DB_PATH))
    try:
        build_fact(con)
        build_dim_product(con)
        build_dim_customer(con)
        build_dim_date(con)
    finally:
        con.close()
    logger.info("=== Modelo relacional completado ===")


if __name__ == "__main__":
    main()