# Playback has the highest mean severity among the four areas and should lead next quarter's effort, with billing/support fixes as a close second.

## Recommendation

Prioritize Playback next quarter. Playback accounts for 652 [C059] complaints with a severity sum of 2198 [C060] and a mean severity of 3.371166 [C061], the highest mean severity of the four areas. Its top issue, `playback/general`, has 241 [C016] complaints and mean severity 3.435685 [C018], and `playback/stops_pausing` adds 111 [C041] complaints with mean severity 3.396396 [C043].

## Evidence

Billing/support is the largest in-scope area by severity sum (2123 [C064]) with 750 [C063] complaints, and its top issue `billing/subscription_entitlement` ranks second overall with 492 [C006] complaints. Usability is the largest area by volume (1288 [C055] complaints, severity sum 3344 [C056]), but its mean severity is 2.596273 [C057]. Access has the highest mean severity of all (3.877907 [C069]) yet only 172 [C067] complaints, and its issue `access/login_failure` has mean severity 3.969072 [C038]. Playback reports are concrete: review `40abba11-6cce-4eff-ae74-9ec4579550e0` describes the app closing while songs play, and review `10878c3f-c43e-43cb-86fe-c993b56403cc` describes playback failing at different times.

## Alternatives considered

Usability has the largest volume but a lower mean severity than Playback, so it is a strong second candidate. Its largest issue, `usability/ads`, has 448 [C011] complaints and mean severity 2.301339 [C013], and review `ee11e1df-cb73-4c3a-b5e8-7268c7872b01` describes ad interruptions in the free tier. Billing/support has the highest in-scope severity sum and a clear subscription-entitlement problem in `billing/subscription_entitlement`, with 2.906504 [C008] mean severity; review `e51bcefb-8071-4e36-9c57-87281443bd29` describes a purchase that was not approved. Access is the smallest area by volume, though its per-complaint severity is the highest, so it is worth monitoring but is not the largest pool of user harm.

Much of the overall volume sits outside the four areas (1669 [C051] complaints, share 0.368351 [C054]), mostly in `other/general`, which has 1469 [C001] vague complaints. Those reviews are too general to assign to a product area, so they should be triaged before any reallocation.

## Limitations

Reviews are self-selected public app-store text, not a representative sample. Cancellation language reflects stated intent, not observed churn, and cancellation intent appears in 397 [C074] records. The dataset covers 10000 [C071] completed records, of which 4531 [C072] are complaint or cancellation records. Unresolved, pending, or quarantined records number 0 [C073], so no records are excluded for that reason. This memo does not estimate revenue impact or causal effects.
