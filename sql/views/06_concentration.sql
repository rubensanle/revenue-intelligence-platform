-- Concentración de ingresos: ¿qué % de productos generan el 80% del ingreso?
CREATE OR REPLACE VIEW v_product_concentration AS
WITH ranked AS (
    SELECT
        stock_code,
        net_revenue,
        ROW_NUMBER() OVER (ORDER BY net_revenue DESC)              AS rank,
        SUM(net_revenue) OVER (ORDER BY net_revenue DESC)          AS cumulative_revenue,
        SUM(net_revenue) OVER ()                                   AS total_revenue
    FROM v_revenue_by_product
    WHERE net_revenue > 0
)
SELECT
    stock_code,
    net_revenue,
    rank,
    ROUND(cumulative_revenue, 2)                                   AS cumulative_revenue,
    ROUND(100.0 * cumulative_revenue / total_revenue, 2)           AS cumulative_pct
FROM ranked;