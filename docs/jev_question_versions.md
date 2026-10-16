# Jev question wording: measured cost vs quality (q1 → q4)

Why: the course limit is $20 for the whole project, and on the first pilot ~95% of Jev input tokens were question
text repeated on every request. All comparisons below use the same 100 reviews (`cost_100.csv`, development data)
and the same blind Haiku verifier; the golden 50 was **not** used to choose the wording (the golden run happened
after q4 was fixed).

**Token probe (7 tiny calls, `runs/token-probe-20261014/`).** All five q2 questions in one request: 873 input
tokens; the same questions sent one at a time: 521 + 283 + 313 + 406 + 394 = 1,917. So each request carries ≈260
fixed tokens, and the per-question cost was topic ≈260, intent ≈145, severity ≈133, sentiment ≈52, cancel Noul ≈22.
The review text is counted once per question, so packing several reviews into one request would not save tokens.

| version | change | Jev input tokens / review | full-run Jev estimate | verifier agreement topic / intent / severity exact | evidence |
|---|---|---|---|---|---|
| q1 | contract definitions + all topic rules in the instructions | 1,100 | $22.38 | 91% / 94% / 90% | `runs/pilot100_cold`, [cost/pilot_q1/](../cost/pilot_q1/) |
| q2 | shorter instructions, same definitions | 908 | $18.47 | 92% / 93% / 89% | `runs/pilot100_q2_cold` |
| q3 | the assignment brief's short label forms everywhere | 794 | $16.14 | 93% / 93% / **81%** | `runs/pilot100_q3_cold` |
| **q4** | q3 + q2's fuller severity definitions | **818** | **$16.63** | 92% / 92% / 90% | `runs/pilot100_q4_cold`, [cost/report.md](../cost/report.md) |

q3 lost 8–9 points of severity agreement (it labeled seven severity-3 reviews as 4: the terse "core task blocked" lost
"clearly ... such as inability to log in or play music"). q4 restores the severity wording and keeps the other savings.
Measured full-run Jev cost with q4: **$16.46** ([cost/full_run_actuals.json](../cost/full_run_actuals.json)).

Each version has its own `label_config`, so results never mix across versions in the result cache or the export.
