"""Tests del Módulo A.3 — Limpieza."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from src.utils.constants import CLEAN_TABLE, RAW_TABLE

ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "data" / "processed" / "revenue.duckdb"


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect(str(DB_PATH), read_only=True)
    yield c
    c.close()


def test_row_count_after_dedup(con):
    """Tras deduplicar, el número de filas debe ser el esperado."""
    n_raw = con.execute(f"SELECT COUNT(*) FROM {RAW_TABLE}").fetchone()[0]
    n_clean = con.execute(f"SELECT COUNT(*) FROM {CLEAN_TABLE}").fetchone()[0]
    # 1.067.371 - 34.335 = 1.033.036 (según el análisis de duplicados)
    assert n_raw - n_clean == 34_335, f"Se esperaban 34.335 filas eliminadas, se eliminaron {n_raw - n_clean}"


def test_no_exact_duplicates_remain(con):
    """No deben quedar duplicados exactos."""
    n_dups = con.execute(f"""
        SELECT COUNT(*) FROM (
            SELECT *, COUNT(*) AS n
            FROM {CLEAN_TABLE}
            GROUP BY ALL
            HAVING COUNT(*) > 1
        )
    """).fetchone()[0]
    assert n_dups == 0, f"Quedan {n_dups} grupos con duplicados exactos"


def test_legitimate_repeated_lines_preserved(con):
    """Las líneas legítimas repetidas (distinta cantidad/precio) se mantienen."""
    # C544580 / S tenía 16 filas con 15 precios distintos en raw.
    # Debe seguir ahí tras la limpieza.
    n = con.execute(f"""
        SELECT COUNT(*) FROM {CLEAN_TABLE}
        WHERE invoice_no = 'C544580' AND stock_code = 'S'
    """).fetchone()[0]
    assert n > 1, "Se han perdido líneas legítimas repetidas en C544580/S"


def test_customer_id_is_integer(con):
    """Customer ID debe ser entero, no float."""
    dtype = con.execute(f"""
        SELECT typeof(customer_id) FROM {CLEAN_TABLE} LIMIT 1
    """).fetchone()[0]
    assert "BIGINT" in dtype.upper(), f"customer_id es {dtype}, se esperaba BIGINT"


def test_flags_are_consistent(con):
    """Las flags deben ser coherentes con las reglas."""
    # Cancelaciones: todas deben tener invoice_no que empiece por 'C'
    n_bad = con.execute(f"""
        SELECT COUNT(*) FROM {CLEAN_TABLE}
        WHERE is_cancellation AND invoice_no NOT LIKE 'C%'
    """).fetchone()[0]
    assert n_bad == 0

    # Devoluciones: todas deben tener quantity < 0 y no ser cancelación
    n_bad = con.execute(f"""
        SELECT COUNT(*) FROM {CLEAN_TABLE}
        WHERE is_return AND (quantity >= 0 OR is_cancellation)
    """).fetchone()[0]
    assert n_bad == 0


def test_non_product_codes_excluded_from_products(con):
    """Los códigos no-producto no deben marcarse como producto."""
    n_bad = con.execute(f"""
        SELECT COUNT(*) FROM {CLEAN_TABLE}
        WHERE stock_code IN ('POST', 'DOT', 'M', 'BANK CHARGES', 'AMAZONFEE')
          AND is_product = TRUE
    """).fetchone()[0]
    assert n_bad == 0