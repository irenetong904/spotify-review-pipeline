"""Rank stage (code only, zero model calls): baseline priority = complaint_count x mean_severity = severity_sum.
Sorted by priority_score desc, then issue_id asc. Means to 6 dp with Decimal ROUND_HALF_UP (contract)."""

import csv
import io
import json
from collections import Counter, defaultdict

from srp.contract import mean_string
from srp.io_atomic import write_json_atomic, write_text_atomic

AREA = {"access": "Access", "usability": "Usability", "playback": "Playback", "downloads": "Playback",
        "billing": "Billing/support", "support": "Billing/support",
        "catalog": "Outside the four areas", "other": "Outside the four areas"}


def read_membership(path):
    with open(path, encoding="utf-8", newline="") as f:
        return [(r["issue_id"], r["review_id"]) for r in csv.DictReader(f)]


def compute_ranking(severity_by_id, membership):
    members = defaultdict(list)
    seen = set()
    for issue_id, rid in membership:
        if (issue_id, rid) in seen:
            raise ValueError(f"duplicate membership pair {issue_id},{rid}")
        seen.add((issue_id, rid))
        members[issue_id].append(severity_by_id[rid])
    rows = [{"issue_id": i, "complaint_count": len(v), "severity_sum": sum(v),
             "mean_severity": mean_string(sum(v), len(v)), "priority_score": sum(v)} for i, v in members.items()]
    rows.sort(key=lambda r: (-r["priority_score"], r["issue_id"]))
    for n, r in enumerate(rows, 1):
        r["rank"] = n
    return rows


def ranking_csv(rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    cols = ["rank", "issue_id", "complaint_count", "severity_sum", "mean_severity", "priority_score"]
    w.writerow(cols)
    for r in rows:
        w.writerow([r[c] for c in cols])
    return buf.getvalue()


def run_rank(con, ws):
    sev = {rid: s for rid, s in con.execute(
        "SELECT review_id, json_extract(fields_json,'$.severity') FROM enriched WHERE synthetic=0")}
    membership = read_membership(ws / "group" / "membership.csv")
    rows = compute_ranking(sev, membership)
    text = ranking_csv(rows)
    write_text_atomic(ws / "rank" / "ranking.csv", text)
    agg = aggregates(con, rows)
    write_json_atomic(ws / "rank" / "aggregates.json", agg)
    return rows, agg


def aggregates(con, ranking):
    status = dict(con.execute("SELECT status, COUNT(*) FROM records GROUP BY status").fetchall())
    reasons = dict(con.execute("SELECT reason, COUNT(*) FROM records WHERE status='quarantined' GROUP BY reason").fetchall())
    recs = con.execute("""SELECT json_extract(fields_json,'$.topic'), json_extract(fields_json,'$.intent'),
                                 json_extract(fields_json,'$.severity'), json_extract(fields_json,'$.needs_review'), origin
                          FROM enriched WHERE synthetic=0""").fetchall()
    topic_intent = Counter((t, i) for t, i, *_ in recs)
    area = defaultdict(lambda: {"complaint_count": 0, "severity_sum": 0, "topics": set()})
    for t, i, s, *_ in recs:
        if i in ("complaint", "cancellation"):
            a = area[AREA[t]]
            a["complaint_count"] += 1
            a["severity_sum"] += s
            a["topics"].add(t)
    total_c = sum(a["complaint_count"] for a in area.values())
    areas = []
    for name, a in sorted(area.items(), key=lambda kv: (-kv[1]["severity_sum"], kv[0])):
        areas.append({"area": name, "complaint_count": a["complaint_count"], "severity_sum": a["severity_sum"],
                      "mean_severity": mean_string(a["severity_sum"], a["complaint_count"]),
                      "share_of_complaints": mean_string(a["complaint_count"], total_c) if total_c else None,
                      "topics": sorted(a["topics"])})
    periods = comparable_periods(con)
    return {
        "comparable_periods": periods,
        "record_status_counts": status, "quarantine_reasons": reasons,
        "completed_non_synthetic": len(recs),
        "origin_counts": dict(Counter(r[4] for r in recs)),
        "needs_review_count": sum(1 for r in recs if r[3]),
        "intent_counts": dict(Counter(i for _, i, *_ in recs)),
        "topic_counts": dict(Counter(t for t, *_ in recs)),
        "topic_intent_counts": {f"{t}|{i}": n for (t, i), n in sorted(topic_intent.items())},
        "complaint_or_cancellation_total": total_c,
        "areas": areas,
        "area_mapping": AREA,
        "top_issues": ranking[:15],
        "issue_count": len(ranking),
        "method": "areas: playback+downloads=Playback, billing+support=Billing/support; complaint+cancellation only",
    }


def comparable_periods(con):
    """Same calendar months in the first and last year of the window, excluding the partial first/last months.
    Returns complaint counts by area with denominators, for a like-for-like trend (not a causal claim)."""
    rows = con.execute("""SELECT substr(r.review_timestamp,1,7), json_extract(e.fields_json,'$.topic'),
                                 json_extract(e.fields_json,'$.intent')
                          FROM reviews r JOIN enriched e USING(review_id) WHERE e.synthetic=0""").fetchall()
    months = sorted({m for m, *_ in rows})
    if len(months) < 3:
        return []
    full = months[1:-1]
    y0, y1 = full[0][:4], full[-1][:4]
    common = sorted({m[5:] for m in full if m[:4] == y0} & {m[5:] for m in full if m[:4] == y1})
    if y0 == y1 or not common:
        return []
    out = []
    for y in (y0, y1):
        c = Counter()
        for m, topic, intent in rows:
            if m[:4] == y and m[5:] in common:
                c["classified"] += 1
                if intent in ("complaint", "cancellation"):
                    c["complaints"] += 1
                    c[AREA[topic]] += 1
                if intent == "cancellation":
                    c["cancellation"] += 1
        out.append({"period": f"{y} months {common[0]}-{common[-1]}", "classified": c["classified"],
                    "complaints": c["complaints"], "cancellation": c["cancellation"],
                    "complaint_share": mean_string(c["complaints"], c["classified"]) if c["classified"] else None,
                    "area_complaints": {a: c[a] for a in sorted(set(AREA.values()))}})
    return out


def ranking_hash(ws):
    import hashlib

    return hashlib.sha256((ws / "rank" / "ranking.csv").read_bytes()).hexdigest()


def dump(o):
    return json.dumps(o, indent=2)


def rerank_from_export(grading_dir):
    """Offline, from committed files only: rebuild the baseline ranking from grading/records.jsonl(.gz) and
    grading/membership.csv, then compare with grading/ranking.csv and grading/claims.csv. No workspace, no model."""
    import gzip
    from pathlib import Path

    g = Path(grading_dir)
    path = g / "records.jsonl" if (g / "records.jsonl").exists() else g / "records.jsonl.gz"
    opener = gzip.open if path.suffix == ".gz" else open
    sev = {}
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["status"] == "completed" and r["intent"] in ("complaint", "cancellation"):
                sev[r["review_id"]] = r["severity"]
    rows = compute_ranking(sev, read_membership(g / "membership.csv"))
    rebuilt = ranking_csv(rows)
    saved = (g / "ranking.csv").read_text(encoding="utf-8")
    by_issue = {r["issue_id"]: r for r in rows}
    with open(g / "claims.csv", encoding="utf-8", newline="") as f:
        claims = list(csv.DictReader(f))
    claim_mismatch = [c["claim_id"] for c in claims if str(by_issue.get(c["issue_id"], {}).get(c["metric"])) != c["value"]]
    return {"source": str(path), "complaint_records": len(sev), "issues": len(rows),
            "ranking_identical_to_saved": rebuilt == saved, "claims_checked": len(claims),
            "claim_mismatches": claim_mismatch, "top3": [(r["rank"], r["issue_id"], r["priority_score"]) for r in rows[:3]]}
