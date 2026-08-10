# CR163 — Autonomous bug crawler on the simulator

**Filed:** 2026-08-10 · **Track:** `AT:R66` · **Status:** in_progress · **Depends on:** CR162

## Why

Saiful: *"since we are running lean, I want to be able to use the simulations to work out
bugs so they can be fixed. I need you to create a framework where we can do this
autonomously."*

The existing harness (CR080, CR162) only finds bugs someone already imagined — every check
is an assertion a human wrote about a screen a human listed. That does not scale for a
one-person team, and it structurally cannot find the surprising defects, which are the
expensive ones.

CR162 made the alternative possible. Once the accessibility semantics tree is exposed, the
app is *enumerable*: the harness can list every addressable control, so it can explore on
its own rather than following a script. Coverage then grows by walking further, not by
writing more tests.

## What

Three parts, deliberately separated:

1. **Explorer** (`qa/appium/crawler/explorer.py`) — breadth-first walk. Enumerate controls,
   tap, observe, replay back, repeat, until a wall-clock budget expires.
2. **Oracles** (`crawler/oracles.py`, `crawler/errorsink.py`) — anything that can call a
   screen wrong with no screen-specific assertion: Flutter framework errors, layout
   overflow, controls under the safe area, sparse/blank screens, unlabelled controls.
3. **Ledger + triage** (`crawler/ledger.py`, `tools/triage.py`) — fingerprint every finding,
   suppress what has already been triaged, and promote the real ones into the dispatch
   pipeline for a fixer agent + auditor.

Entry point: `scripts/crawl_ios_sim.sh`.

### The finding that redirected the design

The first implementation read Flutter's errors from the device log. **That does not work,
and it was proven rather than assumed:**

> A `xcrun simctl spawn <udid> log stream` capture of a live `Runner` process, taken while
> the app was actively calling `debugPrint`, returned **5,685 lines and zero Dart-origin
> entries** (2026-08-10). Every apparent "flutter" match was a CFBundle resource lookup.

Dart stdout/stderr goes to the process's own stdout; `os_log` never sees it. `flutter run`
displays those lines only because that command holds the pipe — a harness attaching to an
already-running app does not.

So the app records its own errors instead: `mobile/lib/qa/error_sink.dart` installs
`FlutterError.onError` + `PlatformDispatcher.onError` behind the existing
`--dart-define=AMI_QA_SEMANTICS=1`, and appends de-duplicated records to a JSONL file in
the app container. The crawler reads it back with `simctl get_app_container`. Uniform
across platforms, survives the crawler crashing, and reuses the QA-build gate CR162 already
established.

### Debug build, deliberately

Flutter compiles most framework assertions out of release builds, so a release crawl finds
only hard crashes. The crawler drives `--debug` (Saiful's call, given the trade). The
consequence to keep in mind: timing-sensitive behaviour differs from release, so a
performance-shaped finding from a crawl is a lead, not a measurement.

### Why the crawler does not file its own findings

CR080 twice had a harness bug written up as application failures — the worst instance was a
single `TypeError` reported as **27 failing tests**, none of which were real. An autonomous
crawler makes that risk larger, not smaller, and Saiful's pipeline puts a **fixer agent
waiting on whatever is filed**. An auto-filing crawler plus an auto-fixing agent turns one
bad build into a branch full of fixes for defects that never existed.

So the gate stays, and it is cheap: `tools/triage.py` lists findings with their evidence,
and writes an **intake stub** per accepted one. Stubs, not `DEF###` rows, because ids are
minted by a single owner to avoid collisions (CLAUDE.md) — a script minting them
autonomously is exactly that race. From the stub, the existing pipeline takes over:
Architect mints the id and writes the assign lane → `coder.*` fixes → auditor verdict
(`orchestration/dispatch/DISPATCH_PROTOCOL.md`).

## Design decisions worth not re-litigating

- **The frontier holds replayable paths, not screen fingerprints.** The first version queued
  fingerprints, which is unimplementable — there is no `goto(fingerprint)`, and the only way
  back to a screen is to walk there again. Depth > 1 silently never worked.
- **Wall-clock budget, not step count.** Steps range from 200ms to seconds, so a step budget
  gives wildly different coverage run to run and makes findings incomparable.
- **Destructive controls are never tapped** — this drives the real Alpha backend with a real
  account. The deny-list is asserted in `tests_offline/test_crawler_logic.py`, not trusted.
- **The scroll oracle runs last** because it swipes; the explorer re-reads the control list
  after the oracles rather than tapping nodes enumerated before the screen moved.
- **A missing error sink is a hard failure, never "no errors found".** Otherwise every crawl
  against a mis-built app reports a clean bill of health.
- **Seen ≠ triaged.** A finding that was merely reported keeps being reported; only an
  explicit `filed` / `false_positive` / `wontfix` decision silences it.

## Acceptance

1. `scripts/crawl_ios_sim.sh` builds, installs, crawls and writes `report.md` +
   `findings.json` + screenshots without manual intervention.
2. The crawl reaches more than one screen and records the path to each.
3. A deliberately-injected Flutter error appears in the report with its stack.
4. Running twice reports the second run's findings as *known*, not as new.
5. `tools/triage.py --file <fp>` writes an intake stub the dispatch pipeline can consume.
6. Offline guards pass in CI (no device needed).

## Not in scope

- Scheduling. Saiful chose "on-demand now, scheduled once it's proven" — the launchd timer
  lands once the signal-to-noise is known from real runs.
- Android. The design is platform-neutral (the sink is a file on both), but only the iOS
  simulator path is built here.
- Auto-fixing. The fixer agent and auditor already exist in `orchestration/dispatch/`;
  this CR feeds them, it does not replace them.
