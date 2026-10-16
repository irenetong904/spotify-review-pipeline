# 100-review pilot: measured cost & runtime, and full-run projections

Generated offline by `python cost/calculator.py` from `pilot_calls.jsonl`, `pilot_runs.json`, `rates.csv`, `assumptions.yaml`. No API key or model call is used.

## Measured on `cost_100.csv`

- Input checksum: `c884ac3b9be5066995d5063f96ad9af6e5e082975788c1684c4f6b6ea661dd0e`; IDs: 100; completed: 100; failed/quarantined: 0
- Unique texts: 100; cold-run result-cache hits: 0; warm-run result-cache hits: 100
- Wall-clock: cold 200.16 s, warm 0.025 s (clock, not summed latencies)
- API spend: cold $0.026437, warm $0.000000 (incremental). Unknown-usage attempts: 0
- Cost per 1,000 input rows (cold): $0.2644; per completed record: $0.000264
- Local compute: Pipeline orchestration runs on a personal laptop; electricity/hardware cost not metered. Cost: **unknown** (not counted as zero).

| run | stage | provider | model | effort | config | batch | workers | requests | attempts | failed | retries | in tok | cache-w | cache-r | out tok | API $ | stage s | req/s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cold | enrich | typesafe | `jev-1.13.0` | n/a (Jev classifier, no generation) | `jev-1.13.0+rubric-v1.002865e8+q4.cd7ce12b` | 1 review/request | 1 | 100 | 100 | 0 | 0 | 81774 | 0 | 0 | 21781 | 0.003435 | 10.184 | 9.819 |
| cold | verify | anthropic | `claude-haiku-5-5` | adaptive thinking, effort=low | `claude-haiku-5-5+effort-low+verify-v1+rubric.002865e8` | 1 review/request | 1 | 100 | 100 | 0 | 0 | 140892 | 0 | 0 | 7627 | 0.017903 | 138.529 | 0.722 |
| cold | group | anthropic | `claude-haiku-5-5` | adaptive thinking, effort=low | `claude-haiku-5-5+effort-low+group-v1+taxonomy-v1` | <=20 examples/request | 1 | 18 | 18 | 0 | 0 | 11446 | 0 | 0 | 2582 | 0.002436 | 31.132 | 0.578 |
| cold | memo | anthropic | `claude-haiku-5-5` | adaptive thinking, effort=medium | `claude-haiku-5-5+effort-medium+memo-v2` | aggregates only | 1 | 1 | 1 | 0 | 0 | 4502 | 0 | 0 | 4427 | 0.002664 | 20.299 | 0.049 |
| warm | enrich | typesafe | `jev-1.13.0` | n/a (Jev classifier, no generation) | `jev-1.13.0+rubric-v1.002865e8+q4.cd7ce12b` | 1 review/request | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.000000 | 0.007 | 0 |
| warm | verify | anthropic | `claude-haiku-5-5` | adaptive thinking, effort=low | `claude-haiku-5-5+effort-low+verify-v1+rubric.002865e8` | 1 review/request | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.000000 | 0.003 | 0 |
| warm | group | anthropic | `claude-haiku-5-5` | adaptive thinking, effort=low | `claude-haiku-5-5+effort-low+group-v1+taxonomy-v1` | <=20 examples/request | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.000000 | 0.005 | 0 |
| warm | memo | anthropic | `claude-haiku-5-5` | adaptive thinking, effort=medium | `claude-haiku-5-5+effort-medium+memo-v2` | aggregates only | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.000000 | 0.002 | 0 |

Infrastructure: Supabase (free plan) and Vercel (Hobby plan) cost $0 for this project; provider prompt-cache savings: none occurred (no cache-read tokens in any call). Local laptop compute: not metered (unknown).

## Rates (editable: `rates.csv`)

| model | item | USD/unit | as quoted | source | checked |
|---|---|---|---|---|---|
| `jev-1.13.0` | input_tokens | 0.000000042 | $0.042 per 1M input tokens | https://docs.typesafe.ai/models | 2026-10-14 |
| `jev-1.13.0` | output_tokens | 0 | free | https://docs.typesafe.ai/models | 2026-10-14 |
| `claude-haiku-5-5` | input_tokens | 0.0000001 | $0.10 per 1M input tokens (prompt <=100K tokens) | https://platform.claude.com/docs/en/about-claude/pricing | 2026-10-14 |
| `claude-haiku-5-5` | cache_write_input_tokens | 0.000000125 | $0.125 per 1M (5-min cache write; 1.25x input) | https://platform.claude.com/docs/en/about-claude/pricing | 2026-10-14 |
| `claude-haiku-5-5` | cache_read_input_tokens | 0.00000001 | $0.01 per 1M (cache read; 0.1x input) | https://platform.claude.com/docs/en/about-claude/pricing | 2026-10-14 |
| `claude-haiku-5-5` | output_tokens | 0.0000005 | $0.50 per 1M output tokens (prompt <=100K tokens) | https://platform.claude.com/docs/en/about-claude/pricing | 2026-10-14 |

## Full-run projection (660,622 rows; 660,609 classifications; 13 empty-text quarantines)

Controls: budget $20.0, output-token cap 1024, max workers 4, rps limit 20, declared fallback fraction 0.0.

| scenario | exact-text reuse | stage | units | attempts/unit | $/call | cost $ | throughput rps | seconds | note |
|---|---|---|---|---|---|---|---|---|---|
| base | True | enrich | 484189 | 1.0 | 3.435e-05 | 16.6295 | 20 | 24209.5 |  |
| base | True | verify | 2000 | 1.0 | 0.00017903 | 0.3581 | 2.89 | 692.1 |  |
| base | True | group | 40 | 1.0 | 0.00013531 | 0.0054 | 2.315 | 17.3 |  |
| base | True | memo | 2 | 1.0 | 0.0026637 | 0.0053 | 0.197 | 10.1 |  |
| base | True | TOTAL |  |  |  | 16.9983 |  | 24945.9 | within budget (budget $20.0) |
| base | False | enrich | 660609 | 1.0 | 3.435e-05 | 22.6887 | 20 | 33030.4 |  |
| base | False | verify | 2000 | 1.0 | 0.00017903 | 0.3581 | 2.89 | 692.1 |  |
| base | False | group | 40 | 1.0 | 0.00013531 | 0.0054 | 2.315 | 17.3 |  |
| base | False | memo | 2 | 1.0 | 0.0026637 | 0.0053 | 0.197 | 10.1 |  |
| base | False | TOTAL |  |  |  | 23.0575 |  | 33766.9 | OVER BUDGET (budget $20.0) |
| conservative | True | enrich | 484189 | 1.1 | 3.511e-05 | 18.7009 | 20 | 26630.4 |  |
| conservative | True | verify | 2000 | 1.1 | 0.0001833 | 0.4033 | 2.054 | 1070.9 |  |
| conservative | True | group | 40 | 1.1 | 0.0002145 | 0.0094 | 1.437 | 30.6 |  |
| conservative | True | memo | 2 | 1.1 | 0.0026637 | 0.0059 | 0.197 | 11.2 |  |
| conservative | True | TOTAL |  |  |  | 19.1195 |  | 27760.0 | within budget (budget $20.0) |
| conservative | False | enrich | 660609 | 1.1 | 3.511e-05 | 25.5148 | 20 | 36333.5 |  |
| conservative | False | verify | 2000 | 1.1 | 0.0001833 | 0.4033 | 2.054 | 1070.9 |  |
| conservative | False | group | 40 | 1.1 | 0.0002145 | 0.0094 | 1.437 | 30.6 |  |
| conservative | False | memo | 2 | 1.1 | 0.0026637 | 0.0059 | 0.197 | 11.2 |  |
| conservative | False | TOTAL |  |  |  | 25.9334 |  | 37463.1 | OVER BUDGET (budget $20.0) |

**WARNING: base (reuse=False) $23.0575, conservative (reuse=False) $25.9334 exceed the $20.0 budget.**

Formulas: `item_cost = billed_units x price_per_unit`; per stage `cost = units x billed_calls_per_unit x cost_per_call`; `seconds = units x attempts_per_unit / min(workers / latency, rps_limit)`; fixed ingest overhead added once. Memo/group are fixed counts, not multiplied by reviews. Verification is a declared fraction of distinct texts. The 100-review sample is an initial estimate; refresh after 500 and 10,000.
