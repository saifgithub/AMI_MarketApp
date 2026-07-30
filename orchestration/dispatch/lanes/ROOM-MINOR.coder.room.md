<!-- lane hand-off — coder.room. CR052. -->
# ROOM-MINOR — coder.room hand-off

STATUS: READY_FOR_AUDIT (round 1)

Branch: `lane/ROOM-MINOR.coder.room` (pushed to origin)
Worktree: `.claude/worktrees/coder.room-ROOM-MINOR`
File touched: **only** `backend/app/services/room_runner.py`, plus its tests and the DEF register.

## DEF172 — `round(entry * 0.94)` TypeError crash

`_parse_pm_verdict` (room_runner.py, was :913-922) derives `stop`/`target` from
`entry` (`entry_raw or ctx.trader_entry`) via `round(entry * 0.94, 2)` /
`round(entry * 1.13, 2)`. If both `entry_raw` (PM stated none) and
`ctx.trader_entry` are `None`, `entry` is `None` and the multiply raises
`TypeError`, killing the agent turn.

**Fix shape chosen:** guard the derivation on `entry is not None`. When it
holds, behaviour is byte-identical to before. When it doesn't:
- `stop`/`target` fall back to whatever the PM itself stated (`stop_raw`/
  `target_raw`), which is `None` if the PM said nothing either — **never** a
  fabricated number.
- `level_provenance` is now built as a dict that only gets a key for a price
  actually attributed to something. Previously it unconditionally emitted all
  three keys (`entry`/`stop`/`target`); now `entry` is omitted when neither
  source held, and `stop`/`target` are omitted when they're `None` (nothing to
  label `pm` or `ami_default`). This keeps T-BACKFILL's invariant: an omitted
  key must never be read as "came from the PM" — the `Literal["pm","trader",
  "ami_default"]` type on `Verdict.level_provenance` has no fourth value, so
  the only honest way to represent "couldn't be attributed" is absence, not a
  new literal that would need a schema change beyond this lane's scope.
- `reason` gets a new sentence — "(stop/target not stated by the PM, and no
  entry price was available to derive a protective level from.)" — parallel to
  the existing "defaulted to a ~6%/13%..." sentence, so a reader sees *why*
  the levels are missing rather than a silently blank field. This satisfies
  the acceptance criterion that the absence be visible.

**Sibling check (row asked for this explicitly):** searched the whole file for
other unguarded multiplications off `entry`. Found exactly two — the `stop`
and `target` derivations already fixed above, both in the same block. No other
site in `room_runner.py` multiplies on a possibly-`None` `entry`. (Line
2360-2361, `ctx.trader_stop = round(base * 0.94, 2)`, looks similar but `base`
there is guaranteed non-`None` — `profile.get("base_price")` falls back to
`get_market_data_provider().get_price(...) or 100.0` two lines above — so it
was not in scope.)

**Test:** new file `backend/tests/unit/test_def172_pm_verdict_no_entry.py`,
calling `_parse_pm_verdict` directly against a hand-built `_RoomContext` with
`ctx.trader_entry = None` (the real convene path always ends up setting
`trader_entry` to a float via the `or 100.0` fallback at line ~2358, so this
crash is reachable only when a caller constructs/mutates `_RoomContext`
directly with `trader_entry` unset to its type-hinted-but-unenforced
default — the unit-level entry point is the honest place to pin it, not a
full `RoomRunner.run()` integration test). Three tests: turn survives, level
is visibly absent (entry/stop/target None, provenance omits the keys, reason
names why), and a stop the PM *did* state survives even with no entry.

## DEF163 — `_clip_summary` strip order

One-line fix at room_runner.py: `cut.rstrip().rstrip(',;:')` →
`cut.rstrip(',;:').rstrip()`. Added
`test_a_cut_landing_on_punctuation_before_a_space_leaves_no_trailing_space` to
the existing `test_def150_journal_summary_clip.py`, using the row's own
`('ab , cd ' * 40)` reproduction.

## Verification performed

1. Both new tests **watched red** against unfixed code before fixing:
   - DEF172: `TypeError: unsupported operand type(s) for *: 'NoneType' and 'float'`
     at the `target = ...` line.
   - DEF163: `AssertionError: punctuation strip exposed a trailing space` —
     the fixture ends `"...ab , cd ab …"`.
2. Both green after the fix.
3. **Mutation check, run individually:**
   - Reverted only the DEF163 `.rstrip()` swap (DEF172 fix left in place):
     the DEF163 test went red (1 failed), all DEF172 tests stayed green.
   - Reverted only the DEF172 guard (DEF163 fix left in place): the 3 DEF172
     tests went red with the same `TypeError`, the DEF163 test stayed green.
   - Confirms the two fixes are independent and each test is load-bearing for
     its own defect, not accidentally passing either way.
   - No mutation came back green when it should have been red — nothing to
     report as a false-positive guard.
4. Full suite from repo root:
   `"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest backend/tests/unit/ -q`
   → **1747 passed, 0 failed** (baseline 1719 — well clear). Ran full suite
   twice (once mid-lane, once after final restore) with identical result.

## Registers

`DEF172.row.md` and `DEF163.row.md` flipped to `fixed`, regenerated
`docs/defect/def_list.md` via `scripts/registers/gen_registers.py gen def`.
Not yet committed — leaving that to the integration step per sprint mode
(Architect verifies + integrates; no `.architect.md` submit file this round).

## Fences respected

Only `backend/app/services/room_runner.py` edited in `backend/app/`. Test
files added/edited under `backend/tests/unit/`. `mobile/` untouched. No
restructuring — both fixes are local edits inside `_parse_pm_verdict` and
`_clip_summary`, no signature or call-site changes elsewhere.

## Nothing to disclose as wrong in the assignment

No instruction in the lane assign measured out as incorrect. Both defects
matched their row descriptions exactly once the code was read.
