# Golden-label corrections (disclosure)

The human labels were frozen on 2026-10-14 (`golden_50_human_labels_v1_frozen.csv`, sha256 in
`golden_50_human_labels_v1_frozen.sha256`) before any pipeline prediction existed. After the first evaluation
(q4, `runs/golden50`), the labeler reviewed the disagreement list and corrected **2 labels whose own `notes`
contradicted the recorded label** (clerical slips). No other label was changed, and the corrections were
not used for any prompt, threshold, rubric or grouping change.

| review_id | field | before | after | reason (labeler's own note) |
|---|---|---|---|---|
| 215463ae-95b7-4481-8747-1754b68f31fa | topic | access | playback | "Both inability to play and inability to open the app fall under playback" |
| 215463ae-95b7-4481-8747-1754b68f31fa | intent | request | complaint | review reports failures (cannot play / open), so it is not a pure request |
| 99b93e31-9f15-4daa-88ac-349ab0419c48 | intent | request | complaint | "Criticizes the update; the implied wish ... comes after the complaint" |

Both versions are evaluated and reported: `v1_frozen_labels/eval_results.json` (original labels) and `eval_results.json`
(corrected). The README reports both.
