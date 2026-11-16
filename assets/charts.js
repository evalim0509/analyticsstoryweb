/* Chart drawing. One shared look: thin marks, quiet grid, colours in a fixed order,
   a legend whenever there is more than one series, hover to read exact values. */
const SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];
const INK = "#15211d", MUTED = "#5e6b66", GRID = "#e6e9e6";

Chart.defaults.font.family = '"Hanken Grotesk", system-ui, sans-serif';
Chart.defaults.font.size = 12.5;
Chart.defaults.color = MUTED;
Chart.defaults.animation = false;

const nf0 = new Intl.NumberFormat("en", { maximumFractionDigits: 0 });
const nf2 = new Intl.NumberFormat("en", { maximumFractionDigits: 2 });
function fmtNum(v) {
  if (v === null || v === undefined || v === "") return "";
  if (typeof v !== "number") return String(v);
  return Math.abs(v) >= 100 || Number.isInteger(v) ? nf0.format(v) : nf2.format(v);
}
const compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });

const whiteBackground = {
  id: "whiteBackground",
  beforeDraw(chart) {
    const { ctx, width, height } = chart;
    ctx.save(); ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, width, height); ctx.restore();
  },
};

function baseOptions(many, horizontal, xTitle, yTitle) {
  const value = { grid: { color: GRID }, border: { display: false }, beginAtZero: true,
                  ticks: { callback: (v) => compact.format(v) }, title: { display: !!yTitle, text: yTitle, color: MUTED } };
  const label = { grid: { display: false }, border: { color: GRID }, ticks: { maxRotation: 0, autoSkipPadding: 14 },
                  title: { display: !!xTitle, text: xTitle, color: MUTED } };
  return {
    responsive: true, maintainAspectRatio: false, indexAxis: horizontal ? "y" : "x",
    interaction: { mode: "index", intersect: false, axis: horizontal ? "y" : "x" },
    scales: horizontal ? { x: value, y: label } : { x: label, y: value },
    plugins: {
      legend: { display: many, position: "top", align: "start", labels: { boxWidth: 10, boxHeight: 10, useBorderRadius: true, borderRadius: 2, color: INK } },
      tooltip: { backgroundColor: INK, padding: 10, cornerRadius: 6, boxPadding: 4,
                 callbacks: { label: (c) => ` ${c.dataset.label}: ${fmtNum(c.parsed[horizontal ? "x" : "y"])}` } },
    },
  };
}

/* spec: {type, labels, series:[{name,data}], x_title, y_title}; type is bar | hbar | stacked | line */
const calm = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const GROW = { duration: 650, easing: "easeOutQuart" };

/* Share of the total: a ring with at most six slices, each slice's share written in the legend. */
function drawShare(canvas, spec) {
  const data = spec.series[0].data, total = data.reduce((a, b) => a + b, 0) || 1;
  const pct = (v) => Math.round((100 * v) / total) + "%";
  const narrow = canvas.parentElement.clientWidth < 520;
  canvas.parentElement.style.height = narrow ? "360px" : "300px";
  return new Chart(canvas, {
    type: "doughnut",
    data: { labels: spec.labels, datasets: [{ label: spec.series[0].name, data, borderColor: "#fff", borderWidth: 2,
      backgroundColor: spec.labels.map((l, i) => (l === "All others" ? "#c3c9d4" : SERIES[i])) }] },
    options: { responsive: true, maintainAspectRatio: false, cutout: "62%", animation: spec.animate && !calm() ? GROW : false,
      plugins: {
        legend: { position: narrow ? "bottom" : "right", labels: { boxWidth: 10, boxHeight: 10, useBorderRadius: true, borderRadius: 2, color: INK, padding: 14,
          generateLabels: (chart) => Chart.overrides.doughnut.plugins.legend.labels.generateLabels(chart).map((l) => ({ ...l, text: `${l.text}  ${pct(data[l.index])}` })) } },
        tooltip: { backgroundColor: INK, padding: 10, cornerRadius: 6, boxPadding: 4, callbacks: { label: (c) => ` ${c.label}: ${fmtNum(c.parsed)} (${pct(c.parsed)})` } },
      } },
    plugins: [whiteBackground],
  });
}

function drawChart(canvas, spec) {
  const old = Chart.getChart(canvas);
  if (old) old.destroy();
  if (spec.type === "share") return drawShare(canvas, spec);
  const series = spec.series.slice(0, 8);
  const many = series.length > 1;
  let type = spec.type || "bar";
  const longest = Math.max(0, ...spec.labels.map((l) => String(l).length));
  if (type === "bar" && !spec.time && (spec.labels.length > 9 || longest > 12) && spec.labels.length <= 40) type = "hbar";
  const horizontal = type === "hbar";
  const line = type === "line";
  const options = baseOptions(many, horizontal, horizontal ? spec.y_title : spec.x_title, horizontal ? spec.x_title : spec.y_title);
  if (type === "stacked") { options.scales.x.stacked = true; options.scales.y.stacked = true; }
  if (spec.animate && !calm()) options.animation = GROW;
  const datasets = series.map((s, i) => line
    ? { label: s.name, data: s.data, borderColor: SERIES[i], backgroundColor: SERIES[i], borderWidth: 2, cubicInterpolationMode: "monotone", spanGaps: true,
        pointRadius: spec.labels.length > 40 ? 0 : 2.5, pointHoverRadius: 5, pointBackgroundColor: SERIES[i], pointBorderColor: "#fff", pointBorderWidth: 1.5 }
    : { label: s.name, data: s.data, backgroundColor: spec.signed ? s.data.map((v) => (v < 0 ? SERIES[1] : SERIES[0])) : spec.emphasis === "last" ? s.data.map((_, k) => (k === s.data.length - 1 ? SERIES[0] : "#b9c6dc")) : SERIES[i], borderColor: "#fff", borderWidth: type === "stacked" ? 1 : 0,
        borderRadius: type === "stacked" ? 0 : 4, borderSkipped: "start", maxBarThickness: 30, categoryPercentage: 0.75, barPercentage: many ? 0.9 : 0.8 });
  canvas.parentElement.style.height = (horizontal ? Math.max(220, spec.labels.length * (many ? 16 * series.length + 14 : 30) + 70) : 320) + "px";
  return new Chart(canvas, { type: line ? "line" : "bar", data: { labels: spec.labels, datasets }, options, plugins: [whiteBackground] });
}

/* Forecast: past values, the forecast, and the band where the result will probably land. */
function drawForecast(canvas, r, animate) {
  const old = Chart.getChart(canvas);
  if (old) old.destroy();
  const past = r.history.slice(-48);
  const labels = past.map((p) => p.label).concat(r.forecast.map((f) => f.label));
  const pad = past.map(() => null);
  const last = past[past.length - 1].value;
  const options = baseOptions(true, false, "", r.label);
  if (animate && !calm()) options.animation = GROW;
  options.plugins.legend.labels.filter = (item) => item.text !== "low";
  options.plugins.tooltip.filter = (c) => c.dataset.label !== "low" && c.parsed.y !== null;
  options.plugins.tooltip.callbacks.label = (c) => {
    if (c.dataset.label === "Likely range") {
      const f = r.forecast[c.dataIndex - past.length];
      return f ? ` Likely range: ${fmtNum(f.lo)} to ${fmtNum(f.hi)}` : "";
    }
    return ` ${c.dataset.label}: ${fmtNum(c.parsed.y)}`;
  };
  canvas.parentElement.style.height = "340px";
  return new Chart(canvas, {
    type: "line",
    data: { labels, datasets: [
      { label: "Actual", data: past.map((p) => p.value), borderColor: SERIES[0], backgroundColor: SERIES[0], borderWidth: 2, cubicInterpolationMode: "monotone", pointRadius: 0, pointHoverRadius: 5 },
      { label: "Forecast", data: pad.slice(0, -1).concat([last], r.forecast.map((f) => f.value)), borderColor: SERIES[0], backgroundColor: "#fff",
        borderWidth: 2, borderDash: [6, 4], cubicInterpolationMode: "monotone", pointRadius: 2.5, pointBackgroundColor: "#fff", pointBorderColor: SERIES[0], pointHoverRadius: 5 },
      { label: "low", data: pad.slice(0, -1).concat([last], r.forecast.map((f) => f.lo)), borderWidth: 0, pointRadius: 0, pointHoverRadius: 0, cubicInterpolationMode: "monotone" },
      { label: "Likely range", data: pad.slice(0, -1).concat([last], r.forecast.map((f) => f.hi)), borderWidth: 0, pointRadius: 0, pointHoverRadius: 0, cubicInterpolationMode: "monotone",
        backgroundColor: "rgba(42,120,214,0.16)", fill: "-1" },
    ] },
    options, plugins: [whiteBackground],
  });
}

function downloadChart(canvas, name) {
  const a = document.createElement("a");
  a.href = canvas.toDataURL("image/png");
  a.download = name + ".png";
  a.click();
}
