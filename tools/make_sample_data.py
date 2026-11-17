"""Generates the dummy files in sample-data/. Deterministic (fixed seed).
Run:  python tools/make_sample_data.py
The data is invented. It contains deliberate flaws (duplicates, blanks, typos,
extreme values, unmatched IDs) so the data check has something to find."""
import csv, math, random, datetime as dt
from pathlib import Path
from openpyxl import Workbook
from docx import Document
from pptx import Presentation

OUT = Path(__file__).resolve().parent.parent / "sample-data"
OUT.mkdir(exist_ok=True)
R = random.Random(7)

# ---------------- products
products = [
    ("P01", "Atlas Laptop 14", "Hardware", 620, 980), ("P02", "Atlas Laptop 16", "Hardware", 810, 1290),
    ("P03", "Orbit Monitor 27", "Hardware", 150, 260), ("P04", "Pulse Headset", "Accessories", 28, 65),
    ("P05", "Dock Station Pro", "Accessories", 55, 120), ("P06", "Glide Mouse", "Accessories", 9, 25),
    ("P07", "Ledger Suite (annual)", "Software", 40, 240), ("P08", "Shield Security (annual)", "Software", 22, 150),
    ("P09", "Insight Reports (annual)", "Software", 35, 310), ("P10", "Onboarding Package", "Services", 180, 450),
    ("P11", "Premium Support (annual)", "Services", 90, 380), ("P12", "Training Day", "Services", 240, 600),
]
wb = Workbook(); ws = wb.active; ws.title = "Products"
ws.append(["Product ID", "Product Name", "Category", "Unit Cost", "List Price", "Launch Year"])
for i, (pid, name, cat, cost, price) in enumerate(products):
    ws.append([pid, name, cat, cost, price, 2019 + i % 5])
wb.save(OUT / "products.xlsx")

# ---------------- customers
first = "Harbor Summit Lumen Cedar Nimbus Vertex Beacon Juniper Onyx Quartz Meadow Falcon Ember Tidal Aspen Cobalt Willow Granite Solace Kestrel".split()
second = "Logistics Foods Dental Studio Partners Retail Labs Clinics Travel Robotics Bakery Motors Legal Energy Textiles Media Farms Freight Optics Works".split()
countries = ["Singapore", "Malaysia", "Indonesia", "Thailand", "Vietnam", "Philippines"]
segments = ["Small Business", "Mid-Market", "Enterprise"]
customers = []
for i in range(1, 241):
    seg = R.choices(segments, [55, 30, 15])[0]
    signup = dt.date(2019, 1, 1) + dt.timedelta(days=R.randint(0, 2300))
    tenure = max(1, round((dt.date(2025, 9, 30) - signup).days / 30.4))
    sat = min(10, max(1, round(R.gauss(7, 1.8))))
    tickets = max(0, round(R.gauss(4 - 0.35 * (sat - 7), 2.2)))
    spend = round({"Small Business": 420, "Mid-Market": 1900, "Enterprise": 7400}[seg] * R.uniform(0.6, 1.5), 2)
    z = -3.2 + 0.62 * sat - 0.38 * tickets + 0.022 * tenure + (0.5 if seg == "Enterprise" else 0)
    renewed = "Yes" if R.random() < 1 / (1 + math.exp(-z)) else "No"
    name = f"{first[(i * 7) % 20]} {second[(i * 3 + i // 20) % 20]}" + (f" {i}" if i > 200 else "")
    customers.append([f"C{i:03d}", name, seg, R.choice(countries), signup.isoformat(), tenure, sat, tickets, spend, renewed])
for idx in (11, 57, 102, 160, 201): customers[idx][6] = ""        # blank satisfaction
for idx in (23, 88, 140): customers[idx][2] = "enterprise" if customers[idx][2] == "Enterprise" else customers[idx][2].upper()
customers.insert(60, list(customers[30])); customers.insert(150, list(customers[97]))   # repeated rows
with open(OUT / "customers.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["Customer ID", "Customer Name", "Segment", "Country", "Signup Date", "Tenure Months",
                "Satisfaction Score", "Support Tickets", "Monthly Spend", "Renewed"])
    w.writerows(customers)

# ---------------- orders
regions = ["North", "South", "East", "West"]; rw = [30, 22, 20, 28]
channels = ["Online", "Retail", "Partner"]
season = [0.92, 0.80, 0.95, 1.00, 1.03, 0.97, 0.90, 0.94, 1.05, 1.10, 1.28, 1.38]
rows = []; oid = 10001
months = [(y, m) for y in (2023, 2024, 2025) for m in range(1, 13)][:33]
for k, (y, m) in enumerate(months):
    n = round(42 * (1 + 0.016 * k) * season[m - 1] + R.gauss(0, 2.5))
    for _ in range(n):
        day = R.randint(1, 28)
        p = R.choices(products, [9, 6, 10, 14, 9, 16, 8, 8, 6, 5, 5, 4])[0]
        region = R.choices(regions, rw)[0]
        ch = R.choices(channels, [50, 30, 20] if (y, m) >= (2023, 3) else [62, 38, 0])[0]
        qty = R.choices([1, 2, 3, 4, 5, 8, 10, 20], [30, 22, 14, 10, 9, 7, 5, 3])[0]
        disc = R.choices([0, 5, 10, 15], [55, 20, 17, 8])[0]
        cust = f"C{R.randint(1, 240):03d}"
        amount = round(qty * p[4] * (1 - disc / 100), 2)
        rows.append([f"SO-{oid}", dt.date(y, m, day), cust, p[0], region, ch, qty, p[4], disc, amount]); oid += 1
rows.sort(key=lambda r: r[1])
for i, r in enumerate(rows): r[0] = f"SO-{10001 + i}"
pick = R.sample(range(len(rows)), 90)
for i in pick[:9]: rows[i][4] = rows[i][4].lower()
for i in pick[9:15]: rows[i][4] = rows[i][4].upper() + " "
for i in pick[15:19]: rows[i][4] = {"North": "Nroth", "South": "Sout", "East": "Eest", "West": "Wst"}[rows[i][4]]
for i in pick[19:33]: rows[i][8] = None                                   # blank discount
for i in pick[33:36]: rows[i][6] = R.choice([600, 750, 900]); rows[i][9] = round(rows[i][6] * rows[i][7], 2)
rows[pick[36]][6] = -3; rows[pick[36]][9] = round(-3 * rows[pick[36]][7], 2)  # negative quantity
for i in pick[37:71]: rows[i][2] = f"C9{R.randint(10, 99)}"                # customers not on the list
rows[pick[71]][1] = dt.date(2052, 3, 14)                                  # typo date
rows[pick[72]][8] = "n/a"; rows[pick[73]][8] = "tbc"
for i in pick[74:82]: rows.append(list(rows[i]))                           # exact repeats
wb = Workbook(); ws = wb.active; ws.title = "Orders"
ws.append(["Order ID", "Order Date", "Customer ID", "Product ID", "Region", "Channel",
           "Quantity", "Unit Price", "Discount %", "Sales Amount"])
for r in rows: ws.append(r)
for c in ws["B"][1:]: c.number_format = "yyyy-mm-dd"
ws2 = wb.create_sheet("Notes")
ws2["A1"] = "Export from the order system. Sales Amount = Quantity x Unit Price less discount."
wb.save(OUT / "sales_orders.xlsx")

# ---------------- word document
d = Document()
d.add_heading("Q3 2025 Business Review", 0)
for t in [
    "Summary. Sales continued to grow through the third quarter of 2025, led by the North and West regions. November and December remain the strongest months each year because of year-end budget spending.",
    "Returns policy. Customers may return hardware within 30 days of delivery for a full refund. Software subscriptions can be cancelled within 14 days. Services are not refundable once delivered.",
    "Discount policy. Sales staff may offer up to 10 percent discount without approval. A 15 percent discount needs sign-off from the regional manager. Discounts above 15 percent are not allowed.",
    "Partner channel. The Partner channel was launched in March 2023 and is managed by Priya Raman. Partners receive a 12 percent commission on every order they bring in.",
    "Customer renewals. The renewal target for 2025 is 80 percent. Customers with a satisfaction score below 6 are contacted by the customer success team within one week.",
    "Risks. Supplier delays for Orbit Monitor 27 may limit hardware availability in the fourth quarter. The team is qualifying a second supplier in Vietnam.",
]:
    d.add_paragraph(t)
d.add_heading("Regional sales targets for 2025", 1)
t = d.add_table(rows=1, cols=3); t.style = "Table Grid"
for c, h in zip(t.rows[0].cells, ["Region", "Sales Target 2025", "Regional Manager"]): c.text = h
for row in [("North", "215000", "Daniel Okafor"), ("South", "190000", "Mei Lin Tan"), ("East", "165000", "Arjun Mehta"), ("West", "240000", "Sofia Alvarez")]:
    for c, v in zip(t.add_row().cells, row): c.text = v
d.save(OUT / "q3_business_review.docx")

# ---------------- powerpoint
p = Presentation()
def slide(title, bullets):
    s = p.slides.add_slide(p.slide_layouts[1]); s.shapes.title.text = title
    tf = s.placeholders[1].text_frame; tf.text = bullets[0]
    for b in bullets[1:]: tf.add_paragraph().text = b
slide("2026 Strategy Update", ["Prepared for the leadership meeting", "Draft for discussion"])
slide("Three priorities for 2026", ["Grow software subscriptions to 40 percent of total sales",
      "Expand the Partner channel into the Philippines and Vietnam", "Raise customer renewals from 80 percent to 85 percent"])
slide("Pricing", ["List prices rise by 4 percent on 1 February 2026", "Premium Support stays at its current price",
      "The maximum discount stays at 15 percent"])
slide("Hiring plan", ["Six new account managers, two in each of North, West and South", "One data analyst to support forecasting",
      "Hiring budget approved by Helena Brandt, Chief Financial Officer"])
p.save(OUT / "strategy_update.pptx")
print("orders", len(rows), "customers", len(customers))

# ---------------- overseas sales: amounts in more than one currency (shows the mixed-currency stop)
R2 = random.Random(11)
overseas = []
for m in range(1, 10):
    for k in range(8):
        country, code, scale = R2.choice([("Malaysia", "RM", 4.4), ("Singapore", "SGD", 1.3), ("Indonesia", "USD", 1), ("Thailand", "USD", 1)])
        day = dt.date(2025, m, 28 if k == 7 else R2.randint(1, 27)) + dt.timedelta(days=2 if (m == 9 and k == 7) else 0)
        overseas.append([day.isoformat(), country, f"{R2.choice(first)} {R2.choice(second)}", f"{code} {round(R2.uniform(300, 2500) * scale):,}"])
with open(OUT / "overseas_sales.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["Invoice Date", "Country", "Customer", "Amount"])
    w.writerows(sorted(overseas))
