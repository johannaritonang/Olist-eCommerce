\encoding UTF8
-- =====================================================================================
-- 02 · Clean analysis tables
-- Same rules as the Power BI model and the Python notebook:
--   * purchases from 1 Jan 2017 to 31 Aug 2018, delivered orders only
--   * late = delivered (date) after the estimated delivery date
--   * revenue = item price (freight excluded), customers = customer_unique_id
--   * one review per order: the latest answer
-- =====================================================================================

-- Items with English category and seller state
DROP TABLE IF EXISTS fact_items;
CREATE TABLE fact_items AS
SELECT
    i.order_id,
    i.order_item_id,
    i.product_id,
    i.seller_id,
    s.seller_state,
    COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
    i.price,
    i.freight_value,
    p.product_weight_g,
    p.product_length_cm * p.product_height_cm * p.product_width_cm AS product_volume_cm3
FROM raw_order_items AS i
LEFT JOIN raw_products AS p ON p.product_id = i.product_id
LEFT JOIN raw_category_translation AS t ON t.product_category_name = p.product_category_name
LEFT JOIN raw_sellers AS s ON s.seller_id = i.seller_id;

ANALYZE fact_items;

-- One row per delivered order
DROP TABLE IF EXISTS fact_orders;
CREATE TABLE fact_orders AS
WITH latest_review AS (
    SELECT order_id, review_score, review_creation_date, review_comment_message,
           ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY review_answer_timestamp DESC, review_id) AS rn
    FROM raw_order_reviews
),
item_totals AS (
    SELECT order_id,
           SUM(price)                AS revenue,
           SUM(freight_value)        AS freight,
           COUNT(*)                  AS items,
           COUNT(DISTINCT seller_id) AS sellers,
           SUM(product_weight_g)     AS weight_g
    FROM fact_items
    GROUP BY order_id
),
first_item AS (          -- category and seller of the first item, as in the notebook
    SELECT order_id, category, seller_id, seller_state,
           ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY order_item_id) AS rn
    FROM fact_items
)
SELECT
    o.order_id,
    c.customer_unique_id,
    c.customer_state,
    CASE
        WHEN c.customer_state IN ('AC','AP','AM','PA','RO','RR','TO') THEN 'North'
        WHEN c.customer_state IN ('AL','BA','CE','MA','PB','PE','PI','RN','SE') THEN 'Northeast'
        WHEN c.customer_state IN ('DF','GO','MT','MS') THEN 'Center-West'
        WHEN c.customer_state IN ('ES','MG','RJ','SP') THEN 'Southeast'
        WHEN c.customer_state IN ('PR','RS','SC') THEN 'South'
    END                                                              AS region,
    o.order_purchase_timestamp                                       AS purchased_at,
    CAST(o.order_purchase_timestamp AS DATE)                         AS purchase_date,
    CAST(DATE_TRUNC('month', o.order_purchase_timestamp) AS DATE)    AS purchase_month,
    CAST(o.order_delivered_customer_date AS DATE)                    AS delivered_date,
    CAST(o.order_estimated_delivery_date AS DATE)                    AS estimated_date,
    CAST(o.order_estimated_delivery_date AS DATE) - CAST(o.order_purchase_timestamp AS DATE)  AS promised_days,
    CAST(o.order_delivered_customer_date AS DATE) - CAST(o.order_purchase_timestamp AS DATE)  AS delivery_days,
    CAST(o.order_delivered_customer_date AS DATE) - CAST(o.order_estimated_delivery_date AS DATE) AS days_late,
    CAST(o.order_delivered_customer_date AS DATE) > CAST(o.order_estimated_delivery_date AS DATE) AS is_late,
    it.revenue,
    it.freight,
    it.items,
    it.sellers,
    it.weight_g,
    fi.category,
    fi.seller_id,
    fi.seller_state,
    fi.seller_state = c.customer_state                               AS same_state,
    r.review_score,
    CAST(r.review_creation_date AS DATE) < CAST(o.order_delivered_customer_date AS DATE) AS review_before_arrival
FROM raw_orders AS o
JOIN raw_customers AS c ON c.customer_id = o.customer_id
LEFT JOIN item_totals AS it ON it.order_id = o.order_id
LEFT JOIN first_item  AS fi ON fi.order_id = o.order_id AND fi.rn = 1
LEFT JOIN latest_review AS r ON r.order_id = o.order_id AND r.rn = 1
WHERE o.order_purchase_timestamp >= TIMESTAMP '2017-01-01'
  AND o.order_purchase_timestamp <  TIMESTAMP '2018-09-01'
  AND o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL;

ANALYZE fact_orders;

-- Check against the dashboard: 96,203 delivered orders, 6.8% late, 4.3★ on time vs 2.3★ late
-- result: reconciliation
SELECT
    COUNT(*)                                                                 AS delivered_orders,
    COUNT(DISTINCT customer_unique_id)                                       AS customers,
    ROUND(CAST(SUM(revenue) AS NUMERIC(18,6)), 0)                                  AS revenue_brl,
    ROUND(CAST(100.0 * AVG(CASE WHEN is_late THEN 1 ELSE 0 END) AS NUMERIC(18,6)), 1) AS late_pct,
    ROUND(CAST(AVG(review_score) FILTER (WHERE NOT is_late) AS NUMERIC(18,6)), 2)  AS avg_review_on_time,
    ROUND(CAST(AVG(review_score) FILTER (WHERE is_late) AS NUMERIC(18,6)), 2)      AS avg_review_late
FROM fact_orders;
