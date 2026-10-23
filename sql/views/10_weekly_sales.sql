-- ===========================================================================
-- 08_weekly_sales.sql
-- ---------------------------------------------------------------------------
-- Serie semanal por producto, la unidad mínima de forecasting.
--
-- Granularidad: (stock_code, week_start) -> units_sold.
-- week_start = lunes de cada semana (ISO week, estándar en retail).
--
-- Solo se incluyen productos REALES (is_product = TRUE).
-- Los no-productos (POST, DOT, etc.) se excluyen: no son predecibles.
-- ===========================================================================

CREATE OR REPLACE VIEW v_weekly_sales AS
SELECT
    stock_code,
    -- Lunes de la semana (DATE_TRUNC en DuckDB de una fecha da el inicio)
    DATE_TRUNC('week', invoice_date)::DATE AS week_start,
    SUM(units_sold_line) AS units_sold,
    SUM(units_net_line) AS units_net,
    SUM(returns_line) AS units_returned,
    COUNT(DISTINCT invoice_no) AS n_invoices,
    COUNT(DISTINCT customer_id) FILTER (WHERE customer_id IS NOT NULL) AS n_customers,
    ROUND(SUM(gross_revenue_line), 2) AS gross_revenue
FROM v_sales_lines
WHERE is_product = TRUE
  AND NOT is_partial_month
GROUP BY stock_code, DATE_TRUNC('week', invoice_date);