"""Reads uploaded files into candidate tables and searchable text.
Excel, CSV, Word, PowerPoint, PDF, text and JSON are supported."""
import csv, io, json, re, zipfile
import xml.etree.ElementTree as ET
from . import store, accounting

PENDING = {}   # token -> parsed file waiting for the user to confirm


def _clean_name(s):
    return re.sub(r"\s+", " ", re.sub(r"[_\-]+", " ", str(s))).strip()


def _table_from_grid(grid):
    """Find the header row and return (headers, rows) or None."""
    grid = [list(r) for r in grid if any(not store.is_blank(v) for v in r)]
    if len(grid) < 2:
        return None
    width = max(len(r) for r in grid)
    grid = [r + [None] * (width - len(r)) for r in grid]
    best = 0
    for i, r in enumerate(grid[:15]):
        filled = [v for v in r if not store.is_blank(v)]
        if len(filled) >= max(2, 0.6 * width) and all(isinstance(v, str) for v in filled):
            best = i
            break
    header, body = grid[best], grid[best + 1:]
    keep = [j for j in range(width) if not store.is_blank(header[j]) or any(not store.is_blank(r[j]) for r in body)]
    if not body or len(keep) < 1:
        return None
    names, seen = [], {}
    for j in keep:
        n = _clean_name(header[j]) if not store.is_blank(header[j]) else f"Column {j + 1}"
        n = n.replace('"', "'")
        if n == "_row":
            n = "row"
        k = n.lower()
        seen[k] = seen.get(k, 0) + 1
        names.append(n if seen[k] == 1 else f"{n} {seen[k]}")
    return names, [[r[j] for j in keep] for r in body]


def _candidate(name, where, grid):
    grid, report = accounting.tidy(grid)
    t = _table_from_grid(grid)
    if not t:
        return None
    names, body = t
    cols, notes, types = [], [], []
    for j, n in enumerate(names):
        typ, cleaned, bad = store.infer_column([r[j] for r in body])
        cols.append(cleaned)
        types.append(typ)
        if bad:
            shown = ", ".join(f"“{b}”" for b in sorted(set(bad))[:3])
            notes.append({"column": n, "count": len(bad), "examples": sorted(set(bad))[:5],
                          "text": f"{len(bad)} entr{'y' if len(bad) == 1 else 'ies'} in {n} "
                                  f"{'is' if len(bad) == 1 else 'are'} not a {typ} ({shown}) and will be treated as blank."})
    # amounts written in more than one currency are never added together
    currency, warnings = [], []
    for j, n in enumerate(list(names)):
        if types[j] != "number":
            continue
        codes = {store.currency_of(r[j]) for r in body} - {None}
        if "$" in codes and len(codes - {"$"}) == 1:
            codes = codes - {"$"}                                        # "$1,000" beside "USD 1,000": one currency
        if len(codes) > 1:
            field = f"{n} currency"
            names.append(field); types.append("text")
            cols.append([store.currency_of(r[j]) or None for r in body])
            currency.append({"column": n, "field": field, "codes": sorted(codes)})
            warnings.append(f"{n} mixes currencies ({', '.join(sorted(codes))}). Gist will not add them together; you will pick one currency in the story.")
    for j, n in enumerate(names):
        if types[j] == "text" and re.fullmatch(r"(currency( code)?|curr|ccy|currency id)", n.strip(), re.I):
            codes = sorted({v for v in cols[j] if v})
            if len(codes) > 1:
                currency.append({"column": "*", "field": n, "codes": codes})
                warnings.append(f"Amounts are in more than one currency ({', '.join(codes[:5])}, shown in {n}). Gist will not add them together; you will pick one currency in the story.")
    for w in warnings:
        notes.insert(0, {"column": None, "count": 0, "examples": [], "text": w})
    orders = {}
    for j, n in enumerate(names):
        if types[j] == "date" and j < len(body[0] if body else []):
            o = store.date_order([r[j] for r in body])
            if o:
                orders[n] = o
    net = accounting.debit_credit(names, types, cols)
    net_info = None
    if net:
        names = names + [net[0]]; types = types + ["number"]; cols = cols + [net[1]]
        net_info = {"column": net[0], "sign": net[2], "debit": net[3], "credit": net[4]}
        report = report or {"template": None, "notes": []}
        report["notes"].append(f"added Net amount ({'credits' if net[2] == 'credit' else 'debits'} count as positive)")
    data = [list(r) for r in zip(*cols)] if cols else []
    if report and (report["notes"] or report["template"]):
        what = f"Recognised an export from {report['template']}" if report["template"] else "Recognised an accounting report layout"
        notes.insert(0, {"column": None, "count": 0, "examples": [], "text": what + (": " + "; ".join(report["notes"]) if report["notes"] else "") + "."})
    return {"name": name, "where": where, "columns": names, "types": types, "data": data, "notes": notes,
            "template": report["template"] if report else None, "currency": currency, "currency_warning": " ".join(warnings), "net": net_info, "date_orders": orders,
            "read_removed": {"rows": report.get("removed_rows", 0), "totals": report.get("removed_totals", {})} if report else {"rows": 0, "totals": {}}}


def _xml_text(node, tag):
    return "".join(t.text or "" for t in node.iter() if t.tag.endswith("}" + tag))


def _read_xlsx(data):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    tables, passages = [], []
    for ws in wb.worksheets:
        grid = [list(r) for r in ws.iter_rows(values_only=True)]
        cand = _candidate(ws.title, f"sheet “{ws.title}”", grid)
        if cand and len(cand["data"]) >= 1 and len(cand["columns"]) >= 2:
            tables.append(cand)
        else:
            for r in grid:
                for v in r:
                    if isinstance(v, str) and len(v.strip()) > 20:
                        passages.append({"where": f"sheet “{ws.title}”", "text": v.strip()})
    return tables, passages


def _read_xls(data):
    import xlrd, datetime as dt
    wb = xlrd.open_workbook(file_contents=data)
    tables = []
    for sh in wb.sheets():
        grid = []
        for i in range(sh.nrows):
            row = []
            for c in sh.row(i):
                if c.ctype == xlrd.XL_CELL_DATE:
                    row.append(dt.datetime(*xlrd.xldate_as_tuple(c.value, wb.datemode)))
                else:
                    row.append(None if c.ctype in (0, 6) else c.value)
            grid.append(row)
        cand = _candidate(sh.name, f"sheet “{sh.name}”", grid)
        if cand and len(cand["columns"]) >= 2:
            tables.append(cand)
    return tables, []


def _decode(data):
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeError:
            continue
    return data.decode("utf-8", "replace")


def _read_csv(data, stem):
    text = _decode(data)
    try:
        dialect = csv.Sniffer().sniff(text[:5000], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    grid = list(csv.reader(io.StringIO(text), dialect))
    cand = _candidate(stem, "the file", grid)
    return ([cand] if cand else []), []


def _split_passages(text, where):
    out = []
    for para in re.split(r"\n\s*\n|\r\n\s*\r\n", text):
        para = re.sub(r"\s+", " ", para).strip()
        if len(para) > 600:
            for sentence_block in re.findall(r".{1,500}(?:[.!?]\s|$)", para):
                if sentence_block.strip():
                    out.append({"where": where, "text": sentence_block.strip()})
        elif len(para) >= 3:
            out.append({"where": where, "text": para})
    return out


def _read_docx(data, stem):
    z = zipfile.ZipFile(io.BytesIO(data))
    body = ET.fromstring(z.read("word/document.xml"))
    body = next(e for e in body.iter() if e.tag.endswith("}body"))
    tables, passages, n_par, n_tab, heading = [], [], 0, 0, None
    for el in body:
        if el.tag.endswith("}p"):
            text = _xml_text(el, "t").strip()
            if not text:
                continue
            n_par += 1
            style = next((s.attrib.get(k) for s in el.iter() if s.tag.endswith("}pStyle") for k in s.attrib if k.endswith("}val")), "") or ""
            if style.lower().startswith(("heading", "title")):
                heading = text
            passages.append({"where": f"paragraph {n_par}" + (f", under “{heading}”" if heading and heading != text else ""), "text": text})
        elif el.tag.endswith("}tbl"):
            n_tab += 1
            grid = []
            for tr in (r for r in el.iter() if r.tag.endswith("}tr")):
                grid.append([_xml_text(tc, "t").strip() or None for tc in tr if tc.tag.endswith("}tc")])
            cand = _candidate(heading or f"{stem} table {n_tab}", f"table {n_tab} in the document", grid)
            if cand and len(cand["columns"]) >= 2:
                tables.append(cand)
    return tables, passages


def _read_pptx(data, stem):
    z = zipfile.ZipFile(io.BytesIO(data))
    names = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                   key=lambda n: int(re.findall(r"\d+", n)[-1]))
    tables, passages = [], []
    for i, n in enumerate(names, 1):
        root = ET.fromstring(z.read(n))
        title = None
        for sp in (e for e in root.iter() if e.tag.endswith("}sp")):
            is_title = any(e.tag.endswith("}ph") and e.attrib.get("type") in ("title", "ctrTitle") for e in sp.iter())
            paras = [_xml_text(p, "t").strip() for p in sp.iter() if p.tag.endswith("}p")]
            paras = [p for p in paras if p]
            if is_title and paras:
                title = " ".join(paras)
            for p in paras:
                passages.append({"where": f"slide {i}" + (f" “{title}”" if title and p != title else ""), "text": p})
        for k, tbl in enumerate((e for e in root.iter() if e.tag.endswith("}tbl")), 1):
            grid = [[_xml_text(tc, "t").strip() or None for tc in tr if tc.tag.endswith("}tc")]
                    for tr in tbl if tr.tag.endswith("}tr")]
            cand = _candidate(f"{title or stem} table", f"table on slide {i}", grid)
            if cand and len(cand["columns"]) >= 2:
                tables.append(cand)
    return tables, passages


def _read_pdf(data):
    from pypdf import PdfReader
    passages = []
    for i, page in enumerate(PdfReader(io.BytesIO(data)).pages, 1):
        passages += _split_passages(re.sub(r"(?<![.!?:])\n(?!\n)", " ", page.extract_text() or ""), f"page {i}")
    return [], passages


def _read_json(data, stem):
    obj = json.loads(_decode(data))
    if isinstance(obj, dict):
        obj = next((v for v in obj.values() if isinstance(v, list)), [obj])
    if not (isinstance(obj, list) and obj and all(isinstance(r, dict) for r in obj)):
        raise ValueError("This JSON file is not a list of records.")
    keys = list(dict.fromkeys(k for r in obj for k in r))
    grid = [keys] + [[r.get(k) if not isinstance(r.get(k), (dict, list)) else json.dumps(r.get(k)) for k in keys] for r in obj]
    cand = _candidate(stem, "the file", grid)
    return ([cand] if cand else []), []


def preview(filename, data):
    """Parse a file and hold the result until the user confirms the import."""
    stem = _clean_name(re.sub(r"\.[^.]+$", "", filename))
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    try:
        if ext in ("xlsx", "xlsm"):
            tables, passages = _read_xlsx(data)
        elif ext == "xls":
            tables, passages = _read_xls(data)
        elif ext in ("csv", "tsv"):
            tables, passages = _read_csv(data, stem)
        elif ext == "docx":
            tables, passages = _read_docx(data, stem)
        elif ext == "pptx":
            tables, passages = _read_pptx(data, stem)
        elif ext == "pdf":
            tables, passages = _read_pdf(data)
        elif ext == "json":
            tables, passages = _read_json(data, stem)
        elif ext in ("txt", "md"):
            tables, passages = [], _split_passages(_decode(data), "the text")
        else:
            return {"file": filename, "error": f"I can't read .{ext or 'this type of'} files yet. "
                    "Try Excel, CSV, Word, PowerPoint, PDF or a text file."}
    except Exception as e:  # unreadable or damaged file
        return {"file": filename, "error": f"I couldn't open this file. It may be damaged or password-protected. ({type(e).__name__})"}
    if len(tables) == 1 and ext in ("xlsx", "xlsm", "xls"):
        tables[0]["name"] = tables[0]["name"] if tables[0]["name"].lower() not in ("sheet1", "sheet 1", "data") else stem
    for t in tables:
        t["name"] = _clean_name(t["name"]).title() if t["name"].islower() or "_" in t["name"] else _clean_name(t["name"])
    if not tables and not passages:
        return {"file": filename, "error": "I couldn't find any table or text in this file."}
    token = store.next_id("f")
    PENDING[token] = {"file": filename, "tables": tables, "passages": passages}
    return {"file": filename, "token": token, "text_count": len(passages),
            "text_sample": [p["text"][:160] for p in passages[:3]],
            "tables": [{"index": i, "name": t["name"], "where": t["where"], "rows": len(t["data"]), "template": t.get("template"), "currency_warning": t.get("currency_warning") or "",
                        "columns": [{"name": n, "type": ty} for n, ty in zip(t["columns"], t["types"])],
                        "sample": t["data"][:8], "notes": t["notes"]} for i, t in enumerate(tables)]}


def confirm(token, choices=None):
    """choices: {table_index: {"include": bool, "name": str}}"""
    p = PENDING.pop(token)
    choices = choices or {}
    made = []
    for i, t in enumerate(p["tables"]):
        ch = choices.get(str(i), {})
        if ch.get("include", True) is False:
            continue
        ds_id = store.add_table(ch.get("name") or t["name"], p["file"], t["columns"], t["data"], t["where"])
        store.DATASETS[ds_id]["import_notes"] = t["notes"]
        store.DATASETS[ds_id]["read_removed"] = t.get("read_removed") or {"rows": 0, "totals": {}}
        store.DATASETS[ds_id]["currency"] = t.get("currency") or []
        store.DATASETS[ds_id]["net"] = t.get("net")
        store.DATASETS[ds_id]["date_orders"] = t.get("date_orders") or {}
        made.append(ds_id)
    if choices.get("text", {}).get("include", True):
        for x in p["passages"]:
            store.PASSAGES.append({"source": p["file"], "where": x["where"], "text": x["text"]})
    store.FILES.append(p["file"])
    store.LOG.append({"text": f"Imported {p['file']}: {len(made)} table(s), {len(p['passages'])} text passage(s)."})
    return made
