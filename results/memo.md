# Prioritize Usability on severity sum, while noting its lower mean severity

## Recommendation
Put next quarter's main product effort into Usability. It ranks first on severity sum (1 [C051]) and first on complaint count (1 [C053]), with a severity sum of 215962 [C055] across 82988 [C054] complaints. This is a severity-sum decision: Usability ranks fourth on mean severity (4 [C052]), so its complaints are not the most intense per report. Access ranks first on mean severity (1 [C073]) but fourth on severity sum (4 [C072]), so it is a targeted fix rather than the main bet.

## Evidence
Usability's weight comes from several issues. `usability/ads` ranks third overall (3 [C015]) with a severity sum of 66771 [C012] and 28991 [C011] complaints. `usability/general` ranks fifth (5 [C025]), `usability/ui_layout` sixth (6 [C030]), `usability/queue_playlist` seventh (7 [C035]), and `usability/shuffle_and_control` ninth (9 [C045]). Ad reviews describe too many ads and songs interrupting listening, and forced-playback reviews describe song selection being limited. These are self-selected public app-store text.

## Alternatives considered
Playback is second on severity sum (2 [C058]) and second on mean severity (2 [C059]), with a mean of 3.375797 [C063] across 42366 [C061] complaints. Its leading issue `playback/general` ranks fourth overall (4 [C020]), and its reviews describe playback starting or switching to a different song. Billing/support is third on severity sum (3 [C065]) but second on complaint count (2 [C067]), with 45504 [C068] complaints. Its leading issue `billing/subscription_entitlement` ranks second overall (2 [C010]) with a mean severity of 2.888237 [C008]. Access is fourth on severity sum (4 [C072]) and first on mean severity (1 [C073]), with 11455 [C075] complaints, led by `access/login_failure`, ranked eighth overall (8 [C040]). Access is a strong candidate for a focused reliability fix, but its smaller volume does not justify it as the main bet.

## Limitations
Reviews are self-selected public app-store text and do not represent the full user base. Cancellation-intent records (26366 [C086]) are stated intent, not observed churn, and no revenue, churn, or causal effect is estimated here. Of 660609 [C083] completed records, 296619 [C084] are complaint or cancellation records. Unresolved, pending, or quarantined records number 13 [C085], so the ranking may shift once they resolve. Outside the four areas holds 114306 [C079] complaints and sits outside this comparison.
