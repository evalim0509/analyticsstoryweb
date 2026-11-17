/* Gist — the page. All data work happens in the Python engine (assets/worker.js);
   this file only draws screens and passes requests. No data is sent anywhere. */
"use strict";

// ---------------------------------------------------------------- small helpers
// Screens are built with optional parts ("show this only if..."). Skip empty parts and flatten lists
// everywhere, so a missing part never appears on screen as the word "null".
for (const name of ["replaceChildren", "append"]) {
  const native = Element.prototype[name];
  Element.prototype[name] = function (...kids) { return native.apply(this, kids.flat(Infinity).filter((k) => k !== null && k !== undefined && k !== false)); };
}
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "value") el.value = v;
    else if (v === true) el.setAttribute(k, "");
    else el.setAttribute(k, v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return el;
}
const $ = (id) => document.getElementById(id);
const TYPE_WORD = { number: "Number", date: "Date", text: "Text" };
const AGG_WORD = { sum: "Total", avg: "Average", count: "Count", distinct: "How many different", min: "Lowest", max: "Highest" };
const plural = (n, w, ws) => `${fmtNum(n)} ${n === 1 ? w : ws || w + "s"}`;

function toast(text) {
  const t = $("toast");
  t.textContent = text; t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (t.hidden = true), 3800);
}

function renderTable(columns, rows, types, opts = {}) {
  const isNum = (i) => types ? types[i] === "number" : rows.some((r) => typeof r[i] === "number");
  const nums = columns.map((_, i) => isNum(i));
  const cell = (v, i) => v === null || v === undefined || v === ""
    ? h("td", { class: "blank" + (nums[i] ? " num" : "") }, opts.dash ? "–" : "blank")
    : h("td", { class: (nums[i] ? "num" : "") + (opts.wrap === i ? " wrap" : ""), title: typeof v === "string" && v.length > 40 ? v : null },
        columns[i] === "Row in file" ? String(v) : fmtNum(v));
  return h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, columns.map((c, i) => h("th", { class: nums[i] ? "num" : "" }, c)))),
    h("tbody", {}, rows.map((r) => h("tr", {}, r.map(cell))))));
}

function download(name, blob) {
  const a = h("a", { href: URL.createObjectURL(blob), download: name });
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
function downloadCsv(name, columns, rows) {
  const esc = (v) => v === null || v === undefined ? "" : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v);
  download(name + ".csv", new Blob(["﻿" + [columns, ...rows].map((r) => r.map(esc).join(",")).join("\n")], { type: "text/csv" }));
}

// ---------------------------------------------------------------- the engine
const worker = new Worker("assets/worker.js?v=2026-11-18.4");
const waiting = new Map();
let seq = 0, engineReady = false;
worker.onmessage = (e) => {
  const m = e.data;
  if (m.status) {
    const el = $("engineStatus");
    if (m.status === "ready") {
      engineReady = true;
      el.textContent = ""; el.className = "engine ready";
      sendGlossary();
    } else if (m.status === "failed") {
      const stale = /ImportError|Could not load engine|cannot import/.test(m.error);
      el.replaceChildren(stale ? "The app was updated while this tab was open. " : "The engine could not start. Check your internet connection. ",
        h("button", { class: "link", onclick: (e) => { e.stopPropagation(); location.reload(); } }, "Reload the page"),
        h("span", { title: m.error }, stale ? "" : " (details: " + String(m.error).slice(-160) + ")"));
      el.className = "engine failed";
    } else if (m.status !== "ml-ready") el.textContent = m.status;
    return;
  }
  const p = waiting.get(m.id);
  if (!p) return;
  waiting.delete(m.id);
  m.error ? p.reject(new Error(m.error)) : p.resolve(m.result);
};
worker.onerror = (e) => { $("engineStatus").textContent = "The engine could not start: " + e.message; $("engineStatus").className = "engine failed"; };
function call(fn, args, blob) {
  return new Promise((resolve, reject) => {
    const id = ++seq;
    waiting.set(id, { resolve, reject });
    worker.postMessage({ id, fn, args: args || {}, blob }, blob ? [blob] : []);
  });
}

// ---------------------------------------------------------------- app state
const S = {
  state: null, view: "welcome", current: null, checks: {}, context: null,
  build: { dataset: null, rows: [], split: null, values: [], filters: [], chart: "auto", limit: null },
  predict: { kind: "forecast", dataset: null, result: null, options: null },
};
const datasetById = (id) => S.state.datasets.find((d) => d.id === id);
const fieldOf = (ds, name) => ds.columns.find((c) => c.name === name);

function setState(st) {
  S.state = st;
  if (!S.current || !datasetById(S.current)) S.current = (st.datasets[0] || {}).id || null;
  if (!S.build.dataset || !datasetById(S.build.dataset)) resetBuild((st.datasets[0] || {}).id);
  if (!S.predict.dataset || !datasetById(S.predict.dataset)) S.predict.dataset = (st.datasets[0] || {}).id || null;
  const review = st.datasets.reduce((n, d) => n + ((d.health || {}).to_review || 0), 0) + st.joins.length;
  const tab = document.querySelector('[data-view="data"]');
  tab.replaceChildren("Your data", review ? h("span", { class: "count", title: "Items to review" }, review) : "");
}

function show(view) {
  S.view = view;
  $("welcome").hidden = view !== "welcome";
  if (view === "story" && !S.story) view = S.view = "pick";
  for (const v of ["flow", "pick", "story", "data", "catalogues", "ask", "build", "predict"]) $("view-" + v).hidden = v !== view;
  const has = !!S.state;
  if (["data", "catalogues", "ask", "build", "predict"].includes(view)) S.explore = true;
  $("addBtn").hidden = $("exploreBtn").hidden = !has || view === "flow" || (view === "pick" && S.flow);
  $("tabs").hidden = $("wordsBtn").hidden = !(has && S.explore);
  $("exploreBtn").textContent = S.explore ? "Hide tools" : "Explore further";
  if (view === "pick") renderPick();
  if (view === "story") renderStory();
  document.querySelectorAll("#tabs button").forEach((b) => b.setAttribute("aria-current", b.dataset.view === view ? "page" : "false"));
  if (view === "data") renderData();
  if (view === "catalogues") renderCatalogues();
  if (view === "ask") renderAsk();
  if (view === "build") renderBuild();
  if (view === "predict") renderPredict();
  window.scrollTo(0, 0);
}
document.querySelectorAll("#tabs button").forEach((b) => b.addEventListener("click", () => show(b.dataset.view)));
$("exploreBtn").addEventListener("click", () => { S.explore = !S.explore; show(S.explore ? S.view : (S.story ? "story" : "pick")); });

// ---------------------------------------------------------------- business words (the second brain's glossary)
let brainWords = [];
const localWords = () => { try { return JSON.parse(localStorage.getItem("gist.words") || localStorage.getItem("plainly.words") || "[]"); } catch { return []; } };
function parseBrain(md) {
  const m = md.split(/^##\s+/m).find((s) => /^Business words/i.test(s));
  if (!m) return [];
  return m.split("\n").filter((l) => l.trim().startsWith("|")).map((l) => l.split("|").slice(1, -1).map((c) => c.trim()))
    .filter((c) => c.length >= 2 && c[0] && !/^-+$/.test(c[0].replace(/[:\s]/g, "")) && !/^business word/i.test(c[0]) && !c[0].startsWith("_"))
    .map((c) => ({ term: c[0].replace(/[`*]/g, ""), means: c[1].replace(/[`*]/g, ""), note: c[2] || "" }));
}
function sendGlossary() { if (engineReady) call("set_glossary", { entries: [...brainWords, ...localWords(), ...(typeof catalogueWords === "function" ? catalogueWords() : [])] }); }
fetch("SECOND_BRAIN.md", { cache: "no-cache" }).then((r) => (r.ok ? r.text() : "")).then((t) => { brainWords = parseBrain(t); sendGlossary(); }).catch(() => {});

function openWords(prefill) {
  const fields = S.state ? [...new Set(S.state.datasets.flatMap((d) => d.columns.map((c) => c.name)))] : [];
  const term = h("input", { type: "text", placeholder: "e.g. takings", value: prefill || "", "aria-label": "Your word" });
  const means = h("input", { type: "text", placeholder: "e.g. Sales Amount", list: "fieldList", "aria-label": "Field or value it means" });
  const list = h("div", { class: "stack" });
  const draw = () => {
    const mine = localWords();
    list.replaceChildren(
      mine.length || brainWords.length ? null : h("p", { class: "muted" }, "No business words yet."),
      renderTable(["When I say", "It means", "Where it is kept"], [
        ...brainWords.map((w) => [w.term, w.means, "Project notes (SECOND_BRAIN.md)"]),
        ...mine.map((w) => [w.term, w.means, "This browser"]),
        ...catalogueWords().map((w) => [w.term, w.means, "Data catalogue (matched fields)"])], ["text", "text", "text"]),
      mine.length ? h("button", { class: "link", onclick: () => { localStorage.removeItem("gist.words"); localStorage.removeItem("plainly.words"); sendGlossary(); draw(); } }, "Clear the words kept in this browser") : null);
  };
  draw();
  const add = () => {
    if (!term.value.trim() || !means.value.trim()) return;
    localStorage.setItem("gist.words", JSON.stringify([...localWords(), { term: term.value.trim(), means: means.value.trim() }]));
    sendGlossary(); term.value = means.value = ""; draw(); toast("Saved. Try your question again.");
  };
  openModal(h("div", { class: "sheet" },
    h("header", {}, h("h2", {}, "Business words"),
      h("p", { class: "sub" }, "Teach the assistant the words your business uses. If you say “takings” and the file says “Sales Amount”, add it here and questions will match.")),
    h("div", { class: "body stack" },
      h("div", { class: "row" }, "When I say", term, "it means", means, h("button", { class: "primary small", onclick: add }, "Add word"),
        h("datalist", { id: "fieldList" }, fields.map((f) => h("option", { value: f })))),
      list,
      h("p", { class: "muted" }, "Words added here are kept in this browser only. Words in the project notes file apply for everyone who uses this app.")),
    h("footer", {}, h("button", { class: "secondary", onclick: closeModal }, "Done"))));
  (prefill ? means : term).focus();
}
$("wordsBtn").addEventListener("click", () => openWords());

// ---------------------------------------------------------------- modal
function openModal(node) { const m = $("modal"); m.replaceChildren(node); m.hidden = false; }
function closeModal() { $("modal").hidden = true; $("modal").replaceChildren(); }
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("modal").hidden) closeModal(); });

// ---------------------------------------------------------------- bringing files in
const fileInput = $("fileInput");
$("chooseBtn").addEventListener("click", () => fileInput.click());
$("addBtn").addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => { if (fileInput.files.length) readFiles([...fileInput.files]); fileInput.value = ""; });
$("sampleBtn").addEventListener("click", async (e) => {
  e.stopPropagation();
  const names = ["sales_orders.xlsx", "customers.csv", "products.xlsx", "q3_business_review.docx", "strategy_update.pptx"];
  busy("Fetching the sample files…");
  try {
    const files = await Promise.all(names.map(async (n) => ({ name: n, buffer: await (await fetch("sample-data/" + n)).arrayBuffer() })));
    readFiles(files);
  } catch (err) { closeModal(); toast("Could not load the sample files."); }
});
let dragDepth = 0;
const hasFiles = (e) => e.dataTransfer && [...e.dataTransfer.types].includes("Files");
window.addEventListener("dragenter", (e) => { if (hasFiles(e)) { e.preventDefault(); dragDepth++; $("overlay").hidden = false; } });
window.addEventListener("dragleave", (e) => { if (hasFiles(e)) { dragDepth--; if (dragDepth <= 0) { dragDepth = 0; $("overlay").hidden = true; } } });
window.addEventListener("dragover", (e) => { if (hasFiles(e)) e.preventDefault(); });
window.addEventListener("drop", (e) => {
  if (!hasFiles(e)) return;
  e.preventDefault(); dragDepth = 0; $("overlay").hidden = true;
  if (e.dataTransfer.files.length) readFiles([...e.dataTransfer.files]);
});

// ---- the three steps after files are added: 1 what I found, 2 tidy, 3 what to understand
const orbEl = (size) => h("span", { class: "orb " + (size || ""), "aria-hidden": "true" },
  h("span", { class: "core" }, ["haze", "mn", "cy", "pk", "vi", "bl", "lit"].map((c) => h("i", { class: c }))));
document.querySelectorAll("[data-orb]").forEach((el) => el.replaceWith(orbEl(el.dataset.orb)));
const aura = () => h("span", { class: "aura", "aria-hidden": "true" }, h("i"), h("i"), h("i"), h("b"), h("b"));
// The progress bar: each part is a button that takes you back (or forward) to that step once your data is in.
const STEP_NAMES = ["Your files", "Match your fields", "Tidy", "Choose what to understand"];
function stepper(n) {
  const back = n === 1 ? leaveFlow : () => goStep(n - 1);
  return h("nav", { class: "stepper", "aria-label": "Steps" },
    h("button", { class: "back small-back", title: n === 1 ? "Back" : `Back to step ${n - 1}`, onclick: back }, h("span", { "aria-hidden": "true" }, "←"), " Back"),
    h("span", {}, `Step ${n} of 4`),
    h("span", { class: "bars" }, [1, 2, 3, 4].map((i) => h("button", {
      class: (i <= n ? "on" : "") + (i === n ? " cur" : ""), title: STEP_NAMES[i - 1], "aria-label": `Step ${i}: ${STEP_NAMES[i - 1]}`,
      "aria-current": i === n ? "step" : null, disabled: i !== n && (!S.state || (S.pending && i > 1)) ? true : null,
      onclick: () => { if (i !== n) goStep(i); } }, h("i")))));
}
// ---- data catalogues: "what Gist needs" matched to "what you have", saved by name in this browser (names only, never data)
const CAT_KEY = "gist.catalogues";
const catalogues = () => { try { return JSON.parse(localStorage.getItem(CAT_KEY) || "[]"); } catch { return []; } };
const saveCatalogues = (list) => { try { localStorage.setItem(CAT_KEY, JSON.stringify(list)); } catch {} };
S.roles = {}; S.custom = []; S.catalogue = null;
function catalogueWords() {
  const words = { date: "date", sales: "sales", qty: "quantity", cost: "cost", customer: "customer", product: "product", order: "order", region: "region", rep: "salesperson", target: "target" };
  return [...Object.entries(S.roles).filter(([k, v]) => v && words[k]).map(([k, v]) => ({ term: words[k], means: v, from: "catalogue" })),
          ...S.custom.filter((c) => c.label && c.column).map((c) => ({ term: c.label, means: c.column, from: "catalogue" }))];
}
function bestCatalogue(columnNames) {
  const have = new Set(columnNames);
  let best = null, score = 0;
  for (const c of catalogues()) {
    const n = Object.values(c.fields || {}).filter((v) => have.has(v)).length + (c.custom || []).filter((x) => have.has(x.column)).length;
    if (n > score) { best = c; score = n; }
  }
  return best;
}
function downloadCatalogue(c) {
  download(`${c.name}.gist-catalogue.json`, new Blob([JSON.stringify({ gist_catalogue: 1, name: c.name, fields: c.fields, custom: c.custom || [], kinds: c.kinds || {} }, null, 2)], { type: "application/json" }));
}
function loadCatalogueFile(done) {
  const input = h("input", { type: "file", accept: ".json,application/json", hidden: true });
  input.addEventListener("change", async () => {
    try {
      const o = JSON.parse(await input.files[0].text());
      if (!o || !o.gist_catalogue || !o.name || typeof o.fields !== "object") throw new Error("not a Gist catalogue");
      const list = catalogues().filter((c) => c.name !== o.name);
      list.push({ id: "c" + Date.now(), name: String(o.name).slice(0, 60), fields: o.fields, custom: Array.isArray(o.custom) ? o.custom : [], kinds: o.kinds && typeof o.kinds === "object" ? o.kinds : {} });
      saveCatalogues(list); toast(`Loaded the “${o.name}” catalogue.`); done && done();
    } catch (err) { toast("That file is not a Gist catalogue."); }
    input.remove();
  });
  document.body.append(input); input.click();
}

// Step 2: what Gist needs, matched to what your files call it, and how each number is used.
// Returning users whose saved catalogue fits see a one-line page; everyone can go with Gist's guesses in one tap.
const PLAIN = { date: "The date", sales: "Sales", qty: "Quantity", cost: "Cost", customer: "Customer", product: "Product",
                order: "Order number", region: "Where", rep: "Salesperson", target: "Target or budget" };
const NUMBER_NEEDS = ["sales", "qty", "cost", "target"];
async function stepMatch(review, forceFull) {
  busy("Reading your column names…");
  const [r, chk] = await Promise.all([call("catalogue_start"), call("story_checks")]);
  const names = r.columns.map((c) => c.name);
  const saved = (review && S.catalogue && catalogues().find((c) => c.id === S.catalogue)) || bestCatalogue(names);
  // how each number column is used: added up, or averaged (from the saved catalogue, else Gist's guess)
  const kinds = {};
  for (const t of chk.tables) for (const m of t.measures) if (!(m.name in kinds)) kinds[m.name] = m.kind;
  const main = chk.tables[0] || {};
  let complete = main.last_month ? main.complete : null;
  let current = saved, fields = {}, custom = [];
  const fill = (cat) => {
    fields = {};
    for (const n of r.needs) {
      const v = cat ? (cat.fields || {})[n.key] : (review && Object.keys(S.roles).length ? S.roles[n.key] : r.guess[n.key]);
      fields[n.key] = v && names.includes(v) ? v : "";
    }
    custom = (cat ? cat.custom || [] : review ? S.custom : []).map((c) => ({ ...c }));
    if (cat && cat.kinds) for (const [col, k] of Object.entries(cat.kinds)) if (col in kinds) kinds[col] = k;
  };
  fill(saved);

  const finish = async (btn) => {
    document.querySelectorAll("#view-flow .match-go").forEach((b) => (b.disabled = true));
    S.roles = { ...fields }; S.custom = custom.filter((c) => c.label && c.column); S.catalogue = current ? current.id : null;
    const answers = chk.tables.map((t, i) => ({ dataset: t.dataset, kinds: Object.fromEntries(t.measures.map((m) => [m.name, kinds[m.name]])),
      date: fields.date && t.dates.includes(fields.date) ? fields.date : t.date, complete: i === 0 && t.last_month ? complete : null }));
    await call("catalogue_set", { roles: S.roles });
    const res = await call("story_set_checks", { answers });
    S.pick = { ...(S.pick || {}), options: res.options };
    if (S.story) S.story.fresh = true;
    sendGlossary();
    stepTidy();
  };
  const goBtn = () => h("button", { class: "primary big match-go", onclick: (e) => finish(e.target) }, "Looks right, continue");

  // returning user: one line, one button
  const matchedNow = Object.values(fields).filter(Boolean);
  if (saved && !review && !forceFull && matchedNow.length) {
    flowPage(2,
      h("h1", { class: "ask-big" }, `I used your “${saved.name}” catalogue.`),
      h("p", { class: "frame" }, `It matched ${plural(matchedNow.length, "field")}, such as ${matchedNow.slice(0, 3).join(", ")}.`),
      h("div", { class: "flow-actions" }, goBtn(), h("button", { class: "link", onclick: () => stepMatch(true, true) }, "Review the matches")));
    return;
  }

  const options = (value) => h("select", { class: "pill-select", "aria-label": "What you have" },
    h("option", { value: "" }, "Not in my files"),
    [...new Set(r.columns.map((c) => c.table))].map((t) => h("optgroup", { label: t }, r.columns.filter((c) => c.table === t).map((c) => h("option", { value: c.name, selected: c.name === value }, c.name)))));
  const kindTag = (col) => {
    if (!col || !(col in kinds)) return null;
    const tag = h("button", { class: "kind-tag", type: "button" });
    const draw = () => { tag.replaceChildren(kinds[col] === "rate" ? "averaged" : "added up", h("span", {}, " · change")); tag.title = kinds[col] === "rate" ? "Averaged, like a price or a percentage. Tap to add it up instead." : "Added up, like money or a count. Tap to average it instead."; };
    tag.addEventListener("click", () => { kinds[col] = kinds[col] === "rate" ? (/qty|quantity|count|units/i.test(col) ? "count" : "money") : "rate"; draw(); });
    draw();
    return tag;
  };
  const monthTag = () => {
    if (!main.last_month) return null;
    const tag = h("button", { class: "kind-tag", type: "button" });
    const draw = () => tag.replaceChildren(`${main.last_month} ${complete ? "is complete" : "is still running"}`, h("span", {}, " · change"));
    tag.title = main.why || "";
    tag.addEventListener("click", () => { complete = !complete; draw(); });
    draw();
    return tag;
  };
  const row = (label, key, extraFor) => {
    const sel = options(fields[key]);
    const extras = h("div", { class: "match-extra" });
    const drawExtra = () => extras.replaceChildren(key === "date" && fields.date ? monthTag() : null, NUMBER_NEEDS.includes(key) ? kindTag(fields[key]) : null);
    sel.addEventListener("change", () => { fields[key] = sel.value; drawExtra(); });
    drawExtra();
    return h("div", { class: "mrow" }, h("div", { class: "mneed" }, label), h("div", { class: "mhave" }, sel, extras));
  };
  const body = h("div", { class: "match-body" });
  const draw = () => {
    const found = r.needs.filter((n) => fields[n.key]), missing = r.needs.filter((n) => !fields[n.key]);
    const used = new Set(Object.values(fields).filter(Boolean));
    const others = Object.keys(kinds).filter((c) => !used.has(c));
    body.replaceChildren(
      h("div", { class: "mcols" }, h("span", {}, "What Gist needs"), h("span", {}, "What you have")),
      found.map((n) => row(PLAIN[n.key] || n.label, n.key)),
      custom.filter((c) => c.label).map((c) => h("div", { class: "mrow" }, h("div", { class: "mneed" }, c.label), h("div", { class: "mhave" }, (() => { const s2 = options(c.column); s2.addEventListener("change", () => (c.column = s2.value)); return s2; })()))),
      missing.length ? h("details", { class: "mfold" }, h("summary", {}, `Not in your files (${missing.length}): ${missing.map((n) => PLAIN[n.key] || n.label).join(", ")}`),
        h("p", { class: "muted" }, "If one of these is in your files under another name, pick it."),
        missing.map((n) => row(PLAIN[n.key] || n.label, n.key))) : null,
      others.length ? h("details", { class: "mfold" }, h("summary", {}, `Other numbers (${others.length}): ${others.join(", ")}`),
        h("p", { class: "muted" }, "How Gist uses these when you pick one as the subject."),
        others.map((c) => h("div", { class: "mrow" }, h("div", { class: "mneed" }, c), h("div", { class: "mhave" }, kindTag(c))))) : null,
      h("div", { class: "madd" }, (() => {
        const box = h("span", {});
        const show = () => box.replaceChildren(h("button", { class: "link", onclick: ask }, "+ Add a field of your own"));
        const ask = () => {
          const name = h("input", { type: "text", placeholder: "e.g. Project code", "aria-label": "Your field" });
          const sel = options("");
          const ok = () => { if (name.value.trim() && sel.value) { custom.push({ label: name.value.trim(), column: sel.value }); draw(); } else name.focus(); };
          box.replaceChildren(name, sel, h("button", { class: "secondary", onclick: ok }, "Add"), h("button", { class: "link", onclick: show }, "Cancel"));
          name.focus();
        };
        show();
        return box;
      })()));
  };
  draw();

  const chooser = h("select", { class: "cat-choose", "aria-label": "Catalogue", onchange: (e) => {
    current = catalogues().find((c) => c.id === e.target.value) || null; fill(current); draw(); drawSave();
  } }, h("option", { value: "" }, "Gist's guesses"), catalogues().map((c) => h("option", { value: c.id, selected: current && c.id === current.id }, c.name)));
  const saveBox = h("div", { class: "cat-save" });
  const catKinds = () => Object.fromEntries(Object.entries(kinds));
  const drawSave = (asking) => {
    if (asking) {
      const name = h("input", { type: "text", placeholder: "Name it, e.g. Accounting", "aria-label": "Catalogue name", value: asking === "new" ? "" : (current || {}).name || "" });
      const ok = () => {
        const nm = name.value.trim(); if (!nm) { name.focus(); return; }
        const keep = { id: (asking === "update" && current) ? current.id : "c" + Date.now(), name: nm, fields: { ...fields }, custom: custom.filter((c) => c.label && c.column), kinds: catKinds() };
        saveCatalogues([...catalogues().filter((c) => c.id !== keep.id && c.name !== nm), keep]);
        current = keep; chooser.append(h("option", { value: keep.id }, nm)); chooser.value = keep.id;
        toast(`Saved as “${nm}”. Next time Gist will fill this in for you.`); drawSave();
      };
      name.addEventListener("keydown", (e) => { if (e.key === "Enter") ok(); });
      saveBox.replaceChildren(name, h("button", { class: "secondary", onclick: ok }, "Save"), h("button", { class: "link", onclick: () => drawSave() }, "Cancel"));
      setTimeout(() => name.focus(), 30);
    } else {
      saveBox.replaceChildren(
        current ? h("button", { class: "secondary", onclick: () => drawSave("update") }, `Save changes to “${current.name}”`) : null,
        h("button", { class: current ? "link" : "secondary", onclick: () => drawSave("new") }, current ? "Save as a new catalogue" : "Save these matches as a catalogue"));
    }
  };
  drawSave();
  const found = Object.values(fields).filter(Boolean).length;
  flowPage(2,
    h("h1", { class: "ask-big" }, "Match your fields"),
    h("p", { class: "frame" }, current ? `Filled in from your “${current.name}” catalogue.` : `I found ${found} of the ${r.needs.length} things I look for.`, " If it looks right, just continue."),
    h("div", { class: "flow-actions at-top" }, goBtn()),
    h("div", { class: "cat-bar" }, h("label", {}, "Starting from ", chooser)),
    body,
    h("div", { class: "flow-actions" }, goBtn(), saveBox));
}

function goStep(i) {
  S.pending = false;
  if (i === 1) reviewFiles();
  else if (i === 2) stepMatch(true);
  else if (i === 3) stepTidy(true);
  else show("pick");
}

function seg(options, value, onPick, label) {
  const wrap = h("div", { class: "seg", role: "radiogroup", "aria-label": label });
  const draw = (v) => wrap.replaceChildren(...options.map(([k, text]) => h("button", { type: "button", role: "radio", "aria-checked": String(k === v), onclick: () => { draw(k); onPick(k); } }, text)));
  draw(value);
  return wrap;
}
// Step 1 again, once the data is in: what was added, with the details folded away.
function reviewFiles() {
  const tables = S.state.datasets.filter((d) => d.kind === "table"), docs = S.state.documents || [];
  flowPage(1,
    h("h1", { class: "ask-big" }, tables.length ? `You added ${plural(tables.length, "table")}.` : "You added text, but no tables of numbers."),
    h("p", { class: "frame" }, "Check this is what you expected, then continue."),
    h("div", { class: "flow-actions" }, h("button", { class: "primary big", onclick: () => stepMatch(true) }, "Continue"),
      h("button", { class: "link", onclick: () => fileInput.click() }, "Add more files")),
    h("details", { class: "flow-more" }, h("summary", {}, "Show details"),
      h("ul", {}, tables.map((d) => h("li", {}, h("strong", {}, d.name), ` — ${plural(d.rows, "row")}, ${plural(d.columns.length, "field")}, from ${d.source}`)),
        docs.length ? h("li", {}, `${plural(docs.length, "document")} with text you can ask about`) : null)));
}
function flowPage(step, ...kids) {
  if (S.view !== "flow") show("flow");
  $("view-flow").replaceChildren(h("div", { class: "flow arrive" }, step ? stepper(step) : null, ...kids));
}
function leaveFlow() { S.flow = false; S.pending = false; show(S.state ? (S.story ? "story" : "pick") : "welcome"); }

const MIN_WAIT = 3000;
const atLeast = (ms, work) => Promise.all([work, new Promise((r) => setTimeout(r, ms))]).then(([v]) => v);
let busyTimer = null;
function waitScreen(lines, ms = MIN_WAIT) {
  lines = [].concat(lines);
  const text = h("p", { class: "flow-text", "aria-live": "polite" }, lines[0]);
  clearInterval(busyTimer);
  let i = 0;
  if (lines.length > 1) busyTimer = setInterval(() => {
    if (!text.isConnected || i >= lines.length - 1) return clearInterval(busyTimer);
    text.classList.add("swap");
    setTimeout(() => { text.textContent = lines[++i]; text.classList.remove("swap"); }, 380);
  }, Math.max(600, ms / lines.length));
  return h("div", { class: "flow-wait" }, orbEl("mid"), text,
    engineReady ? null : h("p", { class: "muted" }, "The first visit takes a little longer while the engine downloads."));
}
function busy(lines) { flowPage(null, waitScreen(lines)); }

async function readFiles(files) {
  S.flow = true;
  busy([`Reading ${files.length === 1 ? files[0].name : "your " + files.length + " files"}…`, "Looking through every row…", "Working out what each column holds…"]);
  const previews = await atLeast(MIN_WAIT, (async () => {
    const out = [];
    for (const f of files) {
      try {
        const buffer = f.buffer || (await f.arrayBuffer());
        out.push(await call("preview", { name: f.name }, buffer));
      } catch (err) { out.push({ file: f.name, error: "I couldn't read this file. (" + err.message + ")" }); }
    }
    return out;
  })());
  showPreview(previews);
}

// Step 1: say what was found in one sentence. Names, fields and previews stay folded away.
function showPreview(previews) {
  const picks = [];   // {token, index|'text', include, name}
  const body = h("div", { class: "found-list" });
  for (const p of previews) {
    body.append(h("div", { class: "file-name" }, p.file));
    if (p.error) { body.append(h("div", { class: "found" }, h("p", {}, p.error))); continue; }
    for (const t of p.tables) {
      const pick = { token: p.token, index: String(t.index), include: true, name: t.name };
      picks.push(pick);
      body.append(h("div", { class: "found" },
        h("div", { class: "head" },
          h("input", { type: "checkbox", checked: true, "aria-label": "Include " + t.name, onchange: (e) => { pick.include = e.target.checked; count(); } }),
          h("input", { type: "text", value: t.name, "aria-label": "Table name", oninput: (e) => (pick.name = e.target.value) }),
          h("span", { class: "muted" }, `${plural(t.rows, "row")}, ${plural(t.columns.length, "field")}, from ${t.where}`)),
        h("div", { class: "types" }, t.columns.map((c) => h("span", { class: "chip" }, c.name, h("span", { class: "t" }, TYPE_WORD[c.type])))),
        renderTable(t.columns.map((c) => c.name), t.sample, t.columns.map((c) => c.type)),
        t.notes.map((n) => h("p", { class: "notice" }, n.text))));
    }
    if (p.text_count) {
      const pick = { token: p.token, index: "text", include: true };
      picks.push(pick);
      body.append(h("div", { class: "found" },
        h("div", { class: "head" },
          h("input", { type: "checkbox", checked: true, "aria-label": "Include text", onchange: (e) => { pick.include = e.target.checked; count(); } }),
          h("strong", {}, `${plural(p.text_count, "piece")} of text`)),
        h("p", { class: "muted", style: "margin-top:6px" }, "For example: “" + (p.text_sample[0] || "") + "”")));
    }
  }
  const tables = picks.filter((k) => k.index !== "text").length;
  const bad = previews.filter((p) => p.error).map((p) => p.file);
  const files = previews.length;
  S.pending = true;
  const go = h("button", { class: "primary big" }, "Looks right, continue");
  const count = () => { const n = picks.filter((k) => k.include).length; go.disabled = !n; go.textContent = n ? "Looks right, continue" : "Nothing selected"; };
  go.addEventListener("click", async () => {
    S.pending = false;
    busy("Bringing your data in…");
    let st = null;
    for (const p of previews.filter((p) => p.token)) {
      const choices = {};
      picks.filter((k) => k.token === p.token).forEach((k) => (choices[k.index] = { include: k.include, name: k.name }));
      st = await call("confirm", { token: p.token, choices });
    }
    if (!st) return leaveFlow();
    S.checks = {};
    setState(st);
    S.current = (st.datasets.find((d) => d.health && d.health.to_review) || st.datasets[0] || {}).id || null;
    S.story = null; S.pick = null;
    if (!st.datasets.length) { S.flow = false; show("ask"); return; }
    stepMatch();
  });
  const tpls = [...new Set(previews.flatMap((p) => (p.tables || []).map((t) => t.template).filter(Boolean)))];
  const say = tables ? `I found ${plural(tables, "table")} in your ${files === 1 ? "file" : "files"}.`
    : picks.length ? "I found text in your files, but no tables of numbers." : `I couldn't read ${files === 1 ? "this file" : "these files"}.`;
  flowPage(1,
    h("h1", { class: "ask-big" }, say),
    h("p", { class: "frame" }, tables ? (tpls.length ? `Recognised ${tpls.length === 1 ? "an export" : "exports"} from ${tpls.join(" and ")}, and tidied the report layout. ` : "") + "Check this is what you expected, then continue." : picks.length ? "You can still ask questions about the text." : "Try saving it as Excel or CSV, then add it again."),
    bad.length && picks.length ? h("p", { class: "caution" }, `I couldn't read ${bad.join(", ")}.`) : null,
    h("div", { class: "flow-actions" }, picks.length ? go : h("button", { class: "primary big", onclick: () => fileInput.click() }, "Choose other files"),
      h("button", { class: "link", onclick: leaveFlow }, picks.length ? "Start again with other files" : "Go back")),
    picks.length ? h("details", { class: "flow-more" }, h("summary", {}, "Show details"),
      h("p", { class: "muted" }, "Untick anything you do not want, or rename a table."), body) : null);
}

// Step 2: one button tidies everything Gist is sure about. Skipped when there is nothing to tidy.
async function stepTidy(review) {
  busy("Checking your data…");
  const o = await call("story_options");
  S.pick = o;
  const t = o.tidy, n = t.fixes + t.links;
  if (!n && !review) { show("pick"); return; }
  if (!n) {
    flowPage(3,
      h("h1", { class: "ask-big" }, "Everything is tidy."),
      h("p", { class: "frame" }, t.to_review ? `${plural(t.to_review, "item")} still need${t.to_review === 1 ? "s" : ""} a person's judgement, such as unusually large values. They are not changed.` : "There is nothing left to fix."),
      h("div", { class: "flow-actions" }, h("button", { class: "primary big", onclick: () => show("pick") }, "Continue"),
        t.to_review ? h("button", { class: "link", onclick: () => show("data") }, "Look at them") : null));
    return;
  }
  const fix = h("button", { class: "primary big", onclick: async () => {
    busy(["Tidying your data…", "Applying the safe fixes…", "Checking the result…"]);
    const r = await atLeast(MIN_WAIT, call("story_tidy"));
    S.checks = {}; setState(r.state); S.pick = { options: r.options, tidy: r.tidy };
    toast(`${plural(r.done.length, "fix", "fixes")} applied.`);
    show("pick");
  } }, "Fix them all");
  flowPage(3,
    h("h1", { class: "ask-big" }, `I found ${plural(n, "thing")} to tidy.`),
    h("p", { class: "frame" }, "Tidying makes the story more accurate. Your original files are not changed."),
    h("div", { class: "flow-actions" }, fix, h("button", { class: "link", onclick: () => show("pick") }, "Skip for now")),
    h("details", { class: "flow-more" }, h("summary", {}, "Show details"),
      h("ul", {},
        t.fixes ? h("li", {}, `${plural(t.fixes, "safe fix", "safe fixes")}, such as repeated rows, names spelt in different ways, or dates written in different formats.`) : null,
        t.links ? h("li", {}, `${plural(t.links, "pair")} of tables that belong together. Linking them lets the story use fields from both.`) : null,
        t.to_review ? h("li", {}, `${plural(t.to_review, "item")} that need${t.to_review === 1 ? "s" : ""} a person's judgement, such as unusually large values. These are not changed; you can look at them later under Explore further, then Your data.`) : null)));
}

// ---------------------------------------------------------------- Your data: health check and linking
async function renderData() {
  const root = $("view-data");
  const st = S.state;
  const ds = datasetById(S.current);
  const rail = h("aside", { class: "rail" },
    h("h3", {}, "Tables"),
    st.datasets.map((d) => h("button", { class: "item", "aria-current": String(d.id === S.current), onclick: () => { S.current = d.id; renderData(); } },
      h("span", {}, d.name),
      d.health && d.health.to_review ? h("span", { class: "flag", title: "Items to review" }, d.health.to_review) : h("span", { class: "n" }, fmtNum(d.rows)))),
    h("div", { style: "margin-top:18px" }, h("button", { class: "secondary small", onclick: () => fileInput.click() }, "Add files")));
  const main = h("div", {});
  const fixBox = h("div", { class: "fixall" }, h("p", { class: "muted" }, h("span", { class: "spinner" }), "Checking…"));
  const measureBox = h("div", { class: "measures-box" });
  root.replaceChildren(h("h2", {}, "Your data"), fixBox, h("div", { class: "data-grid" }, rail, main), measureBox);
  drawMeasures(measureBox);
  call("story_options").then((o) => {
    S.pick = o;
    const t = o.tidy, n = t.fixes + t.links;
    const fixAll = async (e) => {
      e.target.disabled = true; e.target.textContent = "Fixing…";
      fixBox.replaceChildren(waitScreen(["Tidying your data…", "Applying the safe fixes…", "Checking the result…"]));
      const r = await atLeast(MIN_WAIT, call("story_tidy"));
      S.checks = {}; setState(r.state); S.pick = { options: r.options, tidy: r.tidy };
      if (S.story) { const same = r.options.find((x) => x.value === S.story.spec.value); if (same) S.story.spec.dataset = same.dataset; }
      toast(r.done.length ? `${plural(r.done.length, "fix", "fixes")} applied.` : "Nothing to fix automatically.");
      renderData();
    };
    fixBox.replaceChildren(
      h("div", { class: "grow" },
        h("p", { class: "fix-say" }, n ? `${plural(n, "thing")} can be fixed in one click.` : "Everything that can be fixed automatically is done."),
        h("p", { class: "muted" }, n ? "Safe fixes only, such as repeated rows and tables that belong together. Your original files are not changed."
          : t.to_review ? `${plural(t.to_review, "item")} still need${t.to_review === 1 ? "s" : ""} your judgement. Each one is listed under its table.` : "Your data looks clean.")),
      h("div", { class: "fix-btns" },
        n ? h("button", { class: "primary big", onclick: fixAll }, "Fix all") : null,
        h("button", { class: n ? "secondary big" : "primary big", onclick: () => show("story") }, "Back to the story")));
  });
  if (!ds) { main.append(h("div", { class: "card placeholder" }, h("b", {}, "No tables yet"), "Your documents are ready to search. Go to Ask.")); return; }

  main.append(h("div", { class: "card pad" },
    h("h3", { style: "font-size:20px" }, ds.name),
    h("p", { class: "muted" }, `${plural(ds.rows, "row")}, ${ds.kind === "linked" ? "combined from linked tables" : "from " + ds.source}`)));

  if (ds.kind === "linked") {
    main.append(h("div", { class: "section-title" }, "How this table was put together"),
      h("div", { class: "card" }, ds.parts.map((p) => h("div", { class: "join" },
        h("div", {}, h("div", { class: "pair" }, `Linked with ${p.with} `, h("em", {}, `using ${p.on}`))),
        h("button", { class: "secondary small", onclick: async () => { setState(await call("remove_link", { link: p.link })); renderData(); } }, "Unlink")))));
  } else {
    const box = h("div", { class: "card" }, h("div", { class: "pad muted" }, h("span", { class: "spinner" }), "Checking…"));
    const title = h("div", { class: "row section-title" }, h("span", { class: "grow" }, "Things to review"));
    main.append(title, box);
    const check = S.checks[ds.id] || (S.checks[ds.id] = await call("check", { dataset: ds.id }));
    if (S.current !== ds.id) return;
    const apply = async (fn, args) => {
      box.style.opacity = ".5";
      const r = await call(fn, args);
      S.checks = { [ds.id]: r.check };
      setState(r.state);
      if (r.result && r.result.text) toast(r.result.text);
      if (r.done) toast(r.done.length ? `${plural(r.done.length, "fix", "fixes")} applied.` : "Nothing to fix automatically.");
      renderData();
    };
    if (st.log.some((l) => l.dataset === ds.id)) title.append(h("button", { class: "link small", onclick: () => apply("restore", { dataset: ds.id }) }, "Undo all changes to this table"));
    box.replaceChildren(check.issues.length ? "" : h("div", { class: "pad allclear" }, "✓ Nothing to review. This table looks clean."),
      ...check.issues.map((i) => h("div", { class: "issue" },
        h("h4", {}, i.title),
        h("div", { class: "row" },
          i.fix ? h("button", { class: "primary", onclick: () => apply("fix", { dataset: ds.id, key: i.key }) }, i.fix) : null,
          h("button", { class: "secondary", onclick: () => apply("dismiss", { dataset: ds.id, key: i.key }) }, i.keep)),
        h("details", {}, h("summary", {}, "Show details"),
          h("p", {}, i.detail + (i.note ? ` (${i.note}.)` : "")),
          h("p", { class: "muted" }, `How sure I am that this is a real problem: ${i.confidence.toLowerCase()}.`),
          i.examples && i.examples.rows.length ? renderTable(i.examples.columns, i.examples.rows) : null))));
  }

  if (st.joins.length) {
    main.append(h("div", { class: "section-title" }, "Tables that belong together"),
      h("p", { class: "sub", style: "margin:-6px 0 12px" }, "Linking lets you ask one question across both tables, for example sales by customer segment."),
      h("div", { class: "card" }, st.joins.map((j) => h("div", { class: "join" },
        h("div", {},
          h("span", { class: "pair" }, `${j.a_name} + ${j.b_name}`),
          h("details", {}, h("summary", {}, "Show details"),
          h("p", {}, `Matched on ${j.a_col}. How sure I am: ${j.confidence.toLowerCase()}.`),
          h("div", { class: "row", style: "margin-top:4px" }, h("div", { class: "meter", role: "img", "aria-label": j.match + "% match" }, h("i", { style: `width:${j.match}%` })), h("strong", {}, j.match + "% match"),
            h("span", { class: "muted" }, j.unmatched ? `${plural(j.unmatched, "row")} in ${j.a_name} have no partner (e.g. ${j.unmatched_examples.slice(0, 3).join(", ")})` : "every row finds a partner")),
          h("p", { class: "muted", style: "margin-top:8px" }, "Why I suggest this:"), h("ul", { style: "margin:0;padding-left:20px" }, j.why.map((w) => h("li", {}, w)),
            h("li", {}, `Adds these fields to ${j.a_name}: ${j.adds.slice(0, 8).join(", ")}`)))),
        h("button", { class: "primary", onclick: async () => {
          const r = await call("accept_join", { key: j.key });
          setState(r.state); S.current = r.result.dataset || S.current; renderData();
          toast(`Linked. “${datasetById(S.current).name}” is ready to use.`);
        } }, "Link these tables")))));
  }

  const peek = await call("build", { spec: { dataset: ds.id, mode: "rows", limit: 12 } });
  if (S.current !== ds.id || S.view !== "data") return;
  main.append(h("details", { class: "peek" }, h("summary", {}, "Show a sample of the rows"),
    h("div", { class: "types", style: "margin:12px 0 10px" }, ds.columns.map((c) => h("span", { class: "chip" }, c.name, h("span", { class: "t" }, TYPE_WORD[c.type])))),
    renderTable(peek.columns, peek.rows, peek.types)));
  if (st.log.length) main.append(h("details", { style: "margin-top:20px" }, h("summary", {}, "History of changes"), h("ol", { class: "muted", style: "margin:0;padding-left:20px" }, st.log.map((l) => h("li", {}, l.text)))));
}

// ---- measures built from two numbers: suggested ones, and ones the owner makes
function measureDataset() {
  return (S.story && S.story.spec.dataset) || (((S.pick || {}).options || [])[0] || {}).dataset || null;
}
async function drawMeasures(box) {
  const dsId = measureDataset();
  if (!dsId) { box.replaceChildren(); return; }
  const m = await call("measure_list", { dataset: dsId });
  box.replaceChildren(
    h("div", { class: "section-title row" }, h("span", { class: "grow" }, "Measures built from two numbers"),
      h("button", { class: "primary", onclick: () => openMeasureMaker(dsId, m, () => drawMeasures(box)) }, "Make a measure")),
    h("div", { class: "card" },
      m.suggested.length || m.mine.length ? null : h("div", { class: "pad muted" }, "None yet. Make one, for example Sales Amount divided by Quantity."),
      [...m.suggested.map((x) => [x, false]), ...m.mine.map((x) => [x, true])].map(([x, mine]) => h("div", { class: "join" },
        h("div", {}, h("span", { class: "pair" }, x.label), h("p", { class: "muted" }, x.formula + (mine ? "" : " Suggested automatically."))),
        mine ? h("button", { class: "secondary", onclick: async () => { const r = await call("measure_remove", { value: x.value }); S.pick = { ...(S.pick || {}), options: r.options }; drawMeasures(box); } }, "Remove") : null))));
}
function openMeasureMaker(dsId, m, done) {
  const opt = (v) => h("option", { value: v }, v);
  const name = h("input", { type: "text", placeholder: "e.g. Sales per unit", "aria-label": "Name" });
  const a = h("select", { "aria-label": "First number" }, m.numbers.map(opt));
  const op = h("select", { "aria-label": "How to combine" },
    h("option", { value: "divide" }, "divided by"), h("option", { value: "minus" }, "minus"),
    m.ids.length ? h("option", { value: "per_id" }, "per different") : null, h("option", { value: "per_row" }, "per row"));
  const b = h("select", { "aria-label": "Second number" });
  const fillB = () => { b.hidden = op.value === "per_row"; b.replaceChildren(...(op.value === "per_id" ? m.ids : m.numbers).map(opt)); };
  op.addEventListener("change", fillB); fillB();
  const save = async () => {
    const r = await call("measure_add", { dataset: dsId, name: name.value || `${a.value} ${op.options[op.selectedIndex].text} ${op.value === "per_row" ? "" : b.value}`.trim(), a: a.value, op: op.value, b: op.value === "per_row" ? null : b.value });
    S.pick = { ...(S.pick || {}), options: r.options };
    closeModal(); toast(`“${r.added.label}” is ready. Pick it from the number button on any card.`); done();
  };
  openModal(h("div", { class: "sheet", style: "width:min(620px,100%)" },
    h("header", {}, h("h2", {}, "Make a measure"), h("p", { class: "sub" }, `Combine two numbers from ${m.base}. Gist works it out for every period and group, and shows the formula in "How I got this".`)),
    h("div", { class: "body stack" }, h("label", { class: "stack" }, "Name", name), h("div", { class: "row" }, "Total", a, op, b)),
    h("footer", {}, h("button", { class: "secondary", onclick: closeModal }, "Cancel"), h("button", { class: "primary", onclick: save }, "Save measure"))));
  name.focus();
}

// ---------------------------------------------------------------- Catalogues: view, rename, download, load and delete
function renderCatalogues() {
  const root = $("view-catalogues");
  const list = catalogues();
  const NEED_LABELS = { date: "Date", sales: "Sales amount", qty: "Quantity", cost: "Cost", customer: "Customer", product: "Product", order: "Order or invoice number", region: "Region or branch", rep: "Salesperson", target: "Target or budget" };
  const card = (c) => {
    const pairs = [...Object.entries(c.fields || {}).filter(([, v]) => v).map(([k, v]) => [NEED_LABELS[k] || k, v]), ...(c.custom || []).map((x) => [x.label, x.column])];
    const title = h("h3", {}, c.name);
    return h("div", { class: "card pad cat-card" },
      h("div", { class: "row" }, title, h("span", { class: "grow" }),
        h("button", { class: "secondary small", onclick: () => {
          const nm = prompt("New name for this catalogue", c.name); if (!nm || !nm.trim()) return;
          saveCatalogues(catalogues().map((x) => (x.id === c.id ? { ...x, name: nm.trim().slice(0, 60) } : x))); renderCatalogues();
        } }, "Rename"),
        h("button", { class: "secondary small", onclick: () => downloadCatalogue(c) }, "Download"),
        h("button", { class: "secondary small", onclick: () => { if (confirm(`Delete the “${c.name}” catalogue? This cannot be undone.`)) { saveCatalogues(catalogues().filter((x) => x.id !== c.id)); renderCatalogues(); } } }, "Delete")),
      pairs.length ? renderTable(["What Gist needs", "What you have"], pairs, ["text", "text"]) : h("p", { class: "muted" }, "Nothing matched yet."));
  };
  root.replaceChildren(
    h("h2", {}, "Data catalogues"),
    h("p", { class: "sub" }, "Each catalogue remembers what your columns are called in one system or format. Gist picks the right one automatically when you add files. Column names only; your data is never saved."),
    h("div", { class: "row", style: "margin:16px 0 20px" },
      S.state ? h("button", { class: "primary", onclick: () => stepMatch(true) }, "Match the fields in my current files") : null,
      h("button", { class: "secondary", onclick: () => loadCatalogueFile(renderCatalogues) }, "Load a catalogue file")),
    list.length ? h("div", { class: "stack" }, list.map(card)) : h("div", { class: "card placeholder" }, h("b", {}, "No catalogues yet"), "When you match your fields after adding files, press “Save as a catalogue” and name it, for example “Accounting”."));
}

// ---------------------------------------------------------------- Ask
let thread, composerInput, contextBox;
function renderAsk() {
  const root = $("view-ask");
  if (!thread) {
    thread = h("div", { class: "thread" });
    composerInput = h("input", { type: "text", placeholder: "Ask about your files…", "aria-label": "Your question", autocomplete: "off" });
    contextBox = h("div", {});
    root.classList.add("ask");
    root.append(thread, h("div", { class: "composer" }, contextBox,
      h("form", { onsubmit: (e) => { e.preventDefault(); ask(composerInput.value); } }, composerInput, h("button", { class: "primary", type: "submit" }, "Ask"))));
  }
  if (!thread.children.length) {
    thread.append(h("div", { class: "empty-ask", id: "askIntro" },
      h("h2", {}, "What would you like to know?"),
      h("p", { class: "sub" }, "I answer only from the files you uploaded, by matching your words to the words in them. If it is not in your files, I will say so."),
      h("div", { class: "suggest" }, S.state.suggestions.map((s) => h("button", { onclick: () => ask(s) }, s)))));
  }
  drawContext();
  composerInput.focus();
}
function drawContext() {
  if (!contextBox) return;
  contextBox.replaceChildren(S.context ? h("span", { class: "context" }, "Asking about: " + S.context.title,
    h("button", { "aria-label": "Stop asking about this result", onclick: () => { S.context = null; drawContext(); } }, "×")) : "");
}
function addMessage(node, who) {
  const intro = $("askIntro");
  if (intro) intro.remove();
  const m = h("div", { class: "msg " + who }, node);
  thread.append(m);
  m.scrollIntoView({ block: who === "you" ? "end" : "start", behavior: "smooth" });
  return m;
}
async function ask(question) {
  question = (question || "").trim();
  if (!question) return;
  composerInput.value = "";
  addMessage(h("div", {}, question), "you");
  const wait = addMessage(h("div", { class: "card answer muted" }, h("span", { class: "spinner" }), "Looking through your files…"), "bot");
  try {
    const a = await call("ask", { question, context: S.context });
    wait.replaceChildren(renderAnswer(a));
  } catch (err) {
    wait.replaceChildren(h("div", { class: "card answer" }, h("p", { class: "text" }, "Something went wrong while working that out."), h("p", { class: "muted" }, err.message)));
  }
}
function highlight(text, wordsToMark) {
  if (!wordsToMark || !wordsToMark.length) return [text];
  const re = new RegExp("\\b(" + wordsToMark.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|") + ")\\b", "gi");
  const out = []; let last = 0, m;
  while ((m = re.exec(text))) { out.push(text.slice(last, m.index), h("mark", {}, m[0])); last = m.index + m[0].length; }
  out.push(text.slice(last));
  return out;
}
function renderAnswer(a) {
  const card = h("div", { class: "card answer" });
  card.append(h("p", { class: "text" }, a.text));
  if (a.bullets && a.bullets.length) card.append(h("ul", {}, a.bullets.map((b) => h("li", {}, b))));
  const quote = (p) => h("blockquote", { class: "quote" }, highlight(p.text, p.highlight), h("cite", {}, `${p.source}, ${p.where}`));
  if (a.passages) a.passages.forEach((p) => card.append(quote(p)));
  if (a.ml && a.ml.kind === "forecast") {
    const c = h("canvas", { role: "img", "aria-label": a.ml.title });
    card.append(h("div", { class: "chart-box" }, c));
    requestAnimationFrame(() => drawForecast(c, a.ml));
  } else if (a.chart) {
    const c = h("canvas", { role: "img", "aria-label": "Chart of the answer" });
    card.append(h("div", { class: "chart-box" }, c));
    requestAnimationFrame(() => drawChart(c, a.chart));
  }
  if (a.table && (a.type !== "number") && a.table.rows.length) {
    card.append(renderTable(a.table.columns, a.table.rows, a.table.types));
    if (a.table.more) card.append(h("p", { class: "muted", style: "margin-top:6px;font-size:13px" }, `Showing the first 200 rows. Open in the builder to export all of them.`));
  }
  if (a.related && a.related.length) card.append(h("p", { class: "muted", style: "margin-top:14px;font-size:13px;font-weight:600" }, "Also in your documents"), ...a.related.map(quote));
  if (a.notice) card.append(h("p", { class: "notice" }, a.notice.text + " ", h("button", { class: "link", onclick: () => { S.current = a.notice.dataset; show("data"); } }, "Review now")));
  if (a.suggestions && a.suggestions.length) card.append(h("div", { class: "suggest" }, a.suggestions.map((s) => h("button", { onclick: () => ask(s) }, s))));
  const foot = h("div", { class: "foot row" });
  if (a.confidence) foot.append(h("span", { class: "pill " + a.confidence, title: "High: every word in your question was matched. Medium or low: some words were not used." }, a.confidence + " confidence"));
  foot.append(h("span", { class: "grow" }));
  if (a.builder) foot.append(h("button", { class: "secondary small", onclick: () => openInBuilder(a.builder) }, "Open in builder"));
  if (a.ml) foot.append(h("button", { class: "secondary small", onclick: () => openPrediction(a.ml) }, "Open in Predictions"));
  if (a.ml_id) foot.append(h("button", { class: "secondary small", onclick: () => show("predict") }, "Back to the result"));
  card.append(foot);
  if (a.how) {
    const hw = a.how;
    const teach = (w) => h("button", { class: "link", onclick: () => openWords(w) }, w);
    card.append(h("details", { class: "how" }, h("summary", {}, "How I got this"), h("div", { class: "box" },
      hw.matched && hw.matched.length ? [h("h5", {}, "Words I matched"), h("ul", {}, hw.matched.map((m) => h("li", {}, h("strong", {}, `“${m.words}”`), " → ", m.meaning)))] : null,
      hw.ignored && hw.ignored.length ? [h("h5", {}, "Words I did not use"), h("p", {}, hw.ignored.flatMap((w, i) => [i ? ", " : "", teach(w)]), h("span", { class: "muted" }, " — select a word to teach me what it means"))] : null,
      h("h5", {}, "Steps"), h("ol", {}, hw.steps.map((s) => h("li", {}, s))),
      hw.source ? [h("h5", {}, "Source"), h("p", {}, hw.source)] : null,
      hw.sql ? h("details", { style: "margin-top:12px" }, h("summary", {}, "Technical detail"), h("p", { class: "muted" }, "The exact query that was run on your data. You never need to read this; it is here so an analyst can verify the answer."), h("code", {}, hw.sql)) : null)));
  }
  return card;
}

// ---------------------------------------------------------------- Tables & charts
function resetBuild(dataset) { S.build = { dataset: dataset || null, rows: [], split: null, values: [], filters: [], chart: "auto", limit: null }; }
function openInBuilder(spec) {
  S.build = { dataset: spec.dataset, rows: (spec.rows || []).map((r) => ({ ...r })), split: spec.split ? { ...spec.split } : null,
              values: (spec.values || []).map((v) => ({ ...v })), filters: (spec.filters || []).map((f) => ({ ...f })),
              chart: "auto", limit: spec.limit || null, sort: spec.sort || null };
  show("build");
}
function addField(name, shelf) {
  const b = S.build, ds = datasetById(b.dataset), f = fieldOf(ds, name);
  if (!shelf) shelf = f.role === "measure" ? "values" : !b.rows.length ? "rows" : !b.split ? "split" : "rows";
  if (shelf === "rows" && !b.rows.some((r) => r.field === name)) { if (b.rows.length >= 2) b.rows.pop(); b.rows.push({ field: name }); }
  if (shelf === "split") b.split = { field: name };
  if (shelf === "values" && b.values.length < 3) b.values.push({ field: name, agg: f.type === "number" && f.role === "measure" ? (/price|rate|score|%|percent|tenure|discount|cost/i.test(name) ? "avg" : "sum") : "distinct" });
  if (shelf === "filters" && !b.filters.some((x) => x.field === name)) {
    b.filters.push(f.type === "number" ? { field: name, op: ">=", value: f.min ?? 0 } : f.type === "date" ? { field: name, op: "between", value: [f.min, f.max] } : { field: name, op: "is", value: [] });
  }
  renderBuild();
}
let buildTimer;
function renderBuild() {
  const root = $("view-build"), b = S.build, ds = datasetById(b.dataset);
  if (!ds) { root.replaceChildren(h("h2", {}, "Tables & charts"), h("div", { class: "card placeholder", style: "margin-top:20px" }, h("b", {}, "No tables to build from"), "Add an Excel or CSV file to build tables and charts.")); return; }
  const fields = h("aside", { class: "card fields" },
    h("select", { "aria-label": "Table to build from", onchange: (e) => { resetBuild(e.target.value); renderBuild(); } },
      S.state.datasets.map((d) => h("option", { value: d.id, selected: d.id === b.dataset }, d.name))),
    ds.columns.map((c) => h("div", { class: "chip", draggable: "true", tabindex: "0", role: "button", title: "Drag onto a box, or click to add",
      ondragstart: (e) => { e.dataTransfer.setData("text/plain", c.name); e.dataTransfer.effectAllowed = "copy"; },
      onclick: () => addField(c.name), onkeydown: (e) => { if (e.key === "Enter") addField(c.name); } },
      c.name, h("span", { class: "t" }, c.role === "measure" ? "Number" : TYPE_WORD[c.type]))));
  const x = (fn) => h("button", { class: "x", "aria-label": "Remove", onclick: () => { fn(); renderBuild(); } }, "×");
  const sel = (value, options, onchange, label) => h("select", { "aria-label": label, onchange: (e) => { onchange(e.target.value); renderBuild(); } },
    options.map(([v, w]) => h("option", { value: v, selected: String(v) === String(value) }, w)));
  const rowChip = (r, remove) => {
    const f = fieldOf(ds, r.field);
    return h("span", { class: "chip" }, r.field,
      f.type === "date" ? sel(r.grain || "", [["", "Automatic"], ["year", "By year"], ["quarter", "By quarter"], ["month", "By month"], ["day", "By day"], ["month_of_year", "By month of year"]], (v) => (r.grain = v || undefined), "Date grouping") : null, x(remove));
  };
  const filterChip = (f, i) => {
    const col = fieldOf(ds, f.field);
    const chip = h("span", { class: "chip", style: "align-items:flex-start;flex-wrap:wrap" }, f.field);
    if (col.type === "number") {
      chip.append(sel(f.op, [[">=", "at least"], ["<=", "at most"], [">", "more than"], ["<", "less than"]], (v) => (f.op = v), "Condition"),
        h("input", { type: "number", value: f.value, "aria-label": "Value", onchange: (e) => { f.value = Number(e.target.value); runBuild(); } }));
    } else if (col.type === "date") {
      chip.append(h("input", { type: "date", value: f.value[0], "aria-label": "From", style: "width:auto", onchange: (e) => { f.value[0] = e.target.value; runBuild(); } }), "to",
        h("input", { type: "date", value: f.value[1], "aria-label": "To", style: "width:auto", onchange: (e) => { f.value[1] = e.target.value; runBuild(); } }));
    } else {
      const picked = h("span", { class: "muted", style: "font-weight:500" }, f.value.length ? "is " + f.value.join(", ") : "choose values");
      const list = h("div", { class: "filter-values" }, "Loading…");
      const det = h("details", { open: !f.value.length }, h("summary", {}, picked), list);
      call("field_values", { dataset: ds.id, field: f.field }).then((vals) => list.replaceChildren(...vals.map((v) => h("label", {},
        h("input", { type: "checkbox", checked: f.value.includes(v), onchange: (e) => {
          f.value = e.target.checked ? [...f.value, v] : f.value.filter((y) => y !== v);
          picked.textContent = f.value.length ? "is " + f.value.join(", ") : "choose values"; runBuild();
        } }), " " + v))));
      chip.append(det);
    }
    chip.append(x(() => b.filters.splice(i, 1)));
    return chip;
  };
  const shelf = (key, title, hint, kids) => h("div", { class: "shelf", "data-shelf": key,
    ondragover: (e) => { e.preventDefault(); e.currentTarget.classList.add("over"); },
    ondragleave: (e) => e.currentTarget.classList.remove("over"),
    ondrop: (e) => { e.preventDefault(); e.currentTarget.classList.remove("over"); const n = e.dataTransfer.getData("text/plain"); if (n && fieldOf(ds, n)) addField(n, key); } },
    h("h4", {}, title, " ", h("span", {}, hint)), kids.length ? kids : h("div", { class: "hint" }, "Drop a field here"));
  const shelves = h("div", { class: "shelves" },
    shelf("rows", "Group by", "one line or bar for each", b.rows.map((r, i) => rowChip(r, () => b.rows.splice(i, 1)))),
    shelf("values", "Numbers to show", "what to add up or average", b.values.map((v, i) => h("span", { class: "chip" },
      sel(v.agg, Object.entries(AGG_WORD).filter(([k]) => fieldOf(ds, v.field).type === "number" || ["count", "distinct"].includes(k)), (a) => (v.agg = a), "How to combine"), v.field, x(() => b.values.splice(i, 1))))),
    shelf("split", "Split by", "optional: one colour for each", b.split ? [rowChip(b.split, () => (b.split = null))] : []),
    shelf("filters", "Only include", "optional: narrow the rows", b.filters.map(filterChip)));
  const result = h("div", { class: "card result", id: "buildResult" });
  root.replaceChildren(
    h("div", { class: "row" }, h("div", { class: "grow" }, h("h2", { class: "page-title" }, "Tables & charts"),
      h("p", { class: "sub" }, "Drag fields into the boxes. The table and chart update as you go.")),
      (b.rows.length || b.values.length || b.filters.length) ? h("button", { class: "ghost", onclick: () => { resetBuild(b.dataset); renderBuild(); } }, "Clear") : null),
    h("div", { class: "build-grid" }, fields, h("div", {}, shelves, result)));
  runBuild();
}
function buildSpec() {
  const b = S.build;
  return { dataset: b.dataset, rows: b.rows, split: b.split, values: b.values, filters: b.filters.filter((f) => !(f.op === "is" && !f.value.length)),
           chart: b.chart === "auto" ? null : b.chart, limit: b.limit, sort: b.sort || null };
}
function runBuild() {
  clearTimeout(buildTimer);
  buildTimer = setTimeout(async () => {
    const box = $("buildResult"), b = S.build;
    if (!box) return;
    if (!b.rows.length && !b.values.length) {
      box.replaceChildren(h("div", { class: "placeholder" }, h("b", {}, "Start by dragging a field"), "Try a category into “Group by” and a number into “Numbers to show”."));
      return;
    }
    let r;
    try { r = await call("build", { spec: buildSpec() }); } catch (err) { box.replaceChildren(h("div", { class: "placeholder" }, h("b", {}, "That combination did not work"), err.message)); return; }
    const seg = (options, value, set) => h("div", { class: "seg" }, options.map(([v, w]) => h("button", { "aria-pressed": String(v === value), onclick: () => { set(v); runBuild(); } }, w)));
    const canvas = h("canvas", { role: "img", "aria-label": "Chart of the table below" });
    const dateFirst = b.rows[0] && fieldOf(datasetById(b.dataset), b.rows[0].field).type === "date";
    const measure = (b.values.find((v) => v.field) || {}).field;
    const name = r.dataset_name + " - " + (r.columns.slice(-1)[0] || "table");
    box.replaceChildren(
      h("div", { class: "bar row" },
        r.chart ? seg([["auto", "Automatic"], ["bar", "Bars"], ["line", "Line"], ...(b.split || b.values.length > 1 ? [["stacked", "Stacked"]] : [])], b.chart, (v) => (b.chart = v)) : null,
        b.rows.length ? h("select", { "aria-label": "How many groups to show", onchange: (e) => { b.limit = Number(e.target.value) || null; runBuild(); } },
          [["", "Show all groups"], [5, "Top 5"], [10, "Top 10"], [20, "Top 20"]].map(([v, w]) => h("option", { value: v, selected: String(b.limit || "") === String(v) }, w))) : null,
        h("span", { class: "grow muted", style: "font-size:13px" }, `${fmtNum(r.rows_used)} of ${fmtNum(r.rows_total)} rows used`),
        h("button", { class: "secondary small", onclick: () => askAboutTable() }, "Ask about this"),
        dateFirst ? h("button", { class: "secondary small", onclick: () => runPrediction("forecast", { dataset: b.dataset, date: b.rows[0].field, value: measure, agg: (b.values[0] || {}).agg, filters: buildSpec().filters }) }, "Forecast this")
          : measure ? h("button", { class: "secondary small", onclick: () => runPrediction("drivers", { dataset: b.dataset, target: measure }) }, `What influences ${measure}?`) : null),
      r.chart ? h("div", { class: "pad" }, h("div", { class: "chart-box" }, canvas)) : null,
      h("div", { class: "pad", style: "padding-top:0" }, renderTable(r.columns, r.rows, r.types),
        h("div", { class: "row", style: "margin-top:12px" },
          h("button", { class: "primary small", onclick: () => exportTable("xlsx") }, "Download table (Excel)"),
          h("button", { class: "secondary small", onclick: () => exportTable("csv") }, "Download table (CSV)"),
          r.chart ? h("button", { class: "secondary small", onclick: () => downloadChart(canvas, name) }, "Download chart (PNG)") : null),
        h("details", { class: "how" }, h("summary", {}, "How this was made"), h("div", { class: "box" }, h("ol", {}, r.steps.map((s) => h("li", {}, s))),
          h("details", { style: "margin-top:12px" }, h("summary", {}, "Technical detail"), h("code", {}, r.sql))))));
    if (r.chart) drawChart(canvas, { ...r.chart, type: b.chart === "auto" ? r.chart.type : b.chart });
  }, 60);
}
async function exportTable(kind) {
  const x = await call("export", { spec: buildSpec(), kind });
  const bytes = Uint8Array.from(atob(x.base64), (c) => c.charCodeAt(0));
  download(x.filename, new Blob([bytes]));
}
async function askAboutTable() {
  const spec = buildSpec();
  show("ask");
  addMessage(h("div", {}, "Tell me about the table I just built"), "you");
  const wait = addMessage(h("div", { class: "card answer muted" }, h("span", { class: "spinner" }), "Reading the table…"), "bot");
  wait.replaceChildren(renderAnswer(await call("ask_about_table", { spec })));
}

// ---------------------------------------------------------------- Predictions (machine learning)
const KINDS = {
  forecast: ["What is likely to happen next?", "Forecast a number into the coming months."],
  drivers: ["What influences a result?", "Find which fields matter most, and try a prediction."],
  segments: ["Are there natural groups?", "Find rows that behave alike."],
  unusual: ["What looks unusual?", "Spot records that do not fit the pattern."],
};
function openPrediction(result) { S.predict.kind = result.kind; S.predict.dataset = result.dataset; S.predict.result = result; show("predict"); }
async function runPrediction(kind, spec) {
  S.predict.kind = kind; S.predict.dataset = spec.dataset; S.predict.result = null; S.predict.preset = spec;
  show("predict");
  await doRun(spec);
}
async function doRun(spec) {
  const out = $("predictResult");
  out.replaceChildren(h("div", { class: "card pad muted" }, h("span", { class: "spinner" }), "Working it out. The first run takes a little longer while the machine learning tools load."));
  try { S.predict.result = await call("ml_run", { kind: S.predict.kind, spec }); }
  catch (err) { S.predict.result = { error: "Something went wrong: " + err.message }; }
  drawPrediction();
}
async function renderPredict() {
  const root = $("view-predict"), p = S.predict, ds = datasetById(p.dataset);
  if (!ds) { root.replaceChildren(h("h2", {}, "Predictions"), h("div", { class: "card placeholder", style: "margin-top:20px" }, h("b", {}, "No tables to learn from"), "Add an Excel or CSV file to run predictions.")); return; }
  const form = h("div", { class: "card pad", style: "margin-top:14px" }, h("span", { class: "spinner" }));
  root.replaceChildren(
    h("div", { class: "row" }, h("div", { class: "grow" }, h("h2", { class: "page-title" }, "Predictions"),
      h("p", { class: "sub" }, "Machine learning, explained in plain English. Pick a question; every result says how far to trust it.")),
      h("label", { class: "muted" }, "Using ", h("select", { "aria-label": "Table to use", onchange: (e) => { p.dataset = e.target.value; p.result = null; p.preset = null; renderPredict(); } },
        S.state.datasets.map((d) => h("option", { value: d.id, selected: d.id === p.dataset }, d.name))))),
    h("div", { class: "choices" }, Object.entries(KINDS).map(([k, [title, sub]]) =>
      h("button", { class: "choice", "aria-pressed": String(k === p.kind), onclick: () => { p.kind = k; p.result = null; p.preset = null; renderPredict(); } }, h("b", {}, title), h("span", {}, sub)))),
    form, h("div", { id: "predictResult", style: "margin-top:16px" }));
  const o = await call("ml_options", { dataset: ds.id });
  if (S.view !== "predict" || p.dataset !== ds.id) return;
  const pre = p.preset || (p.result && p.result.spec) || {};
  const pick = (opts, value, label) => h("select", { "aria-label": label }, opts.map((v) => Array.isArray(v) ? h("option", { value: v[0], selected: String(v[0]) === String(value) }, v[1]) : h("option", { value: v, selected: v === value }, v)));
  let run, sentence;
  if (p.kind === "forecast") {
    if (!o.dates.length) sentence = h("p", {}, `“${ds.name}” has no date field, so there is nothing to forecast over time. Choose another table above.`);
    else {
      const agg = pick([["sum", "the total"], ["avg", "the average"], ["count", "the number of rows"]], pre.value === null && pre.agg !== "sum" ? "count" : pre.agg || (o.measures.length ? "sum" : "count"), "What to forecast");
      const val = pick(o.measures, pre.value || o.default_measure, "Number field");
      const date = pick(o.dates, pre.date || o.dates[0], "Date field");
      const hz = pick([[3, "3"], [6, "6"], [12, "12"]], pre.horizon || 6, "How far ahead");
      const sync = () => (val.hidden = agg.value === "count" || !o.measures.length);
      agg.addEventListener("change", sync); sync();
      sentence = h("div", { class: "sentence" }, "Forecast", agg, val, "over", date, "for the next", hz, "periods");
      run = () => ({ dataset: ds.id, date: date.value, value: agg.value === "count" || !o.measures.length ? null : val.value, agg: agg.value === "count" ? "sum" : agg.value, horizon: Number(hz.value), filters: pre.filters || [] });
    }
  } else if (p.kind === "drivers") {
    if (!o.targets.length) sentence = h("p", {}, "This table has no field I can explain. Choose another table above.");
    else {
      const t = pick(o.targets, pre.target || o.default_target, "Result to explain");
      sentence = h("div", { class: "sentence" }, "Find what influences", t, "using the other fields in this table");
      run = () => ({ dataset: ds.id, target: t.value });
    }
  } else {
    sentence = h("div", { class: "sentence" }, p.kind === "segments" ? `Look for groups of similar rows in “${ds.name}”` : `Look for records in “${ds.name}” that do not fit the usual pattern`);
    run = () => ({ dataset: ds.id });
  }
  form.replaceChildren(h("div", { class: "row" }, h("div", { class: "grow" }, sentence), run ? h("button", { class: "primary", onclick: () => { p.preset = null; doRun(run()); } }, "Run") : null));
  drawPrediction();
}
function drawPrediction() {
  const out = $("predictResult"), r = S.predict.result;
  if (!out) return;
  if (!r) { out.replaceChildren(); return; }
  if (r.error) { out.replaceChildren(h("div", { class: "card pad" }, h("p", { class: "text" }, r.error))); return; }
  const card = h("div", { class: "card pad stack" });
  card.append(h("div", { class: "row" }, h("h3", { class: "grow muted", style: "font-weight:600" }, r.title),
    h("button", { class: "secondary small", onclick: () => askAboutPrediction(r) }, "Ask about this"),
    h("button", { class: "secondary small", onclick: () => downloadCsv(r.title, r.table.columns, r.table.rows) }, "Download table (CSV)")),
    h("p", { class: "headline" }, r.headline));
  if (r.reliability) card.append(h("div", { class: "trust" },
    h("div", {}, h("div", { class: "score" }, Math.round(r.reliability.score), h("small", {}, " / 100")), h("span", { class: "pill " + r.reliability.label }, r.reliability.label + " reliability")),
    h("p", {}, h("strong", {}, "How far to trust this. "), r.reliability.text)));
  let canvas;
  if (r.kind === "forecast") { canvas = h("canvas", { role: "img", "aria-label": r.title }); card.append(h("div", { class: "chart-box" }, canvas)); }
  if (r.bullets.length && r.kind !== "drivers") card.append(h("ul", { style: "margin:0;padding-left:20px" }, r.bullets.map((b) => h("li", {}, b))));
  if (r.kind === "drivers" && r.importance.length) {
    card.append(h("h3", {}, "What matters most"),
      h("p", { class: "muted", style: "margin-top:2px" }, "Each bar is that field's share of the model's predictive power. The shares add up to 100%."),
      h("div", { class: "imp" }, r.importance.flatMap((i) => [h("div", {}, i.name), h("div", { class: "track" }, h("i", { style: `width:${i.share}%` })), h("div", { class: "pct" }, Math.round(i.share) + "%"), h("div", {}), h("div", { class: "why" }, i.effect)])));
    const verdict = h("div", {}, h("p", { class: "muted" }, "Change a value to see the prediction."));
    const inputs = {};
    const update = async () => {
      const v = await call("ml_predict", { result: r.id, inputs });
      verdict.replaceChildren(h("p", { class: "verdict" }, v.text), h("p", { class: "muted" }, v.detail));
    };
    card.append(h("h3", {}, "Try a prediction"), h("div", { class: "whatif" }, r.form.map((f) => {
      inputs[f.name] = f.default;
      const ctl = f.kind === "number" ? h("input", { type: "number", value: f.default, min: f.min, max: f.max, step: "any" }) : h("select", {}, f.options.map((o) => h("option", { selected: o === f.default }, o)));
      ctl.addEventListener("change", () => { inputs[f.name] = ctl.value; update(); });
      return h("label", {}, f.name, ctl);
    })), verdict);
    update();
  }
  if (r.kind === "forecast") card.append(h("details", {}, h("summary", {}, "How the methods compared"),
    renderTable(["Method", "Accuracy in the test (%)", ""], r.methods.map((m) => [m.name, m.accuracy, m.chosen ? "Chosen" : ""]), ["text", "number", "text"]),
    h("p", { class: "muted" }, "The test: hide the most recent periods, forecast them, and compare with what really happened."),
    renderTable(["Period", "What really happened", "What the method predicted"], r.backtest.map((b) => [b.label, b.actual, b.predicted]), ["text", "number", "number"])));
  card.append(h("h3", {}, r.kind === "forecast" ? "The forecast in numbers" : r.kind === "drivers" ? "Summary table" : r.kind === "segments" ? "The groups" : "The records"),
    renderTable(r.table.columns, r.table.rows, null, { wrap: r.kind === "unusual" ? 1 : r.kind === "drivers" ? 2 : -1 }),
    h("details", { class: "how" }, h("summary", {}, "How I got this"), h("div", { class: "box" }, h("ol", {}, r.steps.map((s) => h("li", {}, s))))));
  out.replaceChildren(card);
  if (canvas) drawForecast(canvas, r);
}
async function askAboutPrediction(r) {
  S.context = { kind: "ml", id: r.id, title: r.title };
  show("ask");
  addMessage(h("div", {}, "Explain this result: " + r.title), "you");
  const wait = addMessage(h("div", { class: "card answer muted" }, h("span", { class: "spinner" }), "Reading the result…"), "bot");
  wait.replaceChildren(renderAnswer(await call("ask_about_ml", { result: r.id })));
}

// ---------------------------------------------------------------- The story: choose a subject, then the cards
async function renderPick() {
  const root = $("view-pick");
  if (!S.pick) {
    root.replaceChildren(h("p", { class: "muted" }, h("span", { class: "spinner" }), "Reading your data…"));
    S.pick = await call("story_options");
  }
  const { options } = S.pick;
  if (S.view !== "pick") return;
  const choose = (o) => { S.flow = false; S.story = newStory(o); show("story"); };
  const wrap = h("div", { class: "scards arrive" });
  wrap.append(...options.map((o, i) => {
    const key = "s" + i, ds = datasetById(o.dataset);
    const card = cardShell(key, i + 1, o.label, o.detail + (ds ? `, ${plural(ds.rows, "row")}` : ""), "See the story of " + o.label, () => choose(o), h("div", { class: "sbody" }));
    card.classList.add("go-card");
    return card;
  }));
  root.replaceChildren(h("div", { class: "flow arrive" },
    stepper(4),
    h("h1", { class: "ask-big" }, "What do you want to understand?"),
    h("p", { class: "frame" }, options.length ? "Pick one. You can change it at any time." : "I did not find a table with numbers to build a story from. Your documents are still searchable under Explore further.")),
    options.length ? wrap : null);
}

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const yearStart = () => { try { return Number(localStorage.getItem("gist.yearStart")) || 1; } catch { return 1; } };
const newStory = (o) => ({ spec: { dataset: o.dataset, value: o.value, fiscal_start: yearStart() }, open: null, fresh: true });

async function renderStory() {
  const root = $("view-story");
  const fresh = S.story.fresh || !root.children.length;
  const STORY_WAIT = 1800;                                        // a little quicker than reading or tidying
  if (fresh) { root.replaceChildren(waitScreen(["Reading the numbers…", "Finding what changed…", "Preparing your story…"], STORY_WAIT)); S.story.arrived = false; }
  S.story.fresh = false;
  let st;
  try { st = await atLeast(fresh ? STORY_WAIT : 0, call("story_build", { spec: S.story.spec })); } catch (err) { st = { error: "Something went wrong: " + err.message }; }
  if (S.view !== "story") return;
  if (st.error) { root.replaceChildren(h("p", { class: "frame" }, st.error), h("button", { class: "secondary", onclick: () => show("pick") }, "Choose something else")); return; }
  S.story.data = st;
  const spec = S.story.spec;
  const retell = (change) => { Object.assign(spec, change); renderStory(); };
  const options = (S.pick || {}).options || [];
  const listed = options.some((o) => o.dataset === spec.dataset && o.value === st.value);
  const subject = h("select", { "aria-label": "What the story is about", onchange: (e) => { if (e.target.value === "") return; S.story = newStory(options[Number(e.target.value)]); renderStory(); } },
    listed ? null : h("option", { value: "", selected: true }, st.label),
    options.map((o, i) => h("option", { value: i, selected: o.dataset === spec.dataset && o.value === st.value }, o.label)));
  const period = st.periods.length ? h("select", { "aria-label": "Period", onchange: (e) => retell({ period: e.target.value }) },
    st.periods.map((p) => h("option", { value: p.key, selected: p.key === st.period }, p.label))) : null;
  const current = st.filters[0];
  const filter = st.filter_fields.length ? h("select", { "aria-label": "Narrow the story", onchange: (e) => {
      const [f, v] = e.target.value ? JSON.parse(e.target.value) : [];
      retell({ filters: f ? [{ field: f, op: "is", value: [v] }] : [] });
    } },
    h("option", { value: "" }, "everything"),
    st.filter_fields.map((f) => h("optgroup", { label: f.field }, f.values.map((v) =>
      h("option", { value: JSON.stringify([f.field, v]), selected: !!current && current.field === f.field && current.value[0] === v }, v))))) : null;
  const how = st.cards.find((c) => c.key === "how");
  const caution = how && how.actions.find((a) => a.link);
  if (!st.cards.some((c) => c.key === S.story.open)) S.story.open = null;
  const last = lastBriefing(st);
  const cards = st.cards.map((c, i) => storyCard(c, i + 1, st, retell, last));
  const yearSel = st.periods.length ? h("label", { class: "yearstart" }, "Business year starts in ",
    h("select", { onchange: (e) => { try { localStorage.setItem("gist.yearStart", e.target.value); } catch {} retell({ fiscal_start: Number(e.target.value) }); } },
      MONTHS.map((m, i) => h("option", { value: i + 1, selected: i + 1 === st.fiscal_start }, m)))) : null;
  root.replaceChildren(...[
    h("div", { class: "backrow" }, h("button", { class: "back", title: "Back to: What do you want to understand?", onclick: () => show("pick") }, h("span", { "aria-hidden": "true" }, "←"), " Back")),
    h("p", { class: "frame controls" }, h("span", { class: "grp" }, "A look at ", options.length > 1 || !listed ? subject : h("strong", {}, st.label)),
      period ? [" ", h("span", { class: "grp" }, "in ", period)] : null, filter ? [" ", h("span", { class: "grp" }, "for ", filter)] : null),
    h("div", { class: "print-title" }, h("h1", {}, st.title), h("p", {}, `Prepared ${new Date().toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" })} from ${st.source}`)),
    last ? h("p", { class: "since-top" }, `Compared with your last briefing on ${fmtDay(last.date)} (${last.period}). `,
      h("button", { class: "link", onclick: () => { forgetBriefing(); renderStory(); } }, "Forget it")) : null,
    caution ? h("p", { class: "caution" }, caution.why + " ", h("button", { class: "link", onclick: () => show("data") }, "Review now")) : null,
    h("div", { class: "scards" + (S.story.arrived ? "" : " arrive") }, cards),
    h("div", { class: "story-foot" },
      h("button", { class: "primary big", onclick: () => openShare(st) }, "Share the briefing"),
      S.explore ? yearSel : null),
    h("details", { class: "recon" }, h("summary", {}, st.reconcile.line),
      renderTable(st.reconcile.columns, st.reconcile.steps.map((r) => [r[0], r[1], r[2] === null || r[2] === undefined ? null : Math.round(r[2] * 100) / 100]), ["text", "number", "number"], { dash: true }))].filter(Boolean));
  S.story.arrived = true;
  openCard(S.story.open, false);
}

// One card shell, used by the story and by the empty cards on the first page.
function cardShell(key, n, word, sentence, title, onToggle, body) {
  return h("article", { class: "scard", "data-key": key, style: `--i:${n - 1}` },
    aura(),
    h("button", { class: "shead", "aria-expanded": "false", title, onclick: onToggle },
      h("span", { class: "n" }, n), h("span", { class: "t" }, h("span", { class: "q" }, word), h("span", { class: "s" }, sentence)), h("span", { class: "tog", "aria-hidden": "true" })),
    h("div", { class: "swrap" }, h("div", { class: "sclip" }, body)));
}
function toggleCards(wrap, key, byHand) {
  if (!wrap) return null;
  const plan = byHand && key ? scrollPlan(wrap, key) : null;     // measured before anything moves
  wrap.dataset.open = key || "";
  wrap.classList.toggle("has-open", !!key);
  let opened = null;
  wrap.querySelectorAll(":scope > .scard").forEach((el) => {
    const on = el.dataset.key === key;
    el.classList.toggle("open", on);
    el.querySelector(".shead").setAttribute("aria-expanded", String(on));
    el.querySelector(".sclip").inert = !on;
    if (on) opened = el;
  });
  if (plan) glideTo(plan);
  return opened;
}
// Where the opened card's heading will sit once every card has finished moving: measured on an invisible
// copy of the cards in their final state, so the scroll can be planned once and never corrected mid-way.
function scrollPlan(wrap, key) {
  const ghost = wrap.cloneNode(true);
  ghost.classList.remove("arrive");
  ghost.classList.add("plan-copy", "has-open");
  ghost.style.width = wrap.getBoundingClientRect().width + "px";
  ghost.querySelectorAll(":scope > .scard").forEach((el) => el.classList.toggle("open", el.dataset.key === key));
  wrap.after(ghost);                                             // same place in the page, so the same styles apply
  const realW = wrap.querySelector(":scope > .scard").getBoundingClientRect().width;
  const ghostW = ghost.querySelector(":scope > .scard").getBoundingClientRect().width;
  if (Math.abs(realW - ghostW) > 0.5) ghost.style.width = parseFloat(ghost.style.width) + realW - ghostW + "px";   // cards exactly as wide as the real ones
  const card = ghost.querySelector(`:scope > .scard[data-key="${key}"]`);
  const offset = card.getBoundingClientRect().top - ghost.getBoundingClientRect().top;
  ghost.remove();
  const nowTop = wrap.getBoundingClientRect().top + offset;      // where the heading will be on screen if the page does not scroll
  const hi = 84, lo = Math.max(hi + 40, window.innerHeight * 0.42);
  if (nowTop >= hi && nowTop <= lo) return null;                  // already comfortable: no scroll at all
  const target = nowTop < hi ? hi : Math.max(hi + 10, window.innerHeight * 0.16);
  return { by: nowTop - target };
}
let followStop = null;
function glideTo(plan) {
  if (followStop) followStop();
  const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const y0 = window.scrollY, max = document.documentElement.scrollHeight - window.innerHeight + Math.max(0, plan.by);
  const y1 = Math.max(0, Math.min(y0 + plan.by, max)), D = calm ? 0 : 1200, start = performance.now();
  let live = true;
  const stop = () => { live = false; ["wheel", "touchstart", "keydown"].forEach((t) => window.removeEventListener(t, stop)); };
  followStop = stop;
  ["wheel", "touchstart", "keydown"].forEach((t) => window.addEventListener(t, stop, { passive: true }));
  const ease = (t) => -(Math.cos(Math.PI * t) - 1) / 2;
  const step = (now) => {
    if (!live) return;
    const t = D ? Math.min(1, (now - start) / D) : 1;
    window.scrollTo(0, y0 + (y1 - y0) * ease(t));
    if (t < 1) requestAnimationFrame(step); else stop();
  };
  requestAnimationFrame(step);
}

function openCard(key, byHand) {
  S.story.open = key;
  closeRailMenus();
  const el = toggleCards(document.querySelector("#view-story .scards"), key, byHand);
  if (!el) return;
  const c = S.story.data.cards.find((x) => x.key === key), canvas = el.querySelector("canvas");
  // the chart is drawn once the card is well into its glide, so drawing never stutters the motion
  if (canvas) setTimeout(() => {
    if (!el.classList.contains("open")) return;
    c.forecast ? drawForecast(canvas, c.forecast, true, true) : drawChart(canvas, { ...c.chart, emphasis: key === "what" ? "last" : null, animate: true, clear: true });
  }, byHand ? 420 : 60);
}

// ---- the small round buttons on the edge of an open card: change the number, the grouping or the chart
const RAIL_ICON = {
  number: "M6 2.5 4.8 13.5M11.2 2.5 10 13.5M2.5 5.8h11M2 10.2h11",
  group: "M2.5 4h11M2.5 8h7.5M2.5 12h4",
  chart: "M3.5 13V8.5M8 13V3M12.5 13V6",
};
function closeRailMenus(except) {
  document.querySelectorAll(".edge-item.on").forEach((el) => {
    if (el === except) return;
    el.classList.remove("on");
    el.querySelector("button").setAttribute("aria-expanded", "false");
  });
}
document.addEventListener("click", (e) => { if (!e.target.closest(".edge-item")) closeRailMenus(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeRailMenus(); });

function railButton(icon, label, heading, items, pick) {
  const btn = h("button", { class: "edge-btn", title: label, "aria-label": label, "aria-haspopup": "true", "aria-expanded": "false" });
  btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><path d="${RAIL_ICON[icon]}"/></svg>`;
  const item = h("div", { class: "edge-item" }, btn,
    h("div", { class: "edge-menu", role: "group", "aria-label": label },
      h("p", {}, heading),
      items.map((it) => h("button", { "aria-pressed": String(!!it.on), onclick: () => { closeRailMenus(); if (!it.on) pick(it.key); } }, it.label))));
  btn.addEventListener("click", () => {
    const on = !item.classList.contains("on");
    closeRailMenus(item);
    item.classList.toggle("on", on);
    btn.setAttribute("aria-expanded", String(on));
  });
  return item;
}

// ---- the preparer's notes: the person writes the reasons, Gist keeps the facts (kept for this visit only)
S.notes = {};
const noteKey = (st, key) => `${st.label}|${key}`;
function noteBox(c, st) {
  const box = h("div", { class: "pnote-wrap" });
  const draw = (editing) => {
    const text = S.notes[noteKey(st, c.key)] || "";
    if (editing) {
      const ta = h("textarea", { class: "pnote-input", rows: 3, placeholder: "For example: the September dip follows the warehouse move." }, text);
      box.replaceChildren(h("label", { class: "pnote-k" }, "Preparer's note"), ta,
        h("div", { class: "row" }, h("button", { class: "primary", onclick: () => { const v = ta.value.trim(); if (v) S.notes[noteKey(st, c.key)] = v; else delete S.notes[noteKey(st, c.key)]; draw(false); } }, "Save note"),
          h("button", { class: "secondary", onclick: () => draw(false) }, "Cancel")));
      setTimeout(() => ta.focus(), 30);
    } else if (text) {
      box.replaceChildren(h("div", { class: "pnote" }, h("span", { class: "pnote-k" }, "Preparer's note"), h("p", {}, text),
        h("button", { class: "link", onclick: () => draw(true) }, "Edit note")));
    } else {
      box.replaceChildren(h("button", { class: "link add-note", onclick: () => draw(true) }, "+ Add a note"));
    }
  };
  draw(false);
  return box;
}

// ---- since your last briefing: only the headline figures of an exported briefing are kept, never the data
const BRIEF_KEY = "gist.lastBriefing";
const fmtDay = (iso) => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
function lastBriefing(st) {
  try { const b = JSON.parse(localStorage.getItem(BRIEF_KEY) || "null"); return b && b.label === st.label ? b : null; } catch { return null; }
}
function saveBriefing(st) {
  try { localStorage.setItem(BRIEF_KEY, JSON.stringify({ date: new Date().toISOString(), label: st.label, period: st.period_label,
    cards: Object.fromEntries(st.cards.map((c) => [c.key, (c.brief || {}).text || c.sentence])) })); } catch {}
}
function forgetBriefing() { try { localStorage.removeItem(BRIEF_KEY); } catch {} }

// ---- reading at a glance: arrows by meaning (for cost-like numbers a rise is red), bold key words, short tables
const ARROW = { up: "▲", down: "▼", flat: "▸" };
const arrow = (dir, mood) => (dir ? h("span", { class: `arr ${mood || "neutral"}`, "aria-hidden": "true" }, ARROW[dir]) : null);
function rich(text) {               // **bold** -> <strong>
  return String(text).split(/\*\*(.+?)\*\*/g).map((part, i) => (i % 2 ? h("strong", {}, part) : part));
}
function changeChip(c) {
  const words = c.dir === "up" ? "up" : c.dir === "down" ? "down" : "";
  return h("span", { class: `chip ${c.mood || "neutral"}`, title: c.mood === "good" ? "Good news" : c.mood === "bad" ? "Needs attention" : "" },
    h("span", { "aria-hidden": "true" }, ARROW[c.dir] || ""), h("span", { class: "sr" }, words + " "), c.chip);
}
function sentenceNodes(c) {
  if (!c.parts) return c.sentence;
  const out = [];
  c.parts.forEach((p, i) => {
    if (typeof p === "string") out.push((i && !/^[,.;:]/.test(p) ? " " : "") + p);
    else out.push(" ", changeChip(p));
  });
  const last = c.parts[c.parts.length - 1];
  if (typeof last !== "string" || !/[.!?]$/.test(last)) out.push(".");
  return out;
}
function heroFigure(x) {
  return h("div", { class: "hero-fig" }, h("span", { class: `big ${x.mood || ""}` }, x.dir && x.dir !== "flat" ? h("span", { class: "arr-big", "aria-hidden": "true" }, ARROW[x.dir]) : null, x.big),
    h("span", { class: "small" }, x.small));
}
function storyTable(t) {
  const m = t.meta || {}, pct = m.pct || [], pts = m.pts || [], abs = m.abs || [], upGood = m.up_good !== false;
  const isNum = t.columns.map((_, i) => t.rows.some((r) => typeof r[i] === "number"));
  const cell = (v, i) => {
    if (v === null || v === undefined || v === "") return h("td", { class: "blank" + (isNum[i] ? " num" : "") }, "–");
    if (pct.includes(i) || pts.includes(i) || abs.includes(i)) {
      const dir = v > 0 ? "up" : v < 0 ? "down" : "flat", mood = v === 0 ? "neutral" : (v > 0) === upGood ? "good" : "bad";
      const text = abs.includes(i) ? (v > 0 ? "+" : "") + fmtNum(v) : `${Math.abs(v).toFixed(Math.abs(v) < 10 ? 1 : 0)}${pts.includes(i) ? " pts" : "%"}`;
      return h("td", { class: `num chg ${mood}` }, h("span", { "aria-hidden": "true" }, ARROW[dir] + " "), text);
    }
    if (i === m.share) return h("td", { class: "num share" }, h("span", { class: "bar", style: `width:${Math.max(0, Math.min(100, v))}%` }), h("span", { class: "v" }, fmtNum(v) + "%"));
    return h("td", { class: isNum[i] ? "num" : "" }, fmtNum(v));
  };
  const LIMIT = 5;
  const body = h("tbody", {});
  const wrap = h("div", { class: "table-wrap story-table" }, h("table", {},
    h("thead", {}, h("tr", {}, t.columns.map((c, i) => h("th", { class: isNum[i] ? "num" : "" }, c)))), body));
  const draw = (all) => {
    body.replaceChildren(...(all ? t.rows : t.rows.slice(0, LIMIT)).map((r) => h("tr", {}, r.map(cell))));
    more.hidden = t.rows.length <= LIMIT;
    more.textContent = all ? "Show fewer" : `Show all ${fmtNum(t.rows.length)}`;
    more.onclick = () => draw(!all);
  };
  const more = h("button", { class: "link show-all" });
  draw(false);
  return h("div", { class: "story-table-box" }, wrap, more);
}

function storyCard(c, n, st, retell, last) {
  const spec = S.story.spec;
  const rail = [];
  if (c.key !== "how" && st.measures.length > 1) rail.push(railButton("number", "Change the number", "Number (every card follows)",
    st.measures.map((m, i) => ({ key: i, label: m.label, on: m.value === st.value })), (i) => retell({ value: st.measures[i].value })));
  if (c.dims && c.dims.length > 1) rail.push(railButton("group", c.key === "when" ? "Change the date used" : "Change the grouping", c.dim_word || "Grouped by",
    c.dims.slice(0, 8).map((d) => ({ key: d, label: d, on: d === c.dim })), (d) => retell({ [c.key === "when" ? "date" : c.key]: d })));
  if (c.chart_types && c.chart_types.length > 1) rail.push(railButton("chart", "Change the chart", "Chart",
    c.chart_types.map((t) => ({ key: t.key, label: t.label, on: t.key === c.chart_type })), (k) => retell({ charts: { ...(spec.charts || {}), [c.key]: k } })));
  const body = h("div", { class: "sbody" });
  if (rail.length) body.append(h("div", { class: "edge" }, rail));
  const then = last && last.cards[c.key], now = (c.brief || {}).text || c.sentence;
  if (then && then !== now) body.append(h("p", { class: "since" }, h("strong", {}, `Since your last briefing (${fmtDay(last.date)}): `), `then ${then.replace(/\.$/, "")}.`));
  if (c.hero) body.append(heroFigure(c.hero));
  if (c.bullets && c.bullets.length) body.append(h("ul", { class: "bullets" }, c.bullets.map((b) => h("li", { class: b.mood || "" }, arrow(b.dir, b.mood), h("span", {}, rich(b.t))))));
  body.append(noteBox(c, st));
  if (c.actions) body.append(h("ol", { class: "actions" }, c.actions.map((a) => h("li", {}, h("strong", {}, a.do), h("span", {}, a.why)))));
  if (c.note) body.append(h("p", { class: "fine" }, c.note));
  if (c.chart || c.forecast) body.append(h("div", { class: "chart-box", style: `height:${chartHeight(c.forecast ? { type: "forecast" } : c.chart)}px` }, h("canvas", { role: "img", "aria-label": c.forecast ? "Forecast (an estimate)" : c.sentence })));
  if (c.table) body.append(c.table.meta ? storyTable(c.table) : renderTable(c.table.columns, c.table.rows, null, { dash: true }));
  body.append(h("details", { class: "how" }, h("summary", {}, "How I got this"), h("div", { class: "box" }, h("ol", {}, c.steps.map((s) => h("li", {}, s))),
    c.sql ? h("details", { style: "margin-top:12px" }, h("summary", {}, "Technical detail"), h("p", { class: "muted" }, "The main query that was run on your data, for an analyst who wants to verify it."), h("code", {}, c.sql)) : null)));
  const card = cardShell(c.key, n, c.word, sentenceNodes(c), c.ask, () => openCard(S.story.open === c.key ? null : c.key, true), body);
  card.dataset.mood = c.mood || "neutral";
  return card;
}

// ---------------------------------------------------------------- The first page: the cards, empty until data is added
const PREVIEW = [
  ["what", "What", "What happened?", "Your headline number for the latest period, and how it compares with before."],
  ["who", "Who", "Who is behind it?", "The customers, segments or people that make up the total."],
  ["when", "When", "When did it happen?", "How the number has moved, month by month."],
  ["which", "Which", "Which ones matter most?", "The products, regions or categories that count the most."],
  ["why", "Why", "Why did it change?", "Where the change since the last period came from."],
  ["how", "How", "How should we respond?", "Suggested next steps, worked out from your data."],
];
(function renderPreview() {
  const wrap = $("previewCards");
  wrap.replaceChildren(...PREVIEW.map(([key, word, ask, about], i) => cardShell(key, i + 1, word + "?", ask, ask,
    () => toggleCards(wrap, wrap.dataset.open === key ? null : key, true),
    h("div", { class: "sbody" }, h("p", { class: "more" }, about + " Add your data to see it."),
      h("div", { class: "flow-actions" }, h("button", { class: "primary big", onclick: () => fileInput.click() }, "Add your data"))))));
})();
