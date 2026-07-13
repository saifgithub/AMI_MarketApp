# DEF054 — Bull Researcher claims Decision Journal history it never actually reads

**Status:** open · **Filed:** AT:R58 · **Date:** 2026-07-13
**Source:** prompt — split out of CR033 (filed AT:R57, docs-only) into an individual Defect
at Saiful's request, so each of the four remaining agent-truthfulness gaps can be tackled
and closed one at a time instead of as one bundled CR.

## Problem

`content/agents/bull_researcher.md` claims "Historical context from the Decision
Journal" as an input. `journal_store` is write-only from the Room's perspective —
`build_journal_entry_for_run()` writes a run's outcome to the journal *after* it
completes; nothing reads past journal entries back into a *future* run's prompt. The
Bull Researcher never actually sees the user's trade history or past verdicts for this
or any ticker, despite the prompt claiming it as an input.

Also present, same function, lower priority (fold in if trivial, otherwise a follow-up):
`bull_size`/`bull_falsifier` in `room_runner.py::_profile_for_ticker()` are fixed
literals (`4`, and a hardcoded string) regardless of any real input — the Bull
Researcher's narrative *reasoning* can inherit real fundamentals/news/social data
per-ticker (via the CR023/CR024 wiring already shipped), but its sizing/probability
conclusion never does.

## Root cause

The prompt was authored describing the Bull Researcher's conceptual role before any
journal read-back existed anywhere in the pipeline. A real pattern for this already
exists elsewhere — Concierge's `load_concierge_context()`
(`backend/app/services/concierge_prompts.py:305-341`) genuinely pulls the user's last 8
real journal entries via `journal_store.list_for_user(user_id, plan=plan, limit=8)` and
injects them into its own context. This pattern was never extended into the Room
pipeline for either researcher.

## Fix

Wire real journal read-back into the Bull Researcher's Room profile/prompt
construction, mirroring Concierge's existing real pattern rather than inventing a new
one:

- Query `journal_store.list_for_user(user_id, ...)` for the user's recent entries.
  Filter to the current ticker if the journal schema supports that cheaply; if
  ticker-scoped filtering isn't feasible without a schema change, inject the N
  most-recent entries generally and disclose that broader scope explicitly in the
  prompt rather than implying ticker-specific history.
- Inject a compact summary (not raw journal text verbatim — same "synthesize, don't
  echo" discipline CR024 applied to Reddit post snippets) into the profile/prompt
  section `_format_profile()` builds for the Bull Researcher.
- Graceful degradation: a user with no journal history yet (new account) gets an
  explicit "no history yet" framing, never an error.
- `content/agents/bull_researcher.md` rewritten to match whatever real scope lands
  (ticker-scoped vs. general-recent — whichever was actually implemented).

**Hardcoded `bull_size`/`bull_falsifier`:** address in this Defect only if it falls out
naturally from the journal-context wiring (e.g., if real history changes what's
plausible to size); otherwise explicitly note it's still hardcoded and out of scope for
this pass, since the narrative-reasoning fix is the higher-value target here (CR033's
original framing agreed this is lower priority than the fabricated-input claim).

## Acceptance

- [ ] Bull Researcher's Room prompt receives real recent Decision Journal entries for
      the authenticated user (ticker-scoped if the schema supports it cheaply, else
      general-recent with the scope disclosed accurately in the prompt).
- [ ] Real journal content is synthesized into a compact summary, not echoed verbatim
      into the profile/prompt.
- [ ] `content/agents/bull_researcher.md` claim matches actual scope exactly
      (ticker-scoped vs. general-recent, whichever was built).
- [ ] Graceful degradation: no journal entries yet → prompt discloses "no history yet,"
      never errors the Room/1-on-1 turn.
- [ ] Disposition recorded on `bull_size`/`bull_falsifier` (fixed alongside, or
      explicitly deferred as a separate lower-priority item).
- [ ] Regression tests: real entries injected when present; absent gracefully when not.
