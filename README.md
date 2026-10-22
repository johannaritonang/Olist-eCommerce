# The Cost of a Late Box · Olist deep dive

Python companion to the Power BI report *Olist e-commerce* (Brazil, Jan 2017 – Aug 2018).
The dashboard shows that late orders score 2.3★ against 4.3★ and that only 3% of customers order twice. This notebook explains why.

| Question | Method |
|---|---|
| How much does lateness itself cost? | Rating by delivery timing; OLS with robust (HC1) errors controlling for value, freight, items, multi-seller, distance, delivery days, category, state and month |
| What do unhappy customers write? | Portuguese text normalisation, TF-IDF (words and pairs) + NMF topics on 9,194 negative reviews, hand-translated examples |
| Why do fulfilment complaints appear on "on time" orders? | Review timing vs delivery date; multi-item share per complaint topic |
| Does a bad first order explain low retention? | 180-day repeat with full follow-up, logistic regression with controls, Kaplan–Meier time to second order |
| Who is worth winning back? | Recency × Monetary segmentation (Frequency is 1 for 97% of customers) |
| What would fixing lateness be worth? | Counterfactual re-scoring with the controlled effects |

## Headline results
* Lateness is a cliff: early delivery adds nothing, while 4–7 days late costs about 1.9★ even with controls.
* 66% of negative reviews are fulfilment complaints. 27% were written before the parcel arrived, and partial deliveries come mostly from multi-item orders.
* A late first order does not significantly reduce repeat buying (odds ratio 0.90, p = 0.46). Retention is structurally low.
* Fixing lateness would remove about 3,400 of 12,228 1–2★ reviews. The hot spots are Feb–Mar 2018, Black Friday and the North-East states.

## Run it
```bash
pip install -r requirements.txt
jupyter notebook "Olist Deep Dive.ipynb"
```
Put the Olist CSV files from Kaggle ([Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)) in the data folder.
The first cell also looks one level up and in the Power BI data folder, and `DATA_OVERRIDE` takes any other folder. Every chart is saved to the images folder.

## Files
```
Olist Deep Dive/
├── Olist Deep Dive.ipynb      the analysis, with outputs
├── Olist Deep Dive.html       the same notebook as a static page
├── olisttools.py              loading (same rules as the Power BI model), retention helper, Portuguese text tools
├── requirements.txt
├── data/                      Olist CSVs (not included, download from Kaggle)
├── images/                    key charts as PNG
└── powerbi/
    └── Olist Ecommerce Portfolio.pbit   companion Power BI report with DAX-driven insight text
```
