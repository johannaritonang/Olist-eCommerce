\encoding UTF8
-- =====================================================================================
-- 03 · KPIs and trends
-- Monthly volume, revenue growth (LAG), lateness and ratings; the same KPIs by region.
-- =====================================================================================

-- result: monthly trend
WITH monthly AS (
    SELECT
        purchase_month,
        COUNT(*)                                              AS orders,
        SUM(revenue)                                          AS revenue,
        AVG(CASE WHEN is_late THEN 1.0 ELSE 0.0 END)          AS late_rate,
        AVG(CAST(review_score AS DOUBLE PRECISION))           AS avg_review,
        AVG(CASE WHEN review_score <= 2 THEN 1.0 ELSE 0.0 END) AS low_review_rate
    FROM fact_orders
    GROUP BY purchase_month
)
SELECT
    purchase_month,
    orders,
    ROUND(CAST(revenue AS NUMERIC(18,6)), 0)                                               AS revenue_brl,
    ROUND(CAST(100.0 * (revenue / LAG(revenue) OVER (ORDER BY purchase_month) - 1) AS NUMERIC(18,6)), 1) AS revenue_mom_pct,
    ROUND(CAST(100.0 * late_rate AS NUMERIC(18,6)), 1)                                     AS late_pct,
    ROUND(CAST(avg_review AS NUMERIC(18,6)), 2)                                            AS avg_review,
    ROUND(CAST(100.0 * low_review_rate AS NUMERIC(18,6)), 1)                               AS low_review_pct
FROM monthly
ORDER BY purchase_month;

-- result: kpis by region
SELECT
    region,
    COUNT(*)                                                                   AS orders,
    ROUND(CAST(100.0 * COUNT(*) / SUM(COUNT(*)) OVER () AS NUMERIC(18,6)), 1)        AS share_of_orders_pct,
    ROUND(CAST(AVG(revenue) AS NUMERIC(18,6)), 1)                                    AS avg_order_brl,
    ROUND(CAST(100.0 * AVG(freight / NULLIF(revenue, 0)) AS NUMERIC(18,6)), 1)       AS freight_pct_of_price,
    ROUND(CAST(AVG(CAST(delivery_days AS DOUBLE PRECISION)) AS NUMERIC(18,6)), 1)    AS avg_delivery_days,
    ROUND(CAST(100.0 * AVG(CASE WHEN is_late THEN 1.0 ELSE 0.0 END) AS NUMERIC(18,6)), 1) AS late_pct,
    ROUND(CAST(AVG(CAST(review_score AS DOUBLE PRECISION)) AS NUMERIC(18,6)), 2)    AS avg_review
FROM fact_orders
GROUP BY region
ORDER BY late_pct DESC;
