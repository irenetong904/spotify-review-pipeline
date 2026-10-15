"""Golden-50 evaluation (offline). Human labels are read ONLY here, after predictions exist; they are never model
inputs, prompt examples, thresholds or grouping inputs.

Predeclared tolerances (set before the first comparison): sentiment pass if |pred - human| <= 0.5 (one level on the
five-anchor scale); severity reported as exact agreement and MAE. Missing/quarantined predictions count as incorrect.
"""

import csv
import io
import json
from collections import Counter

from srp.contract import INTENTS, TOPICS
from srp.io_atomic import write_json_atomic, write_text_atomic

SENTIMENT_TOL = 0.5


def _bool(v):
    return str(v).strip().upper() == "TRUE"


def _ents(v):
    return sorted({e.strip().lower() for e in (v or "").replace(",", ";").split(";") if e.strip()})


def load_human(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["review_id"].strip(): r for r in csv.DictReader(f)}


def evaluate(human_path, pred_records, out_dir):
    human = load_human(human_path)
    preds = {r["review_id"]: r for r in pred_records}
    cases = []
    for rid, h in human.items():
        p = preds.get(rid)
        ok = p is not None and p.get("status") == "completed"
        hs, hsent = int(h["severity"]), float(h["sentiment"])
        c = {"review_id": rid, "prediction_status": p["status"] if p else "missing",
             "human_topic": h["topic"].strip(), "alt_topic": (h.get("alt_topic") or "").strip(),
             "human_intent": h["intent"].strip(), "human_severity": hs, "human_sentiment": hsent,
             "human_needs_review": _bool(h["needs_review"]), "ambiguous": _bool(h.get("ambiguous")),
             "human_entities": _ents(h.get("entities")), "human_quote": h["evidence_quote"].strip(),
             "notes": (h.get("notes") or "").strip()}
        if ok:
            c.update(pred_topic=p["topic"], pred_intent=p["intent"], pred_severity=p["severity"],
                     pred_sentiment=p["sentiment"], pred_needs_review=p["needs_review"], pred_entities=p["entities"],
                     pred_quote=p["evidence_quote"])
            c["topic_ok"] = p["topic"] == c["human_topic"]
            c["topic_ok_lenient"] = c["topic_ok"] or (bool(c["alt_topic"]) and p["topic"] == c["alt_topic"])
            c["intent_ok"] = p["intent"] == c["human_intent"]
            c["severity_ok"] = p["severity"] == hs
            c["severity_abs_err"] = abs(p["severity"] - hs)
            c["sentiment_abs_err"] = round(abs(p["sentiment"] - hsent), 4)
            c["sentiment_ok"] = c["sentiment_abs_err"] <= SENTIMENT_TOL
            c["entities_unsupported"] = sorted(set(p["entities"]) - set(c["human_entities"]))
            c["entities_missed"] = sorted(set(c["human_entities"]) - set(p["entities"]))
            hw, pw = set(c["human_quote"].lower().split()), set(p["evidence_quote"].lower().split())
            c["quote_word_overlap"] = round(len(hw & pw) / len(hw | pw), 3) if hw | pw else None
        else:
            for k in ("topic_ok", "topic_ok_lenient", "intent_ok", "severity_ok", "sentiment_ok"):
                c[k] = False
        cases.append(c)

    n = len(cases)
    scored = [c for c in cases if c["prediction_status"] == "completed"]

    def rate(key, xs=cases):
        return round(sum(1 for c in xs if c.get(key)) / len(xs), 4) if xs else None

    nr = Counter((c["human_needs_review"], c.get("pred_needs_review")) for c in scored)
    results = {
        "n": n, "completed_predictions": len(scored), "missing_or_quarantined": n - len(scored),
        "ambiguous_cases": sum(c["ambiguous"] for c in cases),
        "topic_agreement": rate("topic_ok"), "topic_agreement_lenient_alt_topic": rate("topic_ok_lenient"),
        "intent_agreement": rate("intent_ok"), "severity_exact": rate("severity_ok"),
        "severity_mae": round(sum(c["severity_abs_err"] for c in scored) / len(scored), 4) if scored else None,
        "sentiment_within_0_5": rate("sentiment_ok"),
        "sentiment_mae": round(sum(c["sentiment_abs_err"] for c in scored) / len(scored), 4) if scored else None,
        "quote_exact_substring_rate": None,  # filled by caller with source texts
        "entities_unsupported_total": sum(len(c.get("entities_unsupported", [])) for c in scored),
        "entities_missed_total": sum(len(c.get("entities_missed", [])) for c in scored),
        "needs_review_confusion": {f"human={h},pred={p}": v for (h, p), v in sorted(nr.items(), key=str)},
        "per_topic_human_counts": dict(Counter(c["human_topic"] for c in cases)),
        "topic_confusion": _confusion(scored, "human_topic", "pred_topic", TOPICS),
        "intent_confusion": _confusion(scored, "human_intent", "pred_intent", INTENTS),
        "severity_confusion": _confusion(scored, "human_severity", "pred_severity", (1, 2, 3, 4, 5)),
        "sentiment_tolerance": SENTIMENT_TOL,
        "note": "Fifty cases are a small diagnostic sample, not a population accuracy estimate.",
    }
    return results, cases


def _confusion(xs, hk, pk, labels):
    m = {str(h): {str(p): 0 for p in labels} for h in labels}
    for c in xs:
        m[str(c[hk])][str(c[pk])] += 1
    return m


def write_outputs(out_dir, results, cases):
    write_json_atomic(out_dir / "eval_results.json", results)
    cols = ["review_id", "prediction_status", "ambiguous", "human_topic", "pred_topic", "alt_topic", "topic_ok",
            "human_intent", "pred_intent", "intent_ok", "human_severity", "pred_severity", "severity_ok",
            "human_sentiment", "pred_sentiment", "sentiment_ok", "human_needs_review", "pred_needs_review",
            "entities_unsupported", "entities_missed", "quote_word_overlap", "human_quote", "pred_quote", "notes"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for c in cases:
        w.writerow({k: (";".join(v) if isinstance(v, list) else v) for k, v in c.items()})
    write_text_atomic(out_dir / "per_case.csv", buf.getvalue())
    L = ["# Golden-50 evaluation", "", f"Predeclared: sentiment tolerance ±{SENTIMENT_TOL}; missing/quarantined = incorrect.", "",
         "| metric | value |", "|---|---|"]
    for k in ("n", "completed_predictions", "missing_or_quarantined", "ambiguous_cases", "topic_agreement",
              "topic_agreement_lenient_alt_topic", "intent_agreement", "severity_exact", "severity_mae",
              "sentiment_within_0_5", "sentiment_mae", "quote_exact_substring_rate", "entities_unsupported_total",
              "entities_missed_total"):
        L.append(f"| {k} | {results[k]} |")
    for name in ("topic_confusion", "intent_confusion", "severity_confusion"):
        m = results[name]
        labels = list(m)
        L += ["", f"### {name.replace('_', ' ')} (rows = human, columns = pipeline)", "",
              "| human \\ pred | " + " | ".join(labels) + " |", "|---" * (len(labels) + 1) + "|"]
        L += [f"| {h} | " + " | ".join(str(m[h][p]) or "" for p in labels) + " |" for h in labels]
    L += ["", f"needs_review (human vs predicted): {results['needs_review_confusion']}", "",
          "## Disagreements", "", "| review_id | field | human | pipeline | human note |", "|---|---|---|---|---|"]
    for c in cases:
        for f, hk, pk in (("topic", "human_topic", "pred_topic"), ("intent", "human_intent", "pred_intent"),
                          ("severity", "human_severity", "pred_severity")):
            if not c.get(f"{f}_ok"):
                L.append(f"| `{c['review_id']}` | {f} | {c[hk]} | {c.get(pk, c['prediction_status'])} | {c['notes'][:80]} |")
    write_text_atomic(out_dir / "eval_report.md", "\n".join(L) + "\n")
