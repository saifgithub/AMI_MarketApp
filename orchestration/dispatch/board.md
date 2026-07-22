<!--
board.md — Architect-owned glanceable dispatch board (DISPATCH_PROTOCOL.md §8.6). Regenerable via
`sh orchestration/dispatch/dispatch.sh state`. May lag real state — detect truth from the lane tokens, never
from this table. CR052.
-->

# Dispatch board

## Roster (9 instances I control + the Auditor gate)

| Instance | Role / kind | Owns / feeds | Auditor |
|---|---|---|---|
| `coder.api` | coder | backend/app (ex trading_math + room); **schema owner**; safety_floor/mandate | auditor.core |
| `coder.room` | coder | room debate cluster | auditor.core |
| `coder.mobile` | coder | mobile/lib | auditor.core |
| `coder.web` | coder | website + website_api (island) | auditor.core |
| `coder.math` | coder | trading_math + CR046 ledger | auditor.core |
| `coder.store` | coder/liaison | store scripts/fastlane/native config | auditor.core |
| `noncoder.edu` | non-coder / maintainer | content corpus data | content review |
| `noncoder.errors` | non-coder / requester | bug_reports → DEF drafts | — |
| `noncoder.gtm` | non-coder / requester | GTM → CR drafts | — |
| *(gate)* `auditor.core` | auditor | existing track-U loop; gates all coders | — |

## Lanes (regenerate: `sh orchestration/dispatch/dispatch.sh state`)

| Item | State | Instance | Notes |
|---|---|---|---|
| ~~CR054-W0a~~ | **DONE ✓ (r1)** | coder.api → auditor.core | **Integrated. 4 tracks wired, audited COMPLETE (72a9403), archived → history/lanes. Unblocks W0b. Awaiting Saiful acceptance** |
| DEF062 | ASSIGNED r1 (idle) | coder.api | validate mandate PATCH — head of safety chain; no worker yet |
| CR038 | ASSIGNED r1 (seed) | coder.room | remove macro/Fed scaffolding at source |
| CR048 | ASSIGNED r1 (seed) | coder.store | Play internal track + fastlane (first upload Saiful-gated) |
| CR049 | ASSIGNED r1 (seed) | coder.web | website support + Concierge (keys/deploy Saiful-gated) |
| CR050 | ASSIGNED r1 (seed) | coder.mobile | login UX (mobile half; Google-on Saiful config) |
| ~~CR054-W0b~~ | **DONE ✓ (r1)** | coder.mobile | new-track short labels audited COMPLETE; Wave 0 fully done |
| ~~CR054-W0c~~ | **DONE ✓ (r1)** | noncoder.edu | author-prompt v2 accepted (Saiful); archived. Now the Wave-1 authoring standard |
| ~~CR054-W0d~~ | **DONE ✓ (r1)** | coder.math → auditor.core | CR046 math M09–M12 audited COMPLETE (200f127), archived. Unblocks ASST/MACRO/QUANT lessons |
| ~~CR054-W1-ETHIC~~ | **DONE ✓ (r2)** | noncoder.edu | 10 Ethics lessons (ETHIC 1-10, 293-302) integrated 32eac8a, corpus→280 |
| ~~CR054-W1-ASST~~ | **DONE ✓ (r1)** | noncoder.edu | 20 Asset lessons (ASST 1-20, 303-322) integrated ff4978c, corpus→300, P2 exact |
| ~~CR054-W1-MACRO~~ | **DONE ✓ (r1)** | noncoder.edu | 12 Macro lessons (MACRO 1-12, 323-334) integrated b4a30e5, corpus→312, P2 exact |
| ~~CR054-W1-QUANT~~ | **DONE ✓ (r1)** | noncoder.edu | 12 Quant lessons (QUANT 1-12, 335-346, L12) integrated 680a8f3, corpus→324, P2 hand-verified. **Wave-1 lesson tracks COMPLETE** |
| ~~CR059~~ (backend) | **DONE ✓ (r1)** | coder.api → auditor.core | islamic_finance/SHARIA + decision_evaluation/EVAL wired (a63d1c5); auditor COMPLETE (927 pass + blind probe). 13-facet taxonomy locked |
| ~~CR059-MOBILE~~ | **DONE ✓ (r1)** | coder.mobile | `_trackShortLabel` ISLAMIC FINANCE/EVALUATION wired (f188d7b), flutter analyze clean. **CR059 fully DONE** |
| ~~CR058-MATH~~ | **DONE ✓ (r1)** | coder.math → auditor.core | `screening.py` (CR046 M13) integrated 21fb8b6; auditor COMPLETE (hand-recompute + 68+22 green). Unblocks CR058-CONTENT |
| ~~CR058-CONTENT~~ | **DONE ✓ (r2)** | noncoder.edu | 10 Sharia lessons SHARIA 1-10 (347-356) integrated, corpus 324→**334**. P2 via screening.py, frame in every lesson |
| ~~CR058-SUPPORT~~ | **DONE ✓ (r1)** | noncoder.edu | 20 islamic_finance glossary (188→208) + 15 Q&A + 10 daily (2026_12) integrated 5ebfef4; content review PASS (P2 exact, frame verified, 32 green). **CR058 FULLY CLOSED** (math+lessons+support) |
| ~~CR053-BE~~ | **DONE ✓ (r1)** | coder.api → auditor.core | `{{lesson:}}` token + resolve guard integrated 36314f4; auditor COMPLETE (257587d) — blind probe proved the guard bites, 41 green. Lean AUDIT_TESTS audit (no 828s trap). Unblocks MOBILE+MIGRATE |
| **CR053-MOBILE** | **ASSIGNED r1 → launching** | coder.mobile → auditor.core | `{{lesson:}}` chip + prereq render/link + tappable gateway rows. Ships render branch BEFORE MIGRATE content reaches users |
| CR053-MIGRATE | **held (DEPENDS-ON BE; run after MOBILE)** | noncoder.edu → review | migrate 238 lesson + 41 daily bare refs → tags/codes (scripted + guard) |
| **CR061** (proposed) | **QUEUED — quick wins** | architect | verify helper + audit-launch helper + test-timeout wrapper (828s) + roster live_handle fix |
| CR030 | UNASSIGNED (re-queued) | coder.api | earnings/dividend — re-queued behind CR054 Wave 0 to free a slot |
| DEF061 | UNASSIGNED (queued) | coder.api | enforce 4 mandate toggles — DEPENDS-ON DEF062 |
| CR026 | UNASSIGNED (queued) | coder.api | sector enforcement — DEPENDS-ON DEF061 (safety_floor hot) |
| CR020 | UNASSIGNED (queued) | coder.api | concierge full-context — head of CR020→021→022 |

**Idle/available:** `coder.math`, `coder.api` (DEF062 idle at cap-1), most coders (seed lanes only).
**Intake awaiting triage:** `intake/gtm-001.md` (Share-a-Premium impl CR proposal); `errors-001` is a
format template.

## WIP snapshot

- **CR054 Wave-1 LESSON tracks COMPLETE:** ETHIC ✓ (10) + ASST ✓ (20) + MACRO ✓ (12) + QUANT ✓ (12)
  = 54 lessons integrated, **corpus 270→324**. Remaining Wave-1: glossary (~120) + coach Q&A (~80).
- **Saiful-direct (immediate): CR059 then CR058.** CR059 = wire the 2 net-new tracks (`islamic_finance`,
  `decision_evaluation`) → locks the 13-facet hex tessellation (7 existing + 6 new). CR058 = Sharia
  content (M25), DEPENDS-ON CR059. Both "address the same areas" as the in-flight BOK.
- Content tracks run **sequentially** — the CR057 launch helper works in the main repo, so concurrent
  commits would race (disjoint files author fine in parallel, but `git commit`/`pull --rebase` don't).
- Open: CR057 → auditor.core audit (Saiful's call); LESSON_COUNT_FLOOR 270→324 + positional-option-ref
  guard, bundled into one coder.api micro-lane at Wave-1 wrap; CR060 (provenance/accuracy gate) standing.
