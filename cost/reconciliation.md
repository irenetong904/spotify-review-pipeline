# Reconciliation with provider dashboards (checked 2026-10-15)

Computed cost = every logged call attempt in `runs/*/calls.jsonl` × [rates.csv](rates.csv) (offline). Dashboard figures
were read from each provider's console by the account owner. Only amounts are recorded here.

| provider | dashboard figure | computed from logs | difference | notes |
|---|---|---|---|---|
| TypeSafe (Jev) | $25.00 credit purchased − $8.23 remaining = **$16.77** used | **$16.7674** (399,224,938 input tokens; output free) | +$0.003 (0.02%) | dashboard rounds to cents; the 30 failed attempts (HTTP 499/502, connection resets) had no usage and evidently were not billed |
| Anthropic (Claude Haiku 5.5) | API key `spotify_new` cost **$0.69** | **$0.7104** (5,159,273 input / 388,937 output tokens) | −$0.02 (−3%) | most likely reporting lag for the last memo calls on 2026-10-15; no cache tokens were used |
| **Total** | **$17.46** | **$17.48** | | within the $20 course limit |

Scope: the TypeSafe credit and the Anthropic key were used only for this project (smoke tests, four 100-review pilots,
500, golden 50, 10k, injection test, full run, memo iterations). Infrastructure (Supabase free plan, Vercel Hobby) $0.
