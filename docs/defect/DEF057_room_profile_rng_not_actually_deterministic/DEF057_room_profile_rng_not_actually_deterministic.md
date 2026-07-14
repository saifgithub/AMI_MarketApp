# DEF057 — `_profile_for_ticker`'s "deterministic" rng wasn't actually deterministic across process restarts

**Status:** resolved · **Filed:** AT:R58 · **Fixed:** AT:R58 · **Date:** 2026-07-14
**Source:** track U's DEF056 audit (`audit/handshake/cr/DEF056.auditor.md`, observation
O2) — a pre-existing bug from the CR024 era, unrelated to DEF056 itself, surfaced as a
flaky test failure under a randomized default test-process hash seed.

## Problem

`room_runner.py::_profile_for_ticker()`'s own docstring promises: *"Builds a
deterministic synthetic baseline (so tests stay reproducible and Yahoo outages don't
break a run)."* The seed was:

```python
rng = random.Random(hash(ticker.upper()))
```

Python's builtin `hash()` for `str` is **randomized per process** (`PYTHONHASHSEED`)
unless explicitly pinned — a deliberate security property (defends against
hash-flooding DoS), not a bug in `hash()` itself, but wrong to rely on for reproducible
pseudo-randomness. So the function's actual behavior was: deterministic *within one
process* (every call in the same test run or the same server process sees the same
`hash("AAPL")`), but a **different synthetic profile on every process restart** —
directly contradicting its own docstring.

Surfaced as `test_room_runner.py::test_social_media_mention_trend_varies_by_ticker`
failing under a randomly-selected default `PYTHONHASHSEED` (all 6 tickers happened to
collide on the same `rng.choice` outcome for that seed) while passing reliably at
`PYTHONHASHSEED=0..5`. Not a production correctness bug (the profile's narrative
fields are explicitly synthetic/illustrative either way — no user-facing contract
depends on a *specific* per-ticker value persisting across restarts), but a genuine
test-flakiness bug and a real gap between the code's documented intent and its actual
behavior.

## Fix

`backend/app/services/room_runner.py`:

```python
rng = random.Random(zlib.crc32(ticker.upper().encode()))
```

`zlib.crc32` is a stable, non-randomized 32-bit hash — same ticker always produces the
same seed, in any process, forever. No new dependency (`zlib` is stdlib). Single call
site; no other code in the module seeds off `hash(ticker)`.

## Testing

- Adversarially confirmed the flaky test now passes under 9 different explicit
  `PYTHONHASHSEED` values (`0,1,2,3,4,5,42,1337,999999`) — previously seed-dependent,
  now seed-independent by construction.
- New `test_profile_for_ticker_rng_seed_is_hash_seed_independent`
  (`test_room_runner.py`) pins the exact expected `base_price`/`pe` for `"AAPL"` under
  the `crc32`-seeded implementation — a `hash()`-seeded implementation would need a
  specific `PYTHONHASHSEED` to reproduce these values by chance, so this test pins the
  fix rather than merely re-asserting same-process consistency (which would have
  passed before the fix too). Adversarially confirmed: reverted `room_runner.py` to
  the pre-fix `hash()`-based seeding (kept the new test), re-ran — **failed**
  (`assert 271.74 == 408.14`); restored the fix, re-ran — green.
- No hardcoded-exact-value test elsewhere in the suite depends on the old `hash()`-derived
  numbers — every existing `_profile_for_ticker` test either compares two calls for
  the same ticker (still equal under the new seed) or checks a field's shape/range,
  not a literal value.
- `pytest backend/tests/unit/ -q` → **742 passed** (741 → 742, +1).

## Acceptance

- [x] `_profile_for_ticker`'s rng seed is a stable function of the ticker string,
      independent of `PYTHONHASHSEED`.
- [x] The previously-flaky test passes deterministically across multiple explicit
      hash seeds.
- [x] A new regression test pins the fix against reversion, adversarially confirmed
      to fail on the pre-fix code.
- [x] No existing test broke — the change doesn't affect any test's exact-value
      assertions (none existed for the old seed's outputs).
