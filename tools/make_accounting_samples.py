"""Dummy exports in the standard layouts of common accounting systems, for testing the
import templates. All names and figures are invented.  Run:  python tools/make_accounting_samples.py"""
import csv, random, datetime as dt
from pathlib import Path
import openpyxl

OUT = Path(__file__).resolve().parent.parent / "sample-data" / "accounting"
OUT.mkdir(parents=True, exist_ok=True)
R = random.Random(7)
CUSTOMERS = ["Harbour Cafe", "Nimbus Clinics", "Orchid Florist", "Summit Optics", "Tidewater Books"]
ITEMS = [("Design hours", 120.0), ("Printing", 45.5), ("Consulting", 200.0), ("Delivery", 18.0)]


def days(n, start=dt.date(2025, 1, 2)):
    return sorted(start + dt.timedelta(days=R.randint(0, 88)) for _ in range(n))


def money(v):
    return f"({abs(v):,.2f})" if v < 0 else f"{v:,.2f}"


def write_xlsx(name, rows):
    wb = openpyxl.Workbook(); ws = wb.active
    for r in rows:
        ws.append(r)
    wb.save(OUT / name)


# 1. Xero: sales invoice export (CSV, CamelCase headers, required columns marked with *)
with open(OUT / "xero_invoices.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["*ContactName", "EmailAddress", "*InvoiceNumber", "Reference", "*InvoiceDate", "*DueDate", "Total", "*Description",
                "*Quantity", "*UnitAmount", "LineAmount", "*AccountCode", "*TaxType", "TaxAmount", "Currency"])
    for i, d in enumerate(days(40)):
        item, price = R.choice(ITEMS); qty = R.randint(1, 8)
        w.writerow([R.choice(CUSTOMERS), "accounts@example.com", f"INV-{1001 + i}", f"PO{R.randint(100, 999)}", d.strftime("%d/%m/%Y"),
                    (d + dt.timedelta(days=30)).strftime("%d/%m/%Y"), f"{qty * price * 1.08:.2f}", item, qty, f"{price:.2f}", f"{qty * price:.2f}",
                    "200", "Tax on Sales", f"{qty * price * .08:.2f}", "MYR"])

# 2. QuickBooks: Sales by Customer Detail report (title rows, customer headings, Total for rows, footer)
rows = [["Craig's Design and Landscaping"], ["Sales by Customer Detail"], ["January - March, 2025"], [],
        [None, "Date", "Transaction Type", "Num", "Product/Service", "Memo/Description", "Qty", "Sales Price", "Amount", "Balance"]]
grand = 0
for c in CUSTOMERS[:4]:
    rows.append([c]); bal = 0
    for d in days(6):
        item, price = R.choice(ITEMS); qty = R.randint(1, 5); amt = qty * price
        if R.random() < .1:
            amt = -amt
        bal += amt
        rows.append([None, d.strftime("%m/%d/%Y"), "Invoice" if amt > 0 else "Credit Memo", str(R.randint(1000, 1999)), item, item.lower(), qty, price, money(amt), money(bal)])
    rows.append([f"Total for {c}", None, None, None, None, None, None, None, money(bal), None]); grand += bal
rows += [["TOTAL", None, None, None, None, None, None, None, money(grand), None], [], ["Accrual Basis Monday, April 7, 2025 09:12 AM GMT+08:00"]]
write_xlsx("quickbooks_sales_by_customer.xlsx", rows)

# 3. AutoCount: Sales Invoice Listing (Malaysia; RM amounts as text, Grand Total row)
rows = [["ABC Trading Sdn Bhd"], ["Sales Invoice Listing"], ["Date From 01/01/2025 To 31/03/2025"], [],
        ["Doc. No.", "Doc. Date", "Debtor Code", "Debtor Name", "Agent", "Area", "Total", "Tax", "Net Total"]]
gt = 0
for i, d in enumerate(days(30)):
    c = R.randrange(len(CUSTOMERS)); tot = round(R.uniform(200, 4000), 2); tax = round(tot * .06, 2)
    rows.append([f"IV-{25001 + i}", d.strftime("%d/%m/%Y"), f"300-{c + 1:03d}", CUSTOMERS[c].upper(), R.choice(["ALI", "MEI LING", "RAJ"]),
                 R.choice(["KL", "PENANG", "JB"]), f"RM {tot:,.2f}", f"{tax:,.2f}", f"{tot + tax:,.2f}"]); gt += tot
rows.append(["Grand Total", None, None, None, None, None, f"RM {gt:,.2f}", None, None])
write_xlsx("autocount_sales_listing.xlsx", rows)

# 4. SQL Account: sales document listing (CSV, credit notes in brackets)
with open(OUT / "sqlaccount_sales.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Doc No", "Doc Date", "Code", "Company Name", "Agent", "Area", "Description", "Amount", "Local Amount"])
    for i, d in enumerate(days(30)):
        c = R.randrange(len(CUSTOMERS)); amt = round(R.uniform(150, 3000), 2)
        if R.random() < .15:
            amt = -amt
        w.writerow([("CN-" if amt < 0 else "IV-") + str(5001 + i), d.strftime("%d/%m/%Y"), f"300-{c + 1:04d}", CUSTOMERS[c], "----", "KL",
                    "Credit note" if amt < 0 else "Sales", money(amt), money(amt)])

# 5. SAP Business One: A/R invoice lines
rows = [["Document Number", "Posting Date", "Customer/Vendor Code", "Customer/Vendor Name", "Item No.", "Item Description", "Quantity", "Row Total", "Document Total"]]
for i, d in enumerate(days(25)):
    c = R.randrange(len(CUSTOMERS)); item, price = R.choice(ITEMS); qty = R.randint(1, 10)
    rows.append([700 + i, d, f"C{2000 + c}", CUSTOMERS[c], f"A{R.randint(100, 999)}", item, qty, round(qty * price, 2), round(qty * price, 2)])
write_xlsx("sap_b1_ar_invoices.xlsx", rows)

# 6. Sage 50: Nominal Activity (title rows, account headings, Totals rows, debit and credit)
with open(OUT / "sage_nominal_activity.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerows([["Wizard Training Limited"], ["Nominal Activity"], ["Date From: 01/01/2025 Date To: 31/03/2025"], []])
    w.writerow(["N/C", "Tran No.", "Type", "Date", "Ref", "Details", "Net", "Tax", "T/C", "Debit", "Credit"])
    for acct in ["4000 Sales Type A", "5000 Costs of Sales"]:
        w.writerow([acct]); dr = cr = 0
        for i, d in enumerate(days(8)):
            v = round(R.uniform(100, 900), 2)
            if acct.startswith("4"):
                w.writerow([acct[:4], 300 + i, "SI", d.strftime("%d/%m/%Y"), f"S{i}", "Sales", f"{v:.2f}", f"{v * .2:.2f}", "T1", "", f"{v:.2f}"]); cr += v
            else:
                w.writerow([acct[:4], 400 + i, "PI", d.strftime("%d/%m/%Y"), f"P{i}", "Purchases", f"{v:.2f}", f"{v * .2:.2f}", "T1", f"{v:.2f}", ""]); dr += v
        w.writerow(["", "", "", "", "", "Totals:", "", "", "", f"{dr:.2f}", f"{cr:.2f}"])

# 7. MYOB: general ledger detail (account headings, $ amounts, Total rows)
with open(OUT / "myob_general_ledger.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["ID No.", "Src", "Date", "Memo", "Debit", "Credit", "Job No."])
    for acct in ["4-1000 Sales", "6-1100 Advertising"]:
        w.writerow([acct]); dr = cr = 0
        for i, d in enumerate(days(7)):
            v = round(R.uniform(50, 1500), 2)
            if acct.startswith("4"):
                w.writerow([f"{8000 + i}", "SJ", d.strftime("%d/%m/%Y"), "Sale; " + R.choice(CUSTOMERS), "", f"${v:,.2f}", ""]); cr += v
            else:
                w.writerow([f"{9000 + i}", "CD", d.strftime("%d/%m/%Y"), "Online ads", f"${v:,.2f}", "", ""]); dr += v
        w.writerow(["Total:", "", "", "", f"${dr:,.2f}", f"${cr:,.2f}", ""])
print("Wrote", len(list(OUT.iterdir())), "files to", OUT)
