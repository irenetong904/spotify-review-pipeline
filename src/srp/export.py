"""Standardized grading/ export (GRADING_CONTRACT.md). Offline: reads saved workspace outputs only.

Exact-text provenance: within each identical-text group, the 'original' is the ID that has model-call evidence
(a model call in this workspace, or the result-cache source ID whose call is in an earlier dev workspace with the
same label_config). Every other ID in the group gets cache_source_id -> that original (direct, no chains).
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

from srp.contract import VERSION, file_sha
from srp.enrich import export_records
from srp.io_atomic import write_json_atomic, write_text_atomic
from srp.paths import ROOT
from srp.workspace import open_cache, open_workspace

ROLES = {"enrich", "verify", "group", "memo"}
CALL_FIELDS = ("request_id", "role", "review_ids", "model", "phase", "outcome", "label_config", "input_tokens",
               "output_tokens")


def normalize_provenance(con, cache, records):
    rows = {r[0]: r[1:] for r in con.execute("""
        SELECT r.review_id, r.text_sha256, r.row_order, e.origin, e.label_config
        FROM reviews r JOIN enriched e USING(review_id)""")}
    groups = {}
    for rec in records:
        if rec["status"] == "completed":
            groups.setdefault(rows[rec["review_id"]][0], []).append(rec)
    stats = {"groups": len(groups), "originals_from_model": 0, "originals_from_dev_cache": 0, "no_call_evidence": 0}
    for tsha, members in groups.items():
        by_id = {m["review_id"]: m for m in members}
        model_ids = sorted((rows[i][1], i) for i in by_id if rows[i][2] == "model")
        original = None
        if model_ids:
            original = model_ids[0][1]
            stats["originals_from_model"] += 1
        else:
            src = cache.execute("SELECT source_review_id FROM results WHERE kind='enrich' AND text_sha256=? AND config=?",
                                (tsha, members[0]["label_config"])).fetchone()
            if src and src[0] in by_id:
                original = src[0]
                stats["originals_from_dev_cache"] += 1
            else:
                original = min(by_id, key=lambda i: rows[i][1])
                stats["no_call_evidence"] += 1
        for rid, m in by_id.items():
            m.pop("cache_source_id", None)
            if rid != original:
                m["cache_source_id"] = original
    return stats


def collect_calls(ws, dev_workspaces, label_config, original_ids):
    out, seen = [], set()

    def add(c, source):
        if c.get("role") not in ROLES or c["request_id"] in seen:
            return
        seen.add(c["request_id"])
        ev = {k: c.get(k) for k in CALL_FIELDS}
        if c["role"] != "enrich":
            ev.pop("phase")
        ev.update({k: c[k] for k in ("run_id", "attempt", "purpose", "latency_ms", "cost_usd", "http_status", "error",
                                     "effort", "inputs", "issue_id") if c.get(k) is not None})
        ev["source_workspace"] = source
        out.append(ev)

    for line in (Path(ws) / "calls.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            add(json.loads(line), str(ws))
    for dev in dev_workspaces:  # only enrich calls under the same label_config that back an exported original
        p = Path(dev) / "calls.jsonl"
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            c = json.loads(line) if line.strip() else {}
            if (c.get("role") == "enrich" and c.get("label_config") == label_config
                    and set(c.get("review_ids", [])) & original_ids):
                add(c, str(dev))
    return out


def export_grading(*, ws, input_csv, cache_path, out_dir, dev_workspaces=(), checkpoint_before=None,
                   checkpoint_after=None, allow_multi_issue=False):
    ws, out = Path(ws), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    con = open_workspace(ws)
    cache = open_cache(cache_path)
    records, pending = export_records(con)
    if pending:  # never silently drop source IDs: unresolved rows are exported as quarantined with a reason
        ssha = dict(con.execute("SELECT review_id, source_sha256 FROM reviews"))
        records += [{"review_id": rid, "source_sha256": ssha[rid], "status": "quarantined",
                     "reason": "unresolved_pending_after_run_stop"} for rid in pending]
    for r in records:
        r.pop("attempt_count", None)  # retry details stay in run logs (contract)
        r.pop("synthetic", None)
    prov = normalize_provenance(con, cache, records)
    lcs = {r["label_config"] for r in records if r["status"] == "completed"}
    originals = {r["review_id"] for r in records if r["status"] == "completed" and "cache_source_id" not in r}
    calls = collect_calls(ws, dev_workspaces, next(iter(lcs)) if len(lcs) == 1 else None, originals)

    write_json_atomic(out / "run.json", {"version": VERSION, "analysis_count": len(records),
                                         "analysis_sha256": file_sha(input_csv),
                                         "classification_input_fields": ["review_text"],
                                         "allow_multi_issue": allow_multi_issue})
    write_text_atomic(out / "records.jsonl", "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    write_text_atomic(out / "calls.jsonl", "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in calls))
    shutil.copy(ws / "group" / "membership.csv", out / "membership.csv")
    shutil.copy(ws / "rank" / "ranking.csv", out / "ranking.csv")
    shutil.copy(ws / "memo" / "claims.csv", out / "claims.csv")
    for src, name in ((checkpoint_before, "checkpoint_before.json"), (checkpoint_after, "checkpoint_after.json")):
        if src:
            shutil.copy(src, out / name)
    subprocess.run([sys.executable, str(ROOT / "tools" / "check_submission.py"), "profile", "--full",
                    str(_full_csv()), "--out", str(out / "ingestion.json")],  # always the full-file profile
                   check=True)
    return {"records": len(records), "pending_not_exported": len(pending), "calls": len(calls),
            "label_configs": sorted(lcs), "provenance": prov}


def _full_csv():
    from srp.paths import FULL_CSV

    return FULL_CSV
