# 100-review pilot findings (2026-10-14)

Evidence: [cost/report.md](../cost/report.md) (offline-regenerable), workspaces `runs/pilot100_cold`, `runs/pilot100_warm`.

| | cold (empty cache, 1 worker) | warm (saved cache, same settings) |
|---|---|---|
| records completed / failed | 100 / 0 | 100 / 0 |
| model calls | 219 (100 enrich, 100 verify, 18 group, 1 memo); 0 failed, 0 retries | **0** (all stages served from saved results) |
| API spend | $0.028504 | $0.000000 |
| wall-clock | 207.9 s (verify 140 s dominates at 1 worker) | 0.02 s |
| ranking sha256 | 537ac6f5… | identical; `cli.py replay` also identical |

Verifier (Claude Haiku 5.5, blind, 100% of pilot): topic agreement 0.91, intent 0.94, severity exact 0.90
(MAE 0.11), sentiment MAE 0.175. Weakest: Jev `billing` vs verifier (5/8 agree) — billing/usability boundary
on premium-only controls; see `runs/pilot100_cold/verify/disagreements.csv`.

Full-run projection (cost/report.md): base $26.87 with exact-text reuse ($35.02 without); conservative $45.02 / $57.85;
all within the declared $60 budget. Jev enrich is ~83% of cost (~1.1K input tokens/review, dominated by the
repeated rubric). Runtime is bounded by the shared rps limit (20) -> ~6.7 h enrich at base; raising workers/rps
within TypeSafe's org limits is the main lever.

## Issue found and fixed after the pilot
- **memo-v1 hid claim values from the writer** (it saw only claim IDs), so it compared areas blind and wrongly said
  Billing/support totals were "unpopulated". memo-v2 shows the values but still requires placeholders in the
  output, so every rendered number still comes from code. The pilot memo is kept as measured (v1); v2 is used from
  the 500-review run onward.
- Calculator showed the enrich label_config for warm-run Claude stages; fixed (display only, no cost change).
