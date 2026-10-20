"""
Constantes compartidas por todo el proyecto.

Una sola fuente de verdad para:
    - Códigos de StockCode que no son productos.
    - Umbrales de calidad.
    - Nombres de tablas.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Códigos de StockCode que NO son productos reales
# ---------------------------------------------------------------------------
# Basado en el informe de calidad (docs/quality_report.md).
# Estos códigos representan portes, ajustes, cargos o pruebas.
NON_PRODUCT_CODES: frozenset[str] = frozenset({
    "POST", "DOT", "M", "C2", "D", "S",
    "BANK CHARGES", "AMAZONFEE", "B", "CRUK",
    "PADS", "SP1002",
    "TEST001", "TEST002",
    "gift_0001_10", "gift_0001_20", "gift_0001_30",
    "gift_0001_40", "gift_0001_50",
})

# ---------------------------------------------------------------------------
# Nombres de tablas
# ---------------------------------------------------------------------------
RAW_TABLE = "raw_transactions"
CLEAN_TABLE = "clean_transactions"
FACT_TABLE = "fact_sales_line"
DIM_PRODUCT = "dim_product"
DIM_CUSTOMER = "dim_customer"
DIM_DATE = "dim_date"

# ---------------------------------------------------------------------------
# Fechas límite
# ---------------------------------------------------------------------------
# Diciembre 2011 está incompleto (el dataset termina el 9-dic-2011).
PARTIAL_MONTH_START = "2011-12-01"