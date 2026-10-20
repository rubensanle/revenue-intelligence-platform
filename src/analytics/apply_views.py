"""
Módulo B — Aplica las vistas SQL de la capa semántica.

Ejecuta los ficheros sql/views/*.sql en orden alfabético.
Es idempotente: usa CREATE OR REPLACE VIEW.
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

ROOT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = ROOT_DIR / "data" / "processed" / "revenue.duckdb"
VIEWS_DIR = ROOT_DIR / "sql" / "views"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def apply_views() -> None:
    sql_files = sorted(VIEWS_DIR.glob("*.sql"))
    if not sql_files:
        raise FileNotFoundError(f"No hay ficheros .sql en {VIEWS_DIR}")

    con = duckdb.connect(str(DB_PATH))
    try:
        for sql_file in sql_files:
            logger.info("Aplicando %s", sql_file.name)
            con.execute(sql_file.read_text(encoding="utf-8"))
        logger.info("=== %s vistas aplicadas ===", len(sql_files))

        # Resumen
        views = con.execute("""
            SELECT table_name FROM information_schema.views
            WHERE table_schema = 'main'
            ORDER BY table_name
        """).fetchall()
        for (name,) in views:
            n = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            logger.info("  %-30s %s filas", name, f"{n:,}")
    finally:
        con.close()


if __name__ == "__main__":
    apply_views()