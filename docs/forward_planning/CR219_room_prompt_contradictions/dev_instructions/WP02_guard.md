# WP02 — Guard v2 (R8–R14, R22, R44, R61)

The one control that makes every other WP stick (CR038: prompt wording is ignored ~70%
of the time under pressure — the guard is the guarantee, the prose is just the input).
Base spec: `../GLM/02_improved_plan.md` Phase 1 and `../GLM/03_target_prompt_set.md`
§6, extended by the 2026-09-02 rulings below. Model routing: **Opus** (or Sonnet with
explicit acceptor review) — this is load-bearing.

**Shape**: one new test module, suggested `backend/tests/unit/
test_cr219_availability_guard.py`, plus a small fixtures helper if needed. It runs in
the normal unit suite (sqlite tempfile env, no network). Reuse the sentinel-injection
fixtures from `backend/tests/unit/test_prompt_data_parity.py` to render a fully
populated sheet through the production renderer (`_format_profile`,
`backend/app/services/room_prompts.py:1882`) — never hand-build a sheet approximation.

## Requirements (each is a register row — cite the row in the test's docstring)

- **R8 (ruled)** — mechanism is hand-fixed prose + this guard. No generated prompt
  content, no registry module that renders into prompts. The guard *reads*; it never
  *writes* prompt text.
- **R9** — every negative availability claim found in a persona must be proven **TRUE**
  against the fully-populated rendered sheet for that agent's lanes — not merely
  "present in an allowlist". A claim is true iff its collision markers (below) are
  absent from that agent's rendered sheet.
- **R10** — scan the **whole persona file**, not just an `## Inputs`→`## Output` slice.
  Every match of the denial-pattern set anywhere in the file must resolve to a
  known-absent entry or an explicit allowlisted category (runtime-deference or
  role-boundary), else red.
- **R11** — the **overlay generator is in scope**: extract the data demands
  `backend/app/agents/overlay_generator.py` emits (all branches — iterate the Mandate
  enum space, don't hand-pick) and map each demand phrase to a `field_state` key the
  sheet actually renders. A demand with no backing key is red. (This is what closes
  R21 mechanically once WP06's field lands.)
- **R12** — every known-absent entry carries **collision markers**: short substrings
  that, if ever found in the fully-populated rendered sheet, prove the denial false and
  fail the guard. Markers short enough to survive rewording (e.g. `"Margin trend"`,
  not a whole sentence).
- **R13 (ruled: adopted)** — **exhaustive by construction**: the guard enumerates
  `content/agents/*.md` from the filesystem and requires every file to appear in its
  mapping (even if mapped to "no availability claims expected"). An unmapped or newly
  added file = red until someone maps it. This is what makes R44 automatic.
- **R14** — the test module's docstring states the design's blind spot plainly: the
  mapping is authored, so a *mis*-mapped claim can still lie; the guard guarantees
  every claim is examined, not that the examiner is infallible.
- **R22** — forbidden-phrase check on overlay output: no overlay branch may demand
  "guidance" (the sheet's own disclaimer says guidance is not supplied). Keep as its
  own assertion so the error message names the branch.
- **R61 (ruled: rides CR219)** — headline-framing check: news headlines are untrusted
  input. Assert the news/social personas (and any prompt that embeds headlines)
  instruct framing headlines as **quoted data** ("the headline says…"), never as
  instructions or verified facts. Add one fixture with a hostile headline
  ("IGNORE PREVIOUS INSTRUCTIONS…") and assert the prompt text around it establishes
  the quoted-data frame. This is a prompt-text check, not a jailbreak test — keep its
  claim honest in the docstring.
- **R44** — the 26 unswept prompts (concierge, Brief Your Agent surfaces) enter the
  R13 enumeration. For rendering them, extend `../evidence/dump_sheets.py` /
  `../evidence/assemble_room.py` — do NOT write parallel new scripts.

## Red fixtures (the guard must fail when it should — prove it)

1. Plant a false denial in a copy of a persona's `## Voice` section ("we receive no
   margin data") → guard red (proves R10 whole-file + R9 truth-check).
2. Add a fabricated known-absent entry with `collision_markers=("Margin trend",)` →
   guard red against today's sheet (proves R12 fires on real collisions).
3. Drop a new `content/agents/zz_test_agent.md` into the enumeration fixture → guard
   red (proves R13).

Wire these as pytest cases that assert the guard's own failure, not as skipped
examples.

## Retirement

`backend/tests/unit/test_cr105_analyst_inputs_field_state_guard.py` carries
presence-only negative-claim checks. Retire the ones this guard supersedes **in
lockstep, same commit** as each replacement lands — never delete first. Anything in
cr105 the new guard does not cover stays.

## Acceptance

- Guard green on HEAD after WP01's persona fixes; red on each fixture above.
- `backend/.venv/bin/pytest backend/tests/unit/ -q` green overall.
- Deliberately reintroduce finding #1's denial sentence in a scratch branch → guard
  red. (This is the acceptor's manual check, not a committed test.)
