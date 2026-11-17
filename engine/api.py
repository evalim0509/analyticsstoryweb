"""The only door between the web page and the Python engine.
The page sends a function name and JSON; it gets JSON back."""
import json, math, traceback
from . import store, ingest, quality, joins, builder, chat, ml, story
from . import measures, catalogue


def state():
    datasets = []
    for ds in store.DATASETS.values():
        d = store.public(ds)
        d["health"] = quality.check(ds["id"])["summary"] if ds["kind"] == "table" else None
        datasets.append(d)
    docs = {}
    for p in store.PASSAGES:
        docs[p["source"]] = docs.get(p["source"], 0) + 1
    return {"datasets": datasets, "documents": [{"name": k, "passages": v} for k, v in docs.items()],
            "joins": joins.suggest(), "links": store.LINKS, "log": store.LOG[-30:], "suggestions": chat.suggestions()}


def preview(name, data):
    return ingest.preview(name, data.to_bytes() if hasattr(data, "to_bytes") else bytes(data))


def confirm(token, choices=None):
    ingest.confirm(token, choices)
    return state()


def check(dataset):
    return quality.check(dataset)


def fix(dataset, key):
    r = quality.apply_fix(dataset, key)
    return {"result": r, "check": quality.check(dataset), "state": state()}


def fix_all(dataset):
    """Accept every suggested fix that is rated High confidence."""
    done = []
    for _ in range(40):
        todo = [i for i in quality.check(dataset)["issues"] if i["fix"] and i["confidence"] == "High" and i["kind"] != "missing"]
        if not todo:
            break
        done.append(quality.apply_fix(dataset, todo[0]["key"]).get("text"))
    return {"done": done, "check": quality.check(dataset), "state": state()}


def dismiss(dataset, key):
    quality.dismiss(dataset, key)
    return {"check": quality.check(dataset), "state": state()}


def restore(dataset):
    quality.restore(dataset)
    return {"check": quality.check(dataset), "state": state()}


def accept_join(key):
    r = joins.accept(key)
    return {"result": r, "state": state()}


def remove_link(link):
    joins.remove_link(link)
    return state()


def ask(question, context=None):
    a = chat.answer(question, context)
    ds = store.DATASETS.get(a.get("dataset") or "")
    if ds:
        base = store.DATASETS.get(ds.get("base", ds["id"]), ds)
        n = quality.check(base["id"])["summary"]["to_review"] if base["kind"] == "table" else 0
        if n:
            a["notice"] = {"dataset": base["id"], "text": f"“{base['name']}” still has {n} item{'s' if n != 1 else ''} to review in the data check. Unfixed duplicates or typing mistakes can change this answer."}
    return a


def ask_about_table(spec):
    r = builder.run(spec)
    return {"type": "table", "text": builder.describe(r), "confidence": "High",
            "table": {"columns": r["columns"], "rows": r["rows"][:200], "types": r["types"], "more": max(0, len(r["rows"]) - 200)},
            "chart": r.get("chart"), "builder": spec, "dataset": r["dataset"],
            "how": {"matched": [], "ignored": [], "steps": r["steps"] + ["Read the finished table: highest, lowest, total and change over time."],
                    "sql": r["sql"], "source": f"{r['dataset_name']} — {r['rows_used']:,} of {r['rows_total']:,} rows used"}}


def ask_about_ml(result):
    return chat.describe_ml(result)


def build(spec):
    return builder.run(spec)


def export(spec, kind="xlsx"):
    return builder.export(spec, kind)


def field_values(dataset, field):
    return builder.field_values(dataset, field)


def ml_options(dataset):
    return ml.options(dataset)


def ml_run(kind, spec):
    return {"forecast": ml.forecast, "drivers": ml.drivers, "segments": ml.segments, "unusual": ml.unusual}[kind](spec)


def ml_predict(result, inputs):
    return ml.predict_one(result, inputs)


def story_options():
    return {"options": story.options(), "tidy": story.tidy_status()}


def story_tidy():
    done = story.tidy_all()
    return {"done": done, "state": state(), "options": story.options(), "tidy": story.tidy_status()}


def story_build(spec):
    return story.build(spec)


def catalogue_start():
    """What Gist needs, every column in the files, and Gist's best guess for each need."""
    return {"needs": catalogue.needs(), "columns": catalogue.columns(), "guess": catalogue.guess(), "roles": dict(catalogue.ROLES), "nets": catalogue.nets(),
            "date_orders": catalogue.date_orders()}


def catalogue_set(roles, signs=None, orders=None, date_fallback=None):
    """roles: {need: {table, column}}; signs: {dataset: "credit"|"debit"}; orders: {"dataset|column": "dmy"|"mdy"};
    date_fallback: {table, column} to use where the matched date is blank."""
    for dataset, sign in (signs or {}).items():
        catalogue.set_sign(dataset, sign)
    for key, order in (orders or {}).items():
        dataset, column = key.split("|", 1)
        catalogue.set_order(dataset, column, order)
    roles = dict(roles or {})
    d, fb = roles.get("date"), date_fallback or {}
    if isinstance(d, dict) and fb.get("column") and fb.get("table") == d.get("table"):
        roles["date"] = {"table": d["table"], "column": catalogue.combine_dates(d["table"], d["column"], fb["column"])}
    return {"roles": catalogue.set_roles(roles), "options": story.options(), "columns": catalogue.columns()}


def story_checks():
    """Gist's guesses for the quick-checks step."""
    return {"tables": measures.checks()}


def story_set_checks(answers):
    measures.set_checks(answers)
    return {"tables": measures.checks(), "options": story.options()}


def measure_list(dataset):
    ds = store.DATASETS[dataset]
    base = store.DATASETS[ds.get("base", ds["id"])]
    return {"suggested": measures.suggested(ds), "mine": [m for m in measures.derived(ds) if m.get("user")],
            "numbers": [c["name"] for c in ds["columns"] if c["type"] == "number"],
            "ids": [c["name"] for c in ds["columns"] if c["role"] == "id"], "base": base["name"]}


def measure_add(dataset, name, a, op, b=None):
    r = measures.add(dataset, name, a, op, b)
    return {"added": r, "options": story.options()}


def measure_remove(value):
    measures.remove(value)
    return {"options": story.options()}


def set_glossary(entries):
    chat.set_glossary(entries)
    return {"count": len(chat.GLOSSARY)}


def _safe(o):
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else o
    if isinstance(o, dict):
        return {str(k): _safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_safe(v) for v in o]
    if hasattr(o, "item") and not isinstance(o, (str, bytes)):
        try:
            return _safe(o.item())
        except Exception:
            return str(o)
    return o


def dispatch(fn, args_json="{}", blob=None):
    try:
        args = json.loads(args_json or "{}")
        if blob is not None:
            args["data"] = blob
        return json.dumps({"ok": True, "result": _safe(globals()[fn](**args))}, default=str)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-1500:]})
