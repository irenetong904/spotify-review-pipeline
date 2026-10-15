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


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cli.py", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ingest", help="Profile the full CSV and build the pending queue (no API calls)").set_defaults(func=cmd_ingest)
    p = sub.add_parser("smoke-jev", help="Jev smoke test on dev-only reviews (dry run unless --paid)")
    p.add_argument("--n", type=int, default=8)
    p.add_argument("--paid", action="store_true", help="Actually call the Jev API (costs money)")
    p.add_argument("--spend-cap", type=float, default=0.05, help="USD cap for this smoke run")
    p.set_defaults(func=cmd_smoke_jev)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
