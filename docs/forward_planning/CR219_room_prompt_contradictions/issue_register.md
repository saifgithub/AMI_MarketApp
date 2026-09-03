# CR219 — consolidated issue register

Every unique issue raised across the five independent reviews (`kimi/`, `antigravity/`,
`fable/`, `GLM/`, `QWEN/`), one row each, for tracking through to close. Companion to
[`reviewer_comparison_matrix.html`](reviewer_comparison_matrix.html) (same `R#` refs —
that page shows what each reviewer said per issue; this page tracks status and next
action). Built from all 16 review files read in full, 2026-09-02.

**61 issues.** 17 map to the base CR's numbered findings (#1–17); 44 were surfaced by
one or more reviewers beyond that list.

## How to read the Status column

| Status | Meaning |
|---|---|
| `RULED` | Saiful made an explicit decision, cited below — build it as ruled |
| `CONVERGENT` | Every reviewer who addressed it agrees — no decision needed, just build |
| `FORK` | Reviewers land on genuinely different answers and it has **not** been reconciled — needs a call before it can be built |
| `CORRECTION` | A stale fact in the base CR doc, not a design question — just fix the doc |
| `OPEN` | Raised (usually by one reviewer) with no ruling and no disagreement — awaiting a decision |

**One caveat that affects several FORK rows below:** two separate ruling sessions
happened. `GLM/02_improved_plan.md` records Saiful's R1–R5 rulings on where
Kimi/Antigravity/Fable disagreed. `QWEN/02_review_of_plan.md` and `03_improved_plan.md`
record a *different* set of rulings Saiful made against QWEN's own (blind) review. The
two sessions were never cross-reconciled — so a few places where GLM's doc claims
"unanimous" (R21, R40) actually still have a live fork against Fable or QWEN's own
ruling track. Flagged inline where it happens.

Use `Build` as a plain checklist — flip `☐` to `☑` as each item lands, ideally in the
same commit that closes it.

**2026-09-02, later:** the six roll-up forks were put to Saiful and ruled (provenance:
[`dev_instructions/DECISIONS_2026-09-02.md`](dev_instructions/DECISIONS_2026-09-02.md));
per-row build instructions for every item live in [`dev_instructions/`](dev_instructions/).

---

## Class A — persona denies a field the sheet marks LIVE

| Ref | Issue | Status | Disposition | Reviewers | Build |
|---|---|---|---|---|---|
| R1 | #1–2 Margin trend denied outright | CONVERGENT | Rewrite to a two-point rule: quote the bps figures and their two basis dates, never extend the direction beyond them | K,A,F,G,Q | ☑ |
| R2 | #3 Buybacks / capital returned / M&A denied | CONVERGENT | Split: buybacks + capital-returned claimable (capital-returned flagged as AMI's sum); M&A stays denied | K,A,F,G,Q | ☑ |
| R3 | #4 "No history for any of them" (multi-period figures) | CONVERGENT | Narrow to what's actually still true — only the 6 multi-period figures the sheet states are citable | K,A,F,G,Q | ☑ |
| R4 | #5–6 Market analyst series/trend denials | CONVERGENT | Cite window/primary trend + RS by name; indicator trajectories ("RSI is clearing") stay denied | K,A,F,G,Q | ☑ |
| R5 | #7 News analyst "not supplied consensus estimates" | CONVERGENT | Delete the sentence; replace with a use-mention naming it the Street's estimate | K,A,F,G,Q | ☑ |
| R6 | #8 Social "no historical baseline" — the weak link | CONVERGENT | Narrow, don't delete — name exactly what the mention trend does/doesn't baseline. **Reject Antigravity's rewrite** (K/F/G/Q all flag it as granting a false sentiment-baseline claim) | K,A,F,G,Q | ☑ |
| R7 | Which denials must *stay* (peer-basket P/E, MACD/Bollinger, Twitter/X) | CONVERGENT | Keep all 3; move into the guard's known-absent list rather than free prose | K,F,G | ☑ |

## Root-cause fix mechanism & the guard

| Ref | Issue | Status | Disposition | Reviewers | Build |
|---|---|---|---|---|---|
| R8 | How to stop the next field-adding CR from recreating this bug | **RULED** | Hand-fix + guard (rejects Antigravity's static contract block and Fable's generated registry) — `GLM/02` Ruling R1 | K,A,F,G | ☑ |
| R9 | Guard must check negative claims TRUE, not just present | RULED / CONVERGENT | Required — folds into guard v2 under R1 | K,A,F,G | ☑ |
| R10 | Guard must scan the whole file, not just `## Inputs`→`## Output` | RULED / CONVERGENT | Required — folds into guard v2 under R1 | K,A,F,G,Q | ☑ |
| R11 | Guard must also cover the overlay generator (map demands → field_state keys) | RULED / CONVERGENT | Required — folds into guard v2 under R1 | K,F,G | ☑ |
| R12 | Collision markers — a future field ships, an absence claim goes red automatically | **RULED** | Adopted into the R1 guard design, explicitly "stolen" from Fable's registry proposal | F,G | ☑ |
| R13 | Guard exhaustive by construction — every persona file must be mapped, unknown = red | **RULED 2026-09-02** | Adopt — QWEN's Gap 6 folds into the R1 guard spec (makes R44's sweep automatic). Build: `dev_instructions/WP02_guard.md` | Q | ☑ |
| R14 | Guard should document its own authored-mapping blind spot | RULED / CONVERGENT | Adopted — state the limit in the test docstring | K,G | ☑ |

## Class B — instruction fights instruction

| Ref | Issue | Status | Disposition | Reviewers | Build |
|---|---|---|---|---|---|
| R15 | #9 Technical overlay demands a trend the persona forbids | CONVERGENT | Resolved automatically once R4 lands; add one overlay clause naming the trends the sheet states. Done `3420fe74` (+R11 mapping) | F,G,Q | ☑ |
| R16 | #10 Bull "end with CONVICTION" vs "write once at top only" | **RULED 2026-09-02** | Disambiguate vocabulary, keep both — Fable withdrew its delete dissent (the trailing CONVICTION is the code-parsed stance envelope, `room_runner.py:2902`). Done `3ae20272` (persona uses "case strength"; envelope byte-identical) | K,F,G,Q | ☑ |
| R17 | #11 Bull date-pairing vs no-speculation | CONVERGENT | Scope the no-speculation ban to claims; dating your own inference is honesty, reword to say so. Done `3ae20272` | K,G,Q | ☑ |
| R18 | #12 Trader WAIT vs mandatory stop-loss | CONVERGENT | Fix in `trader.md` persona (WAIT/HOLD carve-out), land alongside the already-landed CR210 regex — not a regex change. Done `41a18e4a` (37/37 CR210 tests) | K,A,F,G,Q | ☑ |
| R19 | #13–14 Risk Officers handed operands, forbidden to compute | CLOSED — finding was stale | WP03 diagnostic (2026-09-02): DEF241+DEF243 (closed 2026-08-13) already precompute and label the per-role drawdown contribution (`_drawdown_snapshot_line`: "AMI computed this. Quote it; do not recompute it"). No code change; correction note added to the base doc | K,F,G,Q | ☑ |
| R20 | Should agents ever do arithmetic on sheet figures? (a general policy, not just #13/14) | **RULED** | Global ban + extended precompute — AMI mints and labels every derived number, `Asymmetry` line as the template. Ruled inside QWEN's own review track (`QWEN/02`, `QWEN/03`). Done `e394b1d3` (policy in shared tail + guard section; one documented DEF245-motivated allowlist entry in bear_researcher.md) | Q | ☑ |

## Class C — overlay demands data nothing fetches

| Ref | Issue | Status | Disposition | Reviewers | Build |
|---|---|---|---|---|---|
| R21 | #15 Short/medium-horizon demand (earnings revisions, surprise history, guidance) | **RULED 2026-09-02** | **Back with real fetches, inside CR219** (GLM track upheld; QWEN/Fable delete position overruled). Done: fields `ecb8f199` (eps_trend + earnings_history — NOT earnings_dates, needs uninstalled lxml), demand aligned `955349bc` ("guidance" dropped, guard carry-list deleted, R11 mapping resolves every phrase) | K,F,G,Q | ☑ |
| R22 | #16 "Guidance" demand collides with the sheet's own disclaimer | CONVERGENT | Fold into the guard as a forbidden-phrase check on overlay_generator outputs | G,Q | ☑ (check built; the one live violation is carried in `KNOWN_R22_VIOLATIONS_PENDING_WP03` — deleting the demand at `overlay_generator.py:447` is WP03's, and the guard's vacuity test goes red the moment it does, forcing the carry-list empty) |

## Class D & E — surface / lane gaps

| Ref | Issue | Status | Disposition | Reviewers | Build |
|---|---|---|---|---|---|
| R23 | Class D — 8 downstream agents hold the sheet, briefs never mention it | **RULED** | Name the sheet + a "quote, don't re-derive" numbers rule, now (not the expensive lane-gating half). GLM's R3 and QWEN's own ruling converge on this independently. Done `5ff7375b` (8 briefs; AC4's before-arm is the banked 66-turn corpus) | K,F,G,Q | ☑ |
| R24 | Class E — 1-on-1 lane gap (Fundamentals gets price-prediction data its persona forbids) | CONVERGENT | Lane-gate `build_live_data_block()` on the 1-on-1 surface, same mechanism as the Room lanes. Done `a5731d32` + CR040 loud-withhold notice `14b32e92` (reuses `_AGENT_LANES`; guard covers the 1-on-1 surface) | K,F,G | ☑ |

## Finding #17 — primary_goal collected, never branched on

| Ref | Issue | Status | Disposition | Reviewers | Build |
|---|---|---|---|---|---|
| R25 | Wire it, or delete the printed line? | **RULED** | Wire it, as weighted guidance — not hard PM filter gates. GLM's R2 and QWEN's own ruling converge (QWEN sequences it as Phase 3b). Done `2f70cc5d` (`_goal_block`, all 6 arms distinct) | K,A,F,G,Q | ☑ |
| R26 | If wired, by what mechanism? | RULED / CONVERGENT | Weighted guidance per goal value; PM keeps holistic gatekeeping. QWEN adds: exhaustive `match` over every enum arm, no silent default on an unhandled value. Done `2f70cc5d` (`case _:` raises — load-bearing, since Pydantic `model_copy` skips re-validation) | K,A,F,G,Q | ☑ |

## Factual corrections to the base CR doc

| Ref | Issue | Status | Disposition | Reviewers | Build |
|---|---|---|---|---|---|
| R27 | `pm_self_consistency_samples` "defaults to 1" | CORRECTION | Stale — actual default is 5 since CR214 (`config.py:751`). Fix the CR doc's arms section. **Fable's own `05` doc still repeats the stale figure** — its Tier-1 item 1 (R47 below) needs re-reading in light of this | K,G,Q | ☑ |
| R28 | "An uncommitted `trader_block_regex` hunk" | CORRECTION | Stale — landed via CR210 commit `49380813`. Re-point the citation, add to `verify_citations.py`'s tracked list | G,Q | ☑ |

## Measurement & the acceptance instrument

| Ref | Issue | Status | Disposition | Reviewers | Build |
|---|---|---|---|---|---|
| R29 | Does citation-rate recovery prove the Room's answer got better? | CONVERGENT | No — it's a suppression proxy, not an outcome measure. Need a real benchmark (R31). Distinction documented in `harness/README.md` (2c75f1c8) | K,F,G,Q | ☑ |
| R30 | Should Acceptance #4 gate the merge, or trail it? | **RULED 2026-09-03** | **Trail the merge** — Saiful ruled the standing Fable position as put to him: ~1–2 weeks Alpha traffic, no fixed threshold, no revert on a null result (a null is a new finding). Closes the gap where this was being *treated* as decided without ever being ruled | F | ☑ |
| R31 | Benchmark / golden-set harness design | **RULED 2026-09-02** | Merged: QWEN's deterministic scorers + ticker×mandate frame at Kimi/GLM's initial scale (4–5 cached profiles), production 5-way PM vote (R32); grow to 8–10 once scorers hold. Built + smoke-tested (`harness/`, 2c75f1c8, CAT×long 12/12 turns) | K,G,Q | ☑ |
| R32 | PM verdict sampling inside the harness | CONVERGENT | Mirror the production 5-way vote, not single draws (Kimi's D3 / GLM's R5). Done in `harness/run_convene.py` (smoke: 5 draws, 4 parsed, 4/4 PASS) | K,G | ☑ |

## Data additions

| Ref | Issue | Status | Disposition | Reviewers | Build |
|---|---|---|---|---|---|
| R33 | Interest coverage (free) | CONVERGENT | Build — zero network cost, #1 arm request (21× from 9/12 agents). Done `ab9decb2` | K,A,F,G,Q | ☑ |
| R34 | Capex line (free) | CONVERGENT | Build — already implicit in rendered FCF. Done `a841ac13` (explicit line; R20 forbids reverse-engineering it) | K,F,G,Q | ☑ |
| R35 | Buyback pacing (free) | CONVERGENT | Build — four-quarter series already fetched and discarded. Done `c7c40213` | K,F,G,Q | ☑ |
| R36 | ATR / volatility for stop sizing | CONVERGENT | Build — computable from daily bars already fetched. Fable: confirm the bar window covers 14+ sessions first. Done `a4459b01` (window confirmed ~65 sessions; Trader+RO lanes only) | K,A,F,G,Q | ☑ |
| R37 | Historical median multiples (5/10yr P/E, EV/EBITDA) | **RULED 2026-09-02** | **Build in CR219** (Fable's defer dissent overruled). Window labeled honestly (~4–5y from yfinance, not 10). Done `d3943aa5` (own-history medians, window+year-count keys ride each half; peer-basket denial R7 stays true — marker did not fire) | K,A,F,G | ☑ |
| R38 | Debt split: industrial vs. captive finance | **RULED 2026-09-02** · note **ACKNOWLEDGED 2026-09-03** — build unblocked | Design note landed `ecbbd4b7` (`dev_instructions/R38_edgar_design_note.md`) with a scope-shrinking finding: no new endpoint — the segment data is already in the `companyfacts` payload the existing ingest discards; needs a dimensional parser. Saiful acknowledged the note 2026-09-03; "Build all" dispatched WP10 — and **the escape hatch FIRED (2026-09-03, `c05793c5`)**: the note's premise is false — companyfacts carries **no** per-fact `segment` data (0 of CAT's 39,403 / Deere's 35,550 fact points; proven independently by CR221's census `f7381096` AND by WP10's own finished parser against the live payload). The full build (5 source files, 83 green tests) is **parked, not shipped** — `dev_instructions/WP10_R38_parked/` — because a parser that can never fire is observationally identical to "no captive segment reported", the CR040 silent-fallback shape. The data exists at `FilingSummary.xml` per-filing reports — outside the hatch's boundary. **RULED 2026-09-03 (Saiful): declared-absent entry in CR219 now + re-route under CR221 later.** Done `b7102f43`, accepted (91/91 on dispatcher rerun): persona sentence ("the industrial-vs-captive-finance split of that total is not supplied — never split it yourself") + `_KNOWN_ABSENT` row R38 in the availability guard (the real shipped mechanism — the plan's `SHEET_ABSENTS` module name was never built; the worker detected and reported the substitution) with 4 collision markers transcribed from the parked patch's own `debt_split_line()` renders, red-fixture-proven against both its resolved and unresolved states — so the guard goes red the day CR221 lands the real line. FilingSummary.xml route + `WP10_R38_parked/` head start belong to CR221 | K,A,F,G | ☑ |
| R39 | Sequencing — contradiction fixes before new fields? | CONVERGENT | Yes — guard + persona fixes land before any new field, every reviewer who addressed it agrees. Honored: WP01–WP03 merged 2026-09-02 before the first field (`ab9decb2`, 2026-09-03) | K,F,G,Q | ☑ |
| R40 | Scope — does all data work ride CR219, or split to another CR? | RESOLVED 2026-09-02 | All data work rides CR219 — the R37/R38 exception dissolved when both were ruled in. (R55's outcome ledger remains the one explicit split-out.) Enacted: all fields shipped in-CR; R38's code is the one piece pending its gate | K,A,F,G,Q | ☑ |

## Process & governance

| Ref | Issue | Status | Disposition | Reviewers | Build |
|---|---|---|---|---|---|
| R41 | Undisclosed harness artifact — `convene_gemini.py` hardcodes `LONG_HORIZON` while `--horizon` varies | OPEN (half done) | README caveat DONE (commit `38a9e85f`); REMAINING: extend `aggregate_arms.py`'s artifact filter to the 4 affected `h_short` reports — `dev_instructions/WP09_docs_corrections.md` | F | ☑ |
| R42 | CR210 measurements (50/69, 47/68) exist only in code comments, no results artifact | DONE 2026-09-02 | Committed as `49380813` with a results note (`CR210_.../results/acceptance3_wrong_constraint_regressions.md`); CR210's post-fix arm re-run stays open in that note | F | ☑ |
| R43 | PM breaks its JSON-only contract under instruction pressure | **MINTED 2026-09-03 → [DEF398](../../defect/def_list.md)** | Minted on Saiful's instruction ("mint it and fix it") and the cheap leg fixed in the same commit `886355e4`: `extract_json_object` tries `raw_decode` before DEF352's `rfind` trim, because the trailing section **quotes the JSON-only rule it is breaking** — `begin with '{' and end with '}'` — and that quoted brace is what defeated the trim. Recovers both arms (`h_short`'s lost verdict was an APPROVE → DEF059 PASS). **Deliberately not oversold:** against R47's n=5 corpus this recovers 1 of XOM's 17 lost draws (17%→16% loss); the other 16 never opened an object, the contract-abandonment class only CR210's grammar can reach. DEF398 stays **open** on that leg. R43's own condition — the DEF exists — is met | K,G | ☑ |
| R44 | Sweep the 26 unswept prompts (concierge, Brief Your Agent) | CONVERGENT | Extend `dump_sheets.py`/`assemble_room.py` rather than writing new scripts. Becomes automatic if R13 (exhaustive guard) is adopted | K,F,G,Q | ☑ |
| R45 | A named target architecture — what does "done" look like? | CONVERGENT (independently duplicated) | Canonical section landed in the base CR doc (`9d764194`). Reconciliation found the "near-identical" claim was wrong for the five properties (only "Complete" is shared, with different meanings) — QWEN's naming canonical, one OPEN sub-point recorded in the section: whether GLM's Guarded/Profiled fold in. Surface at a daily review | G,Q | ☑ |
| R46 | Acceptance #5 "evidence/ regenerates" implies byte-identical output | OPEN | Reword to "scripts run clean against a freshly built profile" — the cached profile is gitignored and market data moves | Q | ☑ |

## Beyond CR219 — further Room-result levers

Fable's second-pass list (`05_further_improvements.md`), 15 items, explicitly *"none of
it is built."* Fable's own doc records which of these Saiful decided should ride
CR219's umbrella vs. split off — captured below; this is a narrower and more specific
ruling than "everything rides CR219" (R40) and applies only to this group.

| Ref | Issue | Status | Disposition | Reviewers | Build |
|---|---|---|---|---|---|
| R47 | Raise PM self-consistency default (production, decision variance) | MEASURED 2026-09-03 | **Keep n=5.** Measured at n=5: 8.3% flip (5/60 votes; 0% CAT/MSFT, 25% XOM) — and every flip is an R43 parse-loss tie (a lost draw makes the denominator even, 2-2 ties break to PASS), not PM indecision. Raising n would mask R43 at linear cost. Also corrects the "~19.7%" framing: that was non-unanimity at k=3; the comparable flip figure is 6.6%. `c8ebfa67`, `harness/results/2026-09-03_R47_flip_at_n5.md` | F | ☑ |
| R48 | Thinking mode is verified OFF on the live model | **RULED** | Rides CR219 — also GLM's R5: PM-only, measured, decode budget re-derived first. Done `c8ebfa67`: budget re-derived on the real prompt (toy probe understated reasoning 8×; B arm 1700+1500=3200), A/B on CAT — identical verdicts, parse loss 14%→2% (directional), **5.4× latency**, and a thinking-runaway anomaly on contested MSFT (full 8k ceiling, zero answer — no max_tokens fixes it). **No default change ships.** `harness/results/2026-09-03_R48_thinking_ab.md` | F,G | ☑ |
| R49 | PM overridden by floor checks (cooldown, over-trading) it never sees | RULED (Fable's scoping) | Rides CR219's umbrella per Fable's own categorization. Done `b1ea0901` (floor-state preview from the floor's own helpers; `safety_floor.py` byte-identical) | F | ☑ |
| R50 | Code-generated Room scoreboard (stance/conviction/headline table) | RULED (Fable's scoping) | Rides CR219's umbrella. Done `e9733883` (deterministic, `unparsed` rows loud) | F | ☑ |
| R51 | Partial-outage honesty (count/disclose/cap scripted fallbacks) | RULED (Fable's scoping) | Rides CR219's umbrella. Done `2fd4d688` (count + disclose + config-capped abstain; compose parity). DEF397's dropped-draw mechanism (`room_runner.py:4540`) stays open under DEF397 | F | ☑ |
| R52 | "What would change this call" kill-criterion field on the verdict | RULED (Fable's scoping) | Rides CR219's umbrella. Done `683b5346`+`94672fe8` (schema+prompt+tests one commit; DEF264 non-prose keys + DEF058 reformatter divergence fixed). Follow-up flagged: harness scorer for criterion grounding | F | ☑ |
| R53 | Permanent DATA GAPS telemetry tail on analyst turns | **RE-RULED 2026-09-03 — Build all** | Un-parked, rides CR219 — `dev_instructions/WP14_R53_R57_turn_telemetry.md` (wave 2, queued behind WP13's `room_runner.py` lane) | F | ☐ |
| R54 | Standing replay eval harness across prompt CRs | **RULED 2026-09-02** | Stays inside CR219 — AC4 and several experiments (R31, R48) depend on it. Satisfied by `harness/` (2c75f1c8) | F | ☑ |
| R55 | Verdict-outcome ledger (internal calibration floor) | **RE-RULED 2026-09-03 — Build all** | The "own future CR" half is superseded — rides CR219 via `dev_instructions/WP11_R55_verdict_outcome_ledger.md`. **Accepted-except-hook 2026-09-03** (`0aba79fb`+4: table, migration `cr219a0b0c0d3` proven up/down, scorer, exclusions via `admin_analytics._real_users_clause()`, admin aggregates; 45/45 on dispatcher rerun incl. migration guards). The verified runner hook (site `room_runner.py`, anchor `run.status = RoomStatus.COMPLETED`) lands after WP14's acceptance — box flips then. **Internal-only stands**: no user-facing calibration stats before v1.0. Worker also surfaced a DEF candidate: the CR051 real-users exclusion rule is hand-synced across five sites and already drifted (only the two ORM copies carry the 12 by-id probe exclusions) — mint at daily review | F | ☐ |
| R56 | Mandate-utilization guard — `drawdown_response`/`regret_asymmetry` are also dead fields | RULED (Fable's scoping) | Rides CR219's umbrella; fold into the R25/R26 (`primary_goal`) work while that's open. Done `2f70cc5d` — both wired (debator stress-emphasis line; researcher/debator regret-framing line), neither stopped-printing | F | ☑ |
| R57 | Stance-envelope grammar tension (force emission vs. keep it a measurement channel) | **RE-RULED 2026-09-03 — Build all** (measurement leg) | Un-parked as the measurement leg only: per-turn emission telemetry + per-agent rates + a written revisit rule — `dev_instructions/WP14_R53_R57_turn_telemetry.md`. Grammar-forcing stays gated on that data and on Saiful explicitly amending the two pins (CR210 no-prose-agent-constrained; DEF251 measurement-never-control) | F | ☐ |
| R58 | Debate-order randomization (Bull always speaks before Bear) | **RE-RULED 2026-09-03 — Build all** | Un-parked, rides CR219 — `dev_instructions/WP13_R58_debate_order.md`. **Part A accepted 2026-09-03 (`29eb025d`)**: `room_debate_order_seeded` (default OFF) + iteration-time reorder, CR077 pin untouched, 32/32 on dispatcher rerun. Part B replay (24 contexts × both orders, qwen3.8-flash-next) in flight — memo decides the recommendation; flipping the default is Saiful's | F | ☐ |
| R59 | Audit: every number the user reads is computed or checked in code | **RE-RULED 2026-09-03 — Build all** | Un-parked, two phases: read-only inventory `dev_instructions/WP12_R59_numbers_audit.md` (Opus lane, wave 1) → fixes + provenance guard dispatched after dispatcher review. R20's shipped RO-precompute half stands | F,Q | ☐ |
| R60 | "What changed since your last convene" delta line | **RE-RULED 2026-09-03 — Build all** | Un-parked, rides CR219 — `dev_instructions/WP15_R60_delta_line.md` (wave 3, queued behind WP14). Pairs with R52: prior kill criterion checked first. Backend-only surface now; mobile rendering + i18n flagged follow-up | F | ☐ |
| R61 | News headlines are untrusted input — verify they're framed as quoted data | **RULED 2026-09-02** | **Rides CR219** — folded into the guard. Build: `dev_instructions/WP02_guard.md` | F | ☑ |

---

## Open decisions this register surfaces (roll-up) — ALL RULED 2026-09-02

The six forks were put to Saiful and ruled inline in the Fable session, 2026-09-02.
Provenance and full wording: [`dev_instructions/DECISIONS_2026-09-02.md`](dev_instructions/DECISIONS_2026-09-02.md).

1. **R21** — back with real fetches, inside CR219 (GLM track upheld).
2. **R37 / R38** — build BOTH inside CR219 (defer dissent overruled).
3. **R31** — merged design: QWEN's deterministic scorers at Kimi/GLM's initial scale.
4. **R16** — disambiguate, keep both (Fable withdrew the dissent — the trailing CONVICTION is code-parsed).
5. **R13** — adopted: guard is exhaustive by construction.
6. **R53, R57–R60** — parked to a future CR; **R61 rides CR219** (guard).

The plan is now fully ruled. Per-row build instructions for every item:
[`dev_instructions/`](dev_instructions/) — start at its `README.md` (routing, build
order, house rules, definition of done).
