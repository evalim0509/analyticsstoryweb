"""The data catalogue: what Gist needs, matched to what the owner's files call it.

The owner (or a saved catalogue such as "Accounting") says, for example, that
"Customer" is called "Client Number" in their files. Gist then uses that column for
Who, Which, margin, dates and targets. Stories keep the owner's own column names.
Only the matches (column names) are held here, never data."""
import re
from . import store

NEEDS = [
    ("date", "Date", "When it happened", re.compile(r"date|posted|period|month|day", re.I), "date"),
    ("sales", "Sales amount", "The money from sales", re.compile(r"net total|sales|revenue|turnover|line amount|amount|total|income", re.I), "number"),
    ("qty", "Quantity", "How many units", re.compile(r"\bqty\b|quantity|units|volume", re.I), "number"),
    ("cost", "Cost", "What it cost (total, or per unit)", re.compile(r"\bcost|cogs|expense|purchase", re.I), "number"),
    ("customer", "Customer", "Who bought", re.compile(r"customer|client|debtor|contact|company name|buyer|account name|business partner|customer/vendor name", re.I), "text"),
    ("product", "Product", "What was sold", re.compile(r"product|item|sku|service|description", re.I), "text"),
    ("order", "Order or invoice number", "One number per order or invoice", re.compile(r"order|invoice|doc\.? ?no|document number|receipt|transaction|\bnum\b|\bref", re.I), "any"),
    ("region", "Region or branch", "Where it happened", re.compile(r"region|branch|area|state|country|territory|store|location|outlet", re.I), "text"),
    ("rep", "Salesperson", "Who sold it", re.compile(r"sales ?rep|salesperson|sales ?person|agent|account manager|regional manager|staff|owner", re.I), "text"),
    ("target", "Target or budget", "What was planned", re.compile(r"target|budget|plan|goal|quota", re.I), "number"),
]
NOT_SALES = re.compile(r"cost|price|unit|discount|tax|gst|vat|sst|%|balance|paid|due", re.I)
WORDS = {"date": "date", "sales": "sales", "qty": "quantity", "cost": "cost", "customer": "customer", "product": "product",
         "order": "order", "region": "region", "rep": "salesperson", "target": "target"}

ROLES = {}        # need key -> {"table": dataset id, "column": name}, as confirmed by the owner


def role(key, ds=None):
    """The column the owner matched to this need. With a table given, the name of that column inside it
    (a combined table may show a linked table's column as "Amount (Customers)"), or None if it is not there."""
    r = ROLES.get(key)
    if not r:
        return None
    if ds is None:
        return r["column"]
    names = {c["name"] for c in ds["columns"]}
    if ds["id"] == r["table"] or ds.get("base") == r["table"]:
        return r["column"] if r["column"] in names else None
    if ds.get("kind") == "linked":
        for part in ds.get("parts", []):
            link = next((l for l in store.LINKS if l["id"] == part["link"]), None)
            if link and link["b"] == r["table"]:
                alt = f"{r['column']} ({store.DATASETS[r['table']]['name']})"
                return alt if alt in names else (r["column"] if r["column"] in names and r["column"] not in
                                                 {c["name"] for c in store.DATASETS[ds["base"]]["columns"]} else None)
    return None


def _tables():
    return [d for d in store.DATASETS.values() if d["kind"] == "table"]


def columns():
    return [{"dataset": d["id"], "table": d["name"], "name": c["name"], "type": c["type"]} for d in _tables() for c in d["columns"]]


def guess():
    """Gist's best guess for each need, from the column names and what they hold."""
    out, used = {}, set()
    cols = [(d, c) for d in _tables() for c in d["columns"]]
    for key, _, _, pattern, typ in NEEDS:
        best, score = None, 0
        for d, c in cols:
            n = c["name"]
            if not pattern.search(n) or n in used:
                continue
            if typ == "date" and c["type"] != "date":
                continue
            if typ == "number" and (c["type"] != "number" or c["role"] == "id"):
                continue
            if typ == "text" and c["type"] == "number":
                continue
            if key == "sales" and NOT_SALES.search(n):
                continue
            s = 1 + (2 if typ != "any" or c["role"] == "id" else 0) + (1 if key in ("customer", "product", "rep") and re.search(r"name|description", n, re.I) else 0) \
                + (1 if d["rows"] == max(x["rows"] for x in _tables()) else 0) + (2 if key == "sales" and re.search(r"line amount|row total|sales amount|net amount|line total", n, re.I) else 0) - (1 if re.search(r"code|no\.?$|id$", n, re.I) and key in ("customer", "product") else 0)
            if score < s:
                best, score, best_table = n, s, d["id"]
        if best:
            out[key] = {"table": best_table, "column": best}
            used.add(best)
    return out


def needs():
    return [{"key": k, "label": label, "hint": hint} for k, label, hint, _, _ in NEEDS]


def set_roles(roles):
    """roles: {need: {"table": dataset id, "column": name}}. A bare column name is matched to the first table that has it."""
    ROLES.clear()
    cols = columns()
    for k, v in (roles or {}).items():
        if not v or k not in WORDS:
            continue
        if isinstance(v, str):
            v = next(({"table": c["dataset"], "column": c["name"]} for c in cols if c["name"] == v), None)
        if v and any(c["dataset"] == v.get("table") and c["name"] == v.get("column") for c in cols):
            ROLES[k] = {"table": v["table"], "column": v["column"]}
    return dict(ROLES)


def date_orders():
    """Date columns whose day/month order cannot be told from the file."""
    out = []
    for d in _tables():
        for col, o in (d.get("date_orders") or {}).items():
            if o.get("ambiguous") and any(c["name"] == col for c in d["columns"]):
                ex = store.scalar(f"SELECT {store.q(col)} FROM {store.q(d['table'])} WHERE {store.q(col)} IS NOT NULL LIMIT 1")
                out.append({"dataset": d["id"], "table": d["name"], "column": col, "order": o["order"], "example": ex})
    return out


def set_order(dataset, column, order):
    """Read an ambiguous date column the other way round (03/04 as 4 March instead of 3 April)."""
    d = store.DATASETS[dataset]
    o = (d.get("date_orders") or {}).get(column)
    if not o or not o.get("ambiguous") or order not in ("dmy", "mdy") or o["order"] == order:
        return
    c = store.q(column)
    for t in (d["table"], d["table"] + "_orig"):
        store.DB.execute(f"UPDATE {store.q(t)} SET {c} = substr({c}, 1, 5) || substr({c}, 9, 2) || '-' || substr({c}, 6, 2) WHERE {c} IS NOT NULL AND length({c}) >= 10")
    store.DB.commit()
    o["order"] = order
    store.LOG.append({"text": f"{column} in {d['name']} is now read as {'day/month' if order == 'dmy' else 'month/day'}.", "dataset": dataset})
    _refresh_all()


def combine_dates(dataset, primary, fallback):
    """For messy files where the date is sometimes in one column and sometimes in another: a new column that
    takes the first column, and the second where the first is blank. Returns its name."""
    from . import joins
    d = store.DATASETS[dataset]
    have = {c["name"] for c in d["columns"]}
    if primary not in have or fallback not in have or primary == fallback:
        return primary
    name = f"{primary} or {fallback}"
    for t in (d["table"], d["table"] + "_orig"):
        cols = {r[1] for r in store.rows(f"PRAGMA table_info({store.q(t)})")}
        if name not in cols:
            store.DB.execute(f"ALTER TABLE {store.q(t)} ADD COLUMN {store.q(name)}")
        store.DB.execute(f"UPDATE {store.q(t)} SET {store.q(name)} = COALESCE({store.q(primary)}, {store.q(fallback)})")
    store.DB.commit()
    if name not in have:
        d["columns"].append({"name": name})
    d.setdefault("combined", {})[name] = [primary, fallback]
    store.refresh(dataset)
    if any(x.get("base") == dataset for x in store.DATASETS.values()):
        joins._rebuild(dataset)
    return name


def _refresh_all():
    for x in list(store.DATASETS):
        store.refresh(x)


def nets():
    """Tables with a Net amount made from Debit and Credit, and which side counts as positive."""
    return [{"dataset": d["id"], "table": d["name"], **d["net"]} for d in _tables() if d.get("net")]


def set_sign(dataset, sign):
    """Flip Net amount when the owner says the other side counts as positive (data as imported is flipped too)."""
    d = store.DATASETS[dataset]
    net = d.get("net")
    if not net or sign not in ("credit", "debit") or net["sign"] == sign:
        return
    for t in (d["table"], d["table"] + "_orig"):
        store.DB.execute(f"UPDATE {store.q(t)} SET {store.q(net['column'])} = -{store.q(net['column'])}")
    store.DB.commit()
    net["sign"] = sign
    store.LOG.append({"text": f"{net['column']} in {d['name']} now counts {'credits' if sign == 'credit' else 'debits'} as positive.", "dataset": dataset})
    for x in list(store.DATASETS):
        store.refresh(x)
