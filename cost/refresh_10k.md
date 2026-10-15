# Projection refresh from the 10k checkpoint

Source: `runs/analysis10k/calls.jsonl` (8403 attempts, 0 failed); measured spend $0.3571; wall-clock 599.849 s with 4 workers.

| scenario | reuse | stage | units | attempts/unit | $/call | cost $ | rps | seconds | note |
|---|---|---|---|---|---|---|---|---|---|
| base | True | enrich | 484189 | 1.0 | 3.442e-05 | 16.6639 | 20 | 24209.5 |  |
| base | True | verify | 2000 | 1.0 | 0.00018006 | 0.3601 | 3.218 | 621.5 |  |
| base | True | group | 40 | 1.0 | 0.0002814 | 0.0113 | 2.024 | 19.8 |  |
| base | True | memo | 2 | 1.0 | 0.0012449 | 0.0025 | 0.564 | 3.5 |  |
| base | True | TOTAL |  |  |  | 17.0377 |  | 24871.3 | within budget (budget $20.0) |
| base | False | enrich | 660609 | 1.0 | 3.442e-05 | 22.7355 | 20 | 33030.4 |  |
| base | False | verify | 2000 | 1.0 | 0.00018006 | 0.3601 | 3.218 | 621.5 |  |
| base | False | group | 40 | 1.0 | 0.0002814 | 0.0113 | 2.024 | 19.8 |  |
| base | False | memo | 2 | 1.0 | 0.0012449 | 0.0025 | 0.564 | 3.5 |  |
| base | False | TOTAL |  |  |  | 23.1094 |  | 33692.3 | OVER BUDGET (budget $20.0) |
| conservative | True | enrich | 484189 | 1.1 | 3.94e-05 | 20.9826 | 20 | 26630.4 |  |
| conservative | True | verify | 2000 | 1.1 | 0.0001842 | 0.4052 | 2.223 | 989.4 |  |
| conservative | True | group | 40 | 1.1 | 0.0003621 | 0.0159 | 1.715 | 25.7 |  |
| conservative | True | memo | 2 | 1.1 | 0.0012449 | 0.0027 | 0.564 | 3.9 |  |
| conservative | True | TOTAL |  |  |  | 21.4065 |  | 27666.4 | OVER BUDGET (budget $20.0) |
| conservative | False | enrich | 660609 | 1.1 | 3.94e-05 | 28.6279 | 20 | 36333.5 |  |
| conservative | False | verify | 2000 | 1.1 | 0.0001842 | 0.4052 | 2.223 | 989.4 |  |
| conservative | False | group | 40 | 1.1 | 0.0003621 | 0.0159 | 1.715 | 25.7 |  |
| conservative | False | memo | 2 | 1.1 | 0.0012449 | 0.0027 | 0.564 | 3.9 |  |
| conservative | False | TOTAL |  |  |  | 29.0518 |  | 37369.5 | OVER BUDGET (budget $20.0) |
