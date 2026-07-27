<!-- intake handoff from the Room-quality lane (AT:R59). CR098 filed + registered; needs laning + audit. -->
# room-quality — CR098 filed, ready to lane (build + independent audit)

PROPOSED-KIND: CR (already minted CR098 — register regenerated; re-verify no collision at pickup)
SOURCE: Saiful (plan approved 2026-07-26; **amended by him 2026-07-27**) — Room analyst pull-back / FOMO
TRIAGE: READY-TO-LANE

**Brief:** `docs/forward_planning/CR098_room_analyst_pullback/CR098_room_analyst_pullback.md`
**Approved design (full):** `/Users/saiful/.claude/plans/i-am-reasonably-sure-stateless-cray.md`

**What it is:** progressively withhold analyst voices from the free tier on a per-user tenure schedule
(full Room early → pulled back to a Fundamentals-only floor by ~6 weeks). The PM names the absent
voices; the free user sees a locked chair + countdown. Wires the dormant CR090 entitlement layer to
also bank the data-fetch cost.

## ⚠️ Amended 2026-07-27 — re-read the brief if you saw the 2026-07-26 version

Four changes, all from Saiful directly:

1. **Market is now withholdable; the floor drops to Fundamentals only.** Withholdable set =
   {Social, News, Market}. Verified safe: technicals (`rsi`/`trend`/`support`/`breakout`/`volume_tone`)
   are consumed **only** by the fact sheet (`room_prompts.py:413,419,421`) — no Trader level, PM field
   or safety-floor input reads them. Fundamentals stays unwithholdable **in code** (no knob exists).
2. **Thresholds move to `.env`** — three ints, `ROOM_PULLBACK_DAYS_SOCIAL` / `_NEWS` / `_MARKET`,
   `0` = never withheld, `N ≥ 1` = withheld once `account_age_days >= N`. Independent, not ordered
   steps. Negative → boot fails (CR040). Replaces the earlier encoded-schedule-string design.
3. **Amendment 1 — gating the fetch is NOT enough.** `_profile_for_ticker` builds a complete
   **synthetic rng baseline first** (`room_runner.py:311-354`) and overlays live data on top
   (`:357-388`), and `_format_profile` renders **one shared fact sheet into all 12 prompts**. Skip
   `compute_technicals` alone and every agent still reads `rsi=rng.randint(35,75)`,
   `support=base×0.9`, `breakout=base×1.03` — fabricated numbers in the live slot. That is no FOMO, no
   decode saving, and a **DEF059-class silent-synthetic violation of CR040**. Withholding must do
   three things: skip the fetch, **strip the fact-sheet lines**, skip the turn. Per-domain line
   ownership is tabulated in the brief.
4. **Amendment 2 — Market withheld is terminal for the verdict.** New `VerdictAction.NO_VERDICT`; the
   `Verdict` is **built in code with null levels, bypassing `_parse_pm_verdict`**, so no LLM output can
   produce a tradeable call without price data. The floor already short-circuits on non-APPROVE
   (`safety_floor.py:401`) — **verify, don't assume**. The PM still speaks on a narrow
   no-recommendation prompt, backed by a **deterministic contradiction guard** that discards narration
   which still recommends a trade (CR038). Confirm no journal entry / simulated position can open from
   a NO_VERDICT run (`room_runner.py:1085-1086`).

**Voice rule (new, applies to the whole CR):** **no agent prompt or agent-authored string may mention
plans, upgrades or pricing.** The PM declines because calling a trade without a market read is bad
practice — not because the user hasn't paid. Fixed copy is in the brief; the CTA is app chrome only.
Saiful: *"it would be reckless to render judgement without market. think of a way to deliver this
message diplomatically."*

## Suggested lanes

- `coder.api` — components 1–7 (roster resolver in `entitlements.py`; three `.env` ints + compose
  parity; phase-loop filter + `agent_withheld` event; fetch-gating via the CR090 resolvers;
  **fact-sheet stripping**; deterministic `opinions_not_included`; **the NO_VERDICT path + contradiction
  guard**; prompt-copy softening).
- `coder.mobile` — component 8 (locked chair + countdown + PM disclosure CTA + the NO_VERDICT screen).
- Room-quality (me) — component 9 doc update (`agent_data_blueprint.md`).

## Why it needs independent audit (track R + track U)

It edits the **safety-adjacent PM verdict path** (`_parse_pm_verdict`, `Verdict` schema + enum,
`_PM_VERDICT_FORMAT` / `_PM_REFORMAT_SYSTEM`) and the convene roster. The safety floor is provably
analyst-independent (`safety_floor.py:103-250`) — the audit's job is to confirm that invariant survives,
**and** that a NO_VERDICT run cannot open a position or be mistaken for an approval anywhere downstream.

## Ship discipline

Phase A must be a **proven no-op** with all three thresholds `0` (golden-transcript compare) before any
voice is withheld. Rollout is an `.env` change + restart, not a deploy.

## Coordination — DEF098 (architect-owned, do NOT let this CR edit it)

Once CR098 lands, DEF098's prompt-data parity guard must treat a withheld analyst as a **declared**
omission for degraded `FLOOR_PASS` (keyed on the roster resolver), not a dropped-field defect. Flagging
so the guard and the pull-back don't fight.
