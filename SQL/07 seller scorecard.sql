\encoding UTF8
-- =====================================================================================
-- 07 · Seller scorecard
-- Every seller with 30+ delivered orders: volume, lateness, ratings, rank within their state
-- and percentile against all sellers. A watch list flags sellers that are late at least twice
-- as often as the platform.
-- =====================================================================================

DROP TABLE IF EXISTS seller_scorecard;
CREATE TABLE seller_scorecard AS
WITH seller_orders AS (          -- an order counts for every seller that shipped an item in it
    SELECT DISTINCT i.seller_id, i.seller_state, o.order_id, o.is_late, o.review_score, o.delivery_days
    FROM fact_items AS i
    JOIN fact_orders AS o ON o.order_id = i.order_id
),
seller_revenue AS (
    SELECT i.seller_id, SUM(i.price) AS revenue
    FROM fact_items AS i
    JOIN fact_orders AS o ON o.order_id = i.order_id
    GROUP BY i.seller_id
),
platform AS (
    SELECT AVG(CASE WHEN is_late THEN 1.0 ELSE 0.0 END) AS late_rate FROM fact_orders
),
sellers AS (
    SELECT
        s.seller_id,
        s.seller_state,
        COUNT(*)                                                AS orders,
        AVG(CASE WHEN s.is_late THEN 1.0 ELSE 0.0 END)          AS late_rate,
        SUM(CASE WHEN s.is_late THEN 1 ELSE 0 END)              AS late_orders,
        AVG(CAST(s.review_score AS DOUBLE PRECISION))           AS avg_review,
        AVG(CASE WHEN s.review_score <= 2 THEN 1.0 ELSE 0.0 END) AS low_review_rate,
        AVG(CAST(s.delivery_days AS DOUBLE PRECISION))          AS avg_delivery_days
    FROM seller_orders AS s
    GROUP BY s.seller_id, s.seller_state
    HAVING COUNT(*) >= 30
)
SELECT
    s.*,
    r.revenue,
    RANK() OVER (PARTITION BY s.seller_state ORDER BY s.late_rate)        AS late_rank_in_state,   -- 1 = most punctual
    COUNT(*) OVER (PARTITION BY s.seller_state)                           AS sellers_in_state,
    PERCENT_RANK() OVER (ORDER BY s.late_rate)                            AS late_percentile,      -- 1 = latest of all
    PERCENT_RANK() OVER (ORDER BY s.avg_review)                           AS review_percentile,    -- 1 = best rated
    CASE WHEN s.orders >= 50 AND s.late_rate >= 2 * p.late_rate THEN TRUE ELSE FALSE END AS watch_list
FROM sellers AS s
JOIN seller_revenue AS r ON r.seller_id = s.seller_id
CROSS JOIN platform AS p;

-- result: watch list
SELECT
    seller_id,
    seller_state,
    orders,
    late_orders,
    ROUND(CAST(100.0 * late_rate AS NUMERIC(18,6)), 1)        AS late_pct,
    ROUND(CAST(avg_review AS NUMERIC(18,6)), 2)               AS avg_review,
    late_rank_in_state || ' of ' || sellers_in_state    AS rank_in_state
FROM seller_scorecard
WHERE watch_list
ORDER BY late_orders DESC, seller_id
LIMIT 15;

-- result: watch list concentration
SELECT
    COUNT(*)                                                                   AS sellers_scored,
    SUM(CASE WHEN watch_list THEN 1 ELSE 0 END)                                AS watch_list_sellers,
    ROUND(CAST(100.0 * SUM(CASE WHEN watch_list THEN orders ELSE 0 END) / SUM(orders) AS NUMERIC(18,6)), 1)           AS watch_list_share_of_orders_pct,
    ROUND(CAST(100.0 * SUM(CASE WHEN watch_list THEN late_orders ELSE 0 END) / SUM(late_orders) AS NUMERIC(18,6)), 1) AS watch_list_share_of_late_orders_pct
FROM seller_scorecard;
