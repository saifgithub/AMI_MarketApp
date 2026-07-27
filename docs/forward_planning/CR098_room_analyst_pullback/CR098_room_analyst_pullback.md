# CR098 — Room analyst pull-back path (tenure-drip degradation + PM disclosure + FOMO)

**Filed:** 2026-07-26 · **Amended:** 2026-07-27 — Market added to the withholdable set; thresholds moved
to `.env`; fact-sheet stripping (*Amendment 1*); Market withheld ⇒ PM renders **NO VERDICT**, framed as
professional discipline rather than a paywall (*Amendment 2*)
**Source:** Saiful — *"Slowly, we will remove analysts from the room, but not break the room. PM will
continue but will say which analyst opinions are not included"* + *"we need to create a feeling of FOMO
so that we can entice the customer to become a paying customer"* + *"we need to set when we begin to
pull back … after a week, we take some … until full final pullback after 6 weeks or so"* + (2026-07-27)
*"we need to pull the market as well. we will need to have the number of days for the pull back based
on the .env"* + *"when we pull the market, PM will render No verdict, saying that while the fundamentals
have been analyzed, no conclusion can be made without the market"* + *"it would be reckless to render
judgement without market. think of a way to deliver this message diplomatically"*
**Track:** AT:R59 (protect-the-Room lane — diagnosis + brief; the build team + audit implement)
**Status:** proposed — plan approved by Saiful; not yet built. Full approved design:
`/Users/saiful/.claude/plans/i-am-reasonably-sure-stateless-cray.md`.

---

## Why

Convene-the-Room runs all 12 agents unconditionally, for every plan, and fetches all analyst data
sources wholesale before anyone speaks (`room_runner.py:1579,1632`). Two goals:

1. **Cut cost** — the Room is decode-bound and the metered feeds (Alpha Vantage for News, Adanos for
   Social) plus the yfinance OHLCV pull for technicals fire on every convene regardless of plan.
   Withholding a voice *and* its fetch *and* its fact-sheet lines banks GPU + API + decode cost.
2. **Manufacture upgrade FOMO** — a new free user gets the **full** Room (the hook); as the account
   ages without converting, analyst voices are removed on a timed drip; the PM still issues a verdict
   but **names the opinions that were not included**, and the free user sees a locked "empty chair"
   (with a countdown). Paying users always get the full Room. The felt gap is the conversion lever.

## Locked product decisions (Saiful)

- **Free-tier floor = Fundamentals only.** *(Amended 2026-07-27 — was Fundamentals + Market.)* The
  withholdable set is **Social + News + Market** — three voices. Fundamentals is protected in **code**,
  not config: there is no knob that can withhold it, so no `.env` value can empty the Room.
- **Thresholds live in `.env`** *(Amended 2026-07-27)* — one integer per withholdable analyst, the
  account-age day at which that voice goes dark. Not a compact encoded schedule string; three plain
  ints an operator can read and change.
- **Time-phased drip keyed to account tenure.** Full Room early; first voice ~week 1; full pull-back by
  ~week 6. Suggested operational values: **Social day 7 · News day 21 · Market day 42.** Ships with all
  three unset (`0` = never) → no-op.
- **Trial (`trial_trader`) = full Room.** Only `FLOOR_PASS` is ever degraded. The clock is account age
  (`users.created_at`), so a trial that lapses at day 14 lands mid-schedule — correct.
- **Withheld UX = visible locked chair** with a 🔒 upgrade CTA + countdown, plus the PM's closing
  disclosure.
- **The other 8 agents are never removed.** Bull, Bear, Research Manager, Trader, the 3 Risk debators
  and the PM always run. At full pull-back a free user still gets **9 of 12 agents** and a real verdict.

## Why it is safe to build (verified by exploration)

1. Degradation is graceful *by construction* — `_format_transcript` (`room_prompts.py:478-485`) is a
   dynamic loop; a missing analyst simply isn't in the transcript. No hardcoded "4 analysts" in
   executable logic, no KeyError, no dangling reference.
2. The **safety floor is provably analyst-independent** — `check_mandate_compliance`
   (`safety_floor.py:103-250`) reads only the mandate, the proposed trade, and the sourced screening
   universes. Removing voices cannot weaken compliance.
3. The **Fundamentals *fetch* is decoupled from the Fundamentals *agent*** (`_profile_for_ticker`,
   `room_runner.py:1579`, independent of `PHASES`) — `base_price` → Trader entry/stop/target survives
   regardless of which voices speak.
4. **Technicals are prompt-only** *(verified 2026-07-27)* — `rsi`/`rsi_tone`/`trend`/`volume_tone`/
   `support`/`breakout` are consumed **exclusively** by the fact sheet (`room_prompts.py:413,419,421`).
   No Trader level, PM verdict field or safety-floor input reads them. Market is therefore safely
   withholdable.

---

## Amendment 1 (2026-07-27) — skipping a fetch does NOT remove the data

**The finding.** `_profile_for_ticker` builds a **complete synthetic rng baseline first**
(`room_runner.py:311-354`) and overlays live data onto it (`:357-388`). Every field — `rsi`, `support`,
`breakout`, `volume_tone`, `trend`, `sentiment_tone`, `sentiment_score`, `catalyst` — has a synthetic
value *before* any fetch runs. And `_format_profile` (`room_prompts.py:~355-437`) renders one **shared**
fact sheet into **every** agent's prompt, not a per-analyst block.

**Consequence if we only gate the fetch:** a Market-withheld free user still sees
`RSI: 58 (neither overbought nor oversold), trend: consolidating` and `Recent range: $x–$y` in every
agent's prompt — fabricated numbers from `rng`, presented in the same slot as live ones. That is:
- **no FOMO** — the data is still on screen,
- **no decode saving** — every downstream prompt is the same length,
- **a CR040 "degrade loudly" violation** — silent synthetic substitution is exactly the failure class
  DEF059 taught us, and CR038 says a prompt disclaimer will not hold.

**Therefore withholding an analyst must do three things, not two:**
1. skip its **fetch** (bank the API cost),
2. **strip its fact-sheet lines** from the shared profile block (bank the decode cost, create the gap),
3. skip its **turn** in the phase loop (bank the generation).

Line ownership in `_format_profile` for step 2:

| Domain | Fact-sheet lines | On withhold |
|---|---|---|
| Fundamentals | `:409-411` (reference price, P/E, growth/margin), `_net_position_line`, `_valuation_line`, `_sector_line`, `_capital_allocation_line`, `_analyst_line`, `next_earnings_*` `:430-436` | **always present** |
| Market | `:413` (RSI/tone/trend), `:419-420` (recent range / 52-week), `:421` (volume) + the technicals provenance header line | removed |
| News | `_catalyst_line` `:422` (the `catalyst` headline overlay) | removed; `forward_catalyst` (real FOMC date) stays |
| Social | `:423` (retail sentiment tone/score), `_social_detail_lines` `:425` + the social provenance header line | removed |

Each removed block is replaced by **one declared line** naming the withholding, e.g.
`Market technicals: withheld on this plan (upgrade to include the Market Analyst).` — declared absence,
never a synthetic stand-in.

---

## Amendment 2 (2026-07-27) — Market withheld ⇒ the PM renders **NO VERDICT**

Saiful: *"when we pull the market, PM will render No verdict, saying that while the fundamentals have
been analyzed, no conclusion can be made without the market."*

Market is not just another chair — losing it is **terminal for the verdict**. At the final drip step the
free Room still convenes, still debates, and then stops short of a recommendation. This is the sharpest
FOMO lever in the CR: the user watches the full analysis and hits a wall at the moment of decision.

**It must be structural, not prompted.** CR038: emphatic prompt instructions are ignored ~70% of the
time. So:

- **New enum member `VerdictAction.NO_VERDICT`** (`schemas/room.py:12-17`). The enum already carries
  APPROVE / REJECT / MODIFY / PASS, and `api/room.py:129` already emits a `"no_verdict"` string when
  `run.verdict` is None — the concept exists; this makes it a first-class verdict rather than an absence.
- **The Verdict object is constructed in code, not parsed from the LLM**, whenever
  `market_analyst ∈ withheld`: `action=NO_VERDICT`, `size_pct/entry/target/stop/horizon = None`,
  fixed `reason` copy, `opinions_not_included` from the roster. `_parse_pm_verdict`
  (`room_runner.py:621-680`) is bypassed for this path. No LLM output can produce a tradeable verdict
  when the market data is not there.
- **Safety floor is already correct** — `enforce_safety_floor` short-circuits on
  `llm_verdict.action != VerdictAction.APPROVE` (`safety_floor.py:401`), so NO_VERDICT passes through
  untouched with nothing to enforce. **Verify, don't assume**: acceptance #12.
- **Narration contradiction guard.** The PM still speaks (the closing beat is the product), but on a
  narrow prompt — *explain what could not be concluded and why; state no recommendation.* Because that
  instruction will fail some of the time, add a **deterministic post-check**: if the narration parses to
  an actionable recommendation, discard it and render fixed copy. Reuse the existing reparse machinery
  (`room_runner.py:1809`, `_PM_REFORMAT_SYSTEM:2064-2086`). The app must never show NO_VERDICT beside
  prose that recommends a trade.
- **Journal / portfolio:** a NO_VERDICT run is not a tradeable decision. `room_runner.py:1085-1086`
  builds the journal title/summary from `verdict.action` — confirm the entry reads as an inconclusive
  session and no simulated position can be opened from it.

### The message must read as professional discipline, not as a paywall

Saiful: *"it would be reckless to render judgement without market. think of a way to deliver this
message diplomatically."*

The framing rule: **the PM declines because calling a trade without price data is bad practice — not
because the user hasn't paid.** That is both true and the stronger lever. A desk that refuses to guess
with your capital is a desk worth paying for; a desk that hides the answer behind a paywall is a
toll booth. The refusal must sound like the former.

Three structural rules that make it land:

1. **The PM never sells.** No upgrade language, no plan names, no pricing in any agent's voice. The PM
   states the professional position and stops. The CTA is **app chrome** rendered beside the verdict,
   never words in the PM's mouth. This also keeps marketing copy out of the prompt context entirely
   (CR038 leakage risk).
2. **Credit the work that was done.** The fundamentals case was argued in full by real agents — say so
   first. The user got value; they hit a limit, not a wall of nothing.
3. **Name the missing input factually, not as a lack.** "This session ran without a market read" —
   a stated condition of the analysis, the way a real analyst would caveat a note.

**Fixed PM copy (deterministic, ticker slot only):**

> **No verdict — and that is deliberate.**
> The fundamentals case for {TICKER} was argued in full, and it stands on its own.
> But entry, stop and target are price decisions, and this session ran without a market read. Issuing a
> position on that basis would be a guess presented as a call, and I won't put that on your book.
> The analysis holds. The trade doesn't — not until someone reads the tape.

App chrome beneath it (not the PM's voice): **"Include the Market Analyst →"**

**Fact-sheet declared line (also neutral, no sell):** `Market technicals: not included in this session.`
Same pattern for News and Social. Agents describe the shape of the session; they never mention plans.

**Open operator question (flagged, not decided):** at the NO_VERDICT step, EXECUTION (Trader) and RISK
(3 debators) still run and cost ~25s of decode to produce nothing actionable. Recommendation: **keep
them** — the debate is the product and the education, and the wall lands harder after a full session
than after a truncated one. Skipping them is a legitimate cost option if the measured saving justifies
it; it belongs to Phase C tuning, not to the mechanism.

---

## Scope — one roster decision, keyed to (plan, account age); six consumers

1. **Roster resolver (new)** — `resolve_analyst_roster(plan, account_age_days, *, now)` in
   `entitlements.py`, returning `present` / `withheld` / `next_step (agent, days_until)`. `FLOOR_PASS`
   applies the thresholds; every other plan gets all four. Withholdable domain **hard-capped in code to
   {news_analyst, social_media_analyst, market_analyst}** — `fundamentals_analyst` has no threshold
   setting at all, so it is structurally unwithholdable.
2. **Config — three `.env` integers** *(amended)* in `config.py`:
   `room_pullback_days_social`, `room_pullback_days_news`, `room_pullback_days_market`
   (env `ROOM_PULLBACK_DAYS_SOCIAL` / `_NEWS` / `_MARKET`), each `int = 0`.
   **Semantics: `0` (or unset) = never withheld; `N ≥ 1` = withheld once `account_age_days >= N`.**
   Thresholds are **independent**, not ordered steps — any combination is legal, so cadence is a pure
   operator decision. A negative value **fails boot** (CR040). All three forwarded in
   `docker-compose.yml` api-alpha or `test_config_compose_parity.py:71-92` fails the build.
   Rollout = an `.env` change + container restart, not a deploy.
3. **Phase-loop filter + event** — at `room_runner.py:1632`, run only `present` analysts; emit a new
   `RoomEvent(kind="agent_withheld", agent_id, reason="upgrade", next_step)` per withheld analyst for
   the locked chair + countdown.
4. **Fetch gating** — pass the roster into `_profile_for_ticker`; skip withheld analysts' fetches
   (`fetch_live_news`, `fetch_live_sentiment`, `compute_technicals`). Fundamentals fetch always runs.
   **Wires the dormant CR090 layer** — `resolve_news_feed`/`resolve_social_feed` +
   `live_data_state(available, entitled)` with `entitled = analyst ∈ present` (first production caller).
5. **Fact-sheet stripping** *(new — Amendment 1)* — pass the roster into `_format_profile`; omit the
   withheld domains' lines and emit one declared-withheld line each. **No synthetic stand-in ever
   renders for a withheld domain.**
6. **PM disclosure** — new `opinions_not_included: list[str]` on `Verdict` (`schemas/room.py:28-41`),
   **populated deterministically from `ctx.withheld`** in `_parse_pm_verdict` + the fail-safe/override
   sites (not LLM-derived — CR038). Add the key to `_PM_VERDICT_FORMAT` + `_PM_REFORMAT_SYSTEM` and
   instruct the PM to acknowledge the absent perspectives in narration.
6b. **NO_VERDICT path (Amendment 2)** — add `VerdictAction.NO_VERDICT`; when
   `market_analyst ∈ withheld`, build the `Verdict` in code (bypassing `_parse_pm_verdict`) with null
   levels + the fixed copy; run the PM on the narrow no-recommendation prompt with the deterministic
   contradiction post-check; ensure no journal entry or simulated position can be opened from it.
   **No agent prompt or agent-voiced string may mention plans, upgrades or pricing** — the CTA is app
   chrome only.
7. **Prompt-copy softening** — `bull_researcher.md:16`, `bear_researcher.md:16`,
   `research_manager.md:18` ("the 4 Analysts" → "the analyst opinions present … (there may be fewer
   than four)"); fix stale prose `room_runner.py:6,1653`.
8. **UI (separate lane, coder.mobile)** — locked chair + countdown from `agent_withheld`; PM
   `opinions_not_included` as a closing disclosure + upgrade CTA.
9. **Docs (this lane)** — update `docs/initial_specs/02_agents/agent_data_blueprint.md` (roster now
   plan-+tenure-dependent; floor = Fundamentals); flag to the architect that **DEF098's parity guard
   must treat a withheld analyst as a declared omission for degraded `FLOOR_PASS`, not a defect** (do
   NOT edit DEF098).

## Rollout (the "slowly")

- **Phase A — mechanism, ships as a no-op** (all three thresholds `0`). Byte-identical convene vs today
  (golden-transcript compare). Safe to promote.
- **Phase B — FOMO surface** (locked chair + countdown + PM disclosure CTA). Inert until a threshold is set.
- **Phase C — operational rollout.** `ROOM_PULLBACK_DAYS_SOCIAL=7` first; measure conversion /
  Room-quality / cost; then `_NEWS=21`; then `_MARKET=42`. Each step is an `.env` change; revert anytime.

**Out of scope (flag):** convene price stays flat per plan. CR090's designed-but-unwired
`live_data_surcharge(n_live_analysts)` (`credit_service.py:93-101`) is related, not touched here.

## Acceptance

1. `pytest tests/unit/ -q` green.
2. **No-op proof:** all thresholds `0` → convene transcript + verdict byte-identical to today.
3. Resolver (clock injected), with `SOCIAL=7, NEWS=21, MARKET=42`: `FLOOR_PASS` day 3 → all four
   present; day 10 → withheld {social}; day 30 → withheld {social, news}; day 50 → withheld
   {social, news, market}, present {fundamentals}; paid/`trial_trader` any age → all four; a negative
   threshold → **boot fails**.
4. `next_step`: day-3 `FLOOR_PASS` with `SOCIAL=7` → `(social, 4 days)`.
5. Fetch gating: withholding Social skips `fetch_live_sentiment` (Adanos not called); withholding News
   skips `fetch_live_news`; withholding Market skips `compute_technicals`. Fundamentals fetch still
   runs, `base_price` live, Trader levels intact.
6. **Fact-sheet stripping (Amendment 1):** with Market withheld, the rendered profile block contains
   **no** `RSI:`, `Recent range:` or `Volume:` line and **no** synthetic substitute — one declared
   withheld line instead. Assert on the exact prompt string, not on the fetch call count. Same for
   News (`catalyst`) and Social (`Retail sentiment` + `_social_detail_lines`).
7. **Safety-floor regression:** identical REJECT for a violating trade with the full roster vs. the
   Fundamentals-only floor.
8. `Verdict.opinions_not_included` deterministic even when the LLM omits it; in `model_dump` + event.
9. CR040 parity passes with all three new fields forwarded.
10. **NO_VERDICT (Amendment 2):** Market withheld → `Verdict.action == NO_VERDICT`, all of
    `size_pct/entry/target/stop/time_horizon_days` are `None`, `reason` is the fixed copy, and this
    holds **even when the LLM emits a well-formed APPROVE block** (force-fed fixture — proves the
    code path, not the prompt, decides).
11. **Contradiction guard:** LLM narration containing an actionable recommendation is discarded and
    replaced by fixed copy; the rendered output never pairs NO_VERDICT with trade-recommending prose.
12. **Safety-floor regression:** identical REJECT for a violating trade with the full roster vs. the
    Fundamentals-only floor; and a NO_VERDICT run passes through `enforce_safety_floor`
    (`safety_floor.py:401`) unchanged, opening no position and writing no tradeable journal entry.
13. **No sell in an agent's voice:** assert no rendered agent prompt or agent-authored string contains
    plan names, "upgrade", or pricing.
14. Live smoke: aged `FLOOR_PASS` convene with Social+Market withheld → both voices absent, Adanos not
    hit, no OHLCV pull, `agent_withheld` emitted twice, verdict is NO_VERDICT and lists both.

## Governance

- Commit tag `(AT:R59 CR098)`. **Risky + touches the safety-adjacent PM path → independent audit**
  (track R architect + track U auditor) per `orchestration/audit/PROTOCOL.md`.
- Relates to **CR090** (wires its dormant entitlement layer), **CR040** (degrade loudly + compose
  parity), **CR038** (deterministic disclosure), **DEF059** (silent synthetic fallback — the failure
  class Amendment 1 prevents), **DEF098** (parity guard: withheld-for-plan is declared), the
  **agent_data_blueprint**, and the **earn-path unlock** (`one_on_one.py:67-81`, the separate paywall).
