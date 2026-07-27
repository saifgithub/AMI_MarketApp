<!--
Auditor run report — run-64 (2026-07-27, session auditor.core/track U). Round-1
audit of DEF116. Audited SHA d68a028 on lane/DEF116.coder.api. Verdict
AWAITING_FIXES round 2 — one MAJOR in the guard. Owner: AUDITOR.
-->

# run-64 (round 1) — DEF116 blocking-I/O offload + AST guard → AWAITING_FIXES

- **Auditor session:** auditor.core (track U), 2026-07-27.
- **Audited SHA:** `d68a028`, off `main` @ `e5fc1ad`. Isolated worktree
  `.claude/worktrees/audit-DEF116/`, own venv, everything foreground or explicitly awaited.
- **Provenance:** the coder never reported and never committed (5th lane-worker protocol failure
  in ~27h). The Architect committed the work as found without altering a line, then verified it.
  **No coder claims exist in this lane — only Architect claims.**
- **The item:** synchronous, network-bound calls (yfinance / `SimEngine.current_*` /
  `build_*_block` / `_profile_for_ticker`) made inline from `async def` handlers on a
  single-process, single-event-loop uvicorn. Saiful graded it an **MVP show-stopper**.
- **Gate:** independent — show-stopper severity, Room + 1-on-1 hot paths, production Dockerfile
  CMD, and the second occurrence of a class that produced a MAJOR audit finding the same day
  (CR049).

## Reproduced independently

Scope `git diff e5fc1ad d68a028 --stat` → 5 files, **+263/−13**, exact match. Full suite
`./backend/.venv/bin/python -m pytest backend/tests/unit/ -q` → **1333 passed** in 204s (baseline
1332 + 1 new guard test), matching. `import asyncio` present in all three touched modules.
`quotes_batch`'s `run_in_executor` fan-out untouched (0 diff lines), as the assign required.

**D2 (leaves stay synchronous)** — the strongest available structural check:
`git diff … -- backend/app | grep -E "^[+-].*(async )?def "` returns **zero lines**. No function
signature anywhere in the diff moved, so no leaf became `async def` and no patch site could have
been invalidated by a signature change.

**Dockerfile** — `--reload` dropped from the production CMD. Grepped every `*.yml` / `Dockerfile*`
/ `*.sh` in the tree: **zero `--reload` remaining**, and `docker-compose.yml`'s `api-alpha` block
carries only `build:`/`dockerfile:` — no `command:` or `entrypoint:` that could reinstate it.

## The 5 call sites

Read all 5 hunks. Each is `await asyncio.to_thread(<leaf>, …)` at the call site, leaf passed **by
reference**, never called — D1's mandated pattern and consistent with the codebase's existing
`sharia_universe.py:512-521` / `classification_universe.py:508-513` precedent.

## Item #4 — CR090's kwargs survived the hoist — mutation-proved

`room_runner.py` hoists `profile = await asyncio.to_thread(_profile_for_ticker, ticker,
news_feed=news_feed, social_feed=social_feed)` ahead of `_RoomContext(...)` and passes
`profile=profile`. `_RoomContext` is a plain `@dataclass` with **no `__post_init__`** (read
directly), so the subsequent `profile = ctx.profile` is the same object — the seam is inert.

Not taken on reading. **Dropped `news_feed=`/`social_feed=` from the hoisted call** →
`test_cr090_room_live_data_surcharge.py` went **3 failed / 9 passed**, all three
`test_charged_surcharge_equals_rendered_live_feeds` parametrisations. CR090's D4 lesson (moving
this exact seam silently voids patch-based tests) did **not** repeat. Reverted, tree clean.

This doubles as the useful half of the D2 follow-up: the hand-off's "~15 `monkeypatch.setattr`
tests" is loose — exactly **one** test patches a DEF116 leaf by name
(`test_cr090_room_live_data_surcharge.py:230`, `_profile_for_ticker`), and the mutation above
proves it is live *through* the `to_thread` boundary rather than passing vacuously. Everything
else is neutralised below the leaf.

## Item #2 — guard soundness, on four shapes the Architect never used

Deliberately avoided the Architect's two probes (they asked for independent shapes; the CR049
auditor did the same). Each mutation reverted individually, guard re-confirmed green after each.

| Probe | Shape | Guard |
|---|---|---|
| P-A | `agent_runner.py`'s `build_live_data_block` un-deferred — a **third module**, neither of the two probed | **RED** |
| P-B | blocking leaf inside a **list comprehension** in a route handler | **RED** |
| P-C | blocking leaf in a **dead conditional branch** | **RED** |
| P-D | blocking leaf via a **brand-new class method hop** (`SimEngine._audit_probe_hop`) | **RED**, chain names the hop |

P-A's output is the strongest evidence the walker is real, not a diff-scoped name match — it
resolved **5 hops through 4 modules** the mutation never touched:

```
coach.py:coach_message_legacy -> build_live_data_block (via stream_one_on_one_message in agent_runner.py)
    (via event_stream in one_on_one.py) (via brief_message in brief.py)
coach.py:coach_message_legacy -> yf.Ticker (via fetch_live_fundamentals in services/fundamentals.py)
    (via build_live_data_block in services/fundamentals.py) (via stream_one_on_one_message …) …
```

## Item #1 — the waiver — the MAJOR

Wrote a probe harness that loads the guard module and re-runs its own analysis with
`_WAIVED_CALL_CHAIN_NAMES` swapped, so every number here is measured.

- **Baseline:** 85 route handlers walked, **0 offenders** — guard green.
- **Empty waiver:** **11 chains across exactly the 9 handlers** the hand-off names
  (`get_portfolio`, `reset_portfolio`, `preview_trade`, `submit_trade`, `evaluate_trades`,
  `close_trade`, `audit_holdings`, `sector_allocation`, `stream_room`). The Architect's DEF120
  measurement reproduces exactly.

**The docstring's honesty claim** — *"removing a name here without fixing its call site should
turn this guard red again"* — **is false for 7 of the 9 names**:

| dropped from the waiver | chains | guard |
|---|---|---|
| `_marks_with_quotes` | 2 | RED |
| `preview` | 1 | RED |
| `current_marks` | 0 | **STILL GREEN** |
| `current_marks_with_source` | 0 | **STILL GREEN** |
| `current_price` | 0 | **STILL GREEN** |
| `submit` | 0 | **STILL GREEN** |
| `evaluate_outcomes` | 0 | **STILL GREEN** |
| `manual_close` | 0 | **STILL GREEN** |
| `_build_room_sector_context` | 0 | **STILL GREEN** |

Mechanism: the names **shadow one another**. `current_marks` is called straight from
`api/sim.py:126`, but its only blocking path runs through `_marks_with_quotes` — still waived, so
still pruned — and `current_marks` has no direct leaf call of its own. `current_price`
(`sim_engine.py:259`, a direct `self.current_quote` caller) is reachable only via
`submit`/`evaluate_outcomes`/`manual_close`, all still waived, so it is never entered at all. The
waiver is therefore not revocable name-by-name; it is a blanket suppression wearing the costume of
honest bookkeeping. That claim is, per the hand-off's own framing, "the only thing keeping the
waiver honest rather than decorative."

**The consequence is worse than stale bookkeeping.** The prune skips the entire subtree, so a
blocking call that does not exist today is equally invisible if added inside a waived function.
Proved it rather than reasoning it: injected `self.current_news("AAPL", 1)` as a brand-new first
statement of `SimEngine.submit` — reachable from `POST /sim/trade` (`submit_trade`), the hottest
write path in the app — and the guard reported **`1 passed`, green**. That is precisely the
Architect's stated failure condition ("a guard that goes green on a genuinely new regression is
worse than no guard") and this project's own DEF038/DEF063 lesson in a different costume.
Reverted; tree clean.

**Name-collision sub-question, answered:** grepped every definition matching each of the 9 names.
Exactly one collision exists — `merge_service.py:110::preview` — and reading it shows pure DB
counting, no network leaf, so nothing unrelated is masked **today**. Latent, not live.

**Recommended fix, small and confined to the test file.** Either scope the waiver to
`(module, function)` and prune only that edge instead of the subtree, or — cheaper and stronger —
add a companion test that runs the same walk with an **empty** waiver and asserts the offending
route set equals exactly the 9 known DEF120 routes. DEF120 stays waived; a 10th route (a new
regression, or a DEF120 fix that missed a site) turns that companion test red.

## Item #2b — the `to_thread` exemption is inverted

`_to_thread_wrapped_call_ids` exempts any `ast.Call` occupying `asyncio.to_thread`'s first
positional slot. Probe P-E: `q = await asyncio.to_thread(sim.current_quote(ticker))` → guard
**GREEN**. That line genuinely blocks the event loop (the leaf executes inline) and then raises
`TypeError` in the worker, since a `Quote` is not callable. The exempted shape is **never
correct** — a *called* leaf handed to `to_thread` is always a bug — so the exemption is inverted:
it should be a flagged violation. **MINOR**, because laundered code of this shape is loudly broken
at runtime and cannot ship silently.

Probe P-F (assign a leaf to a local, then call the alias) also goes green — the documented
name-resolution blind spot. Grepped for live instances (`= sim.current_quote` and siblings):
**zero**. Recorded as a limitation, not a finding.

## Item #5 — the Alpaca gap

Bug confirmed live: `alpaca_service.py:77` `httpx.post` / `:113` `httpx.get`, reached from
`room_runner.py:1801` and `agent_runner.py:146` — identical class. Gated on
`urow.alpaca_access_token`, so it fires only for users who linked Alpaca — narrower blast radius
than the DEF116 sites, which fire on every convene.

The docstring's justification for excluding httpx was **measured, not trusted**: added
`httpx.<verb>` detection exactly the way `website_api`'s guard does (`f.value.id == "httpx"`),
traversal untouched → **85 offender chains, all bogus**, e.g.

```
auth.py:magic_link_verify -> httpx.post (via transfer_alias in revenuecat_client.py)
  (via execute in merge_service.py) (via get in mandate_store.py) (via get in session_store.py)
  (via _resolve_url in db/session.py) (via get_engine …) (via get_sessionmaker …) …
```

The claim holds — name-based traversal genuinely cannot carry httpx detection at this size.

D4 authorised two outs (leave it failing-but-excluded, or a documented narrowly-scoped waiver);
what shipped is a third — a guard structurally unable to see it, plus prose. The technical
reasoning is sound, but a **non-graph** check would cost ~10 lines: pin the inventory of
`httpx.<verb>(` call sites under `backend/app` so a *new* one anywhere turns red, no reachability
required. **MINOR.**

## Beyond the ask — the unmeasured merge, now measured

The hand-off lists "not rebased onto current `main` … expected is not measured." Trial-merged
current `main` (`e41569f` — two commits past the `b7ac8e9` the hand-off names) into the audited
SHA: **automatic merge clean, 0 conflicts**, guard green, **full suite 1339 passed** on the merged
tree. Merge aborted, worktree left clean. Integration is still the Architect's step; this removes
the unknown from it.

## Not verified

- **Acceptance #5 (melehost concurrency smoke)** — untestable from the Mac (pure editor). Remains
  a post-promote check, as the hand-off states.
- **No latency measurement** — nobody has timed a Room convene before/after, and I could not
  either. The fix's correctness does not depend on it, but the *benefit* is unquantified.

## Findings

1. **MAJOR** — the waiver prunes the entire subtree by bare function name, so a blocking call
   added inside a waived function is undetectable. Mutation-proved: a fresh `self.current_news(…)`
   in `SimEngine.submit`, reachable from `POST /sim/trade`, leaves the guard green. Separately the
   docstring's stated integrity property is measurably false for **7 of 9** waived names (name
   shadowing). Fix: scope the waiver to `(module, function)` and prune the edge only, or add an
   empty-waiver companion test pinning the offender-route set to exactly the 9 known DEF120 routes.
2. **MINOR** — `_to_thread_wrapped_call_ids` is inverted: `asyncio.to_thread(leaf(x))` both blocks
   the loop and `TypeError`s at runtime, yet is exempted (P-E → green). Flag the shape instead.
3. **MINOR** — the live Alpaca `httpx` pair is held by a comment. The stated reason for excluding
   httpx from the call-graph walk is independently confirmed true (85 bogus chains measured), but
   a non-graph inventory pin of `httpx.<verb>(` sites would cost ~10 lines.

## Verdict

**VERDICT: AWAITING_FIXES (round 2)** — one MAJOR, two MINOR.

The production fix is correct and I found nothing wrong with it: 5 call sites use the right
pattern, D2 holds structurally (zero `def` lines in the diff), CR090's kwargs are mutation-proved
intact, the Dockerfile change is clean with no override anywhere in the tree, 1333 green on the
lane and 1339 green on a clean trial merge with current `main`. Four independent probe shapes
confirm the guard is a genuine call-graph walker over the surface it does cover.

The MAJOR is entirely inside the guard — this lane's *required* deliverable under CLAUDE.md's
second-occurrence rule and acceptance #2, and the exact artifact the hand-off nominated as "where
the risk lives." Per `PROTOCOL.md` line 37, COMPLETE requires zero MAJOR. Round 2 should be small
and confined to the test file.
