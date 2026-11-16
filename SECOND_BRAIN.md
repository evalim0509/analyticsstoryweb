# Second brain

Living memory for this project. Business requirements, business knowledge and
decisions are recorded here as they are given, so the project keeps improving
without anything having to be repeated.

How it is used:

- **Claude reads this file first** at the start of every session, and updates it
  in the same change whenever new requirements or business knowledge are given
  (see `CLAUDE.md`).
- **The app reads the "Business words" table** below when it starts, so the
  chatbot understands the business's own vocabulary.

Last updated: 2026-11-16

## Purpose

A private analytics workspace for people who are not analysts. Drop in a file,
confirm what was found, then ask questions, build tables and charts, and run
predictions. The two things it must protect are **confidentiality** (data never
leaves the user's computer) and **accuracy** (answers come only from the
uploaded files, and every answer can be audited).

## Business words

The app loads this table. Each row teaches the chatbot that a word the business
uses means a field name or a value in the uploaded data. Add rows as vocabulary
comes up. Rows whose first cell starts with `_` are ignored.

| Business word | Means (field or value in the data) | Notes |
|---|---|---|
| revenue | Sales Amount | Sample data vocabulary |
| turnover | Sales Amount | |
| takings | Sales Amount | |
| units | Quantity | |
| client | Customer ID | |
| satisfaction | Satisfaction Score | |
| tickets | Support Tickets | |
| _example | _Field Name_ | _Copy this row to add a word_ |

## Business requirements

Recorded from the project owner. Newest entries at the bottom of each group.

### Experience
- R1. Live, interactive web interface. No terminal, no installation.
- R2. First screen invites "Drop a file to begin". Accepts Excel, Word,
  PowerPoint and similar documents.
- R3. The app reads the file, shows a preview, and the user confirms the import.
- R4. Must be friendly for non-technical users. It must not feel like an
  analytics tool that needs analytics knowledge to navigate.
- R5. Users never read or type SQL. Everything is drag and drop or plain words.
- R6. Professional, minimal, intuitive look.

### Data handling
- R7. A SQL backend holds the uploaded data.
- R8. On upload the system suggests fields to join tables on, with data match %
  and a confidence level, and a one-click accept.
- R9. On upload the system reports missing data, duplicated data, anomalies and
  abnormalities, and inconsistencies, each with a one-click accept.
- R10. Confidentiality: data stays private. No external data is brought in.
- R11. Accuracy: answers and displays use only the uploaded documents.

### Three connected tabs
- R12. **Chatbot.** Answers questions from the uploaded documents using
  deterministic Python. No LLM. Matches the words in the question to the words
  in the documents. Every answer has a "How I got this" so it can be audited.
- R13. **Table and chart builder.** Drag and drop fields from the uploaded data.
  Export the table and the chart.
- R14. **Machine learning.** Forecasts, time series, prediction and similar.
  Results (model accuracy, feature importance, confidence bands and so on) are
  explained in plain English.
- R15. The tabs are connected: a chat answer has "Open in builder", which leads
  to the table and chart; "Ask about this" connects to machine learning results.

### Project
- R16. Code lives in the connected GitHub repository (`evalim0509/analyticsstoryweb`, branch `main`).
- R17. This file acts as the second brain and is updated continuously.
- R18. Dummy data is included to test all three tabs.

### Story-first redesign (2026-11-16; this repository's main product)
- R19. Redefine the BI dashboard: no charts and tables at first glance. The main
  screen is five cards: What, Who, When, Which, How.
- R20. Each card expands into data in a fixed order: sentence first, then chart,
  then table.
- R21. Story driven, not chatbot driven. The five cards alone let the reader
  understand what is happening, in sequence.
- R22. Audience is upper management: not technical, wants quick insight and a
  decision.
- R23. Clean, story focused, generous whitespace, no clutter.
- R24. Card meanings: What happened (headline number and its change), Who is
  behind it, When (trend over time), Which ones matter most (ranking), How to
  respond (suggested next steps from fixed rules, not AI).
- R25. After upload the user picks the subject first ("What do you want to
  understand?"), then the story is built.
- R26. Cards are stacked vertically and only one is open at a time.
- R27. Headline numbers are compared with the previous period, the same period
  last year, and a target or budget when the files contain one.
- R28. The story can be printed as a briefing, copied as text, and narrowed with
  one filter that re-tells all five cards.
- R29. The data check still runs after upload. Ask, Tables & charts and
  Predictions stay available behind one quiet "Explore further" control.
- R30. Look: editorial briefing. Light background, large sentences as the main
  visual, one restrained accent colour, few lines and boxes.

## Business knowledge

- Main uses are **sales and customers** (revenue, orders, customers, products,
  regions, targets) and **finance** (costs, budgets against actuals, margins).
- Readers are upper management who want a quick read and a decision, not analysis.
- For cost-like numbers (cost, expense, spend) a rise is the concern; for
  sales-like numbers a fall is the concern. The story's suggested steps follow this.

Nothing else recorded yet beyond the sample data. Add things like: what each file contains, how figures are
defined (for example "revenue excludes refunds"), reporting periods, thresholds
that matter, who uses the output.

## Decisions

| Date | Decision | Why |
|---|---|---|
| 2026-11-15 | Everything runs in the browser (Python via Pyodide, SQL via SQLite). No server. | Owner's choice. Uploaded files never leave the computer, and there is nothing to host or pay for. |
| 2026-11-15 | Published with GitHub Pages. | Owner's choice. A normal web link, no terminal. |
| 2026-11-15 | The second brain both records notes and teaches the chatbot vocabulary. | Owner's choice. |
| 2026-11-15 | Data lives in memory only. Closing or reloading the tab erases it. | Confidentiality. Nothing is written to disk or sent anywhere. |
| 2026-11-15 | Data fixes change a working copy, never the original import. "Undo all changes" restores it. | Accuracy and auditability. |
| 2026-11-15 | The chatbot refuses rather than guesses when words do not match the files. | Accuracy. |
| 2026-11-15 | SQL is hidden behind a "Technical detail" disclosure inside "How I got this". | Users never need SQL, but an analyst can still verify an answer. |
| 2026-11-15 | Charts follow one consistent style; no dual axes; at most 8 colours. | Readability for non-analysts. |

| 2026-11-16 | Story branch: the first screen after import asks "What do you want to understand?" and offers up to five subjects. | Owner's choice (R25). |
| 2026-11-16 | Story branch: default period is the latest complete quarter; the latest month and the latest 12 months are one click away. Incomplete final months are left out. | Quarters suit management reporting; partial months mislead. |
| 2026-11-16 | Story branch: one "Apply them all" button accepts high-confidence fixes and high-confidence table links before the story. Lower-confidence items are flagged at the top of the story and as step 1 of How, never applied silently. | Executives should not have to tidy data, but accuracy must not be hidden. |
| 2026-11-16 | Story branch: a target or budget is found automatically when a small table has a number field named target, budget, plan, goal or quota and shares a field with the main table. Annual targets are compared with year-to-date pace. | R27, without asking the user to configure anything. |
| 2026-11-16 | Story branch: "How" steps come from fixed rules (open data issues, distance from target, biggest fall and rise, 40%+ reliance on one group, 3-month forecast). | R24 and the no-AI rule. |
| 2026-11-16 | Story branch: sentences use rounded figures (188K, 1.52M); tables show exact figures. | Quick reading without losing auditability. |
| 2026-11-16 | Story branch: accent colour changed from green to ink blue, with a serif face (Source Serif 4) for sentences. | R30. |
| 2026-11-16 | The story project lives in its own repository, `evalim0509/analyticsstoryweb` (branch `main`). `analyticschatbotv1` keeps the original three-tab version. | Owner's choice, so the two products can evolve separately. |

## Open questions

- Should imported data be remembered between visits (stored in the browser), or
  always start fresh? Currently always fresh.
- Largest file size the business expects? The browser engine is comfortable up
  to roughly a few hundred thousand rows.
- Does the business use calendar quarters, or a fiscal year that starts in another month?
- Are there fixed business definitions (fiscal year start, currency, what counts
  as an active customer) that the chatbot should apply automatically?

## Ideas not yet built

- Saving and reopening a workspace.
- Follow-up questions that remember the previous one ("and for South?").
- Joining on two fields at once.
- Scanned PDFs (text recognition).

## Change log

| Date | Change |
|---|---|
| 2026-11-16 | Fixed "engine could not start" after an update: the list of engine files now comes from `engine/manifest.json`, fetched fresh every time, and all app files carry a version stamp. Project also copied to the `evalim0509/analyticsstoryweb` repository. |
| 2026-11-16 | Branch `claude/story-cards`: five-card story (What, Who, When, Which, How) as the main screen, subject picker, one-click tidy, period and filter controls, copy summary, print briefing. Existing tools moved behind "Explore further". Sample targets made realistic. |
| 2026-11-15 | First version: file import with preview, data check with one-click fixes, join suggestions, chatbot, table and chart builder, machine learning tab, sample data, this file. |
