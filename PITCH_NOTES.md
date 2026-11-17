# Gist: pitch notes

A private reference for pitching Gist. It lists what is strong, what is weak, what
is broken today, and how to answer the questions prospects will ask.
Last reviewed: 2026-11-17, against `main` at commit 511d4a4.

> **This repository is public.** Anyone can read this file, including the weaknesses
> below. Make the repository private, or move this file out of it, before sharing
> the link with anyone outside the team.

---

## 1. What Gist is, in one line

**Drop in your month-end export and get the board briefing: every sentence is
worked out, not written by AI, and your file never leaves your laptop.**

- **Category:** a private monthly briefing writer. Not BI, not an AI chatbot.
- **Buyer (working hypothesis):** finance or operations manager at a 20–200-person
  company with no BI team, using AutoCount, SQL Account, Xero or QuickBooks.
- **Reader:** the owner, CEO or management team who receives the briefing.

---

## 2. Strengths to lead with

| Strength | Why it matters to a buyer | How to show it |
|---|---|---|
| Runs entirely in the browser; no server, no upload | Confidential figures never reach a vendor. Nothing to approve with IT. Fits PDPA-minded customers. | Open the browser's network tab during the demo. (Once Pyodide is self-hosted: switch the wifi off.) |
| No AI writes the sentences | The numbers can't be made up. Same file, same answers. | Open "How I got this" on any card. |
| Every figure is traceable | Each card shows its steps and the SQL behind them. The reconciliation runs from the file as read to the number on screen. | Show the reconciliation line at the foot of the story. |
| Cards are hidden when the data can't support them | Gist doesn't pad the briefing or guess. | Load a file with no dates: the When card disappears. |
| Story first: What, Who, When, Which, Why, How | An executive gets the point in under a minute, without a dashboard to learn. | Read three cards aloud. |
| Accounting exports recognised | Title rows, group headings and subtotal rows from Xero, QuickBooks, AutoCount, SQL Account, SAP B1, Sage and MYOB are tidied, and debit/credit is combined. | Drop an AutoCount export. **Call it "in pilot"** (see section 4). |
| Saved field catalogues | The second month takes one tap: "I used your Accounting catalogue". | Load a second file with the same columns. |
| Guard rails | Mixed currencies are blocked; margin is worked out only where cost is known, with coverage stated; day/month order is shown; identical rows are removed only when there's an ID column. | Load `overseas_sales.csv` from the sample set. |
| Briefing exports | PDF, PowerPoint (workings in the speaker notes), email draft and copy-for-email. | Export the PDF live. |
| Preparer's notes | The human adds the reasons; Gist keeps the facts. The two are clearly labelled. | Add a note and export it. |
| No setup, no licence prerequisites | Works the first minute, unlike tools that need a data warehouse or capacity licences. | Time the demo. |

---

## 3. Weaknesses to know, and say honestly if asked

| Weakness | Honest answer | Plan |
|---|---|---|
| Nothing is saved between visits (by design) | "Your data is gone when you close the tab. Field matches and the last briefing's headline figures are kept on your computer only." | Optional encrypted local workspace, later. |
| One file at a time, no live connection to the accounting system | "It works from the export you already run at month-end." | Watch-folder or desktop app later. |
| Ask (chat) matches words, not meaning | "It searches your files; it isn't ChatGPT." Don't demo it. | Rename or remove. |
| Forecast is simple and can be weak with short history | "It's labelled as an estimate with a reliability score." | Require 24+ months for seasonal data. |
| PDF can't print Chinese or other non-Latin names | "Slides and email are fine; the PDF uses standard fonts." | Embed a font. |
| Browser memory limits large files | "Comfortable up to a few hundred thousand rows." **Not measured yet.** | Run a performance test before claiming a number. |
| First load downloads the Python engine from a CDN | "The engine is downloaded; your data is not." | Self-host Pyodide and remove the CDN from the security policy. |
| Accounting templates are built from documented layouts, not real customer files | "In pilot: we'll check it against your export." | Collect 10 real exports. |
| No accounts, licensing or payment yet | "Concept stage; pilot pricing on request." | Decide hosted vs desktop first. |
| No licence file; code is public | Don't bring it up; fix it before pitching. | Make the repo private, add a licence. |
| General-ledger stories are unreliable today | Don't demo a GL file. | See bug B4 below. |

---

## 4. Known bugs. Fix these before any demo with a prospect's own file

Found on 2026-11-17 by running the engine against test files.

- **B1. "$" next to "RM" is treated as one currency.** A column holding "$1,000"
  and "RM 500" raises no warning and is added together. The rule meant for
  "$" beside "USD" applies to any single other code.
- **B2. Unreadable amounts disappear without the reconciliation noticing.** Up to 10% of cells in
  a number column can be unreadable (for example "5,000 refund", or European
  "1.000,50"). They become blank, step 1 mentions it once, and the
  reconciliation still says "matching the file".
- **B3. A repeated sale of a product with "Total" in its name is dropped as a
  subtotal** in recognised exports. Two consecutive "Total Gym Pro" lines at
  1,200: the second matches "the sum of the rows above" and is removed.
- **B4. Ledger stories are nonsense, including the bundled Sage sample.** It reads
  "Net amount reached -843", "accounted for -495% of Net amount", "fallen by
  about 4346% a year over the 3 months". Causes: income and cost accounts are
  netted into one number, shares are worked out on a total close to zero, and a
  3-month trend is turned into a yearly rate.
- **B5. Mixed currencies are blocked only in the story.** Ask and Tables & charts still
  add them together.

---

## 5. Competitors and how Gist differs

Checked November 2026. Re-check before each pitch; these products change often.

| | Gist | Power BI Copilot | Tableau Pulse | Julius |
|---|---|---|---|---|
| Plain-language summary of what changed | Yes, fixed rules | Yes, generative AI | Yes, generative AI | Yes, generative AI |
| Setup needed | None, drop a file | Paid Fabric capacity (F2+) or Premium, and a semantic model | Tableau Cloud and its metrics layer | Account, upload |
| Where data goes | Stays in the browser | Microsoft cloud | Salesforce / Tableau cloud | Julius servers; reportedly shared with AI providers by default (opt-out by email) |
| Can it invent a sentence? | No | Possible | Possible | Possible |
| Traceability | Every card: steps + SQL + reconciliation | Partial | Partial | Shows code |
| Best for | Confidential monthly briefing from an export | Companies already on Fabric | Companies already on Tableau | Ad-hoc analysis |

Sources:
- [Power BI Copilot requirements – EPC Group](https://www.epcgroup.net/power-bi-copilot-enterprise-analytics)
- [Tableau Pulse and the metrics layer – SalesforceDevops](https://salesforcedevops.net/?p=38573)
- [Julius data sharing – Stork](https://www.stork.ai/blog/best-ai-for-data-analysis-2026)

**Line to use:** "If you already run Power BI on Fabric, use Copilot. If you have an
export, a deadline and figures you won't upload anywhere, use Gist."

---

## 6. Questions prospects will ask, and answers

**"Can I trust the numbers?"**
Every card has "How I got this", with the exact steps and query. The reconciliation
shows rows and totals from the file to the figure. Gist leaves a card out rather
than guess. *(Once B2 is fixed:)* any amount it couldn't read is shown in the
reconciliation.

**"Who sees my data?"**
Nobody. It's processed in this browser tab and erased when you close it. Exports
are created on your computer and go only where you send them.

**"Is this AI?"**
No. Every sentence comes from fixed templates filled with calculated figures. That's
why it can't invent a reason or a number.

**"Why did sales drop?"**
Gist shows *where* the change came from (which customers, products, regions). It
won't make up *why*, because your files don't record that. The preparer's note is
where your team adds the reason.

**"My export is messy."**
Recognised exports are tidied automatically, and every removed row is shown in the
reconciliation. For anything else, the field-matching step lets you point Gist at
the right columns once and save it.

**"What does it cost?"**
Concept stage. Have a range ready (per preparer per month, or per company per
year) and offer a 3-month-end pilot.

**"What happens when the file is huge?"**
Don't quote a number until it's been measured.

**"Can it connect to AutoCount / Xero directly?"**
Not yet; it works from the export you already run.

---

## 7. Demo script (5 minutes)

1. **The pain (30 s).** "Month-end: the boss asks why sales are down; someone loses
   two days in Excel."
2. **Drop the file (60 s).** Use the prospect's own export, rehearsed beforehand. Network tab open.
3. **Match your fields (30 s).** One tap on "Looks right".
4. **Read the story (90 s).** What → Why → How. Open "How I got this" once.
5. **Trust (30 s).** Point to the reconciliation line.
6. **Share (30 s).** Export the PDF and show the speaker notes in the slides.
7. **Next month (30 s).** "Next time it's one tap, and it tells you what changed
   since this briefing."
8. **Ask.** A pilot over three month-ends.

**Don't demo:** Ask, Predictions, general-ledger files, non-Latin names in PDF.

---

## 8. Don't claim

- "Supports Xero / QuickBooks / AutoCount …": say "recognises their standard exports, in pilot".
- "Works offline": not true until Pyodide is self-hosted.
- "Handles millions of rows": not measured.
- "Explains why": it shows where the change came from, not the cause.
- "Bank-grade security" or any certification: there is none.
- "Nothing is stored": catalogues, business words and the last briefing's headline
  figures are kept in the browser's local storage.

---

## 9. Before the first prospect meeting

- [ ] Fix B1–B5.
- [ ] Self-host Pyodide; remove cdn.jsdelivr.net from the security policy; test with wifi off.
- [ ] Make the repository private, or add a deliberate licence plus third-party notices.
- [ ] Get 10 real exports from 3–5 friendly businesses; check each against their own Excel pivot.
- [ ] Run a performance test at 100k and 500k rows and record the results.
- [ ] One-page security and data note: where code runs, what's stored, retention, what leaves the device.
- [ ] A pricing range and pilot terms.
- [ ] A "decision support, not financial advice" disclaimer in the footer and the exports.
- [ ] Rehearse the demo with the prospect's own file.
