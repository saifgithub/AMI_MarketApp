# CR275 — The Room decides blind

**What:** Remove the Street's view (analyst rating, price targets, rating split, per-firm action tape) from every input the Room's agents and judge receive. Keep the data on the run's profile so post-verdict code can use it (CR267 WP-21b, which re-scopes CR260 to a post-verdict display).

**Why:** CR267 WP-21a. The Beta programme scores the Room against analyst consensus (§3a, decision 6). A Room that was shown the consensus cannot be scored against it, and the CR035 ablation already measured that the consensus is a live influence on the verdict.

**Scope:** CR267 WP-21a only. Not in scope: the judge/grader/Jev logic, model, temperature, gateway (all gated, S12); WP-21b's display; the 1-on-1 chat surface.

## Findings (step 1)

The fact sheet DID carry them, by default. CR260 had just made it carry more.

1. `backend/app/services/fundamentals.py:1319-1343` — `fetch_live_fundamentals` writes `analyst_target_price`, `analyst_rating`, `analyst_opinion_count`, `analyst_target_high/low/median`, `analyst_rating_score` (yfinance `targetMeanPrice`, `recommendationKey`, `numberOfAnalystOpinions`, `target{High,Low,Median}Price`, `recommendationMean`). Gated only by `suppress_analyst_consensus` (CR035, `backend/app/core/config.py:592`), default `False`, an ablation toggle.
2. `backend/app/services/analyst_targets.py` + `room_runner.py:2014` / `_overlay_analyst_targets` (~4218) — CR260's `analyst_rating_split`, `analyst_rating_split_history` (SB/B/H/S/SS counts) and `analyst_tape` (per-firm upgrades, downgrades, price-target changes). Live runs only.
3. Render sites, all inside `room_prompts._format_profile`, the one renderer behind `build_room_messages` (all 12 display agents including the CIO/PM) and `build_risk_officer_messages`: `_analyst_line` (`room_prompts.py:3567`, label "Analyst consensus"), `_analyst_split_line` (3568), `_analyst_tape_line` (3512), the header lines "Analyst rating split: LIVE" (2796) and "Recent analyst actions: LIVE" (2866), and `_asymmetry_line` (4191, "upside to the consensus target").
4. `room_runner._build_next_convene_delta` (~7097) — the PM prompt renders `field: from_state -> to_state` transitions (`room_prompts.py:4582`); an `analyst_*` field flipping state told the PM the Street's view existed.
5. Persona text that presumes the data is on the sheet: `content/agents/fundamentals_analyst.md:167-170` (a bullet listing "Analyst consensus — the rating … target as mean / median / low–high range"), `content/agents/bull_researcher.md:52-54` and `:61-63` (the "consensus target carries no stated horizon" instruction).
6. Checked, not stripped (see Open points): news headlines (`news_context.py`, Yahoo / Alpha Vantage) can carry rating text in a headline; consensus EPS estimates (forward P/E basis, next-earnings EPS estimate, EPS revisions); 1-on-1 chat (`fundamentals.build_live_data_block` uses `analyst_consensus_line`).

## Change

1. New `backend/app/services/street_view_blind.py`: `blind_profile(profile)` returns a shallow copy without any `analyst_`-prefixed key, in the values and in `field_state`. Prefix match, so a Street field added later is withheld by default.
2. `room_prompts._format_profile` calls it first. Every prompt-side reader of the profile goes through that function, so desks, CIO/PM, Risk Officer and any future judge built on it are blind. The original profile is never mutated: `room_runner._analyst_view_from_profile` and the verdict's `analyst_view` (CR260) still work, and the CIO-retry snapshot is unaffected.
3. `room_runner._build_next_convene_delta` drops `analyst_*` transitions from `changed_fields`.
4. Persona text: removed the Fundamentals bullet that listed the consensus as a sheet item, and the two Bull sentences that refer to the consensus target. Nothing else reworded.
5. The CR260 renderers (`_analyst_line`, `_analyst_split_line`, `_analyst_tape_line`, the target branch of `_asymmetry_line`) are now unreachable from the Room. Left in place to keep the diff small; WP-21b may delete them.

## Acceptance

`backend/tests/unit/test_cr275_room_decides_blind.py`: builds real prompts for all 12 display agents (`build_room_messages`) and the Risk Officer (`build_risk_officer_messages`) from a fixture sheet that carries every Street field, and fails if any Street label or value appears. Also pins: fail-closed on a new `analyst_` field, the data survives for post-verdict code, the PM transition list stays blind. Verified red with only the `blind_profile` call and the delta filter reverted (23 failed, 8 passed); green with them.

## Open points

1. Headline text. A Yahoo headline such as "X upgrades Y to Buy, raises target" reaches the News Analyst. Filtering headlines is content removal with real news value; not done. WP-20's baseline can count how often it happens before deciding.
2. Consensus EPS estimates (forward P/E, next-earnings EPS estimate, revision direction) are a Street input but not a rating or target. Left in.
3. The 1-on-1 chat still shows the consensus line. It is not the Room.
