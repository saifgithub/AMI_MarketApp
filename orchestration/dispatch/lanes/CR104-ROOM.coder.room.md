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

~~`STATUS: NOT_READY` (coder.room, superseded — see below)~~ — budget exhausted before the final
full-suite line was read; see gap list above.

---

## Architect addendum (track R, 2026-07-27) — the one declared gap is closed by measurement

The worker's `NOT_READY` rested on exactly one unread number, and it named the remedy itself:
*"read that file (or re-run the suite) and confirm 1368/1368 before treating the suite as green."*

**Done.** Full `backend/tests/unit/` from the repo root, absolute venv path, foreground,
`__pycache__` cleared first: **`1368 passed in 197.89s`**. `main`'s baseline is **1366**; +2 is
exactly the two new guard tests. Verified separately that no existing test was deleted (`def test_`
counts per changed file are identical to `main`).

**No production code was changed by the Architect.** The token below is Architect-issued on the
worker's behalf, on measured evidence, and the worker's original statement is preserved above rather
than rewritten. Independent verification, the Architect's own extra mutation, and one FINDING against
D4 that the Architect deliberately did **not** fix are all recorded in
`orchestration/audit/cr/CR104-ROOM.architect.md`.

~~`STATUS: READY_FOR_AUDIT (round 1)`~~ — superseded by round 2 below (audited AWAITING_FIXES,
two MAJOR). Neutralised so exactly one line in this file opens with the token (DEF121).

---

# Round 2 — both MAJORs closed

**Assembled by the Architect (track R) from two coder.room round-2 workers' output.** Read the
provenance note at the end before auditing: the code is the workers', the verification is the
Architect's, and **both workers died the same structural way.**

## MAJOR 1 — guard inverted to taint-following, deny-by-default (`cd349c5`)

`_PROTECTED_NUMERIC_FIELDS` (a 13-name allowlist) is gone as the primary mechanism. The guard now
flags **any** `profile[...]` assignment whose value is rng-tainted, regardless of field name,
following chained local assignments. The three narrative fields (`sentiment_tone`, `sentiment_score`,
`mention_trend`) are an explicit, justified **exclusion** list — a new field must now argue its way
in rather than being silently unprotected.

**Architect-verified against three mutations, each reverted after:**

| Mutation | Result |
|---|---|
| Auditor's 1B — single-hop laundering into a protected field: `_v = rng.uniform(12.0, 55.0)` → `profile["pe"] = f"{_v:.1f}"` | **RED** |
| Auditor's 1A — new field names outside any list: `profile["peg_ratio"]`, `profile["fcf_yield"]` from `rng` | **RED** |
| **Architect's own two-hop chain** (not asked for by the auditor): `_a = rng.uniform(...)` → `_b = _a` → `_c = f"{_b:.2f}"` → `profile["peg_ratio"] = _c` | **RED** |

The two-hop case matters: single-level taint following would have passed it, and the assign
explicitly warned *"do not settle for 'follows one level of indirection'."*

## MAJOR 2 — every `(LIVE)` label gated on `field_state` (`a2201ce`)

**Five** render sites labelled `(LIVE)` on a presence check without ever consulting `field_state` —
the four the auditor named plus analyst consensus:

| Site | Line |
|---|---|
| next earnings | `room_prompts.py:556` |
| valuation (4 independent parts) | `:613` |
| sector/industry | `:623` |
| dividend yield | `:632` |
| analyst consensus | `_analyst_line` |

All five now route through a single `_field_is_live(profile, key)` helper. Valuation gates each of
its four parts independently, so a part with no recorded provenance is dropped rather than carried
under the line's shared `(LIVE)` label.

**Architect acceptance render** — a profile with `field_state = {}` and every optional field
populated (`pe`, `base_price`, `price_to_sales`, `ev_to_ebitda`, `peg_ratio`, `fcf_yield`, `sector`,
`dividend_yield`, `analyst_target_price`, `analyst_rating`, `next_earnings_date`):

```
(LIVE)-labelled body lines: NONE
values leaked into the prompt: NONE
```

That is the exact probe the auditor used to prove MAJOR 2, now returning the opposite result.

## Suite

`./backend/.venv/bin/python -m pytest backend/tests/unit/ -q` from the repo root, absolute venv path,
**foreground, run to completion**, `__pycache__` cleared first: **`1373 passed in 193.25s`**.
Round 1 was **1368**; +5 is round 2's new tests.

## ⚠️ Provenance — read this before auditing

**Neither round-2 worker completed its own lane, and both failed identically.** Each backgrounded its
verification run and then emitted a final message, which ends the turn — so each died with work
uncommitted, having never read a test result. This is CR057 / `failure_patterns.md` **P7**. The
second worker was **explicitly instructed** not to do it, in its own launch prompt, and did it anyway.
That is CR038's finding reproduced exactly: *prompt instructions are not controls* (~30% compliance).
**A third relaunch was not attempted** — the failure is structural, not a worker defect, and is
flagged to Governance rather than papered over.

**What the Architect did:** reviewed the uncommitted work, found it correct, ran the acceptance render
and the full suite in the foreground, and committed it **unchanged**. The Architect wrote no
production code in round 2.

**What this means for the audit:** the code is the workers'; the verification claims above are the
Architect's own measurements, not repeated from a worker hand-off — neither worker produced one.
Grade the measurements as Architect-supplied, and re-derive them independently as usual.

## Not verified

- **Live behaviour on Alpha** — `main` is under an active promotion hold (`infra/PROMOTION_HOLD.md`);
  unit-level only.
- **The DEF123 corpus reading 0** — unchanged from round 1 and still an **open acceptance item**, not
  a satisfied one. Needs the fix on Alpha plus a re-run filtered to post-promotion prompts. Both the
  Architect and the round-1 auditor agree it cannot close from a coder lane.
- **Whether any `(LIVE)` string exists outside `room_prompts.py`** — the sweep covered that file.

STATUS: READY_FOR_AUDIT (round 2)
