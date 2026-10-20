-- ===========================================================================
-- 01_metrics_canonical.sql
-- ---------------------------------------------------------------------------
-- Vista canónica de métricas. UNA SOLA FUENTE DE VERDAD.
--
-- Cada fila es una línea de factura con sus métricas ya clasificadas.
-- Todas las demás vistas y todos los consumidores (dashboard, copiloto,
-- modelos) deben construirse sobre esta vista.
--
-- Definiciones:
--   net_revenue   = suma con signo de line_value (incluye devoluciones)
--   gross_revenue = suma de gross_value (solo líneas positivas con precio > 0)
--   units_sold    = suma de quantity donde quantity > 0
--   returns       = suma de -quantity donde quantity < 0 (valor positivo)
--   units_net     = suma de quantity (positivas y negativas)
-- ===========================================================================

CREATE OR REPLACE VIEW v_sales_lines AS
SELECT
    sales_line_id,
    invoice_no,
    stock_code,
    description,
    quantity,
    invoice_ts,
    invoice_date,
    year,
    month,
    week,
    day_of_week,
    hour,
    unit_price,
    customer_id,
    country,

    -- Clasificación de la línea
    CASE
        WHEN is_cancellation THEN 'cancellation'
        WHEN is_return       THEN 'return'
        WHEN quantity > 0 AND has_valid_price THEN 'sale'
        WHEN quantity > 0 AND NOT has_valid_price THEN 'zero_price_sale'
        ELSE 'other'
    END AS line_type,

    -- Flags que ya teníamos
    is_cancellation,
    is_return,
    is_product,
    has_valid_price,
    is_partial_month,

    -- Métricas por línea
    line_value    AS net_revenue_line,
    gross_value   AS gross_revenue_line,
    quantity      AS units_net_line,
    CASE WHEN quantity > 0 THEN quantity ELSE 0 END AS units_sold_line,
    CASE WHEN quantity < 0 THEN -quantity ELSE 0 END AS returns_line

FROM fact_sales_line;