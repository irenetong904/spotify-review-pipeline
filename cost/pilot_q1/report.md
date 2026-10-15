# 100-review pilot: measured cost & runtime, and full-run projections

Generated offline by `python cost/calculator.py` from `pilot_calls.jsonl`, `pilot_runs.json`, `rates.csv`, `assumptions.yaml`. No API key or model call is used.

## Measured on `cost_100.csv`

- Input checksum: `c884ac3b9be5066995d5063f96ad9af6e5e082975788c1684c4f6b6ea661dd0e`; IDs: 100; completed: 100; failed/quarantined: 0
- Unique texts: 100; cold-run result-cache hits: 0; warm-run result-cache hits: 100
- Wall-clock: cold 207.899 s, warm 0.021 s (clock, not summed latencies)
- API spend: cold $0.028504, warm $0.000000 (incremental). Unknown-usage attempts: 0
- Cost per 1,000 input rows (cold): $0.2850; per completed record: $0.000285
- Local compute: Pipeline orchestration runs on a personal laptop; electricity/hardware cost not metered. Cost: **unknown** (not counted as zero).

| run | stage | provider | model | effort | config | batch | workers | requests | attempts | failed | retries | in tok | cache-w | cache-r | out tok | API $ | stage s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cold | enrich | typesafe | `jev-1.13.0` | n/a (Jev classifier, no generation) | `jev-1.13.0+rubric-v1.002865e8+q1.ad74bb89` | 1 review/request | 1 | 100 | 100 | 0 | 0 | 110036 | 0 | 0 | 21785 | 0.004622 | 9.805 |
| cold | verify | anthropic | `claude-haiku-5-5` | adaptive thinking, effort=low | `claude-haiku-5-5+effort-low+verify-v1+rubric.002865e8` | 1 review/request | 1 | 100 | 100 | 0 | 0 | 140892 | 0 | 0 | 8830 | 0.018504 | 140.258 |
| cold | group | anthropic | `claude-haiku-5-5` | adaptive thinking, effort=low | `claude-haiku-5-5+effort-low+group-v1+taxonomy-v1` | <=20 examples/request | 1 | 18 | 18 | 0 | 0 | 11446 | 0 | 0 | 2443 | 0.002366 | 32.411 |
| cold | memo | anthropic | `claude-haiku-5-5` | adaptive thinking, effort=medium | `claude-haiku-5-5+effort-medium+memo-v1` | aggregates only | 1 | 1 | 1 | 0 | 0 | 4243 | 0 | 0 | 5175 | 0.003012 | 25.409 |
| warm | enrich | typesafe | `jev-1.13.0` | n/a (Jev classifier, no generation) | `jev-1.13.0+rubric-v1.002865e8+q1.ad74bb89` | 1 review/request | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.000000 | 0.007 |
| warm | verify | anthropic | `claude-haiku-5-5` | adaptive thinking, effort=low | `claude-haiku-5-5+effort-low+verify-v1+rubric.002865e8` | 1 review/request | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.000000 | 0.003 |
| warm | group | anthropic | `claude-haiku-5-5` | adaptive thinking, effort=low | `claude-haiku-5-5+effort-low+group-v1+taxonomy-v1` | <=20 examples/request | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.000000 | 0.005 |
| warm | memo | anthropic | `claude-haiku-5-5` | adaptive thinking, effort=medium | `claude-haiku-5-5+effort-medium+memo-v1` | aggregates only | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.000000 | 0.003 |

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

Controls: budget $60.0, output-token cap 1024, max workers 4, rps limit 20, declared fallback fraction 0.0.

| scenario | exact-text reuse | stage | units | attempts/unit | $/call | cost $ | throughput rps | seconds | note |
|---|---|---|---|---|---|---|---|---|---|
| base | True | enrich | 484189 | 1.0 | 4.622e-05 | 22.3769 | 20 | 24209.5 |  |
| base | True | verify | 24210 | 1.0 | 0.00018504 | 4.4799 | 2.854 | 8482.1 |  |
| base | True | group | 40 | 1.0 | 0.00013145 | 0.0053 | 2.223 | 18.0 |  |
| base | True | memo | 2 | 1.0 | 0.0030118 | 0.006 | 0.158 | 12.7 |  |
| base | True | TOTAL |  |  |  | 26.868 |  | 32739.2 | within budget (budget $60.0) |
| base | False | enrich | 660609 | 1.0 | 4.622e-05 | 30.5301 | 20 | 33030.4 |  |
| base | False | verify | 24210 | 1.0 | 0.00018504 | 4.4799 | 2.854 | 8482.1 |  |
| base | False | group | 40 | 1.0 | 0.00013145 | 0.0053 | 2.223 | 18.0 |  |
| base | False | memo | 2 | 1.0 | 0.0030118 | 0.006 | 0.158 | 12.7 |  |
| base | False | TOTAL |  |  |  | 35.0213 |  | 41560.2 | within budget (budget $60.0) |
| conservative | True | enrich | 484189 | 1.55 | 4.691e-05 | 35.2086 | 20 | 37524.6 |  |
| conservative | True | verify | 24210 | 1.55 | 0.0002608 | 9.7867 | 1.862 | 20151.2 |  |
| conservative | True | group | 40 | 1.55 | 0.0002138 | 0.0133 | 1.381 | 44.9 |  |
| conservative | True | memo | 2 | 1.55 | 0.0030118 | 0.0093 | 0.158 | 19.7 |  |
| conservative | True | TOTAL |  |  |  | 45.0179 |  | 57757.4 | within budget (budget $60.0) |
| conservative | False | enrich | 660609 | 1.55 | 4.691e-05 | 48.0373 | 20 | 51197.2 |  |
| conservative | False | verify | 24210 | 1.55 | 0.0002608 | 9.7867 | 1.862 | 20151.2 |  |
| conservative | False | group | 40 | 1.55 | 0.0002138 | 0.0133 | 1.381 | 44.9 |  |
| conservative | False | memo | 2 | 1.55 | 0.0030118 | 0.0093 | 0.158 | 19.7 |  |
| conservative | False | TOTAL |  |  |  | 57.8465 |  | 71430.0 | within budget (budget $60.0) |

All projected scenarios are within the declared budget.

Formulas: `item_cost = billed_units x price_per_unit`; per stage `cost = units x billed_calls_per_unit x cost_per_call`; `seconds = units x attempts_per_unit / min(workers / latency, rps_limit)`; fixed ingest overhead added once. Memo/group are fixed counts, not multiplied by reviews. Verification is a declared fraction of distinct texts. The 100-review sample is an initial estimate; refresh after 500 and 10,000.
