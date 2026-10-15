# Cost & runtime calculator

Everything here is reproducible **offline, without an API key**.

## Offline replay (default — no model calls)

```bash
.venv/bin/python cost/calculator.py
```

Recomputes `usage.csv` (one row per call attempt × billing item), `projections.csv` and `report.md` from:
`pilot_calls.jsonl` (every attempt, cold + warm, incl. failures/retries), `pilot_runs.json` (measured wall-clock and
stage times), `rates.csv` (editable, dated, source-linked) and `assumptions.yaml` (editable budget, output-token cap,
max workers, rps limit, fallback fraction, scenarios). Importing/opening the calculator never makes a call.

## Explicit pilot execution (paid — separate commands)

```bash
# cold: empty result cache, one worker, all stages, 100% verification sample
.venv/bin/python cli.py run --input "data/Final Assignment - Spotify Reviews Dataset/cost_100.csv" \
  --workspace runs/pilot100_cold --cache runs/pilot100_cache.db --require-empty-cache \
  --workers 1 --verify-fraction 1.0 --spend-cap 1.00 --paid
# warm: same input and settings, saved result cache -> expect zero new enrichment calls
.venv/bin/python cli.py run --input "data/Final Assignment - Spotify Reviews Dataset/cost_100.csv" \
  --workspace runs/pilot100_warm --cache runs/pilot100_cache.db \
  --workers 1 --verify-fraction 1.0 --spend-cap 1.00 --paid
# copy evidence into cost/ (offline) and rebuild the report
.venv/bin/python cost/calculator.py collect --cold runs/pilot100_cold --warm runs/pilot100_warm
```
