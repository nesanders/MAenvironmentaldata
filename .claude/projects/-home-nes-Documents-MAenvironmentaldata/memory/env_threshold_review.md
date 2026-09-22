---
name: env-threshold-review
description: Pending task to revisit environmental relevance threshold after GC fix re-embed, with documented artifact
metadata:
  type: project
---

After the GC formula fix and full re-embed (May 2026), the environmental bill count jumped from 329 → 654 at threshold=0.05. This needs a calibration review.

**Task:** Re-run the threshold analysis — plot the score distribution, spot-check bills near the new boundary, and decide whether 0.05 is still correct or needs adjustment. Document the exercise in a written artifact (analysis page or data note) explaining: the differential cosine similarity method, the reference sets, how the threshold was chosen, and what the before/after counts were at various thresholds.

**Why:** The doubling of env bill count is plausible (correct body text adds real signal) but should be verified with spot-checks. Some new bills at 0.05–0.08 may be genuine env bills the old wrong-GC embeddings missed; others may be false positives from body text that semantically resembles env topics without being env legislation.

**Related:** [[project_data_pipeline]] — score_lobbying_bills.py ENV_THRESHOLD constant; [[ai_analysis_feature]] — env bill counts flow into the AMEND.db and dashboard.
