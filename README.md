# The Cost of a Late Box · Olist end to end

**Power BI · SQL (PostgreSQL / DuckDB) · Python · Machine learning · Streamlit**

One question, followed through every layer of a data stack: **what does late delivery cost a Brazilian marketplace, and can it be prevented?**
Built on the public [Olist e-commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (96,203 delivered orders, Jan 2017 – Aug 2018).

### 👉 [Open the live app](https://olist-delivery-risk.streamlit.app)

[![Order risk checker](images/app%20risk%20checker.png)](https://olist-delivery-risk.streamlit.app)

| Layer | File | What it answers |
|---|---|---|
| **Dashboard** | `Power BI/` | Sales, delivery and review KPIs for the business |
| **SQL** | `sql/` · [Olist SQL Analysis](Olist%20SQL%20Analysis.ipynb) | Clean tables, cohorts, RFM, late-delivery funnel, seller watch list |
| **Python deep dive** | [Olist Deep Dive](Olist%20Deep%20Dive.ipynb) | How much a late box costs in stars, what customers complain about, whether they come back |
| **Risk model** | [Olist Late Delivery Model](Olist%20Late%20Delivery%20Model.ipynb) | Which orders will arrive late, predicted at checkout, explained with SHAP |
| **App** | `app/` · [live](https://olist-delivery-risk.streamlit.app) | Explore the data, score a new order, review a seller |

## Headline results
* **Late orders are 6.8% of deliveries but 32.6% of all 1–2★ reviews.** 61% of late orders end in a low review, against 9% of on-time orders. Being 4–7 days late costs about 1.9★ even with controls.
* **The North-East is twice as late as the South-East** (12.8% vs 6.1%), and SP → RJ is the route with the most late parcels.
* **30 sellers ship 4% of orders but cause 10% of late deliveries.** They form a concrete watch list.
* **Lateness can be predicted at checkout** (ROC AUC 0.73 on six unseen months). The riskiest 10% of orders hold 28% of late ones. The biggest driver is a promise of 10 days or less.
* **Olist is an acquisition business:** only 3.0% of customers ever order twice, so the damage of a late box shows up in reviews, not in lost repeat sales.

## SQL
Seven plain `.sql` files that run unchanged on **PostgreSQL** and **DuckDB**:

| File | Techniques |
|---|---|
| `01 raw tables.sql` | DDL, primary keys |
| `02 clean orders.sql` | CTEs, `ROW_NUMBER`, joins, date arithmetic, reconciliation with the dashboard |
| `03 kpis and trends.sql` | `LAG` month-on-month growth, window totals |
| `04 cohort retention.sql` | Monthly cohorts, month offsets, 180-day repeat rate |
| `05 rfm segments.sql` | `NTILE` scoring, segment rules |
| `06 late delivery impact.sql` | Bucketing, `FILTER`, funnel, `RANK` of routes |
| `07 seller scorecard.sql` | `PARTITION BY`, `PERCENT_RANK`, watch list |

![Seller scorecard](images/sql%20seller%20scorecard.png)

## Run it
```bash
pip install -r requirements.txt
jupyter notebook "Olist SQL Analysis.ipynb"        # builds the database (DuckDB by default) and runs every .sql file
jupyter notebook "Olist Late Delivery Model.ipynb" # trains the model and exports it to app/
streamlit run app/app.py                           # the app, locally
```
**On PostgreSQL:** set `ENGINE = "postgres"` in the first cell of the SQL notebook (it asks for your password and creates the `olist` database),
then run any file in psql, e.g. `\i 'C:/path/to/sql/06 late delivery impact.sql'`.

The `data` folder holds the eight Kaggle files, compressed (`.csv.gz`, 28 MB). Data: Olist, CC BY-NC-SA 4.0.

## Files
```
Olist-Ecommerce/
├── Olist SQL Analysis.ipynb / .html         SQL layer, run from Python, with charts
├── Olist Deep Dive.ipynb / .html            Python deep dive (regression, NLP, retention)
├── Olist Late Delivery Model.ipynb / .html  LightGBM risk model, SHAP, export for the app
├── olistsql.py                              connect to DuckDB/PostgreSQL, load raw files, run .sql files
├── olisttools.py                            loading and text helpers for the deep dive
├── sql/                                     the seven .sql files
├── app/                                     Streamlit app: app.py, olistmodel.py, model/, appdata/
├── data/                                    Kaggle files (.csv.gz)
├── images/                                  charts and app screenshots
├── Power BI/                                dashboard template (.pbit)
├── requirements.txt · packages.txt
└── .streamlit/config.toml                   app theme
```
