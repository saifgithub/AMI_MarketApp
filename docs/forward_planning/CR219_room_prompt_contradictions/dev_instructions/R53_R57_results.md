# R53 + R57 results — permanent turn telemetry

WP14. Source design: `../fable/05_further_improvements.md` §7 (R53) and §11
(R57). Both were parked 2026-09-02 (`PARKING_LOT.md`) and un-parked by
Saiful's 2026-09-03 "Build all" ruling. Neither wake-up condition was met at
build time — R53's ("after AC4's post-fix measurement, if demand needs
continuous tracking") and R57's ("R50 shipped + envelope parse rate known")
are both moot per the PARKING_LOT supersession header; "Build all" overrides
them explicitly rather than around them.

## What shipped

- **R53** — a `GAPS: <up to 3 items, or "none">` instruction line on the FOUR
  analyst turns only (`_GAPS_FORMAT`, `room_prompts.py`), trailing the turn
  (unlike STANCE, which leads it since DEF147 — see "why trailing" below).
  Parsed and stripped in `room_runner.py` (`parse_data_gaps`, same
  locate-loosely/parse-strictly DEF147 idiom as the stance envelope) and
  stored as `AgentMessage.data_gaps: list[str] | None` — `None` for a never-
  asked agent or an asked-and-silent turn, `[]` for the prompt's own
  `GAPS: none` opt-out. No migration: rides the existing `room_runs.
  transcript` JSONB column (`models.py:682`).
- **R57** — `AgentMessage.envelope_parsed: bool | None`, set at
  `parse_stance_envelope`'s call site in `room_runner.py` by comparing the
  pre- and post-strip text (a tail was located exactly when stripping
  changed something — the same fact `parse_stance_envelope`'s own control
  flow proves, computed without duplicating its locator). `True`/`False`
  for every one of the 11 prose voices; `None` for the PM (never asked —
  its turn is a JSON verdict), the CR201 Risk-Officer-rendered debator turns
  (derived, not parsed — DEF247/DEF251/DEF257 are unreachable there by that
  module's own docstring), and the non-live scripted demo path (nothing was
  asked because no LLM ran).
- **`backend/scripts/aggregate_data_gaps.py`** — modeled on the arms
  experiment's prototype (`../evidence/analysis/aggregate_arms.py`, read,
  not run), reusing its bucket taxonomy verbatim so this script's ranking is
  directly comparable to the number that harness already produced. Reads
  `room_runs`, applies `app.services.verdict_outcomes.excluded_user_ids()`
  (that function's own docstring calls it "the most complete" of six
  independently-drifted copies of the CR035-synthetic + seed-burst +
  promotion-probe filter — reused rather than re-derived), and reports both
  channels: gap items ranked by (bucket, ticker, agent), and per-agent
  `envelope_parsed` emission rates.

## Two decisions this does NOT touch (R57's scope boundary)

`fable/05`'s section 11 raises stance-envelope **grammar** (forcing the
field via a decoding constraint) as a candidate and explicitly declines to
build it yet. "Build all" builds the MEASUREMENT LEG that candidate's own
wake-up condition demanded — not the grammar. Two pinned decisions stand,
unchanged, unread, untouched by any file in this WP:

- `test_cr210_room_wiring.py::test_no_prose_agent_is_ever_constrained` — no
  prose agent's decode is ever grammar-constrained. Ran clean in this WP's
  own test pass (198/198 in the scoped envelope+CR210+CR201 batch; see Tests
  below) with zero edits to `room_runner.py`'s constraint-selection code,
  `pm_verdict_schema`, or `trader_block_regex`.
- DEF251's own comment: the envelope is a measurement channel, never a
  control. `envelope_parsed` is exactly that channel, read and stored — it
  changes nothing about how any turn is generated.

## Why GAPS trails while STANCE leads

DEF147 moved STANCE to the front of the turn because it was the field
truncation ate first when appended after prose in a length-capped
generation. GAPS was never observed doing that — it is new telemetry, not a
field with a production incident behind it — and the four analysts' decode
budgets already clear their measured maxima (`_AGENT_MAX_TOKENS`'s DEF125
table). Asking two different things to both occupy "the very first line" is
the exact shape of DEF251's collision (two instructions, one slot, the model
resolves it by answering one and treating the other as discharged):
`_STANCE_FORMAT` already owns that slot, so GAPS was given a different one
rather than contest it.

For the same reason, the GAPS locator in `room_runner.py` stayed
**end-anchored** rather than adopting DEF247's "search every line"
widening: DEF247 widened STANCE's search because the corpus *measured*
displacement (an opener line pushing the envelope off the front). Nothing
has yet been measured displacing GAPS, and inventing a shape nobody has
emitted is the P16 mistake the codebase's own comments warn against
repeatedly. If the aggregation script's `not_measured`/omission counts ever
show GAPS turning up mid-turn on real Alpha convenes, that is the trigger to
widen it — deliberately, from data, the same way DEF247 widened STANCE's.

## Strip-order composition (WP requirement, verified)

Tested and passing (`test_cr219_r53_r57_turn_telemetry.py`) that
`parse_stance_envelope` then `parse_data_gaps`, and the reverse order,
produce **byte-identical** stripped bodies and parsed values — on a full
turn, on a turn missing either tail, and on a turn missing both. This holds
structurally because the two locators operate on disjoint lines in the
ordinary case (STANCE at the front or a legacy trailing form; GAPS strictly
the last line) and because `parse_data_gaps` is called AFTER
`parse_stance_envelope` in production (`room_runner.py`'s
`_compute_agent_text`), on the already-stance-stripped text, specifically so
a leaked machine channel can never appear inside a captured gap item.

## Measured prompt-token delta (no extrapolation)

Measured via vLLM's own `/tokenize` endpoint (LAN host `192.168.20.74:8048`,
model `ami-llm`, backed by `qwen38-flash-next-nvfp4` — verified from
`/v1/models`' own `root` path per the CLAUDE.md convention), applied to the
exact wire payload `OpenAICompatibleProvider.stream_chat` sends — the
grounding directive prepended, system+user messages in the real
role/content shape, chat-template applied server-side — for the current
(shipped) prompt WITH the `GAPS:` instruction against the same prompt with
`_GAPS_FORMAT` monkeypatched to empty (the pre-R53 counterfactual),
ticker=AAPL, empty transcript, risk_score=3 trader mandate:

| Agent | WITH tail (tokens) | WITHOUT tail (tokens) | Delta |
|---|---:|---:|---:|
| fundamentals_analyst | 3722 | 3564 | +158 |
| market_analyst | 2590 | 2432 | +158 |
| news_analyst | 2291 | 2133 | +158 |
| social_media_analyst | 2425 | 2267 | +158 |

**+158 prompt tokens per analyst turn**, identical across all four agents —
expected, since `_GAPS_FORMAT` is one fixed string appended identically
regardless of each agent's own base-prompt length (640 characters; the
system-prompt char delta between the two builds matched `_GAPS_FORMAT`'s own
length exactly, confirming the counterfactual isolated only this one
change).

**Validated against the real production pipeline, in the one convene this WP
budgeted**: a single live call through `LLMGateway.stream_chat` (not a raw
HTTP request) for the WITH-tail `fundamentals_analyst` prompt reported
`usage.input_tokens = 3722` — matching the raw `/tokenize` count exactly.
The model followed the new instruction on this same call, opening its reply
with a stance envelope before hitting the deliberately small 16-token cap.
This confirms the `/tokenize`-based measurement above (used for the other
three agents, avoiding three more live generations) reads the same number a
real convene actually pays for.

**Cost in context**: at 262,144 max context and a convene issuing roughly a
dozen calls (per `_AGENT_MAX_TOKENS`'s own accounting), 158 tokens times 4
analyst turns is 632 tokens total per convene — a rounding error against the
budget, and well inside the headroom DEF125's floor-raise already measured
as unconstrained (`num_gpu_blocks` 1664 against this `max_model_len`, zero
preemptions). Not free, but not the reason to reconsider this.

## Emission-rate table

**No live rows yet.** `data_gaps`/`envelope_parsed` are new fields; no
`room_runs` row on Alpha carries either key until this WP's code is
promoted (Alpha's currently deployed tag predates this commit by several
commits on `main` — verified via `/v1/health` and `git log`, read-only, no
promotion run as part of this WP). `backend/scripts/aggregate_data_gaps.py`
is verified on fixtures instead
(`test_cr219_r53_r57_aggregate_data_gaps.py`, 15 tests): the CR035-synthetic
and seed-burst exclusions are honored, `None`-vs-`[]`-vs-answered states are
kept distinct in both the gap-item and emission tallies, items are bucketed
by the arms taxonomy and ranked by (bucket, ticker, agent), a pre-R53/R57
stored row (the key genuinely absent from the dict, not merely `None`)
degrades to `not_measured` rather than crashing or silently joining the
`unparsed` bucket, and the script's own `main()` was run end-to-end against
a real seeded sqlite DB (not just its internal functions) to confirm the CLI
path itself works.

Once Alpha has banked real convenes on this code, re-run
`python -m scripts.aggregate_data_gaps` (from `backend/`, inside the alpha
container) for the real table.

## R57 revisit rule (verbatim, per the WP)

If any debator's emission rate sustains under 75% over at least 100 real
convenes, surface it at a daily review — amending the two pins is Saiful's
decision, made on this data.

This is also the last line the aggregation script itself prints, so it is
not a fact that lives only in this document — every future run of the
script restates it next to whatever the current rate actually is.

For calibration: DEF251's own measurement (`docs/defect/def_list.md`,
`cr143-def247-baseline-20260810`, 105 debator turns, pre-remedy) found 20.0%
of debator turns emitting no envelope at all; DEF251's shipped fix (deleting
the competing "Open your PROSE with:" instruction from the three debator
files) was verified post-promotion at 39/39 = 100% parsed-stance yield
across aggressive/conservative/neutral. `envelope_parsed` and "parsed-stance
yield" are not quite the same measurement (the latter also required a valid
`stance` field, not just a located tail — see the `STANCE: none`
distinction below), but they move together: DEF251's fix targeted exactly
the failure mode `envelope_parsed=False` now measures directly, on every
future convene, without needing a special one-off baseline batch to find
out again.

One measurement subtlety worth flagging for whoever reads the future table:
`envelope_parsed=True` with `stance=None` is a **fully-formed, deliberate**
`STANCE: none` opt-out (the prompt's own escape hatch for a turn that
genuinely isn't taking a side), not an emission failure — verified in
`test_a_deliberate_none_stance_still_counts_as_a_parsed_envelope`. A rate
computed from `envelope_parsed` alone will read HIGHER than one computed
from "did the agent state a directional stance", by design; the two
questions are different and this field answers the first one.

## Tests

New:
- `backend/tests/unit/test_cr219_r53_r57_turn_telemetry.py` — 41 tests: the
  `parse_data_gaps` parser (well-formed, case/spacing drift, bold emphasis,
  optional bracket, more-than-3-item truncation, over-length-item drop,
  `none` spellings, lettered/bulleted markers stripped, comma-inside-item
  survival, trailing period strip, empty tail, mid-paragraph non-match,
  blank input); strip-order composition with `parse_stance_envelope` (both
  orders, byte-identical, plus all four presence/absence combinations);
  prompt-assembly (exactly the four analysts get the `GAPS:` line, exactly
  once, trailing after STANCE; no other agent ever sees it); storage shape
  end-to-end through a real `RoomRunner.run()` (full turn, `GAPS: none` maps
  to `[]`, a silent analyst maps to `None`, non-analyst agents never carry a
  value, the PM carries neither field, the scripted-demo path carries
  neither field); and R57's `STANCE: none`-is-still-parsed distinction.
- `backend/tests/unit/test_cr219_r53_r57_aggregate_data_gaps.py` — 15 tests
  on a fixture DB: exclusion filter (CR035 synthetic + seed burst) applied
  to both tallies; `None` vs `[]` counted separately; non-`GAPS_AGENTS`
  turns never contribute even if a stray value is present; bucket ranking by
  (bucket, ticker, agent); unbucketed items kept, not dropped;
  parsed/unparsed/not_measured emission tally per agent; a genuinely
  pre-migration row shape (the key deleted, not just set to `None`)
  degrades correctly; PM/internal agents absent from the emission table;
  only agent-role rows counted; ticker and since filters; empty input
  degrades to zeros, not a crash.

Existing (regression, unmodified) — run scoped, per the dispatcher's
mid-WP amendment:

    backend/.venv/bin/pytest tests/unit/test_cr106_stance_envelope.py \
      tests/unit/test_def257_emphasised_stance_envelope.py \
      tests/unit/test_def247_displaced_stance_envelope.py \
      tests/unit/test_cr197_size_envelope.py \
      tests/unit/test_def241_def243_debator_arithmetic_and_stance.py \
      tests/unit/test_cr210_room_wiring.py \
      tests/unit/test_cr210_schemas.py \
      tests/unit/test_cr219_r50_room_scoreboard.py \
      tests/unit/test_cr201_risk_officer_room.py -q
    # 198 passed

plus `test_room_prompts.py` + `test_cr153_risk_state_in_prompt.py` (85
passed), run both from `backend/` and from repo-root CWD (283 passed
repo-root, same files as above plus the prompt-assembly pair). The bare
`backend/tests/unit/ -q` full-suite run was explicitly dropped from this
WP's acceptance evidence — the box was running many concurrent full-suite
pytest invocations from sibling lanes that were starving/SIGTERM-ing each
other. Everything above is the scoped substitute; the promotion suite gate
covers full-suite integration.

## Files touched

- `backend/app/schemas/agents.py` — `AgentMessage.data_gaps`,
  `.envelope_parsed`.
- `backend/app/services/room_prompts.py` — `GAPS_ITEM_MAX_CHARS`,
  `_GAPS_FORMAT`, wired into `build_room_messages` for `phase == "ANALYSTS"`.
- `backend/app/services/room_runner.py` — `_GAPS_LINE_RE`, `_GAPS_MAX_ITEMS`,
  `parse_data_gaps`; `_compute_agent_text` computes `envelope_parsed` and
  (for the four analysts) `data_gaps`, returns both; `_stream_agent_text`
  threads both onto the stored `AgentMessage` (deliberately NOT onto the
  yielded `RoomEvent` — see that function's own docstring: this is
  telemetry, never a wire/UI field); both call sites of each function
  updated (`_speak_one_agent`, the concurrent-ANALYSTS `asyncio.gather`
  path).
- `backend/scripts/aggregate_data_gaps.py` — new.
- `backend/tests/unit/test_cr219_r53_r57_turn_telemetry.py` — new.
- `backend/tests/unit/test_cr219_r53_r57_aggregate_data_gaps.py` — new.
- This file.

## Not touched (in-scope exclusions, verified)

- CR210 grammar wiring, `pm_verdict_schema`, `trader_block_regex`, any
  prompt instruction naming the envelope itself (`_STANCE_FORMAT`,
  `_STANCE_FORMAT_RISK`) — read, never edited.
- `RoomEvent` (the SSE wire schema) — deliberately excluded; see "What
  shipped" above.
- `harness/` under this CR's own folder and its result files — WP13 Part
  B's live replay was mid-flight against the LAN vLLM for the duration of
  this work; nothing in that directory was read, written, or had a process
  killed.
- The two registers (`cr_list.md`, `def_list.md`) — not hand-edited.
