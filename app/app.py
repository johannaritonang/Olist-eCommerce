"""Olist Delivery Risk · Streamlit app

Three views on the Olist public e-commerce data (Brazil, 2017–2018):
  * Overview: KPIs, monthly trend and the rating cliff, with filters
  * Order risk checker: score a new order with the late-delivery model and see why
  * Seller scorecard: one seller against the platform

Run locally:  streamlit run app/app.py
"""
import datetime as dt
import sys
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import olistmodel as om   # noqa: E402

NAVY, BLUE, BLUE_L, AMBER, RED, GREEN, MUTED = "#0B2545", "#2563EB", "#BFD4F5", "#F59E0B", "#EF4444", "#10B981", "#64748B"
REGIONS = {"North": ["AC", "AP", "AM", "PA", "RO", "RR", "TO"], "Northeast": ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"],
           "Center-West": ["DF", "GO", "MT", "MS"], "Southeast": ["ES", "MG", "RJ", "SP"], "South": ["PR", "RS", "SC"]}
STATE_REGION = {s: r for r, ss in REGIONS.items() for s in ss}
REPO_URL = "https://github.com/johannaritonang/Olist-Ecommerce"

st.set_page_config(page_title="Olist Delivery Risk", page_icon="📦", layout="wide")


# ---------------------------------------------------------------- data
@st.cache_data
def load_orders():
    o = pd.read_parquet(HERE / "appdata" / "orders.parquet")
    o["purchase_date"] = pd.to_datetime(o.purchase_date)
    o["month"] = o.purchase_date.dt.to_period("M").dt.to_timestamp()
    o["region"] = o.customer_state.map(STATE_REGION)
    o["is_late"] = o.is_late.astype(bool)
    return o


@st.cache_data
def load_sellers():
    return pd.read_parquet(HERE / "appdata" / "sellers.parquet")


@st.cache_resource
def load_model():
    return om.load_model()


orders = load_orders()
sellers = load_sellers()
booster, meta = load_model()
PLATFORM_LATE = meta["platform_late_rate"]


def pct(v, d=1):
    return f"{v * 100:.{d}f}%"


def show_chart(where, chart):
    """Full-width Altair chart on both newer Streamlit (width="stretch") and older versions (use_container_width)."""
    try:
        where.altair_chart(chart, width="stretch")
    except TypeError:
        where.altair_chart(chart, use_container_width=True)


def timing_bucket(days_late):
    return pd.cut(days_late, [-999, -8, -1, 0, 3, 7, 14, 999],
                  labels=["8+ days early", "1–7 days early", "on the day", "1–3 days late", "4–7 days late", "8–14 days late", "15+ days late"])


# ---------------------------------------------------------------- sidebar
st.sidebar.title("📦 Olist Delivery Risk")
page = st.sidebar.radio("View", ["Overview", "Order risk checker", "Seller scorecard", "About"], label_visibility="collapsed")
st.sidebar.markdown("---")
st.sidebar.caption(f"Olist public data · {meta['trained_on']} · {meta['rows']:,} delivered orders")
st.sidebar.caption(f"[Code, SQL and notebooks on GitHub]({REPO_URL})")


# ---------------------------------------------------------------- overview
def page_overview():
    st.title("Overview")
    st.caption("Delivered orders from the Olist marketplace. Filter to see how lateness and ratings move together.")
    months = sorted(orders.month.unique())
    c1, c2, c3 = st.columns([2, 1.2, 1.8])
    start, end = c1.select_slider("Purchase month", options=months, value=(months[0], months[-1]),
                                  format_func=lambda m: pd.Timestamp(m).strftime("%b %Y"))
    regions = c2.multiselect("Customer region", list(REGIONS), placeholder="All regions")
    cats = c3.multiselect("Category", sorted(orders.category.dropna().unique()), placeholder="All categories")
    d = orders[(orders.month >= start) & (orders.month <= end)]
    if regions:
        d = d[d.region.isin(regions)]
    if cats:
        d = d[d.category.isin(cats)]
    if d.empty:
        st.info("No orders match these filters.")
        return

    k = st.columns(5)
    k[0].metric("Delivered orders", f"{len(d):,}")
    k[1].metric("Revenue", f"R$ {d.revenue.sum() / 1e6:,.2f}M")
    gap = (d.is_late.mean() - PLATFORM_LATE) * 100
    k[2].metric("Late", pct(d.is_late.mean()), delta=f"{gap:+.1f} pts vs all" if abs(gap) >= 0.05 else None, delta_color="inverse")
    k[3].metric("Average review", f"{d.review_score.mean():.2f} ★")
    k[4].metric("1–2★ reviews", pct((d.review_score <= 2).mean()))

    left, right = st.columns(2)
    m = d.groupby("month").agg(orders=("is_late", "size"), late=("is_late", "mean")).reset_index()
    base = alt.Chart(m).encode(x=alt.X("month:T", title=None, axis=alt.Axis(format="%b %y")))
    bars = base.mark_bar(color=BLUE_L).encode(y=alt.Y("orders:Q", title="orders"), tooltip=[alt.Tooltip("month:T", format="%b %Y"), "orders:Q"])
    line = base.mark_line(color=RED, point=alt.OverlayMarkDef(color=RED)).encode(y=alt.Y("late:Q", title="late %", axis=alt.Axis(format="%")),
                                                       tooltip=[alt.Tooltip("month:T", format="%b %Y"), alt.Tooltip("late:Q", format=".1%")])
    left.subheader("Orders and late rate by month")
    show_chart(left, alt.layer(bars, line).resolve_scale(y="independent").properties(height=300))

    t = d.assign(timing=timing_bucket(d.days_late)).groupby("timing", observed=False).agg(
        orders=("review_score", "size"), review=("review_score", "mean")).reset_index()
    t["late"] = t.timing.astype(str).str.contains("late")
    right.subheader("The rating cliff")
    show_chart(right, alt.Chart(t).mark_bar().encode(
        x=alt.X("timing:N", sort=None, title=None, axis=alt.Axis(labelAngle=-35, labelOverlap=False, labelLimit=140)),
        y=alt.Y("review:Q", title="average review", scale=alt.Scale(domain=[0, 5])),
        color=alt.condition("datum.late", alt.value(RED), alt.value(BLUE)),
        tooltip=["timing:N", alt.Tooltip("review:Q", format=".2f"), alt.Tooltip("orders:Q", format=",")]).properties(height=300))

    st.subheader("Late rate by customer state")
    s = d.groupby("customer_state").agg(orders=("is_late", "size"), late=("is_late", "mean"), review=("review_score", "mean")).reset_index()
    s = s[s.orders >= 30].sort_values("late", ascending=False)
    s["region"] = s.customer_state.map(STATE_REGION)
    show_chart(st, alt.Chart(s).mark_bar().encode(
        x=alt.X("customer_state:N", sort="-y", title=None),
        y=alt.Y("late:Q", title="late %", axis=alt.Axis(format="%")),
        color=alt.Color("region:N", scale=alt.Scale(domain=list(REGIONS), range=[AMBER, RED, "#8B5CF6", BLUE, GREEN]), legend=alt.Legend(orient="top")),
        tooltip=["customer_state:N", "region:N", alt.Tooltip("orders:Q", format=","), alt.Tooltip("late:Q", format=".1%"),
                 alt.Tooltip("review:Q", format=".2f")]).properties(height=260))
    st.caption("States with at least 30 orders in the selection.")


# ---------------------------------------------------------------- risk checker
def page_risk():
    st.title("Order risk checker")
    st.caption("Score an order at the moment of purchase. The model uses only what is known at checkout and was tested on six months it never saw "
               f"(ROC AUC {meta['test_metrics']['roc_auc']:.2f}).")
    dflt = meta["defaults"]
    states = sorted(om.CAPITALS)
    seller_list = sellers[sellers.deliveries >= 30].sort_values("deliveries", ascending=False)

    with st.form("order"):
        c1, c2, c3 = st.columns(3)
        customer_state = c1.selectbox("Customer state", states, index=states.index("BA"), format_func=lambda s: f"{s} · {om.STATE_NAMES[s]}")
        seller_mode = c2.radio("Seller", ["Existing seller", "New seller"], horizontal=True)
        if seller_mode == "Existing seller":
            sid = c2.selectbox("Seller (30+ deliveries)", seller_list.seller_id,
                               format_func=lambda x: f"{x[:8]}… · {seller_list.set_index('seller_id').loc[x, 'seller_state']} · "
                                                     f"{int(seller_list.set_index('seller_id').loc[x, 'deliveries'])} deliveries")
            row = seller_list.set_index("seller_id").loc[sid]
            seller_state, prior_orders, prior_late = row.seller_state, float(row.deliveries), float(row.late_rate)
        else:
            seller_state = c2.selectbox("Seller state", states, index=states.index("SP"), format_func=lambda s: f"{s} · {om.STATE_NAMES[s]}")
            prior_orders, prior_late = 0.0, np.nan
        category = c3.selectbox("Category", meta["categories"]["category"], index=meta["categories"]["category"].index("health_beauty")
                                if "health_beauty" in meta["categories"]["category"] else 0)
        purchase = c3.date_input("Purchase date", dt.date(2018, 8, 15))

        c4, c5, c6, c7 = st.columns(4)
        promised = c4.slider("Promised delivery (days)", 2, 60, int(round(dflt["promised_days"])))
        revenue = c5.number_input("Order value (R$)", 1.0, 5000.0, float(round(dflt["revenue"])), step=10.0)
        freight = c6.number_input("Freight (R$)", 0.0, 500.0, float(round(dflt["freight"], 1)), step=1.0)
        items = c7.number_input("Items", 1, 20, 1)
        c8, c9 = st.columns(2)
        weight = c8.slider("Total weight (kg)", 0.05, 30.0, float(round(dflt["weight_kg"], 2)))
        volume = c9.slider("Largest package (litres)", 0.1, 200.0, float(round(dflt["max_volume_l"], 1)))
        submitted = st.form_submit_button("Score this order", type="primary")

    order = pd.DataFrame([{"customer_state": customer_state, "seller_state": seller_state, "promised_days": promised,
                           "purchased_at": pd.Timestamp(purchase), "items": items, "sellers": 1, "revenue": revenue, "freight": freight,
                           "weight_kg": weight, "max_volume_l": volume, "category": category,
                           "seller_prior_orders": prior_orders, "seller_prior_late_rate": prior_late}])
    p, contrib, X = om.score(booster, meta, order)
    p = float(p[0])
    band = "High" if p >= meta["risk_bands"]["high"] else ("Medium" if p >= meta["risk_bands"]["low"] else "Low")
    low_review = p * meta["low_review_if_late"] + (1 - p) * meta["low_review_if_on_time"]

    k = st.columns(4)
    k[0].metric("Chance of arriving late", pct(p), delta=f"{(p - PLATFORM_LATE) * 100:+.1f} pts vs platform", delta_color="inverse")
    k[1].metric("Risk band", {"High": "🔴 High", "Medium": "🟠 Medium", "Low": "🟢 Low"}[band])
    k[2].metric("Chance of a 1–2★ review", pct(low_review))
    k[3].metric("Distance", f"{X.distance_km.iloc[0]:,.0f} km")
    st.caption(f"Risk bands: High = riskiest 10% of orders in the test period (≥ {pct(meta['risk_bands']['high'])}); "
               f"Low = safest half (< {pct(meta['risk_bands']['low'])}). The review chance uses the SQL funnel: "
               f"{pct(meta['low_review_if_late'], 0)} of late orders get 1–2★ against {pct(meta['low_review_if_on_time'], 0)} of on-time ones.")

    left, right = st.columns(2)
    c = contrib.iloc[0]
    shown = X.iloc[0]
    def label(f):
        v = shown[f]
        if f in ("customer_state", "seller_state", "category"):
            return f"{om.LABELS[f]} = {v}"
        if f == "seller_prior_late_rate":
            return f"{om.LABELS[f]} = {'unknown' if pd.isna(v) else pct(v)}"
        if f == "month":
            return f"{om.LABELS[f]} = {pd.Timestamp(2000, int(v), 1):%b}"
        if f == "dow":
            return f"{om.LABELS[f]} = {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][int(v)]}"
        return f"{om.LABELS[f]} = {v:,.1f}" if isinstance(v, float) and not float(v).is_integer() else f"{om.LABELS[f]} = {v:,.0f}"
    top = c.reindex(c.abs().sort_values(ascending=False).index).head(8)
    dd = pd.DataFrame({"driver": [label(f) for f in top.index], "effect": top.values})
    dd["direction"] = np.where(dd.effect > 0, "raises risk", "lowers risk")
    left.subheader("Why this score")
    show_chart(left, alt.Chart(dd).mark_bar().encode(
        x=alt.X("effect:Q", title="effect on risk (log-odds)"),
        y=alt.Y("driver:N", sort=None, title=None, axis=alt.Axis(labelLimit=320, labelOverlap=False)),
        color=alt.Color("direction:N", scale=alt.Scale(domain=["raises risk", "lowers risk"], range=[RED, BLUE]), legend=alt.Legend(orient="bottom")),
        tooltip=["driver:N", alt.Tooltip("effect:Q", format="+.2f")]).properties(height=300))

    # what if the promise were longer?
    grid = pd.concat([order.assign(promised_days=d) for d in range(2, 61)], ignore_index=True)
    pg, _, _ = om.score(booster, meta, grid)
    curve = pd.DataFrame({"promised days": range(2, 61), "late chance": pg})
    safe = curve[curve["late chance"] <= PLATFORM_LATE]
    right.subheader("What if the promise were longer?")
    chart = alt.Chart(curve).mark_line(color=NAVY).encode(x="promised days:Q", y=alt.Y("late chance:Q", title="late chance", axis=alt.Axis(format="%")),
                                                         tooltip=["promised days:Q", alt.Tooltip("late chance:Q", format=".1%")])
    now = alt.Chart(pd.DataFrame({"promised days": [promised], "late chance": [p]})).mark_point(color=RED, size=120, filled=True).encode(
        x="promised days:Q", y="late chance:Q")
    rule = alt.Chart(pd.DataFrame({"y": [PLATFORM_LATE]})).mark_rule(color=MUTED, strokeDash=[4, 4]).encode(y=alt.Y("y:Q", title="late chance"))
    show_chart(right, (chart + now + rule).properties(height=300))
    if p > PLATFORM_LATE and not safe.empty:
        right.info(f"Promising **{int(safe['promised days'].iloc[0])} days** instead of {promised} would bring this order to the platform average "
                   f"({pct(PLATFORM_LATE)}).")
    elif p > PLATFORM_LATE:
        right.warning("Even a 60-day promise keeps this order above the platform average: consider another seller or carrier.")
    else:
        right.success("This order is at or below the platform's average late risk.")


# ---------------------------------------------------------------- seller scorecard
def page_seller():
    st.title("Seller scorecard")
    st.caption("Every seller with at least 30 delivered orders, compared with the whole platform.")
    s30 = sellers[sellers.deliveries >= 30].copy()
    stats = (orders.dropna(subset=["seller_id"]).groupby("seller_id")
             .agg(review=("review_score", "mean"), low=("review_score", lambda x: (x <= 2).mean()), revenue=("revenue", "sum"),
                  states=("customer_state", "nunique")))
    s30 = s30.join(stats, on="seller_id")
    s30["late_pct_rank"] = s30.late_rate.rank(pct=True)
    s30["watch"] = (s30.deliveries >= 50) & (s30.late_rate >= 2 * PLATFORM_LATE)
    c1, c2 = st.columns([2, 1])
    only_watch = c2.toggle("Watch list only", value=False, help="50+ orders and late at least twice as often as the platform")
    pool = s30[s30.watch] if only_watch else s30
    pool = pool.sort_values("deliveries", ascending=False)
    sid = c1.selectbox(f"Seller ({len(pool)})", pool.seller_id,
                       format_func=lambda x: f"{x[:8]}… · {pool.set_index('seller_id').loc[x, 'seller_state']} · "
                                             f"{int(pool.set_index('seller_id').loc[x, 'deliveries'])} deliveries"
                                             + (" · ⚠ watch list" if pool.set_index('seller_id').loc[x, 'watch'] else ""))
    r = s30.set_index("seller_id").loc[sid]
    so = orders[orders.seller_id == sid]

    k = st.columns(5)
    k[0].metric("Deliveries", f"{int(r.deliveries):,}")
    k[1].metric("Late rate", pct(r.late_rate), delta=f"{(r.late_rate - PLATFORM_LATE) * 100:+.1f} pts vs platform", delta_color="inverse")
    k[2].metric("Average review", f"{r.review:.2f} ★", delta=f"{r.review - orders.review_score.mean():+.2f} vs platform")
    k[3].metric("Late-rate percentile", f"{r.late_pct_rank * 100:.0f}th", help="Share of scored sellers with a lower late rate (100th = latest).")
    k[4].metric("Status", "⚠ Watch list" if r.watch else "OK")

    left, right = st.columns(2)
    m = so.groupby("month").agg(orders=("is_late", "size"), late=("is_late", "mean")).reset_index()
    left.subheader("Monthly late rate")
    line = alt.Chart(m).mark_line(color=RED, point=alt.OverlayMarkDef(color=RED)).encode(
        x=alt.X("month:T", title=None, axis=alt.Axis(format="%b %y")), y=alt.Y("late:Q", title="late %", axis=alt.Axis(format="%")),
        tooltip=[alt.Tooltip("month:T", format="%b %Y"), "orders:Q", alt.Tooltip("late:Q", format=".1%")])
    rule = alt.Chart(pd.DataFrame({"y": [PLATFORM_LATE]})).mark_rule(color=MUTED, strokeDash=[4, 4]).encode(y=alt.Y("y:Q", title="late %"))
    show_chart(left, (line + rule).properties(height=280))
    left.caption("Dashed line: platform average.")

    dest = so.groupby("customer_state").agg(orders=("is_late", "size"), late=("is_late", "mean")).reset_index().sort_values("orders", ascending=False).head(10)
    right.subheader("Where this seller ships")
    show_chart(right, alt.Chart(dest).mark_bar().encode(
        x=alt.X("orders:Q"), y=alt.Y("customer_state:N", sort="-x", title=None),
        color=alt.Color("late:Q", title="late %", scale=alt.Scale(scheme="reds"), legend=alt.Legend(format="%")),
        tooltip=["customer_state:N", "orders:Q", alt.Tooltip("late:Q", format=".1%")]).properties(height=280))

    st.subheader("All scored sellers")
    chart = alt.Chart(s30).mark_circle(opacity=0.6).encode(
        x=alt.X("late_rate:Q", title="late rate", axis=alt.Axis(format="%")), y=alt.Y("review:Q", title="average review", scale=alt.Scale(zero=False)),
        size=alt.Size("deliveries:Q", legend=None), color=alt.condition("datum.watch", alt.value(RED), alt.value(BLUE_L)),
        tooltip=[alt.Tooltip("seller_id:N"), "seller_state:N", "deliveries:Q", alt.Tooltip("late_rate:Q", format=".1%"), alt.Tooltip("review:Q", format=".2f")])
    me = alt.Chart(s30[s30.seller_id == sid]).mark_point(color=NAVY, size=300, strokeWidth=3).encode(x="late_rate:Q", y="review:Q")
    show_chart(st, (chart + me).properties(height=320))
    st.caption(f"Red = watch list ({int(s30.watch.sum())} sellers). The circled point is the selected seller.")


# ---------------------------------------------------------------- about
def page_about():
    st.title("About")
    tm = meta["test_metrics"]
    st.markdown(f"""
This app is the last layer of an end-to-end portfolio project on the
[Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (CC BY-NC-SA 4.0).

| Layer | What it does |
|---|---|
| **Power BI** | Dashboard of sales, delivery and reviews |
| **SQL** (PostgreSQL / DuckDB) | Clean tables, cohorts, RFM, late-delivery funnel, seller scorecard |
| **Python deep dive** | What lateness costs in ratings, complaint topics, retention |
| **Risk model** (LightGBM) | Late-delivery risk at purchase, explained with SHAP |
| **This app** (Streamlit) | Explore the data, score an order, review a seller |

**The model** uses only what is known at checkout: states and distance, the promised delivery time, basket value, freight, weight and size, category,
the season and the seller's track record up to that day. Trained on Jan 2017 – Feb 2018 and tested on Mar – Aug 2018:
ROC AUC **{tm['roc_auc']:.2f}**, and the riskiest 10% of orders hold **{tm['late_caught_top10']:.0%}** of late ones (base rate {tm['test_late_rate']:.1%}).
The model shipped here is retrained on all months.

**Limits:** only delivered orders have a known outcome; carrier, weather and strike data are not available; distance is between state capitals.

[Code, SQL and notebooks on GitHub]({REPO_URL})
""")


{"Overview": page_overview, "Order risk checker": page_risk, "Seller scorecard": page_seller, "About": page_about}[page]()
