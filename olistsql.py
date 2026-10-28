"""Run the SQL layer of the Olist project on DuckDB (no server needed) or PostgreSQL.

    con = connect("duckdb")                                   # creates olist.duckdb next to this file
    con = connect("postgres", password=..., dbname="olist")   # your local PostgreSQL
    load_raw(con, data_folder)                                # loads the 8 Kaggle files into raw_* tables
    results = run_file(con, "sql/02 clean orders.sql")        # runs every statement, returns the SELECT results

The same .sql files can be run in psql (SQL Shell) with \\i, see README.
"""
import io
import re
from decimal import Decimal
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
SQL = HERE / "sql"

# Kaggle file -> raw table. Matched loosely (letters only), so "olist_orders_dataset.csv",
# "olist orders dataset.csv.gz" and similar names all work.
FILES = {"olistordersdataset": "raw_orders", "olistcustomersdataset": "raw_customers",
         "olistorderitemsdataset": "raw_order_items", "olistorderpaymentsdataset": "raw_order_payments",
         "olistorderreviewsdataset": "raw_order_reviews", "olistproductsdataset": "raw_products",
         "olistsellersdataset": "raw_sellers", "productcategorynametranslation": "raw_category_translation"}


def _key(name):
    return re.sub(r"[^a-z]", "", re.sub(r"\.csv(\.gz)?$", "", name.lower()))


def find_files(folder):
    folder = Path(folder)
    found = {}
    for f in sorted(folder.iterdir()) if folder.exists() else []:
        if f.name.lower().endswith((".csv", ".csv.gz")) and _key(f.name) in FILES:
            found.setdefault(FILES[_key(f.name)], f)
    return found


class Connection:
    """Thin wrapper so DuckDB and PostgreSQL look the same to the notebook."""

    def __init__(self, engine, raw):
        self.engine, self.raw = engine, raw

    def execute(self, statement):
        """Run one statement. Returns a DataFrame for queries that return rows, else None."""
        if self.engine == "duckdb":
            rel = self.raw.execute(statement)
            return rel.fetchdf() if rel.description else None
        with self.raw.cursor() as cur:
            cur.execute(statement)
            if cur.description:
                cols = [c[0] for c in cur.description]
                df = pd.DataFrame(cur.fetchall(), columns=cols)
                for c in df.columns:   # NUMERIC comes back as Decimal: make it a normal number
                    if df[c].map(lambda v: isinstance(v, Decimal)).any():
                        df[c] = pd.to_numeric(df[c].map(lambda v: float(v) if isinstance(v, Decimal) else v))
                return df
        return None

    def query(self, statement):
        return self.execute(statement)

    def close(self):
        self.raw.close()


def connect(engine="duckdb", path=None, host="localhost", port=5432, user="postgres", password=None, dbname="olist"):
    if engine == "duckdb":
        import duckdb
        return Connection("duckdb", duckdb.connect(str(path or HERE / "olist.duckdb")))
    if engine == "postgres":
        import psycopg2
        # create the database the first time
        admin = psycopg2.connect(host=host, port=port, user=user, password=password, dbname="postgres")
        admin.autocommit = True
        with admin.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
            if cur.fetchone() is None:
                cur.execute(f'CREATE DATABASE "{dbname}"')
        admin.close()
        raw = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname)
        raw.autocommit = True
        return Connection("postgres", raw)
    raise ValueError("engine must be 'duckdb' or 'postgres'")


def split_statements(sql):
    """Split a script on semicolons, ignoring those inside quotes or comments. psql meta-commands (\\...) are skipped."""
    out, buf, i, n = [], [], 0, len(sql)
    quote = None
    while i < n:
        ch = sql[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
        elif sql.startswith("--", i):
            j = sql.find("\n", i)
            j = n if j == -1 else j
            buf.append(sql[i:j]); i = j; continue
        elif sql.startswith("/*", i):
            j = sql.find("*/", i)
            j = n if j == -1 else j + 2
            i = j; continue
        elif ch in ("'", '"'):
            quote = ch; buf.append(ch)
        elif ch == ";":
            out.append("".join(buf)); buf = []
        else:
            buf.append(ch)
        i += 1
    out.append("".join(buf))
    clean = []
    for s in out:
        lines = [l for l in s.splitlines() if not l.strip().startswith("\\")]
        body = "\n".join(lines).strip()
        if re.sub(r"--[^\n]*", "", body).strip():
            clean.append(body)
    return clean


def run_file(con, path):
    """Run every statement in a .sql file. Returns {result name: DataFrame} for the SELECTs, named by the
    '-- result: <name>' comment just above them (else 'result 1', 'result 2', ...)."""
    path = Path(path)
    if not path.is_absolute() and not path.exists():
        path = HERE / path
    results = {}
    for k, stmt in enumerate(split_statements(path.read_text(encoding="utf-8")), 1):
        m = re.search(r"--\s*result:\s*(.+)", stmt)
        df = con.execute(stmt)
        code = re.sub(r"--[^\n]*", "", stmt).strip().upper()
        if df is not None and code.startswith(("SELECT", "WITH")):
            results[m.group(1).strip() if m else f"result {len(results) + 1}"] = df
    return results


def load_raw(con, folder, verbose=True):
    """Create the raw tables (sql/01) and load the Kaggle files into them."""
    files = find_files(folder)
    missing = sorted(set(FILES.values()) - set(files))
    if missing:
        raise FileNotFoundError(f"Missing files for {missing} in {folder}")
    run_file(con, SQL / "01 raw tables.sql")
    for table, f in files.items():
        cols = list(con.execute(f"SELECT * FROM {table} LIMIT 0").columns)
        df = pd.read_csv(f, dtype=str, keep_default_na=False, na_values=[""])
        df = df[cols]
        if con.engine == "duckdb":
            con.raw.register("incoming", df)
            con.raw.execute(f"INSERT INTO {table} SELECT * FROM incoming")
            con.raw.unregister("incoming")
        else:
            buf = io.StringIO()
            df.to_csv(buf, index=False, header=False)
            buf.seek(0)
            with con.raw.cursor() as cur:
                cur.copy_expert(f"COPY {table} FROM STDIN WITH (FORMAT csv)", buf)
        if verbose:
            print(f"{table:<26} {len(df):>8,} rows  <- {f.name}")
    con.execute("ANALYZE")   # fresh statistics, so PostgreSQL picks fast join plans


def table_exists(con, name):
    if con.engine == "duckdb":
        q = f"SELECT COUNT(*) AS n FROM information_schema.tables WHERE table_name = '{name}'"
    else:
        q = f"SELECT COUNT(*) AS n FROM information_schema.tables WHERE table_name = '{name}' AND table_schema = 'public'"
    return int(con.execute(q).n.iloc[0]) > 0
