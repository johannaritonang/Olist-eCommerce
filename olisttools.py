"""Helpers for the Olist deep-dive notebook.

Loading follows exactly the same rules as the Power BI model, so every number here reconciles with the dashboard:
purchase window Jan 2017 – Aug 2018, delivered orders only, revenue = item price (freight excluded),
late = delivered (date) after the estimated delivery date, customers = customer_unique_id.
"""
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- palette (matches the Power BI report)
NAVY, BLUE, AMBER, GREEN, RED, PURPLE, CYAN, INK, MUTED, LINE = (
    "#0B2545", "#2563EB", "#F59E0B", "#10B981", "#EF4444", "#8B5CF6", "#06B6D4", "#0F172A", "#64748B", "#E2E8F0")
BLUE_L, RED_L = "#BFD4F5", "#FCA5A5"


def style_charts():
    import matplotlib.pyplot as plt
    plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#CBD5E1",
                         "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlecolor": INK, "axes.labelcolor": MUTED,
                         "xtick.color": MUTED, "ytick.color": MUTED, "figure.facecolor": "white", "axes.facecolor": "white",
                         "font.family": "DejaVu Sans"})


# ---------------------------------------------------------------- files
# Kaggle file names, matched loosely (letters and digits only) so renamed copies still work
FILES = {"orders": "olistordersdataset", "customers": "olistcustomersdataset", "items": "olistorderitemsdataset",
         "reviews": "olistorderreviewsdataset", "products": "olistproductsdataset", "sellers": "olistsellersdataset",
         "payments": "olistorderpaymentsdataset", "categories": "productcategorynametranslation"}


def _key(name):
    name = re.sub(r"\.csv(\.gz)?$", "", name.lower())
    return re.sub(r"[^a-z0-9]", "", name)


def find_files(folder):
    """Map each dataset to its file inside `folder` (or None). Accepts .csv and gzipped .csv.gz."""
    folder = Path(folder)
    found = {}
    files = [f for f in folder.iterdir() if f.name.lower().endswith((".csv", ".csv.gz"))] if folder.exists() else []
    for k, stem in FILES.items():
        hits = sorted((f for f in files if _key(f.name) == stem), key=lambda f: f.name.endswith(".gz"))
        found[k] = hits[0] if hits else None
    return found


def has_olist(folder):
    f = find_files(folder)
    return all(f[k] is not None for k in ("orders", "customers", "items", "reviews"))


# ---------------------------------------------------------------- loading
STATE_REGION = {"AC": "North", "AP": "North", "AM": "North", "PA": "North", "RO": "North", "RR": "North", "TO": "North",
                "AL": "Northeast", "BA": "Northeast", "CE": "Northeast", "MA": "Northeast", "PB": "Northeast", "PE": "Northeast",
                "PI": "Northeast", "RN": "Northeast", "SE": "Northeast", "DF": "Center-West", "GO": "Center-West",
                "MT": "Center-West", "MS": "Center-West", "ES": "Southeast", "MG": "Southeast", "RJ": "Southeast",
                "SP": "Southeast", "PR": "South", "RS": "South", "SC": "South"}


def load(folder):
    """Returns (orders, items, reviews). `orders` = delivered orders in the window, one row per order with features."""
    f = find_files(folder)
    dates = ["order_purchase_timestamp", "order_delivered_customer_date", "order_estimated_delivery_date"]
    o = pd.read_csv(f["orders"], parse_dates=dates)
    c = pd.read_csv(f["customers"])
    it = pd.read_csv(f["items"])
    rv = pd.read_csv(f["reviews"], parse_dates=["review_creation_date"])
    s = pd.read_csv(f["sellers"]) if f["sellers"] else None
    p = pd.read_csv(f["products"]) if f["products"] else None
    tr = pd.read_csv(f["categories"]) if f["categories"] else None

    o = o[(o.order_purchase_timestamp >= "2017-01-01") & (o.order_purchase_timestamp < "2018-09-01")].merge(c, on="customer_id", how="left")
    d = o[(o.order_status == "delivered") & o.order_delivered_customer_date.notna()].copy()
    d["purchase_day"] = d.order_purchase_timestamp.dt.normalize()
    d["delivered_day"] = d.order_delivered_customer_date.dt.normalize()
    d["estimated_day"] = d.order_estimated_delivery_date.dt.normalize()
    d["late"] = d.delivered_day > d.estimated_day
    d["days_late"] = (d.delivered_day - d.estimated_day).dt.days            # negative = early
    d["delivery_days"] = (d.delivered_day - d.purchase_day).dt.days
    d["promised_days"] = (d.estimated_day - d.purchase_day).dt.days
    d["region"] = d.customer_state.map(STATE_REGION)
    d["month"] = d.order_purchase_timestamp.dt.to_period("M")

    # one review per order: the latest answer (same rule as the dashboard's review table)
    rv = rv.sort_values("review_answer_timestamp").drop_duplicates("order_id", keep="last")
    d = d.merge(rv[["order_id", "review_score", "review_comment_title", "review_comment_message", "review_creation_date"]], on="order_id", how="left")
    d["review_before_arrival"] = d.review_creation_date < d.delivered_day

    if p is not None and tr is not None:
        p = p.merge(tr, on="product_category_name", how="left")
        p["category"] = p.product_category_name_english.fillna(p.product_category_name).fillna("unknown").str.replace("_", " ")
        it = it.merge(p[["product_id", "category"]], on="product_id", how="left")
    else:
        it["category"] = "unknown"
    if s is not None:
        it = it.merge(s[["seller_id", "seller_state"]], on="seller_id", how="left")
    agg = it.groupby("order_id").agg(revenue=("price", "sum"), freight=("freight_value", "sum"), items=("order_item_id", "count"),
                                     sellers=("seller_id", "nunique"), category=("category", "first"),
                                     seller_state=("seller_state", "first") if s is not None else ("seller_id", "first"))
    d = d.merge(agg, on="order_id", how="left")
    d["multi_seller"] = d.sellers > 1
    d["same_state"] = d.seller_state == d.customer_state
    d["freight_ratio"] = d.freight / d.revenue
    return d, it, rv


def first_orders(d, horizon=180, cutoff="2018-03-01"):
    """First delivered order per customer, with the gap (days) to their next order on a different day.
    Only customers whose first order is before `cutoff` get a full `horizon`-day follow-up (data ends 31 Aug 2018)."""
    d = d.sort_values("order_purchase_timestamp")
    days = d.groupby("customer_unique_id").purchase_day.agg(lambda x: sorted(set(x)))
    first = d.groupby("customer_unique_id").head(1).copy()
    first["next_day"] = first.customer_unique_id.map(lambda u: days[u][1] if len(days[u]) > 1 else pd.NaT)
    first["gap"] = (first.next_day - first.purchase_day).dt.days
    first["followup"] = (pd.Timestamp("2018-08-31") - first.purchase_day).dt.days
    first["eligible"] = first.purchase_day < pd.Timestamp(cutoff)
    first["repeat"] = first.gap.le(horizon)
    return first


# ---------------------------------------------------------------- Portuguese text
PT_STOPWORDS = set("""a o e é de da do das dos em no na nos nas um uma uns umas para pra por com sem que se mais muito muita já ja foi ser ter tem
    tinha estava está esta este esse essa isso isto até ate ao aos às as os eu me meu minha meus minhas você voce vocês ele ela eles elas nós nos
    lhe seu sua seus suas mas ou quando como porque pois só so ainda também tambem bem mesmo então entao pelo pela pelos pelas sobre entre após
    apos dia dias hoje agora porém porem qual quais quem onde aqui lá la todo toda todos todas outro outra cada vez vezes sim fiz fez estou estão
    estao foram era são sao seria sendo sido há ha havia nem tão tao algum alguma nenhum nenhuma pouco produto produtos compra comprei loja
    lannister ok""".split())   # "não" is kept on purpose: it carries meaning in complaints ("não recebi")


def normalise_pt(text):
    t = unicodedata.normalize("NFKD", str(text).lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"[^a-z ]", " ", t)


PT_STOP_NORMALISED = sorted({normalise_pt(w).strip() for w in PT_STOPWORDS} - {"nao"})

# English glosses for the Portuguese words that show up in charts and tables
GLOSS = {"recebi": "received", "momento": "moment (so far)", "mercadoria": "goods", "avaliar": "rate", "errado": "wrong", "apenas": "only",
         "entregue": "delivered", "consta": "shows as", "pedido": "order", "site": "website", "chegou": "arrived", "prazo": "deadline",
         "quebrado": "broken", "nunca": "never", "veio": "came", "defeito": "defect", "pedi": "I ordered", "faltando": "missing",
         "cor": "colour", "troca": "exchange", "entrega": "delivery", "demora": "delay", "atraso": "late", "passou": "passed",
         "data": "date", "nada": "nothing", "dois": "two", "duas": "two", "unidades": "units", "nota": "invoice", "fiscal": "(tax)",
         "quero": "I want", "qualidade": "quality", "pessima": "terrible", "gostei": "liked", "recomendo": "recommend", "ruim": "bad",
         "material": "material", "baixa": "low", "foto": "photo", "aguardando": "waiting", "retorno": "reply", "resposta": "answer",
         "contato": "contact", "devolucao": "return", "nao": "not", "ainda": "still", "antes": "before", "posso": "can I"}


def gloss(term):
    words = term.split()
    return term + "  (" + " ".join(GLOSS.get(w, w) for w in words) + ")" if any(w in GLOSS for w in words) else term
