"""Assemble the committed results/ folder from a (large, uncommitted) workspace. Offline, deterministic.
File names follow the assignment's "Save Your Results" list."""

import csv
import hashlib
import io
import json
import shutil
import subprocess
from pathlib import Path

from srp.claude_client import ROLE_MODEL
from srp.contract import file_sha
from srp.io_atomic import write_json_atomic, write_text_atomic
from srp.paths import ROOT
from srp.rubric import label_config
from srp.workspace import open_workspace


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def publish(ws, out_dir, input_csv):
    ws, out = Path(ws), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    con = open_workspace(ws)
    copies = {
        "memo/memo.md": "memo.md", "memo/memo.json": "memo.json", "memo/claims.csv": "claims.csv",
        "memo/claims_all.csv": "claims_all.csv", "memo/check.json": "memo_check.json",
        "memo/evidence_pack.json": "evidence_pack.json", "rank/ranking.csv": "ranking.csv",
        "rank/aggregates.json": "aggregates.json", "group/issues.json": "issues.json",
        "verify/report.json": "verify_report.json", "verify/disagreements.csv": "verify_disagreements.csv",
        "verify/verifier_labels.jsonl": "verifier_labels.jsonl", "enrich/quarantine.jsonl": "quarantine.jsonl",
        "run_summary.json": "run_summary.json",
    }
    for src, dst in copies.items():
        shutil.copy(ws / src, out / dst)

    agg = json.loads((ws / "rank" / "aggregates.json").read_text())
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["table", "key", "complaint_count", "severity_sum", "mean_severity", "share_of_complaints", "count"])
    for a in agg["areas"]:
        w.writerow(["area", a["area"], a["complaint_count"], a["severity_sum"], a["mean_severity"], a["share_of_complaints"], ""])
    for k, n in sorted(agg["topic_intent_counts"].items()):
        w.writerow(["topic|intent", k, "", "", "", "", n])
    for k, n in sorted(agg["record_status_counts"].items()):
        w.writerow(["record_status", k, "", "", "", "", n])
    write_text_atomic(out / "aggregates.csv", buf.getvalue())

    sessions = con.execute("SELECT session_id, stage, phase, started_at, ended_at, stop_reason, stats_json "
                           "FROM sessions ORDER BY started_at").fetchall()
    write_text_atomic(out / "run_log.jsonl", "".join(json.dumps(
        {"session_id": s, "stage": st, "phase": ph, "started_at": a, "ended_at": b, "stop_reason": r,
         "stats": json.loads(j) if j else None}, ensure_ascii=False) + "\n" for s, st, ph, a, b, r, j in sessions))

    meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    write_json_atomic(out / "data_manifest.json", {
        "source": {"file": Path(input_csv).name, "sha256": file_sha(input_csv), "bytes": Path(input_csv).stat().st_size,
                   "url": "https://www.kaggle.com/datasets/bwandowando/3-4-million-spotify-google-store-reviews (v2, CC0; course extract)"},
        "profile": json.loads(meta["profile"]),
        "code_version_git": git,
        "models": {"enrich": "jev-1.13.0 (TypeSafe System One, pinned)", "verify/group/memo": ROLE_MODEL},
        "configs": {"label_config": label_config(),
                    "verify": json.loads((ws / "verify" / "report.json").read_text()).get("verify_config"),
                    "group": json.loads((ws / "group" / "issues.json").read_text()).get("group_config"),
                    "memo": json.loads((ws / "memo" / "check.json").read_text()).get("memo_config")},
        "prompts_and_rubric": {p: _sha(ROOT / p) for p in ("rubric/rubric_v1.yaml", "rubric/taxonomy_v1.yaml",
                                                            "src/srp/jev.py", "src/srp/verify.py", "src/srp/group.py",
                                                            "src/srp/memo.py", "config/run_config.yaml")},
        "outputs_sha256": {p.name: _sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != "data_manifest.json"},
        "grading_export": "grading/ (records.jsonl.gz, calls.jsonl.gz, membership.csv, ranking.csv, claims.csv, ...)",
    })
    shutil.copy(ROOT / "reports" / "ingestion_report.json", out / "ingestion_report.json")
    return sorted(p.name for p in out.iterdir())
