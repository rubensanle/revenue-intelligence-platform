-- Agregación por país. Útil para comparar mercados.
CREATE OR REPLACE VIEW v_revenue_by_country AS
SELECT
    country,
    COUNT(*)                                                       AS n_lines,
    COUNT(DISTINCT invoice_no)                                     AS n_invoices,
    COUNT(DISTINCT customer_id) FILTER (WHERE customer_id IS NOT NULL) AS n_customers,
    ROUND(SUM(net_revenue_line), 2)                                AS net_revenue,
    ROUND(SUM(gross_revenue_line), 2)                              AS gross_revenue,
    SUM(units_net_line)                                            AS units_net,
    SUM(units_sold_line)                                           AS units_sold,
    SUM(returns_line)                                              AS returns
FROM v_sales_lines
GROUP BY country;