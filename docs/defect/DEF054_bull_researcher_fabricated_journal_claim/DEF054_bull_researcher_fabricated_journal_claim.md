# DEF054 — Bull Researcher claims Decision Journal history it never actually reads

**Status:** resolved (AT:R58) · **Filed:** AT:R58 · **Date:** 2026-07-13
**Source:** prompt — split out of CR033 (filed AT:R57, docs-only) into an individual Defect
at Saiful's request, so each of the four remaining agent-truthfulness gaps can be tackled

## Fix (AT:R58)

New `backend/app/services/journal_context.py` mirrors Concierge's existing real
pattern (`concierge_prompts.py::load_concierge_context()` →
`journal_store.list_for_user()`) rather than inventing a new one. Genuinely
ticker-scoped — `list_for_user()` already supports a `ticker` filter, no schema
change needed — so this is real per-ticker history, not a general-recent fallback
the original doc treated as the likely-necessary compromise.

Wired into the Room path (`room_prompts.py::build_room_messages()`, mirroring the
existing Portfolio-Manager-only `pm_note` pattern — a new `journal_note` appended
only for Bull/Bear Researcher) and the 1-on-1 path (`agent_runner.py`,
Bull/Bear-gated, mirroring CR023/CR024/DEF052's Analyst-only gating). No journal
entries yet for a ticker → the block is simply absent, and the rewritten
`content/agents/bull_researcher.md` explicitly instructs the agent to say so rather
than invent one.

**`bull_size`/`bull_falsifier` hardcoded literals:** left untouched this pass — the
narrative-reasoning fix (the actual fabricated-input claim) was the higher-value
target; the sizing figures are a separate, lower-priority finding (per the original
doc's own framing), not folded in here.

Shared with DEF055 (Bear Researcher) via the same `journal_context.py` module —
neither the fetch nor the formatting logic is duplicated.

19 new tests: `test_journal_context.py` (9 — fetch/format/degradation, ticker
isolation, anonymous-user handling, store-error handling), `test_room_runner.py`
extensions (5 — Room-level Bull/Bear-only gating), `test_one_on_one_journal_injection.py`
(5, shared with DEF055 — 1-on-1 gating for both researchers). Backend suite
714 → 733, all green. Full submission:
[`audit/handshake/cr/DEF054.architect.md`](../../../audit/handshake/cr/DEF054.architect.md).
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

- [x] Bull Researcher's Room prompt receives real recent Decision Journal entries for
      the authenticated user — genuinely ticker-scoped (`list_for_user(..., ticker=)`
      already supported it, no schema change needed).
- [x] Real journal content is synthesized into a compact one-line-per-entry summary
      (date + title + outcome), not echoed verbatim.
- [x] `content/agents/bull_researcher.md` claim matches actual scope exactly
      (ticker-scoped, real).
- [x] Graceful degradation: no journal entries yet → the block is absent and the
      prompt instructs the agent to say so; store errors return `[]`, never raise.
- [x] Disposition recorded on `bull_size`/`bull_falsifier`: left untouched this pass —
      explicitly deferred as the separate, lower-priority item the original doc
      framed it as.
- [x] Regression tests: real entries injected when present (ticker-isolated); absent
      gracefully when not (no history, anonymous user, store error).
