"""A workspace = one pipeline run over one input CSV: SQLite state + saved stage handoffs.

<workspace>/state.db      reviews, texts, records (pending/completed/quarantined + attempt_count), enriched, sessions
<workspace>/calls.jsonl   one line per model-call attempt, all roles (append-only)
<workspace>/<stage>/...   handoff files written atomically by each stage
A separate result-cache DB (exact text + label_config) can be shared across workspaces.
"""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from srp.contract import file_sha
from srp.ingest import SCHEMA, load_source

EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS enriched (
  review_id TEXT PRIMARY KEY REFERENCES records(review_id),
  label_config TEXT NOT NULL, fields_json TEXT NOT NULL, reasons_json TEXT NOT NULL,
  origin TEXT NOT NULL CHECK (origin IN ('model','result_cache','exact_text_reuse')),
  cache_source_id TEXT, request_id TEXT, session_id TEXT NOT NULL, completed_at TEXT NOT NULL,
  synthetic INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY, stage TEXT NOT NULL, phase TEXT, started_at TEXT NOT NULL,
  ended_at TEXT, stop_reason TEXT, stats_json TEXT
);
"""

CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
  kind TEXT NOT NULL, text_sha256 TEXT NOT NULL, config TEXT NOT NULL,
  value_json TEXT NOT NULL, source_review_id TEXT, request_id TEXT, run_ref TEXT, created_at TEXT NOT NULL,
  PRIMARY KEY (kind, text_sha256, config)
);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def open_workspace(ws_dir, input_csv=None):
    """Create (from input_csv) or reopen a workspace. Reopening checks the input checksum is unchanged."""
    ws = Path(ws_dir)
    db = ws / "state.db"
    if db.exists():
        con = sqlite3.connect(db, check_same_thread=False)
        if input_csv is not None:
            stored = dict(con.execute("SELECT key, value FROM meta").fetchall())
            if stored.get("input_sha256") != file_sha(input_csv):
                raise SystemExit(f"{ws} was built from a different input (checksum mismatch); use a new workspace")
        con.executescript(EXTRA_SCHEMA)
        return con
    if input_csv is None:
        raise SystemExit(f"No workspace at {ws}; pass --input to create it")
    ws.mkdir(parents=True, exist_ok=True)
    tmp = ws / "state.db.tmp"
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)
    con.executescript(EXTRA_SCHEMA)
    counts, texts, _ = load_source(con, Path(input_csv))
    meta = {"input_path": str(input_csv), "input_sha256": file_sha(input_csv), "created_at": now(),
            "profile": json.dumps(dict(counts, distinct_nonempty_texts=len(texts)))}
    con.executemany("INSERT INTO meta VALUES (?,?)", list(meta.items()))
    con.commit()
    con.close()
    tmp.rename(db)
    return open_workspace(ws_dir)


def open_cache(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, check_same_thread=False)
    con.executescript(CACHE_SCHEMA)
    return con


def cache_get(cache, kind, text_sha256, config):
    row = cache.execute("SELECT value_json, source_review_id, request_id, run_ref FROM results "
                        "WHERE kind=? AND text_sha256=? AND config=?", (kind, text_sha256, config)).fetchone()
    if not row:
        return None
    return {"value": json.loads(row[0]), "source_review_id": row[1], "request_id": row[2], "run_ref": row[3]}


def cache_put(cache, kind, text_sha256, config, value, source_review_id, request_id, run_ref):
    cache.execute("INSERT OR IGNORE INTO results VALUES (?,?,?,?,?,?,?,?)",
                  (kind, text_sha256, config, json.dumps(value, ensure_ascii=False, sort_keys=True),
                   source_review_id, request_id, run_ref, now()))


class CallLog:
    """Thread-safe append-only JSONL call log (never contains credentials)."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, event):
        line = json.dumps(event, ensure_ascii=False, sort_keys=True)
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()

    def read(self):
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]


class SpendLedger:
    """Shared across workers: reserve worst-case cost before dispatch, settle with actual usage after.
    Admission stops when spent + reserved + next reservation would exceed the cap."""

    def __init__(self, cap_usd, spent_usd=0.0):
        self.cap, self.spent, self.reserved = cap_usd, spent_usd, 0.0
        self._lock = threading.Lock()

    def reserve(self, amount):
        with self._lock:
            if self.spent + self.reserved + amount > self.cap:
                return False
            self.reserved += amount
            return True

    def settle(self, reserved, actual):
        with self._lock:
            self.reserved -= reserved
            self.spent += actual

    def snapshot(self):
        with self._lock:
            return {"cap_usd": self.cap, "spent_usd": round(self.spent, 8), "reserved_usd": round(self.reserved, 8)}
