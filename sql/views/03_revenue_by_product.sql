-- Agregación por producto (excluye no-productos y precio inválido).
CREATE OR REPLACE VIEW v_revenue_by_product AS
SELECT
    stock_code,
    MODE(description)                                              AS description,
    COUNT(*)                                                       AS n_lines,
    COUNT(DISTINCT invoice_no)                                     AS n_invoices,
    ROUND(SUM(net_revenue_line), 2)                                AS net_revenue,
    ROUND(SUM(gross_revenue_line), 2)                              AS gross_revenue,
    SUM(units_net_line)                                            AS units_net,
    SUM(units_sold_line)                                           AS units_sold,
    SUM(returns_line)                                              AS returns,
    MIN(invoice_date)                                              AS first_sale_date,
    MAX(invoice_date)                                              AS last_sale_date,
    COUNT(DISTINCT invoice_date)                                   AS n_active_days
FROM v_sales_lines
WHERE is_product = TRUE
GROUP BY stock_code;