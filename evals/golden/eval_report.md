# Golden-50 evaluation

Predeclared: sentiment tolerance ±0.5; missing/quarantined = incorrect.

| metric | value |
|---|---|
| n | 50 |
| completed_predictions | 50 |
| missing_or_quarantined | 0 |
| ambiguous_cases | 2 |
| topic_agreement | 0.8 |
| topic_agreement_lenient_alt_topic | 0.8 |
| intent_agreement | 0.92 |
| severity_exact | 0.88 |
| severity_mae | 0.12 |
| sentiment_within_0_5 | 0.92 |
| sentiment_mae | 0.1762 |
| quote_exact_substring_rate | 1.0 |
| entities_unsupported_total | 0 |
| entities_missed_total | 5 |

### topic confusion (rows = human, columns = pipeline)

| human \ pred | access | usability | playback | downloads | catalog | billing | support | other |
|---|---|---|---|---|---|---|---|---|
| access | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| usability | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 2 |
| playback | 0 | 1 | 4 | 0 | 1 | 0 | 0 | 0 |
| downloads | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| catalog | 0 | 0 | 0 | 0 | 4 | 0 | 0 | 2 |
| billing | 0 | 2 | 0 | 0 | 0 | 1 | 0 | 0 |
| support | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| other | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 24 |

### intent confusion (rows = human, columns = pipeline)

| human \ pred | complaint | request | praise | cancellation | unclear |
|---|---|---|---|---|---|
| complaint | 20 | 0 | 0 | 0 | 0 |
| request | 0 | 2 | 0 | 0 | 0 |
| praise | 1 | 1 | 20 | 0 | 1 |
| cancellation | 0 | 0 | 0 | 2 | 0 |
| unclear | 0 | 1 | 0 | 0 | 2 |

### severity confusion (rows = human, columns = pipeline)

| human \ pred | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| 1 | 26 | 1 | 0 | 0 | 0 |
| 2 | 1 | 8 | 1 | 0 | 0 |
| 3 | 0 | 2 | 7 | 1 | 0 |
| 4 | 0 | 0 | 0 | 3 | 0 |
| 5 | 0 | 0 | 0 | 0 | 0 |

needs_review (human vs predicted): {'human=False,pred=False': 40, 'human=False,pred=True': 2, 'human=True,pred=False': 5, 'human=True,pred=True': 3}

## Disagreements

| review_id | field | human | pipeline | human note |
|---|---|---|---|---|
| `292ce26a-815d-4bce-a3b6-93cb6c9e7e2c` | topic | catalog | other | Content is described as being banned/removed, so catalog; negative criticism mak |
| `292ce26a-815d-4bce-a3b6-93cb6c9e7e2c` | severity | 3 | 2 | Content is described as being banned/removed, so catalog; negative criticism mak |
| `b5ee7834-a0eb-4c15-9c7b-935831021922` | topic | catalog | other | Diversity most naturally refers to breadth of content/catalog. |
| `1fc8b08f-7d6a-472f-b317-8ceb28d00f22` | topic | billing | usability | Premium is only mentioned; the specifically praised feature is the ad-free exper |
| `723f07de-9881-4049-8680-1a9e25652914` | topic | support | playback | The old issue is a every-time crash (severity 4). Support resolved it, so sentim |
| `723f07de-9881-4049-8680-1a9e25652914` | intent | praise | complaint | The old issue is a every-time crash (severity 4). Support resolved it, so sentim |
| `fc344263-308d-48a1-9715-c380d063b6de` | intent | praise | unclear | Generic praise. |
| `ac6cd66d-a9d2-42a4-afb8-2f84beff7fd1` | intent | praise | request | Tagalog/Filipino phrasing interpreted as saying all kinds of songs are on Spotif |
| `46842184-32f8-4088-ac15-2a700a7e94ed` | severity | 3 | 2 | Indonesian slang; interpreted as complaining that lyrics are sometimes unavailab |
| `5de7f95b-ccad-41b2-9f63-a13f7c1d9f09` | severity | 1 | 2 | Per the stated rule, a pure boycott slogan is unclear rather than cancellation. |
| `372d4e67-59cc-4c54-879f-3e8a202ee554` | severity | 2 | 1 | Hinglish request to reduce ads, but it reports a negative ad experience first un |
| `46c0b49f-83a1-427e-8f0b-cef62e3c94b5` | topic | playback | usability | Audio-volume behavior occurs during playback; serious annoyance/risk but not one |
| `283b5843-a992-464f-b1dc-9dc7281ff390` | topic | other | billing | Meaning is too unclear to identify a reliable product issue or intent. |
| `283b5843-a992-464f-b1dc-9dc7281ff390` | intent | unclear | request | Meaning is too unclear to identify a reliable product issue or intent. |
| `2aa566c6-b98d-4513-b900-83702a8db8eb` | topic | usability | other | Specifically praises low ad frequency. |
| `8c0546b0-ce43-4a36-9d33-9f979e98d522` | topic | playback | catalog | Lyrics issue and playback-control issue are both severity 3; tie goes to the fir |
| `ac4e860a-c042-49cc-90f3-189591c336ac` | severity | 3 | 4 | The broken function is offline mode (downloads); payment context makes billing a |
| `d2f3874f-d15d-4a2f-bb97-4f1213defa46` | topic | billing | usability | Price complaint and ad complaint are both severity 2; tie goes to the first-ment |
| `d2f3874f-d15d-4a2f-bb97-4f1213defa46` | severity | 2 | 3 | Price complaint and ad complaint are both severity 2; tie goes to the first-ment |
| `99b93e31-9f15-4daa-88ac-349ab0419c48` | topic | usability | other | Criticizes the update; the implied wish for the old version comes after the comp |
