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

Last updated: 2026-11-17

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

### Gist (2026-11-17)
- R31. The product is named **Gist** (was Plainly).
- R32. A sixth card, **Why**, sits between Which and How: What, Who, When, Which,
  Why, How. Why reports which groups the change since the previous period came
  from. It never gives outside causes, because the files do not record them.
- R33. Only facts, no assumptions. If the data lacks what a card needs, the card
  is hidden completely (no dates: no When; nothing that says who: no Who; no
  earlier period or no grouping: no Why). This replaces showing a card that
  says something is missing. Cards are renumbered so there are no gaps.
- R34. The header no longer shows "Files stay on this computer". The behaviour
  is unchanged (data still never leaves the browser); the smaller privacy notes
  on the start page and the story footer stay.
- R35. The line above the cards reads "A look at ..." (was "The story of ...").
- R36. Cards animate with a smooth glide: the open card grows while the others
  draw in to slim bars, each card numbered in a small circle. Reference was a
  side-by-side expanding-cards animation; only the motion was wanted, in the
  site's own style. Cards stay stacked top to bottom (R26 stands).
- R37. Each card's chart and table can be changed with small round buttons on
  the card's right edge: the number, the grouping, and the chart type. The clean
  look comes first, so buttons show only when there is a real choice.
- R38. Changing the number re-tells every card (the story stays about one
  thing). Changing the grouping or chart affects only that card.
- R39. Sentences are rebuilt from fixed templates whenever a field changes, in
  a "boardroom brief" voice: short, confident, one main point. Example: "Sales
  Amount reached 1.52M in Q3 2026, 8% ahead of Q2 2026 and 12% ahead of Q3 2025."
- R40. Numbers are always totals (or a count of rows). No average option.
- R41. Chart choices are limited to two that suit each card: line or bars for
  When; bars or share of the total for Who and Which; the change or before and
  after for Why.
- R42. How keeps its rule-based steps and the forecast, with the forecast
  clearly labelled as an estimate, not a fact.
- R43. Figures carry no currency symbol.
- R44. Quarters and years follow the normal calendar year (Q1 = January to
  March). There is no year-start choice on the story page. A quiet "Business
  year starts in" choice appears at the foot of the story only while "Explore
  further" is on, for anyone who needs a different start. (Changed 2026-11-17:
  it was first shown to every reader.)
- R45. The story footer no longer says "Worked out from your files only.
  Nothing is guessed." The start page no longer has the three explanatory
  notes under the drop box. Behaviour is unchanged; each card still has "How I
  got this".
- R46. Story cards look like cards: white, thin outline, rounded corners, with
  space between them. This replaces "few lines and boxes" in R30 for the cards.
- R47. Card motion: cards arrive one by one; a card lifts slightly when
  hovered or pressed; the tapped card expands in place while the others dim and
  draw in; the content then flows in piece by piece. The automatic scroll that
  keeps the opened card in view is slow and eased, and stops if the reader
  scrolls.
- R48. Glass feel: clean white cards on the plain light background; only the
  top bar is frosted glass. (Owner chose this over tinted or strong glass.)
- R49. The app must work well on a phone (iPhone size) on every screen.
- R51. In a story card the topic word (What, Who...) is the heading: large, bold,
  dark. The one-line finding sits under it as the subtitle: smaller and grey,
  growing a little when the card opens. The two must be easy to tell apart.
- R52. (Replaced by R58.) While a card is hovered or open, pale blue hues drift slowly inside the
  card's shape (about 15 seconds a pass). They must stay light enough not to
  disturb reading; charts and tables keep a solid white backing. The subject
  choice cards do the same on hover.
- R53. The first page is the story cards themselves, all six shown empty as a
  preview. Above them: the Gist orb, one line ("Add your data and get the
  gist"), one big "Add your data" button and a small "Try with sample data"
  link. Opening an empty card shows one line about what it will tell and the
  same big button. After data is added, only cards the data supports appear
  (R33).
- R54. Adding files is three plain steps with a progress bar and one big button
  each: 1 "I found N tables in your files" (Looks right, continue); 2 "I found N
  things to tidy" (Fix them all, or Skip for now; skipped when there is nothing
  to tidy); 3 "What do you want to understand?". Names, fields, previews and
  explanations are folded behind "Show details". The audience is not technical
  and has no data knowledge.
- R55. "Your data" has one big "Fix all" button at the top. It applies safe
  fixes only (repeated rows, spelling variants, date formats, linking tables
  that belong together). Items that need judgement, such as unusually large
  values, stay listed with their own buttons; details are folded away. The
  "Text I can search" list is removed from this page.
- R56. The Gist icon is an orb matching the owner's reference image: a soft,
  edgeless glow with a deep blue core, cyan on the right, violet below, mint
  and a bright white crescent on the left, slowly turning and breathing. It is
  the logo in the top bar, the large orb on the first page, and the waiting
  animation during the steps.
- R57. Opening a story card is slow and smooth (about 1.2 seconds on one gentle
  curve). The opened card's heading stays steady and, if low on screen, is
  carried up along one eased curve.
- R58. The colour in a hovered or open card sits on its right edge: the orb's
  blue, cyan and violet, much fainter, rolling like waves with soft ripples.
  On touch screens it shows only on the open card.
- R59. The step bar on steps 1 to 3 is clickable: pressing a part goes to that
  step. Once data is in, earlier steps are a look back, nothing is undone: step
  1 shows "You added N tables" (details folded) with Continue; step 2 shows what
  is left to tidy, or "Everything is tidy" with Continue. Later steps cannot be
  reached while new files are still waiting to be confirmed.
- R60. The story page has a "Back" button at the top that returns to step 3.
- R61. Step 3 choices are story cards (same look and motion). Tapping one opens
  it to one plain line and a big "See the story" button. (Replaces R50's
  "tapping goes straight to the story".)
- R62. All story cards start closed; none opens by itself.
- R63. The automatic scroll when a card opens is gentle at both ends (about 1.6
  seconds) and only happens when the card sits low on screen.
- R64. The first-page headline splits evenly on phones ("Add your data" / "and
  get the gist"), in lighter type; one line on wide screens.
- R65. The "A look at ..." line is centred, and its phrases stay together when
  it wraps ("in Q3 2025", "for everything").
- R66. The orb follows the owner's five keyframe screenshots over a calm
  12-second cycle: violet-blue lens, azure rounded triangle, deep blue round
  core, light cyan core with mint and yellow, deep blue half-moon; cyan, pink,
  violet and mint clouds move round the core on the same clock.
- R67. The orb has no white line (crescent) around it.
- R68. The first page no longer shows "Ready. Everything runs inside this
  browser tab."
- R69. The first page has slow waves and ripples in the page background, as a
  band running down the middle of the whole page from top to bottom, fading out
  towards the sides; not on the cards (the empty cards stay plain white). On
  phones the band is narrower (about half the screen) so there is white space
  either side, in proportion with the laptop view. Colours are pale: light teal with
  sky, aqua and periwinkle blues mixed in, never one dark blue.
  The empty cards' titles are questions: What?, Who?, When?, Which?, Why?, How?
- R70. The automatic scroll when a card opens must not shake. It is planned once
  (where the card will end up after all cards finish moving) and done as one
  smooth movement.
- R71. Steps 1 to 3 each have a small "Back" button: step 1 back leaves the steps,
  step 2 goes to step 1, step 3 to step 2.
- R72. On step 3, one tap on a subject goes straight to the story (replaces R61's
  two taps). A waiting screen with the orb shows "Reading the numbers…", "Finding
  what changed…", "Preparing your story…" in turn, for about 2 seconds
  (quicker than the reading and tidying screens).
- R73. Reading files and tidying take at least about 3 seconds on screen, with
  the orb and changing lines, so the work feels thorough. Real work is never cut
  short.
- R74. Card mood (very light, so it never distracts): the open card's waves turn soft red for bad news, soft green
  for good news, and stay blue when neutral. Fixed rules, flipped for cost-like
  numbers: What follows the change on the previous period (under 1% neutral);
  When follows the long-term trend (within 3% a year neutral); Why follows the
  overall change; Who, Which and How are always neutral.
- R75. At the end of each round of changes, Claude asks the owner whether to
  publish to main, instead of waiting to be told.
- R50. The choices on "What do you want to understand?" use the same card
  design and motion. (Tapping now opens the card first; see R61.)

## Business knowledge

- Main uses are **sales and customers** (revenue, orders, customers, products,
  regions, targets) and **finance** (costs, budgets against actuals, margins).
- Readers are upper management who want a quick read and a decision, not analysis.
- For cost-like numbers (cost, expense, spend) a rise is the concern; for
  sales-like numbers a fall is the concern. The story's suggested steps follow this.
- The business year does not have one fixed start month for every reader, so the
  reader picks it (R44).

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
| 2026-11-17 | With a business year that does not start in January, quarters are written with their months, for example "Q2 (Jul–Sep 2025)", and a target year as "the year from Apr 2025". | There is no single convention for naming such a year (by its first or last calendar year), and guessing would break R33. |
| 2026-11-17 | Sentences say "ahead of / behind" for sales-like numbers and the neutral "above / below" for cost-like numbers. | "Ahead" sounds like good news, which is wrong for a cost. |
| 2026-11-17 | Why shows one grouping at a time. By default it is the grouping whose two largest movers explain the biggest part of all movement, preferring groupings with 3 to 20 groups. The reader can switch it. | Contributions from different groupings overlap, so mixing them in one sentence would double count. |
| 2026-11-17 | A target or budget is only compared with the number it names ("Sales Target" with Sales Amount, never with Quantity). A target with no subject in its name is read as the main number's target. | R33. Found when changing the number became one click. |
| 2026-11-17 | Share-of-total charts are rings with at most five named slices plus "All others". | Readability; more slices cannot be told apart. |
| 2026-11-17 | The Dribbble orb reference could not be read from the build environment (the site blocks automated visits), so the orb was matched to a screenshot the owner uploaded. | Owner's choice to share the image. |
| 2026-11-17 | The chart in an open card is drawn about 0.4 seconds into the opening, and its space is reserved in advance. | Drawing during the first frames made the opening stutter, and late sizing made it jump. |
| 2026-11-17 | Work for Gist was built on branch `claude/gist-story`; `main` (the live site) changes only when the owner approves. | The owner reviews before publishing. |
| 2026-11-16 | The story project lives in its own repository, `evalim0509/analyticsstoryweb` (branch `main`). `analyticschatbotv1` keeps the original three-tab version. | Owner's choice, so the two products can evolve separately. |

## Open questions

- Should imported data be remembered between visits (stored in the browser), or
  always start fresh? Currently always fresh.
- Largest file size the business expects? The browser engine is comfortable up
  to roughly a few hundred thousand rows.
- Are there fixed business definitions (for example what counts as an active
  customer) that the chatbot should apply automatically? Fiscal year start and
  currency are answered (R43, R44).

## Ideas not yet built

- Saving and reopening a workspace.
- Follow-up questions that remember the previous one ("and for South?").
- Joining on two fields at once.
- Scanned PDFs (text recognition).

## Change log

| Date | Change |
|---|---|
| 2026-11-17 | First-page wave band narrowed on phones; step 3 "preparing your story" screen shortened to about 2 seconds. |
| 2026-11-17 | First-page background waves now run as a band down the middle of the whole page. |
| 2026-11-17 | First-page background waves narrowed to the middle and changed to pale teal, sky, aqua and periwinkle blues. |
| 2026-11-17 | First-page waves moved from the cards to the page background; red and green card moods made lighter and quieter. |
| 2026-11-17 | Orb crescent removed; "Ready" line removed; centred waves and question titles on first-page cards; shake-free planned scroll; Back buttons on steps; one tap on step 3 with an orb "preparing" screen; 3-second reading and tidying screens; red/green/blue card moods. |
| 2026-11-17 | Clickable step bar with look-back steps; Back button on the story; step 3 as story cards; all story cards closed at first; gentler auto-scroll; even two-line headline on phones; centred "A look at" line; orb re-animated from the owner's keyframes. |
| 2026-11-17 | First page is now the empty story cards under the Gist orb; adding files is three big-button steps with details folded; Your data has one "Fix all" and no text list; slower, steadier card opening; colour waves on the right edge of cards; orb logo. |
| 2026-11-17 | Story cards: topic word as a bold heading with the finding as a grey subtitle under it; slow drifting blue hues inside hovered and open cards. Printed briefing tidied. |
| 2026-11-17 | Story and subject choices restyled as outlined white cards with arrival, lift, expand and flow-in motion; slower eased auto-scroll; frosted top bar; phone layout pass; footer note and start-page notes removed; business-year choice moved behind "Explore further". Fixed the data check's side list, whose layout had been disturbed by the card edge buttons sharing its style name. |
| 2026-11-17 | Renamed to Gist. Added the Why card; cards the data cannot support are hidden; glide animation and numbered cards; edge buttons to change the number, grouping and chart; sentences rewritten in a boardroom voice; forecast labelled as an estimate; reader-chosen business year start; header privacy badge removed; "A look at ...". Targets no longer compared with the wrong number. |
| 2026-11-16 | Fixed "engine could not start" after an update: the list of engine files now comes from `engine/manifest.json`, fetched fresh every time, and all app files carry a version stamp. Project also copied to the `evalim0509/analyticsstoryweb` repository. |
| 2026-11-16 | Branch `claude/story-cards`: five-card story (What, Who, When, Which, How) as the main screen, subject picker, one-click tidy, period and filter controls, copy summary, print briefing. Existing tools moved behind "Explore further". Sample targets made realistic. |
| 2026-11-15 | First version: file import with preview, data check with one-click fixes, join suggestions, chatbot, table and chart builder, machine learning tab, sample data, this file. |
