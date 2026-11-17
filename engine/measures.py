"""What a story can measure, and the owner's answers to the quick checks.

A measure is a total (money, counts, quantities), an average (prices, rates, scores),
the number of rows, or a derived measure built from two numbers (margin, average order
value). Every measure carries the plain-English formula shown in "How I got this".
Also here: whether the last month is complete, and the reconciliation from file to story."""
import calendar, re
from . import store
from . import catalogue as CAT
from .store import q, rows, scalar

MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
LEAD = ["sales", "revenue", "amount", "profit", "margin", "income", "actual", "cost", "expense", "spend", "value", "total", "quantity", "units", "volume"]
RATE_NAME = re.compile(r"price|rate|score|percent|%|discount|tenure|\bage\b|ratio|rating|year|margin %|average|avg", re.I)
SALES = re.compile(r"sales|revenue|turnover|income|amount|net total|gross", re.I)
COST_TOTAL = re.compile(r"\bcost|cogs|expense|purchase", re.I)
UNIT_COST = re.compile(r"unit cost|cost price|cost per|unit purchase", re.I)
QTY = re.compile(r"\bqty\b|quantity|units sold|\bunits\b|volume", re.I)
ORDER_ID = re.compile(r"order|invoice|receipt|transaction|bill|sale no|doc", re.I)

# The owner's answers. kinds: "<base id>|<column>" -> "money" | "count" | "rate"
SETTINGS = {"kinds": {}, "date": {}, "complete": {}}
USER = []          # measures the owner made: {id, dataset, name, a, op, b}


def kind_of(base, col):
    """The owner's answer if given, otherwise a guess from the name."""
    k = SETTINGS["kinds"].get(f"{base['id']}|{col}")
    if k:
        return k, False
    if col in (CAT.role("sales"), CAT.role("cost"), CAT.role("target")):
        return "money", True
    if col == CAT.role("qty"):
        return "count", True
    if RATE_NAME.search(col):
        return "rate", True
    return ("count" if QTY.search(col) or re.search(r"count|number|tickets|visits|orders", col, re.I) else "money"), True


def chosen_date(base):
    dates = [c["name"] for c in base["columns"] if c["type"] == "date"]
    d = SETTINGS["date"].get(base["id"]) or CAT.role("date", base)
    return d if d in dates else (dates[0] if dates else None)


def _cols(ds):
    return {c["name"]: c for c in ds["columns"]}


def _num(ds, pattern, exclude=None):
    for c in ds["columns"]:
        if c["type"] == "number" and c["role"] == "measure" and pattern.search(c["name"]) and not (exclude and exclude.search(c["name"])):
            return c["name"]
    return None


def suggested(ds):
    """Derived measures offered automatically when the fields exist."""
    out = []
    sales = CAT.role("sales", ds) or _num(ds, SALES, re.compile(r"cost|price|unit|discount|%", re.I))
    qty = CAT.role("qty", ds) or _num(ds, QTY)
    mc = CAT.role("cost", ds)
    cost, cost_expr, cost_words = (mc if mc and not UNIT_COST.search(mc) else None) or (None if mc else _num(ds, COST_TOTAL, re.compile(r"unit|per|price", re.I))), None, None
    if cost:
        cost_expr, cost_words = q(cost), cost
    else:
        uc = mc if mc and UNIT_COST.search(mc) else _num(ds, UNIT_COST)
        if uc and qty:
            cost_expr, cost_words = f"({q(qty)} * {q(uc)})", f"{qty} × {uc}"
    if sales and cost_expr:
        out.append({"value": "calc:margin", "label": "Margin", "op": "minus", "a": q(sales), "b": cost_expr,
                    "formula": f"Margin = total {sales} minus total cost ({cost_words}).", "detail": f"{sales} minus cost"})
        out.append({"value": "calc:margin_pct", "label": "Margin %", "op": "margin_pct", "a": q(sales), "b": cost_expr,
                    "formula": f"Margin % = ({sales} minus cost ({cost_words})) ÷ {sales} × 100.", "detail": f"Margin as a share of {sales}"})
    oid = CAT.role("order", ds) or next((c["name"] for c in ds["columns"] if c["role"] == "id" and ORDER_ID.search(c["name"])), None)
    if sales and oid:
        out.append({"value": "calc:aov", "label": "Average order value", "op": "per_id", "a": q(sales), "b": q(oid),
                    "formula": f"Average order value = total {sales} ÷ number of different {oid}s.", "detail": f"{sales} per {oid}"})
    if sales and qty:
        out.append({"value": "calc:unit_price", "label": "Average price per unit", "op": "divide", "a": q(sales), "b": q(qty),
                    "formula": f"Average price per unit = total {sales} ÷ total {qty}.", "detail": f"{sales} per {qty}"})
    return out


def _user(ds):
    out = []
    for m in USER:
        if m["dataset"] not in (ds["id"], ds.get("base")):
            continue
        cols = _cols(ds)
        if m["a"] not in cols or (m["op"] in ("minus", "divide", "margin_pct") and m["b"] not in cols) or (m["op"] == "per_id" and m["b"] not in cols):
            continue
        words = {"minus": "minus", "divide": "divided by", "per_id": "per different", "per_row": "per row"}[m["op"]]
        b = "" if m["op"] == "per_row" else f" {m['b']}"
        out.append({"value": f"calc:{m['id']}", "label": m["name"], "op": m["op"], "a": q(m["a"]), "b": q(m["b"]) if m.get("b") else None,
                    "formula": f"{m['name']} = total {m['a']} {words}{(' total' if m['op'] in ('minus', 'divide') else '')}{b}.", "detail": f"{m['a']} {words}{b}", "user": True})
    return out


def derived(ds):
    return suggested(ds) + _user(ds)


def define(ds, base, value):
    """Everything the story needs to know about one measure."""
    if not value:
        return {"value": None, "label": f"Number of {base['name']}", "of": base["name"], "expr": "COUNT(*)", "additive": True,
                "kind": "count", "unit": "", "column": None, "formula": None, "verb": "Counted the rows"}
    if str(value).startswith("calc:"):
        d = next((m for m in derived(ds) if m["value"] == value), None)
        if not d:
            raise ValueError("That measure is no longer available.")
        a, b, op = d["a"], d["b"], d["op"]
        expr = {"minus": f"(TOTAL({a}) - TOTAL({b}))",
                "margin_pct": f"(100.0 * (TOTAL({a}) - TOTAL({b})) / NULLIF(TOTAL({a}), 0))",
                "divide": f"(TOTAL({a}) * 1.0 / NULLIF(TOTAL({b}), 0))",
                "per_id": f"(TOTAL({a}) * 1.0 / NULLIF(COUNT(DISTINCT {b}), 0))",
                "per_row": f"AVG({a})"}[op]
        return {"value": value, "label": d["label"], "of": d["label"], "expr": expr, "additive": op == "minus",
                "kind": "ratio" if op != "minus" else "money", "unit": "%" if op == "margin_pct" else "", "column": None,
                "formula": d["formula"], "verb": "Worked out " + d["label"]}
    kind, _ = kind_of(base, value)
    if kind == "rate":
        return {"value": value, "label": f"Average {value}", "of": f"Average {value}", "expr": f"AVG({q(value)})", "additive": False,
                "kind": "rate", "unit": "", "column": value, "formula": f"Average {value} = the average of {value} over the rows in each period or group.",
                "verb": f"Averaged {value}"}
    return {"value": value, "label": value, "of": value, "expr": f"SUM({q(value)})", "additive": True, "kind": kind, "unit": "",
            "column": value, "formula": None, "verb": f"Added up {value}"}


def listing(ds, base):
    """Every measure a story about this table can use, in a sensible order."""
    totals, rates = [], []
    for c in base["columns"]:
        if c["role"] != "measure" or c["type"] != "number":
            continue
        (rates if kind_of(base, c["name"])[0] == "rate" else totals).append(c["name"])
    order = lambda n: -1 if n == CAT.role("sales") else next((i for i, w in enumerate(LEAD) if w in n.lower()), 99)
    totals.sort(key=order)
    out = [{"value": m, "label": m, "detail": f"Total {m}, from {base['name']}"} for m in totals]
    out += [{"value": d["value"], "label": d["label"], "detail": d["detail"] + f", from {base['name']}"} for d in derived(ds)]
    out += [{"value": m, "label": f"Average {m}", "detail": f"Average {m}, from {base['name']}"} for m in rates]
    out.append({"value": None, "label": f"Number of {base['name']}", "detail": f"How many rows there are in {base['name']}"})
    return out


# ---------------------------------------------------------------- is the last month finished?
def month_complete(base, date, last_m, last_day):
    """(complete, reason). The owner's answer wins; otherwise judge by the calendar."""
    y, m = last_m // 12, last_m % 12 + 1
    label = f"{MON[m - 1]} {y}"
    ans = SETTINGS["complete"].get(base["id"])
    if ans is not None:
        return bool(ans), (f"You confirmed {label} is complete." if ans else f"You said {label} is still running, so it is left out.")
    days = scalar(f"SELECT COUNT(DISTINCT strftime('%d', {q(date)})) FROM {q(base['table'])} WHERE {q(date)} IS NOT NULL") or 0
    if days <= 2:
        return True, "The data has one date per month, so every month counts as complete."
    length = calendar.monthrange(y, m)[1]
    if last_day >= length - 3:
        return True, f"The last date is {last_day} {MON[m - 1]}, at the end of the month, so {label} looks complete."
    return False, f"The data stops on {last_day} {MON[m - 1]}, before the month ends, so {label} looks unfinished."


def last_month(base, date):
    """The latest month in the data and its last day, ignoring stray dates far from the rest."""
    r = rows(f"SELECT CAST(strftime('%Y', {q(date)}) AS INTEGER) * 12 + CAST(strftime('%m', {q(date)}) AS INTEGER) - 1, "
             f"MAX(CAST(strftime('%d', {q(date)}) AS INTEGER)), COUNT(*) FROM {q(base['table'])} WHERE {q(date)} IS NOT NULL GROUP BY 1 ORDER BY 1")
    if not r:
        return None
    runs, block = [], [r[0]]
    for x in r[1:]:
        if x[0] - block[-1][0] > 6:
            runs.append(block); block = [x]
        else:
            block.append(x)
    runs.append(block)
    main = max(runs, key=lambda b: sum(x[2] for x in b))
    return main[-1][0], main[-1][1]


def checks():
    """Gist's best guesses for the quick-checks step, for each table a story can be about."""
    from .story import _lookup_tables
    lookups = _lookup_tables()
    facts = [d for d in store.DATASETS.values() if d["kind"] == "table" and d["id"] not in lookups]
    facts.sort(key=lambda d: (not any(c["type"] == "date" for c in d["columns"]), -d["rows"]))
    out = []
    for base in facts[:2]:
        ms = [c["name"] for c in base["columns"] if c["role"] == "measure" and c["type"] == "number"]
        if not ms:
            continue
        entry = {"dataset": base["id"], "name": base["name"],
                 "measures": [{"name": m, "kind": kind_of(base, m)[0]} for m in ms[:8]],
                 "dates": [c["name"] for c in base["columns"] if c["type"] == "date"], "date": chosen_date(base)}
        if entry["date"]:
            lm = last_month(base, entry["date"])
            if lm:
                done, why = month_complete(base, entry["date"], *lm)
                entry.update({"last_month": f"{['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'][lm[0] % 12]} {lm[0] // 12}",
                              "complete": done, "why": why})
        out.append(entry)
    return out


def set_checks(answers):
    """answers: [{dataset, kinds: {col: kind}, date, complete}]"""
    for a in answers or []:
        tid = a["dataset"]
        for col, k in (a.get("kinds") or {}).items():
            if k in ("money", "count", "rate"):
                SETTINGS["kinds"][f"{tid}|{col}"] = k
        if a.get("date"):
            SETTINGS["date"][tid] = a["date"]
        if a.get("complete") is not None:
            SETTINGS["complete"][tid] = bool(a["complete"])
    return checks()


def add(dataset, name, a, op, b=None):
    if op not in ("minus", "divide", "per_id", "per_row"):
        raise ValueError("Choose minus, divided by, per different, or per row.")
    name = re.sub(r"\s+", " ", str(name)).strip()[:60] or "My measure"
    mid = f"u{len(USER) + 1}"
    USER.append({"id": mid, "dataset": dataset, "name": name, "a": a, "op": op, "b": b})
    return {"value": f"calc:{mid}", "label": name}


def remove(value):
    USER[:] = [m for m in USER if f"calc:{m['id']}" != value]
    return {"done": True}


# ---------------------------------------------------------------- from the file to the story
def reconcile(ds, base, M, where, params, fwords, period, plabel, period_total, date, notes_rows):
    """Rows and totals at each step from the original file to the figure on screen."""
    t, orig = q(base["table"]), q(base["table"] + "_orig")
    n0 = scalar(f"SELECT COUNT(*) FROM {orig}") or 0
    n1 = scalar(f"SELECT COUNT(*) FROM {t}") or 0
    col = M["column"] if M["kind"] != "rate" else None
    tot = lambda table, cond="": scalar(f"SELECT TOTAL({q(col)}) FROM {table}{cond}") if col else None
    t0, t1 = tot(orig), tot(t)
    gone = scalar(f"SELECT COUNT(*) FROM {orig} WHERE _row NOT IN (SELECT _row FROM {t})") or 0
    gone_total = tot(orig, f" WHERE _row NOT IN (SELECT _row FROM {t})")
    changed = (t0 - t1 - gone_total) if col else 0
    steps = [["Rows in " + base["source"], n0, t0]]
    if gone:
        steps.append(["Removed when tidying (for example repeated rows)", -gone, -gone_total if col else None])
    if col and abs(changed) > 0.005:
        steps.append(["Changed when tidying (for example blanks filled in)", None, -changed])
    steps.append(["Used by Gist", n1, t1])
    if fwords:
        nf = scalar(f"SELECT COUNT(*) FROM {q(ds['table'])}{where}", params) or 0
        steps.append(["Narrowed to rows where " + " and ".join(fwords), nf, scalar(f"SELECT TOTAL({q(col)}) FROM {q(ds['table'])}{where}", params) if col else None])
    if period:
        steps.append([plabel, notes_rows, period_total if M["additive"] else None])
    fv = lambda v: store.fmt(round(v, 2) if isinstance(v, float) else v)
    file = base["source"]
    line = f"From {n0:,} rows in {file}"
    line += f": {gone:,} removed when tidying, {n1:,} used." if gone else f": all {n1:,} used."
    if col:
        if abs(t0 - t1) < 0.005:
            line += f" {M['label']} adds up to {fv(t1)}, matching the file."
        else:
            parts = [f"{fv(gone_total)} in removed rows"] if gone else []
            if abs(changed) > 0.005:
                parts.append(f"{fv(changed)} from changes such as filled-in blanks")
            line += f" {M['label']} adds up to {fv(t1)} against {fv(t0)} in the file; the difference is {' and '.join(parts)}."
    if fwords:
        line += f" Narrowed to rows where {' and '.join(fwords)}: {nf:,} rows."
    if period:
        line += f" {plabel}: " + (f"{fv(period_total)} from " if M["additive"] and col else "") + f"{notes_rows:,} rows."
    return {"line": line, "steps": steps, "columns": ["Step", "Rows", M["label"] if col else ""]}
