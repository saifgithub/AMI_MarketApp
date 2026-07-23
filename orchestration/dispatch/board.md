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
| **DEF084-BE** | **ASSIGNED r1 — TOP** | coder.api | **halal flag is a 7-ticker allowlist, not a screen — serving now.** Option 2 (Saiful, 07-22): relabel as a curated demonstration universe + guard that every mandate flag is enforced by the mechanism its copy describes. 4th degrade-loudly occurrence |
| **DEF084-MOBILE** | ASSIGNED r1 | coder.mobile | Settings toggle says "Halal screen" — relabel + subtitle, 3 locales. **DEPENDS-ON DEF084-BE** (mirror its wording) |
| **DEF084-CONTENT** | ASSIGNED r1 | noncoder.edu | lessons `355`/`351` claim a two-stage screen + a reachable `purification_amount`. **DEPENDS-ON DEF084-BE** (spec: do not correct 355 first). Religious substance EXCLUDED — Saiful/SME only |
| **DEF083** | ASSIGNED r1 | noncoder.edu | 11 quiz explanations name the wrong option (incl. `276`/`277`, the don't-over-trust-AMI pair). Guard ships WITH the fix — DEF079's regex only matches the literal word "option"; mirror into `shuffle_quiz_answers.py` |
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
| ~~CR053-MOBILE~~ | **DONE ✓ (r1)** | coder.mobile → auditor.core | `{{lesson:}}` chip + prereq render/link + tappable gateway rows integrated 921f15f; auditor COMPLETE (a4aede0) — additive tokenizer, 37/37 tests, degrade-to-text proven. Render branch shipped |
| ~~CR053-MIGRATE~~ | **DONE ✓ (r1)** | noncoder.edu → review | 327 lesson-body refs → full-id `<Lesson/>` tags (270 global + 57 within-module, 0 flagged) + 33 daily → codes, integrated 320bf45; content review PASS (Class-2 same-prefix verified, 0 bare refs remain, guards green). **CR053 FULLY DONE (BE+MOBILE+MIGRATE)** |
| ~~DEF079~~ | **DONE ✓ (r1)** | noncoder.edu → review | 10 positional option refs reworded by content + guard extended (proved bites) + shuffle-parity + LESSON_COUNT_FLOOR 270→334, integrated 88cd4e4; content review PASS (24 green, 0 positional quiz refs remain). Wave-1 wrap closed |
| ~~DEF080~~ | **DONE ✓ (r1)** | coder.api → review | concierge context budget 12k→20k (corpus 270→334 tripped the guard, blocked promote); test tied to constant. Integrated 50872ca; full suite re-run 939 pass 0 fail. **Promote preflight green** |
| **CR061** (proposed) | **QUEUED — quick wins** | architect | verify helper + audit-launch helper + test-timeout wrapper (828s) + roster live_handle fix |
| CR030 | UNASSIGNED (re-queued) | coder.api | earnings/dividend — re-queued behind CR054 Wave 0 to free a slot |
| DEF061 | UNASSIGNED (queued) | coder.api | enforce 4 mandate toggles — DEPENDS-ON DEF062 |
| CR026 | UNASSIGNED (queued) | coder.api | sector enforcement — DEPENDS-ON DEF061 (safety_floor hot) |
| CR020 | UNASSIGNED (queued) | coder.api | concierge full-context — head of CR020→021→022 |

**Idle/available:** `coder.math`, `coder.api` (DEF062 idle at cap-1), most coders (seed lanes only).
**Intake awaiting triage:** `intake/gtm-001.md` (Share-a-Premium impl CR proposal); `errors-001` is a
format template.

## WIP snapshot

- **Saiful's AFK directive "058, 059, 053 all done" — DELIVERED (AT:R64).** CR058 (math + 10 SHARIA
  lessons + support content) ✓, CR059 (13-facet taxonomy: backend + mobile labels) ✓, CR053 (reference
  identifiability: BE + MOBILE + MIGRATE) ✓. Corpus **334 lessons**.
- **CR054 Wave-1 LESSON tracks COMPLETE:** ETHIC ✓ (10) + ASST ✓ (20) + MACRO ✓ (12) + QUANT ✓ (12)
  = 54 lessons, corpus 270→324, then CR058 SHARIA (10) → **334**. Remaining Wave-1: glossary + coach Q&A
  (CR058-SUPPORT already added 20 islamic_finance glossary terms + 15 Q&A).
- **BACKEND IS LIVE ON ALPHA** (tag `alpha-2026-07-22-3` @ 44759a9): rsync 0.9s, api-alpha rebuilt and
  healthy on the first poll, alembic no-op, smoke green (vllm + yfinance AAPL $327.74), config-check
  matches `infra/alpha.env` intent. **342 lessons / 13 tracks** (EVAL authored by CR062). `audit/` +
  `reports/` intact — DEF081 excludes held. Lesson `294`'s duty-based reframe verified served by the
  API: equal-access phrase gone, duty framing present, retired provenance line absent.
- **Mobile 0.1.0+50 SHIPPED to both stores** — Play internal verified via the Play API
  (`google_play_track_version_codes track:internal` → `[50]`), TestFlight uploaded. Carries the DEF082
  honeycomb, so all 13 tracks are reachable in-app. *(Superseded note, kept for the audit trail:)*
  earlier `0.1.0+45` (commit 48611d5): signed AAB (50MB, upload-key SHA-1
  verified) + signed IPA (26MB, `CFBundleVersion 45`). **+45 is required** — the live backend serves
  `{{lesson:…}}` tokens that only the CR053-MOBILE render branch understands; testers on +44 see raw
  token text. Upload (TestFlight + Play internal) is **Saiful-gated** — I build, he uploads.
- Content tracks run **sequentially** — the CR057 launch helper works in the main repo, so concurrent
  commits would race (disjoint files author fine in parallel, but `git commit`/`pull --rebase` don't).
- Open: CR057 → auditor.core audit (Saiful's call); **DEF078** (20 CR060 sourced-lesson content errors,
  1 legal escalation — routed to the education lane, live on Alpha today); **DEF076** (Android Google
  Sign-In code 10 — console/propagation side, NOT a build fix: upload key + web-client-id + audience all
  verified correct); CR060 (provenance/accuracy gate) standing.
- Closed this round: DEF079 (positional option refs + guard + `LESSON_COUNT_FLOOR` 270→334), DEF080
  (concierge context budget 12k→20k — had blocked the promote), DEF081 (`/promote-to-alpha` rsync
  `--delete` would have wiped 134 melehost-only files; excludes added).

## 2026-07-23 — CR077 triaged, two coder.api lanes opened

- **CR077 (Phase 0) dispatched** as `CR077-CONCIERGE`, `GATE: spawned`. The Architect re-measured
  the mechanism independently — own synthetic prompt, own request, metrics delta on
  `vllm:prefix_cache_hits_total`: **catalogue-last → 0 hit tokens of 29,892 queried, 5,218 ms;
  catalogue-first, same brand-new user → 29,344 hit tokens, 284 ms.** Serving config reproduced
  exactly (`block_size="2096"`, `_block_size_resolved="True"`, `user_specified_block_size="False"`,
  `enable_prefix_caching="True"`, `mamba_cache_mode="align"`). Those latencies are on a prompt ~2×
  the real Concierge's — **not the app's numbers**; CR077's own 14,672 cached / 344 ms on the real
  15,731-token prompt is the figure the lane must reproduce. Structural cause confirmed in code:
  `base` (`concierge_prompts.py:84`) is mandate-derived, so **nothing** before the catalogue is
  shared between users.
- **CR077 Phases 1–2 held, deliberately.** Phase 1's 5-ticker A/B decides whether four analysts may
  run concurrently — every Room prompt carries *"build on the transcript"*, so concurrent analysts
  go blind to each other. That is a Room-quality question about what the Room **is**, not a latency
  one, and it is Saiful's call, not an ops decision. ~15 s/convene stays on the table until he rules.
- **CR077 Phase 3 blocked, not deferred.** Raising `gpu_memory_utilization` from `0.5` needs the LLM
  host; `ssh 192.168.20.74` returns `Permission denied (publickey,password)` (verified today).
  Saiful's to apply.
- **DEF094 laned**, `GATE: independent` — D-5: an observance disclosure crossing the wire to two app
  stores. The lane **widens** the filed fix: DEF094 names `sim.py:186-190` and `:230-234`, but those
  are the preview and *rejected*-submit paths. `submit_trade`'s **accepted** path was never audited,
  and a fix that discloses on rejections while staying dark on trades that actually go through is
  worse than none.
- **Stale model name corrected** in `CLAUDE.md`, `hosting.md`, `HANDOVER_R.md` and the memory files.
  Docs said *"Gemma 4 31B"*; `/v1/models` reports `root: models--RedHatAI--Qwen3.6-35B-A3B-NVFP4`.
  CR077 flagged it; verified against the host before changing anything.
- `coder.api` now **at cap** (`DEF094`, `CR077-CONCIERGE`). `live_handle` marked stale — respawn per
  lane rather than resuming the CR069-DIVERGE session.
