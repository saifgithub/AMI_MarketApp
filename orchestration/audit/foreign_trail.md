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
| 2026-09-01 | DEF392 | — | — | coder | ami-vllm/qwen3.8-flash-next | — | lane DEF392 launched |
| 2026-09-01 | DEF367-LESSONS | — | — | coder | ami-vllm/qwen3.8-flash-next | — | lane DEF367-LESSONS launched |
| 2026-09-01 | DEF382 | — | — | coder | ami-vllm/qwen3.8-flash-next | — | lane DEF382 launched |
| 2026-09-01 | BATCH-R75 | f8be15e2 | r1 | auditor | kimi-code/k3 | ADVISORY-CONCERNS | 3 findings, dispositions pending |
| 2026-09-01 | BATCH-R75 | 383e60f16a2f83f91432f83d63ffb60ac2c14c60 | r2 | auditor | kimi-code/k3 | ADVISORY-CONCERNS | 4 findings, dispositions pending |
| 2026-09-01 | BATCH-R75 | 6127c6e4570f406d0bf3e8cd2a4d2b1c5d811467 | r3 | auditor | kimi-code/k3 | ADVISORY-CONCERNS | 5 findings, dispositions pending |

## BATCH-R75 — first full MHBP round (2026-09-01, AT:R75)

Batch: DEF392 (backend) + DEF367 (backend tests) + DEF382 (mobile). Tier B. Base `7c07dc5b`.

| date | item | sha | round | role | model | findings | disposition | correlated-error catch |
|---|---|---|---|---|---|---|---|---|
| 2026-09-01 | DEF392 | 7416051f | — | coder | ami-vllm/qwen3.8-flash-next | — | landed after 1 architect correction (self-reference trap in its own guard) | — |
| 2026-09-01 | DEF367 | 30d3ff37 | — | coder | qwen3.8 (cut at 58m, 0 files) → claude-sonnet-5 | 3 of 6 surfaces closed | 3 remaining diagnosed as `discover_pairs.py` instrument bugs, verified true | — |
| 2026-09-01 | DEF382 | 4e91fd3b | — | coder | ami-vllm/qwen3.8-flash-next (resumed) | — | ran to natural finish; declined to claim the device acceptance | — |
| 2026-09-01 | BATCH-R75 | f8be15e2 | r1 | auditor (binding) | claude-opus-4-8 | **0** | COMPLETE (round 1) — and 2 FALSE assertions | **missed both** |
| 2026-09-01 | BATCH-R75 | f8be15e2 | r1 | auditor (foreign) | kimi-code/k3 | 3 | **3 real, 0 false-divergence, 0 noise** | **DEF394** |
| 2026-09-01 | BATCH-R75 | 383e60f1 | r2 | auditor (binding) | claude-opus-4-8 | 0 + 1 dismissed as "benign" | COMPLETE (round 2); dispositioned r1 as 3 real | dismissed the chain drain the foreign leg called real |
| 2026-09-01 | BATCH-R75 | 383e60f1 | r2 | auditor (foreign) | kimi-code/k3 | 4 | **4 real** (2 of them defects the ARCHITECT introduced while fixing r1) | **DEF395 (d)+(e)** |
| 2026-09-01 | BATCH-R75 | 6127c6e4 | r3 | auditor (foreign) | kimi-code/k3 | 5 | **5 real**, 0 blocking; both r2 fixes survived attack | corrected the architect's own register prose and supplied a working behavioural pin |

**Score: foreign 12 findings, 12 real, 0 false. Binding gate 0 findings, 2 false assertions, 1 real
issue dismissed as benign.** Cost: gate ~$30 over two rounds; foreign $0 (flat-rate subscription).

**What this round actually establishes (and what it does not).** It is the first measured
correlated-error catch, and the mechanism was visible: DEF392's row, the lane brief, the coder's
implementation, its test docstring and commit message, the architect's mutation test AND the
architect's own audit brief all framed the defect as *"the OpenAI-compatible default"*. Five
artifacts, one framing, one blind spot — and `AnthropicProvider`, a sibling class, sat outside every
one of them. The foreign auditor named the cause unprompted.

**It does NOT settle the tier.** n=1 batch. Round 1's binding gate was handicapped by the architect's
own brief, which scoped it into the same blind spot; that is an architect error, not a model result.
Foreign finding quality also rose as the briefs got more specific — r3's most valuable output (a
working behavioural pin for a guard the architect had disclosed as unpinnable) came directly from
disclosing that weakness in the brief. An unbriefed always-on watcher would look like r1, not r3.
Needs N>=5 before any of this hardens into doctrine.

**Process failures worth carrying into the next round, all architect-side:** the audit was not
started until prompted; the r1 brief omitted the mandatory foreign-disposition step
(AMI_TRADE_BINDINGS gap-fill 9), so the gate never read the findings; the two legs ran concurrently
and the gate read the foreign branch before it was committed; and fixes were committed while r2 was
auditing, so its COMPLETE describes a tree that no longer exists.
