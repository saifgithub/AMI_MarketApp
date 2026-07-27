<!-- intake handoff from the Room-quality lane (AT:R59). CR098 filed + registered; needs laning + audit. -->
# room-quality — CR098 filed, ready to lane (build + independent audit)

PROPOSED-KIND: CR (already minted CR098 — register regenerated; re-verify no collision at pickup)
SOURCE: Saiful (plan approved this session) — Room analyst pull-back / FOMO
TRIAGE: READY-TO-LANE

**Brief:** `docs/forward_planning/CR098_room_analyst_pullback/CR098_room_analyst_pullback.md`
**Approved design (full):** `/Users/saiful/.claude/plans/i-am-reasonably-sure-stateless-cray.md`

**What it is:** progressively withhold News/Social analyst voices from the free tier on a per-user
tenure schedule (full Room early → full pull-back to a Fundamentals+Market floor by ~6 weeks). PM
still issues a verdict and names the absent voices; free user sees a locked chair + countdown. Wires
the dormant CR090 entitlement layer to also bank the data-fetch cost.

**Suggested lanes:**
- `coder.api` — components 1–6 (roster resolver in `entitlements.py`, config schedule + compose
  parity, phase-loop filter + `agent_withheld` event, fetch-gating via CR090 resolvers, deterministic
  `opinions_not_included` on `Verdict`, prompt-copy softening).
- `coder.mobile` — component 7 (locked chair + countdown + PM disclosure CTA).
- Room-quality (me) — component 8 doc update (`agent_data_blueprint.md`).

**Why it needs independent audit (track R + track U):** it edits the **safety-adjacent PM verdict
path** (`_parse_pm_verdict`, `Verdict` schema, `_PM_VERDICT_FORMAT`/`_PM_REFORMAT_SYSTEM`) and the
convene roster. The safety floor is provably analyst-independent (`safety_floor.py:103-250`) — the
audit's job is to confirm that invariant survives the change (regression test #6 in the brief).

**Ship discipline:** Phase A must be a **proven no-op** with the schedule empty (golden-transcript
compare) before any voice is withheld. Rollout is a config change, not a deploy.

**Coordination — DEF098 (architect-owned, do NOT let this CR edit it):** once CR098 lands, DEF098's
prompt-data parity guard must treat a withheld analyst as a **declared** omission for degraded
`FLOOR_PASS` (keyed on the roster resolver), not a dropped-field defect. Flagging so the guard and the
pull-back don't fight.
