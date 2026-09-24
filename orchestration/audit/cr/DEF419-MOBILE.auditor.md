<!--
DEF419-MOBILE.auditor.md — audit lane verdicts. Auditor-owned; the architect never writes here.
Newest round at the bottom. State derives from round numbers here vs DEF419-MOBILE.architect.md.
-->

# DEF419-MOBILE — auditor verdicts (per-account mandate check, mobile half)

## Round 1 — auditor u66

**SHA audited:** `f2bc07b9`, in a detached scratch worktree `DEF419-MOBILE-u66` per DEF159.
Worktree verified clean after every probe was removed.

**Tier A** — it decides which account's snapshot reaches the safety floor.

**Lane dependency:** DEF419-BE was audited this same session and is **AWAITING_FIXES** with
two MAJOR findings (open risk left on the AMI denominator; the drawdown rule silently inert on
the snapshot path). Neither is caused by this half, and neither is fixable here — but this
half's whole purpose is to feed that path, so its promotion is gated behind the backend's
round 2 regardless of this verdict.

### MAJOR-1 — `.take()` before `.where()` silently drops real long positions

`models/alpaca.dart:152-169`, `toMandateSnapshotJson()`:

```dart
final sorted = [...positions]
  ..sort((a, b) => b.marketValue.abs().compareTo(a.marketValue.abs()));
...
  'positions': sorted
      .take(maxPositions)        // <-- truncate FIRST
      .where((p) => p.qty >= 0)  // <-- filter shorts AFTER
```

The sort key is `marketValue.abs()`, so **shorts sort as if they were large longs**, consume
slots inside the 100-position cap, and are then discarded — taking real long positions out of
the snapshot with them.

Driven, with the fixture size asserted so a failed setup can't be mistaken for a result:

```
PROBE: 120 positions in (100 short + 20 long), snapshot sent 0 positions
```

120 positions in, **zero out**. The mandate check then sizes single-name and sector caps
against an account it believes holds nothing, while the real account holds $100k of longs.
Under-reported exposure on the safety-floor path — the same defect family as DEF419 itself.

Severity is bounded and I measured the boundary rather than asserting it:

```
PROBE modest book: 8 in (3 short, 5 long) -> 5 sent
PROBE: under the cap the ordering bug does not bite
```

Below 100 positions the ordering is harmless. At or above the cap **with shorts present**,
longs are dropped silently, up to all of them. A 100+ position paper account is unusual but
entirely reachable, and nothing surfaces when it happens.

Fix is a one-line reorder (`.where(...)` before `.take(...)`). The cap then counts only
positions that will actually be sent.

### MAJOR-2 — `toMandateSnapshotJson()` has no test at all

The one serializer that feeds the mandate floor is untested. The cap test that exists covers
the **other** method:

```
test/services/alpaca/alpaca_snapshot_wire_test.dart:107
  expect(positions.length, AlpacaSnapshot.maxPositions);   // toWireJson(), not the mandate shape
```

`grep -rn 'toMandateSnapshotJson' test/` returns **nothing**. So the cap, the short filter and
the ordering above are all unguarded — which is why MAJOR-1 shipped. House rule: *an entry
without an enforcing check is not done.*

The 6 new `def419_per_account_test.dart` cases are good widget-level tests of the ticket's
behaviour, but they all drive small fixtures, so none reaches the serializer's edges.

### MINOR-1 — the "concurrent-fetch fix" does not do what the submission says

Attack surface 2 asks me to verify the `Completer` rewrite "isn't just quieted in the test
harness specifically." It is neither: the scenario it guards **cannot occur**, and the
sharing it was meant to remove is still there.

```dart
final inFlight = _alpacaSnapshotFetch;
if (inFlight != null) return inFlight;   // still hands ONE future to every caller
final completer = Completer<AlpacaSnapshot>.sync();
_alpacaSnapshotFetch = completer.future;
```

One `Completer`, one `future`, returned to all callers — structurally the same as returning
the shared in-flight `Future`. And there are only two call sites (`:742` `_submitAlpacaOnly`,
`:889` `_legAlpaca`) which sit on **mutually exclusive destination paths**; `_submitBoth`
fetches exactly once, through `_legAlpaca` alone. Two concurrent listeners never arise.

Harmless as written, and the `onError` branch correctly clears the cache so a failure isn't
replayed. But it is defensive scaffolding for an impossible case, described as a bug fix.
Worth correcting in the record so a future reader doesn't rely on a guarantee that isn't there.

### MINOR-2 — the 30s cache TTL (attack surface 1), noted not blocking

Judged as asked: 30s is acceptable here. The account is paper-only under D-071, the snapshot
is re-fetched per ticket session, and `onError` clears it. A staler snapshot can only mis-size
a simulated order. I would not spend a round on this.

### What I verified and found sound

- **Attack surface 3 — no AMI fallback, confirmed on both paths.** `_submitAlpacaOnly`
  (`:741-754`) and `_legAlpaca` (`:887-896`) both `catch` → set the outcome → **`return`**.
  No `preview()`, no `submit()`, nothing reached after a caught fetch failure. Both also
  return without placing when `preview == null` (AMI unreachable) rather than proceeding —
  correct per DEF059. The message is explicit: *"Couldn't read your Alpaca paper account —
  order not sent."*
- **Attack surface 4 — the legs are genuinely independent.** `_legAmi` and `_legAlpaca` each
  return their own `_DestinationOutcome` value; neither reads `state.lastSubmit` or any shared
  mutable flag before deciding to proceed. `_submitBoth` only reads `lastSubmit` **after**
  `Future.wait` resolves, and only for advisories. The builder's own test proves the
  behaviour: on an Alpaca fetch failure the AMI leg still places (`submitCalls == 1`,
  `previewCalls` empty).
- **Attack surface 5 — no accidental suppression.** `_destinationOutcomes` is cleared to
  `const []` at submit start (`:613`) and populated only on the Alpaca-only (`:745/765/782`)
  and BOTH (`:824`) paths. On a plain AMI Sim submit it stays empty, so the legacy `refusal`
  panel (`:1156`) still renders. Correct.
- **Attack surface 6, the short question itself.** Shorts are dropped client-side, which
  matches the backend bound I verified in DEF419-BE (`AccountPositionIn.qty ge=0` → 422 on a
  negative). So a short cannot reach the floor by either route. The documented limitation
  stands as documented; MAJOR-1 above is a *different* bug that the filter's placement causes,
  not the filter's existence.
- **Attack surface 7 — no crossed wires.** `toWireJson()` is called only from
  `room_providers.dart:213` and `one_on_one_providers.dart:85` (the Room-overlay
  `AlpacaSnapshotIn` shape); `toMandateSnapshotJson()` only from the two ticket sites. No
  call site points at the wrong serializer.

### Evidence, run bare in the pinned worktree

```
cd mobile && flutter test
01:06 +1505: All tests passed!        EXIT=0

cd mobile && flutter analyze
11 issues found. (ran in 6.5s)        EXIT=1, 0 errors
```

Both match the submission exactly (1505 / 11 / 0 errors). `analyze`'s exit 1 is its
nonzero-on-any-issue behaviour against the stated unchanged baseline.

### Verdict

The wiring this half exists to do is right, and the parts that matter most for safety are
right: the fetch-failure path never substitutes AMI's book, the BOTH legs are genuinely
decoupled, and the refusal panel still renders where it must. I attacked each of those
directly.

But the serializer that feeds the safety floor drops real positions at the cap boundary and
has no test of its own. Both are one round's work.

VERDICT: AWAITING_FIXES (round 1)
