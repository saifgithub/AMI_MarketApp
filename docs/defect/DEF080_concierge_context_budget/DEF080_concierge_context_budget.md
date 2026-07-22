# DEF080 — Concierge full-context lesson index outgrew its token-budget guard (BOK growth)

**Status:** planned · **Session:** AT:R64 · **Filed:** 2026-07-22 · **Kind:** prompt-spotted (full-suite preflight) · **Area:** backend

## The defect

`test_concierge_context_router.py::test_full_context_token_budget` fails: the Concierge's
`_full_context_index(_all_lessons())` block is **~13,051 est-tokens vs the test's hardcoded 13,000
cap** (over by 0.4%). Root cause: the lesson corpus grew **270 → 334** (CR054 BOK Wave-1
ETHIC/ASST/MACRO/QUANT + CR058 SHARIA), and the index is one line per lesson, so it scales linearly.
The `_CONTEXT_TOKEN_BUDGET = 12_000` constant (`concierge_prompts.py:49`) and the test threshold were
both sized when the docstring's "~270 lessons" was current.

**Production impact is minor** (this is why it's a guard-trip, not an outage): over-budget only
**logs** `concierge_context_over_budget` (`concierge_prompts.py:92`) — it never truncates or fails,
and the on-prem vLLM (`ami-llm`, **262k context**) holds a 13k index trivially. The failing test is a
soft-cap guard, but it correctly **blocks `/promote-to-alpha`** (the preflight runs the full unit
suite), which is how it surfaced.

## Fix

Raise the budget to reflect the grown corpus + the 262k-context LLM, and **tie the test to the
constant so they can't silently drift again**:

1. `concierge_prompts.py` — `_CONTEXT_TOKEN_BUDGET` `12_000` → `20_000` (headroom to ~500 lessons at
   the current per-line size). Update the comment: note corpus 334 and growing; the vLLM's 262k
   context makes a ~13–20k index a non-issue; **`embedding` mode (CR019) remains the escape hatch**
   when the corpus reaches many hundreds and full_context stops being the right strategy.
2. `test_concierge_context_router.py::test_full_context_token_budget` — assert against
   `_CONTEXT_TOKEN_BUDGET` (import it) instead of a hardcoded `13_000`; refresh the "~270 lessons"
   docstring to the current corpus. This makes the guard track the constant automatically.

No routing-signal loss (all tags kept — full_context stays full). No behaviour change beyond the log
threshold. This is a guard-maintenance fix, not a redesign; index compaction / pagination /
`embedding` cutover is a **future CR** when the corpus is much larger.

## Guard / acceptance

`cd backend && uv run pytest tests/unit/test_concierge_context_router.py -q` green, **and the full
unit suite green** (this is the promote preflight gate). No other test regresses.

Commit tag: `(AT:R64 DEF080)`.
