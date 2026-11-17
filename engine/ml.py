"""Machine learning, explained in plain English.
forecast  - what is likely to happen next (time series)
drivers   - what influences a result, and predicting it (random forest)
segments  - natural groups in the data (k-means)
unusual   - records that do not look like the rest (isolation forest)
Everything is seeded, so the same data always gives the same answer."""
import math, datetime as dt
import numpy as np
from . import store, builder
from .store import q, rows, fmt

RESULTS = {}     # id -> last results, so the chat can answer questions about them
MODELS = {}      # id -> fitted model for "try a prediction"
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _keep(result, model=None):
    rid = store.next_id("m")
    result["id"] = rid
    RESULTS[rid] = result
    if model is not None:
        MODELS[rid] = model
    return result


def _reliability(score):
    if score >= 0.9:
        return "High"
    if score >= 0.8:
        return "Good"
    if score >= 0.65:
        return "Fair"
    return "Low"


# ------------------------------------------------------------------ forecast
def _period(d, grain):
    y, m, day = int(d[:4]), int(d[5:7]), int(d[8:10])
    if grain == "month":
        return y * 12 + (m - 1)
    o = dt.date(y, m, day).toordinal()
    return o // 7 if grain == "week" else o


def _period_label(p, grain):
    if grain == "month":
        return f"{MON[p % 12]} {p // 12}"
    d = dt.date.fromordinal(p * 7 if grain == "week" else p)
    return f"{d.day} {MON[d.month - 1]} {d.year}"


def _fit_predict(name, y, h, m):
    """Returns (in-sample fitted values, next h values)."""
    n = len(y)
    t = np.arange(n)
    if name == "last":
        return np.r_[y[0], y[:-1]], np.repeat(y[-1], h)
    if name == "seasonal":
        fitted = np.r_[y[:m], y[:-m]]
        return fitted, np.array([y[n - m + (i % m)] for i in range(h)])
    if name == "trend":
        b, a = np.polyfit(t, y, 1)
        return a + b * t, a + b * (n + np.arange(h))
    if name == "trend_seasonal":
        X = np.zeros((n + h, m + 1))
        X[:, 0] = np.arange(n + h)
        X[np.arange(n + h), 1 + (np.arange(n + h) % m)] = 1
        coef = np.linalg.lstsq(X[:n], y, rcond=None)[0]
        return X[:n] @ coef, X[n:] @ coef
    if name == "smoothing":          # Holt-Winters, additive, small fixed grid
        best = None
        for al in (0.2, 0.4, 0.6, 0.8):
            for be in (0.05, 0.2):
                for ga in (0.1, 0.3, 0.5):
                    level = y[:m].mean()
                    trend = (y[m:2 * m].mean() - y[:m].mean()) / m
                    season = list(y[:m] - level)
                    fitted = []
                    for i in range(n):
                        s = season[i % m]
                        fitted.append(level + trend + s)
                        new_level = al * (y[i] - s) + (1 - al) * (level + trend)
                        trend = be * (new_level - level) + (1 - be) * trend
                        season[i % m] = ga * (y[i] - new_level) + (1 - ga) * s
                        level = new_level
                    sse = float(((np.array(fitted[m:]) - y[m:]) ** 2).sum())
                    if best is None or sse < best[0]:
                        best = (sse, np.array(fitted), np.array([level + (k + 1) * trend + season[(n + k) % m] for k in range(h)]))
        return best[1], best[2]
    raise ValueError(name)


MODEL_WORDS = {"last": "Carry the latest value forward", "seasonal": "Repeat the same period from last year",
               "trend": "Follow the straight-line trend", "trend_seasonal": "Trend plus the yearly pattern",
               "smoothing": "Weighted recent history with trend and yearly pattern"}


def forecast(spec):
    ds = store.DATASETS[spec["dataset"]]
    date = spec.get("date") or next((c["name"] for c in ds["columns"] if c["type"] == "date"), None)
    if not date:
        return {"error": f"“{ds['name']}” has no date field, so there is nothing to forecast over time. Pick a table with dates."}
    value, agg = spec.get("value"), spec.get("agg") or "sum"
    if value and store.col(ds, value)["type"] != "number":
        value = None
    label = builder.value_label({"field": value, "agg": agg}) if value else f"Number of {ds['name']}"
    where, params, filter_words = builder.where_clause(ds, spec.get("filters"))
    if filter_words:
        label += " where " + " and ".join(filter_words)
    expr = builder.AGG_SQL[agg].format(c=q(value)) if value else "COUNT(*)"
    dq = q(date)
    cond = (where + " AND " if where else " WHERE ") + f"{dq} IS NOT NULL"
    span = rows(f"SELECT MIN({dq}), MAX({dq}), COUNT(*) FROM {q(ds['table'])}{cond}", params)[0]
    if not span[2]:
        return {"error": "There are no dated rows to forecast from."}
    grain = spec.get("grain")
    raw = rows(f"SELECT {dq}, {expr.replace('COUNT(*)', '1') if not value else q(value)} FROM {q(ds['table'])}{cond}", params)
    days = sorted(dt.date.fromisoformat(r[0]).toordinal() for r in raw)
    core_span = days[int(0.98 * (len(days) - 1))] - days[int(0.02 * (len(days) - 1))]
    if not grain:
        grain = "month" if core_span > 300 else "week" if core_span > 70 else "day"
    m = {"month": 12, "week": 52, "day": 7}[grain]
    buckets = {}
    for d, v in raw:
        buckets.setdefault(_period(d, grain), []).append(v)
    periods = sorted(buckets)
    # keep the main run of periods; stray dates far from the rest are ignored
    runs, cur = [], [periods[0]]
    for p in periods[1:]:
        if p - cur[-1] > 6:
            runs.append(cur); cur = [p]
        else:
            cur.append(p)
    runs.append(cur)
    main = max(runs, key=lambda r: sum(len(buckets[p]) for p in r))
    ignored = sum(len(buckets[p]) for r in runs if r is not main for p in r)
    notes = []
    if ignored:
        notes.append(f"Ignored {ignored} row{'s' if ignored != 1 else ''} with dates far away from all the others.")
    first, last = main[0], main[-1]
    if grain == "month":           # drop a final month that is clearly incomplete
        last_day = max(int(d[8:10]) for d, _ in raw if _period(d, grain) == last)
        from . import measures as MS
        base = store.DATASETS[ds.get("base", ds["id"])]
        done, why = MS.month_complete(base, date, last, last_day) if date in [c["name"] for c in base["columns"]] else (last_day >= 25, "")
        if not done and last - first > 3:
            notes.append(f"Left out {_period_label(last, grain)}. {why}".strip())
            last -= 1

    def combine(vs):
        vs = [v for v in vs if v is not None]
        if not value:
            return float(len(vs))
        if not vs:
            return 0.0 if agg in ("sum", "count") else float("nan")
        return {"sum": sum(vs), "avg": sum(vs) / len(vs), "count": len(vs), "distinct": len(set(vs)), "min": min(vs), "max": max(vs)}[agg]
    y = np.array([combine(buckets.get(p, [])) if p in buckets else (0.0 if agg in ("sum", "count") or not value else float("nan"))
                  for p in range(first, last + 1)], dtype=float)
    if np.isnan(y).any():
        idx = np.arange(len(y)); ok = ~np.isnan(y)
        y = np.interp(idx, idx[ok], y[ok])
    n = len(y)
    unit = grain
    if n < 6:
        return {"error": f"I need at least 6 {unit}s of history to forecast, and this data has {n}. Add more history or pick a different date field."}
    h = int(spec.get("horizon") or {"month": 6, "week": 8, "day": 14}[grain])
    h = max(1, min(h, 36))
    seasonal_ok = n >= 2 * m
    names = ["last", "trend"] + (["seasonal", "trend_seasonal", "smoothing"] if seasonal_ok else [])
    test = max(2, min(h, n // 4))
    train = y[:-test]
    scores = []
    for name in names:
        if name in ("seasonal", "trend_seasonal", "smoothing") and len(train) < (2 * m if name == "smoothing" else m + 3):
            continue
        _, pred = _fit_predict(name, train, test, m)
        denom = np.abs(y[-test:]).sum() or 1.0
        wape = float(np.abs(pred - y[-test:]).sum() / denom)
        scores.append((wape, name, pred))
    scores.sort(key=lambda s: s[0])
    wape, best, test_pred = scores[0]
    fitted, pred = _fit_predict(best, y, h, m)
    start = m if best in ("seasonal", "smoothing") else 1 if best == "last" else 0
    resid = y[start:] - fitted[start:]
    sigma = float(max(np.std(resid), np.std(test_pred - y[-test:]) * 0.8)) if len(resid) > 1 else float(np.std(y))
    z = 1.2816
    non_negative = bool((y >= 0).all())
    fc = []
    for k in range(h):
        s = sigma * math.sqrt(1 + k / max(m if seasonal_ok else 6, 1))
        lo, hi = pred[k] - z * s, pred[k] + z * s
        if non_negative:
            lo = max(lo, 0.0)
        fc.append({"label": _period_label(last + 1 + k, grain), "value": float(max(pred[k], 0) if non_negative else pred[k]),
                   "lo": float(lo), "hi": float(hi)})
    accuracy = max(0.0, 1 - wape)
    mae = float(np.abs(test_pred - y[-test:]).mean())
    history = [{"label": _period_label(first + i, grain), "value": float(v)} for i, v in enumerate(y)]
    slope = float(np.polyfit(np.arange(n), y, 1)[0])
    yearly_change = slope * m / (abs(y.mean()) or 1)
    trend_word = "rising" if yearly_change > 0.03 else "falling" if yearly_change < -0.03 else "flat"
    bullets = [f"The trend is {trend_word}" + (f": about {abs(yearly_change) * 100:.0f}% {'up' if yearly_change > 0 else 'down'} per year on average." if trend_word != "flat" else ": no clear growth or decline.")]
    season = None
    if grain == "month" and seasonal_ok:
        detr = y - np.polyval(np.polyfit(np.arange(n), y, 1), np.arange(n))
        by_m = [float(np.mean([detr[i] for i in range(n) if (first + i) % 12 == k] or [0])) for k in range(12)]
        hi_m, lo_m = int(np.argmax(by_m)), int(np.argmin(by_m))
        strength = (max(by_m) - min(by_m)) / (abs(y.mean()) or 1)
        if strength > 0.1:
            season = {"high": MON[hi_m], "low": MON[lo_m]}
            bullets.append(f"There is a yearly pattern: {MON[hi_m]} is usually the strongest month and {MON[lo_m]} the weakest.")
    total_fc = sum(f["value"] for f in fc)
    additive = (not value) or agg in ("sum", "count")
    prev = float(y[-h:].sum()) if n >= h else None
    headline = f"{label} is expected to be about {fmt(fc[0]['value'])} in {fc[0]['label']}"
    if additive and h > 1:
        headline += f", and {fmt(total_fc)} in total over the next {h} {unit}s"
        if prev:
            ch = 100 * (total_fc - prev) / abs(prev)
            headline += f" ({'up' if ch >= 0 else 'down'} {abs(ch):.0f}% on the last {h} {unit}s)"
    headline += "."
    rel = _reliability(accuracy)
    if value and ds["kind"] == "table":
        from . import quality
        if any(i["kind"] == "unusual" and i["column"] == value for i in quality.check(ds["id"])["issues"]):
            bullets.append(f"Heads-up: {value} still contains a few extreme values (see the data check). They can distort a forecast.")
    bullets.append(f"Likely range for {fc[0]['label']}: {fmt(fc[0]['lo'])} to {fmt(fc[0]['hi'])}. The range gets wider further out because the future is less certain.")
    reliability = {"label": rel, "score": round(accuracy * 100),
                   "text": f"I hid the last {test} {unit}s, forecast them from the earlier data, and compared with what really happened. "
                           f"The forecast was {round(accuracy * 100)}% accurate, typically off by about {fmt(mae)} per {unit}."
                           + (" Treat this as a rough guide only." if rel in ("Fair", "Low") else "")}
    steps = [f"Started with “{ds['name']}” ({ds['rows']:,} rows) from {ds['source']}."]
    if filter_words:
        steps.append(f"Kept only rows where {' and '.join(filter_words)}.")
    steps += notes
    steps += [f"Worked out {label} for each {unit} using {date}: {n} {unit}s from {history[0]['label']} to {history[-1]['label']}.",
              f"Tried {len(scores)} forecasting methods. Tested each one by hiding the last {test} {unit}s and checking how close it got.",
              f"Chose “{MODEL_WORDS[best]}” because it was the most accurate in that test ({round(accuracy * 100)}%).",
              f"Used all {n} {unit}s to forecast the next {h}. The shaded band is where about 8 in 10 outcomes should fall, based on past misses."]
    return _keep({"kind": "forecast", "title": f"Forecast of {label}", "headline": headline, "bullets": bullets, "reliability": reliability,
                  "history": history, "forecast": fc, "unit": unit, "label": label, "season": season, "trend": trend_word,
                  "backtest": [{"label": history[n - test + i]["label"], "actual": float(y[n - test + i]), "predicted": float(test_pred[i])} for i in range(test)],
                  "methods": [{"name": MODEL_WORDS[nm], "accuracy": round(max(0, 1 - w) * 100, 1), "chosen": nm == best} for w, nm, _ in scores],
                  "typical_error": mae, "steps": steps, "dataset": ds["id"], "dataset_name": ds["name"],
                  "spec": {"dataset": ds["id"], "date": date, "value": value, "agg": agg, "horizon": h, "filters": spec.get("filters") or []},
                  "table": {"columns": [unit.capitalize(), "Forecast", "Low end", "High end"],
                            "rows": [[f["label"], round(f["value"], 2), round(f["lo"], 2), round(f["hi"], 2)] for f in fc]}})


# ------------------------------------------------------------------ shared data prep
def _load(ds, names):
    data = rows(f"SELECT {', '.join(q(n) for n in names)} FROM {q(ds['table'])}")
    return [list(r) for r in data]


def _usable_features(ds, target=None):
    feats = []
    for c in ds["columns"]:
        present = ds["rows"] - c["missing"]
        if c["name"] == target or present < 0.6 * ds["rows"] or c["distinct"] < 2:
            continue
        if c["role"] == "measure" or (c["type"] == "number" and c["role"] == "category"):
            feats.append((c["name"], "number"))
        elif c["role"] == "category" and c["distinct"] <= 25:
            feats.append((c["name"], "category"))
    return feats


def _encode(col_values, kind, levels=None):
    if kind == "number":
        vals = np.array([np.nan if v is None else float(v) for v in col_values])
        med = float(np.nanmedian(vals)) if not np.isnan(vals).all() else 0.0
        return np.where(np.isnan(vals), med, vals), {"median": med}
    levels = levels or sorted({str(v) for v in col_values if v is not None})
    index = {v: i for i, v in enumerate(levels)}
    return np.array([index.get(str(v), -1) if v is not None else -1 for v in col_values], dtype=float), {"levels": levels}


# ------------------------------------------------------------------ drivers / prediction
def drivers(spec):
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.inspection import permutation_importance
    ds = store.DATASETS[spec["dataset"]]
    target = spec["target"]
    tc = store.col(ds, target)
    feats = [(n, k) for n, k in _usable_features(ds, target) if not spec.get("features") or n in spec["features"]]
    if not feats:
        return {"error": "There are no other usable fields in this table to explain the result with."}
    data = [r for r in _load(ds, [target] + [f[0] for f in feats]) if r[0] is not None]
    if len(data) < 40:
        return {"error": f"I need at least 40 rows with a known {target} to learn from, and this table has {len(data)}."}
    regression = tc["type"] == "number" and tc["distinct"] > 10
    if not regression and tc["distinct"] > 12:
        return {"error": f"{target} has too many different values to predict. Pick a number, or a field with a few categories (such as Yes / No)."}
    X_cols, meta = [], []
    for j, (name, kind) in enumerate(feats):
        arr, info = _encode([r[j + 1] for r in data], kind)
        X_cols.append(arr); meta.append({"name": name, "kind": kind, **info})
    X = np.column_stack(X_cols)
    if regression:
        yv = np.array([float(r[0]) for r in data])
        model = RandomForestRegressor(n_estimators=150, min_samples_leaf=3, random_state=0)
    else:
        classes = sorted({str(r[0]) for r in data})
        yv = np.array([classes.index(str(r[0])) for r in data])
        model = RandomForestClassifier(n_estimators=150, min_samples_leaf=3, random_state=0)
    Xtr, Xte, ytr, yte = train_test_split(X, yv, test_size=0.25, random_state=0)
    model.fit(Xtr, ytr)
    pred = model.predict(Xte)
    n_te = len(yte)
    if regression:
        ss_res, ss_tot = float(((yte - pred) ** 2).sum()), float(((yte - yte.mean()) ** 2).sum()) or 1.0
        r2 = max(0.0, 1 - ss_res / ss_tot)
        mae = float(np.abs(yte - pred).mean())
        base = float(np.abs(yte - np.median(ytr)).mean())
        score = r2
        rel_text = (f"I trained on {len(ytr):,} rows and tested on {n_te:,} rows the model had never seen. "
                    f"The other fields explain {r2 * 100:.0f}% of the differences in {target}. "
                    f"Predictions were typically off by {fmt(mae)}, compared with {fmt(base)} if you simply guessed the typical value every time.")
    else:
        acc = float((pred == yte).mean())
        maj = int(np.bincount(ytr).argmax())
        base = float((yte == maj).mean())
        score = acc
        rel_text = (f"I trained on {len(ytr):,} rows and tested on {n_te:,} rows the model had never seen. "
                    f"It got {acc * 100:.0f}% of them right. Always guessing “{classes[maj]}” would get {base * 100:.0f}% right, "
                    f"so the model {'adds real insight' if acc - base > 0.05 else 'is only slightly better than guessing' if acc > base else 'is no better than guessing'}.")
        if acc - base <= 0.05:
            score = min(score, 0.6)
    imp = permutation_importance(model, Xte, yte, n_repeats=8, random_state=0).importances_mean
    imp = np.clip(imp, 0, None)
    shares = imp / imp.sum() if imp.sum() > 0 else np.zeros_like(imp)
    order = np.argsort(-shares)
    pos = None
    if not regression:
        pos = next((c for c in classes if c.lower() in ("yes", "true", "1", "y", "won", "churned")), None) or \
              classes[int(np.bincount(yv).argmin())]
        outcome = (yv == classes.index(pos)).astype(float)
    else:
        outcome = yv

    def effect(j):
        m = meta[j]
        col = X[:, j]
        if m["kind"] == "number":
            med = np.median(col)
            hi, lo = outcome[col > med], outcome[col <= med]
            if len(hi) < 5 or len(lo) < 5:
                return ""
            a, b = hi.mean(), lo.mean()
            if regression:
                return f"When {m['name']} is above {fmt(float(med))}, {target} averages {fmt(float(a))}; at or below it, {fmt(float(b))}."
            return f"When {m['name']} is above {fmt(float(med))}, {a * 100:.0f}% are “{pos}”; at or below it, {b * 100:.0f}%."
        stats = [(lv, outcome[col == i].mean(), int((col == i).sum())) for i, lv in enumerate(m["levels"]) if (col == i).sum() >= 5]
        if len(stats) < 2:
            return ""
        hi, lo = max(stats, key=lambda s: s[1]), min(stats, key=lambda s: s[1])
        if regression:
            return f"Highest for {m['name']} “{hi[0]}” (average {fmt(float(hi[1]))}), lowest for “{lo[0]}” ({fmt(float(lo[1]))})."
        return f"“{pos}” is most common when {m['name']} is “{hi[0]}” ({hi[1] * 100:.0f}%) and least when “{lo[0]}” ({lo[1] * 100:.0f}%)."

    importance = [{"name": meta[j]["name"], "share": round(float(shares[j]) * 100, 1), "effect": effect(j)} for j in order if shares[j] > 0.005][:8]
    rel = _reliability(score)
    if not importance:
        headline = f"Nothing in this table reliably explains {target}."
    else:
        top = importance[0]
        headline = f"{top['name']} has the biggest influence on {target}" + \
                   (f", followed by {importance[1]['name']}" if len(importance) > 1 else "") + "."
    bullets = [i["effect"] for i in importance[:3] if i["effect"]]
    if importance and importance[0]["share"] > 85 and score > 0.97:
        bullets.append(f"{importance[0]['name']} predicts {target} almost perfectly. It may be the same information recorded a different way.")
    form = []
    for j in order[:6]:
        m = meta[j]
        if m["kind"] == "number":
            form.append({"name": m["name"], "kind": "number", "default": round(m["median"], 2), "min": float(X[:, j].min()), "max": float(X[:, j].max())})
        else:
            common = int(np.bincount(X[:, j][X[:, j] >= 0].astype(int)).argmax())
            form.append({"name": m["name"], "kind": "category", "options": m["levels"], "default": m["levels"][common]})
    steps = [f"Started with “{ds['name']}” ({ds['rows']:,} rows) from {ds['source']}; used the {len(data):,} rows where {target} is filled in.",
             f"Used these fields as possible explanations: {', '.join(m['name'] for m in meta)}. Left out IDs, free text and dates because they do not generalise.",
             f"Set aside a quarter of the rows ({n_te:,}) for testing, and let the model learn from the other {len(ytr):,}.",
             "The model is a “random forest”: 150 simple decision trees that each vote, which handles both numbers and categories.",
             f"Measured how well it predicts the test rows it had never seen ({'explains ' + str(round(score * 100)) + '% of the variation' if regression else str(round(float((pred == yte).mean()) * 100)) + '% correct'}).",
             "To rank the fields, shuffled each one in turn and measured how much worse the predictions became. A bigger drop means the field matters more."]
    defaults = {m["name"]: (m["median"] if m["kind"] == "number" else (m["levels"][0] if m["levels"] else None)) for m in meta}
    for f in form:
        defaults[f["name"]] = f["default"]
    return _keep({"kind": "drivers", "title": f"What influences {target}", "headline": headline, "bullets": bullets,
                  "reliability": {"label": rel, "score": round(score * 100), "text": rel_text},
                  "importance": importance, "target": target, "regression": regression, "form": form, "positive": pos,
                  "steps": steps, "dataset": ds["id"], "dataset_name": ds["name"], "spec": {"dataset": ds["id"], "target": target},
                  "table": {"columns": ["Field", "Share of influence (%)", "What the data shows"],
                            "rows": [[i["name"], i["share"], i["effect"]] for i in importance]}},
                 model={"model": model, "meta": meta, "regression": regression, "classes": None if regression else classes,
                        "defaults": defaults, "target": target})


def predict_one(result_id, inputs):
    """'Try a prediction': the user sets a few values, the trained model answers."""
    m = MODELS[result_id]
    row = []
    for meta in m["meta"]:
        v = inputs.get(meta["name"], m["defaults"][meta["name"]])
        if meta["kind"] == "number":
            try:
                row.append(float(v))
            except (TypeError, ValueError):
                row.append(meta["median"])
        else:
            row.append(float(meta["levels"].index(str(v))) if str(v) in meta["levels"] else -1.0)
    X = np.array([row])
    if m["regression"]:
        each = np.array([t.predict(X)[0] for t in m["model"].estimators_])
        return {"text": f"Predicted {m['target']}: about {fmt(float(each.mean()))}",
                "detail": f"Most likely between {fmt(float(np.percentile(each, 10)))} and {fmt(float(np.percentile(each, 90)))}."}
    proba = m["model"].predict_proba(X)[0]
    ranked = sorted(zip(m["classes"], proba), key=lambda p: -p[1])
    return {"text": f"Predicted {m['target']}: {ranked[0][0]} ({ranked[0][1] * 100:.0f}% likely)",
            "detail": ", ".join(f"{c}: {p * 100:.0f}%" for c, p in ranked[:4]) + "."}


# ------------------------------------------------------------------ segments
def segments(spec):
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    ds = store.DATASETS[spec["dataset"]]
    feats = [n for n, k in _usable_features(ds) if k == "number" and (not spec.get("features") or n in spec["features"])]
    if len(feats) < 2:
        return {"error": "I need at least two number fields to find groups. This table does not have enough."}
    cats = [n for n, k in _usable_features(ds) if k == "category"][:4]
    data = _load(ds, feats + cats)
    if len(data) < 30:
        return {"error": f"I need at least 30 rows to find groups, and this table has {len(data)}."}
    if len(data) > 6000:
        data = [data[i] for i in np.random.RandomState(0).choice(len(data), 6000, replace=False)]
    X = np.column_stack([_encode([r[j] for r in data], "number")[0] for j in range(len(feats))])
    lo, hi = np.percentile(X, 1, axis=0), np.percentile(X, 99, axis=0)
    Xc = np.clip(X, lo, hi)
    sd = Xc.std(axis=0); sd[sd == 0] = 1
    Z = (Xc - Xc.mean(axis=0)) / sd
    best = None
    for k in range(2, 7):
        km = KMeans(n_clusters=k, n_init=10, random_state=0).fit(Z)
        if np.bincount(km.labels_).min() < max(3, 0.03 * len(Z)):
            continue
        s = float(silhouette_score(Z, km.labels_, sample_size=min(2000, len(Z)), random_state=0))
        if best is None or s > best[0] + 0.02:
            best = (s, k, km.labels_)
    if best is None:
        return {"error": "The rows in this table are too alike to split into meaningful groups."}
    sil, k, labels = best
    overall = X.mean(axis=0)
    order = np.argsort(-np.bincount(labels))
    groups = []
    for rank, g in enumerate(order):
        mask = labels == g
        means = X[mask].mean(axis=0)
        diff = (Xc[mask].mean(axis=0) - Xc.mean(axis=0)) / sd
        traits = [f"{'higher' if diff[j] > 0 else 'lower'} {feats[j]} ({fmt(float(means[j]))} vs {fmt(float(overall[j]))} overall)"
                  for j in np.argsort(-np.abs(diff)) if abs(diff[j]) > 0.4][:3]
        mix = []
        for ci, cname in enumerate(cats):
            vals = [data[i][len(feats) + ci] for i in range(len(data)) if mask[i] and data[i][len(feats) + ci] is not None]
            allv = [r[len(feats) + ci] for r in data if r[len(feats) + ci] is not None]
            if vals:
                top = max(set(vals), key=vals.count)
                share, base = vals.count(top) / len(vals), allv.count(top) / len(allv)
                if share - base > 0.12:
                    mix.append(f"{share * 100:.0f}% have {cname} “{top}” (vs {base * 100:.0f}% overall)")
        groups.append({"name": f"Group {chr(65 + rank)}", "size": int(mask.sum()), "share": round(100 * mask.mean(), 1),
                       "traits": traits, "mix": mix[:2], "means": [round(float(v), 2) for v in means]})
    quality = "clearly different from each other" if sil > 0.45 else "fairly different, with some overlap" if sil > 0.25 else "only loosely separated, so treat them as a rough guide"
    score = min(0.95, 0.5 + sil)
    headline = f"The {len(data):,} rows fall into {k} natural groups."
    bullets = [f"{g['name']} ({g['share']:.0f}% of rows): " + ("; ".join(g["traits"] + g["mix"]) or "close to the overall average") + "." for g in groups]
    steps = [f"Started with “{ds['name']}” ({ds['rows']:,} rows) from {ds['source']}.",
             f"Compared rows on these number fields: {', '.join(feats)}. Put them on the same scale so that no field dominates.",
             "Tried splitting the rows into 2, 3, 4, 5 and 6 groups, so that rows in a group are as alike as possible (a method called k-means).",
             f"Kept {k} groups because that gave the cleanest separation.",
             "Described each group by the fields where it differs most from the overall average."]
    return _keep({"kind": "segments", "title": f"Natural groups in {ds['name']}", "headline": headline, "bullets": bullets,
                  "reliability": {"label": _reliability(score), "score": round(score * 100),
                                  "text": f"The groups are {quality}. Groups describe patterns in this data; they are not fixed rules."},
                  "groups": groups, "features": feats, "steps": steps, "dataset": ds["id"], "dataset_name": ds["name"],
                  "spec": {"dataset": ds["id"]},
                  "table": {"columns": ["Group", "Rows", "Share (%)"] + [f"Average {f}" for f in feats],
                            "rows": [[g["name"], g["size"], g["share"]] + g["means"] for g in groups]}})


# ------------------------------------------------------------------ unusual records
def unusual(spec):
    from sklearn.ensemble import IsolationForest
    ds = store.DATASETS[spec["dataset"]]
    feats = [n for n, k in _usable_features(ds) if k == "number"]
    if not feats:
        return {"error": "This table has no number fields to check for unusual records."}
    show = [c["name"] for c in ds["columns"]][:8]
    data = rows(f"SELECT _row, {', '.join(q(n) for n in feats)}, {', '.join(q(n) for n in show)} FROM {q(ds['table'])}")
    if len(data) < 30:
        return {"error": f"I need at least 30 rows to judge what is unusual, and this table has {len(data)}."}
    X = np.column_stack([_encode([r[1 + j] for r in data], "number")[0] for j in range(len(feats))])
    med = np.median(X, axis=0)
    mad = np.median(np.abs(X - med), axis=0) * 1.4826
    spread = np.where(mad > 0, mad, np.where(X.std(axis=0) > 0, X.std(axis=0), 1))
    zs = np.abs(X - med) / spread
    score = IsolationForest(n_estimators=200, random_state=0).fit(X).score_samples(X)
    n_show = int(max(5, min(25, round(0.01 * len(data)))))
    idx = [i for i in np.argsort(score)[: n_show * 3] if zs[i].max() >= 3][:n_show]
    q1, q3 = np.percentile(X, 25, axis=0), np.percentile(X, 75, axis=0)
    out = []
    for i in idx:
        why = [f"{feats[j]} is {fmt(float(X[i, j]))} (usually {fmt(float(q1[j]))} to {fmt(float(q3[j]))})" for j in np.argsort(-zs[i]) if zs[i, j] >= 3][:2]
        out.append([data[i][0], "; ".join(why)] + list(data[i][1 + len(feats):]))
    headline = f"{len(out)} of {len(data):,} rows stand out from the rest." if out else "Nothing stands out: every row looks similar to the others."
    steps = [f"Started with “{ds['name']}” ({ds['rows']:,} rows) from {ds['source']}.",
             f"Looked at these number fields together: {', '.join(feats)}.",
             "Scored every row on how easy it is to separate from the rest (a method called isolation forest). Rows that are easy to isolate are unusual.",
             "Kept only rows where at least one value is far outside the usual range, and listed the reason for each."]
    return _keep({"kind": "unusual", "title": f"Unusual records in {ds['name']}", "headline": headline,
                  "bullets": ["Unusual does not mean wrong. These are the rows worth a second look.",
                              "“Row in file” is the row number in the file you uploaded, so you can find it."],
                  "reliability": None, "steps": steps, "dataset": ds["id"], "dataset_name": ds["name"], "spec": {"dataset": ds["id"]},
                  "table": {"columns": ["Row in file", "Why it stands out"] + show, "rows": out}})


def options(ds_id):
    """What each analysis can use in this table, with sensible defaults."""
    ds = store.DATASETS[ds_id]
    dates = [c["name"] for c in ds["columns"] if c["type"] == "date"]
    measures = [c["name"] for c in ds["columns"] if c["role"] == "measure"]
    targets = [c["name"] for c in ds["columns"] if c["role"] == "measure" or (c["role"] == "category" and 2 <= c["distinct"] <= 12)]
    two = [c["name"] for c in ds["columns"] if c["role"] == "category" and c["distinct"] == 2]
    best_measure = next((m for m in measures if any(w in m.lower() for w in ("amount", "sales", "revenue", "total", "value"))), measures[-1] if measures else None)
    return {"dates": dates, "measures": measures, "targets": targets,
            "default_target": (two[-1] if two else best_measure), "default_measure": best_measure}
