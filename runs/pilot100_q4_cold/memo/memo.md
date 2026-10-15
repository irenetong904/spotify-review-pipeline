# Prioritize Usability: it has the most complaints and severity among the four named areas, led by the post-update layout regression.

## Recommendation
Prioritize Usability. Among the four named areas it has the most complaints (15 [C051]) and the largest severity sum (40 [C052]), with mean severity 2.666667 [C053] and a complaint share of 0.300000 [C054]. Start with the post-update layout regression in `usability/ui_layout`, then reduce ad interruptions and fix general usability bugs in `usability/ads` and `usability/general`.

## Evidence
`usability/ui_layout` ranks third in the baseline with 5 [C011] complaints and a severity sum of 15 [C012]. Reviews such as `e16a4550-43e7-4ae1-b538-a65cc652c31b` and `9e5f9745-f8be-48d3-b9de-4d118507d94a` describe inability to repeat or go back within tracks after the update, and `45c561b9-cc47-4d80-95d3-f0d20bc84af3` says the update made the app useless.

`usability/general` adds 5 [C016] complaints and `usability/ads` adds 3 [C026]. Review `cf6166ae-d71a-4839-9add-088645ad3b78` reports ads replacing songs, and `9c9757da-6b99-4c95-a0e7-0661ee858027` reports a broken music adjustment feature. `usability/queue_playlist` adds 2 [C031] complaints about playback control frustration.

## Alternatives considered
Billing/support has 8 [C063] complaints, a severity sum of 23 [C064] and mean severity 2.875000 [C065]. Most of that comes from `billing/subscription_entitlement` (7 [C006] complaints, ranked second overall), where review `d146397f-4a94-4980-be00-ae9212eca3a7` describes features locked behind premium. This is a real concern, but it is concentrated in one issue and is smaller than Usability as an area.

Playback has 7 [C059] complaints and a severity sum of 26 [C060], with mean severity 3.714286 [C061]. Its issues are small: `playback/general` has 2 [C021] complaints at mean severity 4.000000 [C023], and review text points to stalling and failed playback with external assistants.

Access has only 2 [C067] complaints, though its mean severity is 4.000000 [C069]. `access/account_recovery` has 1 [C041] complaint. This is a narrow problem and does not justify broad effort.

Outside the four areas there are 18 [C055] complaints, a share of 0.360000 [C058]. Most of that sits in `other/general`, which is generic negative feedback with 12 [C001] complaints and no specific product target, and in `catalog/lyrics`. Neither maps to one of the four areas, so I excluded them from the choice.

## Limitations
Reviews are self-selected public app-store text, not a random sample. Cancellation language is stated intent, not observed churn; there are 7 [C074] cancellation intent records. No revenue, churn, or causal effects are estimated here. Overall there are 100 [C071] completed records and 50 [C072] complaint or cancellation records. 0 [C073] records remain unresolved, pending, or quarantined, so these counts could change once they are resolved.
