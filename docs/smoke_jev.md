# Jev smoke test findings (run `smoke-jev-20261015T003222Z`, 2026-10-14)

Evidence: [runs/smoke-jev-20261015T003222Z/](../runs/smoke-jev-20261015T003222Z/) (report.md, results.json with raw responses, calls.jsonl).

- 8/8 succeeded on first attempt; response model `jev-1.13.0` (pinned id honoured).
- Usage: 9,136 input tokens (~1,142/review, dominated by the repeated rubric), 1,783 output tokens (free). Cost $0.00038371.
- Latency 85–174 ms per call, 0.84 s wall for 8 sequential calls.
- Response shape confirmed: choice -> {choice, confidence, probabilities, type}; noul -> {noul}; score -> {score, confidence, probabilities, legend}.

Observations that shape v1 code/thresholds (dev data only):
1. Code-owned intent precedence works: "Finally removed waze, so 5 stars" — Jev intent choice was `cancellation` (0.94) but the cancellation Noul was 0.32, so code set `praise` and flagged needs_review.
2. Topic splits near 50/50 occur (billing 0.46 vs playback 0.45 on the TV-podcast review) — topic confidence thresholds will be tuned on the 500 run against the verifier.
3. Spanish review: plausible intent/severity but topic `catalog` where `billing` (price) fits better -> non-English is weaker, as documented by TypeSafe.
4. Bug found and fixed: entity regex matched "watch video" as `smartwatch`; tightened in taxonomy_v1.
