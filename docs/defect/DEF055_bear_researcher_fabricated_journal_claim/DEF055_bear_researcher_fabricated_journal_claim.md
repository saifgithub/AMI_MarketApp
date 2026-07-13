# DEF055 — Bear Researcher claims Decision Journal history it never actually reads

**Status:** resolved (AT:R58) · **Filed:** AT:R58 · **Date:** 2026-07-13
**Source:** prompt — found while checking agent-wiring status after DEF051. **CR033's
original audit (AT:R57) reviewed Bull Researcher for this exact claim but never checked
whether Bear Researcher made the identical claim — this Defect closes that gap in the
original audit, not just in the code.**

## Problem

`content/agents/bear_researcher.md` makes the identical unverified claim as
`bull_researcher.md` (DEF054): "Historical context from the Decision Journal." Same
fabrication, same root cause — `journal_store` is write-only from the Room's
perspective; nothing reads past entries back into a future run's prompt. The Bear
Researcher never actually sees the user's trade history or past verdicts.

Also present, same pattern as Bull's `bull_size`/`bull_falsifier`: `bear_size`
(`room_runner.py:273`, fixed at `2`) and `bear_catalyst`/`bear_invalidator` (fixed
literal strings) in `_profile_for_ticker()` never vary with any real input.

## Root cause

Identical to DEF054 — the prompt was authored describing the Bear Researcher's
conceptual role before any journal read-back existed. CR033's audit (AT:R57) reviewed
all 12 agents but, in practice, only checked Bull Researcher's "Decision Journal" claim
explicitly and didn't cross-check the symmetric Bear Researcher prompt for the same
language — an audit-completeness gap, surfaced when re-checking agent wiring status
after DEF051 shipped.

## Fix

Apply the identical fix built for DEF054 (Bull Researcher) to the Bear Researcher's
prompt/profile construction. **Do not duplicate the journal-query logic** — whatever
helper DEF054 introduces for pulling + summarizing the user's recent Decision Journal
entries should be shared between Bull and Bear (both need the same real data, just
narrated from opposite theses), not reimplemented.

- Reuse DEF054's journal read-back helper for the Bear Researcher's profile/prompt
  section.
- `content/agents/bear_researcher.md` rewritten to match the same real scope DEF054
  lands (ticker-scoped vs. general-recent, whichever DEF054 built).
- Same graceful-degradation contract: no journal history yet → "no history yet"
  framing, never an error.

**Hardcoded `bear_size`/`bear_catalyst`/`bear_invalidator`:** same disposition as
DEF054's `bull_size`/`bull_falsifier` — fix alongside if it falls out naturally from the
shared journal-context wiring, otherwise explicitly note as deferred.

## Fix (AT:R58)

Implemented in the same commit as DEF054 — `journal_context.py`'s
`build_journal_context_block()` is shared between both researchers, gated by
`agent_id in (AgentId.BULL_RESEARCHER, AgentId.BEAR_RESEARCHER)` at both call sites
(`room_prompts.py::build_room_messages()` and `agent_runner.py`'s 1-on-1 path) —
no duplicated query or formatting logic. `content/agents/bear_researcher.md`
rewritten identically to Bull's (ticker-scoped, real, "no history yet" framing).

**`bear_size`/`bear_catalyst`/`bear_invalidator` hardcoded literals:** left untouched
this pass, same disposition as DEF054's `bull_size`/`bull_falsifier` — deferred as a
separate, lower-priority item.

Tests are shared with DEF054 where the assertion is symmetric (`test_journal_context.py`
covers both agents equally since the module doesn't distinguish them) and dedicated
where gating specifically needs to prove Bear's own path
(`test_bear_researcher_gets_journal_history_when_present` in `test_room_runner.py`,
`test_journal_block_injected_for_bear_researcher_when_ticker_mentioned` in
`test_one_on_one_journal_injection.py`). Backend suite 714 → 733 (shared delta with
DEF054 — see that Defect's doc for the full count breakdown). Full submission:
[`audit/handshake/cr/DEF055.architect.md`](../../../audit/handshake/cr/DEF055.architect.md).

## Acceptance

- [x] Bear Researcher's Room prompt receives the same real recent Decision Journal
      context as Bull Researcher (DEF054), via **shared** logic, not a duplicated query.
- [x] `content/agents/bear_researcher.md` claim matches actual scope exactly, mirroring
      DEF054's disclosure choice (ticker-scoped, real).
- [x] Same graceful-degradation behavior as DEF054 (no history yet → disclosed, no
      error).
- [x] Disposition recorded on `bear_size`/`bear_catalyst`/`bear_invalidator`: left
      untouched, explicitly deferred, mirroring DEF054's decision.
- [x] Regression tests mirror DEF054's (real entries injected when present; absent
      gracefully when not), extended to Bear Researcher's own gating test (only Bear's
      1-on-1/Room prompt gets the injection when the trigger is Bear-specific).

**depends-on:** DEF054 — implemented together in one commit; this Defect reused its
wiring rather than re-deriving it from scratch, as planned.
