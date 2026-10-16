"""100-review cost & runtime calculator. OFFLINE BY DEFAULT: never calls an API and needs no key.

  python cost/calculator.py                    # replay: recompute usage.csv, projections.csv, report.md from saved files
  python cost/calculator.py collect --cold runs/pilot100_cold --warm runs/pilot100_warm   # offline copy of pilot evidence

The paid pilot itself is a separate, explicit command (see cost/README.md):
  python cli.py run --input <cost_100.csv> --workspace runs/pilot100_cold --cache runs/pilot100_cache.db --paid ...

Formulas: item_cost = billed_units x price_per_unit (rates.csv, per-token prices); total = sum(item_cost).
Usage categories are mutually exclusive (uncached input, cache write, cache read, output). Missing usage stays unknown.
"""

import argparse
import csv
import io
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ITEMS = ("input_tokens", "cache_write_input_tokens", "cache_read_input_tokens", "output_tokens")
PROVIDER = {"enrich": "typesafe", "verify": "anthropic", "group": "anthropic", "memo": "anthropic"}
EFFORT = {"enrich": "n/a (Jev classifier, no generation)", "verify": "adaptive thinking, effort=low",
          "group": "adaptive thinking, effort=low", "memo": "adaptive thinking, effort=medium"}


def load_rates(path):
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return {(r["model"], r["billing_item"]): r for r in rows}


def read_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def usage_rows(calls, rates):
    """One row per (call attempt, billing item) with units, unit price and cost. Unknown usage is kept visible."""
    out = []
    for c in calls:
        for item in ITEMS:
            units = c.get(item)
            if item == "input_tokens" and units is None:
                out.append({**_base(c), "billing_item": item, "units": "", "price_usd_per_unit": "",
                            "cost_usd": "", "note": "usage unavailable (failed attempt; provider billing unknown)"})
                continue
            if not units:
                continue
            rate = rates[(c["model"], item)]
            price = float(rate["price_usd_per_unit"])
            out.append({**_base(c), "billing_item": item, "units": units, "price_usd_per_unit": price,
                        "cost_usd": units * price, "note": f"rate checked {rate['checked_on']}: {rate['source_url']}"})
    return out


def _base(c):
    return {"pilot_run": c["pilot_run"], "role": c["role"], "request_id": c["request_id"], "model": c["model"],
            "attempt": c.get("attempt"), "outcome": c["outcome"], "purpose": c.get("purpose", "")}


def stat(xs, which):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    if which == "mean":
        return statistics.fmean(xs)
    return xs[min(len(xs) - 1, math.ceil(0.9 * len(xs)) - 1)]  # p90 (nearest rank)


def measured(calls, usage, runs, records):
    table = []
    cost_by = defaultdict(float)
    for u in usage:
        if u["cost_usd"] != "":
            cost_by[(u["pilot_run"], u["role"])] += u["cost_usd"]
    for run in ("cold", "warm"):
        info = runs.get(run, {})
        recs = [r for r in records if r.get("pilot_run", "cold") == run] or records
        for role in ("enrich", "verify", "group", "memo"):
            cs = [c for c in calls if c["pilot_run"] == run and c["role"] == role]
            stage = info.get("stages", {}).get(role if role != "memo" else "memo", {})
            row = {
                "run": run, "stage": role, "provider": PROVIDER[role],
                "model": cs[0]["model"] if cs else ("jev-1.13.0" if role == "enrich" else "claude-haiku-5-5"),
                "effort": EFFORT[role], "config": (cs[0].get("label_config") if cs else next((c.get("label_config") for c in calls if c["role"] == role), "")),
                "batch_size": "1 review/request" if role in ("enrich", "verify") else ("<=20 examples/request" if role == "group" else "aggregates only"),
                "workers": info.get("workers"),
                "requests": len({c["request_id"] for c in cs}), "attempts": len(cs),
                "failed_attempts": sum(c["outcome"] == "failed" for c in cs),
                "invalid_output_retries": sum(c.get("purpose") in ("invalid_output_retry", "check_failed_retry") for c in cs),
                **{item: sum(c.get(item) or 0 for c in cs) for item in ITEMS},
                "api_cost_usd": round(cost_by[(run, role)], 8),
                "stage_seconds": stage.get("seconds"),
                "throughput_req_per_s": round(len(cs) / stage["seconds"], 3) if cs and stage.get("seconds") else 0,
            }
            table.append(row)
    return table


def projections(calls, assumptions, rates):
    fr, sc = assumptions["full_run"], assumptions["scenarios"]
    ctl = assumptions["controls"]
    cold = [c for c in calls if c["pilot_run"] == "cold"]
    out = []
    for name, s in sc.items():
        for reuse in (True, False):
            units_enrich = fr["distinct_nonempty_texts"] if reuse else fr["nonempty_classifications"]
            units = {"enrich": units_enrich,
                     "verify": min(math.ceil(s["verify_fraction"] * fr["distinct_nonempty_texts"]),
                                   fr.get("verify_max_sample") or 10**12),
                     "group": fr["issues_named"], "memo": fr["memo_calls"]}
            total_cost, total_seconds = 0.0, float(fr["fixed_overhead_seconds"])
            for role, n in units.items():
                cs = [c for c in cold if c["role"] == role]
                ok = [c for c in cs if c["outcome"] == "succeeded"]
                if not ok:
                    out.append({"scenario": name, "exact_text_reuse": reuse, "stage": role, "work_units": n,
                                "cost_usd": "unknown", "seconds": "unknown", "note": "no measured successful calls"})
                    continue
                pilot_units = len({tuple(c["review_ids"]) for c in ok}) if role in ("enrich", "verify") else len(ok)
                attempts_per_unit = len(cs) / max(pilot_units, 1)
                billed_per_unit = len(ok) / max(pilot_units, 1)
                billed_per_unit = billed_per_unit * s["retry_multiplier"] + s.get("extra_attempt_rate", 0.0)
                attempts_per_unit = attempts_per_unit * s["retry_multiplier"] + s.get("extra_attempt_rate", 0.0)
                per_call = 0.0
                for item in ITEMS:
                    v = stat([c.get(item) or 0 for c in ok], s["token_stat"]) or 0
                    if role != "enrich" and item == "output_tokens":
                        v = min(v, ctl["max_output_tokens"]) if role in ("verify", "group") else v
                    if v:
                        per_call += v * float(rates[(ok[0]["model"], item)]["price_usd_per_unit"])
                cost = n * billed_per_unit * per_call
                lat_ms = stat([c.get("latency_ms") for c in ok], s["latency_stat"])
                if lat_ms:
                    lat = lat_ms / 1000.0
                    throughput = min(ctl["max_workers"] / lat, ctl["rps_limit"])  # requests per second
                    seconds = n * attempts_per_unit / throughput
                    total_seconds += seconds
                else:
                    lat = throughput = seconds = None
                    total_seconds = float("nan")
                total_cost += cost
                out.append({"scenario": name, "exact_text_reuse": reuse, "stage": role, "work_units": n,
                            "attempts_per_unit": round(attempts_per_unit, 4), "cost_per_call_usd": round(per_call, 8),
                            "cost_usd": round(cost, 4), "latency_s": round(lat, 3) if lat else "unknown",
                            "throughput_rps": round(throughput, 3) if throughput else "unknown",
                            "seconds": round(seconds, 1) if seconds is not None else "unknown", "note": ""})
            out.append({"scenario": name, "exact_text_reuse": reuse, "stage": "TOTAL", "work_units": "",
                        "cost_usd": round(total_cost, 4),
                        "seconds": round(total_seconds, 1) if total_seconds == total_seconds else "unknown",
                        "note": ("OVER BUDGET" if total_cost > ctl["budget_usd"] else "within budget")
                                + f" (budget ${ctl['budget_usd']})"})
    return out


def to_csv(rows):
    if not rows:
        return ""
    cols = list(dict.fromkeys(k for r in rows for k in r))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def replay(base=HERE):
    base = Path(base)
    rates = load_rates(base / "rates.csv")
    assumptions = yaml.safe_load((base / "assumptions.yaml").read_text())
    calls = read_jsonl(base / "pilot_calls.jsonl")
    records = read_jsonl(base / "pilot_records.jsonl")
    runs = json.loads((base / "pilot_runs.json").read_text())
    usage = usage_rows(calls, rates)
    meas = measured(calls, usage, runs, records)
    proj = projections(calls, assumptions, rates)
    (base / "usage.csv").write_text(to_csv(usage), encoding="utf-8")
    (base / "projections.csv").write_text(to_csv(proj), encoding="utf-8")
    (base / "report.md").write_text(report_md(meas, proj, runs, records, assumptions, rates, usage), encoding="utf-8")
    return meas, proj


def report_md(meas, proj, runs, records, assumptions, rates, usage):
    cold = runs.get("cold", {})
    n = len({r["review_id"] for r in records})
    completed = sum(r["status"] == "completed" for r in records)
    failed = n - completed
    api_cold = sum(m["api_cost_usd"] for m in meas if m["run"] == "cold")
    api_warm = sum(m["api_cost_usd"] for m in meas if m["run"] == "warm")
    unknown = sum(1 for u in usage if u["cost_usd"] == "")
    L = ["# 100-review pilot: measured cost & runtime, and full-run projections", "",
         "Generated offline by `python cost/calculator.py` from `pilot_calls.jsonl`, `pilot_runs.json`, `rates.csv`, "
         "`assumptions.yaml`. No API key or model call is used.", "",
         "## Measured on `cost_100.csv`", "",
         f"- Input checksum: `{cold.get('input_sha256', 'n/a')}`; IDs: {n}; completed: {completed}; failed/quarantined: {failed}",
         f"- Unique texts: {cold.get('distinct_nonempty_texts', 'n/a')}; cold-run result-cache hits: "
         f"{cold.get('enrich_result_cache_hits', 'n/a')}; warm-run result-cache hits: {runs.get('warm', {}).get('enrich_result_cache_hits', 'n/a')}",
         f"- Wall-clock: cold {cold.get('wall_seconds')} s, warm {runs.get('warm', {}).get('wall_seconds')} s (clock, not summed latencies)",
         f"- API spend: cold ${api_cold:.6f}, warm ${api_warm:.6f} (incremental). Unknown-usage attempts: {unknown}",
         f"- Cost per 1,000 input rows (cold): ${api_cold / max(n, 1) * 1000:.4f}; per completed record: ${api_cold / max(completed, 1):.6f}",
         f"- Local compute: {assumptions['local_compute']['note']} Cost: **{assumptions['local_compute']['cost_usd']}** (not counted as zero).",
         "", "| run | stage | provider | model | effort | config | batch | workers | requests | attempts | failed | retries | in tok | cache-w | cache-r | out tok | API $ | stage s | req/s |",
         "|" + "---|" * 19]
    for m in meas:
        L.append(f"| {m['run']} | {m['stage']} | {m['provider']} | `{m['model']}` | {m['effort']} | `{m['config']}` | {m['batch_size']} "
                 f"| {m['workers']} | {m['requests']} | {m['attempts']} | {m['failed_attempts']} | {m['invalid_output_retries']} "
                 f"| {m['input_tokens']} | {m['cache_write_input_tokens']} | {m['cache_read_input_tokens']} | {m['output_tokens']} "
                 f"| {m['api_cost_usd']:.6f} | {m['stage_seconds']} | {m['throughput_req_per_s']} |")
    ctl = assumptions["controls"]
    L += ["", "Infrastructure: Supabase (free plan) and Vercel (Hobby plan) cost $0 for this project; provider prompt-cache "
          "savings: none occurred (no cache-read tokens in any call). Local laptop compute: not metered (unknown).",
          "", "## Rates (editable: `rates.csv`)", "", "| model | item | USD/unit | as quoted | source | checked |", "|---|---|---|---|---|---|"]
    for (model, item), r in rates.items():
        L.append(f"| `{model}` | {item} | {r['price_usd_per_unit']} | {r['price_as_quoted']} | {r['source_url']} | {r['checked_on']} |")
    L += ["", "## Full-run projection (660,622 rows; 660,609 classifications; 13 empty-text quarantines)", "",
          f"Controls: budget ${ctl['budget_usd']}, output-token cap {ctl['max_output_tokens']}, max workers "
          f"{ctl['max_workers']}, rps limit {ctl['rps_limit']}, declared fallback fraction {ctl['fallback_fraction']}.", "",
          "| scenario | exact-text reuse | stage | units | attempts/unit | $/call | cost $ | throughput rps | seconds | note |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for p in proj:
        L.append(f"| {p['scenario']} | {p['exact_text_reuse']} | {p['stage']} | {p['work_units']} | {p.get('attempts_per_unit', '')} "
                 f"| {p.get('cost_per_call_usd', '')} | {p['cost_usd']} | {p.get('throughput_rps', '')} | {p['seconds']} | {p['note']} |")
    warn = [p for p in proj if p["stage"] == "TOTAL" and "OVER BUDGET" in p["note"]]
    L += ["", "**WARNING: " + ", ".join(f"{p['scenario']} (reuse={p['exact_text_reuse']}) ${p['cost_usd']}" for p in warn)
          + f" exceed the ${ctl['budget_usd']} budget.**" if warn else "All projected scenarios are within the declared budget."]
    L += ["", "Formulas: `item_cost = billed_units x price_per_unit`; per stage `cost = units x billed_calls_per_unit x "
          "cost_per_call`; `seconds = units x attempts_per_unit / min(workers / latency, rps_limit)`; fixed ingest "
          "overhead added once. Memo/group are fixed counts, not multiplied by reviews. Verification is a declared "
          "fraction of distinct texts. The 100-review sample is an initial estimate; refresh after 500 and 10,000."]
    return "\n".join(L) + "\n"


def collect(cold_ws, warm_ws, base=HERE):
    """Offline: copy pilot evidence from two workspaces into cost/ (no API calls)."""
    import sqlite3

    base = Path(base)
    calls, runs, records = [], {}, []
    for label, ws in (("cold", Path(cold_ws)), ("warm", Path(warm_ws))):
        for c in read_jsonl(ws / "calls.jsonl") if (ws / "calls.jsonl").exists() else []:
            calls.append({**c, "pilot_run": label})
        summary = json.loads((ws / "run_summary.json").read_text())
        con = sqlite3.connect(ws / "state.db")
        meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
        prof = json.loads(meta["profile"])
        enr = summary["stages"].get("enrich", {}).get("result", {})
        runs[label] = {"workspace": str(ws), "input_sha256": meta["input_sha256"], "wall_seconds": summary["wall_seconds"],
                       "workers": summary["workers"], "stages": {k: {"seconds": v["seconds"]} for k, v in summary["stages"].items()},
                       "distinct_nonempty_texts": prof["distinct_nonempty_texts"],
                       "enrich_result_cache_hits": enr.get("result_cache_hits"), "label_config": enr.get("label_config"),
                       "ledger": summary.get("ledger")}
        for line in (ws / "enrich" / "enriched.jsonl").read_text().splitlines() + (ws / "enrich" / "quarantine.jsonl").read_text().splitlines():
            if line.strip():
                records.append({**json.loads(line), "pilot_run": label})
    (base / "pilot_calls.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in calls), encoding="utf-8")
    (base / "pilot_records.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records if r["pilot_run"] == "cold"), encoding="utf-8")
    (base / "pilot_records_warm.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records if r["pilot_run"] == "warm"), encoding="utf-8")
    (base / "pilot_runs.json").write_text(json.dumps(runs, indent=2), encoding="utf-8")


def refresh(ws, label, base=HERE):
    """Offline: re-project the full run from a larger dev checkpoint's measured calls (500 / 10,000)."""
    base, ws = Path(base), Path(ws)
    rates = load_rates(base / "rates.csv")
    assumptions = yaml.safe_load((base / "assumptions.yaml").read_text())
    calls = [{**c, "pilot_run": "cold"} for c in read_jsonl(ws / "calls.jsonl")]
    proj = projections(calls, assumptions, rates)
    summary = json.loads((ws / "run_summary.json").read_text())
    (base / f"projections_{label}.csv").write_text(to_csv(proj), encoding="utf-8")
    measured_cost = sum(c.get("cost_usd") or 0 for c in calls)
    L = [f"# Projection refresh from the {label} checkpoint", "",
         f"Source: `{ws}/calls.jsonl` ({len(calls)} attempts, {sum(c['outcome'] == 'failed' for c in calls)} failed); "
         f"measured spend ${measured_cost:.4f}; wall-clock {summary['wall_seconds']} s with {summary['workers']} workers.", "",
         "| scenario | reuse | stage | units | attempts/unit | $/call | cost $ | rps | seconds | note |", "|---|---|---|---|---|---|---|---|---|---|"]
    for p in proj:
        L.append(f"| {p['scenario']} | {p['exact_text_reuse']} | {p['stage']} | {p['work_units']} | {p.get('attempts_per_unit', '')} "
                 f"| {p.get('cost_per_call_usd', '')} | {p['cost_usd']} | {p.get('throughput_rps', '')} | {p['seconds']} | {p['note']} |")
    (base / f"refresh_{label}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return proj


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")
    c = sub.add_parser("collect")
    c.add_argument("--cold", required=True)
    c.add_argument("--warm", required=True)
    r = sub.add_parser("refresh")
    r.add_argument("--workspace", required=True)
    r.add_argument("--label", required=True)
    args = p.parse_args(argv)
    if args.cmd == "refresh":
        for row in refresh(args.workspace, args.label):
            if row["stage"] == "TOTAL":
                print(f"{args.label}: {row['scenario']:>12} reuse={str(row['exact_text_reuse']):5} ${row['cost_usd']} {row['seconds']} s {row['note']}")
        return
    if args.cmd == "collect":
        collect(args.cold, args.warm)
    meas, proj = replay()
    for row in proj:
        if row["stage"] == "TOTAL":
            print(f"{row['scenario']:>12} reuse={str(row['exact_text_reuse']):5} total ${row['cost_usd']}  "
                  f"{row['seconds']} s  {row['note']}")
    print(f"wrote {HERE / 'report.md'}")


if __name__ == "__main__":
    sys.exit(main())
