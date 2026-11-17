# Corrections

Every change to a published label or a published trap is recorded here. Answers are never
edited; only labels, traps and their evidence change, and the reason is written down.

Format: date, item, what changed, why, and who reviewed it.

## 2026-11-17 - initial release

* **Scoring rule change (pre-release):** the refusal pattern did not match contracted forms such
  as "I'm not able to answer questions about that topic", so the gold-set answer `g057` was
  scored `WRONG` instead of `REFUSED`. The pattern was widened to `\b(?:not able|unable) to
  (?:help|assist|comply|answer|provide)\b`. The gold label was not changed. Agreement went from
  59/60 to 60/60. Recorded because a change made after seeing a mismatch belongs in the log,
  even when it happens before the first release.
* **Generator change (pre-release):** book titles beginning with a vowel used "A" ("A Unwritten
  Moth"); they now use "An". Scientific-term roots that ended in `-ine` produced doubled
  suffixes ("solverineine"); the root pool was corrected. The day was regenerated and every
  trap was re-verified against all four sources.
* **Demo data notice:** the first published run uses synthetic mock models. No real model
  answers exist yet, so no real-model label has been published or corrected.
