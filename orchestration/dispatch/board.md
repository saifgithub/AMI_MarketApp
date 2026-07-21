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
| **CR054-W0a** | **IN_AUDIT r1** | coder.api → auditor.core | **BOK track-enum wiring — built, 892 tests green, pushed (c401a17). Auditor verifying** |
| DEF062 | ASSIGNED r1 (idle) | coder.api | validate mandate PATCH — head of safety chain; no worker yet |
| CR038 | ASSIGNED r1 (seed) | coder.room | remove macro/Fed scaffolding at source |
| CR048 | ASSIGNED r1 (seed) | coder.store | Play internal track + fastlane (first upload Saiful-gated) |
| CR049 | ASSIGNED r1 (seed) | coder.web | website support + Concierge (keys/deploy Saiful-gated) |
| CR050 | ASSIGNED r1 (seed) | coder.mobile | login UX (mobile half; Google-on Saiful config) |
| CR054-W0b | UNASSIGNED (queued) | coder.mobile | new-track short labels — DEPENDS-ON CR054-W0a |
| CR054-W0c | **ASSIGNED r1 · WORKER LIVE** | noncoder.edu | author-prompt v2 (content review gate, not Auditor) |
| CR054-W0d | **ASSIGNED r1 · WORKER LIVE** | coder.math | CR046 bond/option/portfolio math entries + guard tests |
| CR030 | UNASSIGNED (re-queued) | coder.api | earnings/dividend — re-queued behind CR054 Wave 0 to free a slot |
| DEF061 | UNASSIGNED (queued) | coder.api | enforce 4 mandate toggles — DEPENDS-ON DEF062 |
| CR026 | UNASSIGNED (queued) | coder.api | sector enforcement — DEPENDS-ON DEF061 (safety_floor hot) |
| CR020 | UNASSIGNED (queued) | coder.api | concierge full-context — head of CR020→021→022 |

**Idle/available:** `noncoder.edu` (W0c ready), `coder.math` (W0d ready).
**Intake awaiting triage:** `intake/gtm-001.md` (Share-a-Premium impl CR proposal); `errors-001` is a
format template.

## WIP snapshot

- `coder.api`: 2 active (**CR054-W0a — worker live**, DEF062 idle) — **at cap**; CR030/DEF061/CR026/
  CR020 queued. CR030 re-queued behind the CR054 dogfood to keep the cap honest.
- All other coders: 1 seed lane each (no workers). Auditor queue: 0 IN_AUDIT (W0a not yet submitted).
- **Live workers:** `coder.api` on CR054-W0a — `live_handle` in `roster/coder.api.md`.
