# Interruption / resume evidence (full corpus run)

- Recording: [resume_demo.mp4](resume_demo.mp4) (7 min 45 s, compressed from the original 227 MB screen recording, 10 fps).
- `checkpoint_before.json`: 140,796 completed IDs saved when the full run was interrupted with Ctrl-C
  (session `enrich-20261014T200223-6e591a`, stop_reason `interrupted`; 4,065 Jev calls, 8,492 result-cache hits
  from same-config dev runs, the rest exact-text reuse).
- Resume: the same command restarted as session `enrich-20261014T200706-43e659`, phase `resume`,
  "already completed: 140796", 471,632 distinct texts still pending (= 484,189 - 4,065 - 8,492).
- Check at 1,956 resume-phase enrich calls: **0** of their review IDs were in checkpoint_before (no paid relabeling).
- `checkpoint_after.json` is written from the final state after the run completes.

Failure found during the recording (and fixed): after Ctrl-C the enrich stage saved correctly, but the old
orchestrator continued into the verify stage on the partial corpus (189 verify calls, about $0.03, results
discarded). Fix (commit 53abca7): the pipeline now stops after an incomplete enrich and prints a resume hint.
