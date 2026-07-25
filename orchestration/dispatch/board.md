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

## 2026-07-23 (cont.) — CR077 Phase 2 laned; Phase 3 handed to the host team

- **CR077 Phase 2 dispatched** as `CR077-ROOM` → coder.room, `GATE: independent`. Saiful settled the
  Room-quality question the Architect had held: the four ANALYSTS are four lenses on **one shared
  data block**, not a dependency chain — `news_analyst` quoted the Reddit sentiment score (social's
  domain) *while speaking before social*, so it read it from the `profile`, not the transcript.
  Architect confirmed structurally: `room_prompts.py:338` renders the sentiment score into the
  `profile` fact-sheet and `_format_profile` is agent-independent. R59 had already logged the same
  evidence from INGN/MSFT transcripts. So concurrency changes no data dependency — laned, not held.
  **Hard condition in the lane:** strip/rescope the "build on the transcript" line for the concurrent
  analysts (with concurrency their transcript is empty). RESEARCHERS/RISK/VERDICT stay sequential.
  Phase 1's A/B demoted from blocking gate to verification the lane attaches.
- **CR077 Phase 3 is the LLM-host team's, not this board's.** Saiful: *"we have a team taking care of
  it. do not touch it."* The `gpu_memory_utilization` bump is a request handed to that team with a
  before/after measurement ask — no coder instance touches `192.168.20.74`. (Corrects the earlier
  entry today that framed it as SSH-blocked/Architect-applied.)
- `coder.room` now holds `CR077-ROOM` (CR069-ROOM DONE + merged d507a87); 1 free slot. `live_handle`
  marked stale — respawn per lane.

## 2026-07-24 — DEF095 + DEF096 laned to coder.room (the two Room data-integrity holes from R59's audit)

- **DEF095** (Trader narrates R:R/drawdown nothing checks — 4/4 wrong across the window, PM approved
  the SCHD one) → `coder.room`, `GATE: independent`, round 1, workable now. Fix sites all coder.room:
  `_pm_rr_coherence_signal` (room_runner.py:587-604) inspects only the PM and passes silently on
  `stated is None`; the Trader's derived figures are structurally starved (DEF066 proposal gating,
  room_prompts.py:214-216); the check is telemetry, not a surface. Build per CR038 — the *system*
  computes every ratio from the Trader's levels and that computed figure feeds the transcript RISK/VERDICT
  read (killing the contagion vector). `trading_math` fns already exist + imported → consume, no coder.math
  sub-lane.
- **DEF096** (Room Social Analyst denied 3 of 4 live Reddit fields) → `coder.room`, `GATE: independent`,
  round 1, `DEPENDS-ON: DEF095`. Render `mention_trend` / `influencer_take` / `pattern` in `_format_profile`
  under the existing `social_live` gate (room_prompts.py:268). **Ownership corrected at laning:** the spec
  said "coder.api owns the files" — wrong; the roster puts the room cluster on coder.room and tells coder.api
  "never edit the room cluster." Pure coder.room; `social_context.py` (the coder.api-adjacent service the
  spec meant) needs no change.
- **WIP:** both share `room_prompts.py` with each other and with CR077-ROOM (which strips the "build on the
  transcript" line in the same block DEF095 rewrites). One instance owns all three → serialize internally.
  wip_cap:2 respected — CR077-ROOM + DEF095 active; DEF096 dep-blocked behind DEF095.
- Register rows flipped `open → laned` (def_list.md DEF095/DEF096). `AT:architect`.

## 2026-07-24 (cont.) — DEF095+DEF096 batched to one audit; DEF098 (the class) laned to coder.api

- Saiful: *"if 95 & 96 are essentially doing the same thing, you might as well batch them together to
  the auditor. Check 98 too."* Correct — 95 (Trader's derived R:R/drawdown unchecked) and 96 (social
  trio dropped) are one class (CR040 computed-but-dropped/unchecked) and both edit `room_prompts.py`.
- **DEF095 + DEF096 → ONE coder.room build + ONE audit.** The coder.room agent already firing on DEF095
  was widened (SendMessage) to build DEF096 in the same worktree and produce a single combined hand-off.
  DEF096's `DEPENDS-ON: DEF095` dropped (no longer serialized — they're one build). On the single COMPLETE
  both register rows flip `fixed`.
- **DEF098 → coder.api, `GATE: independent`, `DEPENDS-ON: DEF095, DEF096`.** 98 is the *systemic* parity
  guard (a field the pipeline computes must render on every surface the agent reads, or be declared in an
  `INTENTIONALLY_OMITTED` registry — modelled on `test_config_compose_parity.py`). It is **coder.api, not
  coder.room**: the guard spans the 1-on-1 + Concierge surfaces (`agent_runner`/`social_context`/
  `concierge_prompts`) coder.room may not touch, and it carries the api-side instance fix (1-on-1 drops
  next-earnings). It builds ON TOP of the landed Room batch (so its Room assertions are green), and queues
  behind coder.api's cap (DEF094 + CR077-CONCIERGE). Not folded into the Room audit — different instance,
  different surfaces.
- Register rows: DEF095/096 annotated batched; DEF098 flipped `open → laned`. Architect-written per CR081.

## 2026-07-24 (cont.) — DEF095+DEF096 batch DONE (built, independently audited COMPLETE, integrated)

- **coder.room built** the batch in an isolated worktree (commit `87fc062`, 3 files: room_runner.py +
  room_prompts.py + test_room_runner.py, 5 guards). Architect verified independently first: scope (no
  forbidden files), diff (real structural fix, DEF059-safe), own pytest (guards 5/5, suite 1058, exit 0).
- **Independent audit → COMPLETE** (adversarial agent, GATE: independent). It neutered the fix to prove
  4/5 guards go RED (guard5 is an honesty guard, correctly stays green); traced the R:R correction as
  strictly upstream of `run.transcript.append` (:1829 vs :1841) so downstream agents read AMI's computed
  figure not the narration; confirmed `enforce_safety_floor` consumes the untouched structured verdict
  (DEF059 held); confirmed DEF096's `social_source` gate is load-bearing; ran the suite itself (1058, exit
  0). Two non-blocking regex notes logged on the DEF095 row (wrong inline number can coexist with the loud
  `[AMI verified]` note on free-prose phrasings — truth always surfaced; keyword-proximity false-match on
  out-of-domain prose that can't occur in-Room).
- **Integrated** onto main via cherry-pick `dc29c5c` (clean — no overlap with the dispatch/docs commits
  main advanced through). `DISPATCH: ACCEPTED (round 1)` on both lanes; both register rows `fixed`;
  coder.room back to 1 free slot (holds CR077-ROOM).
- **Unblocks DEF098** (coder.api) — its `DEPENDS-ON: DEF095, DEF096` is now satisfied; fires when a
  coder.api slot frees (still at cap: DEF094 + CR077-CONCIERGE).

## 2026-07-25 — CR055 + CR056 laned (the SCHD phantom-holdings pair) after a fix-check

- **Verified first that neither was already fixed** (Saiful's ask): no impl commits (only the
  `e6aff3a`/`07c3346` filing commits), no lanes, no audit files, both `proposed`, and — the important
  part — **no code fix present**. CR055: zero sim-holdings injection anywhere in the Room prompt path
  (`list_trades`/`total_value` still uncalled in `room_runner.py`), `risk_tier_cap` wired only to
  PM/Trader/cosmetic display, not the researcher prompts. CR056: no "no assumed data" imperative
  anywhere in `llm_gateway.py` or any prompt path. **The live SCHD hallucination is still reproducible.**
- **CR055 → `coder.room`, `GATE: independent`, round 1.** Single lane (all hot files are room-cluster
  owned; sim + `trading_math` consumed read-only). Three parts: (1) unconditional sim-holdings block
  injected via the `build_agent_prompt` snapshot slot with an explicit "you hold 0% / no open positions"
  for empty users + **loud `unavailable` on fetch failure, never silence** (this is the exact bug);
  (2) `risk_tier_cap(risk_score)` into Bull/Bear/Research-Manager prompts (M03 coherence — removes the
  10–15%-vs-3.0% incoherence that fed the fabrication); (3) one-sentence `long_only` tighten.
- **CR056 → `coder.api`, `GATE: independent`, round 1, no `DEPENDS-ON`.** Placement **fixed to the
  gateway** `LLMGateway.stream_chat` (prepend), NOT `build_agent_prompt` — the latter misses Concierge +
  reformatter (fails "all LLM") AND would collide with CR055's `agent_prompts.py` edits. Two hard
  caveats written into the lane: preamble must contain **no agent-id token** (mock branches on
  `system_prompt.lower()` :154) and must **prepend** (PM safety-floor-last invariant). Honest ceiling
  flagged: ~30% effective (CR038) — defence-in-depth, paired with CR055's structural fix, not a substitute.
- **Disjoint file-sets** (`room_runner`/`room_prompts`/`agent_prompts` vs `llm_gateway`) → the two lanes
  run **fully in parallel**, integrate independently. Register rows `proposed → in_progress` (drift green,
  84 CR rows). Both coders spawned as isolated-worktree agents; each self-tests, pushes to its lane
  branch, and writes its `SUBMITTED: round 1` audit file for the pre-spawned track-U auditor.
  `AT:architect`.

## 2026-07-25 — DEF061 laned to coder.api ("build enforcement now")

- **Saiful directive: "Build enforcement now."** The 4 advertised-but-unenforced mandate toggles
  (`esg_lite`, `no_tobacco_alcohol_gambling`, `no_fossil_fuels`, `custom_constraints`) — Settings sells
  them as hard per-trade filters (`settings_screen.dart:365-386`) but `check_mandate_compliance()`
  (`safety_floor.py:98-205`) never reads them. Sits on the "safety floor is sacred" commitment; the
  halal-conscious AR/MS markets are the sharp edge.
- **DEF061 → `coder.api`, `GATE: independent`, round 1** (`lanes/DEF061.assign.md`). **DEF062 dep
  overridden** (idle/unstarted, no live serialization; trade-time enforcement ⟂ write-time validation).
- **Scope split, source-verified (DEF089's rule — no lane on an unverified source):** BUILD NOW =
  `no_fossil_fuels` + `no_tobacco_alcohol_gambling` via a **sourced, held sector/industry classification
  snapshot** on the CR069/CR075 architecture — classify the ~503 S&P parent constituents CR075 already
  persists, using `yf.Ticker(t).info` sector/industry already read at `fundamentals.py:139,234-239`; new
  append-only snapshot table + daily background refresh + read-through (no request-path socket); two new
  checks mirroring the halal three-state `resolve` seam; UNKNOWN permitted-with-disclosure (halal G3),
  `None`→paused loud-degrade. **FORKED to Saiful** = `esg_lite` (no free authoritative ESG source) +
  `custom_constraints` (freeform text ≠ deterministic hard filter) — guessing either repeats DEF059.
- **Coupled honesty follow-up (CR040):** until esg/custom are built, Settings must stop presenting them
  as hard filters — a small `coder.mobile` lane the Architect will file (not DEF061's lane).
- **Serialization clear:** coder.room holds only CR077-ROOM/`room_prompts.py`; `safety_floor.py` is free.
- Register row flipped `open → laned` (DEF061.row.md), regen+verified (106 rows). `AT:architect`.
- **DEF061-BE coder spawned** (isolated worktree, opus) against the launch-ready lane — building the
  fossil+sin sourced classification snapshot on the CR069/CR075 templates (`sharia_universe.py` /
  `ShariaUniverseSnapshotRow` / migration `b2d3e4f50021` / `_sharia_universe_refresh` / the halal
  `resolve` seam). Fixture-based unit tests; live classification counts pair with the next promote
  (CR075's flow). Independent audit + Architect repo-root re-verify gate it on `READY_FOR_AUDIT`.
- **DEF061-MOBILE queued** (`lanes/DEF061-MOBILE.assign.md`) — the CR040 honesty half: relabel
  `esg_lite` + `custom_constraints` in Settings so they stop advertising as hard filters while forked.
  Activates on Saiful's esg/custom ruling (build → superseded; scope-out → this ships). Not blocking.
