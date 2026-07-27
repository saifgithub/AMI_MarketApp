# CR098 — Room analyst pull-back path (tenure-drip degradation + PM disclosure + FOMO)

**Filed:** 2026-07-26 · **Source:** Saiful, this session — *"Slowly, we will remove analysts from
the room, but not break the room. PM will continue but will say which analyst opinions are not
included"* + *"we need to create a feeling of FOMO so that we can entice the customer to become a
paying customer"* + *"we need to set when we begin to pull back … after a week, we take some … until
full final pullback after 6 weeks or so"*
**Track:** AT:R59 (protect-the-Room lane — diagnosis + brief; the build team + audit implement)
**Status:** proposed — plan approved by Saiful; not yet built. Full approved design:
`/Users/saiful/.claude/plans/i-am-reasonably-sure-stateless-cray.md`.

---

## Why

Convene-the-Room runs all 12 agents unconditionally, for every plan, and fetches all four analyst
data sources wholesale before anyone speaks (`room_runner.py:1579,1632`). Two goals:

1. **Cut cost** — the Room is decode-bound and the metered feeds (Alpha Vantage for News, Adanos for
   Social) fire on every convene regardless of plan. Withholding a voice *and* its fetch banks real
   GPU + API cost.
2. **Manufacture upgrade FOMO** — a new free user gets the **full** Room (the hook); as the account
   ages without converting, analyst voices are removed on a timed drip; the PM still issues a verdict
   but **names the opinions that were not included**, and the free user sees a locked "empty chair"
   (ideally a countdown). Paying users always get the full Room. The felt gap is the conversion lever.

## Locked product decisions (Saiful)

- **Free-tier floor = Fundamentals + Market.** Only **News + Social** are withholdable (the two
  metered-data voices). Fundamentals + Market are protected — no config value can strip below this
  floor.
- **Time-phased drip keyed to account tenure.** Full Room early; first voice ~week 1; full pull-back
  by ~week 6. Default 2-step schedule: **day 7 → withhold Social; day ~42 → withhold Social + News.**
  Tunable via config; ships empty (no-op).
- **Trial (`trial_trader`) = full Room.** Only `FLOOR_PASS` is ever degraded. The clock is account age
  (`users.created_at`), so a trial that lapses at day 14 lands mid-schedule — correct.
- **Withheld UX = visible locked chair** with a 🔒 upgrade CTA + optional countdown, plus the PM's
  closing disclosure.

## Why it is safe to build (verified by exploration this session)

1. Degradation is graceful *by construction* — `_format_transcript` (`room_prompts.py:478-485`) is a
   dynamic loop; a missing analyst simply isn't in the transcript. No hardcoded "4 analysts" in
   executable logic, no KeyError, no dangling reference.
2. The **safety floor is provably analyst-independent** — `check_mandate_compliance`
   (`safety_floor.py:103-250`) reads only the mandate, the proposed trade, and the sourced screening
   universes. Removing voices cannot weaken compliance.
3. The **Fundamentals *fetch* is decoupled from the Fundamentals *agent*** (`_profile_for_ticker`,
   `room_runner.py:1579`, independent of `PHASES`) — `base_price` → Trader entry/stop/target survives
   regardless of which voices speak.

## Scope — one roster decision, keyed to (plan, account age); five consumers

1. **Roster resolver (new)** — `resolve_analyst_roster(plan, account_age_days, *, now)` in
   `entitlements.py`, returning `present` / `withheld` / `next_step (agent, days_until)`. `FLOOR_PASS`
   applies the schedule; every other plan gets all four. Withholdable domain **hard-capped to
   {news_analyst, social_media_analyst}** — a schedule naming fundamentals/market, an unknown id, or
   descending thresholds **fails boot** (CR040).
2. **Config schedule** — `room_floor_pass_pullback_schedule: str = ""` in `config.py`, encoding
   `"7:social_media_analyst;42:social_media_analyst,news_analyst"`, with a validator; forwarded in
   `docker-compose.yml` api-alpha (CR040 parity test enforces it). Rollout = a config change, not a deploy.
3. **Phase-loop filter + event** — at `room_runner.py:1632`, run only `present` analysts; emit a new
   `RoomEvent(kind="agent_withheld", agent_id, reason="upgrade", next_step)` per withheld analyst for
   the locked chair + countdown.
4. **Fetch gating** — pass the roster into `_profile_for_ticker`; skip withheld analysts' fetches
   (Fundamentals fetch always runs). **Wires the dormant CR090 layer** —
   `resolve_news_feed`/`resolve_social_feed` + `live_data_state(available, entitled)` with
   `entitled = analyst ∈ present` (first production caller).
5. **PM disclosure** — new `opinions_not_included: list[str]` on `Verdict` (`schemas/room.py:28-41`),
   **populated deterministically from `ctx.withheld`** in `_parse_pm_verdict` + the fail-safe/override
   sites (not LLM-derived — CR038). Add the key to `_PM_VERDICT_FORMAT` + `_PM_REFORMAT_SYSTEM` and
   instruct the PM to acknowledge the absent perspectives in narration.
6. **Prompt-copy softening** — `bull_researcher.md:16`, `bear_researcher.md:16`,
   `research_manager.md:18` ("the 4 Analysts" → "the analyst opinions present … (there may be fewer
   than four)"); fix stale prose `room_runner.py:6,1653`.
7. **UI (separate lane, coder.mobile)** — locked chair + countdown from `agent_withheld`; PM
   `opinions_not_included` as a closing disclosure + upgrade CTA.
8. **Docs (this lane)** — update `docs/initial_specs/02_agents/agent_data_blueprint.md` (roster now
   plan-+tenure-dependent); flag to the architect that **DEF098's parity guard must treat a withheld
   analyst as a declared omission for degraded `FLOOR_PASS`, not a defect** (do NOT edit DEF098).

## Rollout (the "slowly")

- **Phase A — mechanism, ships as a no-op** (empty schedule). Byte-identical convene vs today
  (golden-transcript compare). Safe to promote.
- **Phase B — FOMO surface** (locked chair + countdown + PM disclosure CTA). Inert until the schedule
  is set.
- **Phase C — operational rollout.** Set `day 7 → Social`, measure conversion / Room-quality / cost,
  then add `day ~42 → +News`. Each step is a config change; revert anytime.

**Out of scope (flag):** convene price stays flat per plan. CR090's designed-but-unwired
`live_data_surcharge(n_live_analysts)` (`credit_service.py:93-101`) is related, not touched here.

## Acceptance

1. `pytest tests/unit/ -q` green.
2. **No-op proof:** empty schedule → convene transcript + verdict byte-identical to today.
3. Resolver (clock injected): `FLOOR_PASS` day 3 → all four; day 10 w/ `7:social` → withheld {social};
   day 50 w/ 2-step → withheld {social,news}; paid/trial any age → all four; bad schedule → boot fails.
4. `next_step`: day-3 `FLOOR_PASS` w/ `7:social` → `(social, 4 days)`.
5. Fetch gating: withholding Social skips `fetch_live_sentiment` (Adanos not called) + drops social
   fact-sheet lines; Fundamentals fetch still runs, `base_price` live.
6. **Safety-floor regression:** identical REJECT for a violating trade with full roster vs News+Social
   withheld.
7. `Verdict.opinions_not_included` deterministic even when the LLM omits it; in `model_dump` + event.
8. CR040 parity passes with the new field forwarded.
9. Live smoke: aged `FLOOR_PASS` convene w/ Social withheld → social voice absent, Adanos not hit,
   `agent_withheld` emitted, verdict lists Social.

## Governance

- Commit tag `(AT:R59 CR098)`. **Risky + touches the safety-adjacent PM path → independent audit**
  (track R architect + track U auditor) per `orchestration/audit/PROTOCOL.md`.
- Relates to **CR090** (wires its dormant entitlement layer), **CR040** (degrade loudly + compose
  parity), **CR038** (deterministic disclosure), **DEF098** (parity guard: withheld-for-plan is
  declared), the **agent_data_blueprint**, and the **earn-path unlock** (`one_on_one.py:67-81`, the
  separate paywall).
