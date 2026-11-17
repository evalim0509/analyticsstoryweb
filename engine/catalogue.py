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

ROLES = {}        # need key -> column name, as confirmed by the owner


def role(key, ds=None):
    """The column the owner matched to this need, if it exists in the given table."""
    c = ROLES.get(key)
    if not c:
        return None
    if ds is None:
        return c
    return c if any(x["name"] == c for x in ds["columns"]) else None


def _tables():
    return [d for d in store.DATASETS.values() if d["kind"] == "table"]


def columns():
    return [{"table": d["name"], "name": c["name"], "type": c["type"]} for d in _tables() for c in d["columns"]]


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
                best, score = n, s
        if best:
            out[key] = best
            used.add(best)
    return out


def needs():
    return [{"key": k, "label": label, "hint": hint} for k, label, hint, _, _ in NEEDS]


def set_roles(roles):
    ROLES.clear()
    names = {c["name"] for c in columns()}
    for k, v in (roles or {}).items():
        if v and v in names and k in WORDS:
            ROLES[k] = v
    return dict(ROLES)
