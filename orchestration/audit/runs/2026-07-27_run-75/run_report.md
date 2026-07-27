# Audit run — 2026-07-27 run-75

**Item:** DEF124 round 1 · **SHA** `55b7eaf` (`lane/DEF124.coder.room`) · **Verdict:** COMPLETE · **BLOCKER 0 · MAJOR 0 · MINOR 1**

Worktree `.claude/worktrees/audit-DEF124` (`git worktree add --detach`), venv symlinked, reaped after.

## Order of operations

1. Scope diff `7090435..55b7eaf` — **10 files, +450/−9**, 5 commits. Exact match.
2. Full suite **1393 passed / 190.58s**, clean tree, `__pycache__` cleared, **before any mutation**.
3. Delta accounting: 16 new test functions, one parametrised over 5 profiles → +20. `--collect-only` = 1393.
4. **End-to-end probe of my own** (not the lane's tests): real `_profile_for_ticker` → real
   `build_room_messages`, all 12 Room agents, system prompt **and** user message.
5. Mutation battery M1/M2/M5/M6/M7 (revert each site + probe the invariant's reach), each verified
   present in source, reverted after, `dirty=0` at the end.
6. M4 — the Architect's flagged non-ISO question, measured.
7. Test-merge of current `main` (post-DEF128) + full suite, then reset.

## The defect's own metric

| | Before (defect filing) | Measured now |
|---|---|---|
| Room prompts carrying the run date | **0 of 12** | **12 of 12** |
| Prompts with earnings date + computed interval | 0 | **12 of 12** |
| Unanchored ISO dates, system prompts | — | **0** |
| Unanchored ISO dates, **user messages** (never inspected by the lane's test) | — | **0** |
| `relative_day_phrase`, 801 offsets −400…+400 | — | **0 failures** |

## Mutation results (baseline 154 passed)

| Probe | Result |
|---|---|
| M1 — drop the Room earnings interval (revert D1) | **4 failed** |
| M2 — drop the run-date header (revert D2) | **1 failed** |
| M6 — drop the 1-on-1 interval (revert D3) | **1 failed** |
| M7 — drop the 1-on-1 `as of` header | **1 failed** |
| M5 — a new unanchored ISO date on an unrelated line | **5 failed** — invariant is load-bearing |
| M4 — a non-ISO unanchored date (`March 14, 2026`) | **154 passed** — **the MINOR** |

## Checks nobody asked for

- **News Analyst block** (`news_context.py`) — the agent that produced the original "13-month void".
  Every headline age goes through `_relative_age` (`2h ago` / `3d ago` / `date unknown`). No
  unanchored absolute date on that surface; the D3 sweep has no gap there.
- **`date.fromisoformat` sits outside the provider `try`** — a non-ISO string would kill the convene.
  Read **all six** `MarketDataProvider.earnings` implementations: only `market_data.py:633`
  constructs a date (ISO), the rest return `None` or delegate. The in-source claim holds.
- **DEF128 merge-order interaction, unmeasured by anyone**: the branch forked before DEF128 widened
  CR104's taint traversal, and DEF124 adds a new profile field — the exact shape that tracker
  watches. Test-merged `main`: **no conflicts, 1398 passed** = main's 1378 + 20. Reset after.
- **D3's Brief Your Agent exclusion** verified rather than accepted: `brief_engine.py` imports no
  profile/fundamentals renderer.

## Methodology note

The end-to-end probe was built deliberately outside the lane's test fixtures — the defect's metric is
a property of the *rendered prompt in the real pipeline*, and reusing the lane's fixtures would have
measured the lane's own assumptions. It also caught the one surface the lane's invariant never
touches (the user message), which came back clean.
