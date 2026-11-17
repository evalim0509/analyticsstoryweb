/* Gist — sharing the briefing: PDF, PowerPoint, an email draft with the PDF attached, and a copy for email.
   Everything is made inside this browser tab. The PDF and slide makers (assets/vendor) load only when used.
   After a briefing is shared, only its headline figures are kept, for "since your last briefing". */
"use strict";

const SHARE_V = "2026-11-19.1";
const loaded = {};
function loadScript(src) {
  if (!loaded[src]) loaded[src] = new Promise((ok, fail) => {
    const s = document.createElement("script");
    s.src = src + "?v=" + SHARE_V; s.onload = ok; s.onerror = () => fail(new Error("Could not load " + src));
    document.head.append(s);
  });
  return loaded[src];
}

// Standard PDF fonts cover Western European text only; swap the few symbols they lack.
const pdfText = (t) => String(t ?? "").replace(/−/g, "-").replace(/→/g, "->").replace(/←/g, "<-").replace(/[  ]/g, " ");

function safeName(t) { return String(t).replace(/[\\/:*?"<>|]+/g, " ").replace(/\s+/g, " ").trim().slice(0, 80); }

// Every card's chart drawn once, off screen, as a picture.
async function chartImages(st) {
  const holder = h("div", { style: "position:fixed;left:-12000px;top:0;width:900px;background:#fff" });
  document.body.append(holder);
  const out = {};
  for (const c of st.cards) {
    if (!c.chart && !c.forecast) continue;
    const spec = c.forecast ? { type: "forecast" } : c.chart;
    const hgt = Math.min(chartHeight(spec), 520);
    const box = h("div", { style: `position:relative;width:900px;height:${hgt}px` }), canvas = h("canvas");
    box.append(canvas); holder.append(box);
    const chart = c.forecast ? drawForecast(canvas, c.forecast) : drawChart(canvas, { ...c.chart, emphasis: c.key === "what" ? "last" : null });
    box.style.height = hgt + "px"; chart.resize(); chart.update("none");
    out[c.key] = { url: canvas.toDataURL("image/jpeg", 0.86), w: canvas.width, h: canvas.height, kind: "JPEG" };
    chart.destroy();
  }
  holder.remove();
  return out;
}

// One plain description of the briefing, used by every format.
function briefing(st) {
  const prepared = new Date().toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });
  return {
    title: st.title, prepared: `Prepared ${prepared} from ${st.source}`, recon: st.reconcile ? st.reconcile.line : "",
    cards: st.cards.map((c, i) => ({
      n: i + 1, key: c.key, word: c.word, sentence: c.sentence, more: c.more || [], note: S.notes[noteKey(st, c.key)] || "",
      actions: c.actions || null, estimate: !!c.forecast, steps: c.steps || [],
      figures: c.table && !c.actions ? { columns: c.table.columns, rows: c.table.rows.slice(0, 6) } : null })),
  };
}

// ---------------------------------------------------------------- PDF
async function makePdf(st) {
  await loadScript("assets/vendor/jspdf.umd.min.js");
  const B = briefing(st), imgs = await chartImages(st);
  const doc = new window.jspdf.jsPDF({ unit: "pt", format: "a4", compress: true });
  const W = doc.internal.pageSize.getWidth(), H = doc.internal.pageSize.getHeight(), M = 48, CW = W - 2 * M;
  let y = M;
  const room = (need) => { if (y + need > H - M) { doc.addPage(); y = M; } };
  const para = (text, size, style = "normal", color = [18, 22, 31], font = "helvetica", gap = 4) => {
    doc.setFont(font, style); doc.setFontSize(size); doc.setTextColor(...color);
    for (const line of doc.splitTextToSize(pdfText(text), CW)) { room(size * 1.3); doc.text(line, M, y + size); y += size * 1.3; }
    y += gap;
  };
  para(B.title, 20, "bold", [18, 22, 31], "times", 2);
  para(B.prepared, 9.5, "normal", [93, 101, 115]);
  if (B.recon) para(B.recon, 9, "normal", [93, 101, 115], "helvetica", 10);
  for (const c of B.cards) {
    room(90);
    doc.setDrawColor(220, 223, 230); doc.line(M, y, W - M, y); y += 14;
    para(`${c.n}  ${c.word}`, 14, "bold", [36, 64, 196], "times", 2);
    para(c.sentence, 12, "bold");
    if (c.more.length) para(c.more.join(" "), 10, "normal", [51, 58, 71]);
    if (c.note) {
      doc.setFont("helvetica", "normal"); doc.setFontSize(10);
      const lines = doc.splitTextToSize(pdfText(c.note), CW - 20);
      const bh = 22 + lines.length * 13; room(bh + 6);
      doc.setFillColor(246, 244, 236); doc.setDrawColor(212, 138, 0); doc.rect(M, y, CW, bh, "F"); doc.line(M, y, M, y + bh);
      doc.setFont("helvetica", "bold"); doc.setFontSize(8.5); doc.setTextColor(122, 84, 0); doc.text("PREPARER'S NOTE", M + 12, y + 14);
      doc.setFont("helvetica", "normal"); doc.setFontSize(10); doc.setTextColor(18, 22, 31);
      lines.forEach((l, k) => doc.text(l, M + 12, y + 28 + k * 13)); y += bh + 10;
    }
    if (c.actions) c.actions.forEach((a, k) => { para(`${k + 1}. ${a.do}`, 10.5, "bold", [18, 22, 31], "helvetica", 0); para(a.why, 9.5, "normal", [93, 101, 115]); });
    const img = imgs[c.key];
    if (img) {
      const iw = CW, ih = Math.min(260, iw * img.h / img.w); room(ih + 8);
      if (c.estimate) para("Forecast: an estimate, not a recorded figure.", 8.5, "italic", [93, 101, 115], "helvetica", 2);
      doc.addImage(img.url, img.kind, M, y, iw, ih, undefined, "FAST"); y += ih + 8;
    }
    if (c.figures) {
      const cols = c.figures.columns, cw = CW / cols.length;
      room(16 + 14 * c.figures.rows.length);
      doc.setFont("helvetica", "bold"); doc.setFontSize(8.5); doc.setTextColor(93, 101, 115);
      cols.forEach((t, j) => doc.text(pdfText(doc.splitTextToSize(String(t), cw - 6)[0]), M + j * cw, y + 9)); y += 14;
      doc.setFont("helvetica", "normal"); doc.setTextColor(18, 22, 31);
      for (const r of c.figures.rows) { r.forEach((v, j) => doc.text(pdfText(doc.splitTextToSize(v === null || v === undefined ? "-" : fmtNum(v), cw - 6)[0]), M + j * cw, y + 9)); y += 13; }
      y += 6;
    }
    y += 6;
  }
  const pages = doc.getNumberOfPages();
  for (let p = 1; p <= pages; p++) {
    doc.setPage(p); doc.setFont("helvetica", "normal"); doc.setFontSize(8); doc.setTextColor(140, 146, 158);
    doc.text(pdfText(`Gist briefing — worked out from the uploaded files only. Page ${p} of ${pages}`), M, H - 24);
  }
  return doc.output("blob");
}

// ---------------------------------------------------------------- PowerPoint
async function makeSlides(st) {
  await loadScript("assets/vendor/pptxgen.bundle.js");
  const B = briefing(st), imgs = await chartImages(st);
  const pptx = new window.PptxGenJS();
  pptx.layout = "LAYOUT_WIDE";       // 13.33 x 7.5 in
  const INK = "12161F", MUTED = "5D6573", ACCENT = "2440C4", FONT = "Calibri";
  let s = pptx.addSlide();
  s.addText(B.title, { x: 0.7, y: 2.2, w: 11.9, h: 1.2, fontFace: "Georgia", fontSize: 36, color: INK });
  s.addText(B.prepared, { x: 0.7, y: 3.4, w: 11.9, h: 0.5, fontFace: FONT, fontSize: 14, color: MUTED });
  if (B.recon) s.addText(B.recon, { x: 0.7, y: 4.1, w: 11.9, h: 1.2, fontFace: FONT, fontSize: 12, color: MUTED, valign: "top" });
  for (const c of B.cards) {
    s = pptx.addSlide();
    s.addText(`${c.n}  ${c.word}`, { x: 0.6, y: 0.35, w: 6, h: 0.45, fontFace: FONT, fontSize: 14, bold: true, color: ACCENT });
    s.addText(c.sentence, { x: 0.6, y: 0.8, w: 12.1, h: 1.1, fontFace: "Georgia", fontSize: 24, color: INK, valign: "top" });
    const img = imgs[c.key];
    const textX = img ? 8.3 : 0.6, textW = img ? 4.4 : 12.1;
    let ty = 2.1;
    if (img) {
      const w = 7.4, hh = Math.min(4.9, w * img.h / img.w);
      s.addImage({ data: img.url, x: 0.6, y: 2.1, w, h: hh });
      if (c.estimate) s.addText("Forecast: an estimate, not a recorded figure.", { x: 0.6, y: 2.1 + hh + 0.05, w, h: 0.3, fontFace: FONT, fontSize: 10, italic: true, color: MUTED });
    }
    if (c.actions) {
      s.addText(c.actions.map((a, k) => ({ text: `${k + 1}. ${a.do}`, options: { bold: true, breakLine: true, paraSpaceBefore: 6 } })), { x: textX, y: ty, w: textW, h: 4.6, fontFace: FONT, fontSize: 15, color: INK, valign: "top" });
    } else if (c.more.length) {
      s.addText(c.more.join(" "), { x: textX, y: ty, w: textW, h: c.note ? 3.1 : 4.8, fontFace: FONT, fontSize: 14, color: "333A47", valign: "top" });
    }
    if (c.note) {
      s.addShape(pptx.ShapeType.rect, { x: textX, y: 5.35, w: textW, h: 1.6, fill: { color: "F6F4EC" }, line: { color: "D48A00", width: 1 } });
      s.addText([{ text: "PREPARER'S NOTE", options: { bold: true, fontSize: 10, color: "7A5400", breakLine: true } }, { text: c.note, options: { fontSize: 12, color: INK } }],
        { x: textX + 0.1, y: 5.4, w: textW - 0.2, h: 1.5, fontFace: FONT, valign: "top" });
    }
    s.addNotes([c.note ? "Preparer's note: " + c.note : "", "How I got this:", ...c.steps.map((x, k) => `${k + 1}. ${x}`)].filter(Boolean).join("\n"));
  }
  return pptx.write({ outputType: "blob" });
}

// ---------------------------------------------------------------- email
const esc = (t) => String(t ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
function emailHtml(B) {
  const card = (c) => `<h3 style="margin:22px 0 4px;font:600 16px Georgia,serif;color:#2440c4">${c.n}. ${esc(c.word)}</h3>
<p style="margin:0 0 6px;font:600 15px/1.45 Arial,sans-serif;color:#12161f">${esc(c.sentence)}</p>
${c.more.length ? `<p style="margin:0 0 6px;font:14px/1.5 Arial,sans-serif;color:#333a47">${esc(c.more.join(" "))}</p>` : ""}
${c.actions ? `<ol style="margin:6px 0;padding-left:20px;font:14px/1.5 Arial,sans-serif;color:#12161f">${c.actions.map((a) => `<li><b>${esc(a.do)}</b> <span style="color:#5d6573">${esc(a.why)}</span></li>`).join("")}</ol>` : ""}
${c.note ? `<p style="margin:8px 0;padding:8px 12px;border-left:3px solid #d48a00;background:#f6f4ec;font:14px/1.5 Arial,sans-serif;color:#12161f"><b style="font-size:11px;color:#7a5400">PREPARER'S NOTE</b><br>${esc(c.note)}</p>` : ""}`;
  return `<div style="max-width:680px"><h2 style="margin:0;font:500 22px Georgia,serif;color:#12161f">${esc(B.title)}</h2>
<p style="margin:4px 0 2px;font:13px Arial,sans-serif;color:#5d6573">${esc(B.prepared)}</p>
${B.recon ? `<p style="margin:0 0 6px;font:12px Arial,sans-serif;color:#5d6573">${esc(B.recon)}</p>` : ""}
${B.cards.map(card).join("\n")}
<p style="margin:22px 0 0;font:12px Arial,sans-serif;color:#8c929e">Worked out by Gist from the uploaded files only.</p></div>`;
}
function emailText(B) {
  return [B.title, B.prepared, B.recon, ""].concat(B.cards.flatMap((c) => [
    `${c.n}. ${c.word.toUpperCase()}: ${c.sentence}`, c.more.join(" "),
    ...(c.actions ? c.actions.map((a, k) => `   ${k + 1}. ${a.do} ${a.why}`) : []),
    c.note ? `   Preparer's note: ${c.note}` : "", ""])).filter((l, i, a) => l !== "" || a[i - 1] !== "").join("\n");
}
const b64 = (bytes) => { let s = ""; for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000)); return btoa(s).replace(/.{76}/g, "$&\r\n"); };
const b64text = (t) => b64(new TextEncoder().encode(t));
async function makeEmail(st) {
  const B = briefing(st), pdf = new Uint8Array(await (await makePdf(st)).arrayBuffer());
  const mix = "gist-mix-" + Math.random().toString(36).slice(2), alt = "gist-alt-" + Math.random().toString(36).slice(2);
  const subject = "=?UTF-8?B?" + b64text("Briefing: " + B.title).replace(/\r\n/g, "") + "?=";
  const file = safeName("Gist briefing - " + B.title) + ".pdf";
  const eml = [
    "To: ", `Subject: ${subject}`, "X-Unsent: 1", "MIME-Version: 1.0", `Content-Type: multipart/mixed; boundary="${mix}"`, "",
    `--${mix}`, `Content-Type: multipart/alternative; boundary="${alt}"`, "",
    `--${alt}`, "Content-Type: text/plain; charset=UTF-8", "Content-Transfer-Encoding: base64", "", b64text(emailText(B)), "",
    `--${alt}`, "Content-Type: text/html; charset=UTF-8", "Content-Transfer-Encoding: base64", "", b64text(emailHtml(B)), "",
    `--${alt}--`, "",
    `--${mix}`, `Content-Type: application/pdf; name="${file}"`, "Content-Transfer-Encoding: base64", `Content-Disposition: attachment; filename="${file}"`, "", b64(pdf), "",
    `--${mix}--`, ""].join("\r\n");
  return new Blob([eml], { type: "message/rfc822" });
}
async function copyForEmail(st) {
  const B = briefing(st), html = emailHtml(B), text = emailText(B);
  try {
    await navigator.clipboard.write([new ClipboardItem({ "text/html": new Blob([html], { type: "text/html" }), "text/plain": new Blob([text], { type: "text/plain" }) })]);
  } catch {
    try { await navigator.clipboard.writeText(text); } catch {
      const t = h("textarea", { style: "position:fixed;opacity:0" }, text); document.body.append(t); t.select(); document.execCommand("copy"); t.remove();
    }
  }
}

// ---------------------------------------------------------------- the share sheet
function openShare(st) {
  const name = safeName("Gist briefing - " + st.title);
  const run = async (btn, work, after) => {
    const label = btn.querySelector("b").textContent;
    btn.disabled = true; btn.querySelector("b").textContent = "Preparing…";
    try { await work(); saveBriefing(st); after && after(); }
    catch (err) { toast("Sorry, that did not work: " + err.message); }
    finally { btn.disabled = false; btn.querySelector("b").textContent = label; }
  };
  const option = (title, text, work, after) => {
    const b = h("button", { class: "share-opt" }, h("b", {}, title), h("span", {}, text));
    b.addEventListener("click", () => run(b, work, after));
    return b;
  };
  openModal(h("div", { class: "sheet share-sheet" },
    h("header", {}, h("h2", {}, "Share the briefing"),
      h("p", { class: "sub" }, "Made on this computer from the story on screen, with your notes. Nothing is uploaded.")),
    h("div", { class: "body share-grid" },
      option("PDF file", "A tidy document with every card, its chart and key figures.", async () => download(name + ".pdf", await makePdf(st))),
      option("PowerPoint slides", "One slide per card; notes and workings in the speaker notes.", async () => download(name + ".pptx", await makeSlides(st))),
      option("Email draft", "Opens in Outlook or Mail with the briefing written out and the PDF attached.", async () => download(name + ".eml", await makeEmail(st))),
      option("Copy for email", "Copies the briefing, formatted, to paste into any email.", async () => copyForEmail(st), () => toast("Copied. Paste it into an email."))),
    h("footer", {}, h("button", { class: "link", onclick: () => { saveBriefing(st); closeModal(); setTimeout(() => window.print(), 50); } }, "Print instead"),
      h("span", { class: "grow" }), h("button", { class: "secondary", onclick: closeModal }, "Done"))));
}
