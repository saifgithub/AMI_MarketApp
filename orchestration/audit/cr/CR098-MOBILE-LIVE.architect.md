<!-- architect bridge — track R. CR052 / orchestration/audit/PROTOCOL.md. -->
# CR098-MOBILE-LIVE — architect bridge

ITEM: CR098-MOBILE-LIVE
INSTANCE: coder.mobile (round 2 fixed by the Architect directly — the worker's lane is closed)
GATE: independent
SCOPE: cr
BRANCH: `lane/CR098-MOBILE-LIVE.coder.mobile` @ `44dcc0f`
WORKTREE: `.claude/worktrees/coder.mobile-CR098-LIVE`
SUBMITTED: round 2

---

# Round 2

Both findings fixed on the lane branch at `44dcc0f` (round 1 was `dca1051`). Suite **122 → 128**.

## MAJOR — the chair now survives recovery

Your diagnosis was exact and I am not re-deriving it. `_recoverViaPolling` rebuilds `order` from the
snapshot transcript alone; a locked chair is never in the transcript; `RoomScreen` iterates `order`.
Fixed where you said, with **one deliberate deviation** from your prototype:

```dart
final chairs = state.withheldAgents.keys.where((id) => !order.contains(id)).toList();
order.insertAll(0, chairs);
```

rather than `insert(0, id)` per key. With a single withheld analyst the two are identical — your
measurement stands. With **two or more**, per-key `insert(0)` reverses their relative order, so the
chairs would render in the opposite order to the one the stream seated them in. `insertAll` keeps
arrival order. Say if you read that as gold-plating; the one-liner is genuinely fine for today's
single-chair reality and I chose the version that does not have a second-chair surprise in it.

**Test, in the file next to the existing `agent_withheld` coverage:**
`recovery re-seats the withheld agent into order` drives the real notifier through a stream that
yields `started` + `agent_withheld` and then **throws**, with `getRoom` answering a completed
snapshot whose transcript contains only agents that spoke. It asserts recovery ran, `done`,
`error == null`, the chair is in `order`, seated **ahead** of the agents that did speak, and still
absent from the transcript. A second test feeds that recovered state into the real `RoomScreen` and
asserts the chair renders.

**Two harness notes, because both nearly produced a false result and one is yours.**

1. I took your `container.listen`-from-the-start advice — the autoDispose/self-start race you hit is
   real and my stream does real async work.
2. **`testWidgets` runs in a fake-async zone**, so the real timers the scripted stream and the
   polling loop await never fire: the widget test hung for the full 10-minute timeout while the
   identical plain `test` passed. It needs `tester.runAsync()` around the drive, with only the
   render left on the fake clock. Worth knowing before you probe this surface again.
3. `journalNotifierProvider` / `lessonsNotifierProvider` self-refresh on creation **and** are
   refreshed again when a run completes, so left real they issue live HTTP at `test://localhost` and
   park. Overridden with no-op notifiers. That is also why the pre-existing tests never emit `done`.

## MINOR — malformed payloads no longer abort the stream

Fixed, and **your shorthand does not work**: `as String?` still throws on a non-String, so it leaves
your own probes **B5** (`reason` is `7`) and **B6** (`agent_id` is `7`) live. Shape-checked instead —
`is String` for the id and reason, `is num` + `.toInt()` for the days, skip the event on a bad id.
`is num` also covers **B2**/**B3** (`"4"` → dropped, `4.0` → `4`) where `(as num?)?.toInt()` still
throws on the String form.

Four table-driven tests, one per bad shape, each asserting the event **after** the malformed one
still lands and that `getRoom` was called **zero** times — i.e. the run never entered the disconnect
path at all. That last assertion is what makes it a discriminator rather than a coincidence, so the
scripted client grew a `breakStream: false` mode for them.

## Measured — round 2, foreground, this worktree

| Check | Round 1 | Round 2 |
|---|---|---|
| Full `flutter test` | 122/122 | **128/128** |
| `flutter analyze --no-fatal-infos`, both touched files | clean | **No issues found** |
| **M-A** remove the re-seat | — | **RED — exactly the 2 new recovery tests** |
| **M-B** restore the hard casts | — | **RED — exactly the 4 new malformed tests** |
| Tree after mutations reverted | — | clean, **128** restored |

Your five round-1 mutations are untouched by this change and still hold.

## What I did NOT do

- **Nothing on a device or against melehost.** Promotion hold; unchanged from round 1.
- **The `ar`/`ms` translation flag is still open** — the 4 strings you enumerated are unchanged and
  still carry English in the generated files. No new user-visible strings in round 2.
- **Did not touch the notifier-race pattern you recorded but did not score.** You said you were not
  asking for a change and I am not making one; my new tests simply hold a listener.
- **Did not re-trace the CR104 thin-fundamentals claim.** Still unmeasured by all three of us.

---

# Round 1 (superseded — kept for the audit trail)

## Why this took an independent gate

It renders a **paywall-adjacent disclosure**. A disclosure that points at the wrong remedy is the
DEF059 inversion class — the user is told to spend money on a thing that does not fix their problem.
CR090-MOBILE's sibling lane took an independent gate for exactly this reason.

The specific hazard here: CR098 has **two** withhold reasons with **opposite** remedies.
`withheld_paid` is fixed by credits; `withheld_tenure` is fixed by a plan upgrade and credits do
**nothing** for it. Pointing the tenure state at the credits CTA would be a live, shipped inversion.

## Architect independent verification — measured, not read

I re-ran everything the worker claimed, plus wider, plus my own mutations. Flutter is on the Mac, so
unlike the backend lanes this was fully verifiable locally.

| Check | Worker claimed | I measured |
|---|---|---|
| `flutter test test/services/ test/widgets/` | 86/86 | **86/86** ✅ |
| `flutter analyze --no-fatal-infos`, 5 touched non-generated files | 0 issues | **No issues found** ✅ |
| **Full** `flutter test` (worker ran only two dirs) | not run | **122/122** ✅ |

### My own mutations — three, all applied physically, all reverted, tree verified clean

| | Mutation | Result |
|---|---|---|
| **M1** | Rename the `agent_withheld` case in `api_client.dart:176` — kills the **real** wire parse | **RED**, 2 tests |
| **M2** | Rename the `agent_withheld` case in `room_providers.dart:196` — kills the **state** half | **RED**, 2 tests |
| **M3** | `if (_anyTenure)` → `if (false)` in `room_screen.dart:913` — removes tenure's own CTA, leaving only the credits button. **This is the DEF059 inversion the gate exists for.** | **RED** |

`git diff --stat` and `git status --porcelain` both empty after each revert.

M3 is the one that matters: the inversion this lane exists to prevent is **held by a test**, not by
a comment. That is the CR040/"assert it, don't comment it" bar and it clears it.

## ⚠️ Coverage observation for the auditor — the real parse is thinly held

M1 killed the actual `_parseEvent` wire contract and only **2** tests went red. The reason is
structural and the worker disclosed it: the widget tests drive the real `RoomNotifier.start()` but
through a **scripted `ApiClient`**, so they never execute `_parseEvent`. All real-parse coverage
therefore rests on `test/services/api_client_room_stream_test.dart`.

That is not wrong — a scripted client is the right way to test the notifier — but it means the
wire-contract surface is narrower than the 86-test figure suggests. **Worth probing**: a malformed or
partial `agent_withheld` payload (missing `agent_id`, non-int `next_step_days`, `reason` absent) is
where I would look for an uncaught throw that takes down the stream. I did not test those shapes.

## Claims I did NOT verify

- **Anything on a device or against melehost.** `main` is under an active promotion hold
  (`infra/PROMOTION_HOLD.md`) and this lane is not merged; unit + widget level only. Nobody has seen
  this render on a phone.
- **The worker's CR104 thin-fundamentals conclusion** (its main flag, below) — a code-read
  conclusion about backend behaviour, traced through `room_prompts.py` / `room_runner.py` /
  `api/room.py`. I did not re-trace it and no live thin-data run exists to check it against.
- **`ar` / `ms` translations** for the 4 new strings. Generated files carry EN text in all three
  locales. Per project convention translation is a separate non-blocking lane — but this lane DOES
  trip the standing "content change flags translation" rule, and I am recording the flag here rather
  than letting it evaporate: **4 new user-visible strings need `ar` + `ms`.**

## The worker's own flag, which I endorse and am NOT folding into this lane

Both CR098 auditors previously said the client cannot distinguish *absent* from *withheld*. The
worker investigated and reported that for the **agent-chair** case this lane closes it —
`agent_withheld` is an explicit wire signal — but that a genuinely **thin** session (analyst present,
`field_state=unavailable` from a real provider gap) has **no wire signal at all**, so the client
cannot render "this session's data was thin" without guessing from prose content.

It declined to invent a client-side heuristic, citing CR038 ("prompt instructions are not controls").
**That is the right call** and it is the same reasoning that produced CR104. Building the client half
first would mean keying UI off agent prose, which is precisely the fragile shape this project keeps
having to unwind.

**Architect decision: not scope creep onto this lane.** It needs a backend wire signal first. I am
carrying it as a follow-up rather than bouncing this lane for it.

## Scope

11 files, +707/−12. Verdict surface (`_VerdictCard`, `opinions_not_included`) untouched — correctly
left to `CR098-MOBILE-VERDICT`, which is sequenced after this one on the same screen. No backend, no
agent prompt files (so "no agent voice sells" holds by construction — all new copy lives in
app-chrome widgets, never in `_AgentLine`'s markdown).
