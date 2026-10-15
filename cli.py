"""Pipeline CLI. Every command is offline unless it is explicitly a paid command run with --paid."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def cmd_ingest(args):
    from srp.ingest import run_ingest

    report = run_ingest()
    print(json.dumps({k: report[k] for k in ("all_checks_passed", "accounting", "distinct_nonempty_texts",
                                             "ids_reusing_exact_text")}, indent=2))


def load_config():
    import yaml

    return yaml.safe_load((Path(__file__).resolve().parent / "config" / "run_config.yaml").read_text())


def cmd_smoke_jev(args):
    import sqlite3

    from srp import paths
    from srp.smoke import pick_reviews

    cfg = load_config()
    if not args.paid:
        from srp.jev import build_request
        from srp.rubric import label_config

        picks = pick_reviews(sqlite3.connect(paths.DB_PATH), args.n)
        print(f"DRY RUN (no API call). label_config={label_config()}")
        print(f"Would send {len(picks)} requests (1 review each):")
        for rid, text in picks:
            print(f"  {rid}  {text[:70]!r}")
        body, _ = build_request(picks[0][1])
        print("\nExample request body:\n" + json.dumps(body, ensure_ascii=False, indent=2))
        print("\nRe-run with --paid to execute.")
        return
    from dotenv import load_dotenv

    from srp.smoke import run_smoke

    load_dotenv(Path(__file__).resolve().parent / ".env")
    out, summary = run_smoke(args.n, args.spend_cap, cfg["thresholds"])
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Report: {out / 'report.md'}")


def cmd_smoke_claude(args):
    """2 verifier calls + 1 group-naming call on dev-only reviews to confirm the Haiku structured-output path."""
    import sqlite3
    import time

    from srp import paths
    from srp.smoke import pick_reviews

    picks = pick_reviews(sqlite3.connect(paths.DB_PATH), 6)
    if not args.paid:
        print("DRY RUN: would make 2 verify calls and 1 group-naming call on:", [p[0] for p in picks])
        return
    from dotenv import load_dotenv

    from srp.claude_client import ClaudeClient
    from srp.group import SCHEMA as GSCHEMA, SYSTEM as GSYSTEM
    from srp.verify import SCHEMA as VSCHEMA, system_prompt, verify_config
    from srp.workspace import CallLog

    load_dotenv(Path(__file__).resolve().parent / ".env")
    out = Path("runs") / ("smoke-claude-" + time.strftime("%Y%m%dT%H%M%S"))
    log = CallLog(out / "calls.jsonl")
    client = ClaudeClient(on_attempt=log.append)
    results = []
    for rid, text in picks[:2]:
        parsed, ev = client.json_call(system=system_prompt(), user=f"<review>\n{text}\n</review>", schema=VSCHEMA,
                                      max_tokens=1024, context={"run_id": out.name, "role": "verify",
                                                               "label_config": verify_config()}, review_ids=[rid])
        results.append({"role": "verify", "review_id": rid, "parsed": parsed, "usage": {k: ev.get(k) for k in ("input_tokens", "output_tokens")},
                        "latency_ms": ev.get("latency_ms"), "outcome": ev["outcome"], "error": ev.get("error")})
    user = "\n".join(f'<review id="{rid}">{text[:400]}</review>' for rid, text in picks[:5])
    parsed, ev = client.json_call(system=GSYSTEM, user=f"Issue key: smoke/test\n{user}", schema=GSCHEMA, max_tokens=1024,
                                  context={"run_id": out.name, "role": "group", "label_config": "smoke"},
                                  review_ids=[p[0] for p in picks[:5]])
    results.append({"role": "group", "parsed": parsed, "usage": {k: ev.get(k) for k in ("input_tokens", "output_tokens")},
                    "latency_ms": ev.get("latency_ms"), "outcome": ev["outcome"], "error": ev.get("error")})
    (out / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(json.dumps(results, indent=2, ensure_ascii=False))


def cmd_eval_golden(args):
    from srp.enrich import export_records
    from srp.evaluate import evaluate, write_outputs
    from srp.workspace import open_workspace

    con = open_workspace(args.workspace)
    records, _ = export_records(con)
    texts = dict(con.execute("SELECT review_id, review_text FROM reviews"))
    results, cases = evaluate(args.labels, records, args.out)
    done = [r for r in records if r["status"] == "completed"]
    results["quote_exact_substring_rate"] = round(sum(r["evidence_quote"] in texts[r["review_id"]] for r in done) / len(done), 4)
    results["prediction_workspace"] = str(args.workspace)
    results["label_config"] = sorted({r["label_config"] for r in done})
    write_outputs(args.out, results, cases)
    print(json.dumps({k: v for k, v in results.items() if not k.endswith("confusion")}, indent=2))


def cmd_export_grading(args):
    from srp.export import export_grading

    res = export_grading(ws=args.workspace, input_csv=args.input, cache_path=args.cache, out_dir=args.out,
                         dev_workspaces=args.dev_workspaces or [], checkpoint_before=args.checkpoint_before,
                         checkpoint_after=args.checkpoint_after)
    print(json.dumps(res, indent=2))


def cmd_load_db(args):
    from dotenv import load_dotenv

    from srp.db_load import load

    load_dotenv(Path(__file__).resolve().parent / ".env")
    print(json.dumps(load(args.workspace), indent=2))


def cmd_run(args):
    from srp.pipeline import STAGES, run_pipeline

    cfg = load_config()
    stages = tuple(s.strip() for s in args.stages.split(",")) if args.stages else STAGES
    if args.require_empty_cache and Path(args.cache).exists():
        raise SystemExit(f"--require-empty-cache: {args.cache} already exists (cold runs must start empty)")
    if args.paid:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parent / ".env")
    summary = run_pipeline(input_csv=args.input, ws_dir=args.workspace, cache_path=args.cache, cfg=cfg, stages=stages,
                           paid=args.paid, workers=args.workers or cfg["controls"]["max_workers"], rps=args.rps,
                           spend_cap=args.spend_cap, verify_fraction=args.verify_fraction, limit=args.limit)
    print(json.dumps({k: v for k, v in summary.items() if k != "stages"}, indent=2, default=str))
    for name, st in summary["stages"].items():
        res = st["result"]
        brief = res if isinstance(res, dict) else (res[0] if isinstance(res, (list, tuple)) and res and isinstance(res[0], str) else "ok")
        print(f"[{name}] {st['seconds']}s {json.dumps(brief, default=str)[:600]}")


def cmd_replay(args):
    from srp.pipeline import replay

    print(json.dumps(replay(args.workspace), indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cli.py", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ingest", help="Profile the full CSV and build the pending queue (no API calls)").set_defaults(func=cmd_ingest)
    p = sub.add_parser("smoke-jev", help="Jev smoke test on dev-only reviews (dry run unless --paid)")
    p.add_argument("--n", type=int, default=8)
    p.add_argument("--paid", action="store_true", help="Actually call the Jev API (costs money)")
    p.add_argument("--spend-cap", type=float, default=0.05, help="USD cap for this smoke run")
    p.set_defaults(func=cmd_smoke_jev)
    p = sub.add_parser("smoke-claude", help="Haiku structured-output smoke test (dry run unless --paid)")
    p.add_argument("--paid", action="store_true")
    p.set_defaults(func=cmd_smoke_claude)
    p = sub.add_parser("run", help="Run pipeline stages on an input CSV (paid stages require --paid)")
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--workspace", required=True, type=Path)
    p.add_argument("--cache", type=Path, default=Path("data/processed/result_cache.db"))
    p.add_argument("--stages", help="comma list of enrich,verify,group,rank,memo (default: all)")
    p.add_argument("--paid", action="store_true", help="Allow real API calls (costs money)")
    p.add_argument("--workers", type=int)
    p.add_argument("--rps", type=float, default=20.0, help="global requests/second limit across workers")
    p.add_argument("--spend-cap", type=float, help="USD cap for this invocation (default: config)")
    p.add_argument("--verify-fraction", type=float)
    p.add_argument("--limit", type=int, help="max new enrichment dispatches (interruption demo)")
    p.add_argument("--require-empty-cache", action="store_true")
    p.set_defaults(func=cmd_run)
    p = sub.add_parser("eval-golden", help="Offline: compare a workspace's predictions with human golden labels")
    p.add_argument("--workspace", required=True, type=Path)
    p.add_argument("--labels", type=Path, default=Path("evals/golden/golden_50_human_labels.csv"))
    p.add_argument("--out", type=Path, default=Path("evals/golden"))
    p.set_defaults(func=cmd_eval_golden)
    p = sub.add_parser("export-grading", help="Offline: write the standardized grading/ folder from a workspace")
    p.add_argument("--workspace", required=True, type=Path)
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--cache", type=Path, default=Path("data/processed/result_cache.db"))
    p.add_argument("--out", type=Path, default=Path("grading"))
    p.add_argument("--dev-workspaces", nargs="*", type=Path, help="earlier runs whose same-config enrich calls back cached results")
    p.add_argument("--checkpoint-before", type=Path)
    p.add_argument("--checkpoint-after", type=Path)
    p.set_defaults(func=cmd_export_grading)
    p = sub.add_parser("load-db", help="Load a workspace's saved outputs into Supabase Postgres (no model calls)")
    p.add_argument("--workspace", required=True, type=Path)
    p.set_defaults(func=cmd_load_db)
    p = sub.add_parser("replay", help="Offline: regenerate ranking from saved outputs and re-check the memo")
    p.add_argument("--workspace", required=True, type=Path)
    p.set_defaults(func=cmd_replay)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
