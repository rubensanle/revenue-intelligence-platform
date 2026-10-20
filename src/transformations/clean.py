"""
Módulo A.3 — Limpieza del dataset original.

Responsabilidad:
    - Aplicar las 11 reglas de limpieza documentadas en docs/quality_report.md.
    - Producir la tabla 'clean_transactions' en DuckDB.
    - Registrar cuántas filas afecta cada regla.

Principio:
    - Ninguna fila se elimina sin justificación documentada.
    - Solo se deduplican duplicados EXACTOS.
    - Las devoluciones, cancelaciones y ajustes se mantienen con flags.
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

from src.utils.constants import (
    CLEAN_TABLE,
    NON_PRODUCT_CODES,
    PARTIAL_MONTH_START,
    RAW_TABLE,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = ROOT_DIR / "data" / "processed" / "revenue.duckdb"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def build_clean_table(con: duckdb.DuckDBPyConnection) -> None:
    """Construye clean_transactions aplicando las reglas R1–R11."""
    logger.info("Construyendo tabla '%s'...", CLEAN_TABLE)

    # Lista de códigos no-producto para usar en SQL
    codes_sql = ", ".join(f"'{c}'" for c in sorted(NON_PRODUCT_CODES))

    con.execute(f"DROP TABLE IF EXISTS {CLEAN_TABLE}")

    con.execute(f"""
        CREATE TABLE {CLEAN_TABLE} AS
        WITH deduped AS (
            -- R10: Deduplicación EXACTA (todas las columnas iguales).
            -- Nos quedamos con una fila por grupo de filas idénticas.
            SELECT DISTINCT *
            FROM {RAW_TABLE}
        ),
        typed AS (
            SELECT
                -- R1: Customer ID a BIGINT nullable.
                TRY_CAST("Customer ID" AS BIGINT) AS customer_id_raw,

                -- R2: InvoiceDate a TIMESTAMP (sin nanosegundos).
                CAST(InvoiceDate AS TIMESTAMP) AS invoice_ts,

                -- Renombrado de columnas a snake_case.
                Invoice AS invoice_no,
                StockCode AS stock_code,
                COALESCE(Description, 'UNKNOWN') AS description,  -- R3
                Quantity AS quantity,
                Price AS unit_price,
                Country AS country
            FROM deduped
        )
        SELECT
            invoice_no,
            stock_code,
            description,
            quantity,
            invoice_ts,

            -- Columnas derivadas de fecha (R2)
            CAST(invoice_ts AS DATE) AS invoice_date,
            EXTRACT(YEAR FROM invoice_ts) AS year,
            EXTRACT(MONTH FROM invoice_ts) AS month,
            EXTRACT(WEEK FROM invoice_ts) AS week,
            EXTRACT(DOW FROM invoice_ts) AS day_of_week,
            EXTRACT(HOUR FROM invoice_ts) AS hour,

            unit_price,
            customer_id_raw AS customer_id,
            country,

            -- R4: Flag de cancelación (Invoice empieza por 'C').
            (invoice_no LIKE 'C%') AS is_cancellation,

            -- R5: Flag de devolución (Quantity < 0 y NO es cancelación).
            (quantity < 0 AND invoice_no NOT LIKE 'C%') AS is_return,

            -- R6: Flag de producto real (excluye códigos no-producto).
            (stock_code NOT IN ({codes_sql})) AS is_product,

            -- R7: Flag de precio válido (precio > 0).
            (unit_price > 0) AS has_valid_price,

            -- R8: Ingreso neto con signo (Quantity × Price).
            CAST(quantity * unit_price AS DOUBLE) AS line_value,

            -- R9: Ingreso bruto (solo líneas positivas).
            CAST(
                CASE WHEN quantity > 0 AND unit_price > 0
                     THEN quantity * unit_price
                     ELSE 0 END
                AS DOUBLE
            ) AS gross_value,

            -- R11: Flag de mes parcial (diciembre 2011).
            (invoice_date >= DATE '{PARTIAL_MONTH_START}') AS is_partial_month

        FROM typed
    """)

    n = con.execute(f"SELECT COUNT(*) FROM {CLEAN_TABLE}").fetchone()[0]
    logger.info("Tabla '%s' creada con %s filas.", CLEAN_TABLE, f"{n:,}")


def log_rule_impact(con: duckdb.DuckDBPyConnection) -> None:
    """Registra en logs cuántas filas afecta cada regla."""
    logger.info("=== Impacto de cada regla ===")

    rows = con.execute(f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN is_cancellation THEN 1 ELSE 0 END) AS r4_cancellations,
            SUM(CASE WHEN is_return THEN 1 ELSE 0 END) AS r5_returns,
            SUM(CASE WHEN NOT is_product THEN 1 ELSE 0 END) AS r6_non_products,
            SUM(CASE WHEN NOT has_valid_price THEN 1 ELSE 0 END) AS r7_invalid_price,
            SUM(CASE WHEN is_partial_month THEN 1 ELSE 0 END) AS r11_partial_month
        FROM {CLEAN_TABLE}
    """).fetchone()

    labels = [
        ("Total filas tras limpieza", rows[0]),
        ("R4 · Cancelaciones", rows[1]),
        ("R5 · Devoluciones (no cancelación)", rows[2]),
        ("R6 · Líneas no-producto", rows[3]),
        ("R7 · Líneas con precio inválido (≤ 0)", rows[4]),
        ("R11 · Líneas de mes parcial (dic-2011)", rows[5]),
    ]
    for label, value in labels:
        logger.info("  %-45s %s", label, f"{int(value):,}")


def main() -> None:
    logger.info("=== Iniciando limpieza ===")
    con = duckdb.connect(str(DB_PATH))
    try:
        build_clean_table(con)
        log_rule_impact(con)
    finally:
        con.close()
    logger.info("=== Limpieza completada ===")


if __name__ == "__main__":
    main()