"""In-memory SQL store. Every imported table lives in SQLite; every answer,
table and model reads from it. Nothing here touches the network."""
import sqlite3, re, datetime as dt

DB = sqlite3.connect(":memory:")
DATASETS = {}      # id -> dataset dict
PASSAGES = []      # text snippets from documents: {source, where, text}
FILES = []         # names of imported files
LINKS = []         # accepted joins: {id, a, a_col, b, b_col}
LOG = []           # plain-English history of changes made to the data
_counter = [0]


def q(name):
    return '"' + str(name).replace('"', '""') + '"'


def next_id(prefix="t"):
    _counter[0] += 1
    return f"{prefix}{_counter[0]}"


def rows(sql, params=()):
    return DB.execute(sql, params).fetchall()


def scalar(sql, params=()):
    r = DB.execute(sql, params).fetchone()
    return r[0] if r else None


# ---------------------------------------------------------------- value parsing
_NUM = re.compile(r"^\(?[-+]?[$€£¥]?\s?[-+]?(\d{1,3}(,\d{3})+|\d+)?(\.\d+)?\s?%?\)?$")
_DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y",
                 "%b %d, %Y", "%B %d, %Y", "%d-%b-%Y", "%d-%b-%y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
                 "%d/%m/%Y %H:%M", "%m/%d/%Y %H:%M", "%d.%m.%Y", "%b %Y", "%B %Y", "%Y-%m"]
BLANKS = {"", "na", "n/a", "null", "none", "nan", "-", "--", "#n/a", "nil"}


_CURRENCY = re.compile(r"^(rm|myr|sgd|s\$|usd|us\$|aud|a\$|nzd|gbp|eur|idr|rp|php|thb|hkd|inr|rs\.?)\s*|\s*(rm|myr|sgd|usd|aud|nzd|gbp|eur)$", re.I)
_DRCR = re.compile(r"\s*(dr|cr)\.?$", re.I)


def parse_number(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return None if v != v else v
    s = str(v).strip()
    side = _DRCR.search(s)                       # ledger balances such as "1,234.00 Cr"
    if side and re.search(r"\d", s):
        s = s[:side.start()].strip()
    s = _CURRENCY.sub("", s).strip()
    if s.startswith("-(") and s.endswith(")"):
        s = s[1:]
    if side and side.group(1).lower() == "cr" and not s.startswith("("):
        s = "(" + s + ")"
    if not s or not _NUM.match(s) or not re.search(r"\d", s):
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = re.sub(r"[()$€£¥,%\s]", "", s)
    try:
        n = float(s)
    except ValueError:
        return None
    n = -n if neg else n
    return int(n) if n == int(n) and "." not in s else n


def parse_date(v, fmt_hint=None):
    """Returns (iso_string, format_used) or (None, None)."""
    if isinstance(v, dt.datetime):
        return v.date().isoformat(), "native"
    if isinstance(v, dt.date):
        return v.isoformat(), "native"
    if not isinstance(v, str):
        return None, None
    s = v.strip()
    if len(s) < 6 or len(s) > 25 or not re.search(r"\d", s):
        return None, None
    for f in ([fmt_hint] if fmt_hint and fmt_hint != "native" else []) + _DATE_FORMATS:
        try:
            d = dt.datetime.strptime(s, f)
            if 1900 <= d.year <= 2200:
                return d.date().isoformat(), f
        except ValueError:
            continue
    return None, None


def is_blank(v):
    return v is None or (isinstance(v, float) and v != v) or (isinstance(v, str) and v.strip().lower() in BLANKS)


def infer_column(values):
    """Decide what a column holds. Returns (type, cleaned_values, not_understood)."""
    present = [v for v in values if not is_blank(v)]
    if not present:
        return "text", [None] * len(values), []
    nums = [parse_number(v) for v in present]
    n_ok = sum(1 for n in nums if n is not None)
    if n_ok >= 0.9 * len(present) and n_ok > 0:
        out, bad = [], []
        for v in values:
            if is_blank(v):
                out.append(None)
            else:
                n = parse_number(v)
                if n is None:
                    bad.append(str(v))
                out.append(n)
        return "number", out, bad
    fmt, sample = None, [v for v in present[:200] if isinstance(v, str)]
    if sample:                       # the format that reads the most values (so 01/15/2025 picks month-first)
        best = max(_DATE_FORMATS, key=lambda f: sum(1 for v in sample if parse_date(v, f)[1] == f))
        if any(parse_date(v, best)[1] == best for v in sample):
            fmt = best
    dates = [parse_date(v, fmt)[0] for v in present]
    d_ok = sum(1 for d in dates if d)
    if d_ok >= 0.9 * len(present):
        out, bad = [], []
        for v in values:
            if is_blank(v):
                out.append(None)
            else:
                d = parse_date(v, fmt)[0]
                if d is None:
                    bad.append(str(v))
                out.append(d)
        return "date", out, bad
    out = []
    for v in values:
        if is_blank(v):
            out.append(None)
        elif isinstance(v, float) and v == int(v):
            out.append(str(int(v)))
        elif isinstance(v, (dt.datetime, dt.date)):
            out.append(parse_date(v)[0])
        else:
            out.append(str(v))
    return "text", out, []


_ID_NAME = re.compile(r"(^|[\s_\-#])(id|code|key|ref|no|number|num|sku|postcode|zip)\.?$", re.I)
_YEAR_NAME = re.compile(r"\b(year|yr)\b", re.I)


def describe_columns(source, names):
    """Profile each column of a table or view and decide its role:
    id / measure (a number you can add up) / category / date / text."""
    total = scalar(f"SELECT COUNT(*) FROM {q(source)}") or 0
    cols = []
    for name in names:
        c = q(name)
        missing, distinct = rows(f"SELECT SUM({c} IS NULL), COUNT(DISTINCT {c}) FROM {q(source)}")[0]
        missing = missing or 0
        kinds = dict(rows(f"SELECT typeof({c}), COUNT(*) FROM {q(source)} WHERE {c} IS NOT NULL GROUP BY 1"))
        numeric = kinds.get("integer", 0) + kinds.get("real", 0)
        present = total - missing
        sample = scalar(f"SELECT {c} FROM {q(source)} WHERE {c} IS NOT NULL LIMIT 1")
        if present and numeric == present:
            typ = "number"
        elif present and isinstance(sample, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", sample) and \
                scalar(f"SELECT COUNT(*) FROM {q(source)} WHERE {c} IS NOT NULL AND {c} NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'") == 0:
            typ = "date"
        else:
            typ = "text"
        if typ == "date":
            role = "date"
        elif _ID_NAME.search(name.strip()):
            role = "id"
        elif typ == "number":
            role = "category" if (_YEAR_NAME.search(name) and distinct <= 60) else "measure"
        else:
            role = "category" if distinct <= max(30, 0.2 * present) and distinct <= 300 else \
                   ("id" if present and distinct == present and present > 20 and
                    scalar(f"SELECT AVG(LENGTH({c})) FROM {q(source)}") <= 14 and
                    scalar(f"SELECT COUNT(*) FROM {q(source)} WHERE {c} GLOB '*[0-9]*'") >= 0.9 * present
                    else "text")
        col = {"name": name, "type": typ, "role": role, "missing": missing, "distinct": distinct}
        if typ in ("number", "date") and present:
            col["min"], col["max"] = rows(f"SELECT MIN({c}), MAX({c}) FROM {q(source)}")[0]
        cols.append(col)
    return total, cols


def refresh(ds_id):
    ds = DATASETS[ds_id]
    ds["rows"], ds["columns"] = describe_columns(ds["table"], [c["name"] for c in ds["columns"]])
    return ds


def add_table(name, source, columns, data, where=None):
    """columns: list of names; data: list of row lists (already cleaned)."""
    ds_id = next_id()
    table = f"data_{ds_id}"
    defs = ", ".join(q(c) for c in columns)
    DB.execute(f"CREATE TABLE {q(table)} (_row INTEGER, {defs})")
    marks = ",".join("?" * (len(columns) + 1))
    DB.executemany(f"INSERT INTO {q(table)} VALUES ({marks})", [[i + 2] + list(r) for i, r in enumerate(data)])
    DB.execute(f"CREATE TABLE {q(table + '_orig')} AS SELECT * FROM {q(table)}")
    DB.commit()
    existing = {d["name"].lower() for d in DATASETS.values()}
    base, n = name, 2
    while name.lower() in existing:
        name = f"{base} ({n})"
        n += 1
    DATASETS[ds_id] = {"id": ds_id, "name": name, "table": table, "source": source, "where": where,
                       "kind": "table", "columns": [{"name": c} for c in columns], "dismissed": []}
    refresh(ds_id)
    return ds_id


def col(ds, name):
    for c in ds["columns"]:
        if c["name"] == name:
            return c
    raise KeyError(f"No column called {name}")


def public(ds):
    return {k: ds[k] for k in ("id", "name", "source", "where", "kind", "rows", "columns")} | \
           {"parts": ds.get("parts", [])}


def fmt(v, digits=2):
    if v is None:
        return "blank"
    if isinstance(v, float):
        if abs(v) >= 100 or v == int(v):
            return f"{v:,.0f}"
        return f"{v:,.{digits}f}"
    if isinstance(v, int):
        return f"{v:,}" if abs(v) >= 10000 else str(v)
    return str(v)
