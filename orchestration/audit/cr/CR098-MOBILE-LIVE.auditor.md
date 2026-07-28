<!--
CR098-MOBILE-LIVE.auditor.md — auditor lane file (track U owns). State derives
from round numbers here vs CR098-MOBILE-LIVE.architect.md (see PROTOCOL.md).
-->

# CR098-MOBILE-LIVE — audit lane (auditor)

**Item:** the client-side locked-chair / roster-countdown surface for `agent_withheld` (tenure
roster pull-back), plus `withheld_tenure` on the CR090 live-data-notice card.

**Gate:** independent — it renders a paywall-adjacent disclosure, and CR098 has two withhold reasons
with **opposite** remedies (`withheld_paid` → credits, `withheld_tenure` → plan upgrade). Pointing
the tenure state at the credits CTA would be a live DEF059 inversion.

**Audited SHA:** `dca1051` on `lane/CR098-MOBILE-LIVE.coder.mobile`, merge-base `ce6d55e`. Isolated
worktree `.claude/worktrees/audit-CR098-LIVE/`, created detached at that SHA.

## Round 1

### Reproduced independently

| Check | Lane claimed | I measured |
|---|---|---|
| Scope | 11 files, +707/−12 | **11 files, +707/−12** ✅ |
| `flutter test test/services/ test/widgets/` | 86/86 | **86/86** ✅ |
| **Full** `flutter test` | 122/122 | **122/122** ✅ |
| `flutter analyze --no-fatal-infos`, 5 touched non-generated files | 0 issues | **No issues found** ✅ |
| New user-visible strings needing `ar`/`ms` | 4 | **4**, enumerated below ✅ |

### The Architect's three mutations, re-derived — plus two of my own

Each applied physically, verified present in source, reverted; `dirty(lib)=0` at the end and the
86 baseline restored.

| | Mutation | Result |
|---|---|---|
| **M1** | rename the `agent_withheld` case in `api_client.dart` — kills the **real** wire parse | **RED** (2) |
| **M2** | rename the `agent_withheld` case in `room_providers.dart` — kills the **state** half | **RED** (2) |
| **M3** | `if (_anyTenure)` → `if (false)` — removes tenure's own CTA, leaving only credits. **The DEF059 inversion this gate exists for** | **RED** (1) |
| **M4** ᵐⁱⁿᵉ | drop the `order` mirroring so the chair never gets a seat | **RED** (1) |
| **M5** ᵐⁱⁿᵉ | null out `nextStepDays` so the countdown silently disappears | **RED** (1) |

All five red, all three of the Architect's counts matching exactly. **The inversion is held by a
test, not a comment** — that is the bar and the lane clears it.

---

## MAJOR — an ordinary dropped connection erases the locked chair, silently

This is the surface the Architect flagged as un-probed, and it does not need a malformed payload to
fire. **It needs the phone to sleep.**

`room_screen.dart:115` renders chairs by iterating **`state.order` only**:

```dart
for (final agentId in state.order)
  if (state.withheldAgents[agentId] != null) _WithheldAgentChair(...) else _AgentLine(...)
```

`_recoverViaPolling` — the path taken on "phone sleep, network loss, etc.", by its own comment —
rebuilds `order` from `snap.transcript` alone, and a locked chair is **deliberately never in the
transcript** (`room_providers.dart`: "Never in transcript — a locked chair has no streamed text").
`RoomRunSnapshot` carries no withhold field at all, so recovery cannot restore it even in principle.

Measured, not read — same scripted-notifier harness the lane uses, plus a stream that throws:

```
A0  stream ends NORMALLY  order=[market_analyst, news_analyst]      RENDERS_CHAIR=true   done=false
A1  stream BREAKS         order=[news_analyst, pm]                  RENDERS_CHAIR=false  done=true
                          withheld=[market_analyst]  err=null
```

`withheldAgents` still holds the analyst. Nothing iterates it. The run completes, `done=true`,
**`error=null`** — the user is shown a finished Room with one analyst missing, no locked chair, no
countdown, no upgrade path, and no indication anything was withheld.

**Why MAJOR and not MINOR.** It is fail-**open**: the disclosure disappears and the user is told
nothing, so they end up believing they received the full roster. That is this project's DEF059 class
— the lane's own stated gate rationale is "a disclosure that points at the wrong remedy"; a
disclosure that silently evaporates is the same family, and CR098's entire reason to exist is that
the user should learn an analyst is off their roster. The trigger is not contrived: `_recoverViaPolling`
was written **because** mobile streams break mid-run, and a Room run is minutes long.

**CR090's sibling disclosure on the same screen does it correctly**, which is what makes this a
lane-level defect rather than a design limit: `liveDataNotice` is untouched by the recovery
`copyWith` and renders from `state.liveDataNotice` directly, independent of `order`. It survives.
CR098's chair does not, purely because it was routed through `order`.

**Fix prototyped and MEASURED — do not re-derive it.** Re-seat the withheld chairs when recovery
rebuilds the order, in `_recoverViaPolling`:

```dart
for (final id in state.withheldAgents.keys) {
  if (!order.contains(id)) order.insert(0, id);
}
```

Measured with that patch applied: **A1 → `order=[market_analyst, news_analyst, pm]`,
`RENDERS_CHAIR=true`**, chair re-seated at the top exactly as D4 asks, and the **full suite 130
passed** (122 lane + 8 probes) — **zero regressions, zero false positives**. Reverted after; tree
clean. A widget-level test that drives a break-then-recover stream and asserts the chair is still
rendered is what closes this, and it belongs next to the existing `agent_withheld` tests.

---

## MINOR — every field of the payload is hard-cast, and one bad event kills the run

`room_providers.dart` casts three ways with no shape check:

```dart
final withheldAgentId = ev['agent_id'] as String;      // throws on absent / non-String
reason: (ev['reason'] as String?) ?? 'upgrade',        // null-safe; throws on non-String
nextStepDays: ev['next_step_days'] as int?,            // throws on String or double
```

`parseRoomSseEvent` has a `try/catch → return null` that swallows malformed events, but the
`agent_withheld` case performs **no casts inside it** — it passes raw `dynamic` straight through, so
the throw happens later, in the notifier's `await for`, where the generic catch reads it as a broken
socket and diverts to polling recovery.

| Probe | Result |
|---|---|
| **B1** `agent_id` absent | throws → recovery, `withheld=[]`, `done=true`, `err=null` |
| **B2** `next_step_days` is `"4"` | same |
| **B3** `next_step_days` is `4.0` | same |
| **B4** `reason` absent | **handled** — `?? 'upgrade'` |
| **B5** `reason` is `7` | throws → recovery |
| **B6** `agent_id` is `7` | throws → recovery |

**MINOR, not MAJOR, because there is no live instance** — I checked the only producer rather than
assuming: `agent_id` is `AgentId.value` (always a str, and the emit site always sets it), `reason` is
the literal `"upgrade"`, and `next_step_days` is `threshold - account_age_days` where both operands
are pydantic-validated `int`. Nothing in `backend/app/` can emit these shapes today.

Worth fixing anyway, cheaply, because the **consequence is identical to the MAJOR** — silent loss of
the disclosure, reported to the user as nothing at all — and one shared fix covers both:
`as String?` + skip, and `(ev['next_step_days'] as num?)?.toInt()`.

---

## Recorded, not scored

- **The lane's notifier tests win a race they don't know they're in.** `roomNotifierProvider` is
  `.autoDispose` **and** self-starting (`Future.microtask(n.start)`), and `start()` returns
  immediately when `state.streaming` is already true. A test that reads `.notifier`, awaits
  `start()`, then re-reads the provider is relying on the element not being disposed between the two
  reads. It holds today (122/122, repeatedly) because the scripted stream is a synchronous iterable.
  It stopped holding the moment I gave the stream real async work — my first A1 attempt read back an
  empty state and I nearly wrote it up as the finding. **It is my own harness bug, not the lane's**,
  and I am recording it so the next probe of this surface holds a `container.listen` from the start.
  The pattern pre-dates this lane and I am not asking for a change to it.
- **Chair ordering is correct.** The mirror appends (`[...state.order, id]`) rather than inserting at
  the front, but every `agent_withheld` arrives before any analyst speaks, so `order` is empty at that
  point. Measured in A0: `order=[market_analyst, news_analyst]` — chair first, in seat, as D4 asks.
- **`withheld_paid` vs `withheld_tenure` read distinctly before you read them** — separate accent
  colour, separate copy, separate CTA. M3 confirms the CTA split is load-bearing.

## Translation flag — 4 strings, `ar` + `ms`

Per the standing content-change rule, recorded here so it does not evaporate. The generated `ar`/`ms`
files currently carry **English** text for all four:

- `roomLiveDataFeedTenure`
- `roomLiveDataTenureUpgradeCta`
- `roomAgentWithheldChairLabel`
- `roomAgentWithheldRosterNote` (has an `int` plural — needs plural forms per locale, not a
  string swap)

## Not verified

- **Anything on a device or against melehost.** Promotion hold; nobody has seen this render on a
  phone. Unit + widget level only, same as the lane discloses.
- **The worker's CR104 thin-fundamentals conclusion.** A code-read conclusion about backend
  behaviour; the Architect did not re-trace it and neither did I. The decision *not* to build a
  client-side heuristic off agent prose is correct per CR038 and I endorse it — but the underlying
  claim is unmeasured by all three of us.
- **Whether the `next_step` countdown is semantically right** — that it names the roster's nearest
  upcoming pull-back and never reads as "this analyst returns" is a copy judgement, and the string
  is written correctly. Whether users read it that way is not measurable here.

**BLOCKER 0 · MAJOR 1 · MINOR 1**

**VERDICT: AWAITING_FIXES (round 1)** — the lane's own acceptance is genuinely met and mutation-proved:
the wire parse, the state half, the seat mirroring, the countdown and the DEF059 CTA split are each
held by a test that goes red when broken, and the Architect's three counts reproduce exactly. What
bounces it is one hop outside what anyone tested: the disclosure this lane exists to render is
**erased by the app's own reconnect path**, on the most ordinary mobile failure there is, with no
error surfaced. The fix is four lines in `_recoverViaPolling`, prototyped and measured here at 130
passed with zero regressions, and CR090's disclosure on the same screen already survives the same
path — so this is a lane defect, not a design limit. Run report `runs/2026-07-28_run-77/`.

---

## Round 2

**Audited SHA:** `44dcc0f` on `lane/CR098-MOBILE-LIVE.coder.mobile`, fresh detached worktree.
Round-2 scope: **2 files, +287/−4** (`room_providers.dart`, `room_agent_withheld_test.dart`) —
confirmed by `git diff --stat dca1051 44dcc0f`.

### Round-1 MAJOR — FIXED, measured independently

Full suite **128/128** reproduced (lane claimed 128; round 1 was 122, +6 = 2 recovery + 4
malformed). `flutter analyze --no-fatal-infos` on both touched files: No issues found (the 5
full-tree infos are pre-existing, in unrelated test files).

Mutations re-derived, each applied physically and reverted:

| | Mutation | Result |
|---|---|---|
| **M-A** | remove the re-seat (`order.insertAll(0, chairs)`) | **RED — exactly the 2 new recovery tests** |
| **M-B** | restore the hard casts | **RED — exactly the 4 new malformed tests** |

Tree clean after reverts (`git status --porcelain` empty), **128** restored.

### The `insertAll` deviation — validated, and better than my prototype

The Architect replaced my per-key `insert(0)` with `insertAll(0, chairs)` on the argument that
per-key insertion reverses relative order for two or more withheld chairs. My own probe (P1,
real notifier, break-then-recover, two withholds): recovery seats
`[market_analyst, fundamentals_analyst, news_analyst]` — **arrival order preserved**, where
per-key `insert(0)` would have produced `[fundamentals_analyst, market_analyst, …]`. The
deviation is correct and the reasoning in the bridge is accurate. Not gold-plating: the
two-chair case is one roster change away.

### Round-1 MINOR — FIXED, and the Architect's correction of my shorthand is right

I wrote `as String?` + skip; the bridge correctly notes `7 as String?` still throws, so my own
probes B5/B6 would have stayed live under it. The shipped shape-checks (`is String`, `is num` +
`.toInt()`, skip on a bad id) cover B1/B2/B3/B5/B6 — verified against the four table-driven
tests, each asserting the following event still lands **and** `getRoom` was never called (the
discriminator). My P2 probe adds the shape nobody tabled: a **skipped** malformed withhold
(bad `agent_id`) followed by a good one, then a break — recovery re-seats only the good chair
(`order == [market_analyst, news_analyst]`), nothing is resurrected from the skipped event.

### Harness notes — both confirmed, one cost me a probe

The `tester.runAsync()` requirement is real: `testWidgets` fake-async zones never fire the
timers the polling loop awaits. And my first probe run failed with zero events processed — my
own harness bug (missing `SharedPreferences.setMockInitialValues`, which `DeviceUser.getOrCreate`
needs), caught before it became a finding, same class as my round-1 autoDispose note.

### MAJOR 1 (round 2) — no DoD table on a `SCOPE: cr` submission

Same finding as DEF131 round 2, same rule, same severity, applied consistently: the bridge opens
`SCOPE: cr`, and per AUDITOR_LOOP_PROMPT step 4 + DEFINITION_OF_DONE.md rule 5 a CR-scope
submission owes the DoD table and a missing table is a MAJOR. Most dispositions are already in
the bridge prose (tests, manual verification, scope, what-was-not-done); rendering the table is
minutes. If this lane is in truth a chunk of CR098, the correct move is `SCOPE: chunk` with the
shorter evidence list — but the submission as it stands says `cr`.

### Recorded, not scored

- **Translation flag, still open:** the 4 round-1 strings still carry English in the generated
  `ar`/`ms` files; no new strings in round 2. Separate non-blocking lane per convention.
- **Nothing on a device or against melehost** — promotion hold, unchanged from round 1.
- **CR104 thin-fundamentals claim** — still unmeasured by all three of us.
- Round-1 M1–M5 mutation coverage is untouched by this diff; baseline green re-confirms the
  wiring. Not re-derived.

**BLOCKER 0 · MAJOR 1 · MINOR 0**

**VERDICT: AWAITING_FIXES (round 2)** — both round-1 findings are genuinely closed: the chair
survives a dropped connection (mutation-proved, M-A red at exactly the 2 recovery tests), a
malformed payload no longer diverts the run into recovery (M-B red at exactly the 4 malformed
tests), the `insertAll` deviation is validated against my own two-chair probe, and the Architect's
correction of my cast shorthand is right. What bounces it is procedural and identical to DEF131
round 2 an hour ago: `SCOPE: cr` stated, no DoD table rendered, and the rule leaves no
discretion. Render the table — or state `SCOPE: chunk` if that is what this lane is — and this
closes. Run report `runs/2026-07-28_run-80/`.

---

## Round 2 — amendment (stakeholder ruling)

**Stakeholder ruling, 2026-07-28 (Saiful):** DoD-table enforcement is waived until he starts it
formally — closure without the table is allowed for now. Round-2 MAJOR 1 (missing DoD table) is
therefore downgraded to recorded-not-scored, and the waiver is on record in
`AMI_TRADE_BINDINGS.md` so a fresh auditor session does not re-bounce on it. No BLOCKER and no
MAJOR remains.

**VERDICT: COMPLETE (round 2)** — on the substance: the chair survives a dropped connection
(M-A red at exactly the 2 recovery tests), a malformed payload no longer diverts the run (M-B red
at exactly the 4 malformed tests), the `insertAll` deviation is validated against my two-chair
probe, and suite 128/128 + analyze reproduce. The 4 `ar`/`ms` strings remain flagged for the
translation lane; device/melehost verification remains `NEEDS-DEVICE-CHECK` under the promotion
hold. The DoD table is owed the day enforcement starts, per the stakeholder's own note.
