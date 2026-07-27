<!-- dispatch hand-off — coder.room, CR104-ROOM, round 1 -->
# CR104-ROOM — hand-off (coder.room round 1)

Worktree: `.claude/worktrees/coder.room-CR104`, branch `lane/CR104-ROOM.coder.room`, off `main` @ `64033cc`.

## What's done, per D5 order, each its own commit

1. `c1f0693` + `54cd623` — deleted the rng baseline from `_profile_for_ticker`;
   moved it to `backend/tests/unit/fixtures/synthetic_room_baseline.py`
   (nothing under `app/` imports it). Numeric fields
   (base_price/pe/rev_growth/profit_margin/net_cash/rsi/trend/support/
   breakout/low/high/volume_tone) are LIVE-or-absent, tracked per-field in
   `profile["field_state"]`. 52-week range decoupled from technicals
   support/breakout (independent sources, previously rendered on one line).
   `_TEMPLATES` scripted-demo fallback (no real LLM reachable) degrades
   loudly instead of crashing on an absent field.
2. `d3d3d84` — `_format_profile` renders a numeric field ONLY when
   `field_state` says "live" (D4 renderer refusal). CR098's three block
   flags (`technicals_state`/`news_state`/`social_state`) migrated onto
   `field_state["technicals"|"news"|"social"]` and deleted (D1). Every test
   that hand-built a profile dict with the old keys updated.
3. `520ef91` — structural AST guard,
   `test_cr104_no_fabricated_numeric_reaches_room_prompt.py`. Walks
   `_profile_for_ticker`'s AST; fails if a protected numeric field is a key
   in the unconditional baseline dict OR assigned anywhere from an
   rng-referencing expression. **Demonstrated failing**: reintroduced
   `"pe": f"{rng.uniform(12,55):.1f}"` into the baseline dict —
   ```
   AssertionError: DEF123 regression: a numeric fact that must be
   LIVE-or-absent is present as a key in _profile_for_ticker's
   unconditional baseline dict ...
   assert not {'pe'}
   ```
   reverted, green again. (First version of the guard picked the wrong dict
   — `field_state: dict[str,str] = {}`, an unrelated empty literal earlier
   in source — and passed silently on the same mutation; fixed to match by
   assignment-target name, then re-proved red/green. That failure is worth
   knowing about if you're reviewing AST-guard shape generally.)
4. `8b4fc94` — `backend/scripts/def123_corpus_check.py`, a re-runnable
   acceptance harness (re-derives the exact pre-fix synthetic P/E draw,
   counts LIVE-declared Room fundamentals prompts whose rendered P/E
   matches it). Re-run against the same 60-day melehost `llm_audit` window:
   reproduces DEF123's original numbers exactly (895 total, 842 declared
   LIVE, 178 fabricated, 36 tickers) — **this is historical, pre-fix data**;
   those rows were served before the fix exists and cannot retroactively
   read 0. `failure_patterns.md` P2 updated with a DEF123 entry naming the
   CR104 guard as its enforcing check.
5. `b1e4983` — `CR104.row.md` (proposed→started) and `DEF123.row.md`
   (open→fixed, closed-by-CR104 note), `gen cr` + `gen def` + `verify all`
   (DEF 126 rows / CR 100 rows, content identical to live).

## Verified

- Every individual test file touched, run separately, green: `test_room_runner.py`
  88 passed; `test_cr098_room_analyst_pullback.py` 25 passed;
  `test_cr090_room_live_data_surcharge.py` 12 passed;
  `test_room_prompts.py` + `test_prompt_data_parity.py` 35 passed;
  `test_cr104_no_fabricated_numeric_reaches_room_prompt.py` 2 passed.
- Full `backend/tests/unit/` suite from repo root, absolute venv path,
  foreground, run **twice**: once at the step-2 commit point — **1366
  passed** (matches `main`'s baseline, re-measured from this worktree, not
  trusted from the assign) — and once more after the guard test was added.
  **The second full run had reached ~65% with zero failures (all dots) when
  this hand-off was written — I did not wait for it to finish or read its
  final line.** Output file:
  `/private/tmp/claude-501/-Volumes-Extreme-Pro-AMI-MarketApp/3b3d0178-bc45-4584-a1c3-a02d6a07926a/tasks/bqeom2ea2.output`
  on the machine this session ran on. Expected final count is 1368 (1366 +
  the 2 new guard tests) based on every constituent file having passed
  individually and the run showing no red before I stopped watching it —
  but I have not read the actual final number, so I am not stating it as
  measured. **Whoever picks this up: read that file (or re-run the suite)
  and confirm 1368/1368 before treating the suite as green.**
- `__pycache__` cleared before each mutation-test measurement (external
  volume, coarse mtime — per the assign's warning).

## Not verified (explicit gap list)

- **The final line of the second full-suite run** — see above. High
  confidence, not measured.
- **DEF123's corpus count reading 0** — cannot be true yet. It requires the
  fix to reach Alpha (`/promote-to-alpha`, a separate Saiful-gated step
  outside a coder lane's scope) and a re-run of
  `backend/scripts/def123_corpus_check.py` filtered to prompts generated
  after that promotion timestamp. Flagging this explicitly rather than
  fudging the acceptance check.
- **Live smoke** (convene BBAI on Alpha, confirm no fabricated P/E) —
  same reason, needs promotion first.
- I did not attempt CR037/CR038's undecided guards — see FLAG 3 below.

## FLAGS (raising, not deciding — per the assign)

1. **Outage behaviour is now visibly thinner and the mobile client has no
   "intentionally thin" rendering.** A Yahoo outage today produces `P/E:
   not available` / `Market technicals: not available this call.` lines
   instead of a fabricated number — correct (CR040), but a client that
   doesn't distinguish "field genuinely absent" from "field withheld for a
   paid/tenure reason" will render both identically. CR090-MOBILE already
   has withheld-vs-unavailable CTAs for news/social; fundamentals/technicals
   have no equivalent yet.
2. **Degradation is uneven by ticker class**, confirmed by the corpus
   measurement: loss-making names (AMC, BBAI, MARA, RIVN, ...) lose the P/E
   line every convene (yfinance has no `trailingPE` for a negative-earnings
   company — the ratio is mathematically undefined, not a fetch failure);
   ETFs (SCHD, VGK) lose the entire company-fundamentals block, which is
   correct (a fund has no P/E/growth/margin/net-cash) but was previously
   invisible because the block always rendered *something*.
3. **The corpus harness (`def123_corpus_check.py`) is reusable for
   CR037/CR038's undecided guards** in shape (query `llm_audit`, compare a
   rendered value against a known-fabricated-value function, count) but
   NOT as-is — CR037/CR038 are about sentiment/macro text assertions, not a
   numeric match. Someone would need to write a different detector
   function; the SQL extraction pattern and the "re-run against a
   post-promotion window" caveat both carry over. I did not build this —
   flagging per the assign, not taking it on.

## Not done — budget

Ran low on budget (~$1.7 of $15 left) while the confirmatory full-suite run
was still in flight. Per the assign's own instruction ("if you run low on
budget, do NOT emit the READY_FOR_AUDIT token — write an honest gap list
instead"), I'm stopping here rather than emitting the token on an unread
final test count. Everything else in the assign's acceptance list is done
and committed; the only open item is reading one number.

STATUS: NOT_READY — budget exhausted before the final full-suite line was read; see gap list above
