-- Devoluciones por cliente.
-- Mide unidades devueltas, tasa de devolución y revenue devuelto.
CREATE OR REPLACE VIEW v_returns_by_customer AS
WITH returns AS (
    SELECT
        customer_id,
        SUM(CASE WHEN invoice_date >= DATE '2011-06-01'
                 THEN returns_line ELSE 0 END) AS units_returned_recent,
        SUM(CASE WHEN invoice_date >= DATE '2011-06-01'
                 THEN -net_revenue_line ELSE 0 END) AS revenue_returned_recent,
        COUNT(DISTINCT CASE WHEN invoice_date >= DATE '2011-06-01'
                            THEN invoice_no END) AS n_invoices_returned_recent
    FROM v_sales_lines
    WHERE is_product AND NOT is_partial_month
      AND line_type IN ('sale', 'cancellation', 'return')
      AND customer_id IS NOT NULL
    GROUP BY customer_id
),
sales AS (
    SELECT
        customer_id,
        SUM(CASE WHEN invoice_date >= DATE '2011-06-01'
                 THEN units_sold_line ELSE 0 END) AS units_sold_recent,
        SUM(CASE WHEN invoice_date >= DATE '2011-06-01'
                 THEN gross_revenue_line ELSE 0 END) AS revenue_sold_recent,
        COUNT(DISTINCT CASE WHEN invoice_date >= DATE '2011-06-01'
                            THEN invoice_no END) AS n_invoices_recent,
        MODE(country) AS country
    FROM v_sales_lines
    WHERE is_product AND NOT is_partial_month
      AND line_type IN ('sale', 'cancellation', 'return')
      AND customer_id IS NOT NULL
    GROUP BY customer_id
)
SELECT
    COALESCE(r.customer_id, s.customer_id) AS customer_id,
    s.country,
    COALESCE(r.units_returned_recent, 0)     AS units_returned_recent,
    COALESCE(s.units_sold_recent, 0)         AS units_sold_recent,
    COALESCE(r.revenue_returned_recent, 0)   AS revenue_returned_recent,
    COALESCE(s.revenue_sold_recent, 0)       AS revenue_sold_recent,
    COALESCE(r.n_invoices_returned_recent, 0) AS n_invoices_returned_recent,
    COALESCE(s.n_invoices_recent, 0)         AS n_invoices_recent,

    -- Tasa de devolución por unidades
    ROUND(
        100.0 * COALESCE(r.units_returned_recent, 0)
        / NULLIF(COALESCE(s.units_sold_recent, 0) + COALESCE(r.units_returned_recent, 0), 0),
        2
    ) AS return_rate_units_pct,

    -- Tasa de devolución por revenue
    ROUND(
        100.0 * COALESCE(r.revenue_returned_recent, 0)
        / NULLIF(COALESCE(s.revenue_sold_recent, 0) + COALESCE(r.revenue_returned_recent, 0), 0),
        2
    ) AS return_rate_revenue_pct,

    -- Clasificación
    CASE
        WHEN COALESCE(r.units_returned_recent, 0) = 0 THEN 'no_returns'
        WHEN 100.0 * COALESCE(r.units_returned_recent, 0)
             / NULLIF(COALESCE(s.units_sold_recent, 0) + COALESCE(r.units_returned_recent, 0), 0) > 30
             THEN 'high_returner'
        WHEN 100.0 * COALESCE(r.units_returned_recent, 0)
             / NULLIF(COALESCE(s.units_sold_recent, 0) + COALESCE(r.units_returned_recent, 0), 0) > 10
             THEN 'medium_returner'
        ELSE 'low_returner'
    END AS returner_severity

FROM returns r
FULL OUTER JOIN sales s USING (customer_id)
WHERE COALESCE(r.units_returned_recent, 0) > 0
ORDER BY units_returned_recent DESC;