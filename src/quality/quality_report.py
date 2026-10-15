"""
Responsabilidad:
    - Medir nulos, duplicados, rangos, outliers y valores raros.
    - Identificar cancelaciones, devoluciones y códigos no-producto.
    - Generar un informe en Markdown (docs/quality_report.md).

Principio: NO se modifica nada. Solo se mide y se documenta.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = ROOT_DIR / "data" / "processed" / "revenue.duckdb"
REPORT_PATH = ROOT_DIR / "docs" / "quality_report.md"
RAW_TABLE = "raw_transactions"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Códigos de StockCode que NO son productos reales
NON_PRODUCT_CODES = {
    "POST", "D", "M", "C2", "DOT", "BANK CHARGES",
    "PADS", "CRUK", "S", "AMAZONFEE", "gift_0001_20",
    "gift_0001_40", "gift_0001_50", "gift_0001_30",
    "gift_0001_10", "B", "TEST001", "TEST002", "SP1002",
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def connect() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DB_PATH), read_only=True)


def section(title: str, level: int = 2) -> str:
    """Genera un encabezado Markdown."""
    return f"\n{'#' * level} {title}\n"


def df_to_md(df: pd.DataFrame) -> str:
    """Convierte un DataFrame a tabla Markdown sin dependencias extra."""
    if df.empty:
        return "_Sin resultados._\n"
    return df.to_markdown(index=False) + "\n"


# ---------------------------------------------------------------------------
# Secciones del informe
# ---------------------------------------------------------------------------

def overview(con: duckdb.DuckDBPyConnection) -> str:
    """Panorama general: filas, columnas, rango temporal, memoria."""
    n_rows = con.execute(f"SELECT COUNT(*) FROM {RAW_TABLE}").fetchone()[0]
    n_cols = len(con.execute(f"DESCRIBE {RAW_TABLE}").fetchall())

    date_range = con.execute(
        f"SELECT MIN(InvoiceDate), MAX(InvoiceDate) FROM {RAW_TABLE}"
    ).fetchone()

    schema = con.execute(f"DESCRIBE {RAW_TABLE}").df()

    out = section("1. Panorama general")
    out += f"- **Filas:** {n_rows:,}\n"
    out += f"- **Columnas:** {n_cols}\n"
    out += f"- **Rango temporal:** {date_range[0]} → {date_range[1]}\n"
    out += f"- **Fecha del informe:** {datetime.now():%Y-%m-%d %H:%M}\n"
    out += "\n**Esquema:**\n\n"
    out += df_to_md(schema[["column_name", "column_type"]])
    return out


def nulls_report(con: duckdb.DuckDBPyConnection) -> str:
    """Nulos por columna, con porcentaje."""
    cols = [r[0] for r in con.execute(f"DESCRIBE {RAW_TABLE}").fetchall()]
    parts = []
    for c in cols:
        parts.append(  
            f"SUM(CASE WHEN \"{c}\" IS NULL THEN 1 ELSE 0 END) AS \"{c}\""
        )
    query = f"SELECT COUNT(*) AS total, {', '.join(parts)} FROM {RAW_TABLE}"
    df = con.execute(query).df()

    total = int(df["total"].iloc[0])
    rows = []
    for c in cols:
        n = int(df[c].iloc[0])
        rows.append({
            "columna": c,
            "nulos": n,
            "porcentaje": f"{100 * n / total:.2f}%",
        })
    result = pd.DataFrame(rows)

    out = section("2. Valores nulos")
    out += f"Total de filas: **{total:,}**\n\n"
    out += df_to_md(result)
    return out


def duplicates_report(con: duckdb.DuckDBPyConnection) -> str:
    """Duplicados exactos y por clave de negocio."""
    # DuckDB no soporta COUNT(DISTINCT *) en todas las versiones;
    # hacemos un enfoque alternativo con GROUP BY.
    exact_dups = con.execute(f"""
        SELECT COUNT(*) FROM (
            SELECT *, COUNT(*) AS n
            FROM {RAW_TABLE}
            GROUP BY ALL
            HAVING COUNT(*) > 1
        )
    """).fetchone()[0]

    # Duplicados por clave de negocio: misma factura + producto + cantidad + precio
    key_dups = con.execute(f"""
        SELECT COUNT(*) FROM (
            SELECT Invoice, StockCode, Quantity, Price, COUNT(*) AS n
            FROM {RAW_TABLE}
            GROUP BY Invoice, StockCode, Quantity, Price
            HAVING COUNT(*) > 1
        )
    """).fetchone()[0]

    out = section("3. Duplicados")
    out += f"- **Duplicados exactos (filas completas):** {exact_dups:,}\n"
    out += f"- **Grupos duplicados por (Invoice, StockCode, Quantity, Price):** {key_dups:,}\n"
    out += "\n_Nota: los duplicados por clave de negocio pueden ser legítimos "
    out += "(misma línea repetida en la misma factura) o errores de registro._\n"
    return out


def quantity_price_report(con: duckdb.DuckDBPyConnection) -> str:
    """Distribución de Quantity y Price, incluyendo negativos y ceros."""
    stats = con.execute(f"""
        SELECT
            MIN(Quantity) AS q_min,
            MAX(Quantity) AS q_max,
            AVG(Quantity) AS q_mean,
            MEDIAN(Quantity) AS q_median,
            SUM(CASE WHEN Quantity < 0 THEN 1 ELSE 0 END) AS q_neg,
            SUM(CASE WHEN Quantity = 0 THEN 1 ELSE 0 END) AS q_zero,
            MIN(Price) AS p_min,
            MAX(Price) AS p_max,
            AVG(Price) AS p_mean,
            MEDIAN(Price) AS p_median,
            SUM(CASE WHEN Price < 0 THEN 1 ELSE 0 END) AS p_neg,
            SUM(CASE WHEN Price = 0 THEN 1 ELSE 0 END) AS p_zero
        FROM {RAW_TABLE}
    """).df().iloc[0]

    total = con.execute(f"SELECT COUNT(*) FROM {RAW_TABLE}").fetchone()[0]

    out = section("4. Quantity y Price")
    out += "**Quantity (unidades):**\n\n"
    q_df = pd.DataFrame([{
        "min": stats["q_min"],
        "max": stats["q_max"],
        "media": f"{stats['q_mean']:.2f}",
        "mediana": stats["q_median"],
        "negativas": f"{int(stats['q_neg']):,} ({100*stats['q_neg']/total:.2f}%)",
        "cero": f"{int(stats['q_zero']):,} ({100*stats['q_zero']/total:.2f}%)",
    }])
    out += df_to_md(q_df)

    out += "\n**Price (precio unitario en GBP):**\n\n"
    p_df = pd.DataFrame([{
        "min": stats["p_min"],
        "max": stats["p_max"],
        "media": f"{stats['p_mean']:.4f}",
        "mediana": stats["p_median"],
        "negativos": f"{int(stats['p_neg']):,} ({100*stats['p_neg']/total:.2f}%)",
        "cero": f"{int(stats['p_zero']):,} ({100*stats['p_zero']/total:.2f}%)",
    }])
    out += df_to_md(p_df)

    out += "\n_Interpretación: Quantity negativa suele indicar devolución. "
    out += "Price = 0 puede indicar muestras gratuitas, ajustes o errores._\n"
    return out


def cancellations_report(con: duckdb.DuckDBPyConnection) -> str:
    """Cancelaciones: facturas que empiezan por 'C'."""
    n_canc = con.execute(f"""
        SELECT COUNT(*) FROM {RAW_TABLE}
        WHERE Invoice LIKE 'C%'
    """).fetchone()[0]

    n_total = con.execute(f"SELECT COUNT(*) FROM {RAW_TABLE}").fetchone()[0]

    # ¿Las cancelaciones siempre tienen Quantity negativa?
    canc_q = con.execute(f"""
        SELECT
            SUM(CASE WHEN Quantity < 0 THEN 1 ELSE 0 END) AS neg,
            SUM(CASE WHEN Quantity > 0 THEN 1 ELSE 0 END) AS pos,
            SUM(CASE WHEN Quantity = 0 THEN 1 ELSE 0 END) AS zero
        FROM {RAW_TABLE}
        WHERE Invoice LIKE 'C%'
    """).df().iloc[0]

    out = section("5. Cancelaciones (Invoice comienza por 'C')")
    out += f"- **Total de líneas con Invoice 'C%':** {n_canc:,} "
    out += f"({100*n_canc/n_total:.2f}% del dataset)\n"
    out += f"- De esas: {int(canc_q['neg']):,} con Quantity < 0, "
    out += f"{int(canc_q['pos']):,} con Quantity > 0, "
    out += f"{int(canc_q['zero']):,} con Quantity = 0.\n"
    out += "\n_Nota: una cancelación debería tener Quantity negativa. "
    out += "Si hay positivas, son ajustes o casos atípicos que requieren revisión._\n"
    return out


def non_product_codes_report(con: duckdb.DuckDBPyConnection) -> str:
    """StockCodes que no son productos reales (POST, D, M, etc.)."""
    codes_list = "', '".join(NON_PRODUCT_CODES)
    df = con.execute(f"""
        SELECT StockCode, COUNT(*) AS n, SUM(Quantity * Price) AS revenue
        FROM {RAW_TABLE}
        WHERE StockCode IN ('{codes_list}')
        GROUP BY StockCode
        ORDER BY n DESC
    """).df()

    out = section("6. Códigos que no son productos reales")
    out += "Estos códigos representan cargos, ajustes, portes o pruebas. "
    out += "Deben excluirse de análisis de producto y forecasting.\n\n"
    out += df_to_md(df)
    return out


def missing_customer_report(con: duckdb.DuckDBPyConnection) -> str:
    """Clientes sin ID: cuántos son y cuánto facturan."""
    df = con.execute(f"""
        SELECT
            CASE WHEN "Customer ID" IS NULL THEN 'Sin ID' ELSE 'Con ID' END AS tipo,
            COUNT(*) AS lineas,
            ROUND(SUM(Quantity * Price), 2) AS revenue
        FROM {RAW_TABLE}
        GROUP BY 1
    """).df()

    total = df["lineas"].sum()
    df["porcentaje_lineas"] = (100 * df["lineas"] / total).round(2).astype(str) + "%"

    out = section("7. Clientes sin identificador")
    out += "Las ventas sin Customer ID no pueden atribuirse a un cliente. "
    out += "Se analizarán por separado cuando corresponda (RFM, cohortes).\n\n"
    out += df_to_md(df)
    return out


def date_range_report(con: duckdb.DuckDBPyConnection) -> str:
    """Rango temporal y meses cubiertos."""
    df = con.execute(f"""
        SELECT
            DATE_TRUNC('month', InvoiceDate) AS mes,
            COUNT(*) AS lineas
        FROM {RAW_TABLE}
        GROUP BY 1
        ORDER BY 1
    """).df()

    out = section("8. Cobertura temporal")
    out += f"- **Meses cubiertos:** {len(df)}\n"
    out += f"- **Primer mes:** {df['mes'].iloc[0]}\n"
    out += f"- **Último mes:** {df['mes'].iloc[-1]}\n\n"
    out += "_Nota: diciembre 2011 puede estar incompleto (el dataset termina el 9-dic-2011)._\n"
    return out


def outliers_report(con: duckdb.DuckDBPyConnection) -> str:
    """Outliers en Quantity y Price usando IQR."""
    df = con.execute(f"""
        WITH stats AS (
            SELECT
                QUANTILE_CONT(Quantity, 0.25) AS q1_q,
                QUANTILE_CONT(Quantity, 0.75) AS q3_q,
                QUANTILE_CONT(Price, 0.25) AS q1_p,
                QUANTILE_CONT(Price, 0.75) AS q3_p
            FROM {RAW_TABLE}
        )
        SELECT
            (SELECT q1_q FROM stats) AS q1_q,
            (SELECT q3_q FROM stats) AS q3_q,
            (SELECT q1_p FROM stats) AS q1_p,
            (SELECT q3_p FROM stats) AS q3_p
    """).df().iloc[0]

    iqr_q = df["q3_q"] - df["q1_q"]
    iqr_p = df["q3_p"] - df["q1_p"]
    low_q, high_q = df["q1_q"] - 1.5 * iqr_q, df["q3_q"] + 1.5 * iqr_q
    low_p, high_p = df["q1_p"] - 1.5 * iqr_p, df["q3_p"] + 1.5 * iqr_p

    n_out_q = con.execute(f"""
        SELECT COUNT(*) FROM {RAW_TABLE}
        WHERE Quantity < {low_q} OR Quantity > {high_q}
    """).fetchone()[0]
    n_out_p = con.execute(f"""
        SELECT COUNT(*) FROM {RAW_TABLE}
        WHERE Price < {low_p} OR Price > {high_p}
    """).fetchone()[0]

    total = con.execute(f"SELECT COUNT(*) FROM {RAW_TABLE}").fetchone()[0]

    out = section("9. Outliers (método IQR)")
    out += f"- **Quantity:** rango normal [{low_q:.0f}, {high_q:.0f}]. "
    out += f"Outliers: {n_out_q:,} ({100*n_out_q/total:.2f}%).\n"
    out += f"- **Price:** rango normal [{low_p:.2f}, {high_p:.2f}]. "
    out += f"Outliers: {n_out_p:,} ({100*n_out_p/total:.2f}%).\n"
    out += "\n_Nota: los outliers NO se eliminan automáticamente. "
    out += "Pueden ser ventas mayoristas legítimas o errores. Requieren inspección._\n"
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("=== Generando informe de calidad ===")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    con = connect()
    try:
        parts = [
            "# Informe de calidad — Online Retail II\n",
            "_Generado automáticamente por `src/quality/quality_report.py`._\n",
            overview(con),
            nulls_report(con),
            duplicates_report(con),
            quantity_price_report(con),
            cancellations_report(con),
            non_product_codes_report(con),
            missing_customer_report(con),
            date_range_report(con),
            outliers_report(con),
        ]
    finally:
        con.close()

    content = "\n".join(parts)
    REPORT_PATH.write_text(content, encoding="utf-8")
    logger.info(f"Informe escrito en: {REPORT_PATH}")
    logger.info(f"Tamaño: {len(content):,} caracteres")


if __name__ == "__main__":
    main()