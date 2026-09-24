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

---

## Round 2 — auditor u66

**SHA audited:** `a51ea92d`, in a detached scratch worktree `DEF419MOB-r2-u66` per DEF159 — the
same commit as DEF419-BE round 2, both halves landed together. Worktree verified clean after
every probe and mutation was reverted.

All four round-1 items are resolved. Verified by re-running my own round-1 probes and my own
mutations, not from the submission's transcript.

### MAJOR-1 — fixed

`toMandateSnapshotJson()` is now filter → sort → take (`alpaca.dart:163-180`), so the cap counts
only positions that will actually be sent. My round-1 probe, re-run verbatim with the fixture
size asserted:

```
PROBE: 120 in (100 short + 20 long) -> 20 sent
PROBE: round-1 MAJOR-1 is fixed — all 20 longs present
```

20 sent where round 1 sent **0**, every one a real long. Two edges I added this round also hold:

```
PROBE short-only book -> 0 sent (expect 0)        # empty, not wrong
PROBE 150 longs -> 100 sent, largest=149.0, smallest=50.0   # cap keeps the largest
```

### MAJOR-2 — fixed, and the new guard is load-bearing

`toMandateSnapshotJson()` now has its own test group. I checked it does real work by mutating
the method back to round 1's cap-then-filter order:

```
Expected: <20>
  Actual: <0>
00:00 +13 -1: Some tests failed.
```

It reproduces my round-1 finding exactly and fails on it. That is the guard that would have
stopped MAJOR-1 shipping.

### MINOR-1 — fixed, and the claim corrected rather than defended

`_fetchAlpacaSnapshot` is now a plain `async`/`await` over the TTL cache; the `Completer`
fan-out and `_alpacaSnapshotFetch` are gone, and the docstring records the finding instead of
repeating the round-1 claim. That is the right resolution — the guarded scenario could not
occur, so removing it is better than keeping defensive scaffolding that reads as a guarantee.

One behaviour I checked rather than assumed: the old `onError` branch cleared the cache on
failure, and the new code has no such branch. It does not need one — the cache is written
**only** on success (`:723-724`) and every read is TTL-gated (`:709-713`), so a failed fetch
leaves behind only data that was itself successfully fetched inside the last 30s. No stale-cache
path opens up.

The legs remain structurally independent: `_legAmi` never calls `_fetchAlpacaSnapshot` at all,
which is what actually guarantees the round-1 property, and the
`BOTH: an unreadable Alpaca account still lets the AMI leg place independently` test still
passes.

### MINOR-2 (30s TTL) — unchanged, as agreed

### The disclosure reaches the user — verified at every hop

This was the open question I carried over from DEF419-BE round 2: a disclosure that stops at the
response model is the same defect one layer out. It does not stop there.

`UnmeasuredRule` (`sim.dart:860-870`) parses both `rule` and `reason`; `_unmeasuredRulesNote`
(`trade_ticket_sheet.dart:71-75`) renders a localized line on the accepted-outcome paths. I
silenced the renderer:

```
Expected: exactly one matching candidate
  Actual: Found 0 widgets with text containing "Not checked for this"
00:01 +10 -1: Some tests failed.
```

A widget test asserts the rendered text, so the chain is closed end to end — backend computes,
wire carries, model parses, **UI renders** — with a guard at the last hop.

Two judgement calls I looked at and agree with:

- **Only the rule NAMES are rendered, not the backend's `reason` prose.** A trade ticket is not
  the place for two sentences. The `reason` is parsed onto the model and available for a later
  surface (tooltip, tap-to-expand) with no further backend round. Sound layering, not a gap.
- **The disclosure renders only on an ACCEPTED outcome**, never beside a violation — correct, a
  rejected trade's reason is the violation, and adding "also, two rules weren't checked" there
  would muddy it. The negative test for this exists.

### Carried, not re-charged — the i18n guard failure

`tradeTicketUnmeasuredRulesNote` is hand-copied English in `app_ar.arb` / `app_ms.arb` and fails
DEF295's guard. **Already charged as MINOR-2 on DEF419-BE round 2** (same commit, `a51ea92d`);
recorded here for completeness rather than counted twice.

One correction to this submission's stated reasoning, because it would mislead the next reader:

> *"added to `app_ar.arb`/`app_ms.arb` with the English string as placeholder, matching how every
> other not-yet-translated key in those files reads"*

Measured, that is not how the others read. DEF295's mechanism is an `@@x-ami-seeds` map holding
`key → sha256[:12]` of each seeded value:

```
app_ar.arb: @@x-ami-seeds holds 825 entries — tradeTicketUnmeasuredRulesNote present? False
app_ms.arb: @@x-ami-seeds holds 841 entries — tradeTicketUnmeasuredRulesNote present? False
```

Every other untranslated key **is** registered there; this one alone is not, which is exactly
the state DEF295 exists to catch ("skipped by the translator forever ... the key is present, the
parity guard is green, and the Arabic screen renders English"). `l10n_key_parity_test.dart`
passing does not cover it — that is DEF137's guard, and DEF295's whole filing was that DEF137's
guard is satisfied by the very hand-copy it cannot see. `--seed-missing` is the one supported
route.

### Evidence, run bare in the pinned worktree

```
cd mobile && flutter test test/screens/sim/def419_per_account_test.dart \
                         test/services/alpaca/alpaca_snapshot_wire_test.dart \
                         test/l10n_key_parity_test.dart
00:02 +38: All tests passed!          EXIT=0

cd mobile && flutter analyze
11 issues found. (ran in 8.6s)        EXIT=1, 0 errors — baseline exactly
```

The analyze count confirms their `use_build_context_synchronously` fix held: resolving
`AppLocalizations` in `_submitBoth` before either leg's `await` and passing it in, rather than
reading `context` inside a helper with no `mounted` check, is the right shape.

Full mobile suite, pinned worktree, run bare:

```
cd mobile && flutter test
01:28 +1516: All tests passed!        EXIT=0
```

Matches the submission exactly. 1516 = round 1's 1505 plus this round's 6 serializer tests and
the disclosure/rendering cases.

### Verdict

Both MAJORs are properly fixed: the serializer sends real longs again, and the test that would
have caught the original defect now exists and fails on it. MINOR-1 was resolved by removing the
machinery and correcting the claim rather than defending it, which is the harder and better
choice. And the disclosure this round wired up is verifiable at every hop to the user's screen.

The i18n seeding is owed before this ships — it is one command, and it is charged on the backend
half of the same commit rather than twice.

VERDICT: COMPLETE (round 2)
