"""
Módulo C — Funciones de diagnóstico de negocio.

Cada función responde a una de las 5 preguntas del EDA y devuelve
un DataFrame listo para graficar o para incluir en el informe.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = ROOT_DIR / "data" / "processed" / "revenue.duckdb"


def _con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DB_PATH), read_only=True)


# ---------------------------------------------------------------------------
# Pregunta 1: ¿Cómo evoluciona el negocio?
# ---------------------------------------------------------------------------

def q1_monthly_evolution(include_partial: bool = False) -> pd.DataFrame:
    """
    Evolución mensual del negocio.

    Devuelve: mes, ingresos netos, unidades vendidas, devoluciones,
              crecimiento MoM, crecimiento YoY.

    Si include_partial=False, excluye dic-2011 (incompleto).
    """
    con = _con()
    try:
        return con.execute(f"""
            SELECT
                month,
                net_revenue,
                units_sold,
                LAG(net_revenue) OVER (ORDER BY month) AS prev_month,
                mom_growth_pct,
                yoy_growth_pct,
                is_partial
            FROM (
                SELECT
                    DATE_TRUNC('month', invoice_date)::DATE AS month,
                    ROUND(SUM(net_revenue_line), 2) AS net_revenue,
                    SUM(units_sold_line) AS units_sold,
                    ROUND(
                        100.0 * (SUM(net_revenue_line) -
                            LAG(SUM(net_revenue_line)) OVER (ORDER BY DATE_TRUNC('month', invoice_date)))
                        / NULLIF(LAG(SUM(net_revenue_line)) OVER (ORDER BY DATE_TRUNC('month', invoice_date)), 0),
                        2
                    ) AS mom_growth_pct,
                    ROUND(
                        100.0 * (SUM(net_revenue_line) -
                            LAG(SUM(net_revenue_line), 12) OVER (ORDER BY DATE_TRUNC('month', invoice_date)))
                        / NULLIF(LAG(SUM(net_revenue_line), 12) OVER (ORDER BY DATE_TRUNC('month', invoice_date)), 0),
                        2
                    ) AS yoy_growth_pct,
                    MAX(is_partial_month) AS is_partial
                FROM v_sales_lines
                GROUP BY DATE_TRUNC('month', invoice_date)
            )
            {'WHERE NOT is_partial' if not include_partial else ''}
            ORDER BY month
        """).df()
    finally:
        con.close() 


def q1_seasonality_by_dow() -> pd.DataFrame:
    """Ingresos medios por día de la semana (0=domingo, 6=sábado)."""
    con = _con()
    try:
        return con.execute("""
            SELECT
                day_of_week,
                CASE day_of_week
                    WHEN 0 THEN 'Domingo' WHEN 1 THEN 'Lunes' WHEN 2 THEN 'Martes'
                    WHEN 3 THEN 'Miércoles' WHEN 4 THEN 'Jueves' WHEN 5 THEN 'Viernes'
                    WHEN 6 THEN 'Sábado'
                END AS day_name,
                ROUND(AVG(daily_revenue), 2) AS avg_revenue,
                COUNT(*) AS n_days
            FROM (
                SELECT invoice_date, day_of_week, SUM(net_revenue_line) AS daily_revenue
                FROM v_sales_lines
                WHERE NOT is_partial_month
                GROUP BY invoice_date, day_of_week
            )
            GROUP BY day_of_week
            ORDER BY day_of_week
        """).df()
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Pregunta 2: ¿Qué productos generan el valor?
# ---------------------------------------------------------------------------

def q2_concentration_curve() -> pd.DataFrame:
    """Curva de concentración: % acumulado de ingreso vs. % acumulado de productos."""
    con = _con()
    try:
        return con.execute("""
            WITH ranked AS (
                SELECT
                    stock_code,
                    net_revenue,
                    ROW_NUMBER() OVER (ORDER BY net_revenue DESC) AS rank,
                    SUM(net_revenue) OVER (ORDER BY net_revenue DESC) AS cum_revenue,
                    SUM(net_revenue) OVER () AS total_revenue,
                    COUNT(*) OVER () AS total_products
                FROM v_revenue_by_product
                WHERE net_revenue > 0
            )
            SELECT
                rank,
                ROUND(100.0 * rank / total_products, 4) AS pct_products,
                ROUND(100.0 * cum_revenue / total_revenue, 4) AS pct_revenue
            FROM ranked
            ORDER BY rank
        """).df()
    finally:
        con.close()


def q2_top_bottom_products(n: int = 20) -> dict[str, pd.DataFrame]:
    """Top N y bottom N productos por ingreso."""
    con = _con()
    try:
        top = con.execute("""
            SELECT stock_code, description, net_revenue, units_sold
            FROM v_revenue_by_product
            WHERE net_revenue > 0
            ORDER BY net_revenue DESC
            LIMIT ?
        """, [n]).df()

        bottom = con.execute("""
            SELECT stock_code, description, net_revenue, units_sold
            FROM v_revenue_by_product
            WHERE net_revenue > 0
            ORDER BY net_revenue ASC
            LIMIT ?
        """, [n]).df()

        return {"top": top, "bottom": bottom}
    finally:
        con.close()


def q2_product_trend() -> pd.DataFrame:
    """
    Clasifica productos por tendencia: últimos 6 meses vs 6 meses anteriores.

    Reglas:
        - anomaly_returns:  devoluciones > ventas en el período reciente.
        - new_launch:       primera venta después de 2011-02-01 (base no comparable).
        - dormant:          existía antes pero no vendió en el período anterior.
        - dead:             vendía antes, ahora no.
        - growing:          +50% en el período reciente (base comparable).
        - declining:        -50% en el período reciente (base comparable).
        - stable:           resto (base comparable).

    growth_pct solo se calcula si first_sale_date < 2011-02-01 y units_previous > 0.
    Para new_launch y dormant se usan métricas absolutas:
        - units_per_month_recent
        - n_invoices_recent
        - avg_units_per_invoice
    """
    con = _con()
    try:
        return con.execute("""
            WITH recent AS (
                SELECT
                    stock_code,
                    SUM(units_net_line)         AS units_recent,
                    COUNT(DISTINCT invoice_no)  AS n_invoices_recent
                FROM v_sales_lines
                WHERE is_product AND NOT is_partial_month
                  AND line_type IN ('sale', 'cancellation', 'return')
                  AND invoice_date >= DATE '2011-06-01'
                  AND invoice_date <  DATE '2011-12-01'
                GROUP BY stock_code
            ),
            previous AS (
                SELECT
                    stock_code,
                    SUM(units_net_line) AS units_previous
                FROM v_sales_lines
                WHERE is_product AND NOT is_partial_month
                  AND line_type IN ('sale', 'cancellation', 'return')
                  AND invoice_date >= DATE '2010-12-01'
                  AND invoice_date <  DATE '2011-06-01'
                GROUP BY stock_code
            ),
            first_sale AS (
                SELECT stock_code, MIN(invoice_date) AS first_sale_date
                FROM v_sales_lines
                WHERE is_product AND NOT is_partial_month
                  AND line_type IN ('sale', 'cancellation', 'return')
                GROUP BY stock_code
            )
            SELECT
                COALESCE(r.stock_code, p.stock_code) AS stock_code,
                COALESCE(r.units_recent, 0)          AS units_recent,
                COALESCE(p.units_previous, 0)        AS units_previous,
                COALESCE(r.units_recent, 0) - COALESCE(p.units_previous, 0) AS delta,

                -- growth_pct: solo si es comparable
                CASE
                    WHEN f.first_sale_date >= DATE '2011-02-01' THEN NULL
                    WHEN COALESCE(p.units_previous, 0) = 0        THEN NULL
                    ELSE ROUND(
                        100.0 * (COALESCE(r.units_recent, 0) - COALESCE(p.units_previous, 0))
                        / NULLIF(ABS(COALESCE(p.units_previous, 0)), 0),
                        1
                    )
                END AS growth_pct,

                -- Métricas absolutas (para todos, especialmente new_launch/dormant)
                ROUND(COALESCE(r.units_recent, 0) / 6.0, 1)                    AS units_per_month_recent,
                COALESCE(r.n_invoices_recent, 0)                               AS n_invoices_recent,
                ROUND(
                    COALESCE(r.units_recent, 0) / NULLIF(r.n_invoices_recent, 0),
                    1
                )                                                              AS avg_units_per_invoice,

                f.first_sale_date,

                CASE
                    WHEN COALESCE(r.units_recent, 0) < 0 THEN 'anomaly_returns'
                    WHEN f.first_sale_date >= DATE '2011-02-01' THEN 'new_launch'
                    WHEN COALESCE(p.units_previous, 0) = 0 THEN 'dormant'
                    WHEN COALESCE(r.units_recent, 0) = 0   THEN 'dead'
                    WHEN r.units_recent > p.units_previous * 1.5 THEN 'growing'
                    WHEN r.units_recent < p.units_previous * 0.5 THEN 'declining'
                    ELSE 'stable'
                END AS trend

            FROM recent r
            FULL OUTER JOIN previous p USING (stock_code)
            LEFT JOIN first_sale f ON COALESCE(r.stock_code, p.stock_code) = f.stock_code
            WHERE (ABS(COALESCE(r.units_recent, 0)) + ABS(COALESCE(p.units_previous, 0))) >= 100
            ORDER BY delta DESC
        """).df()
    finally:
        con.close()


def q2_inspect_product(stock_code: str) -> pd.DataFrame:
    """
    Inspecciona la serie temporal semanal de un producto concreto.
    """
    con = _con()
    try:
        return con.execute("""
            SELECT
                DATE_TRUNC('week', invoice_date)::DATE AS week,
                SUM(CASE WHEN line_type = 'sale'         THEN units_net_line ELSE 0 END) AS units_sold,
                SUM(CASE WHEN line_type = 'cancellation' THEN units_net_line ELSE 0 END) AS units_cancelled,
                SUM(CASE WHEN line_type = 'return'       THEN units_net_line ELSE 0 END) AS units_returned,
                SUM(units_net_line) AS units_net,
                ROUND(SUM(net_revenue_line), 2) AS revenue,
                COUNT(DISTINCT invoice_no) AS n_invoices
            FROM v_sales_lines
            WHERE stock_code = ? AND is_product
              AND line_type IN ('sale', 'cancellation', 'return')
            GROUP BY 1
            ORDER BY 1
        """, [stock_code]).df()
    finally:
        con.close()

# ---------------------------------------------------------------------------
# Pregunta 3: ¿Qué patrones presentan los clientes?
# ---------------------------------------------------------------------------

def q3_rfm_distribution() -> pd.DataFrame:
    """Distribución de clientes por segmento RFM con métricas clave."""
    con = _con()
    try:
        return con.execute("""
            SELECT
                rfm_segment,
                COUNT(*) AS n_customers,
                ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_customers,
                ROUND(AVG(recency_days), 0) AS avg_recency_days,
                ROUND(AVG(frequency), 1) AS avg_frequency,
                ROUND(AVG(monetary), 2) AS avg_monetary,
                ROUND(SUM(monetary), 2) AS total_revenue,
                ROUND(100.0 * SUM(monetary) / SUM(SUM(monetary)) OVER (), 2) AS pct_revenue
            FROM v_rfm_segments
            GROUP BY rfm_segment
            ORDER BY total_revenue DESC
        """).df()
    finally:
        con.close()


def q3_repeat_purchase_rate() -> dict:
    """Tasa de recurrencia: % de clientes con >1 factura."""
    con = _con()
    try:
        row = con.execute("""
            SELECT
                COUNT(*) AS total_customers,
                SUM(CASE WHEN frequency > 1 THEN 1 ELSE 0 END) AS repeat_customers,
                ROUND(100.0 * SUM(CASE WHEN frequency > 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS repeat_rate_pct,
                ROUND(AVG(frequency), 2) AS avg_frequency
            FROM v_rfm_segments
        """).fetchone()
        return {
            "total_customers": int(row[0]),
            "repeat_customers": int(row[1]),
            "repeat_rate_pct": float(row[2]),
            "avg_frequency": float(row[3]),
        }
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Pregunta 4: ¿Qué mercados son más importantes?
# ---------------------------------------------------------------------------

def q4_country_ranking(include_uk: bool = True) -> pd.DataFrame:
    """Ranking de países por ingreso."""
    where_uk = "" if include_uk else "WHERE country <> 'United Kingdom'"
    con = _con()
    try:
        return con.execute(f"""
            SELECT
                country,
                net_revenue,
                units_sold,
                n_customers,
                ROUND(100.0 * net_revenue / SUM(net_revenue) OVER (), 2) AS pct_revenue,
                ROUND(100.0 * units_sold / NULLIF(SUM(units_sold) OVER (), 0), 2) AS pct_units
            FROM v_revenue_by_country
            {where_uk}
            ORDER BY net_revenue DESC
        """).df()
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Pregunta 5: ¿Qué productos se pueden prever con fiabilidad?
# ---------------------------------------------------------------------------

def q5_forecastability() -> pd.DataFrame:
    """
    Métricas de 'forecastability' por producto:
    - volumen total
    - número de semanas activas
    - % de semanas sin ventas (intermitencia)
    - coeficiente de variación (CV)
    - volumen medio semanal

    Productos con mucha intermitencia (>50% semanas sin venta) son
    candidatos a modelos agregados, no a forecasting individual.
    """
    con = _con()
    try:
        return con.execute("""
            WITH weekly AS (
                SELECT
                    stock_code,
                    DATE_TRUNC('week', invoice_date)::DATE AS week,
                    SUM(units_sold_line) AS units
                FROM v_sales_lines
                WHERE is_product AND NOT is_partial_month
                GROUP BY stock_code, DATE_TRUNC('week', invoice_date)
            ),
            all_weeks AS (
                SELECT COUNT(DISTINCT week) AS total_weeks
                FROM weekly
            ),
            stats AS (
                SELECT
                    stock_code,
                    COUNT(*) AS n_active_weeks,
                    SUM(units) AS total_units,
                    AVG(units) AS mean_weekly_units,
                    STDDEV(units) AS std_weekly_units
                FROM weekly
                GROUP BY stock_code
            )
            SELECT
                s.stock_code,
                s.n_active_weeks,
                w.total_weeks,
                ROUND(100.0 * (w.total_weeks - s.n_active_weeks) / w.total_weeks, 1) AS pct_missing_weeks,
                s.total_units,
                ROUND(s.mean_weekly_units, 2) AS mean_weekly_units,
                ROUND(s.std_weekly_units / NULLIF(s.mean_weekly_units, 0), 2) AS cv,
                CASE
                    WHEN s.total_units < 50 THEN 'low_volume'
                    WHEN 100.0 * (w.total_weeks - s.n_active_weeks) / w.total_weeks > 50 THEN 'intermittent'
                    WHEN s.std_weekly_units / NULLIF(s.mean_weekly_units, 0) > 1.5 THEN 'high_variance'
                    ELSE 'forecastable'
                END AS forecastability
            FROM stats s
            CROSS JOIN all_weeks w
            ORDER BY total_units DESC
        """).df()
    finally:
        con.close()