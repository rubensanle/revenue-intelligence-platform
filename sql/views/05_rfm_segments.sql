-- RFM: Recencia, Frecuencia, Monetario. Solo clientes identificados.
-- La fecha de referencia es el último día del dataset.
CREATE OR REPLACE VIEW v_rfm_segments AS
WITH ref_date AS (
    SELECT MAX(invoice_date) AS max_date FROM v_sales_lines
),
customer_agg AS (
    SELECT
        customer_id,
        MAX(invoice_date)                                          AS last_purchase,
        COUNT(DISTINCT invoice_no)                                 AS frequency,
        ROUND(SUM(net_revenue_line), 2)                            AS monetary
    FROM v_sales_lines
    WHERE customer_id IS NOT NULL
    GROUP BY customer_id
),
rfm_base AS (
    SELECT
        c.customer_id,
        (SELECT max_date FROM ref_date) - c.last_purchase         AS recency_days,
        c.frequency,
        c.monetary
    FROM customer_agg c
),
rfm_scored AS (
    SELECT
        customer_id,
        recency_days,
        frequency,
        monetary,
        -- Score 1–5 con NTILE (más alto = mejor)
        NTILE(5) OVER (ORDER BY recency_days ASC)                 AS r_score,
        NTILE(5) OVER (ORDER BY frequency DESC)                   AS f_score,
        NTILE(5) OVER (ORDER BY monetary DESC)                    AS m_score
    FROM rfm_base
)
SELECT
    customer_id,
    recency_days,
    frequency,
    monetary,
    r_score,
    f_score,
    m_score,
    CASE
        WHEN r_score >= 4 AND f_score >= 4 THEN 'champion'
        WHEN r_score >= 3 AND f_score >= 3 THEN 'loyal'
        WHEN r_score >= 4 AND f_score <= 2 THEN 'new'
        WHEN r_score <= 2 AND f_score >= 3 THEN 'at_risk'
        WHEN r_score <= 2 AND f_score <= 2 THEN 'lost'
        ELSE 'regular'
    END AS rfm_segment
FROM rfm_scored;