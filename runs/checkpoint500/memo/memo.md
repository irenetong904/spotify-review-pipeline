# Prioritize Usability next quarter, focused on ads load and the new layout

## Recommendation
Put next quarter's product effort into Usability. Its issues carry the largest total severity among the four named areas: 173 [C056] across 66 [C055] complaints, a share of 0.273859 [C058] of complaints. Scope the work narrowly to ad load and the new layout first.

## Evidence
Usability leads on total severity: 173 [C056] versus Playback at 147 [C060], Billing/support at 117 [C064], and Access at 40 [C068]. Within Usability, `usability/ads` accounts for 21 [C016] complaints with a severity sum of 48 [C017], and `usability/ui_layout` accounts for 14 [C021] complaints with a severity sum of 41 [C022]. The broader `usability/general` bucket (16 [C026] complaints) is fragmented and should be triaged rather than targeted directly.

The single largest issue is `other/general` (66 [C001] complaints, severity sum 134 [C002]), which sits outside the four areas. It is too vague to act on directly, and it is excluded from this comparison.

## Alternatives considered
Playback is the strong second option: 43 [C059] complaints, severity sum 147 [C060], and a mean severity of 3.418605 [C061], which is higher than Usability's 2.621212 [C057]. Its issues are concrete defects, including `playback/general` (15 [C011] complaints), `playback/connectivity` (8 [C036] complaints with mean severity 3.375000 [C038]), and `playback/stops_pausing` (7 [C041] complaints). If leadership weights severity per complaint over volume, Playback is the better choice.

Billing/support has 40 [C063] complaints and a severity sum of 117 [C064]. Its top issue, `billing/subscription_entitlement` (29 [C006] complaints, severity sum 88 [C007]), concerns premium-gated features, such as Canvas being unavailable after an update. That is a product entitlement question more than a support-queue problem.

Access has the highest mean severity (4.000000 [C069]) but only 10 [C067] complaints and a share of 0.041494 [C070]. Its main issue, `access/login_failure`, has 6 [C046] complaints. It is severe per case but too small to lead the quarter.

## Limitations
Reviews are self-selected public app-store text, not a random sample. Cancellation language (22 [C074] cancellation-intent records) reflects stated intent, not observed churn, and this memo estimates no revenue, churn, or causal effects. Of 500 [C071] completed records, 241 [C072] are complaint or cancellation records, and 0 [C073] are unresolved or quarantined, so no pending records are excluded. Severity values are saved scores. Usability and the outside-the-areas group are tied on severity sum, so the ranking depends on how the grouping is defined.
