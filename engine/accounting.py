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


def tidy(grid):
    """Returns (grid, info). info: {template, notes} or None when nothing was recognised."""
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
    name, group_word = next(((n, g) for n, g, test in TEMPLATES if test(lower) or test(flat)), (None, "Group"))
    body = grid[hi + 1:]
    width = max(len(header), max((len(r) for r in body), default=0))
    header += [None] * (width - len(header))
    notes = []
    if hi:
        notes.append(f"skipped {hi} title row{'s' if hi != 1 else ''} above the column names")
    # group headings: a lone text cell in the first filled column, with data rows under it
    first_col = next((j for j in range(width) if any(not store.is_blank((r + [None] * width)[j]) for r in body)), 0)
    out, group, groups, totals, used_group = [], None, 0, 0, False
    for r in body:
        r = r + [None] * (width - len(r))
        cells = _filled(r)
        lead = next((v for v in r if not store.is_blank(v)), None)
        if _text(lead) and TOTAL_ROW.match(str(lead)):
            totals += 1
            continue
        if re.match(r"^(accrual|cash) basis", str(lead or ""), re.I):
            continue                                         # QuickBooks footer line
        if len(cells) == 1 and _text(cells[0]) and not store.parse_date(cells[0])[0] and store.parse_number(cells[0]) is None:
            group = str(cells[0]).strip()
            groups += 1
            continue
        if any(_text(v) and TOTAL_ROW.match(str(v)) for v in r[:3]):
            totals += 1
            continue
        out.append(([group] if groups else []) + r)
        used_group = used_group or group is not None
    if groups and used_group:
        header = [group_word] + header
        notes.append(f"took the {group_word.lower()} name from {groups} group heading{'s' if groups != 1 else ''}")
    if totals:
        notes.append(f"left out {totals} subtotal and total row{'s' if totals != 1 else ''} so nothing is counted twice")
    if header and store.is_blank(header[0]) and not groups:
        header[0] = group_word if name else "Column 1"
    if not name and not notes:
        return grid, None
    return [header] + out, {"template": name, "notes": notes}


def debit_credit(columns, types, cols):
    """When a table has Debit and Credit number columns, add Net (debit minus credit)."""
    low = [c.lower().strip(". ") for c in columns]
    di = next((i for i, c in enumerate(low) if c in ("debit", "dr", "debit amount", "local debit")), None)
    ci = next((i for i, c in enumerate(low) if c in ("credit", "cr", "credit amount", "local credit")), None)
    if di is None or ci is None or types[di] != "number" or types[ci] != "number" or any(c.lower() == "net amount" for c in columns):
        return None
    net = [None if a is None and b is None else (a or 0) - (b or 0) for a, b in zip(cols[di], cols[ci])]
    return "Net amount", net
