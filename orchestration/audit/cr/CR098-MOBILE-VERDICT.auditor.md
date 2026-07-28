<!--
CR098-MOBILE-VERDICT.auditor.md — auditor lane file (track U owns). State derives
from round numbers here vs CR098-MOBILE-VERDICT.architect.md (see PROTOCOL.md).
-->

# CR098-MOBILE-VERDICT — audit lane (auditor)

**Item:** the terminal verdict card under `NO_VERDICT` (Amendment 2 — PM declines to price a
trade without a market read), plus the `opinions_not_included` closing disclosure on every action.

**Gate:** independent — paywall-adjacent disclosure surface; the DEF059 inversion class (a
professional refusal rendered as a rejection).

**Audited SHA:** `89d3f95` on `lane/CR098-MOBILE-VERDICT.coder.mobile` (two commits: `19f9acb`
parse, `89d3f95` render). Detached worktree, plus a second worktree at `origin/main` for the
"already safe" verification.

## Round 1

### Reproduced independently

| Check | Lane claimed | I measured |
|---|---|---|
| Scope (source) | 2 commits, verdict-card surface | **9 files +557/−9** (4 are generated l10n outputs of the ARB change) ✅ |
| Full `flutter test` | 143/143 | **143/143** ✅ (main 128 + 15 new) |
| `flutter analyze --no-fatal-infos`, 4 touched non-generated files | clean | **No issues found** ✅ |
| Mutations M2 + M5, re-derived | RED at exactly one test each | **M2 → RED at exactly the D3-inversion test; M5 → RED at exactly the malformed-list test** ✅; tree clean after reverts |

### The load-bearing claim is TRUE — "already safe on main", verified on main

The bridge's central premise is that the assign mis-scoped the risk: criteria 3–4 (all-null
levels render, and render absent) were already satisfied on `main` by accident. I ran the lane's
own acceptance #3/#4 tests against an **unmodified `origin/main`** worktree (test file reduced to
that group only, since the full file references the new getter): **3/3 pass**. The null-safety
was real, held by nothing, and is now held by tests. The lane's honest framing — "pinned, not
fixed" — is accurate, and the actual defect it found instead (amber + `Icons.cancel` for a
professional refusal) is the right defect.

### The four invited attack points

1. **"Already safe"** — verified above. Not wrong.
2. **`_blockingAnalystId` fallback** — I could not construct a live payload that reaches the
   `market_analyst` constant, and I traced both producers to confirm: `NO_VERDICT` is built only
   by `_assemble_no_verdict`, which requires `MARKET_ANALYST ∈ ctx.withheld`
   (`room_runner.py:2197`) and fills `opinions_not_included` from `ctx.withheld`; the post-loop
   `model_copy` (`room_runner.py:2349`) then overwrites the list on **every** path; and
   `_parse_pm_verdict` can never yield `NO_VERDICT` (enum comment + `_normalize_pm_action`). The
   fallback is dead code against the live backend. Not a finding.
3. **`pause_circle_outline`** — a reasonable neutral, distinguishable from PASS's
   `remove_circle_outline`. No disagreement; not scored.
4. **D4 weaker-than-worded test** — accepted. Empty-list vs absent-key is the comparison that
   matters: it covers existing users against a backend that has not deployed the field, which is
   the actual regression risk D4 names. A byte-diff against pre-change `main` would test the
   prettier property, not the important one.

### DoD table — rendered (despite the waiver) and spot-checked

Tests ✅ (reproduced), Manual verification honest (`NEEDS-DEVICE-CHECK`, promotion hold — not a
false N/A) ✅, Register (`CR098.row.md` stays `started`) ✅ verified, commit tags `(AT:R65 CR098)`
on both commits ✅ verified, scope discipline (`share_service.dart`, 2 lines, disclosed) ✅
verified in the diff. One imprecision, not scored: "5 files" in the Scope row vs 9 in the source
diff — the 4 omitted are generated l10n outputs, mechanical from the ARB change.

### Recorded, not scored

- **4 new `ar`/`ms` keys** added to the DEF137 packet (`roomVerdictActionNoVerdict`,
  `roomVerdictOpinionsHeading`, `roomVerdictOpinionsNote`, `roomVerdictIncludeAnalystCta`) —
  separate translation lane per convention; deliberately no list-grammar placeholder.
- **Nothing on a device or against melehost** — promotion hold; `NEEDS-DEVICE-CHECK`.
- **No live `NO_VERDICT` run** — payloads are hand-built from `_assemble_no_verdict`, read at
  the source and confirmed verbatim against `room_runner.py:1061-1081`.
- **The share card's rendered PNG** — accent input changed and mirrored by construction; the
  image itself was not captured. Acceptable at this gate; Saiful's acceptance test covers it.
- The third duplicate `_resetDateStr` — pre-existing duplication, correctly not refactored here.

**BLOCKER 0 · MAJOR 0 · MINOR 0**

**VERDICT: COMPLETE (round 1)** — the lane found its assign's premise false, proved it (and I
re-proved it on unmodified `main`), pinned the accidental safety with tests, and fixed the real
defect: a professional refusal no longer renders in the reject treatment, on screen or in the
shared image. The D3 disclosure is on every action and the inversion is held by a test that goes
red when gated (M2 re-derived). Wire-hardening (`whereType`) is mutation-proved (M5 re-derived).
The blocking-analyst fallback is unreachable from any live producer — traced, not assumed. Run
report `runs/2026-07-28_run-81/`.
