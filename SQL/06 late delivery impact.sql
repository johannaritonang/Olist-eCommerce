\encoding UTF8
-- =====================================================================================
-- 06 · What a late box costs
-- Ratings by delivery timing, the late-delivery funnel, and the worst shipping routes.
-- =====================================================================================

-- result: rating by delivery timing
SELECT
    CASE
        WHEN days_late <= -8 THEN '1 - 8+ days early'
        WHEN days_late <= -1 THEN '2 - 1-7 days early'
        WHEN days_late = 0   THEN '3 - on the day'
        WHEN days_late <= 3  THEN '4 - 1-3 days late'
        WHEN days_late <= 7  THEN '5 - 4-7 days late'
        WHEN days_late <= 14 THEN '6 - 8-14 days late'
        ELSE                      '7 - 15+ days late'
    END                                                                         AS delivery_timing,
    COUNT(*)                                                                    AS orders,
    ROUND(CAST(100.0 * COUNT(*) / SUM(COUNT(*)) OVER () AS NUMERIC(18,6)), 1)         AS share_pct,
    ROUND(CAST(AVG(CAST(review_score AS DOUBLE PRECISION)) AS NUMERIC(18,6)), 2)     AS avg_review,
    ROUND(CAST(100.0 * AVG(CASE WHEN review_score <= 2 THEN 1.0 ELSE 0.0 END) AS NUMERIC(18,6)), 1) AS low_review_pct,
    ROUND(CAST(100.0 * AVG(CASE WHEN review_before_arrival THEN 1.0 ELSE 0.0 END) AS NUMERIC(18,6)), 1) AS reviewed_before_arrival_pct
FROM fact_orders
GROUP BY 1
ORDER BY 1;

-- result: late delivery funnel
-- Of all low (1–2★) reviews, how many sit on late orders? Of late orders, how many end in a low review?
SELECT
    COUNT(*)                                                               AS delivered_orders,
    SUM(CASE WHEN is_late THEN 1 ELSE 0 END)                               AS late_orders,
    SUM(CASE WHEN is_late AND review_score <= 2 THEN 1 ELSE 0 END)         AS late_and_low_review,
    SUM(CASE WHEN review_score <= 2 THEN 1 ELSE 0 END)                     AS all_low_reviews,
    ROUND(CAST(100.0 * SUM(CASE WHEN is_late AND review_score <= 2 THEN 1 ELSE 0 END)
               / NULLIF(SUM(CASE WHEN is_late THEN 1 ELSE 0 END), 0) AS NUMERIC(18,6)), 1)  AS late_to_low_review_pct,
    ROUND(CAST(100.0 * SUM(CASE WHEN NOT is_late AND review_score <= 2 THEN 1 ELSE 0 END)
               / NULLIF(SUM(CASE WHEN NOT is_late THEN 1 ELSE 0 END), 0) AS NUMERIC(18,6)), 1) AS on_time_to_low_review_pct,
    ROUND(CAST(100.0 * SUM(CASE WHEN is_late AND review_score <= 2 THEN 1 ELSE 0 END)
               / NULLIF(SUM(CASE WHEN review_score <= 2 THEN 1 ELSE 0 END), 0) AS NUMERIC(18,6)), 1) AS share_of_low_reviews_on_late_pct
FROM fact_orders;

-- result: worst shipping routes
-- Seller state → customer state, routes with at least 300 orders, ranked by late rate.
WITH routes AS (
    SELECT
        seller_state || ' -> ' || customer_state                         AS route,
        same_state,
        COUNT(*)                                                         AS orders,
        AVG(CASE WHEN is_late THEN 1.0 ELSE 0.0 END)                     AS late_rate,
        AVG(CAST(promised_days AS DOUBLE PRECISION))                     AS avg_promised_days,
        AVG(CAST(delivery_days AS DOUBLE PRECISION))                     AS avg_delivery_days,
        AVG(CAST(review_score AS DOUBLE PRECISION))                      AS avg_review
    FROM fact_orders
    WHERE seller_state IS NOT NULL
    GROUP BY seller_state, customer_state, same_state
    HAVING COUNT(*) >= 300
)
SELECT
    RANK() OVER (ORDER BY late_rate DESC)                   AS rank,
    route,
    orders,
    ROUND(CAST(100.0 * late_rate AS NUMERIC(18,6)), 1)            AS late_pct,
    ROUND(CAST(avg_promised_days AS NUMERIC(18,6)), 1)            AS avg_promised_days,
    ROUND(CAST(avg_delivery_days AS NUMERIC(18,6)), 1)            AS avg_delivery_days,
    ROUND(CAST(avg_review AS NUMERIC(18,6)), 2)                   AS avg_review
FROM routes
ORDER BY late_rate DESC
LIMIT 10;
