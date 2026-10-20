-- Crecimiento mes a mes y año a año.
CREATE OR REPLACE VIEW v_monthly_growth AS
WITH monthly AS (
    SELECT
        DATE_TRUNC('month', invoice_date)::DATE                    AS month,
        ROUND(SUM(net_revenue_line), 2)                            AS net_revenue,
        SUM(units_sold_line)                                       AS units_sold
    FROM v_sales_lines
    GROUP BY DATE_TRUNC('month', invoice_date)
)
SELECT
    month,
    net_revenue,
    units_sold,
    LAG(net_revenue) OVER (ORDER BY month)                         AS prev_month_revenue,
    ROUND(
        100.0 * (net_revenue - LAG(net_revenue) OVER (ORDER BY month))
        / NULLIF(LAG(net_revenue) OVER (ORDER BY month), 0),
        2
    )                                                              AS mom_growth_pct,
    LAG(net_revenue, 12) OVER (ORDER BY month)                     AS prev_year_revenue,
    ROUND(
        100.0 * (net_revenue - LAG(net_revenue, 12) OVER (ORDER BY month))
        / NULLIF(LAG(net_revenue, 12) OVER (ORDER BY month), 0),
        2
    )                                                              AS yoy_growth_pct
FROM monthly;