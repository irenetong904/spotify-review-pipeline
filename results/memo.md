# Prioritize Usability, led by ads and post-update UI complaints, while watching Billing/support growth

## Recommendation

Put next quarter's product effort into Usability, led by `usability/ads` and `usability/ui_layout`. Usability ranks first on severity_sum (1 [C051]) and first on complaint_count (1 [C053]), with a severity sum of 215962 [C055] across 82988 [C054] complaints. Its mean severity (2.602328 [C056]) ranks fourth (4 [C052]), so the case rests on volume and total severity rather than intensity per complaint. Because Usability is first on the baseline priority measure, no override is needed.

## Evidence

`usability/ads` is the third-ranked issue overall (3 [C015]), with 28991 [C011] complaints. Reviewers describe ads that are too frequent and unrelated songs playing in ad breaks (`45e2aab4-449c-4c23-83d0-69bd568a9e08`, `92bd7ff4-4322-4406-9033-f13e3079aa74`). `usability/ui_layout` ranks sixth (6 [C030]), and reviewers say recent updates removed loop and shuffle features and made the app worse (`141bd2c2-8403-45b8-ae65-6e9cfa24270b`, `e7747485-42c5-4bb9-b1e2-1b4044eedb5a`). `usability/general` covers autoplay overriding song choices (`f7ead10f-db26-479f-b2d7-411c2804f044`).

## Recent trend

In the first matched period, Usability complaints were 17976 [C091]; in the later period they rose to 32526 [C100], which is the highest of the four areas. Billing/support is the area whose complaints grew most among the four: they rose from 3788 [C088] to 30084 [C097]. Access moved from 2110 [C087] to 5460 [C096], and Playback from 12432 [C090] to 12506 [C099]. The recommendation still holds on the later-period ranking, but Billing/support is closing in and deserves a dedicated track. Complaint share of classified records rose from 0.301064 [C085] to 0.590511 [C094], and cancellation-intent records rose from 2789 [C086] to 16003 [C095]. These are observed changes; they are not attributed to any cause, and cancellation language is stated intent, not observed churn.

## Alternatives considered

Billing/support ranks second on complaint_count (2 [C067]) and third on severity_sum (3 [C065]). Its top issue, `billing/subscription_entitlement`, is second overall (2 [C010]), with reviewers objecting to features locked behind premium (`c917e047-2d4b-41c5-ad41-bc9355b6d6e4`). Playback ranks second on severity_sum (2 [C058]) and second on mean severity (2 [C059]), with a mean of 3.375797 [C063]. Its `playback/general` issue ranks fourth (4 [C020]), and reviewers report wrong or stalled audio (`557527a9-d504-4387-a2e5-47d80048747c`). Access ranks first on mean severity (1 [C073], mean 3.890877 [C077]) but fourth on severity_sum (4 [C072]) with only 11455 [C075] complaints. Its `access/login_failure` issue ranks eighth (8 [C040]), though login failures are severe for affected users (`97be5642-eab6-45f4-9c08-3aa28cc8e8ac`, `663a93eb-c77a-4b86-a883-c98889ac5f11`).

## Limitations

Reviews are self-selected public app-store text and do not represent all users. 13 [C103] records were quarantined for empty review text, and 0 [C104] records remain unclassified. Of 660609 [C101] completed records, 296619 [C102] were complaint or cancellation records. Complaints outside the four areas total 114306 [C079], mostly general dissatisfaction (1 [C005] rank), which is not an actionable area. Cancellation language is stated intent, not observed churn, and no revenue effect is estimated.
