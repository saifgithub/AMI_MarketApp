# M7 investigation — the "missing debator turns" (2026-10-14)

**Verdict: the turns were never missing — the Jev scorer never fetched them.**
Root cause is two filters in `jev_score_runs.py`, compounded by a design change
in how the Room runs its risk stage.

## Root cause (two layers)

1. **CR201 consolidated the risk stage.** On Alpha, `ROOM_RISK_OFFICER_ENABLED=true`
   (melehost `.env`). The three prose debator turns (aggressive/conservative/neutral)
   are replaced by ONE structured call: `agent_id=risk_officer`,
   `flow=room_risk_officer`, a size-ladder JSON (`case_for`/`case_against`/`key_number`
   per rung + `recommended`/`confidence`/`decisive_number`). The three debator voices
   are *rendered from* that payload into the transcript; no further LLM calls exist
   to audit. Verified in `llm_audit` (7-day window): 2,099 `risk_officer` rows,
   411/410/408 legacy debator rows from before the flag.
2. **The scorer filtered both dimensions out.** `fetch_arm_turns` queried
   `flow = 'room'` only, and `PROSE_AGENTS` did not include `risk_officer` — so the
   single risk-stage call failed BOTH filters. PM turns (`room_pm`) are excluded by
   the same flow filter (flagged for CR257; not M7 scope).

## Fix (committed with this memo)

`tools/jev_score_runs.py`:
- `flow IN ('room', 'room_risk_officer')`; `risk_officer` added to `PROSE_AGENTS`.
- `flow` recorded per scored row (downstream tools can distinguish officer turns).
- New `--agents` flag (comma list) for targeted re-scores — born from an incident:
  the first re-score pass ran unfiltered (540 turns/level instead of 60) and burned
  ~2,700 Jev calls, draining the account (HTTP 402) mid-pass. **Lesson recorded:
  targeted passes must use `--agents`.**

## Verification state

- `cr251-v2-dsv4` (prod): **300/300 officer turns scored clean** into
  `out/cr251-v2-dsv4/jev_officer/r{1..5}.jsonl` (60/level, exactly one per room —
  confirms the consolidation). `core_claim_supported` answers: 144 well / 153
  partially / 3 unsupported.
- Jev question fit: `core_claim_supported` maps onto the ladder's case sentences and
  answers meaningfully. `figures_consistent` / `conviction_justified` /
  `envelope_matches_prose` return None — they are prose-stance rubric and the officer
  output is structured JSON with no STANCE envelope.
- **COMPLETE (2026-10-14, fund topped up):** all four arms' officer turns
  re-scored clean with `--agents risk_officer` — cr251-v2-dsv4 (300),
  cr253-disp-matrix (300), cr254-tmall-matrix (300), cr251-v2-ami-fix +
  original-dir r1/r4 (300). Zero errors. `jev_officer/` holds 60 turns per
  level per arm, exactly one per room.

## CR256 consequence

- M7 as written ("debator turns absent from llm_audit") is **resolved**: the risk
  stage is present and auditable as one turn per room.
- The objection-audit question set for CR256 Layer-1 OBJECTIONS does NOT exist yet:
  the V1 four questions only partially map onto structured officer output, and the
  officer ladder has no objections field at all (it is a sizing ladder). This is a
  **CR257 coordination item** (question-set freeze): the card pilot needs new Jev
  questions (card support / key_number-in-payload / objection-severity) agreed there
  before the pilot runs.
- `evidence_bar.py` Step-0 proxies are unaffected (officer turns are not in the
  BULL/BEAR desk sets; `jev_officer/` is a separate directory from the frozen
  `jev/` inputs).
