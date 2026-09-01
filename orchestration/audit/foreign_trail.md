# Foreign audit trail (CR215)

Pre-registration ledger for the foreign (non-Claude) tier. One row per run, appended by
`dispatch_foreign_audit.sh` (auditor) and `dispatch_launch.sh` (coder, `TIER=local`).

**Why this exists.** MHBP §9/§10: predictions are logged *before* each run so neither outcome can be
rationalised afterwards, and **N ≥ 5** before any kept/killed call. The headline metric is
**correlated-error catches** — real defects the all-Claude review missed. The counter-predictions this
ledger has to be able to falsify: the foreign model false-alarms at a rate that drowns the signal
(`noise`); its divergences are model-quirk rather than substantive (`false-divergence`); or it simply
misses what Claude catches, in which case the tier is additive insurance or nothing at all.

**Dispositions are written by the Claude auditor, not by the foreign tool** — the launcher records
`dispositions pending` and the auditor amends the row when it has classified each finding.

A row reading `UNAVAILABLE` is a real observation, not a gap: it means the tier did not run, and it
must never be read as the foreign auditor having been satisfied (DEF059).

| Date | Item | SHA | Round | Role | Model | Foreign-verdict | Findings / dispositions |
|---|---|---|---|---|---|---|---|
| 2026-09-01 | DEF389 | 94a86e77 | r1 | auditor | — | — | UNAVAILABLE: kimi exited 1 without committing |
| 2026-09-01 | DEF389 | 94a86e77 | r1 | auditor | kimi-code/k3 | ADVISORY-CONCERNS | 4 findings: **4 real, 0 false-divergence, 0 noise**. 1 correlated-error catch -> DEF391 (fixed, mutation-proved). 2 latent -> DEF392 (open). 1 accurate framing nit, no action. |
