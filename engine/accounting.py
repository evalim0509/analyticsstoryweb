"""Recognises exports from common accounting systems and tidies their report layout
before the table is read: title rows above the header, group headings (a customer or
account name on its own row), subtotal and total rows, and debit/credit columns.

Templates are written from each system's standard export layouts:
Xero, QuickBooks, AutoCount / SQL Account, SAP Business One, Sage and MYOB."""
import re
from . import store

HEADER_WORDS = re.compile(r"^(date|doc\.? ?date|posting date|invoice date|txn date|transaction date|description|memo|details|memo/description|"
                          r"amount|total|net|gross|debit|credit|dr|cr|balance|running balance|account|account code|account name|n/c|"
                          r"invoice|invoice number|invoice no\.?|reference|ref|num|no\.?|doc\.? ?no\.?|document number|source|src|type|"
                          r"transaction type|tran no\.?|customer|customer name|contact|contact name|name|debtor code|debtor name|code|"
                          r"company name|agent|area|qty|quantity|item|item code|item number|product|price|unit price|sales price|"
                          r"tax|gst|vat|sst|tax amount|currency|line amount|unit amount|due date|status|id no\.?|job no\.?|"
                          r"co\./last name|first name|customer/vendor code|customer/vendor name|bp code|bp name|document total|row total)$", re.I)
TOTAL_ROW = re.compile(r"^\s*(total|sub\s?-?total|grand total|net total|total for|totals|opening balance|closing balance|"
                       r"balance b/?f|balance c/?f|balance brought forward|balance carried forward|report total)\b", re.I)

TEMPLATES = [
    # (name, kind of grouping heading, test on the lower-cased header names)
    ("Xero", "Contact", lambda h: ("contactname" in h or "contact name" in h) and any(x in h for x in ("invoicenumber", "invoice number", "reference"))),
    ("Xero", "Account", lambda h: {"source", "reference", "debit", "credit"} <= set(h) and "running balance" in h),
    ("QuickBooks", "Customer", lambda h: ("transaction type" in h and "num" in h) or ("memo/description" in h)),
    ("AutoCount", "Debtor", lambda h: "debtor code" in h or "debtor name" in h),
    ("SQL Account", "Customer", lambda h: ("doc no" in h or "doc. no." in h or "doc no." in h) and ("company name" in h or "code" in h)),
    ("SAP Business One", "Business partner", lambda h: "posting date" in h or "customer/vendor code" in h or "bp code" in h or "document total" in h),
    ("Sage", "Account", lambda h: "n/c" in h or ("tran no." in h or "tran no" in h)),
    ("MYOB", "Account", lambda h: "co./last name" in h or ({"src", "id no."} <= set(h)) or ("id no." in h and "memo" in h)),
]


def _text(v):
    return isinstance(v, str) and v.strip() != ""


def _filled(row):
    return [v for v in row if not store.is_blank(v)]


def _header_score(row):
    names = [str(v).strip().lower().rstrip(":") for v in row if _text(v)]
    if len(names) < 2:
        return 0
    return sum(1 for n in names if HEADER_WORDS.match(n.lstrip("*").strip()) or HEADER_WORDS.match(_split_camel(n.lstrip("*")).lower()))


def _split_camel(s):
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(s))


AMOUNT_COL = re.compile(r"amount|total|debit|credit|\bnet\b|balance|\bdr\b|\bcr\b|value|price", re.I)
ID_COL = re.compile(r"\bid\b|\bno\.?$|number|\bnum\b|\bref|doc|invoice|tran|\bsrc\b", re.I)


def _is_date(v):
    return not store.is_blank(v) and store.parse_date(v)[0] is not None


def tidy(grid):
    """Returns (grid, info). info: {template, notes, removed_rows, removed_totals}, or None for an ordinary file.

    Report cleanup (title rows, group headings, subtotal rows) only happens when the layout is recognised as an
    export from a known accounting system. Ordinary files are left exactly as they are."""
    grid = [list(r) for r in grid if any(not store.is_blank(v) for v in r)]
    if len(grid) < 3:
        return grid, None
    scores = [(_header_score(r), i) for i, r in enumerate(grid[:25])]
    best, hi = max(scores, key=lambda x: (x[0], -x[1]))
    if best < 3:
        return grid, None
    header = [(_split_camel(str(v).lstrip("*").strip()) if _text(v) else None) for v in grid[hi]]
    lower = [str(h).lower() for h in header if h]
    flat = [h.replace(" ", "") for h in lower]
    name, group_word = next(((n, g) for n, g, test in TEMPLATES if test(lower) or test(flat)), (None, None))
    if not name:
        return grid, None
    body = grid[hi + 1:]
    width = max(len(header), max((len(r) for r in body), default=0))
    header = header + [None] * (width - len(header))
    amount_cols = [j for j, h in enumerate(header) if h and AMOUNT_COL.search(h)]
    id_cols = [j for j, h in enumerate(header) if h and ID_COL.search(h)]
    notes = [f"skipped {hi} title row{'s' if hi != 1 else ''} above the column names"] if hi else []
    out, groups_of, removed = [], [], []
    group, groups, running, since = None, 0, {j: 0.0 for j in amount_cols}, 0
    for r in body:
        r = (r + [None] * width)[:width]
        cells = _filled(r)
        lead = next((v for v in r if not store.is_blank(v)), None)
        if re.match(r"^(accrual|cash) basis", str(lead or ""), re.I):
            continue                                         # QuickBooks footer line, not data
        if any(_text(v) and TOTAL_ROW.match(str(v)) for v in r):
            first_is_label = _text(lead) and TOTAL_ROW.match(str(lead))
            has_date = any(_is_date(v) for v in r if v is not lead)
            has_id = any(not store.is_blank(r[j]) for j in id_cols if r[j] is not lead)
            sums = [(store.parse_number(r[j]), running[j]) for j in amount_cols if store.parse_number(r[j]) is not None]
            equals = since > 0 and any(abs(v - total) < 0.005 for v, total in sums)
            if equals or (first_is_label and not has_date and not has_id):
                removed.append(r)
                running, since = {j: 0.0 for j in amount_cols}, 0
                continue
        if len(cells) == 1 and _text(cells[0]) and not _is_date(cells[0]) and store.parse_number(cells[0]) is None:
            group, groups = str(cells[0]).strip(), groups + 1
            running, since = {j: 0.0 for j in amount_cols}, 0
            continue
        out.append(r); groups_of.append(group); since += 1
        for j in amount_cols:
            v = store.parse_number(r[j])
            if v is not None:
                running[j] += v
    if groups and any(groups_of):
        header = [group_word] + header
        out = [[g] + r for g, r in zip(groups_of, out)]
        notes.append(f"took the {group_word.lower()} name from {groups} group heading{'s' if groups != 1 else ''}")
    if removed:
        notes.append(f"left out {len(removed)} subtotal and total row{'s' if len(removed) != 1 else ''} so nothing is counted twice")
    if header and store.is_blank(header[0]):
        header[0] = group_word
    assert all(len(r) == len(header) for r in out), "every row must line up with the column names"
    names = [h for h in header[1:]] if groups and any(groups_of) else header
    totals = {}
    for r in removed:                                       # what the removed rows held, for the reconciliation
        for j, h in enumerate(names):
            v = store.parse_number(r[j]) if h else None
            if v is not None:
                key = re.sub(r"\s+", " ", re.sub(r"[_\-]+", " ", str(h))).strip()
                totals[key] = totals.get(key, 0) + v
    return [header] + out, {"template": name, "notes": notes, "removed_rows": len(removed), "removed_totals": totals}


INCOME = re.compile(r"sales|income|revenue|turnover|fees? received", re.I)


def debit_credit(columns, types, cols):
    """When a table has Debit and Credit number columns, add a Net amount.
    Credits count as positive for sales and income (where most of the money is credits); otherwise debits do.
    The owner can change this in Match your fields. Returns (name, values, sign, debit column, credit column)."""
    low = [c.lower().strip(". ") for c in columns]
    di = next((i for i, c in enumerate(low) if c in ("debit", "dr", "debit amount", "local debit")), None)
    ci = next((i for i, c in enumerate(low) if c in ("credit", "cr", "credit amount", "local credit")), None)
    if di is None or ci is None or types[di] != "number" or types[ci] != "number" or any(c.lower() == "net amount" for c in columns):
        return None
    dr, cr = sum(v or 0 for v in cols[di]), sum(v or 0 for v in cols[ci])
    words = " ".join(str(v) for j, t in enumerate(types) if t == "text" for v in set(cols[j][:500]) if v)
    sign = "credit" if INCOME.search(words) or cr >= dr else "debit"
    k = 1 if sign == "debit" else -1
    net = [None if a is None and b is None else k * ((a or 0) - (b or 0)) for a, b in zip(cols[di], cols[ci])]
    return "Net amount", net, sign, columns[di], columns[ci]
