"""Ingest + profile the full CSV into a local SQLite state store. No model calls.

Outputs:
  data/processed/pipeline.db   reviews, texts (exact-text dedup map), records (pending/quarantined), samples
  reports/ingestion_report.json
The database is built in a temp file and renamed only if every expected count matches.
"""

import hashlib
import json
import os
import sqlite3
from collections import Counter

from srp import paths
from srp.contract import csv_rows, file_sha, row_sha
from srp.io_atomic import write_json_atomic

EXPECTED_DISTINCT_NONEMPTY_TEXTS = 484_189  # from the assignment brief

SCHEMA = """
CREATE TABLE reviews (
  review_id TEXT PRIMARY KEY, row_order INTEGER NOT NULL,
  review_text TEXT NOT NULL, review_rating TEXT NOT NULL, review_likes TEXT NOT NULL,
  app_version TEXT NOT NULL, review_timestamp TEXT NOT NULL,
  source_sha256 TEXT NOT NULL, text_sha256 TEXT NOT NULL, is_empty INTEGER NOT NULL
);
CREATE INDEX reviews_text ON reviews(text_sha256);
CREATE TABLE texts (
  text_sha256 TEXT PRIMARY KEY, canonical_review_id TEXT NOT NULL, n_ids INTEGER NOT NULL
);
CREATE TABLE records (
  review_id TEXT PRIMARY KEY REFERENCES reviews(review_id),
  status TEXT NOT NULL CHECK (status IN ('pending','completed','quarantined')),
  reason TEXT,
  attempt_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE samples (
  sample TEXT NOT NULL, review_id TEXT NOT NULL REFERENCES reviews(review_id),
  PRIMARY KEY (sample, review_id)
);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def text_sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_source(con, csv_path):
    """Parse any input CSV (multiline-safe), insert reviews/texts/records. Empty texts are quarantined.
    Returns (counts, texts {text_sha: [canonical_id, n]}, sources {review_id: source_sha256})."""
    counts = Counter(records=0, duplicate_review_ids=0, empty_review_text=0, missing_app_version=0)
    seen, texts, sources = set(), {}, {}
    rows = []
    for order, row in enumerate(csv_rows(csv_path)):
        rid = row["review_id"]
        counts["records"] += 1
        if rid in seen:
            counts["duplicate_review_ids"] += 1
            continue  # keep the first occurrence; duplicates are reported, never double-counted
        seen.add(rid)
        empty = not row["review_text"].strip()  # same rule as check_submission.py
        counts["empty_review_text"] += empty
        counts["missing_app_version"] += not row["app_version"].strip()
        tsha = text_sha(row["review_text"])
        ssha = row_sha(row)
        sources[rid] = ssha
        if not empty:
            entry = texts.setdefault(tsha, [rid, 0])
            entry[1] += 1
        rows.append((rid, order, row["review_text"], row["review_rating"], row["review_likes"],
                     row["app_version"], row["review_timestamp"], ssha, tsha, int(empty)))
    con.executemany("INSERT INTO reviews VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    con.executemany("INSERT INTO texts VALUES (?,?,?)", [(k, v[0], v[1]) for k, v in texts.items()])
    con.executemany(
        "INSERT INTO records (review_id, status, reason, attempt_count) VALUES (?,?,?,0)",
        [(r[0], "quarantined", "empty_review_text") if r[9] else (r[0], "pending", None) for r in rows],
    )
    return counts, texts, sources


def run_ingest(full_csv=None, db_path=None, report_path=None, manifest_path=None, samples=None):
    full_csv = full_csv or paths.FULL_CSV
    db_path = db_path or paths.DB_PATH
    report_path = report_path or paths.REPORTS_DIR / "ingestion_report.json"
    manifest_path = manifest_path or paths.MANIFEST
    samples = paths.SAMPLES if samples is None else samples

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {
        "records": manifest["profile"]["records"],
        "duplicate_review_ids": manifest["profile"]["duplicate_review_ids"],
        "empty_review_text": manifest["profile"]["empty_review_text"],
        "missing_app_version": manifest["profile"]["missing_app_version"],
        "distinct_nonempty_texts": EXPECTED_DISTINCT_NONEMPTY_TEXTS,
        "file_sha256": manifest["files"][full_csv.name]["sha256"],
    }

    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = db_path.with_suffix(".db.tmp")
    tmp_path.unlink(missing_ok=True)
    con = sqlite3.connect(tmp_path)
    con.executescript(SCHEMA)
    counts, texts, sources = load_source(con, full_csv)

    sample_report = {}
    for name, path in samples.items():
        ids, mismatched, absent = [], [], []
        for row in csv_rows(path):
            rid = row["review_id"]
            if rid not in sources:
                absent.append(rid)
            elif row_sha(row) != sources[rid]:  # row_sha reads only the six source fields
                mismatched.append(rid)
            ids.append(rid)
        con.executemany("INSERT INTO samples VALUES (?,?)", [(name, rid) for rid in ids])
        sample_report[name] = {"file": path.name, "file_sha256": file_sha(path), "rows": len(ids),
                               "absent_from_full": len(absent), "row_hash_mismatches": len(mismatched)}

    file_sha256 = file_sha(full_csv)
    observed = dict(counts, distinct_nonempty_texts=len(texts), file_sha256=file_sha256)
    checks = {k: {"expected": expected[k], "observed": observed[k], "ok": expected[k] == observed[k]} for k in expected}
    for name, s in sample_report.items():
        ok = s["absent_from_full"] == 0 and s["row_hash_mismatches"] == 0 \
            and s["file_sha256"] == manifest["files"].get(s["file"], {}).get("sha256")
        checks[f"sample_{name}"] = {"expected": "present, hash-matched", "observed": s, "ok": ok}
    status_counts = dict(con.execute("SELECT status, COUNT(*) FROM records GROUP BY status").fetchall())
    golden_ids = {r[0] for r in con.execute("SELECT review_id FROM samples WHERE sample='golden_50'")}
    dev_ids = {r[0] for r in con.execute("SELECT review_id FROM samples WHERE sample!='golden_50'")}
    checks["golden_disjoint_from_dev"] = {"expected": 0, "observed": len(golden_ids & dev_ids),
                                          "ok": not (golden_ids & dev_ids)}

    all_ok = all(c["ok"] for c in checks.values())
    report = {
        "input": str(full_csv.name),
        "file_sha256": file_sha256,
        "checks": checks,
        "all_checks_passed": all_ok,
        "record_status_counts": status_counts,
        "accounting": {"pending": status_counts.get("pending", 0),
                       "quarantined_empty_review_text": status_counts.get("quarantined", 0),
                       "total": sum(status_counts.values())},
        "distinct_nonempty_texts": len(texts),
        "ids_reusing_exact_text": counts["records"] - counts["empty_review_text"] - len(texts),
        "max_ids_per_text": max(v[1] for v in texts.values()),
        "note": "Missing app_version is profiled but is not an exclusion reason.",
    }
    con.execute("INSERT INTO meta VALUES ('ingestion_report', ?)", (json.dumps(report, sort_keys=True),))
    con.commit()
    con.close()
    write_json_atomic(report_path, report)
    if not all_ok:
        tmp_path.unlink(missing_ok=True)
        failed = [k for k, c in checks.items() if not c["ok"]]
        raise SystemExit(f"Ingestion checks failed: {failed}. Database not promoted; see {report_path}")
    os.replace(tmp_path, db_path)
    return report
