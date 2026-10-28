\encoding UTF8
-- =====================================================================================
-- 01 · Raw tables
-- One table per Kaggle file, same columns, no transformation.
-- Runs on PostgreSQL and DuckDB. Data is loaded by olistsql.load_raw() (see README).
-- =====================================================================================

DROP TABLE IF EXISTS raw_orders;
CREATE TABLE raw_orders (
    order_id                      VARCHAR PRIMARY KEY,
    customer_id                   VARCHAR,
    order_status                  VARCHAR,
    order_purchase_timestamp      TIMESTAMP,
    order_approved_at             TIMESTAMP,
    order_delivered_carrier_date  TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP
);

DROP TABLE IF EXISTS raw_customers;
CREATE TABLE raw_customers (
    customer_id              VARCHAR PRIMARY KEY,
    customer_unique_id       VARCHAR,
    customer_zip_code_prefix VARCHAR,
    customer_city            VARCHAR,
    customer_state           VARCHAR
);

DROP TABLE IF EXISTS raw_order_items;
CREATE TABLE raw_order_items (
    order_id            VARCHAR,
    order_item_id       INTEGER,
    product_id          VARCHAR,
    seller_id           VARCHAR,
    shipping_limit_date TIMESTAMP,
    price               DOUBLE PRECISION,
    freight_value       DOUBLE PRECISION,
    PRIMARY KEY (order_id, order_item_id)
);

DROP TABLE IF EXISTS raw_order_payments;
CREATE TABLE raw_order_payments (
    order_id             VARCHAR,
    payment_sequential   INTEGER,
    payment_type         VARCHAR,
    payment_installments INTEGER,
    payment_value        DOUBLE PRECISION
);

DROP TABLE IF EXISTS raw_order_reviews;
CREATE TABLE raw_order_reviews (
    review_id               VARCHAR,
    order_id                VARCHAR,
    review_score            INTEGER,
    review_comment_title    VARCHAR,
    review_comment_message  VARCHAR,
    review_creation_date    TIMESTAMP,
    review_answer_timestamp TIMESTAMP
);

DROP TABLE IF EXISTS raw_products;
CREATE TABLE raw_products (
    product_id                 VARCHAR PRIMARY KEY,
    product_category_name      VARCHAR,
    product_name_lenght        INTEGER,
    product_description_lenght INTEGER,
    product_photos_qty         INTEGER,
    product_weight_g           DOUBLE PRECISION,
    product_length_cm          DOUBLE PRECISION,
    product_height_cm          DOUBLE PRECISION,
    product_width_cm           DOUBLE PRECISION
);

DROP TABLE IF EXISTS raw_sellers;
CREATE TABLE raw_sellers (
    seller_id              VARCHAR PRIMARY KEY,
    seller_zip_code_prefix VARCHAR,
    seller_city            VARCHAR,
    seller_state           VARCHAR
);

DROP TABLE IF EXISTS raw_category_translation;
CREATE TABLE raw_category_translation (
    product_category_name         VARCHAR PRIMARY KEY,
    product_category_name_english VARCHAR
);
