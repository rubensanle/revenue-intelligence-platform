-- Devoluciones por producto.
-- Mide unidades devueltas, tasa de devolución y tendencia.
--
-- Notas:
--   - return_rate_recent_pct es NULL si units_sold_recent = 0
--     (no se puede calcular tasa sin ventas).
--   - return_severity = 'no_sales_but_returns' cuando hay devoluciones
--     pero no ventas en el período (devolución de ventas anteriores,
--     ajuste de inventario o error de datos).
CREATE OR REPLACE VIEW v_returns_by_product AS
WITH returns AS (
    SELECT
        stock_code,
        SUM(CASE WHEN invoice_date >= DATE '2011-06-01'
                 THEN returns_line ELSE 0 END) AS units_returned_recent,
        SUM(CASE WHEN invoice_date <  DATE '2011-06-01'
                 THEN returns_line ELSE 0 END) AS units_returned_previous,
        COUNT(DISTINCT CASE WHEN invoice_date >= DATE '2011-06-01'
                            THEN invoice_no END) AS n_invoices_returned_recent
    FROM v_sales_lines
    WHERE is_product AND NOT is_partial_month
      AND line_type IN ('sale', 'cancellation', 'return')
    GROUP BY stock_code
),
sales AS (
    SELECT
        stock_code,
        SUM(CASE WHEN invoice_date >= DATE '2011-06-01'
                 THEN units_sold_line ELSE 0 END) AS units_sold_recent,
        SUM(CASE WHEN invoice_date <  DATE '2011-06-01'
                 THEN units_sold_line ELSE 0 END) AS units_sold_previous,
        MODE(description) AS description
    FROM v_sales_lines
    WHERE is_product AND NOT is_partial_month
      AND line_type IN ('sale', 'cancellation', 'return')
    GROUP BY stock_code
)
SELECT
    COALESCE(r.stock_code, s.stock_code) AS stock_code,
    s.description,
    COALESCE(r.units_returned_recent, 0)   AS units_returned_recent,
    COALESCE(r.units_returned_previous, 0) AS units_returned_previous,
    COALESCE(s.units_sold_recent, 0)       AS units_sold_recent,
    COALESCE(s.units_sold_previous, 0)     AS units_sold_previous,
    COALESCE(r.n_invoices_returned_recent, 0) AS n_invoices_returned_recent,

    -- Tasa de devolución reciente (%)
    -- NULL si no hay ventas (no se puede calcular la tasa).
    CASE
        WHEN COALESCE(s.units_sold_recent, 0) = 0 THEN NULL
        ELSE ROUND(
            100.0 * COALESCE(r.units_returned_recent, 0)
            / NULLIF(COALESCE(s.units_sold_recent, 0) + COALESCE(r.units_returned_recent, 0), 0),
            2
        )
    END AS return_rate_recent_pct,

    -- Tasa de devolución anterior (%)
    -- NULL si no hay ventas en el período anterior.
    CASE
        WHEN COALESCE(s.units_sold_previous, 0) = 0 THEN NULL
        ELSE ROUND(
            100.0 * COALESCE(r.units_returned_previous, 0)
            / NULLIF(COALESCE(s.units_sold_previous, 0) + COALESCE(r.units_returned_previous, 0), 0),
            2
        )
    END AS return_rate_previous_pct,

    -- Tendencia de devoluciones
    COALESCE(r.units_returned_recent, 0) - COALESCE(r.units_returned_previous, 0) AS returns_delta,
    CASE
        WHEN COALESCE(r.units_returned_previous, 0) = 0 THEN NULL
        ELSE ROUND(
            100.0 * (COALESCE(r.units_returned_recent, 0) - COALESCE(r.units_returned_previous, 0))
            / NULLIF(ABS(COALESCE(r.units_returned_previous, 0)), 0),
            1
        )
    END AS returns_growth_pct,

    -- Clasificación
    CASE
        WHEN COALESCE(r.units_returned_recent, 0) = 0 THEN 'no_returns'
        -- Caso especial: devoluciones sin ventas (no se puede calcular tasa)
        WHEN COALESCE(s.units_sold_recent, 0) = 0 THEN 'no_sales_but_returns'
        WHEN 100.0 * COALESCE(r.units_returned_recent, 0)
             / NULLIF(COALESCE(s.units_sold_recent, 0) + COALESCE(r.units_returned_recent, 0), 0) > 50
             THEN 'high_return_rate'
        WHEN 100.0 * COALESCE(r.units_returned_recent, 0)
             / NULLIF(COALESCE(s.units_sold_recent, 0) + COALESCE(r.units_returned_recent, 0), 0) > 20
             THEN 'medium_return_rate'
        ELSE 'low_return_rate'
    END AS return_severity

FROM returns r
FULL OUTER JOIN sales s USING (stock_code)
WHERE COALESCE(r.units_returned_recent, 0) > 0
   OR COALESCE(r.units_returned_previous, 0) > 0
ORDER BY units_returned_recent DESC;