# CR251 — analysis_r5: disposition-vs-sub-cap isolation (FINAL)

**Arms** (all dsv4, R5, n=3 per ticker, 11 size-sensitive tickers, review OFF):
- uncapped production prompts (from the main arm, n=2): 5/22 approvals (23%)
- `cr253-subcap` = production PM + disposition table + sub-cap conditional: 13/33 (39%)
- `cr253-disposition` = production PM + disposition table only: **16/33 (48%)**

## The isolation answer

**The disposition table alone drives the entire willingness shift** — it
matches and slightly exceeds the combined variant. The sub-cap conditional
contributes nothing measurable and is removed from the fold-in candidate.

**Sub-cap sizing is spontaneous model behavior, not instruction-following.**
Below-cap approvals: 2/13 in the instructed arm (3.5%, 4.5%), 2/16 in the
UNINSTRUCTED disposition arm (2.5%, 2.0%), 2/78 in the cap-1% backend-default
arm (0.5%, 0.7% — NKE, SLB). dsv4 sub-caps ~13–15% of approvals unprompted.
A prose conditional cannot raise that rate; policy-level sub-cap sizing must
be computed and enforced structurally (CR255 C8 direction), never narrated.

**Stability is untouched by both variants.** Per-name wobble persists at n=3
(DE A/P/P, DHR A/P/A, MO P/A/A, PYPL P/P/A in the disposition arm). Prompt
prose moves the LEVEL of willingness, not the CONSISTENCY — reinforcing the
CR255 position that stability requires the measured bar / deterministic gate.

## Per-ticker final (disposition-only)

JPM A/A/A · DHR A/P/A · WFC A/P/A · LEVI P/A/A · MO P/A/A · TMO A/P/P ·
BAC P/P/A · DE A/P/P · SO P/A/P · PYPL P/P/A · CAG P/P/P.
New recoveries vs uncapped: DHR 0→2/3, WFC 1→2/3, JPM 1→3/3, LEVI 0→2/3,
DE 0→1/3, BAC 0→1/3. CAG stayed out (grounded balance-sheet case — correct).

## Standing position for CR253 / CR255

1. **Fold-in candidate = disposition table only.** Pending: ami-llm control
   arm (hourly watcher; DGX ~2 days out) + the full CR253 acceptance
   benchmark (LEVI/DHR/APD/PYPL × R1–R5 × 3 + RIOT holdout) — the R5-only
   probe above is supportive evidence, not the acceptance run.
2. **Sub-cap feature → respec under CR255 C8** as a structural sizing
   computation (size from measured evidence, enforced arithmetically).
3. **Acceptance caveat for the full run:** the willingness shift cuts both
   ways — with discrimination still negative (analysis_r3), more full-size
   approvals means more exposure to weak-evidence approvals. The disposition
   fold-in should ship together with or after the C7 evidence mechanism, not
   before it.
