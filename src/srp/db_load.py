"""Load a workspace's saved outputs into Supabase Postgres (no model calls). Replaces all business rows atomically
in one transaction, so the dashboard never sees a half-loaded state."""

import csv
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from srp.paths import ROOT
from srp.rank import AREA
from srp.workspace import open_workspace


def _rows(con, issue_of):
    q = """
        SELECT r.review_id, r.source_sha256, r.review_timestamp, r.review_rating, r.app_version,
               rec.status, rec.reason, e.fields_json, e.cache_source_id
        FROM reviews r JOIN records rec USING(review_id) LEFT JOIN enriched e USING(review_id)
        WHERE rec.status != 'pending' AND COALESCE(e.synthetic, 0) = 0"""
    for rid, ssha, ts, rating, ver, status, reason, fj, cache_src in con.execute(q):
        f = json.loads(fj) if fj else {}
        topic = f.get("topic")
        yield (rid, ssha, ts or None, (ts or "")[:7] or None, int(rating) if rating and rating.isdigit() else None,
               ver or None, status, reason, topic, AREA.get(topic) if topic else None, f.get("intent"),
               f.get("sentiment"), f.get("severity"), f.get("entities"), f.get("evidence_quote"), f.get("needs_review"),
               issue_of.get(rid), cache_src)


def monthly_trend(con, issue_of):
    """Complaint share by month with denominators (first and last months are partial)."""
    m = defaultdict(Counter)
    for ts, fj in con.execute("""SELECT r.review_timestamp, e.fields_json FROM reviews r JOIN enriched e USING(review_id)
                                 WHERE e.synthetic=0"""):
        f = json.loads(fj)
        c = m[ts[:7]]
        c["completed"] += 1
        if f["intent"] in ("complaint", "cancellation"):
            c["complaints"] += 1
            c["area:" + AREA[f["topic"]]] += 1
    return [{"month": k, **dict(v)} for k, v in sorted(m.items())]


def load(ws, db_url=None):
    import psycopg

    ws = Path(ws)
    con = open_workspace(ws)
    db_url = db_url or os.environ["SUPABASE_DB_URL"]
    with open(ws / "group" / "membership.csv", encoding="utf-8", newline="") as f:
        membership = [(r["issue_id"], r["review_id"]) for r in csv.DictReader(f)]
    issue_of = {rid: iid for iid, rid in membership}
    with open(ws / "rank" / "ranking.csv", encoding="utf-8", newline="") as f:
        ranking = list(csv.DictReader(f))
    issues_meta = {i["issue_id"]: i for i in json.loads((ws / "group" / "issues.json").read_text())["issues"]}
    agg = json.loads((ws / "rank" / "aggregates.json").read_text())
    memo = json.loads((ws / "memo" / "memo.json").read_text())
    check = json.loads((ws / "memo" / "check.json").read_text())
    with open(ws / "memo" / "claims_all.csv", encoding="utf-8", newline="") as f:
        claims = list(csv.DictReader(f))
    summary = json.loads((ws / "run_summary.json").read_text())
    verify = json.loads((ws / "verify" / "report.json").read_text()) if (ws / "verify" / "report.json").exists() else {}
    golden = ROOT / "evals" / "golden" / "eval_results.json"
    meta = dict(con.execute("SELECT key, value FROM meta").fetchall())

    info = {
        "run": {"label_config": con.execute("SELECT label_config FROM enriched LIMIT 1").fetchone()[0],
                "workspace": str(ws), "input": summary.get("input"), "input_sha256": meta.get("input_sha256"),
                "profile": json.loads(meta.get("profile", "{}")), "wall_seconds": summary.get("wall_seconds"),
                "ledger": summary.get("ledger"), "ranking_sha256": summary.get("ranking_sha256"),
                "ended_at": summary.get("ended_at")},
        "aggregates": agg,
        "monthly": monthly_trend(con, issue_of),
        "verification": {k: v for k, v in verify.items() if not isinstance(v, dict) or k in ("by_enricher_topic", "non_latin")},
        "golden_eval": json.loads(golden.read_text()) if golden.exists() else None,
    }
    with psycopg.connect(db_url, connect_timeout=20) as pg:
        pg.execute((ROOT / "db" / "schema.sql").read_text())
        with pg.transaction():
            for t in ("issues", "claims", "recommendations", "reviews_enriched", "run_info"):
                pg.execute(f"truncate {t} restart identity")  # reclaims space immediately (delete leaves dead rows)
            with pg.cursor() as cur:
                with cur.copy("COPY reviews_enriched FROM STDIN") as cp:
                    for row in _rows(con, issue_of):
                        cp.write_row(row)
            pg.cursor().executemany(
                "insert into issues values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                [(r["issue_id"], int(r["rank"]), r["issue_id"].split("/")[0], r["issue_id"].split("/", 1)[1],
                  AREA[r["issue_id"].split("/")[0]], issues_meta.get(r["issue_id"], {}).get("name"),
                  issues_meta.get(r["issue_id"], {}).get("description"), int(r["complaint_count"]), int(r["severity_sum"]),
                  r["mean_severity"], int(r["priority_score"]), issues_meta.get(r["issue_id"], {}).get("example_ids"))
                 for r in ranking])
            pg.cursor().executemany("insert into claims values (%s,%s,%s,%s,%s)",
                                    [(c["claim_id"], c["issue_id"], c["metric"], c["value"], c["source"]) for c in claims])
            rend = memo["rendered"]
            pg.execute("""insert into recommendations (run_id, generator, recommended_area, headline, memo_markdown, items,
                          evidence, check_status) values (%s,%s,%s,%s,%s,%s,%s,%s)""",
                       (str(ws), check["memo_config"], rend["recommended_area"], rend["headline"], rend["memo_markdown"],
                        json.dumps(rend["recommendations"]), json.dumps(memo["evidence"]), check["status"]))
            pg.cursor().executemany("insert into run_info values (%s,%s)",
                                    [(k, json.dumps(v, ensure_ascii=False)) for k, v in info.items()])
        counts = {t: pg.execute(f"select count(*) from {t}").fetchone()[0]
                  for t in ("reviews_enriched", "issues", "claims", "recommendations", "run_info")}
        size = pg.execute("select pg_size_pretty(pg_database_size(current_database()))").fetchone()[0]
    return {"loaded": counts, "database_size": size}
