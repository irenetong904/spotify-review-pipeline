"""Enrich stage orchestrator (code owns dispatch, state, validation, budget and logs; Jev classifies).

Input : workspace records with status 'pending'
Output: enriched rows + records 'completed'/'quarantined' (state.db), enrich/enriched.jsonl, enrich/quarantine.jsonl
Failure: invalid output -> retry once -> quarantine 'invalid_model_output'; non-retryable 4xx -> quarantine
         'request_rejected_<status>'; 429/529/5xx/timeout -> bounded backoff in the client, record stays pending
Stop  : queue empty | spend cap | --limit reached | Ctrl-C | consecutive call failures | 401
Saves : one SQLite transaction per batch (atomic); resume skips completed IDs (no new calls for them).
"""

import json
import threading
import time
import uuid
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from srp.io_atomic import write_json_atomic, write_text_atomic
from srp.jev import JEV_INPUT_USD_PER_TOKEN, FatalAPIError, InvalidOutput, build_request, parse_answers
from srp.labels import finalize
from srp.rubric import label_config
from srp.workspace import cache_get, cache_put, now

MAX_CONSECUTIVE_CALL_FAILURES = 10


class RateLimiter:
    """Global requests-per-second limiter shared by all workers."""

    def __init__(self, rps):
        self.interval = 1.0 / rps if rps else 0.0
        self._next = 0.0
        self._lock = threading.Lock()

    def wait(self):
        if not self.interval:
            return
        with self._lock:
            t = max(time.monotonic(), self._next)
            self._next = t + self.interval
        time.sleep(max(0.0, t - time.monotonic()))


def _enrich_one(client, limiter, ledger, rid, text, ctx):
    """Runs in a worker thread. Returns a result dict; never touches SQLite."""
    attempts, last_error = 0, None
    for purpose in ("first", "invalid_output_retry"):
        body, sents = build_request(text)
        reserve = len(json.dumps(body, ensure_ascii=False)) * JEV_INPUT_USD_PER_TOKEN  # chars >= tokens: worst case
        if not ledger.reserve(reserve):
            return {"kind": "spend_cap", "attempts": attempts}
        limiter.wait()
        data, info = client.call(body, [rid], {**ctx, "purpose": purpose})
        actual = ((data or {}).get("usage") or {}).get("input_tokens") or 0
        ledger.settle(reserve, actual * JEV_INPUT_USD_PER_TOKEN)
        attempts += info["attempts"]
        if data is None:
            return {"kind": "call_failed", "attempts": attempts, "info": info}
        try:
            return {"kind": "ok", "attempts": attempts, "signals": parse_answers(data, text, sents),
                    "request_id": info["request_id"]}
        except InvalidOutput as e:
            last_error = str(e)
    return {"kind": "invalid", "attempts": attempts, "error": last_error}


def _complete(con, rid, lc, fields, reasons, origin, session_id, request_id=None, cache_source_id=None):
    con.execute("INSERT OR REPLACE INTO enriched (review_id, label_config, fields_json, reasons_json, origin, "
                "cache_source_id, request_id, session_id, completed_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (rid, lc, json.dumps(fields, ensure_ascii=False, sort_keys=True), json.dumps(reasons), origin,
                 cache_source_id, request_id, session_id, now()))
    con.execute("UPDATE records SET status='completed', reason=NULL WHERE review_id=?", (rid,))


def fan_out(con, lc, session_id):
    """Copy validated canonical results to pending rows with identical text (direct cache_source_id).
    If the canonical was quarantined for invalid output, its exact-text duplicates are quarantined too."""
    rows = con.execute("""
        SELECT r.review_id, t.canonical_review_id, rc.status, e.fields_json, e.reasons_json, e.label_config
        FROM records rec JOIN reviews r USING(review_id) JOIN texts t ON t.text_sha256 = r.text_sha256
        JOIN records rc ON rc.review_id = t.canonical_review_id
        LEFT JOIN enriched e ON e.review_id = t.canonical_review_id
        WHERE rec.status='pending' AND r.review_id != t.canonical_review_id AND rc.status != 'pending'""").fetchall()
    n = 0
    for rid, cid, cstatus, fj, rj, clc in rows:
        if cstatus == "completed" and clc == lc:
            _complete(con, rid, lc, json.loads(fj), json.loads(rj), "exact_text_reuse", session_id, cache_source_id=cid)
            n += 1
        elif cstatus == "quarantined":
            con.execute("UPDATE records SET status='quarantined', reason=? WHERE review_id=?",
                        (f"invalid_model_output_exact_text_of_{cid}", rid))
            n += 1
    return n


def run_enrich(con, cache, calllog, client, cfg, *, ledger, workers=1, rps=20, limit=None, stop_event=None,
               retry_quarantined=False):
    lc = label_config()
    thresholds = cfg["thresholds"]
    batch_every = cfg["controls"]["batch_save_every"]
    stop_event = stop_event or threading.Event()
    session_id = "enrich-" + time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
    phase = "resume" if con.execute("SELECT 1 FROM sessions WHERE stage='enrich'").fetchone() else "initial"
    con.execute("INSERT INTO sessions (session_id, stage, phase, started_at) VALUES (?,?,?,?)",
                (session_id, "enrich", phase, now()))
    con.commit()
    t0 = time.monotonic()
    stats = {"session_id": session_id, "phase": phase, "label_config": lc, "workers": workers, "rps_limit": rps,
             "model_completed": 0, "result_cache_hits": 0, "exact_text_reuse": 0, "quarantined": 0,
             "still_pending_after_failures": 0, "attempts": 0}
    stats["exact_text_reuse"] += fan_out(con, lc, session_id)
    con.commit()

    queue = con.execute("""
        SELECT r.review_id, r.review_text, r.text_sha256 FROM records rec JOIN reviews r USING(review_id)
        JOIN texts t ON t.text_sha256 = r.text_sha256
        WHERE rec.status='pending' AND r.review_id = t.canonical_review_id ORDER BY r.row_order""").fetchall()
    stats["queue_at_start"] = len(queue)

    to_call = []
    for rid, text, tsha in queue:  # result-cache lookup happens in code before any dispatch
        hit = cache_get(cache, "enrich", tsha, lc)
        failed = None if (hit or retry_quarantined) else cache_get(cache, "enrich_invalid", tsha, lc)
        if failed:  # same text + same config already failed validation twice: do not pay again
            con.execute("UPDATE records SET status='quarantined', reason=? WHERE review_id=?",
                        (failed["value"]["reason"], rid))
            stats["quarantined_from_failure_cache"] = stats.get("quarantined_from_failure_cache", 0) + 1
        elif hit:
            _complete(con, rid, lc, hit["value"]["fields"], hit["value"]["reasons"], "result_cache", session_id,
                      request_id=hit["request_id"])
            stats["result_cache_hits"] += 1
        else:
            to_call.append((rid, text, tsha))
    con.commit()

    limiter = RateLimiter(rps)
    ctx = {"run_id": session_id, "role": "enrich", "phase": phase, "label_config": lc}
    stop_reason, consecutive_failures, since_commit, dispatched = "queue_empty", 0, 0, 0
    items = iter(to_call)
    inflight = {}

    def handle(item, res):
        nonlocal consecutive_failures, stop_reason
        rid, text, tsha = item
        stats["attempts"] += res.get("attempts", 0)
        con.execute("UPDATE records SET attempt_count = attempt_count + ? WHERE review_id=?", (res.get("attempts", 0), rid))
        kind = res["kind"]
        if kind == "ok":
            fields, reasons = finalize(res["signals"], text, thresholds)
            _complete(con, rid, lc, fields, reasons, "model", session_id, request_id=res["request_id"])
            cache_put(cache, "enrich", tsha, lc, {"fields": fields, "reasons": reasons}, rid, res["request_id"], session_id)
            stats["model_completed"] += 1
            consecutive_failures = 0
        elif kind == "invalid":
            con.execute("UPDATE records SET status='quarantined', reason='invalid_model_output' WHERE review_id=?", (rid,))
            cache_put(cache, "enrich_invalid", tsha, lc, {"reason": "invalid_model_output", "error": res.get("error")},
                      rid, None, session_id)
            stats["quarantined"] += 1
            consecutive_failures = 0
        elif kind == "call_failed":
            status = res["info"].get("http_status")
            if status in (400, 413, 415, 422):
                con.execute("UPDATE records SET status='quarantined', reason=? WHERE review_id=?",
                            (f"request_rejected_{status}", rid))
                stats["quarantined"] += 1
            else:
                stats["still_pending_after_failures"] += 1
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_CALL_FAILURES:
                    stop_reason = "too_many_consecutive_call_failures"
                    stop_event.set()
        elif kind == "spend_cap":
            stop_reason = "spend_cap"
            stop_event.set()

    def commit_batch():
        stats["exact_text_reuse"] += fan_out(con, lc, session_id)
        con.commit()
        cache.commit()

    ex = ThreadPoolExecutor(max_workers=workers)
    try:
        while True:
            while not stop_event.is_set() and len(inflight) < workers * 2:
                if limit is not None and dispatched >= limit:
                    stop_reason = "limit_reached"
                    stop_event.set()
                    break
                item = next(items, None)
                if item is None:
                    break
                inflight[ex.submit(_enrich_one, client, limiter, ledger, item[0], item[1], ctx)] = item
                dispatched += 1
            if not inflight:
                break
            done, _ = wait(list(inflight), timeout=1.0, return_when=FIRST_COMPLETED)
            for f in done:
                item = inflight.pop(f)
                handle(item, f.result())  # FatalAPIError propagates
                since_commit += 1
            if since_commit >= batch_every:
                commit_batch()
                since_commit = 0
    except KeyboardInterrupt:
        stop_reason = "interrupted"
        stop_event.set()
        for f in list(inflight):  # in-flight requests may already be billed: wait and save them
            try:
                handle(inflight.pop(f), f.result())
            except FatalAPIError:
                pass
    except FatalAPIError:
        stop_reason = "fatal_auth_error"
        raise
    finally:
        ex.shutdown(wait=True)
        commit_batch()
        stats.update(stop_reason=stop_reason, wall_seconds=round(time.monotonic() - t0, 3), ledger=ledger.snapshot(),
                     status_counts=dict(con.execute("SELECT status, COUNT(*) FROM records GROUP BY status").fetchall()))
        con.execute("UPDATE sessions SET ended_at=?, stop_reason=?, stats_json=? WHERE session_id=?",
                    (now(), stop_reason, json.dumps(stats), session_id))
        con.commit()
    return stats


def export_records(con):
    """Contract-shaped final records: one per source ID (completed or quarantined); pending rows are reported."""
    out, pending = [], []
    for rid, ssha, status, reason, attempts, lc, fj, cache_src, synthetic in con.execute("""
            SELECT r.review_id, r.source_sha256, rec.status, rec.reason, rec.attempt_count,
                   e.label_config, e.fields_json, e.cache_source_id, COALESCE(e.synthetic, 0)
            FROM reviews r JOIN records rec USING(review_id) LEFT JOIN enriched e USING(review_id)
            ORDER BY r.row_order"""):
        if status == "completed":
            rec = {"review_id": rid, "source_sha256": ssha, "status": "completed", **json.loads(fj), "label_config": lc}
            if cache_src:
                rec["cache_source_id"] = cache_src
            if synthetic:
                rec["synthetic"] = True
            out.append(rec)
        elif status == "quarantined":
            out.append({"review_id": rid, "source_sha256": ssha, "status": "quarantined", "reason": reason,
                        "attempt_count": attempts})
        else:
            pending.append(rid)
    return out, pending


def write_enrich_outputs(con, ws):
    records, pending = export_records(con)
    d = ws / "enrich"
    write_text_atomic(d / "enriched.jsonl", "".join(json.dumps(r, ensure_ascii=False) + "\n"
                                                    for r in records if r["status"] == "completed"))
    write_text_atomic(d / "quarantine.jsonl", "".join(json.dumps(r, ensure_ascii=False) + "\n"
                                                      for r in records if r["status"] == "quarantined"))
    write_json_atomic(d / "pending_ids.json", pending)
    write_json_atomic(d / "checkpoint.json", {"completed_ids": [r["review_id"] for r in records
                                                                if r["status"] == "completed"]})
    return records, pending
