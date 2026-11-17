"""Data checks: blanks, repeats, inconsistent spellings, unusual values.
Each finding comes with a plain-English description, a confidence level,
example rows, and a one-click fix."""
import re, datetime as dt, difflib
from . import store
from .store import q, rows, scalar, fmt


def _plural(n, word, plural=None):
    return f"{n:,} {word if n == 1 else (plural or word + 's')}"


def _examples(ds, where, params=(), limit=5):
    names = [c["name"] for c in ds["columns"]]
    sel = ", ".join(q(n) for n in names)
    data = rows(f"SELECT _row, {sel} FROM {q(ds['table'])} WHERE {where} ORDER BY _row LIMIT {limit}", params)
    return {"columns": ["Row in file"] + names, "rows": [list(r) for r in data]}


def _norm(v):
    return re.sub(r"[\s_\-\.]+", " ", str(v)).strip().casefold()


def check(ds_id):
    ds = store.DATASETS[ds_id]
    if ds["kind"] != "table":
        return {"issues": [], "summary": _summary(ds, [])}
    t, total = q(ds["table"]), ds["rows"]
    names = [c["name"] for c in ds["columns"]]
    issues = []

    def add(kind, column, title, detail, count, confidence, where, params=(), fix=None, keep="Keep as is", extra=None):
        key = f"{kind}:{column or ''}"
        if key in ds["dismissed"] or count == 0:
            return
        issues.append({"key": key, "kind": kind, "column": column, "title": title, "detail": detail, "count": count,
                       "share": round(100 * count / total, 1) if total else 0, "confidence": confidence,
                       "examples": _examples(ds, where, params), "fix": fix, "keep": keep, **(extra or {})})

    # 1. rows that are exact copies of another row
    allcols = ", ".join(q(n) for n in names)
    extra_rows = scalar(f"SELECT COALESCE(SUM(n - 1), 0) FROM (SELECT COUNT(*) n FROM {t} GROUP BY {allcols} HAVING n > 1)")
    if extra_rows:
        # With an ID column (Order ID, Invoice No.) a whole repeated row is a copy made by mistake.
        # Without one, identical rows can be real (two identical sales on the same day), so a person decides.
        has_id = any(c["role"] == "id" for c in ds["columns"])
        add("duplicates", None, f"{_plural(extra_rows, 'row')} appear{'s' if extra_rows == 1 else ''} more than once",
            "These rows are exact copies of another row, including the ID, so totals would count them twice." if has_id else
            "These rows are exact copies of another row. There is no ID column to tell whether they are mistakes or real repeat entries, "
            "such as two identical sales on the same day. Check before removing them.",
            extra_rows, "High" if has_id else "Medium",
            f"_row NOT IN (SELECT MIN(_row) FROM {t} GROUP BY {allcols})",
            fix="Remove the extra copies")

    for c in ds["columns"]:
        name, cq = c["name"], q(c["name"])
        present = total - c["missing"]
        # 2. blanks
        if c["missing"] and present:
            share = 100 * c["missing"] / total
            if c["type"] == "number":
                med = _median(t, cq)
                fix, detail = f"Fill blanks with the typical value ({fmt(med)})", \
                    "Blank numbers are skipped in totals and averages. If a blank really means a typical value, you can fill it in."
            elif c["type"] == "text":
                fix, detail = "Label blanks as “Unknown”", "Blank entries are left out when you group by this field."
            else:
                fix, detail = None, "Rows with no date are left out of anything shown over time."
            add("missing", name, f"{_plural(c['missing'], 'blank')} in {name}", detail, c["missing"],
                "High", f"{cq} IS NULL", fix=fix, keep="Leave blank",
                extra={"note": f"{share:.1f}% of rows"})
        # 3. the same thing spelled different ways
        if c["type"] == "text" and c["role"] in ("category",) and present:
            vals = rows(f"SELECT {cq}, COUNT(*) FROM {t} WHERE {cq} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC")
            groups = {}
            for v, n in vals:
                groups.setdefault(_norm(v), []).append((v, n))
            mapping, conf = {}, "High"
            for variants in groups.values():
                for v, _ in variants[1:]:
                    mapping[v] = variants[0][0]
            canon = [(g[0][0], sum(n for _, n in g)) for g in groups.values()]
            common = [v for v, n in canon if n >= 5]
            for v, n in canon:
                if n <= max(2, 0.02 * present) and len(str(v)) >= 3 and v not in common:
                    best = difflib.get_close_matches(_norm(v), [_norm(x) for x in common], n=1, cutoff=0.72)
                    if best:
                        target = next(x for x in common if _norm(x) == best[0])
                        for raw, _ in groups[_norm(v)]:
                            mapping[raw] = target
                        conf = "Medium"
            if mapping:
                affected = sum(n for v, n in vals if v in mapping)
                by_target = {}
                for raw, tgt in mapping.items():
                    by_target.setdefault(tgt, []).append(raw)
                shown = "; ".join(f"{', '.join('“' + r + '”' for r in raws[:4])} → “{tgt}”" for tgt, raws in list(by_target.items())[:4])
                marks = ",".join("?" * len(mapping))
                add("spelling", name, f"{name} has the same value written different ways",
                    f"{_plural(affected, 'row')} use a different spelling, capital letters or extra spaces: {shown}. "
                    "Grouping would treat these as separate values.", affected, conf,
                    f"{cq} IN ({marks})", tuple(mapping), fix="Use one spelling for each", extra={"mapping": mapping})
        # 4. numbers far outside the usual range
        if c["type"] == "number" and c["role"] == "measure" and present >= 20 and c["distinct"] > 5:
            q1, q3 = _quantile(t, cq, 0.25), _quantile(t, cq, 0.75)
            lo, hi = _fences(t, cq)
            n = scalar(f"SELECT COUNT(*) FROM {t} WHERE {cq} < ? OR {cq} > ?", (lo, hi))
            if 0 < n <= 0.02 * present + 1:
                ex = rows(f"SELECT {cq} FROM {t} WHERE {cq} < ? OR {cq} > ? ORDER BY ABS({cq} - ?) DESC LIMIT 3", (lo, hi, (q1 + q3) / 2))
                add("unusual", name, f"{_plural(n, 'unusually extreme value')} in {name}",
                    f"Most values fall between {fmt(q1)} and {fmt(q3)}, but {'this row has' if n == 1 else 'these rows have'} "
                    f"{', '.join(fmt(e[0]) for e in ex)}. They may be real, or a typing mistake.",
                    n, "Medium", f"{cq} < ? OR {cq} > ?", (lo, hi),
                    fix="Leave these rows out", keep="Keep — they are real")
            # 5. negative values in a column that is otherwise positive
            neg = scalar(f"SELECT COUNT(*) FROM {t} WHERE {cq} < 0")
            if 0 < neg <= 0.02 * present:
                add("negative", name, f"{_plural(neg, 'negative value')} in {name}",
                    f"Almost every {name} is above zero. Negative entries may be refunds or mistakes.",
                    neg, "Low", f"{cq} < 0", fix="Leave these rows out", keep="Keep — they are real")
        # 6. dates that cannot be right
        if c["type"] == "date" and present:
            far = (dt.date.today() + dt.timedelta(days=366 * 2)).isoformat()
            n = scalar(f"SELECT COUNT(*) FROM {t} WHERE {cq} > ? OR {cq} < '1950-01-01'", (far,))
            if 0 < n <= 0.05 * present + 1:
                add("dates", name, f"{_plural(n, 'date')} in {name} look{'s' if n == 1 else ''} wrong",
                    "These dates are far in the future or the distant past, which usually means a typing mistake.",
                    n, "High", f"{cq} > ? OR {cq} < '1950-01-01'", (far,), fix="Leave these rows out")
        # 7. an ID that should be unique but repeats
        if c["role"] == "id" and present and c["distinct"] >= 0.95 * present and c["distinct"] < present:
            n = scalar(f"SELECT COALESCE(SUM(n - 1), 0) FROM (SELECT COUNT(*) n FROM {t} WHERE {cq} IS NOT NULL GROUP BY {cq} HAVING n > 1)")
            if n > extra_rows:
                add("repeat_id", name, f"{_plural(n, 'repeated value')} in {name}",
                    f"{name} looks like it should be different on every row, but some values are used more than once with different details.",
                    n, "Medium", f"{cq} IN (SELECT {cq} FROM {t} GROUP BY {cq} HAVING COUNT(*) > 1)",
                    fix="Keep only the first of each")
    for note in ds.get("import_notes", []):
        if f"note:{note['column']}" not in ds["dismissed"]:
            issues.append({"key": f"note:{note['column']}", "kind": "note", "column": note["column"],
                           "title": f"Some entries in {note['column']} could not be read", "detail": note["text"],
                           "count": note["count"], "share": round(100 * note["count"] / max(total, 1), 1),
                           "confidence": "High", "examples": None, "fix": None, "keep": "OK"})
    return {"issues": issues, "summary": _summary(ds, issues)}


def _summary(ds, issues):
    cells = ds["rows"] * max(len(ds["columns"]), 1)
    blanks = sum(c["missing"] for c in ds["columns"])
    return {"rows": ds["rows"], "columns": len(ds["columns"]), "to_review": len(issues),
            "complete": round(100 * (1 - blanks / cells), 1) if cells else 100.0}


def _quantile(t, cq, p):
    n = scalar(f"SELECT COUNT({cq}) FROM {t}")
    if not n:
        return 0
    return scalar(f"SELECT {cq} FROM {t} WHERE {cq} IS NOT NULL ORDER BY {cq} LIMIT 1 OFFSET ?", (min(n - 1, int(p * (n - 1) + 0.5)),))


def _fences(t, cq):
    """Values outside these limits are 'extreme': far beyond both the middle half of
    the data and the top/bottom 1%."""
    q1, q3 = _quantile(t, cq, 0.25), _quantile(t, cq, 0.75)
    p1, p99 = _quantile(t, cq, 0.01), _quantile(t, cq, 0.99)
    iqr = (q3 - q1) or abs(q3) or 1
    hi = max(q3 + 4 * iqr, 3 * p99 if p99 > 0 else q3 + 4 * iqr)
    lo = min(q1 - 4 * iqr, 3 * p1) if p1 < 0 else float("-inf") if q1 >= 0 else q1 - 4 * iqr
    return lo, hi


def _median(t, cq):
    return _quantile(t, cq, 0.5)


def apply_fix(ds_id, key):
    """One-click fix. Changes the working copy only; the original import is kept for undo."""
    ds = store.DATASETS[ds_id]
    issue = next((i for i in check(ds_id)["issues"] if i["key"] == key), None)
    if not issue:
        return {"done": False}
    t, kind, column = q(ds["table"]), issue["kind"], issue["column"]
    cq = q(column) if column else None
    names = [c["name"] for c in ds["columns"]]
    cur = store.DB.cursor()
    if kind == "duplicates":
        allcols = ", ".join(q(n) for n in names)
        cur.execute(f"DELETE FROM {t} WHERE _row NOT IN (SELECT MIN(_row) FROM {t} GROUP BY {allcols})")
        text = f"Removed {cur.rowcount:,} repeated rows from {ds['name']}."
    elif kind == "missing":
        c = store.col(ds, column)
        value = _median(t, cq) if c["type"] == "number" else "Unknown"
        cur.execute(f"UPDATE {t} SET {cq} = ? WHERE {cq} IS NULL", (value,))
        text = f"Filled {cur.rowcount:,} blanks in {column} ({ds['name']}) with {fmt(value)}."
    elif kind == "spelling":
        n = 0
        for raw, target in issue["mapping"].items():
            cur.execute(f"UPDATE {t} SET {cq} = ? WHERE {cq} = ?", (target, raw))
            n += cur.rowcount
        text = f"Made the spelling consistent in {n:,} rows of {column} ({ds['name']})."
    elif kind == "unusual":
        cur.execute(f"DELETE FROM {t} WHERE {cq} < ? OR {cq} > ?", _fences(t, cq))
        text = f"Left out {cur.rowcount:,} rows with extreme {column} values from {ds['name']}."
    elif kind == "negative":
        cur.execute(f"DELETE FROM {t} WHERE {cq} < 0")
        text = f"Left out {cur.rowcount:,} rows with negative {column} from {ds['name']}."
    elif kind == "dates":
        far = (dt.date.today() + dt.timedelta(days=366 * 2)).isoformat()
        cur.execute(f"DELETE FROM {t} WHERE {cq} > ? OR {cq} < '1950-01-01'", (far,))
        text = f"Left out {cur.rowcount:,} rows with impossible dates in {column} ({ds['name']})."
    elif kind == "repeat_id":
        cur.execute(f"DELETE FROM {t} WHERE {cq} IS NOT NULL AND _row NOT IN (SELECT MIN(_row) FROM {t} GROUP BY {cq})")
        text = f"Kept only the first row for each repeated {column} in {ds['name']} ({cur.rowcount:,} removed)."
    else:
        return {"done": False}
    store.DB.commit()
    store.LOG.append({"text": text, "dataset": ds_id})
    _refresh_all()
    return {"done": True, "text": text}


def dismiss(ds_id, key):
    store.DATASETS[ds_id]["dismissed"].append(key)
    return {"done": True}


def restore(ds_id):
    """Undo every fix on this table by going back to the data exactly as imported."""
    ds = store.DATASETS[ds_id]
    store.DB.execute(f"DELETE FROM {q(ds['table'])}")
    store.DB.execute(f"INSERT INTO {q(ds['table'])} SELECT * FROM {q(ds['table'] + '_orig')}")
    store.DB.commit()
    ds["dismissed"] = []
    store.LOG.append({"text": f"Restored {ds['name']} to the data exactly as imported.", "dataset": ds_id})
    _refresh_all()
    return {"done": True}


def _refresh_all():
    for d in store.DATASETS:
        store.refresh(d)
