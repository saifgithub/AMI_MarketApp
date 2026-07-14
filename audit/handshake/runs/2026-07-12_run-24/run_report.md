<!--
Auditor run report — run-24 (2026-07-12, session AT:U1). Round-1 audit of DEF057
(_profile_for_ticker rng seed made hash-seed-independent via zlib.crc32). Minted from
my DEF056 audit O2. Fixed in b0c85a2. Verdict COMPLETE. Owner: AUDITOR.
-->

# run-24 (round 1) — DEF057 (deterministic profile rng seed) → COMPLETE

- **Auditor session:** AT:U1 (track U), 2026-07-12
- **Audited SHA:** `b0c85a2`. `git diff b0c85a2..HEAD -- backend/` empty → main checkout
  == committed fix. Full suite → **742 passed** (fixed `PYTHONHASHSEED=0`).
- **Provenance:** minted by the architect from **my own DEF056 audit observation O2**
  (the flaky `test_social_media_mention_trend_varies_by_ticker`) — loop closed.
- **Verdict:** COMPLETE — zero BLOCKER/MAJOR.

---

## DEF057 — profile rng seed made deterministic (`b0c85a2`) → COMPLETE

**The bug:** `_profile_for_ticker`'s docstring promises a "deterministic synthetic
baseline," but it seeded `random.Random(hash(ticker.upper()))`. `str.__hash__` is
randomized per process under `PYTHONHASHSEED`, so the same ticker produced a different
synthetic profile on every restart — contradicting the docstring, and surfacing as the
flaky test I flagged in DEF056 O2.

**The fix (verified):** one line — `hash(ticker.upper())` →
`zlib.crc32(ticker.upper().encode())`. `crc32` is a stable, non-randomized CRC;
`zlib` is stdlib. Single call site (my grep confirms no other `hash(ticker)` seeding).

**Why it's correct — proven, not trusted:**
- **Determinism**: `_profile_for_ticker("AAPL")` → `base_price=408.14, pe=53.3`
  **identical across `PYTHONHASHSEED` = 0/1/42/1337/999999**. The docstring's promise
  now holds.
- **The bug was real** (revert evidence): the old `hash()`-seeded base_price for AAPL
  is 346.23 / 207.76 / 424.52 at seeds 0/1/42 — varies per process, none is 408.14. So
  the new pin-test (which asserts 408.14) would fail on the pre-fix code — non-vacuous.
- **Flaky test fixed**: `test_social_media_mention_trend_varies_by_ticker` passes at
  every tested seed (0, 42, 1337, 999999, 7).
- **No regression**: 742 passed; no existing `_profile_for_ticker` test asserted an
  exact value tied to the old seed.

**Register:** `def_list.md` DEF057 = `resolved`.

**Live:** backend-only, no user-facing behavior change (fields already disclosed as
illustrative); not yet promoted, no urgency.

---

## Verdicts

| Item | SHA | Verdict |
|---|---|---|
| DEF057 | `b0c85a2` | **COMPLETE (round 1)** — `zlib.crc32` seed makes the profile deterministic across processes (proven: base_price 408.14 identical across 5 seeds; old hash() varied); flaky + pin tests pass all seeds; 742, no regression. Closes my DEF056 O2. |

No OUT-OF-SCOPE findings (this lane resolves my prior O2).
