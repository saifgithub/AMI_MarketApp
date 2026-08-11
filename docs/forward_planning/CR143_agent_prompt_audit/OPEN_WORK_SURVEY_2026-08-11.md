# Open work survey — agent prompts + agent data feeds

**Compiled:** 2026-08-11 · **Scope:** every `open` Defect and every `proposed`/`in_progress` CR that
touches (a) the 12+1 agent prompts, or (b) the data that reaches the fact sheet, or (c) the parser
that reads agent replies back — the prompt's other half.

**Sources:** `docs/defect/_registry/DEF*.row.md` and `docs/forward_planning/_registry/CR*.row.md`
read directly (status = 4th-from-last pipe field). The generated tables were not trusted. Every
"still live at HEAD" claim below was re-verified against the code in this session, not taken from
the row.

**HEAD at survey time:** `d4d0f496` (main).

---

## 0. Counts

| Primary layer | Count | Items |
|---|---|---|
| **PROMPT TEXT** | 8 | DEF251, CR146, CR149, CR150, CR153, CR154, CR155, CR160 |
| **PROMPT ASSEMBLY** | 5 | DEF236, DEF241, CR104, CR145, CR151 |
| **DATA FEED** | 8 | DEF063, CR023, CR024, CR069, CR147, CR148, CR157, CR164 |
| **REPLY PARSING** | 6 | DEF237, DEF239, DEF242, DEF255, CR152, CR156 |
| **ROUTING** | 2 | CR017, CR141 |
| **CROSS / measurement** | 2 | DEF230, CR143 |
| **TOTAL IN SCOPE** | **31** | 9 open Defects + 22 non-done CRs |

Excluded after checking (named so nobody re-derives them): DEF100, DEF104, DEF144, DEF145, DEF178,
DEF182, DEF195, DEF199, DEF200, DEF204, DEF205, DEF218, DEF220, DEF223, DEF226, DEF246, DEF253,
DEF254 · CR004, CR022, CR036, CR039, CR043, CR045, CR049, CR051, CR052, CR054, CR057, CR061, CR070,
CR080, CR083, CR084, CR092, CR102, CR103, CR107, CR109, CR120, CR122, CR123, CR126, CR129, CR133,
CR134, CR135, CR136, CR138, CR140, CR159, CR161, CR162, CR163.

Two exclusions are close calls and are recorded rather than dropped silently:

- **DEF226** (vLLM never emits `prompt_tokens_details.cached_tokens`) — routing *telemetry*, not
  something that changes what an agent can do. It does, however, block CR017 §5 step-0 prompt-prefix
  reordering, which *would* be in scope. Watch it.
- **DEF205** (1-on-1 and Brief turns cost zero credits) — product/billing decision. In scope only in
  that CR147 §4 argues the *opposite* direction: a 2-credit live-news surcharge is being charged for
  a feed with no relevance ranking.

---

## 1. In-scope items — full table

Status source is the row file. "Commits" is `git log --all --oneline --grep=<ID> | wc -l`.

### 1a. Open Defects

| ID | Status | Domain | What it is | Layer | Agent(s) | Blocked-by / depends-on | Commits | Fix or filing? | Superseded? |
|---|---|---|---|---|---|---|---|---|---|
| **DEF063** | open | prompt/infra | `ALPHA_VANTAGE_API_KEY` still parked (commented) in `infra/alpha.env:84`; `ADANOS_API_KEY_SECONDARY` is a live key with no `Settings` field and no compose forward | DATA FEED | News Analyst (AV sentiment tags), Social Media Analyst (spare quota) | Adanos half closed 2026-07-21; AV half is a Saiful budget call | 18 | Only `9c699b1` (CR040) is a real fix — the *structural* half. AV half never enabled | **NO.** Partly fixed only |
| **DEF230** | open | prompt/backend | Room returned zero APPROVE 07-31 → 08-07; corrected human-only series 32.7% → 0%, p≈0.003; two confounds (tier mix, mandate version) uncontrolled | CROSS (prompt-constraint framing) | PM primarily | DEF227/228/229 (all `fixed`) were the input defects; needs post-promotion replay | 5 | 3 commits fix DEF227/228/229; **no commit fixes DEF230**. Closing action is a measurement | **NO.** Its three named input defects shipped; the re-measure is owed |
| **DEF236** | open | room | `_LENGTH_GUIDE` vs `_PROSE_FORMAT` vs `_STANCE_FORMAT` cannot all be satisfied; `_AGENT_MAX_TOKENS` sized to the loser | PROMPT TEXT + PROMPT ASSEMBLY | All 11 prose agents | Owned by CR145 Tier B; **blocks** CR152 Tier A.4, gates CR153/154/155/156 Tier B/C renders | 3 | **All 3 are filing/booking.** Verified live at HEAD: `room_prompts.py:68-80`, `:210`, `:264` unchanged | **NO** |
| **DEF237** | open | room | `_annotate_rr_against_levels` has no plausibility gate; a mis-parsed level renders a fabricated downside under "These are the figures of record" | REPLY PARSING | Every prose agent (`_verify_and_annotate_geometry` runs on all, `room_runner.py:3526`) | DEF242 (widening the number group makes more prose numerals candidates); DEF236 is the cause that keeps levels in prose | 4 | **All 4 are audit/mint commits.** Verified: no `last_close` comparison in `_annotate_rr_against_levels` at HEAD | **NO** |
| **DEF239** | open | room | PM writes reasoning under `rationale`/`reasoning`; `_parse_pm_verdict` reads only `narration` → AMI publishes "it wrote no rationale" over three real sentences | REPLY PARSING (+ PROMPT TEXT cause) | Portfolio Manager | None. == CR156 Tier A2 | 1 | **Filing only** (`e0a4ae4b`). Verified: `room_runner.py:1050` reads `narration` alone | **NO** |
| **DEF241** | open | room | Prose agents compute cap consumption in prose, ~half wrong; one shipped attached to "stays within the safety floor" | PROMPT ASSEMBLY + DATA FEED | **Bull Researcher + Research Manager only** (3 debators done) | DEF243 shipped with it; residue split to DEF244 (`fixed`) | 7 | `719d2e48` is a **real fix** + 4 audit rounds; reopened by a round-2 MAJOR | **PARTLY.** Debator half shipped. Verified live: `room_prompts.py:432` still gates the proposal block on `phase in ("RISK","VERDICT")`, so Bull (RESEARCHERS) and RM (SYNTHESIS) are **byte-identical to pre-fix** |
| **DEF242** | open | room | `_LEVEL_PATTERNS` still `(\d+(?:\.\d+)?)` — `"Entry: $1,507.00"` → `1.0`. DEF234's defect in the sibling parser | REPLY PARSING | Trader primarily; any prose agent | DEF237 (the backstop that makes a regex fix sufficient) | 1 | **Mint only** (`50e554a2`). Verified: `room_runner.py:1250-1254` lacks the group `_LEVEL_NUMBER:1535` already has | **NO** |
| **DEF251** | open | room | Debator prompt asks for the stance twice; 20% of turns state it once, in prose. 53.3% of debator turns yielded no parsed stance | PROMPT TEXT | Aggressive, Conservative, Neutral Debator | DEF247 (`fixed`) is the parser half; DEF243 is the **failed prior guard** | 1 | **Filing only** (`89f975fa`). Verified: `Open your PROSE with:` still on line 23 of **all three** debator files at HEAD | **NO.** DEF247 stopped the *leak*, not the omission |
| **DEF255** | open | room | PM states 1095-day horizons (the mandate label restated) beside stops that trigger in a fortnight; 4 of 5 such approvals stopped out | PROMPT TEXT (PM JSON contract) + REPLY PARSING (missing coherence check) | Portfolio Manager (+ Trader owns `trader_horizon_weeks`) | CR164 (found it), CR152, CR156 | 1 | **Filing only** (`328c4ea0`) | **NO** |

### 1b. Non-done CRs

| ID | Status | Domain | What it is | Layer | Agent(s) | Blocked-by / depends-on | Commits | Fix or filing? |
|---|---|---|---|---|---|---|---|---|
| **CR143** | in_progress | quality | Parent audit — Phases 1/3b/4/5 done, per-agent CRs + DEFs are its output | CROSS | All 13 | — | 14 | Real work (dumps, corpus, Phase 5 verdict); no prompt edits of its own |
| **CR145** | proposed | quality | Fundamentals data + lane discipline. **A**: render marketCap/FCF$/gross debt, fix the margin example; **B**: DEF235/DEF236 prompt conflicts; **C**: `_format_profile(profile, agent_id)` + visibility matrix; **D**: margin trend + buybacks (blocked on a fundamentals cache) | DATA FEED + PROMPT ASSEMBLY + PROMPT TEXT | Fundamentals primary, **all 12** for Tier C | Tier C needs Saiful's matrix call; Tier D blocked on `fundamentals.py` having **no cache at all** | 3 | Filing only |
| **CR146** | proposed | quality | Market Analyst — delete 4 unhonourable demands (entry/target/stop bullet 0/18, R:R bullet 0/18, leverage line, ACTIVE-branch R:R floors); Tier B render SMA-20/50 + volume ratio; Tier C longer history window | PROMPT TEXT (A), DATA FEED (B/C) | Market Analyst; Tier B lands on all 12 | Tier B/C sequence behind CR145 Tier C | 2 | Filing only |
| **CR147** | proposed | quality | News Analyst — 18/18 turns out of lane; the Alpha Vantage conditional is false in 216/216 prompts and 1/18 turns invented the tag; 2 of 5 output bullets unexecutable; feed has no relevance ranking (top headline off-ticker 50%) yet costs 2 credits | PROMPT TEXT + PROMPT ASSEMBLY + DATA FEED | News Analyst; the shared header edit hits **all 12** | **DEF063 AV half gates Tier A.1**; Tier B.2 behind CR145 Tier C; Tier C needs the 6h earnings cache | 2 | Filing only |
| **CR148** | proposed | quality | Social Analyst — "as of this call" false for 93% of cache rows (mean 20.2 d); 4 Adanos dimensions fetched and discarded; 9/18 turns attribute sentiment to a named subreddit with no per-community data | DATA FEED + PROMPT ASSEMBLY + PROMPT TEXT | Social Media Analyst | Tier B paid half needs Saiful's quota call; **names the `ADANOS_API_KEY_SECONDARY` DEF063-class gap** | 2 | Filing only |
| **CR149** | proposed | quality | Bull Researcher — citation instruction inert (1/18 cite ≥3 analysts, 14/18 cite none), falsifier 0/18; the cap **is** the sizing model and 7/18 mandates have no cap | PROMPT TEXT (A), REPLY PARSING (C) | Bull Researcher | Tier B needs Saiful's 100%-cap policy call | 2 | Filing only |
| **CR150** | proposed | quality | Bear Researcher — 7 verified findings; A1 (delete `-25%`) **already shipped as DEF245**; A2 market cap shared with CR145 Tier A; open-risk cap unverifiable (18/18 state it, 0/18 render a stop) | PROMPT TEXT + DATA FEED | Bear Researcher; A2/A4 hit all 12 | Tier C needs Saiful's short-clause decision | 2 | Filing only |
| **CR151** | proposed | quality | Research Manager — launders upstream wrong numbers (GRAB 44% → "both acknowledge the 44% upside"); three output shapes, wrong one wins 72%; the operative instruction is in `overlay_generator.py:385`, not the base prompt | PROMPT ASSEMBLY + PROMPT TEXT | Research Manager | Tier A behind CR145 Tier C; Tier D deferred on zero measured yield | 2 | Filing only |
| **CR152** | proposed | quality | Trader — the parser was written for this agent and sees almost nothing (full triple 2/18; `"entry signal (RSI 73"` → entry=73.0); base prompt names Risk Debators who have not spoken | REPLY PARSING (B) + PROMPT TEXT (A) + DATA FEED (C) | Trader | **Tier A.4 blocked on DEF236**; Tier B **is** DEF242 and must precede A.4 | 2 | Filing only |
| **CR153** | proposed | quality | Aggressive Debator — the `Open your PROSE with:` opener displaces the stance envelope; HARD CONSTRAINT's inputs computed and never rendered; `## Inputs` names 2 agents that have not spoken | PROMPT TEXT + PROMPT ASSEMBLY | Aggressive Debator (F1 cross-filed to all 3) | Tier B ≡ CR154 B ≡ CR155 C ≡ CR156 C — **ship once** | 2 | Filing only |
| **CR154** | proposed | quality | Conservative Debator — states a cap-consumption figure in 8/18 turns, wrong in 4/9 measured; A3 finds a canned worked example in `_mandate_common_block` contradicting the cap **in the same sentence**, wrong in 8/18, seen by all 12 | PROMPT TEXT + PROMPT ASSEMBLY | Conservative Debator; A3 hits all 12 | A1 must ship with CR153/CR155; Tier C depends on DEF236 | 2 | Filing only |
| **CR155** | proposed | quality | Neutral Debator — stance stored 12/18 (worst of 11); the leaked envelope is then read by the level parser; `hedge` cannot be supplied (no `option_chain` anywhere) and is barred by LONG-ONLY | PROMPT TEXT + REPLY PARSING | Neutral Debator; Tier A hits all 3 debators | Explicitly forbids fixing this in the parser; `test_cr106_stance_envelope.py` must stay unmodified | 2 | Filing only |
| **CR156** | proposed | quality | Portfolio Manager — A1 (sector kwarg) **shipped as DEF238**; A2 **is DEF239**; Tier B REJECT-inside-PASS 6/18; the trailing safety-floor tag lands inside `narration` | PROMPT ASSEMBLY + REPLY PARSING + PROMPT TEXT | Portfolio Manager | Tier C duplicates CR155 Tier C — dedupe rule stated in the CR | 2 | Filing only |
| **CR157** | proposed | quality | Weekly retrospective loop — capture scoreable conclusions, weekly scoring batch, post-mortem with the CR143 E1–E5 taxonomy | DATA FEED / persistence | All 12 (scored, not edited) | CR158 (`done`) is a hard dependency in practice — partition by `prompt_version`, not date | 4 | Row completion + folder; no build |
| **CR023** | in_progress | agents | News Analyst live feed — Yahoo half live; **Alpha Vantage NEWS_SENTIMENT half has never run** | DATA FEED | News Analyst | DEF063 AV half | 15 | Real work shipped (Yahoo); AV half never enabled |
| **CR024** | in_progress | agents | Social Analyst live feed — Adanos live and verified 2026-07-21; residue is quota + the unwired secondary key | DATA FEED | Social Media Analyst | DEF063 secondary-key half; CR148 Tier B quota call | 12 | Real work shipped |
| **CR069** | in_progress | agents | Sharia indicator — phase 1 (SPUS ETF) live; phases 2 (Malaysia SC PDF) + 3 (vendor eval) open | DATA FEED | All 12 via `_compliance_block` (`overlay_generator.py:105`) — the halal verdict **is** in the prompt | Needs a named-standard decision; two free sources disagree on 47.9% | — | Phase 1 shipped |
| **CR104** | in_progress | quality | Delete the synthetic numeric baseline from the Room path | PROMPT ASSEMBLY | All 12 | — | 37 | **Numeric half delivered** — `_profile_for_ticker` is live-or-absent with per-field `field_state`. Residue is the CR034 narrative scaffolding, explicitly out of its own scope |
| **CR141** | in_progress | backend | Multi-provider routing build — usage capture + provider registration shipped; `provider_policy.pick_provider(plan, agent_id, tier)` exists and is **dormant by construction** | ROUTING | Any agent, once a call site opts in | CR017 §4.4 plan→level mapping is an open pricing decision; DEF226 blocks the cache-rate half | 8 | Real work shipped |
| **CR017** | proposed | backend | Multi-provider routing + per-provider caching — the research spec CR141 builds from; §5 step 0 is prompt-prefix reordering | ROUTING | All | DEF226 (cannot measure a cache-hit rate on vLLM) | — | Design record |
| **CR160** | proposed | quality | Rename 6 agent roles away from the TradingAgents lineage (Debator ×3 → Risk Officer, PM → CIO, Trader → Execution Desk, Market → Technical Strategist, Social → Flow & Positioning, News → Macro & Events) | PROMPT TEXT (+ 272 files of user-visible copy) | 6 of the 12 | AR/MS transcreation; subsumes the "Debator" spelling defect | 1 | Filing/renumber only |
| **CR164** | in_progress | quality | Room backtest harness — as-of mode on production infra, EDGAR PIT fundamentals, pinned regression batch | DATA FEED (fact sheet under `as_of`) + measurement | All 12 | CR104/DEF123 `field_state` machinery for non-reconstructable fields | 7 | **Real work shipped**, harness parked after pilot; it produced DEF255 |

---

## 2. Overlap map — which per-agent CRs are already absorbed by shipped DEFs

Verified by reading the current prompt files and code, not by reading the DEF rows.

### 2.1 Wholly absorbed

| CR finding | Verbatim claim | Shipped by | Verified at HEAD |
|---|---|---|---|
| **CR150 A1** | *"**Delete `-25%` from the style example**"* — *"22 of 811 real PM verdicts carry it, 12 attributing it to the Bear"* | **DEF245** (`25501a14`, `635c765f`, `04b83931`; COMPLETE at `d39eb883`) | ✅ `grep "25%" content/agents/bear_researcher.md` → **no hits.** The instruction now models the derivation, not a result |
| **CR156 Tier A1** | *"The one data feed built exclusively for this agent has never reached it"* — `_stream_pm_response` *"does not pass `sector_weights`"*, empty-state copy 18/18 | **DEF238** (`fa411ae5` — *"CR026's sector allocation never reached the PM; the one call site that renders it was the one that never passed it"*) | ✅ DEF238 status `fixed` |
| **CR146 rejected-item 4** | *"no-position-in-range / direction-blind trend"* → *"**Already fixed** (DEF228, DEF227)"* | **DEF227/228/229** (`258625a7`) | ✅ all three `fixed` |
| **CR150 rejected-item 8** | *"NOT VERIFIED — forward P/E"* | **DEF233** (`06098b4f` — *"give the PM the other half of the valuation"*) | ✅ `fundamentals.py:255-266` labels the PEG basis |
| **CR149 §2 / CR152 reject-1 / CR154 note** | *"DEF235 (the `size` prose-parse) is **FIXED** — `size` now comes from `ctx.trader_size_pct`"* | **DEF235** (`e319ba49`) | ✅ `fixed`; DEF237 minted as the residue |

### 2.2 Partly absorbed — the dangerous middle

| CR finding | What shipped | What did NOT |
|---|---|---|
| **CR153 F1 / CR154 A1 / CR155 Tier A** — the `Open your PROSE with:` opener displaces the stance envelope | **DEF247** (`bdb27e1a`, *"strip the stance envelope wherever it sits, and keep counting where it sat"*) — fixed the **parser**, so a displaced envelope no longer leaks `[STANCE: …]` to the user | ✅ **The prompt-side line is untouched.** `Open your PROSE with:` is still at line 23 of `aggressive_debator.md`, `conservative_debator.md` and `neutral_debator.md` at HEAD. All three CRs insist the fix belongs on the prompt side and CR155 rejects the parser fix pre-emptively. **DEF251 (open) is that work**, and it measured the real cost: 20% of debator turns emit **no** envelope at all, which DEF247 cannot recover |
| **CR149/CR151/CR154 → DEF241** — prose agents mis-compute cap consumption | **DEF243 + DEF241 round 1** (`719d2e48`) — each debator now receives its own drawdown figure with *"AMI computed this. Quote it; do not recompute it"* | ✅ **Bull Researcher and Research Manager receive nothing.** `room_prompts.py:432` still reads `proposal = trade_proposal if phase in ("RISK","VERDICT") else None`; `bull_researcher` is RESEARCHERS and `research_manager` is SYNTHESIS. Their prompts are byte-identical to pre-fix and still carry the raw `P×S/100` formula. The round-2 auditor caught this and reopened DEF241 |
| **CR145 Tier A** — *"delete the `32.4% gross margins, up 180bps YoY` example"* | **DEF244/DEF245 round-1** (`6f079de9`) replaced the literal | ⚠️ **It replaced it with something the fact sheet still cannot honour.** `content/agents/fundamentals_analyst.md:40` now reads *"gross margins at the level the fact sheet states, and the direction it is moving"* — but `fundamentals.py:237` renders **`profitMargins`** (net margin, `room_prompts.py:723`) and there is **no gross margin and no margin trend anywhere in the fact sheet** (margin trend is CR145 Tier D, unbuilt, blocked on the absent cache). The literal is gone; the unfollowable instruction is not. CR145 Tier A's other three items — render `marketCap`, `freeCashflow` as $, gross `totalDebt` — are **entirely undone**: `marketCap` is fetched at `fundamentals.py:270` and consumed **only** to derive `fcf_yield`, never rendered |
| **CR152 Tier B** — the thousands-separator gap | **DEF234** (`3f4d33d2`) fixed `_LEVEL_NUMBER` | ✅ `_LEVEL_PATTERNS` (`room_runner.py:1250-1254`) never got the group. **DEF242 (open) is that work**, filing only |
| **CR156 Tier A2** — PM rationale key aliases | nothing | ✅ **DEF239 (open)**, filing only. `_parse_pm_verdict` (`room_runner.py:1050`) reads `narration` alone |

### 2.3 Not addressed at all

Every remaining CR145–CR156 tier. In particular, the three levers Phase 5 ranked highest:

- **`_format_profile` still takes no `agent_id`** (`room_prompts.py:540`) — all 12 agents get a
  byte-identical fact sheet. CR145 Tier C, gating CR146 Tier B, CR147 Tier B.2, CR148 F9, CR151
  Tier A/D, CR152 Tier D.
- **`trade_asymmetry` is still rendered into no prompt.** Two call sites only, both post-hoc:
  `room_runner.py:1313` (the `[AMI …]` annotation) and `:3290` (the scripted no-LLM fallback).
  Phase 5 §1's remaining half, unchanged since it was written.
- **No risk state reaches any prompt.** `current_drawdown_pct` / `risk_existing_open_risk_pct` are
  built per run and passed only to `enforce_safety_floor`. Phase 5 §2: *"the only lever that puts
  information in front of an agent it has never had."*

---

## 3. Dependency ordering — what must precede what

```
DEF063 (AV key decision)  ──► CR147 Tier A.1 (delete or honour the AV conditional)
                          ──► CR023 residue

DEF236 (output contract)  ──► CR152 Tier A.4  (delete the Trader's fenced block)
                          ──► CR154 Tier C    (pick one output spec)
                          ──► ANY new prompt block  ── PHASE5 §2: "Adding blocks before
                                                       resolving DEF236 buys truncation"

DEF242 (comma group)      ──► CR152 Tier A.4  (CR152: "sequenced BEFORE Tier A.4")
DEF242                    ──► DEF237          (a wider group makes more numerals candidates;
                                               DEF237 is why a regex fix is not sufficient alone)

DEF251 (delete opener)    ──► CR153 Tier A / CR154 A1 / CR155 Tier A  (same edit, one commit)
DEF247 (shipped)          ──► DEF251          (parser first, prompt second — already in that order)

CR145 Tier C (agent_id)   ──► CR146 Tier B, CR147 Tier B.2, CR148 F9, CR151 Tier A + D,
                              CR152 Tier D, CR150 A4
                          ──► needs Saiful's visibility-matrix call BEFORE any code

CR145 Tier D              ──► BLOCKED: "fundamentals.py has no caching of any kind …
                              a TTL fundamentals cache ships in this tier or the tier doesn't ship"

DEF241 residue            ──► must be decided (widen the phase gate, or record the deferral)
                              BEFORE CR149 Tier C's derived-arithmetic backstop is designed

CR158 (done)              ──► CR157  (partition scoring by prompt_version, not by date)
DEF227/228/229 (done)     ──► DEF230 closing re-measure (tier-stratified, mandate-version-pinned)
DEF226                    ──► CR017 §5 step 0 (prompt-prefix reordering is unmeasurable until then)

CR160 (rename 6 agents)   ──► CONFLICTS WITH EVERYTHING. 272 files of user-visible copy plus every
                              agent prompt. Must not run concurrently with any prompt batch.
```

**The dependency most likely to be ignored, and what breaks:** `DEF236 → any render`. Batches 5, 6
and 8 below all *add* lines to prompts whose `_AGENT_MAX_TOKENS` was sized by DEF125 against a
`_LENGTH_GUIDE` the model already overshoots 61–100% of the time. Truncation is currently 0/198 —
absorbed by headroom, not by design. Ship a render batch first and DEF125's truncation class
returns, at which point the stance envelope is safe (DEF147 moved it to the front) but the *levels*
at the tail of a Trader turn are not.

---

## 4. Conflict risk — items that touch the same file or block

Batch along these lines and each file takes one Tier-A audit cycle instead of five.

| Shared surface | Items | Note |
|---|---|---|
| `content/agents/{aggressive,conservative,neutral}_debator.md:23` | DEF251, CR153 Tier A, CR154 A1, CR155 Tier A | **One line, three files, four items.** All three CRs independently demand a single commit |
| `room_prompts.py` `_LENGTH_GUIDE` / `_PROSE_FORMAT` / `_STANCE_FORMAT` / `_AGENT_MAX_TOKENS` | DEF236, CR145 Tier B, CR154 Tier C, CR152 Tier A.4, CR149 Tier A.2/A.3, CR147 Tier A exclusion | The single highest-contention block in the repo. Touches all 11 prose agents |
| `room_prompts.py` `_format_profile` (`:540`) | CR145 Tier A + C, CR146 Tier B, CR147 Tier B.2, CR148 Tier A, CR150 A2/A3, CR151 Tier A, CR152 Tier C, DEF242 (render format) | Every fact-sheet render. Batch or pay 8 audits |
| `room_prompts.py` RISK/VERDICT mandate snapshot (`:400-401`, `:432`) | CR153 Tier B ≡ CR154 Tier B ≡ CR155 Tier C ≡ CR156 Tier C, DEF241 residue, CR152 Tier C | **Four CRs propose the identical render.** CR156 states the dedupe rule: *"Ship it once, in whichever CR lands first, and delete the tier from the other"* |
| `room_runner.py` `_LEVEL_PATTERNS` / `_match_level` / `_annotate_rr_against_levels` / `_verify_and_annotate_geometry` | DEF242, DEF237, CR152 Tier B, CR146 F1, CR155 F3–F6 | Code only. One corpus replay covers all |
| `room_runner.py` `_parse_pm_verdict` / `_normalize_pm_action` | DEF239, CR156 Tier A2/B, DEF255 (coherence check) | PM only |
| `overlay_generator.py` `_mandate_common_block` (`:90-91`) | CR154 A3 | Hard-coded `30% cap` example, wrong in 8/18, **seen by all 12 agents** — cheapest all-agent correctness win on the board |
| `overlay_generator.py` per-agent blocks (`:296`, `:306-307`, `:385`, `:415-427`, `:471-477`) | CR146 Tier A, CR147 Tier A.4/A.5, CR151 Tier B, CR153 F2, CR156 Tier B | One file, five agents |
| `fundamentals.py` | CR145 Tier A + D, CR150 A2 + Tier B, CR147 Tier C, CR164 (EDGAR PIT path) | **CR164 already edits this file** (`ee21c8dc`, `8a68d858`). Check for drift before touching |
| `docker-compose.yml` + `config.py` + `test_config_compose_parity.py` | DEF063, CR148 Tier B, CR024 | One config commit |
| `backend/tests/unit/test_prompt_data_parity.py` (558 lines) | CR145 Tier C, CR148 Tier A, CR152 Tier C | Will turn red on any of them; CR145 says it must learn "not this agent's lane" ≠ "dropped" |

---

## 5. CR142 tier per item

CR142's literal Tier A list does not name "prompt bytes" — the closest bullet is *"compliance-perimeter
surfaces: advice detection, Sharia rulings, disclosures, published methodology copy"*. The
**Tier-A-for-prompt-bytes convention** is established in the rows themselves: DEF236 (*"any fix
changes what all eleven agents receive (CR142 Tier A)"*), DEF251 (*"this is a CR142 Tier A change and
owes the audit handshake"*), DEF255 (*"Tier A under CR142 if the fix touches prompt bytes"*) and
CR145 Tier B (*"CR142 Tier A"*). Applied consistently below.

| Item | Changes prompt bytes? | CR142 tier |
|---|---|---|
| DEF236 | **Yes** — all 11 prose agents | **A** (row states it) |
| DEF251 | **Yes** — 3 debator files | **A** (row states it) |
| DEF241 residue | **Yes** — Bull + RM prompts gain a rendered line | **A** |
| DEF255 | **Yes** if the PM contract changes | **A** (row states it); the coherence check alone is **B** |
| DEF063 | No (config + env) — **but** CR147 A.1's paired prompt edit is **A** | **B** for the config half |
| DEF239 | No — parser key aliases | **B** (user-visible behaviour: what the verdict board shows) |
| DEF242 | No — one regex | **B** |
| DEF237 | No — a plausibility gate | **B** (threshold is a judgement call; row says the corpus cannot validate it — P16) |
| DEF230 | No — a measurement | **C** |
| CR145 A | **Yes** (fact sheet + `fundamentals_analyst.md`) | **A** |
| CR145 B | **Yes** | **A** (stated) |
| CR145 C | **Yes** (assembled bytes) | **A** |
| CR145 D | **Yes** (retires a disclosure) | **A**; the cache itself is **B** |
| CR146 A | **Yes** (prompt-only) | **A** |
| CR146 B/C | **Yes** (rendered) | **A** |
| CR147 A | **Yes** (incl. a shared header on all 12) | **A** |
| CR147 B/C | **Yes** (rendered) | **A**; the recency floor + surcharge change is **B** |
| CR148 A | **Yes** (rendered) | **A** |
| CR148 B | **Yes** (freshness string) + config | **A** |
| CR148 C | **Yes** | **A** |
| CR148 D | No — schema | **B** |
| CR149 A | **Yes** | **A** |
| CR149 B | Policy + code + a prompt table | **A** |
| CR149 C | No — annotators | **B** |
| CR150 A1–A7 | **Yes** | **A** |
| CR150 B | **Yes** (rendered) | **A** |
| CR150 C | **Yes** (deletion) | **A** |
| CR151 A/B/C | **Yes** | **A** |
| CR151 D | **Yes** (gating change) | **A** |
| CR152 A | **Yes** | **A** |
| CR152 B | No — regex (== DEF242) | **B** |
| CR152 C | **Yes** (rendered) | **A** |
| CR153 A / CR154 A / CR155 A/B | **Yes** | **A** |
| CR153 B ≡ CR154 B ≡ CR155 C ≡ CR156 C | **Yes** (rendered) | **A** |
| CR156 A1 | shipped (DEF238) | — |
| CR156 A2 | No (== DEF239) | **B** |
| CR156 B | **Yes** | **A** |
| CR156 D | No — docs only | **C** |
| CR157 | No — capture + scoring | **B** (new table + job); the report is **C** |
| CR160 | **Yes** — every agent name in every prompt + 272 files | **A** |
| CR164 | **Yes** under `as_of` (fact sheet contents) | **A** for the data layer; the harness is **B** |
| CR104 residue | **Yes** (narrative scaffolding) | **A** |
| CR069 ph2/3 | **Yes** (`_compliance_block`) | **A** — Sharia rulings are a *literal* CR142 Tier A bullet |
| CR141 / CR017 | No — dormant routing | **B** on the day a call site opts in |
| CR023 / CR024 residue | No — config/quota | **B** |
| CR143 | No | **C** |

---

## 6. Feed keys set on the Mac but not reaching the container (the DEF063 class)

Cross-checked `infra/alpha.env` → `docker-compose.yml` api-alpha `environment:` → `Settings.model_fields`
→ `test_config_compose_parity.py::_NOT_FORWARDED`.

**Two findings.**

### 6.1 `ADANOS_API_KEY_SECONDARY` — a live key that no code path can ever see

```
infra/alpha.env:103    ADANOS_API_KEY_SECONDARY=sk_live_9c28873b517ae0261cb0e19de5e6739b
docker-compose.yml     grep ADANOS → only line 259 (ADANOS_API_KEY). No SECONDARY.
config.py              grep adanos → only line 202 (adanos_api_key: str = ""). No secondary field.
```

This is DEF063's exact shape with one twist that matters: **`test_config_compose_parity.py` cannot
catch it.** The test walks `Settings.model_fields` → compose (`test_config_compose_parity.py:68`,
`_NOT_FORWARDED` at `:29`). A key that exists in the env file but has **no `Settings` field** is
invisible to it in both directions. CR148 Tier B named this and its assessment is correct:

> *"**Latent, DEF063-class:** `ADANOS_API_KEY_SECONDARY` exists in melehost's `.env` but no
> `adanos_api_key_secondary` setting exists in `config.py` and nothing forwards it in
> `docker-compose.yml`"*

Cost: 250 Adanos calls/month of paid-for spare quota sitting idle while CR148 Tier B is being asked
to make a **TTL-shortening budget decision under exactly that quota constraint** (30-day TTL ≈ 250
distinct tickers/month vs 7-day TTL ≈ 58). Doubling the quota is on the table and nobody costed it.

### 6.2 `ALPHA_VANTAGE_API_KEY` — forwarded correctly, dark by value

```
infra/alpha.env:84     # ALPHA_VANTAGE_API_KEY=AL9FWEE8DYN7978M      ← COMMENTED (parked by CR040)
docker-compose.yml     ALPHA_VANTAGE_API_KEY: ${ALPHA_VANTAGE_API_KEY:-}   ← forwarded
config.py:195          alpha_vantage_api_key: str = ""
```

The forwarding is fine — CR040 fixed that. The **value** was deliberately parked so enabling stays a
decision. But nothing downstream knows it is parked, so:

- `content/agents/news_analyst.md:16-17` promises *"where configured — Alpha Vantage's per-article
  sentiment-scored feed"* and *"Where Alpha Vantage supplies it, a sentiment tag per headline"*;
- `room_prompts.py:613-615` tells **all 12 agents** *"Some headlines may carry a sentiment tag; treat
  it as one input, not a verdict"*;
- CR147 measured the consequence: **216/216 prompts assert the tag may exist, 0/216 catalyst lines
  carry one, and 1 of 18 News turns invented the provenance** ("the sentiment tag from 24/7 Wall
  St.") — an invented *source*, which no numeric-grounding metric can see.

This is the live half of DEF063 and it has been open since 2026-07-17.

### 6.3 Clean

`LUNARCRUSH_API_KEY` is commented and vestigial (no Settings field, no compose entry, no code path) —
harmless, worth deleting from `alpha.env` when the file is next touched. `SMTP_HOST` is parked but
`SMTP_USER`/`SMTP_PASSWORD` are set, which is an ops question, not a feed question. Everything else
absent from the api-alpha block is compose-level wiring by design (`CF_TUNNEL_TOKEN`, `AMI_ENV`,
`POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `WEBSITE_*`, `REVENUECAT_*_SDK_KEY`).

---

## 7. What CR143 concluded, and what it says is still outstanding

Read from `README.md`, `PHASE5_feasibility_verdict.md`, and the `CR143.row.md` Phase-1 correction.

### Concluded

1. **The premise was wrong and the audit says so.** The CR was filed on five instruction-following
   failure rates that argued for putting the *model* on the table. Epoch-partitioning killed three:
   PM reformatter **0/18** (the filed 18.4% was a 30-day pooling artefact in which 2026-07-30 alone
   contributed 15 reformats on 22 turns), banned `MODIFY-*` **0/18**, stance-envelope-missing
   **10/198 = 5.1%**. *"Every rate here is meaningless if pooled across a prompt change."*
2. **The model arm (Phase 4b) is dropped.** *"E1 near zero; three of four remaining failures are our
   code; constrained decoding is already available on the deployed server."* A live probe against
   `192.168.20.74:8000` returned schema-conformant JSON first call on server `0.23.1.dev0+g0fc695fc6`
   — so the PM's JSON can be made unbreakable without touching the model.
3. **Six of eight accuracy levers are feasible; §3 splits; §4 is rejected as specified.** §4 (flag
   every numeral not present in the prompt) would fire on ~4.3% of numerals at a false-positive rate
   near 100% — every novel figure in the corpus was hand-read and found legitimate. It is also the
   general-pattern-over-agent-prose class with the worst record in the repo (DEF231 took nine audit
   rounds; DEF234/235/242 all came from it), and CR144 is the convention written to bar it.
4. **The prompts are, on the measured epoch, mostly doing their job.** Grounding 92.6%, inherited
   3.1%, novel 4.3% and all legitimate. The 63×-wrong drawdown that started the alarm was **our
   parser**, not the model (DEF235).
5. **Phase 3b's rejection of the scope-firewall concern is superseded** by CR145's direct
   measurement — differentiation (M2b = 0.128) was the wrong instrument; agents can differ sharply in
   emphasis while borrowing each other's facts. News cites valuation 18/18.

### Outstanding, in CR143's own words

Phase 5 §3, *"By accuracy gained ÷ blast radius, with the memo's dependency inverted — subtract
before you add"*:

| # | Work | Status today |
|---|---|---|
| 1 | DEF236 + DEF251 — unify the output contract, re-derive `_AGENT_MAX_TOKENS` | **both open, both filing-only** |
| 2 | Risk-state block + DEF241 residue (Bull, RM) + render `trade_asymmetry` | **none started** — verified: no risk state in any prompt, `trade_asymmetry` in no prompt, phase gate unchanged |
| 3 | CR156 — deterministic verified-facts recap above the PM transcript | not started |
| 4 | CR145 Tier A — market cap / FCF $ / gross debt; delete the `32.4% gross margins` example | **example replaced (DEF244/245), the three renders undone, and the replacement text names a field the sheet still lacks** |
| 5 | Deterministic scorer gate over the frozen golden set | not started |
| 6 | CR145 Tier C — per-agent fact sheets | **needs Saiful's visibility-matrix call** before any code |
| 7 | PM structured output via `response_format` | not started; needs `LLMGateway.stream_chat()` to grow the parameter across all four providers, degrading **loudly** on Anthropic failover (which needs tool-use, not `response_format`) |

Explicitly **not** scheduled: §4 as specified, §6.2 `[unverified figure]` transcript labels, few-shot
anchoring (*"DEF245 is the proof"*), the §3 part-2 prose-agent repair loop (deferred, not rejected —
zero measured demand at 0/18, doubles worst-case calls on a streaming path), and the Phase 4b model
arm.

Phase 5 also records the constraint the rest of this survey is built around:

> *"Constraint the memo misses: DEF236 (open) measured every prose agent over its length guide
> 61–100% of the time, and `_AGENT_MAX_TOKENS` was sized to that guide (DEF125). Adding blocks
> before resolving DEF236 buys truncation. **Subtract before you add** — or ship §2 with re-derived
> token budgets in the same commit."*

---

## 8. Recommended batch sequence

Ordered. Each batch is 2–4 items, states what it changes, what verifies it, and its CR142 tier.
Batches 1–3 are subtraction and parser work; nothing is *added* to a prompt until Batch 4.

### Batch 1 — Unify the output contract (subtract first)
**Items:** DEF236 · DEF251 (⊇ CR153 Tier A, CR154 A1, CR155 Tier A) · CR154 Tier C
**Changes:** `room_prompts.py` `_LENGTH_GUIDE` / `_PROSE_FORMAT` / `_AGENT_MAX_TOKENS`;
`content/agents/{aggressive,conservative,neutral}_debator.md:23` (delete the `Open your PROSE with:`
bullet, naming what owns the slot — `market_analyst.md`'s *"That's the Trader."* is the in-repo
precedent).
**Verifies:** re-run the 32-ticker `cr143-def247` batch; **parsed-stance yield ≥ 95%** of debator
turns with the residual hand-read; argument length must **not** shorten (the opener carries the
role's framing); re-measure the six over-budget rates from DEF236; `test_cr106_stance_envelope.py`
**unmodified and green**; `pytest backend/tests/unit/ -q`.
**Tier: A.** Owes the audit handshake.
**Why first:** every later batch adds prompt bytes, and `_AGENT_MAX_TOKENS` is currently calibrated
against a guide the model cannot meet. Truncation at 0/198 is headroom, not design.

### Batch 2 — Parser hardening (code only, no prompt bytes)
**Items:** DEF242 (≡ CR152 Tier B) · DEF237
**Changes:** `room_runner.py:1250-1254` — reuse `_LEVEL_NUMBER`'s comma group in `_LEVEL_PATTERNS`;
`_annotate_rr_against_levels` / `_verify_and_annotate_geometry` gain `profile["last_close"]` and a
**symmetric** ratio plausibility gate (the existing `_DIRECTION_MAX_PLAUSIBLE_GAP_PCT` formula is
asymmetric — a level 13.8× the close evaluates to −92.8% and passes 400%).
**Verifies:** replay the committed 216-turn epoch corpus **and** the 811-row `pm_verdict_corpus.txt`;
assert on the extracted *value*, not on whether a match occurred; confirm the wider number group does
not resurrect DEF235's shape; state the threshold as **derived**, not chosen — with 5 full triples in
216 turns the corpus cannot validate one (P16), so say so.
**Tier: B.**
**Why second:** CR152 states its Tier B must precede Tier A.4, and DEF237 is why a one-line regex fix
is not sufficient on its own.

### Batch 3 — Delete the demands the system cannot honour (prompt-only, free)
**Items:** CR146 Tier A · CR152 Tier A (now unblocked by Batches 1+2) · CR149 Tier A · CR147 Tier A
items 2/3/4/5
**Changes:** `content/agents/{market_analyst,trader,bull_researcher,news_analyst}.md` +
`overlay_generator.py` (`:296` watchlist half, `:306-307` macro softening, the market-analyst leverage
line, the `Path.ACTIVE` R:R floors). Deletions only.
**Verifies:** re-measure each deleted instruction's compliance rate — all were 0/18 or 1/18, so the
acceptance is that **nothing else moves**; `pytest backend/tests/unit/ -q`; the CR105 Amendment-1
rule (a prompt edit whose effect is not re-measured is the trap).
**Tier: A.**
**Note:** CR146 Tier A alone removes two of five output bullets that have never once been obeyed, and
removes the level-emitting instruction that produced the one live `_LEVEL_PATTERNS` mis-parse on that
agent (NVDA, `"stop-loss below the 50-day low of $189.8"` → stop = **50**).

### Batch 4 — The dark feed key, and the claim that depends on it
**Items:** DEF063 (both halves) · CR147 Tier A.1 · CR024 residue
**Changes:** (a) **Saiful's call** — populate `ALPHA_VANTAGE_API_KEY` in `infra/alpha.env` **or**
delete both claims (`news_analyst.md:16-17` and the shared header `room_prompts.py:613-615`). CR147:
*"Not both half-done."* (b) Add `adanos_api_key_secondary` to `config.py`, forward it in compose, and
extend `test_config_compose_parity.py` to walk **env-file → Settings** as well as Settings → compose,
so an env key with no Settings field stops being invisible.
**Verifies:** `test_config_compose_parity.py` red against the real gap before it is green;
`/v1/admin/config-check`; a live uncached `fetch_live_sentiment()` on the secondary key; if AV is
enabled, one catalyst line carrying a real tag; if deleted, 0 occurrences of the conditional in a
fresh `dump_assembled_prompts` run.
**Tier: A** for the prompt half (the header reaches all 12), **B** for the config half.

### Batch 5 — Render what is already fetched (fundamentals + technicals)
**Items:** CR145 Tier A · CR150 A2/A3 · CR146 Tier B
**Changes:** `fundamentals.py` returns `marketCap`, `freeCashflow` as $, gross `totalDebt`;
`room_prompts.py` renders them plus % below the 52-week high / % above the low, SMA-20, SMA-50 and
the volume ratio's **value** (today only its label ships); reconcile `Reference price` against
`last close` (they diverge in 7 of 16 post-fix prompts); **fix `fundamentals_analyst.md:40`** — it now
asks for *"gross margins at the level the fact sheet states, and the direction it is moving"* and the
sheet carries **net** margin and no trend at all; correct the input list's *"net cash"* to the *"Net
debt"* the renderer actually emits.
**Verifies:** rendering market cap is what makes *"Avoid microcaps (< $500M market cap)"* — a HARD
compliance constraint carried in 17/18 prompts against 0/18 fact sheets — followable for the first
time; `test_prompt_data_parity.py`; `dump_assembled_prompts --verify`.
**Tier: A.** Blast radius all 12 (`_format_profile` has no `agent_id` yet — accept the widening
knowingly, as CR146 Tier B says, or wait for Batch 9).

### Batch 6 — Render the risk state (the only new information on the board)
**Items:** the deduped **CR153 B ≡ CR154 B ≡ CR155 C ≡ CR156 C** · DEF241 residue · CR152 Tier C ·
CR150 A4/A5/A6
**Changes:** thread `ctx.current_drawdown_pct` and `ctx.risk_existing_open_risk_pct` (+ pace counts,
last stop-out) into `build_room_messages`' RISK/VERDICT mandate snapshot — **once**, deleting the tier
from the other three CRs; per-position `stop` in `_build_sim_holdings_block`; widen
`_drawdown_snapshot_line`'s phase gate to reach Bull (RESEARCHERS) and RM (SYNTHESIS) **or** record
the deferral explicitly (DEF241's row refuses to let a re-scope pass as a close); disclose the
journal window and say structurally when there is no history.
**Verifies:** a `stop=None` must render *"no stop recorded"* via `field_state` UNAVAILABLE, never
silence (CR040); preserve `CONTEXT_NOT_SUPPLIED`; label open risk *"across open positions carrying a
stop"*; an **end-to-end test driving the real `RoomRunner.run()`** — DEF241's own mutation proof
showed MUT-1/MUT-2 die only under that, because every other test passes the kwarg itself (the DEF238
blind spot); re-measure DEF241's wrong-figure rate over ≥30 convenes post-promotion.
**Tier: A.** **Hard-gated on Batch 1** — this is the batch PHASE5 warns buys truncation if DEF236 is
still open.

### Batch 7 — The Portfolio Manager
**Items:** DEF239 (≡ CR156 Tier A2) · CR156 Tier B · DEF255 · CR156 Tier D
**Changes:** accept the rationale from `rationale`/`reasoning`/`reason` and fire `_PM_NO_RATIONALE`
only when **no** key carries prose (do **not** widen to a general free-text scrape — the disclosure
exists for genuinely unexplained decisions, DEF232); reconcile the REJECT-inside-PASS vocabulary the
REPLACES line leaves uncovered (6/18); define `horizon_days` as a **thesis** horizon distinct from the
mandate's investment horizon, give it an admissible range anchored to the evidence actually supplied
(3-month technicals, TTM fundamentals, 52-week range), and add a deterministic stop-vs-horizon
coherence check beside the existing geometry annotations; fix the doc claim in `agent_prompts.py:95`
and `safety_floor.md:81` (true on 1-on-1, false in the Room).
**Verifies:** re-run against the 811-row `pm_verdict_corpus.txt` before shipping and re-derive the
5.6%; keep `test_room_prompt_parity.py:68`'s MODIFY canary; the `## Output format` block is
load-bearing on the 1-on-1 surface — keep or replace, never delete; re-run CR164's pinned regression
batch and require no approval pairs a >365-day horizon with a stop closer than realized volatility;
**re-measure DEF231's direction-signal rate** — DEF239's fix enlarges its input population.
**Tier: A** (B for DEF239 alone, C for Tier D).

### Batch 8 — Social + news feed depth
**Items:** CR148 Tier A · CR148 Tier B · CR147 Tier B.1
**Changes:** extend `SocialSentiment` and `_to_sentiment` to carry the four dimensions already
arriving on the same Adanos call (per-subreddit mentions/score/buzz, positive/negative/**neutral**
counts, unique posts, subreddit count) and render them under `_social_detail_lines`, plus the sample
size (n ranges 10 → 3,990 and is rendered identically at both ends); render `fetched_at` and stop
saying *"as of this call"* for a cache whose rows are 93% older than 7 days; add a news recency floor
that flips `field_state["news"]` to UNAVAILABLE — *"also the honest place to stop charging the
2-credit surcharge."*
**Verifies:** `test_prompt_data_parity.py:157/386/410-419` asserts every `SocialSentiment._field` is
rendered-or-declared on both surfaces — it **will** bite, and that is why this tier is hours not
minutes; re-measure the 9/18 fabricated per-community attribution rate, which is what the new fields
are for.
**Tier: A.** Carries **one Saiful decision**: the TTL/quota trade (30-day ≈ 250 distinct
tickers/month vs 7-day ≈ 58) — cheaper if Batch 4 has already doubled the quota.

### Batch 9 — The lane firewall (needs a decision before any code)
**Items:** CR145 Tier C · CR151 Tier A · CR147 §1 / CR148 F9 acceptance re-measure
**Changes:** `_format_profile(profile)` → `_format_profile(profile, agent_id)` with an explicit
visibility matrix; render the asymmetry line for the Research Manager from two numbers already on the
sheet, naming its anchor.
**Verifies:** `test_prompt_data_parity.py` must learn *"not this agent's lane"* ≠ *"dropped"* or it
turns red; interacts with CR098 (withheld analysts already strip fact-sheet lines) and CR104
`field_state`; acceptance is the cross-lane citation rates coming down from News 18/18, Fundamentals
11/18, Social 11/18, Market 6/18.
**Tier: A.** **BLOCKED on Saiful:** Bull, Bear, RM, Trader and PM *legitimately* need cross-lane data,
so the matrix is a product decision, not a filter. Do not start code before that call.

### Batch 10 — Instruments and the closing measurements
**Items:** DEF230 closing re-measure · CR157 · CR164 pinned regression batch
**Changes:** none to prompts. A tier-stratified, mandate-version-pinned replay of a fixed ticker set
diffed against the corrected human-only figures (32.7% → 0%); `room_run_conclusions` capture + the
weekly scoring batch, partitioned by `llm_audit.prompt_version` (CR158) and never by date.
**Verifies:** DEF230's row is explicit that specifying this without stratifying on tier measures the
mix shift, not the prompt.
**Tier: C** (B for CR157's new table + timer).

### Deliberately unscheduled

- **CR160 (rename 6 agents)** — 272 files of user-visible copy plus every agent prompt. It conflicts
  with every batch above. Schedule it as a **freeze point** after Batch 9, not concurrently. Its AR/MS
  transcreation half (Bull/Bear → Long-Side/Short-Side) is the risky part.
- **CR145 Tier D** — blocked on `fundamentals.py` having no caching of any kind. The cache is a
  prerequisite, not a follow-up.
- **CR149 Tier B**, **CR150 Tier C**, **CR151 Tier D**, **CR152 Tier D**, **CR148 Tier C/D** — all
  await a Saiful decision (100%-cap reachability, the short clause, sector-weight widening, ATR,
  three instructions with no data dimension).
- **CR017 §5 step 0** — unmeasurable until DEF226 is resolved on the vLLM host.
- **CR069 phases 2/3** — Sharia rulings are a literal CR142 Tier A category and need a named-standard
  decision first (the two free sources disagree on 47.9% of the union).
