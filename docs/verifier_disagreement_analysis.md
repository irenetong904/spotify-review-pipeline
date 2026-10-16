# Verifier disagreement analysis (full run)

**Setup.** Claude Haiku 5.5 re-labeled a stratified random sample of 2,026 distinct reviews from the original text
and rubric only, without seeing the Jev labels ([results/verify_report.json](../results/verify_report.json)). Code
compared the two label sets ([results/verify_disagreements.csv](../results/verify_disagreements.csv),
[results/verifier_labels.jsonl](../results/verifier_labels.jsonl)). The verifier is a second opinion, not ground
truth; where the shared definitions decide a case, that is noted below.

| field | disagreements / 2,026 | agreement |
|---|---|---|
| topic | 265 | 86.9% |
| intent | 232 | 88.6% |
| severity (any difference) | 326 | 83.9% exact, MAE 0.17 |

## What the disagreements are

Counts are from the full sample; the categories come from reading 36 disagreements in a fixed hash order (review IDs
are listed so each judgment can be checked).

**1. Praise of a specific feature labeled `other` (topic).** The most common topic pairs are other→catalog (31),
other→usability (25) and other→playback (19). Typical: "All the music I love here" (`b7a092aa`), "It's great how many
old songs you can bring out" (`3c3ea2e2`), "We can play the songs we like" (`94f56186`). The shared rule says the first
*specific* praised feature decides the topic, so the verifier is usually right here. Effect on the business result:
none — praise is excluded from the complaint ranking.

**2. Premium-only controls: billing vs usability/playback (topic).** usability→billing (22), billing→usability (11),
e.g. "they removed play by order ... bring back it" (`3954a027`), "can't even shuffle a particular song, we don't
want to buy premium" (`55e82c10`), "everything in Spotify is premium even we cannot play any music" (`0a609aeb`).
The contract puts *explicitly premium-only controls* under billing, but reviews often mix a removed control with a
price complaint. This is the boundary that most affects Usability vs Billing/support totals (see sensitivity below).

**3. Cancellation under-detected by Jev (intent).** complaint→cancellation (19): "worst from best, uninstalling"
(`c4a8d123`), "I uninstalled this app" (`9e37037d`). These are explicit departures that the cancellation Noul scored
below the 0.5 threshold. The reverse (13) is mostly boycott slogans: "Boycott this app ... plz boycott" (`4eb2a6b0`) —
the contract makes bare boycott slogans `unclear`, so the verifier is right there too. Net: cancellation intent
(26,366) is, if anything, slightly undercounted; it is reported as stated intent only.

**4. Mixed praise and criticism labeled praise (intent).** "liked the app ... but didn't have all of the songs, a bit
disappointing" (`d898ea80`). The contract says mixed praise/criticism is a complaint; the verifier follows it.

**5. Request vs complaint (intent).** complaint→request (22) and request→complaint (20): "should add more Bollywood
songs ... 40% isn't available" (`b0987e23`), "where is kannada browse list ... add kannada" (`26548fd3`). A wish that
also reports missing content sits on the boundary between "desired change" and "reported failure".

**6. Unintelligible, profane or non-English text (intent).** complaint→unclear (40), praise→unclear (28):
single-word insults and short non-English phrases. Both models are weakest here, as TypeSafe documents for
non-English text.

**7. Severity is systematically higher from Jev.** Of 326 severity differences, Jev is higher in 242 and lower in 84;
the most common pairs are 3→2 (118), 2→1 (63) and 4→3 (43). Clear over-assignments: "new update. loss your market"
labeled severity 5 (`15bab051`); "i can not download this app" labeled 4 (`5ddf8328`). This is why the memo's evidence
pack uses representative (near-mean, not flagged) reviews instead of the most severe ones.

## Does it change the recommendation?

Sensitivity check ([results/severity_sensitivity.json](../results/severity_sensitivity.json)): for complaint and
cancellation reviews in the sample, compare the mean severity each model gives to the *same* reviews in each area,
and scale the full-run severity sum by that ratio.

| area | sample n | Jev mean | verifier mean | full-run severity sum | verifier-calibrated | complaints |
|---|---|---|---|---|---|---|
| Usability | 329 | 2.64 | 2.49 | 215,962 | 203,288 | 82,988 |
| Playback | 174 | 3.35 | 3.20 | 143,019 | 136,641 | 42,366 |
| Billing/support | 198 | 2.80 | 2.54 | 128,973 | 116,889 | 45,504 |
| Access | 46 | 3.87 | 3.76 | 44,570 | 43,318 | 11,455 |

The order of the four areas is the same under the full-run severity sum and the verifier-calibrated one
(Usability > Playback > Billing/support > Access). By complaint count alone, Billing/support moves above Playback,
and Usability is still first. The recommendation does not depend on the severity bias. The Playback-vs-Billing
second place does depend on the measure, which the memo states as an alternative.

## What would be done next with more budget

- Re-ask only the cancellation Noul with a lower threshold for reviews containing "uninstall"/"switch" terms (cheap,
  code-routed), or route those to the verifier.
- Add two worked examples per boundary above (premium-only controls; mixed praise) from development data.
- Route low-confidence non-English reviews to the verifier as a declared fallback fraction.
