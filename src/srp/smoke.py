"""Jev smoke test on a handful of dev-only reviews. Paid; invoked only via `cli.py smoke-jev --paid`.
Results go to runs/<run_id>/ and are NOT written to the result cache (the 100-review pilot must start cold)."""

import json
import sqlite3
import time
from datetime import datetime, timezone

from srp import paths
from srp.io_atomic import write_json_atomic, write_text_atomic
from srp.jev import JEV_INPUT_USD_PER_TOKEN, InvalidOutput, JevClient, build_request, parse_answers
from srp.labels import finalize, latin_ratio
from srp.rubric import label_config, load_rubric

RUNS_DIR = paths.ROOT / "runs"


def pick_reviews(con, n):
    """Deterministic dev-only pick: analysis_10000 minus checkpoint_500 (so cost_100 stays cold), minus
    rubric examples; mix of short English, one long review, and non-English/non-Latin text."""
    rubric_ids = {e["review_id"] for e in load_rubric()["examples"]}
    rows = con.execute("""
        SELECT r.review_id, r.review_text FROM samples s JOIN reviews r USING(review_id)
        WHERE s.sample='analysis_10000'
          AND s.review_id NOT IN (SELECT review_id FROM samples WHERE sample IN ('checkpoint_500','golden_50'))
        ORDER BY r.review_id""").fetchall()
    rows = [r for r in rows if r[0] not in rubric_ids]
    english = [r for r in rows if latin_ratio(r[1]) > 0.95 and 40 <= len(r[1]) <= 250][: max(n - 3, 1)]
    long_ = [r for r in rows if latin_ratio(r[1]) > 0.95 and len(r[1]) > 350][:1]
    non_latin = [r for r in rows if latin_ratio(r[1]) < 0.3 and len(r[1]) >= 15][:1]
    spanish = [r for r in rows if any(w in r[1].lower().split() for w in ("muy", "aplicación", "canciones"))][:1]
    return (english + long_ + non_latin + spanish)[:n]


def run_smoke(n, spend_cap_usd, thresholds):
    run_id = "smoke-jev-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RUNS_DIR / run_id
    out.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(paths.DB_PATH)
    picks = pick_reviews(con, n)
    lc = label_config()
    calls, results = [], []
    spent = 0.0

    def on_attempt(event):
        calls.append(event)
        with (out / "calls.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    client = JevClient(on_attempt=on_attempt)
    t_start = time.monotonic()
    try:
        for rid, text in picks:
            body, sents = build_request(text)
            # reserve worst case: request size in chars is an upper bound on tokens for this payload
            reserve = len(json.dumps(body, ensure_ascii=False)) * JEV_INPUT_USD_PER_TOKEN
            if spent + reserve > spend_cap_usd:
                results.append({"review_id": rid, "status": "skipped_spend_cap"})
                break
            ctx = {"run_id": run_id, "role": "enrich", "phase": "initial", "label_config": lc}
            resp, _info = client.call(body, [rid], ctx)
            if resp is None:
                results.append({"review_id": rid, "status": "failed_call"})
                continue
            spent += (resp.get("usage", {}).get("input_tokens") or 0) * JEV_INPUT_USD_PER_TOKEN
            try:
                sig = parse_answers(resp, text, sents)
                fields, reasons = finalize(sig, text, thresholds)
                results.append({"review_id": rid, "status": "completed", "text": text, "fields": fields,
                                "review_reasons": reasons, "signals": sig, "raw_response": resp,
                                "n_quote_candidates": len(sents) if sents else 0})
            except InvalidOutput as e:
                results.append({"review_id": rid, "status": "invalid_output", "error": str(e), "raw_response": resp})
    finally:
        client.close()
    wall = time.monotonic() - t_start

    ok = [c for c in calls if c["outcome"] == "succeeded"]
    summary = {
        "run_id": run_id, "label_config": lc, "reviews": len(picks), "wall_seconds": round(wall, 2),
        "attempts": len(calls), "succeeded_calls": len(ok),
        "input_tokens": sum(c["input_tokens"] or 0 for c in ok),
        "output_tokens": sum(c["output_tokens"] or 0 for c in ok),
        "cost_usd": round(sum(c["input_tokens"] or 0 for c in ok) * JEV_INPUT_USD_PER_TOKEN, 8),
        "response_models": sorted({c["response_model"] for c in ok if c["response_model"]}),
        "latency_ms": [c["latency_ms"] for c in ok],
        "statuses": {s: sum(r["status"] == s for r in results) for s in {r["status"] for r in results}},
    }
    write_json_atomic(out / "results.json", results)
    write_json_atomic(out / "summary.json", summary)
    write_text_atomic(out / "report.md", render_report(summary, results))
    return out, summary


def render_report(summary, results):
    lines = [f"# Jev smoke test `{summary['run_id']}`", "",
             f"- label_config: `{summary['label_config']}`",
             f"- response model(s): {summary['response_models']}",
             f"- attempts {summary['attempts']}, succeeded {summary['succeeded_calls']}, wall {summary['wall_seconds']} s",
             f"- tokens in/out: {summary['input_tokens']}/{summary['output_tokens']}, cost ${summary['cost_usd']}", "",
             "| review_id | topic (conf) | intent (cancel_p) | sev | sent | needs_review | quote |",
             "|---|---|---|---|---|---|---|"]
    for r in results:
        if r["status"] != "completed":
            lines.append(f"| {r['review_id']} | **{r['status']}** {r.get('error', '')} | | | | | |")
            continue
        f, s = r["fields"], r["signals"]
        q = f["evidence_quote"].replace("|", "/").replace("\n", " ")[:60]
        lines.append(f"| {r['review_id'][:8]} | {f['topic']} ({(s['topic_conf'] or 0):.2f}) | {f['intent']} ({s['cancel_p']:.2f}) "
                     f"| {f['severity']} | {f['sentiment']} | {f['needs_review']} {r['review_reasons']} | {q} |")
    return "\n".join(lines) + "\n"
