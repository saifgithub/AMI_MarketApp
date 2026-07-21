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
| **CR054-W1-QUANT** | **ASSIGNED r1 · launching** | noncoder.edu | **Wave 1 — 12 Quant lessons (QUANT 1-12, ids 335-346, L12). Content-review gate. Last Wave-1 lesson track** |
| CR030 | UNASSIGNED (re-queued) | coder.api | earnings/dividend — re-queued behind CR054 Wave 0 to free a slot |
| DEF061 | UNASSIGNED (queued) | coder.api | enforce 4 mandate toggles — DEPENDS-ON DEF062 |
| CR026 | UNASSIGNED (queued) | coder.api | sector enforcement — DEPENDS-ON DEF061 (safety_floor hot) |
| CR020 | UNASSIGNED (queued) | coder.api | concierge full-context — head of CR020→021→022 |

**Idle/available:** `coder.math`, `coder.api` (DEF062 idle at cap-1), most coders (seed lanes only).
**Intake awaiting triage:** `intake/gtm-001.md` (Share-a-Premium impl CR proposal); `errors-001` is a
format template.

## WIP snapshot

- **CR054 Wave 1 progress:** ETHIC ✓ (10) + ASST ✓ (20) + MACRO ✓ (12) integrated = **corpus 270→312**.
  QUANT (12, ids 335-346) launching now = last Wave-1 lesson track; then glossary (~120) + coach Q&A (~80).
- `noncoder.edu`: 1 active (CR054-W1-QUANT launching). Content tracks run **sequentially** — the CR057
  launch helper works in the main repo, so concurrent commits would race (disjoint files author fine in
  parallel, but `git commit`/`pull --rebase` don't).
- All coders idle apart from seed lanes; `coder.api` at cap-1 (DEF062 idle). Auditor queue: 0 IN_AUDIT.
- Open: CR057 → auditor.core audit recommended (Saiful's call); LESSON_COUNT_FLOOR 270→312 bump at
  Wave-1 wrap (coder.api micro-lane).
