"""Orchestrator: input CSV -> ingest -> enrich -> verify -> group -> rank -> memo, with saved handoffs.
Paid stages run only when explicitly requested (paid=True); `replay` regenerates rank/claims/memo-render offline."""

import json
import threading
import time
from pathlib import Path

from srp.claude_client import ClaudeClient
from srp.enrich import run_enrich, write_enrich_outputs
from srp.group import run_group
from srp.io_atomic import write_json_atomic
from srp.jev import JevClient
from srp.memo import run_memo
from srp.rank import ranking_hash, run_rank
from srp.verify import run_verify
from srp.workspace import CallLog, SpendLedger, now, open_cache, open_workspace

STAGES = ("enrich", "verify", "group", "rank", "memo")


def run_pipeline(*, input_csv, ws_dir, cache_path, cfg, stages=STAGES, paid=False, workers=1, rps=20,
                 spend_cap=None, verify_fraction=None, limit=None, jev_client=None, claude_client=None):
    ws = Path(ws_dir)
    con = open_workspace(ws, input_csv)
    cache = open_cache(cache_path)
    calllog = CallLog(ws / "calls.jsonl")
    cap = cfg["controls"]["spend_cap_usd"] if spend_cap is None else spend_cap
    # the cap covers the whole workspace: spend from earlier (interrupted) invocations counts against it
    prior_spend = sum(c.get("cost_usd") or 0.0 for c in calllog.read())
    ledger = SpendLedger(cap, spent_usd=prior_spend)
    needs_models = {"enrich", "verify", "group", "memo"} & set(stages)
    if needs_models and not paid and (jev_client is None or claude_client is None):
        raise SystemExit("Stages " + ",".join(sorted(needs_models)) + " may call paid APIs; re-run with --paid "
                         "(or use `replay` for the offline path).")
    if paid and jev_client is None and "enrich" in stages:
        jev_client = JevClient(on_attempt=calllog.append, max_attempts=cfg["controls"]["max_attempts"])
    if paid and claude_client is None and ({"verify", "group", "memo"} & set(stages)):
        claude_client = ClaudeClient(on_attempt=calllog.append)

    t0 = time.monotonic()
    summary = {"workspace": str(ws), "input": str(input_csv), "started_at": now(), "stages": {}, "spend_cap_usd": cap,
               "prior_workspace_spend_usd": round(prior_spend, 6),
               "workers": workers}
    timings = summary["stages"]

    def timed(name, fn):
        s = time.monotonic()
        out = fn()
        timings[name] = {"seconds": round(time.monotonic() - s, 3), "result": out}
        write_json_atomic(ws / "run_summary.json", summary)  # progress is visible after every stage
        return out

    stop = threading.Event()
    if "enrich" in stages:
        timed("enrich", lambda: run_enrich(con, cache, calllog, jev_client, cfg, ledger=ledger, workers=workers,
                                           rps=rps, limit=limit, stop_event=stop))
        records, pending = write_enrich_outputs(con, ws)
        if pending:
            summary["incomplete"] = f"{len(pending)} records still pending; downstream stages use completed records only"
    if "verify" in stages:
        frac = cfg["verification"]["sample_fraction"] if verify_fraction is None else verify_fraction
        timed("verify", lambda: run_verify(con, cache, claude_client, cfg, ws, ledger, fraction=frac, workers=workers,
                                           session_id=f"verify-{int(time.time())}"))
    if "group" in stages:
        timed("group", lambda: run_group(con, cache, claude_client, ws, ledger, session_id=f"group-{int(time.time())}"))
    ranking = agg = None
    if "rank" in stages or "memo" in stages:
        ranking, agg = timed("rank", lambda: _rank_summary(con, ws))
    if "memo" in stages:
        timed("memo", lambda: run_memo(con, cache, claude_client, ws, ledger, ranking, agg,
                                       session_id=f"memo-{int(time.time())}"))
    summary.update(wall_seconds=round(time.monotonic() - t0, 3), ended_at=now(), ledger=ledger.snapshot(),
                   ranking_sha256=ranking_hash(ws) if (ws / "rank" / "ranking.csv").exists() else None)
    write_json_atomic(ws / "run_summary.json", summary)
    return summary


def _rank_summary(con, ws):
    rows, agg = run_rank(con, ws)
    return rows, agg


def replay(ws_dir):
    """Offline: regenerate ranking/aggregates from saved records + membership and re-check the saved memo.
    No API key, no model calls."""
    from srp.memo import check_memo, build_claims, render

    ws = Path(ws_dir)
    con = open_workspace(ws)
    before = ranking_hash(ws) if (ws / "rank" / "ranking.csv").exists() else None
    rows, agg = run_rank(con, ws)
    after = ranking_hash(ws)
    result = {"ranking_sha256_before": before, "ranking_sha256_after": after, "identical": before == after,
              "issues": len(rows)}
    memo_path = ws / "memo" / "memo.json"
    if memo_path.exists():
        saved = json.loads(memo_path.read_text())
        claims = build_claims(rows, agg)
        errors = check_memo(saved["raw"], claims, saved["evidence"], rows)
        same_values = {c["claim_id"]: c["value"] for c in claims} == {c["claim_id"]: c["value"] for c in saved["claims"]}
        result.update(memo_check_errors=errors, claims_match_saved=same_values,
                      memo_rerender_identical=render(saved["raw"]["memo_markdown"], claims) == saved["rendered"]["memo_markdown"])
    return result
