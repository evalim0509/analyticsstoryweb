"""End-to-end check of the Python engine on the sample data.  Run:  python tools/test_engine.py"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine import api

def call(fn, **kw):
    blob = kw.pop("data", None)
    r = json.loads(api.dispatch(fn, json.dumps(kw), blob))
    assert r["ok"], r
    return r["result"]

for f in ["sales_orders.xlsx", "customers.csv", "products.xlsx", "q3_business_review.docx", "strategy_update.pptx"]:
    p = call("preview", name=f, data=(ROOT / "sample-data" / f).read_bytes())
    assert "token" in p, p
    st = call("confirm", token=p["token"])
ID = {d["name"]: d["id"] for d in st["datasets"]}
assert st["datasets"][0]["rows"] == 1783 and len(st["documents"]) == 3
kinds = {i["key"] for i in call("check", dataset=ID["Orders"])["issues"]}
assert {"duplicates:", "spelling:Region", "unusual:Quantity", "dates:Order Date", "missing:Discount %"} <= kinds, kinds
r = call("fix_all", dataset=ID["Orders"]); assert len(r["done"]) >= 2
for key in ("spelling:Region", "unusual:Quantity", "negative:Quantity"):
    call("fix", dataset=ID["Orders"], key=key)
call("fix_all", dataset=ID["Customers"])
j = {(s["a_name"], s["b_name"]): s for s in call("state")["joins"]}
assert j[("Orders", "Customers")]["match"] > 95 and j[("Orders", "Customers")]["confidence"] == "High"
call("accept_join", key=j[("Orders", "Customers")]["key"])
st = call("accept_join", key=j[("Orders", "Products")]["key"])["state"]
linked = next(d for d in st["datasets"] if d["kind"] == "linked")
assert linked["name"] == "Orders + Customers + Products" and linked["rows"] == next(d for d in st["datasets"] if d["name"] == "Orders")["rows"]
a = call("ask", question="total sales by region"); assert a["type"] == "table" and len(a["table"]["rows"]) == 4, a["table"]
a = call("ask", question="total sales amount by category"); assert a["dataset"] == linked["id"] and len(a["table"]["rows"]) == 4
a = call("ask", question="sales by segment in 2024"); assert a["dataset"] == linked["id"]
a = call("ask", question="what is the returns policy"); assert a["type"] == "text" and "30 days" in a["passages"][0]["text"]
a = call("ask", question="what is the weather today"); assert a["type"] == "not_found"
a = call("ask", question="how many customers renewed"); assert a["table"]["rows"][0][0] == 145, a["table"]
b = call("build", spec=a["builder"]); assert b["rows"][0][0] == 145
x = call("export", spec={"dataset": ID["Orders"], "rows": [{"field": "Region"}], "values": [{"field": "Sales Amount", "agg": "sum"}]}); assert len(x["base64"]) > 1000
f = call("ml_run", kind="forecast", spec={"dataset": ID["Orders"], "value": "Sales Amount"}); assert f["reliability"]["score"] > 70 and len(f["forecast"]) == 6
assert call("ask", question="how accurate is this", context={"kind": "ml", "id": f["id"]})["type"] == "ml_note"
d = call("ml_run", kind="drivers", spec={"dataset": ID["Customers"], "target": "Renewed"}); assert d["importance"][0]["name"] == "Satisfaction Score"
assert "Predicted" in call("ml_predict", result=d["id"], inputs={"Satisfaction Score": 2})["text"]
assert len(call("ml_run", kind="segments", spec={"dataset": ID["Customers"]})["groups"]) >= 2
assert call("ml_run", kind="unusual", spec={"dataset": ID["Orders"]})["table"]["rows"]
call("set_glossary", entries=[{"term": "takings", "means": "Sales Amount"}])
assert call("ask", question="total takings")["type"] == "number"
o = call("story_options"); assert o["options"][0]["label"] == "Sales Amount", o
s6 = call("story_build", spec={"dataset": o["options"][0]["dataset"], "value": "Sales Amount"})
K = {c["key"]: c for c in s6["cards"]}
assert list(K) == ["what", "who", "when", "which", "why", "how"] and all(c["sentence"] for c in s6["cards"])
assert s6["period"] == "quarter" and "target" in " ".join(K["what"]["more"]) and K["how"]["actions"]
assert "led by" in K["why"]["sentence"] and abs(sum(r[3] for r in K["why"]["table"]["rows"]) - (K["what"]["table"]["rows"][0][1] - K["what"]["table"]["rows"][1][1])) < 0.01
assert K["what"]["mood"] == "bad" and K["why"]["mood"] == "bad" and K["when"]["mood"] in ("good", "bad") and K["who"]["mood"] == K["how"]["mood"] == "neutral", {k: c["mood"] for k, c in K.items()}
assert any(a.get("estimate") for a in K["how"]["actions"]) and {m["value"] for m in s6["measures"]} >= {"Sales Amount", "Quantity", None}
n = call("story_build", spec={"dataset": o["options"][0]["dataset"], "value": None, "period": "month", "filters": [{"field": "Region", "op": "is", "value": ["North"]}]})
assert "Region" not in next(c for c in n["cards"] if c["key"] == "which")["dims"] and "North" in n["title"]
x = call("story_build", spec={"dataset": o["options"][0]["dataset"], "value": "Quantity", "fiscal_start": 4, "why": "Region", "charts": {"who": "share", "when": "bars", "why": "before"}})
X = {c["key"]: c for c in x["cards"]}
assert "Quantity" in X["who"]["sentence"] and X["who"]["chart"]["type"] == "share" and X["why"]["dim"] == "Region" and len(X["why"]["chart"]["series"]) == 2
assert "target" not in " ".join(X["what"]["more"]) and not any("target" in a["do"] for a in X["how"]["actions"])   # a sales target is not applied to Quantity
assert x["period_label"].startswith("Q2 (Jul–Sep") and x["spec"]["fiscal_start"] == 4
# a table with no dates and nothing to group by: only What and How are told
p = call("preview", name="plain.csv", data=b"Ref,Amount\n" + b"".join(f"R{i},{i * 3}\n".encode() for i in range(1, 41)))
plain = call("confirm", token=p["token"])["datasets"][-1]
assert [c["key"] for c in call("story_build", spec={"dataset": plain["id"], "value": "Amount"})["cards"]] == ["what", "how"]
call("restore", dataset=ID["Orders"]); assert call("state")["datasets"][0]["rows"] == 1783

# --- quick checks, averages, derived measures, reconciliation
chk = call("story_checks")["tables"][0]
kinds = {m["name"]: m["kind"] for m in chk["measures"]}
assert kinds["Unit Price"] == "rate" and kinds["Sales Amount"] == "money" and chk["date"] == "Order Date" and chk["complete"] is True, chk
labels = [x["label"] for x in call("story_options")["options"]]
assert {"Margin", "Margin %", "Average order value", "Average Unit Price"} <= set(labels), labels
ds0 = call("story_options")["options"][0]["dataset"]
mp = call("story_build", spec={"dataset": ds0, "value": "calc:margin_pct"})
assert "points" in mp["cards"][0]["sentence"] and "%" in mp["cards"][0]["sentence"] and "why" not in [c["key"] for c in mp["cards"]]
assert any("Margin %" in st for st in mp["cards"][0]["steps"])            # the formula is shown in How I got this
av = call("story_build", spec={"dataset": ds0, "value": "Unit Price"})
assert av["label"] == "Average Unit Price" and "highest" in av["cards"][1]["sentence"] and "Share (%)" not in av["cards"][1]["table"]["columns"]
sa = call("story_build", spec={"dataset": ds0, "value": "Sales Amount"})
assert "matching the file" in sa["reconcile"]["line"] or "removed rows" in sa["reconcile"]["line"], sa["reconcile"]
assert sa["reconcile"]["steps"][0][1] == 1783
# the owner's answers win: say Sales Amount is a rate, then change it back
call("story_set_checks", answers=[{"dataset": chk["dataset"], "kinds": {"Sales Amount": "rate"}}])
assert call("story_build", spec={"dataset": ds0, "value": "Sales Amount"})["label"] == "Average Sales Amount"
call("story_set_checks", answers=[{"dataset": chk["dataset"], "kinds": {"Sales Amount": "money"}, "complete": False}])
lm = call("story_build", spec={"dataset": ds0, "value": "Sales Amount", "period": "month"})
assert lm["period_label"] == "Aug 2025" and any("still running" in n for n in lm["cards"][0]["steps"]), lm["period_label"]
call("story_set_checks", answers=[{"dataset": chk["dataset"], "complete": True}])
# a measure the owner makes
mine = call("measure_add", dataset=ds0, name="Sales per unit", a="Sales Amount", op="divide", b="Quantity")
assert mine["added"]["label"] in [x["label"] for x in call("measure_list", dataset=ds0)["mine"]]
assert call("story_build", spec={"dataset": ds0, "value": mine["added"]["value"]})["label"] == "Sales per unit"

# monthly data dated on the 1st keeps its latest month; identical rows without an ID are only flagged
csv = "Month,Region,Revenue\n" + "".join(f"2024-{m:02d}-01,{r},{100 + m * 10 + i}\n" for m in range(1, 13) for i, r in enumerate(["North", "South"]))
csv += "2024-12-01,North,220\n"           # an exact repeat, no ID column
p = call("preview", name="monthly.csv", data=csv.encode()); mon = call("confirm", token=p["token"])["datasets"][-1]
mo = call("story_build", spec={"dataset": mon["id"], "value": "Revenue", "period": "month"})
assert mo["period_label"] == "Dec 2024", mo["period_label"]
dup = next(i for i in call("check", dataset=mon["id"])["issues"] if i["kind"] == "duplicates")
assert dup["confidence"] == "Medium", dup

# --- accounting export templates (dummy files in each system's standard layout)
ACC = ROOT / "sample-data" / "accounting"
want = {"xero_invoices.csv": ("Xero", 40), "quickbooks_sales_by_customer.xlsx": ("QuickBooks", 24), "autocount_sales_listing.xlsx": ("AutoCount", 30),
        "sqlaccount_sales.csv": ("SQL Account", 30), "sap_b1_ar_invoices.xlsx": ("SAP Business One", 25),
        "sage_nominal_activity.csv": ("Sage", 16), "myob_general_ledger.csv": ("MYOB", 14)}
for f, (tpl, n) in want.items():
    t = call("preview", name=f, data=(ACC / f).read_bytes())["tables"][0]
    assert t["template"] == tpl and t["rows"] == n, (f, t["template"], t["rows"])
qb = call("preview", name="qb.xlsx", data=(ACC / "quickbooks_sales_by_customer.xlsx").read_bytes())["tables"][0]
names = [c["name"] for c in qb["columns"]]
assert names[0] == "Customer" and "Accrual" not in str(qb["sample"]) and all(r[0] for r in qb["sample"]), qb["sample"][:2]
amt = names.index("Amount")
import openpyxl
qb_total = next(r[8] for r in openpyxl.load_workbook(ACC / "quickbooks_sales_by_customer.xlsx").active.iter_rows(values_only=True) if r[0] == "TOTAL")
qb_total = _n = float(str(qb_total).replace(",", "").replace("(", "-").replace(")", ""))
qb_ds = call("confirm", token=call("preview", name="qb.xlsx", data=(ACC / "quickbooks_sales_by_customer.xlsx").read_bytes())["token"])["datasets"][-1]
from engine import store as _st
qb_sum, qb_min = _st.rows(f'SELECT TOTAL("Amount"), MIN("Amount") FROM "{_st.DATASETS[qb_ds["id"]]["table"]}"')[0]
assert abs(qb_sum - qb_total) < 0.01 and qb_min < 0, (qb_sum, qb_total, qb_min)        # totals match the report; credit memos are negative
sage = call("preview", name="sage.csv", data=(ACC / "sage_nominal_activity.csv").read_bytes())["tables"][0]
assert "Net amount" in [c["name"] for c in sage["columns"]] and "Recognised an export from Sage" in sage["notes"][0]["text"]
ac = call("preview", name="ac.xlsx", data=(ACC / "autocount_sales_listing.xlsx").read_bytes())["tables"][0]
assert next(c for c in ac["columns"] if c["name"] == "Total")["type"] == "number"          # "RM 1,234.00" read as a number
from engine import store as _st
assert _st.parse_number("(1,234.50)") == -1234.5 and _st.parse_number("1,234.00 Cr") == -1234 and _st.parse_number("RM 2,000") == 2000 and _st.parse_number("$1,500.25") == 1500.25
print("All engine checks passed.")
