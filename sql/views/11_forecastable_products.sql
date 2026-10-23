-- ===========================================================================
-- 09_forecastable_products.sql
-- ---------------------------------------------------------------------------
-- Lista de productos que se incluirán en el forecasting individual (MVP).
--
-- Un producto es forecastable si:
--   - Tiene >= 50 unidades totales (evita low_volume).
--   - Tiene al menos 50 semanas activas (evita intermittent).
--   - CV < 1.5 (evita high_variance).
--   - No está marcado como anomaly_returns.
--
-- Esto reproduce la clasificación del EDA, pero persistida en SQL
-- para que el modelo la pueda consumir directamente.
-- ===========================================================================

CREATE OR REPLACE VIEW v_forecastable_products AS
WITH stats AS (
    SELECT
        stock_code,
        COUNT(DISTINCT week_start) AS n_active_weeks,
        SUM(units_sold) AS total_units,
        AVG(units_sold) AS mean_weekly_units,
        STDDEV(units_sold) AS std_weekly_units
    FROM v_weekly_sales
    GROUP BY stock_code
),
total_weeks AS (
    SELECT COUNT(DISTINCT week_start) AS n FROM v_weekly_sales
),
returns_agg AS (
    SELECT
        stock_code,
        SUM(units_returned) AS units_returned_total,
        SUM(units_sold) AS units_sold_total
    FROM v_weekly_sales
    GROUP BY stock_code
)
SELECT
    s.stock_code,
    s.n_active_weeks,
    s.total_units,
    s.mean_weekly_units,
    s.std_weekly_units,
    ROUND(s.std_weekly_units / NULLIF(s.mean_weekly_units, 0), 2) AS cv,
    CASE
        WHEN s.total_units < 50 THEN 'low_volume'
        WHEN 100.0 * (t.n - s.n_active_weeks) / t.n > 50 THEN 'intermittent'
        WHEN s.std_weekly_units / NULLIF(s.mean_weekly_units, 0) > 1.5 THEN 'high_variance'
        WHEN r.units_sold_total > 0
             AND r.units_returned_total / r.units_sold_total > 0.5
             THEN 'anomaly_returns'
        ELSE 'forecastable'
    END AS forecastability
FROM stats s
CROSS JOIN total_weeks t
LEFT JOIN returns_agg r USING (stock_code);