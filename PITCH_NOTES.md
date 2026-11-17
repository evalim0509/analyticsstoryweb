# Gist: pitch notes

A private reference for pitching Gist. It lists what is strong, what is weak, what
is broken today, who else is in the market, and how to answer prospects.

**This file is kept up to date.** Every review or working session that changes
what we know about Gist (a fix, a new weakness, a competitor, a decision) updates
it in the same change. See "How this file is maintained" at the end.

Last updated: 2026-11-17, against `main` at commit 511d4a4.

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
- **The gap Gist fills:** management-reporting tools for accounting data are
  cloud-connected and increasingly AI-written. Private, in-browser tools exist,
  but they are built for analysts. Nobody combines the three: **no upload, no AI
  writing the sentences, and a finished briefing for a non-analyst.** See section 6.

---

## 2. Key points from the review sessions (2026-11-17)

The record of what three rounds of review found, so nothing has to be re-discovered.

### Review 1: the idea
- The real user is the **preparer** (finance manager, analyst, EA); the executive
  is the **reader**. Design for both.
- A one-off file-drop tool is a toy; **monthly use** is the business. That led to
  catalogues, "since your last briefing" and exports.
- Effort had gone into motion and visuals (orb, waves, glass) while accuracy
  questions were open. Artificial waiting screens ("so the work feels thorough")
  undercut the honesty pitch.
- Executives think in **ratios** (margin, average order value), not only totals.
  That led to derived measures.
- The **printed or exported briefing** is the real deliverable for executives.

### Review 2: the accuracy round
Fixed after this review: reconciliation line, quick checks, month-end by the
calendar, averages for rates, duplicate removal only with an ID column, derived
measures, preparer's notes, PDF/PowerPoint/email exports, accounting templates,
data catalogues.

The new accounting cleanup then caused the worst bug so far: it ran on **every**
file. It deleted a sale named "Total Gym Pro" as a "subtotal" and shifted rows
under the wrong headers, while the reconciliation said "matching the file".

### Review 3: Part A fixes (A1–A8), verified
Fixed and checked:
- report cleanup runs only for recognised exports
- the reconciliation starts from the file as read
- mixed currencies (RM + USD) are blocked
- you choose which of debit/credit counts as positive
- margin is worked out only where cost exists, with coverage shown
- ambiguous day/month dates are shown and can be changed
- "since last" is keyed on the whole story
- field matches know their table

Still open: bugs B1–B5 (section 5).

### How a software developer would question Gist
- Where are the tests on **real** files? The templates are built from documented
  layouts, not real exports.
- Why do pattern-matching rules keep growing (currencies, totals, IDs, templates)? What's the single rule
  that stops amounts disappearing?
- State lives in global variables and the UI is one large file. How does it scale to a team?
- Performance at 100k–500k rows: not measured.
- Proving "nothing leaves the browser": the security policy still allows
  `unsafe-eval` and connections to cdn.jsdelivr.net; Pyodide isn't self-hosted.
- No LICENSE file in a public repo; third-party notices missing.
- Releases are manual version bumps, with no CI or rollback.

### How a data governance expert would question Gist
- **Lineage:** can every change from raw file to figure be shown? (Mostly yes now;
  B2 is the gap.)
- **Definitions:** who owns "Sales"? Does it include tax, refunds, credit notes?
  Catalogues map columns, not definitions.
- **Reproducibility:** briefings don't record the engine version, file hash,
  catalogue or quick-check answers.
- **Change control:** there's no lasting record of who applied which fix.
- **Data kept on the device:** catalogues, business words and the last briefing's figures sit
  in localStorage, which is a problem on shared computers.
- **Sharing:** exports carry no confidentiality marking or "prepared by".
- **Quality thresholds:** when should Gist refuse to tell a story?
- **Personal data:** customer names flow into exports (PDPA).

### Concept-phase decisions to make (not code)
Buyer and reader; delivery model (hosted static site vs desktop app vs private
per-company build); a pricing hypothesis to test in conversations; IP (private
repo or a deliberate licence); a written accuracy policy; a validation plan with
10 real exports; terms and a "decision support, not financial advice" disclaimer.

---

## 3. Strengths to lead with

| Strength | Why it matters to a buyer | How to show it |
|---|---|---|
| Runs entirely in the browser; no server, no upload | Confidential figures never reach a vendor. Nothing to approve with IT. Fits PDPA-minded customers. | Open the browser's network tab during the demo. (Once Pyodide is self-hosted: switch the wifi off.) |
| No AI writes the sentences | The numbers can't be made up. Same file, same answers. | Open "How I got this" on any card. |
| Every figure is traceable | Each card shows its steps and the query behind them. The reconciliation runs from the file as read to the number on screen. | Show the reconciliation line at the foot of the story. |
| Cards are hidden when the data can't support them | Gist doesn't pad the briefing or guess. | Load a file with no dates: the When card disappears. |
| Story first: What, Who, When, Which, Why, How | An executive gets the point in under a minute, without a dashboard to learn. | Read three cards aloud. |
| Accounting exports recognised | Title rows, group headings and subtotal rows from Xero, QuickBooks, AutoCount, SQL Account, SAP B1, Sage and MYOB are tidied, and debit/credit is combined. | Drop an AutoCount export. **Call it "in pilot"**. |
| Saved field catalogues | The second month takes one tap: "I used your Accounting catalogue". | Load a second file with the same columns. |
| Guard rails | Mixed currencies blocked; margin only where cost is known, with coverage stated; day/month order shown; identical rows removed only with an ID column. | Load `overseas_sales.csv` from the sample set. |
| Briefing exports | PDF, PowerPoint (workings in the speaker notes), email draft, copy-for-email. | Export the PDF live. |
| Preparer's notes | The human adds the reasons; Gist keeps the facts. The two are clearly labelled. | Add a note and export it. |
| No setup, no licence prerequisites | Works the first minute, unlike tools that need a data warehouse or capacity licences. | Time the demo. |

---

## 4. Weaknesses to know, and say honestly if asked

| Weakness | Honest answer | Plan |
|---|---|---|
| Nothing saved between visits (by design) | "Your data is gone when you close the tab. Field matches and the last briefing's headline figures are kept on your computer only." | Optional encrypted local workspace, later. |
| One file at a time, no live connection to the accounting system | "It works from the export you already run at month-end." | Watch-folder or desktop app later. Competitors (Fathom, Syft, Reach) sync daily; this is a real gap. |
| Cleaning steps aren't a replayable recipe | "Your field matches are saved; fixes are applied again each month." | Make the catalogue a recipe (see section 7). |
| Ask (chat) matches words, not meaning | "It searches your files; it isn't ChatGPT." Don't demo it. | Rename or remove. |
| Forecast is simple and can be weak with short history | "It's labelled as an estimate with a reliability score." | Require 24+ months for seasonal data. |
| PDF can't print Chinese or other non-Latin names | "Slides and email are fine; the PDF uses standard fonts." | Embed a font. |
| Browser memory limits large files | **Not measured yet.** | Run a performance test before quoting a number. |
| First load downloads the Python engine from a CDN | "The engine is downloaded; your data is not." | Self-host Pyodide; remove the CDN from the security policy. |
| Accounting templates are built from documented layouts, not real customer files | "In pilot: we'll check it against your export." | Collect 10 real exports. |
| No consolidation, budgets or 3-way forecasting | "Gist writes the briefing; it isn't a planning tool." | Stay focused; don't compete with Fathom/Syft on planning. |
| No accounts, licensing or payment yet | "Concept stage; pilot pricing on request." | Decide hosted vs desktop first. |
| No licence file; code is public | Don't bring it up; fix it before pitching. | Make the repo private, add a licence. |
| General-ledger stories are unreliable today | Don't demo a GL file. | See bug B4. |

---

## 5. Known bugs. Fix these before any demo with a prospect's own file

Found on 2026-11-17 by running the engine against test files.

- **B1. "$" next to "RM" is treated as one currency.** A column holding "$1,000"
  and "RM 500" raises no warning and is added together. The rule meant for "$"
  beside "USD" applies to any single other currency.
- **B2. Unreadable amounts disappear without the reconciliation noticing.** Up to 10% of cells in a number
  column can be unreadable ("5,000 refund", European "1.000,50"). They become
  blank, step 1 mentions it once, and the reconciliation still says "matching the file".
- **B3. A repeated sale of a product with "Total" in its name is dropped as a
  subtotal** in recognised exports. Two consecutive "Total Gym Pro" lines at
  1,200: the second matches "the sum of the rows above" and is removed.
- **B4. Ledger stories are nonsense, including the bundled Sage sample.** It reads
  "Net amount reached -843", "accounted for -495% of Net amount", "fallen by about
  4346% a year over the 3 months". Income and cost accounts are netted together,
  shares are worked out on a total near zero, and a 3-month trend is turned into a
  yearly rate.
- **B5. Mixed currencies are blocked only in the story.** Ask and Tables & charts still add them together.

**The rule that would have caught B2 and B3:** no amount leaves the file without
appearing in the reconciliation.

---

## 6. Market landscape: who else is doing something like Gist

Checked November 2026. Re-check before each pitch; these products change often.

### 6.1 Management reporting for accounting data (closest commercial competitors)

| Product | What it does | How it writes text | Where data goes |
|---|---|---|---|
| **Fathom** | Board-ready reporting packs from Xero/QuickBooks/MYOB with forecasting and consolidation. Syncs every 24 hours. | Template placeholders write variance lines ("revenue was up 12% on the prior month"), plus an AI Commentary Writer. | Fathom's cloud |
| **Syft Analytics** (part of Xero) | Dashboards, consolidations, forecasts, templated reports for accountants. | AI-powered narrative reports. | Syft/Xero cloud |
| **Reach Reporting** | Financial report builder with "live text", dynamic statements, FP&A. | Live text fields that update with the data, plus AI analysis. | Reach's cloud |

**What this means for Gist:** these tools prove the market. Accountants pay for
automated management reports with commentary. They need a live connection to a
cloud ledger, though, and they're moving to AI-written commentary. Gist's opening is
**file-based, no upload, never AI-written**, for businesses on desktop or local
systems (AutoCount, SQL Account) or that won't connect their books to another cloud.
Don't compete on forecasting or consolidation.

### 6.2 Narrative features inside BI platforms

| Product | Narrative method | Notes |
|---|---|---|
| **Power BI** (Narrative visual, formerly Smart narrative; Copilot) | Custom mode writes summaries with dynamic values; Copilot mode uses generative AI and needs a Copilot licence (paid Fabric capacity F2+ or Premium). | Needs a semantic model and someone to build the report. |
| **Tableau Pulse** | LLM-written summaries of metric changes, delivered by email or Slack. | Needs Tableau Cloud and its metrics layer. |
| **Zoho Analytics (Zia Insights)** | Automatic narrative insights with key-driver analysis and three levels of detail. For its sibling product ManageEngine Analytics Plus, Zoho states Zia Insights is built in-house and doesn't use external LLMs such as OpenAI; Zoho Analytics also markets generative-AI features. | Closest "no outside AI" story among BI vendors, but it's a cloud BI platform. |
| **Julius** | Upload and ask; generative AI writes the analysis and code. | Reportedly shares data with AI providers by default (opt-out by email). |

### 6.3 Deterministic narrative engines

| Product | Notes |
|---|---|
| **Arria NLG** | Enterprise data-to-text: a deterministic, rules-based engine (now combined with generative AI), with add-ins for Power BI, Tableau, Qlik and Excel. Proves deterministic narrative is a serious category, but it's priced and built for enterprises. |

### 6.4 Open-source projects

| Project | What it is | How it relates to Gist |
|---|---|---|
| **Datasette Lite** (simonw/datasette-lite) | Datasette running entirely in the browser via Pyodide; load CSV/SQLite/JSON and query with SQL. | **Same technology as Gist** (Pyodide + SQLite in the browser), but built for people who write SQL. Proves the privacy architecture works; offers no story or guidance. |
| **Evidence** (evidence-dev/evidence) | "BI as code": reports written in SQL + Markdown, built as a static site, with live values in text. | For data teams who write code. Similar output idea (text with numbers), opposite audience. |
| **RATH** (Kanaries/Rath) | Open-source auto-EDA: automatic insight discovery and chart recommendation (AGPL). | Automatic "insights" for analysts; charts first, not a briefing. |
| **LIDA** (microsoft/lida) | Generates visualisations and infographics from data using LLMs. | Opposite philosophy: LLM-driven. |

**Bottom line:** the parts exist (private in-browser engines, deterministic
narrative, management-report templates), but no product found combines **no
upload + no AI writing + a finished briefing for a non-analyst + accounting-export
awareness.** That's Gist's position. It's also defensible only while it stays
accurate.

**Line to use:** "If you already run Power BI on Fabric, use Copilot. If your books
are in Xero and you're happy with a cloud connection, Fathom is excellent. If you
have an export, a deadline and figures you won't upload anywhere, use Gist."

---

## 7. Data preparation: how lighter-weight tools work, compared with Gist

Excludes Power Query and enterprise platforms (Alteryx, Informatica, Dataiku).

### 7.1 How they work

| Tool | Type | How it works | How it handles trust and repeating the work |
|---|---|---|---|
| **OpenRefine** (free, open source) | Local app in the browser | Facets summarise a column (text, number, date, blank); clustering finds variant spellings by key collision (fingerprint by default, the least likely to produce false positives) or nearest neighbour (edit distance). | Every change goes into an undo/redo history that can be exported as JSON and applied to the next file. |
| **Easy Data Transform** (paid once, ~US$99) | Desktop (Windows/Mac) | Drag-and-drop chain of transforms (46 kinds); local processing. | Save a transform template once and re-run it on any number of datasets, in batch or from the command line. |
| **KNIME Analytics Platform** (free, open source) | Desktop | Visual workflow of nodes; each node is one step; output visible after every node. | Workflows are fully auditable, each step explainable; valued in regulated industries. |
| **Data Wrangler** (Microsoft, free VS Code extension) | Developer tool | Pick an operation, preview the change as a data diff, apply it. | Generates pandas code for every step; a Cleaning Steps panel lists them; code exports to a notebook. |
| **Exploratory** | Desktop app on R | Step-based UI; each step can be disabled, moved or charted. | All steps reproducible; can generate an R script. |
| **Datablist** | Online CSV editor | Exact, phonetic and fuzzy duplicate matching, with a merging assistant. | After automatic cleaning, produces a changes file holding the deleted records' previous values. |

### 7.2 The common method in these tools

1. **Profile:** show the shape of each column (facets, histograms, blanks).
2. **Suggest, but let the user decide:** clustering or duplicate candidates are reviewed.
3. **Preview before applying:** a diff or the output of each step.
4. **Record every step as a recipe:** a history, template, workflow or code.
5. **Replay the recipe** on next month's file.
6. **Keep what was removed:** an undo, or a file of deleted rows.

### 7.3 Gist compared

| Step | Lighter-weight prep tools | Gist today | Gap |
|---|---|---|---|
| Profile | Facets, histograms, column stats | Data check lists blanks, repeats, spelling variants, extreme values, bad dates | Fine for the audience |
| Suggest | User reviews clusters and candidates | "Fix all" applies high-confidence fixes automatically; the rest are listed | Faster for non-analysts, but riskier |
| Preview | Diff or output shown per step | No before/after preview of a fix | **Add "this changes n rows and X of Sales" before applying** |
| Record | Recipe / history / workflow / code | Fix log while the tab is open; catalogue saves field matches and number kinds | **Fixes aren't saved as a recipe** |
| Replay | Template re-runs on next file | Catalogue re-applies matches; fixes must be re-done | **Make the catalogue replay fixes too, with a summary of what changed** |
| Keep removed rows | Undo, deleted-records file | `_orig` copy and "Undo all"; the reconciliation shows rows removed while tidying | Offer a "removed rows" download |
| Spelling clusters | Fingerprint key collision first (low false positives), then nearest neighbour | Normalisation, then close-match (0.72) for rare values (Medium confidence) | Consider fingerprint first |
| Explaining the result | Not their job | Story cards, "How I got this", reconciliation | **Gist's advantage** |

**Takeaway:** prep tools are better at **repeatable, reviewable cleaning**; Gist is
better at **explaining the result to a non-analyst**. Borrow the recipe idea and
add a preview step. Don't become a prep tool.

---

## 8. Questions prospects will ask, and answers

**"Can I trust the numbers?"**
Every card has "How I got this", with the exact steps. The reconciliation shows
rows and totals from the file to the figure. Gist leaves a card out rather than
guess. *(Once B2 is fixed:)* any amount it couldn't read is shown in the
reconciliation.

**"Who sees my data?"**
Nobody. It's processed in this browser tab and erased when you close it. Exports
are created on your computer and go only where you send them.

**"Is this AI?"**
No. Every sentence comes from fixed templates filled with calculated figures. That's
why it can't invent a reason or a number.

**"How is this different from Fathom or Syft?"**
They connect to your cloud ledger and increasingly use AI for commentary; they're
excellent if you're happy with that. Gist works from an export, never uploads it, and
never lets AI write the sentences. It also works with desktop systems like AutoCount
and SQL Account.

**"Why did sales drop?"**
Gist shows *where* the change came from (which customers, products, regions). It
won't make up *why*, because your files don't record it. The preparer's note is where
your team adds the reason.

**"My export is messy."**
Recognised exports are tidied automatically, and every removed row is shown in the
reconciliation. For anything else, match your fields once and save them.

**"What does it cost?"**
Concept stage. Have a range ready (per preparer per month, or per company per year)
and offer a 3-month-end pilot. Reference points: Fathom from about US$53/month for one
company; Easy Data Transform US$99 once.

**"What happens when the file is huge?"**
Don't quote a number until it's been measured.

**"Can it connect to AutoCount / Xero directly?"**
Not yet; it works from the export you already run.

---

## 9. Demo script (5 minutes)

1. **The pain (30 s).** "Month-end: the boss asks why sales are down; someone loses two days in Excel."
2. **Drop the file (60 s).** Use the prospect's own export, rehearsed beforehand. Network tab open.
3. **Match your fields (30 s).** One tap on "Looks right".
4. **Read the story (90 s).** What → Why → How. Open "How I got this" once.
5. **Trust (30 s).** Point to the reconciliation line.
6. **Share (30 s).** Export the PDF and show the speaker notes in the slides.
7. **Next month (30 s).** "Next time it's one tap, and it tells you what changed since this briefing."
8. **Ask.** A pilot over three month-ends.

**Don't demo:** Ask, Predictions, general-ledger files (B4), non-Latin names in PDF.

---

## 10. Don't claim

- "Supports Xero / QuickBooks / AutoCount …": say "recognises their standard exports, in pilot".
- "Works offline": not true until Pyodide is self-hosted.
- "Handles millions of rows": not measured.
- "Explains why": it shows where the change came from, not the cause.
- "The only tool that…": say "we haven't found another tool that combines…".
- "Bank-grade security" or any certification: there is none.
- "Nothing is stored": catalogues, business words and the last briefing's headline
  figures are kept in the browser's local storage.

---

## 11. Before the first prospect meeting

- [ ] Fix B1–B5.
- [ ] Self-host Pyodide; remove cdn.jsdelivr.net from the security policy; test with wifi off.
- [ ] Make the repository private, or add a deliberate licence plus third-party notices.
- [ ] Get 10 real exports from 3–5 friendly businesses; check each against their own Excel pivot.
- [ ] Run a performance test at 100k and 500k rows and record the results.
- [ ] One-page security and data note: where code runs, what's stored, retention, what leaves the device.
- [ ] A pricing range and pilot terms.
- [ ] A "decision support, not financial advice" disclaimer in the footer and the exports.
- [ ] Rehearse the demo with the prospect's own file.
- [ ] Re-check section 6 (competitors) in the week of the pitch.

---

## Sources (section 6 and 7)

- [Fathom: Commentary Writer, management reporting](https://fathomhq.com/)
- [Fathom for Xero: 24-hour sync](https://fathomhq.com/xero)
- [Fathom review: variance placeholders, pricing](https://eightx.co/blog/compare/reviews/fathom-for-ecommerce-review)
- [Syft Analytics overview](https://aichief.com/ai-business-tools/syft-analytics/)
- [Syft from Xero](https://www.xero.com/ie/syft-from-xero/)
- [Reach Reporting storytelling / live text](https://reachreporting.com/feature-storytelling)
- [Power BI smart narrative (Custom vs Copilot mode)](https://learn.microsoft.com/en-gb/power-BI/visuals/power-bi-visualization-smart-narrative)
- [Power BI Copilot requirements](https://www.epcgroup.net/power-bi-copilot-enterprise-analytics)
- [Tableau Pulse and the metrics layer](https://salesforcedevops.net/?p=38573)
- [Zoho Zia Insights, no external LLMs (ManageEngine Analytics Plus)](https://manageengine.com/analytics-plus/help/zia/insights.html)
- [Julius data sharing](https://www.stork.ai/blog/best-ai-for-data-analysis-2026)
- [Arria: deterministic rules-based NLG](https://www.toolmage.com/en/tool/arria/)
- [Datasette Lite](https://github.com/simonw/datasette-lite/blob/main/README.md)
- [Evidence](https://motherduck.com/glossary/evidence/)
- [RATH](https://docs.kanaries.net/rath)
- [LIDA](https://microsoft.github.io/lida)
- [OpenRefine clustering in depth](https://docs.openrefine.org/technical-reference/clustering-in-depth)
- [OpenRefine: applying the JSON history to another file](https://data.journalism.columbia.edu/content/more-openrefine-extract-apply-cluster)
- [Easy Data Transform: templates, local processing](https://appleworld.today/?p=62375)
- [Easy Data Transform pricing and batch](https://www.modern-datatools.com/compare/easy-data-transform-vs-kramata)
- [KNIME: auditable workflows](https://www.datacamp.com/ja/blog/what-is-knime)
- [VS Code Data Wrangler](https://code.visualstudio.com/docs/datascience/data-wrangler)
- [Exploratory: reproducible steps](https://exploratory.io/features/wrangling)
- [Datablist: changes file after cleaning](https://www.datablist.com/docs/find-duplicates)

---

## How this file is maintained

- Any session that fixes a bug, finds a new weakness, adds a feature, or learns
  about a competitor updates this file in the same change (see `CLAUDE.md`).
- Fixed bugs move from section 5 into section 2's review history with the date.
- Section 6 is re-checked before each pitch; prices and features change.
- Update "Last updated" and the commit reference at the top.
