import csv
import json
import sqlite3

import pytest

from srp import paths
from srp.contract import row_sha
from srp.ingest import run_ingest

FIELDS = ["review_id", "review_text", "review_rating", "review_likes", "app_version", "review_timestamp"]


def write_csv(path, rows, extra=()):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS + list(extra))
        w.writeheader()
        for r in rows:
            w.writerow(r)


def row(rid, text, version="8.8.0"):
    return {"review_id": rid, "review_text": text, "review_rating": "5", "review_likes": "0",
            "app_version": version, "review_timestamp": "2023-01-01 00:00:00"}


@pytest.fixture
def tiny(tmp_path, monkeypatch):
    import srp.ingest as ingest
    from srp.contract import file_sha

    rows = [row("a", "Great app"), row("b", "Line one\nline two, \"quoted\""), row("c", "   "),
            row("d", "Great app", version=""), row("e", "Crashes")]
    full = tmp_path / "full.csv"
    write_csv(full, rows)
    sample = tmp_path / "s.csv"
    write_csv(sample, [rows[1]])
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "profile": {"records": 5, "duplicate_review_ids": 0, "empty_review_text": 1, "missing_app_version": 1},
        "files": {"full.csv": {"sha256": file_sha(full)}, "s.csv": {"sha256": file_sha(sample)}},
    }))
    monkeypatch.setattr(ingest, "EXPECTED_DISTINCT_NONEMPTY_TEXTS", 3)
    return dict(full_csv=full, db_path=tmp_path / "p.db", report_path=tmp_path / "r.json",
                manifest_path=manifest, samples={"dev": sample})


def test_tiny_ingest_counts_and_quarantine(tiny):
    report = run_ingest(**tiny)
    assert report["all_checks_passed"]
    assert report["accounting"] == {"pending": 4, "quarantined_empty_review_text": 1, "total": 5}
    con = sqlite3.connect(tiny["db_path"])
    assert con.execute("SELECT reason FROM records WHERE review_id='c'").fetchone() == ("empty_review_text",)
    # missing app_version is not an exclusion reason
    assert con.execute("SELECT status FROM records WHERE review_id='d'").fetchone() == ("pending",)
    # exact-text dedup: 'a' is the canonical original for "Great app"
    assert con.execute("SELECT canonical_review_id, n_ids FROM texts t JOIN reviews r ON r.text_sha256=t.text_sha256 "
                       "WHERE r.review_id='d'").fetchone() == ("a", 2)
    # multiline text preserved exactly and hashed like the grader
    text, sha = con.execute("SELECT review_text, source_sha256 FROM reviews WHERE review_id='b'").fetchone()
    assert text == 'Line one\nline two, "quoted"'
    assert sha == row_sha(row("b", text))


def test_count_mismatch_does_not_promote_db(tiny, monkeypatch):
    import srp.ingest as ingest

    monkeypatch.setattr(ingest, "EXPECTED_DISTINCT_NONEMPTY_TEXTS", 999)
    with pytest.raises(SystemExit):
        run_ingest(**tiny)
    assert not tiny["db_path"].exists()


@pytest.mark.skipif(not paths.DB_PATH.exists(), reason="run `python cli.py ingest` first")
def test_real_ingestion_report():
    report = json.loads((paths.REPORTS_DIR / "ingestion_report.json").read_text())
    assert report["all_checks_passed"]
    c = report["checks"]
    assert c["records"]["observed"] == 660_622
    assert c["empty_review_text"]["observed"] == 13
    assert c["missing_app_version"]["observed"] == 159_701
    assert c["duplicate_review_ids"]["observed"] == 0
    assert c["distinct_nonempty_texts"]["observed"] == 484_189
    assert report["accounting"]["pending"] + report["accounting"]["quarantined_empty_review_text"] == 660_622
