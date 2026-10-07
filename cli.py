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


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cli.py", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ingest", help="Profile the full CSV and build the pending queue (no API calls)").set_defaults(func=cmd_ingest)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
