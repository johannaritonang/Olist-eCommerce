\encoding UTF8
-- =====================================================================================
-- 04 · Cohort retention
-- Customers grouped by the month of their first delivered order; the share who order again
-- 1, 2, ... 12 months later. Then the 180-day repeat rate used in the notebook (3.0%).
-- =====================================================================================

DROP TABLE IF EXISTS customer_months;
CREATE TABLE customer_months AS
WITH firsts AS (
    SELECT customer_unique_id, MIN(purchase_month) AS cohort_month
    FROM fact_orders
    GROUP BY customer_unique_id
)
SELECT DISTINCT
    o.customer_unique_id,
    f.cohort_month,
    o.purchase_month,
    CAST((EXTRACT(YEAR FROM o.purchase_month) - EXTRACT(YEAR FROM f.cohort_month)) * 12
         + EXTRACT(MONTH FROM o.purchase_month) - EXTRACT(MONTH FROM f.cohort_month) AS INTEGER) AS month_number
FROM fact_orders AS o
JOIN firsts AS f ON f.customer_unique_id = o.customer_unique_id;

-- result: cohort retention
WITH cohort_size AS (
    SELECT cohort_month, COUNT(DISTINCT customer_unique_id) AS customers
    FROM customer_months
    WHERE month_number = 0
    GROUP BY cohort_month
),
active AS (
    SELECT cohort_month, month_number, COUNT(DISTINCT customer_unique_id) AS active_customers
    FROM customer_months
    WHERE month_number BETWEEN 1 AND 12
    GROUP BY cohort_month, month_number
)
SELECT
    c.cohort_month,
    c.customers,
    a.month_number,
    a.active_customers,
    ROUND(CAST(100.0 * a.active_customers / c.customers AS NUMERIC(18,6)), 2) AS retention_pct
FROM cohort_size AS c
JOIN active AS a ON a.cohort_month = c.cohort_month
WHERE c.cohort_month <= DATE '2018-02-01'          -- cohorts with at least 6 months of follow-up
ORDER BY c.cohort_month, a.month_number;

-- result: repeat customers
-- Share of customers with two or more delivered orders (the dashboard's 3.0%).
SELECT
    COUNT(*)                                                                    AS customers,
    SUM(CASE WHEN orders >= 2 THEN 1 ELSE 0 END)                                AS repeat_customers,
    ROUND(CAST(100.0 * AVG(CASE WHEN orders >= 2 THEN 1.0 ELSE 0.0 END) AS NUMERIC(18,6)), 1) AS repeat_customers_pct
FROM (
    SELECT customer_unique_id, COUNT(DISTINCT order_id) AS orders
    FROM fact_orders
    GROUP BY customer_unique_id
) AS per_customer;

-- result: repeat within 180 days
-- Second order on a different day within 180 days, for customers whose first order is before
-- 1 Mar 2018 (so every customer has a full 180-day window before the data ends).
WITH customer_days AS (
    SELECT DISTINCT customer_unique_id, purchase_date
    FROM fact_orders
),
ranked AS (
    SELECT customer_unique_id, purchase_date,
           ROW_NUMBER() OVER (PARTITION BY customer_unique_id ORDER BY purchase_date) AS nth
    FROM customer_days
),
first_two AS (
    SELECT customer_unique_id,
           MAX(CASE WHEN nth = 1 THEN purchase_date END) AS first_date,
           MAX(CASE WHEN nth = 2 THEN purchase_date END) AS second_date
    FROM ranked
    WHERE nth <= 2
    GROUP BY customer_unique_id
)
SELECT
    COUNT(*)                                                                         AS eligible_customers,
    SUM(CASE WHEN second_date - first_date <= 180 THEN 1 ELSE 0 END)                 AS repeat_customers,
    ROUND(CAST(100.0 * AVG(CASE WHEN second_date - first_date <= 180 THEN 1.0 ELSE 0.0 END) AS NUMERIC(18,6)), 1) AS repeat_pct,
    ROUND(CAST(AVG(CAST(second_date - first_date AS DOUBLE PRECISION)) AS NUMERIC(18,6)), 0) AS avg_days_to_second_order
FROM first_two
WHERE first_date < DATE '2018-03-01';
