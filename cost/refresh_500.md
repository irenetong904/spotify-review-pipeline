# Projection refresh from the 500 checkpoint

Source: `runs/checkpoint500/calls.jsonl` (785 attempts, 0 failed); measured spend $0.0874; wall-clock 320.268 s with 2 workers.

| scenario | reuse | stage | units | attempts/unit | $/call | cost $ | rps | seconds | note |
|---|---|---|---|---|---|---|---|---|---|
| base | True | enrich | 484189 | 1.0 | 3.425e-05 | 16.584 | 20 | 24209.5 |  |
| base | True | verify | 2000 | 1.0 | 0.00017669 | 0.3534 | 3.27 | 611.6 |  |
| base | True | group | 40 | 1.0 | 0.00019074 | 0.0076 | 2.106 | 19.0 |  |
| base | True | memo | 2 | 1.0 | 0.0025095 | 0.005 | 0.218 | 9.2 |  |
| base | True | TOTAL |  |  |  | 16.95 |  | 24866.2 | within budget (budget $20.0) |
| base | False | enrich | 660609 | 1.0 | 3.425e-05 | 22.6266 | 20 | 33030.4 |  |
| base | False | verify | 2000 | 1.0 | 0.00017669 | 0.3534 | 3.27 | 611.6 |  |
| base | False | group | 40 | 1.0 | 0.00019074 | 0.0076 | 2.106 | 19.0 |  |
| base | False | memo | 2 | 1.0 | 0.0025095 | 0.005 | 0.218 | 9.2 |  |
| base | False | TOTAL |  |  |  | 22.9926 |  | 33687.2 | OVER BUDGET (budget $20.0) |
| conservative | True | enrich | 484189 | 1.1 | 3.57e-05 | 19.0141 | 20 | 26630.4 |  |
| conservative | True | verify | 2000 | 1.1 | 0.0001803 | 0.3967 | 2.642 | 832.7 |  |
| conservative | True | group | 40 | 1.1 | 0.0002743 | 0.0121 | 1.728 | 25.5 |  |
| conservative | True | memo | 2 | 1.1 | 0.0025095 | 0.0055 | 0.218 | 10.1 |  |
| conservative | True | TOTAL |  |  |  | 19.4284 |  | 27515.7 | within budget (budget $20.0) |
| conservative | False | enrich | 660609 | 1.1 | 3.57e-05 | 25.9421 | 20 | 36333.5 |  |
| conservative | False | verify | 2000 | 1.1 | 0.0001803 | 0.3967 | 2.642 | 832.7 |  |
| conservative | False | group | 40 | 1.1 | 0.0002743 | 0.0121 | 1.728 | 25.5 |  |
| conservative | False | memo | 2 | 1.1 | 0.0025095 | 0.0055 | 0.218 | 10.1 |  |
| conservative | False | TOTAL |  |  |  | 26.3564 |  | 37218.8 | OVER BUDGET (budget $20.0) |
