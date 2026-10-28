"""Features and scoring for the Olist late-delivery model.

Shared by the model notebook (training) and the Streamlit app (scoring), so both build features the same way.
Only information known at the moment of purchase is used.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
MODEL_DIR = HERE / "model"
MODEL_FILE = MODEL_DIR / "late model.txt"
META_FILE = MODEL_DIR / "model meta.json"

# State capitals (lat, lon): distance between the seller's and the customer's state
CAPITALS = {"AC": (-9.97, -67.81), "AL": (-9.65, -35.73), "AP": (0.03, -51.07), "AM": (-3.12, -60.02), "BA": (-12.97, -38.50),
            "CE": (-3.73, -38.52), "DF": (-15.79, -47.88), "ES": (-20.32, -40.34), "GO": (-16.68, -49.25), "MA": (-2.53, -44.30),
            "MT": (-15.60, -56.10), "MS": (-20.44, -54.65), "MG": (-19.92, -43.94), "PA": (-1.46, -48.50), "PB": (-7.12, -34.86),
            "PR": (-25.43, -49.27), "PE": (-8.05, -34.88), "PI": (-5.09, -42.80), "RJ": (-22.91, -43.17), "RN": (-5.79, -35.21),
            "RS": (-30.03, -51.23), "RO": (-8.76, -63.90), "RR": (2.82, -60.67), "SC": (-27.60, -48.55), "SP": (-23.55, -46.63),
            "SE": (-10.91, -37.07), "TO": (-10.18, -48.33)}
STATE_NAMES = {"AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará", "DF": "Distrito Federal",
               "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
               "PA": "Pará", "PB": "Paraíba", "PR": "Paraná", "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro",
               "RN": "Rio Grande do Norte", "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina",
               "SP": "São Paulo", "SE": "Sergipe", "TO": "Tocantins"}

FEATURES = ["customer_state", "seller_state", "same_state", "distance_km", "promised_days", "month", "dow", "items", "sellers",
            "revenue", "freight", "freight_ratio", "weight_kg", "max_volume_l", "category", "seller_prior_orders", "seller_prior_late_rate"]
CATEGORICAL = ["customer_state", "seller_state", "category"]
LABELS = {"customer_state": "customer state", "seller_state": "seller state", "same_state": "same state", "distance_km": "distance (km)",
          "promised_days": "promised delivery days", "month": "purchase month", "dow": "purchase weekday", "items": "items in order",
          "sellers": "sellers in order", "revenue": "order value (R$)", "freight": "freight (R$)", "freight_ratio": "freight ÷ price",
          "weight_kg": "weight (kg)", "max_volume_l": "largest package (litres)", "category": "category",
          "seller_prior_orders": "seller's past deliveries", "seller_prior_late_rate": "seller's past late rate"}


def distance_km(a, b):
    if a not in CAPITALS or b not in CAPITALS:
        return np.nan
    (la1, lo1), (la2, lo2) = CAPITALS[a], CAPITALS[b]
    la1, lo1, la2, lo2 = map(np.radians, (la1, lo1, la2, lo2))
    h = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return float(6371 * 2 * np.arcsin(np.sqrt(h)))


def seller_history(orders):
    """For every order, the seller's deliveries completed before the purchase day: count and late rate.
    Uses merge_asof, so nothing after the purchase leaks into the features."""
    h = orders[["seller_id", "delivered_date", "is_late"]].dropna(subset=["seller_id", "delivered_date"]).copy()
    h["key"] = pd.to_datetime(h.delivered_date)
    h = h.sort_values("key")
    h["cum_n"] = h.groupby("seller_id").cumcount() + 1
    h["cum_late"] = h.groupby("seller_id").is_late.cumsum()
    q = orders[["order_id", "seller_id", "purchased_at"]].dropna(subset=["seller_id"]).copy()
    q["key"] = pd.to_datetime(q.purchased_at).dt.normalize() - pd.Timedelta(days=1)
    q = q.sort_values("key")
    m = pd.merge_asof(q, h[["seller_id", "key", "cum_n", "cum_late"]], on="key", by="seller_id", direction="backward")
    m["seller_prior_orders"] = m.cum_n.fillna(0)
    m["seller_prior_late_rate"] = (m.cum_late / m.cum_n).where(m.cum_n >= 5)   # too few deliveries -> unknown
    return m.set_index("order_id")[["seller_prior_orders", "seller_prior_late_rate"]]


def build_features(df, categories=None):
    """df needs: customer_state, seller_state, promised_days, purchased_at, items, sellers, revenue, freight,
    weight_kg, max_volume_l, category, seller_prior_orders, seller_prior_late_rate."""
    X = pd.DataFrame(index=df.index)
    X["customer_state"] = df.customer_state.astype(str)
    X["seller_state"] = df.seller_state.astype(str)
    X["same_state"] = (df.customer_state == df.seller_state).astype(float)
    X["distance_km"] = [distance_km(s, c) for s, c in zip(df.seller_state, df.customer_state)]
    X["promised_days"] = df.promised_days.astype(float)
    ts = pd.to_datetime(df.purchased_at)
    X["month"] = ts.dt.month.astype(float)
    X["dow"] = ts.dt.dayofweek.astype(float)
    X["items"] = df["items"].astype(float)
    X["sellers"] = df.sellers.astype(float)
    X["revenue"] = df.revenue.astype(float)
    X["freight"] = df.freight.astype(float)
    X["freight_ratio"] = X.freight / X.revenue.replace(0, np.nan)
    X["weight_kg"] = df.weight_kg.astype(float)
    X["max_volume_l"] = df.max_volume_l.astype(float)
    X["category"] = df.category.astype(str)
    X["seller_prior_orders"] = df.seller_prior_orders.astype(float)
    X["seller_prior_late_rate"] = df.seller_prior_late_rate.astype(float)
    if categories:
        for c in CATEGORICAL:
            levels = categories[c]
            vals = X[c].where(X[c].isin(levels), "other" if "other" in levels else levels[0])
            X[c] = pd.Categorical(vals, categories=levels)
    return X[FEATURES]


def load_model():
    import lightgbm as lgb
    booster = lgb.Booster(model_file=str(MODEL_FILE))
    meta = json.loads(META_FILE.read_text(encoding="utf-8"))
    return booster, meta


def score(booster, meta, df):
    """Probability of a late delivery and per-feature contributions (log-odds) for each row."""
    X = build_features(df, meta["categories"])
    p = booster.predict(X)
    contrib = booster.predict(X, pred_contrib=True)
    contrib = pd.DataFrame(contrib[:, :-1], columns=FEATURES, index=X.index)
    return p, contrib, X
