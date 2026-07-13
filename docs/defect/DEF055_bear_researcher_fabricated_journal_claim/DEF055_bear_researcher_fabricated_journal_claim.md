# DEF055 — Bear Researcher claims Decision Journal history it never actually reads

**Status:** open · **Filed:** AT:R58 · **Date:** 2026-07-13
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

## Acceptance

- [ ] Bear Researcher's Room prompt receives the same real recent Decision Journal
      context as Bull Researcher (DEF054), via **shared** logic, not a duplicated query.
- [ ] `content/agents/bear_researcher.md` claim matches actual scope exactly, mirroring
      DEF054's disclosure choice (ticker-scoped vs. general-recent).
- [ ] Same graceful-degradation behavior as DEF054 (no history yet → disclosed, no
      error).
- [ ] Disposition recorded on `bear_size`/`bear_catalyst`/`bear_invalidator` (fixed
      alongside, or explicitly deferred), mirroring DEF054's decision.
- [ ] Regression tests mirror DEF054's (real entries injected when present; absent
      gracefully when not), extended to Bear Researcher's own gating test (only Bear's
      1-on-1/Room prompt gets the injection when the trigger is Bear-specific).

**depends-on:** DEF054 — implement DEF054 first; this Defect reuses its wiring rather
than re-deriving it from scratch.
