# Prioritize Usability: restore core player controls and reduce ad and autoplay friction

## Recommendation

Put next quarter's product effort into Usability. Usability has the broadest set of distinct complaint themes in the ranked list: general usability and intrusive ads, player controls removed or disrupted by a recent update, excessive advertising, and playlist playback controls. Area-level totals are 14 [C055] complaint records, severity sum 36 [C056], and share of complaints 0.280000 [C058].

## Evidence

The most concrete theme is `usability/ui_layout`, which ranks 4 [C020] in baseline order. Reviewers say repeat, seek-back, and segment-replay features disappeared after an update (`e16a4550-43e7-4ae1-b538-a65cc652c31b`, `9e5f9745-f8be-48d3-b9de-4d118507d94a`). Ad and autoplay complaints appear in `usability/ads` and `usability/general` (`cf6166ae-d71a-4839-9add-088645ad3b78`, `d455c11e-c530-4c03-a395-38f5a5cdb8d3`). Playlist controls appear in `usability/queue_playlist`, rank 7 [C035].

## Alternatives considered

Playback has a clear failure mode in `playback/general`, where the app stalls on loading and voice-assistant playback fails (`66a29b3c-c14d-440e-b722-b23e0c99ae82`). Its area totals are 7 [C059] complaints with share 0.140000 [C062], and it rests on one issue cluster.

Billing/support is the hardest call. `billing/subscription_entitlement` ranks highly (2 [C010]), and reviewers describe features locked behind premium (`d146397f-4a94-4980-be00-ae9212eca3a7`). However, the Billing/support area totals (8 [C063] to 0.160000 [C066]) are unpopulated in this run, so an area-level comparison is not possible. Treat the paywall as an entitlement product decision rather than a support fix.

Access centers on `access/account_recovery`, with password rejections during login. Its area totals are 2 [C067] complaints with share 0.040000 [C070]. This is a real defect but narrower than Usability.

Outside the four areas, `other/general` is vague dissatisfaction (19 [C051] records), and catalog issues are not actionable for this quarter.

## Limitations

Reviews are self-selected public app-store text. Cancellation language (9 [C074] records) is stated intent, not observed churn. This memo makes no revenue, churn, or causal estimates. Unresolved or quarantined records total 0 [C073] and are excluded from the ranking, so the ranking may shift when they resolve. The Billing/support area aggregates are missing, which limits direct comparison.
