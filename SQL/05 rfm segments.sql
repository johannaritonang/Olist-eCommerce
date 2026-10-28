\encoding UTF8
-- =====================================================================================
-- 05 · RFM segments
-- Recency, Frequency and Monetary value per customer, scored 1–5 with NTILE.
-- Frequency is 1 for about 97% of customers, so segments lean on Recency × Monetary.
-- =====================================================================================

DROP TABLE IF EXISTS customer_rfm;
CREATE TABLE customer_rfm AS
WITH snapshot AS (
    SELECT MAX(purchase_date) + 1 AS as_of FROM fact_orders
),
base AS (
    SELECT
        o.customer_unique_id,
        MIN(s.as_of - o.purchase_date)          AS recency_days,
        COUNT(DISTINCT o.order_id)              AS frequency,
        SUM(o.revenue)                          AS monetary
    FROM fact_orders AS o
    CROSS JOIN snapshot AS s
    GROUP BY o.customer_unique_id
),
scored AS (
    SELECT *,
           NTILE(5) OVER (ORDER BY recency_days DESC, customer_unique_id) AS r_score,   -- 5 = bought most recently
           NTILE(5) OVER (ORDER BY monetary, customer_unique_id) AS m_score,   -- 5 = spent the most
           CASE WHEN frequency >= 3 THEN 5 WHEN frequency = 2 THEN 4 ELSE 1 END AS f_score
    FROM base
)
SELECT *,
       CASE
           WHEN frequency >= 2 AND r_score >= 3 THEN 'Loyal repeaters'
           WHEN frequency >= 2                  THEN 'Lapsed repeaters'
           WHEN r_score >= 4 AND m_score >= 4   THEN 'New big spenders'
           WHEN r_score >= 4                    THEN 'New small spenders'
           WHEN r_score <= 2 AND m_score >= 4   THEN 'Big spenders at risk'
           WHEN r_score <= 2                    THEN 'Hibernating'
           ELSE 'Middle'
       END AS segment
FROM scored;

-- result: rfm segments
SELECT
    segment,
    COUNT(*)                                                                 AS customers,
    ROUND(CAST(100.0 * COUNT(*) / SUM(COUNT(*)) OVER () AS NUMERIC(18,6)), 1)      AS share_of_customers_pct,
    ROUND(CAST(100.0 * SUM(monetary) / SUM(SUM(monetary)) OVER () AS NUMERIC(18,6)), 1) AS share_of_revenue_pct,
    ROUND(CAST(AVG(CAST(recency_days AS DOUBLE PRECISION)) AS NUMERIC(18,6)), 0)   AS avg_recency_days,
    ROUND(CAST(AVG(frequency * 1.0) AS NUMERIC(18,6)), 2)                          AS avg_orders,
    ROUND(CAST(AVG(monetary) AS NUMERIC(18,6)), 0)                                 AS avg_spend_brl
FROM customer_rfm
GROUP BY segment
ORDER BY share_of_revenue_pct DESC;
