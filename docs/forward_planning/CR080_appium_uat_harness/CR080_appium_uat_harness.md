# CR080 — Appium UAT/usability harness + standing QA track

**Filed:** 2026-07-23 · **Track:** `AT:Q` (new) · **Status:** in_progress · **Depends on:** CR079

## Why

Saiful asked for a "UAT UI/UX Manager" capability: test scripts that exercise the app purely
from a user's point of view, hunting usability defects — his example, "screens that do not
scroll when they need to." No such role or tooling exists today. Manual device testing has
always been Saiful's alone (`docs/initial_specs/10_delivery/you_do_i_do.md`); Claude has only
ever written automated *unit*/widget tests, never driven the app as a user would.

Static review of `mobile/lib/screens/**` already turned up concrete candidates before a single
test ran: `screens/auth/merge_sheet.dart` and `screens/room/convene_sheet.dart` are modal sheets
with no scroll wrapper around variable-length content; `screens/agent/agent_unlocked_screen.dart`
is a fixed `Column`+`Spacer` layout with no scroll fallback. There's already a precedent bug of
exactly this shape — **DEF075** (a modal-sheet button rendered under the Android system nav bar,
unclickable) — fixed and guarded by one widget test (`sheet_insets_test.dart`), but that test
only proves the layout math against a synthetic `MediaQuery`, not the rendered result on a real
device.

CR079 (same day) built the delivery half of this: every build path now scps a fresh release APK
to `saiful@192.168.20.59:/home/saiful/hermes_folder/project/AMI_MarketApps/apk/`, explicitly
because — Saiful's words — "that is our automated tester." CR080 builds the tester itself: the
Appium scripts that actually drive that APK on the Galaxy A17 already sitting there on USB, plus
the standing track (`Q`) to run it recurringly pre-release.

## What

- **New track `Q`** ("QA/UAT") in `.claude/session-config.yml` — `HANDOVER_Q.md`,
  `history_dir: history/`, `project_plan_path` pointing back at this doc as the living
  screen/flow coverage backlog.
- **`qa/appium/`** — a Python + pytest + Appium-Python-Client harness, source-of-truth in git,
  shipped to melehost's `.../AMI_MarketApps/appium/` the same way CR079 ships the APK: git is
  truth, transfer is a mechanical step, never hand-authored on the remote host.
- **Black-box Appium + UiAutomator2** against the existing release APK — no
  `enableFlutterDriverExtension()` in the app, so this is tested exactly like any native Android
  app: text-based locators (Flutter exposes rendered text to the accessibility tree once
  UiAutomator2's own accessibility interrogation runs, no special build or driver plugin needed),
  screenshots, and gesture-driven checks.
- **Two mechanical usability checks**, the ones Saiful asked for by name:
  - *Non-scrolling overflow* — hierarchy check for a `scrollable` ancestor + a masked
    before/after screenshot diff around a calibrated swipe (masking `home_shell.dart`'s
    always-animating `TickerTape`, which otherwise reads as false movement). Flags only when
    nothing moved, nothing scrollable exists, and content reaches the fold.
  - *Nav-bar overlap* (the DEF075 class) — reads the real nav-bar band from
    `adb shell dumpsys window windows` (Flutter draws edge-to-edge behind the bar, so the
    FlutterView's own bounds carry no signal) and flags any interactive element whose bounds
    intrude on it, across every reachable modal sheet.
- **Reporting**: `hermes_folder/reports/appium/<run_id>/` — `report.html` (pytest-html),
  screenshots, raw accessibility-tree dumps, and a `summary.json` using `def_list.md`'s existing
  `ui_glitch`/`ux` category vocabulary. The harness never files a defect itself — findings are
  human/Claude-reviewed and promoted to `DEF###` (`Source = prompt`).
- **Test data**: Phase 1 needs no credentials (anonymous-first onboarding, `pm clear` for a cold
  session). The synthetic test account gets tagged so it can be added to the existing
  `feedback_user_report_exclusions` filter (same pattern as CR035's room-benchmark rows). Phase 2
  flows that need real credentials (sign-in test inbox, Alpaca paper-trading keys) are flagged as
  pending Saiful input, not fabricated — committed as `test_data/.env.example` placeholders only.

## Not changed

- App code — this CR ships test tooling only; nothing in `mobile/lib/` changes.
- CR079's APK pipeline — CR080 consumes its output (`.../apk/app-release.apk`), doesn't alter it.
- The existing manual device-pass checklist (CR004's A2) — this harness mirrors its journey for
  mechanical coverage, it doesn't replace the human pass.

## Phasing (this doc is the coverage backlog track `Q` ticks off)

- **Phase 1** (this session): harness scaffold, GO/NO-GO locator gate, both mechanical checks on
  the 3 flagged screens + 5 bottom-nav tabs + reachable modal sheets (convene / trade-ticket /
  brief / bug-report), one clean report reviewed and any real findings filed as defects.
- **Phase 2** (next `Q` session): full onboarding cold-start, Room 12-agent run-to-verdict, trade
  submission, `chart_fullscreen` rotation regression, seeded-account `merge_sheet` case, sign-in/
  Alpaca flows once Saiful supplies credentials.
- **Phase 3** (standing): full 25-screen sweep, multi-device matrix (add the Galaxy Note FE),
  visual-regression baselining across builds, `ms`/`ar` + RTL sweeps, scheduled recurring runs.

## Acceptance

1. `.claude/session-config.yml` has a `Q` track; `/start-fresh Q` resolves without error.
2. `qa/appium/` exists in git and mirrors 1:1 onto melehost's
   `.../AMI_MarketApps/appium/` after an rsync.
3. `test_00_smoke_hierarchy.py` passes against the live Galaxy A17 (`R5CY91AY99Y`) — proves
   text locators resolve and the nav-bar read parses.
4. `test_sheets_navbar.py` + `test_scroll_overflow.py` run clean and produce
   `report.html` + `summary.json` + annotated screenshots.
5. Any confirmed usability defect from that run is filed as `DEF###` (`ui_glitch`/`ux`),
   specifically confirming or ruling out the three static-analysis risk candidates above.

## Phase 3 update — 2026-07-25, language matrix

Saiful: *"We now have 3 languages. You need to prepare the test cases for 3 languages."*

AR + MS translation delivery (CR083) and AR lesson serving (CR087) shipped since Phase 1, so
the app now has 3 real, in-app-switchable languages. Delivered:

- **`config/locales.py`** — per-locale `LocaleProfile` (tab labels, hard-assert content
  strings, RTL flag), every string copied verbatim from the live
  `mobile/lib/l10n/app_{en,ar,ms}.arb` on 2026-07-25 — never guessed.
- **`helpers/locale_switch.py`** — switches the **in-app** language override (Settings ->
  Language, `locale_provider.dart`), not the device/OS locale; matches how a real user changes
  language, no relaunch needed (Riverpod state, MaterialApp re-renders live). Locates the
  Settings tab without assuming current locale (tries all 3 known labels).
- **`pages/base_page.py`**: `open_tab()` gained a `locale=` kwarg (default `"en"`, so all 10
  existing Phase 1 call sites are untouched) resolving the semantic tab key to the right
  on-screen string per locale.
- **`tests/test_locale_matrix.py`** (new `phase3`/`locale` markers) — per locale (EN/AR/MS):
  content probe + scroll-overflow across the 5 tabs, nav-bar-overlap + scroll-overflow on the
  Convene sheet, and a hard-asserted RTL bottom-nav mirroring check (`HexBottomNav` is a plain
  `Row` with no `textDirection` override, so AR mirroring left/right is a structural Flutter
  guarantee, not a heuristic — unlike the scroll/navbar checks, a mismatch there fails the test
  outright rather than only recording a finding).
- **Real translation-consistency findings surfaced while extracting the ARB strings** (flagged
  to Saiful in-session, not fixed here — this CR ships test tooling only): `tabFloor` stays
  English/Latin-script in both AR and MS (possibly intentional, matches `floorConciergeHeading`
  = "AMI CONCIERGE" staying untranslated everywhere — but worth a call); `tabPortfolio`/
  `portfolioHeading` also stay English in MS only; most notably `conveneHeading` mixes scripts —
  AR = `"CONVENE الغرفة"`, MS = `"CONVENE BILIK"` — while the sibling keys `conveneCta`/
  `floorConveneCta` for the same concept get either fully translated (AR) or fully untranslated
  (MS `"CONVENE"`), i.e. 3 different treatments of one concept across 3 keys. Also stale:
  `settingsLanguagePlaceholderNote` still reads "AR + MS ship as placeholders today" even though
  CR083/CR087 have since shipped real translations for most of the surface this harness touches.
- **Not yet covered** (would need seeded state, same as Phase 1/2's existing gaps): trade-ticket
  sheet, bug-report sheet, and Room/Lessons-reader content in AR/MS specifically (CR087 shipped
  AR lesson bodies at ~81% coverage, MS lesson bodies at 3/342 — this matrix only reaches the
  Lessons *landing* honeycomb, not an individual lesson's translated body).

## Phase 3 fix — 2026-07-25, onboarding gate blocked the entire first real run

First live run against the Galaxy A17 (post Play-Protect-fix) came back **28 FAIL / 1 PASS / 7
SKIP** — every failure traced to one root cause: the app was landing on the Concierge
onboarding interview, not Floor, so every bottom-nav text locator legitimately found nothing.
`test_00_smoke_hierarchy.py`'s own docstring had already named this exact precondition
("the precondition every other Phase 1 test assumes via noReset") but nothing ever enforced it
— an assumption, not a check.

Verified the actual flow against source before writing a fix, since the UAT team's paraphrase
(2 steps, 3 chips) undersold it substantially: it's an **11-turn, backend-driven** script
(`backend/app/services/concierge_engine.py` — WELCOME + 8 questions + READBACK + a claim-team
screen), whose question/chip prose is server-owned Python string literals, not ARB keys —
meaning it can change without a mobile release, so hardcoding all 11 turns' exact text would be
fragile by construction. Confirmed the SharedPreferences `ami_onboarding_done` flag exists but
is very likely unwritable via adb here (`run-as` needs a debuggable build; this is a
production-signed release APK), ruling out the "just poke the flag" shortcut.

Delivered **`helpers/onboarding.py`**: `ensure_onboarded()`, wired into `conftest.py`'s
`driver` fixture (runs once per fresh install, a ~5s no-op check on every later session thanks
to `noReset=True`). Walks generically — tap whichever clickable, non-text-input element
appears — rather than matching the backend-owned turn-by-turn prose, with explicit preference
given to the few stable ARB-sourced strings so the walk doesn't wander into the wrong branch:
**"SKIP FOR NOW"** over "SAVE MY TEAM" (the latter opens a real sign-in sub-flow needing
credentials this harness must never fabricate), **"LOOKS RIGHT — CONTINUE"** over any READBACK
"Edit ..." chip (all but "Looks right" are HTTP 501 server-side), and **"TRY AGAIN"** on the
documented backend-unreachable screen, capped at 2 retries before raising loudly.

**Process note, not a design change:** diffing melehost's `conftest.py` against git found it
had been **hand-edited directly on the remote copy** — a `_AutoRecoverDriver` wrapper +
crash-recovery pytest hooks, none of it in this repo. That edit also silently deleted the
failure-evidence capture (screenshot + page_source dump) for every failure, not just driver
crashes. This violates the "git is truth, never hand-edit melehost's copy" convention this
harness (and CR079's APK pipeline) both run on. The redelivery below overwrites it — correct,
since git stays authoritative — but flagged to Saiful rather than silently clobbered.

## Phase 3 fix #2 — 2026-07-26, second remote hand-edit produced a misleading test report

A `response/appium_test_report.md` came back claiming **27 FAIL / 2 PASS / 7 SKIP**, root-caused
by the "Automated Test Agent" to two harness bugs: an `exists_text()` signature mismatch and a
Flutter `content-desc`-resolution gap, with a recommended fix to rewrite `by_text()`/`by_text_contains()`
around the premise "Flutter apps do NOT populate `text=`, only `content-desc`."

That premise is false for this app — already disproven by Phase 1's real-device runs and by two
of this very run's own tests passing on plain text locators — and the report itself was
diagnosing damage from a **second direct hand-edit of melehost's copy**, not this harness.
`rsync --dry-run` showed 3 files diverged from git: `helpers/locators.py`, `helpers/onboarding.py`,
`pages/base_page.py`. Someone added a new `_dismiss_overlays()` to `base_page.py` that calls
`exists_text(driver, ..., timeout_s=1)` — but never added a matching `timeout_s` parameter to
the hand-edited `exists_text()` in `locators.py`, so every `open_tab()` call raised a bare
`TypeError`. That single bug, not two independent root causes, explains all 27 failures: every
failure screenshot (smoke test, Settings, and all three `en`/`ar`/`ms` locale-matrix variants)
shows the identical stuck state — a "NEW TRADE" ticket sheet left open over Portfolio, in
English, that `_dismiss_overlays()` could never reach far enough to dismiss. Most likely trigger:
the hand-edited `onboarding.py`'s blind "tap the first clickable element" fallback, whose
Floor-detection switched to a content-desc-only check that doesn't match this app's bottom nav,
so it kept treating Floor as unreached and tapping into the "+ New Trade" launcher.

Zero of the 27 failures are app bugs or gaps in what shipped from git. Fixed by redelivering the
clean `qa/appium/` tree via rsync (no `--delete`, so `start-appium.sh` and other UAT-team-added
operational files were left alone) — confirmed via a post-delivery grep that
`_dismiss_overlays`/`timeout_s=1`/the false content-desc premise are gone from all three files.
This is the **second occurrence** of the same violation (first: the `_AutoRecoverDriver`
hand-edit, previous section) — per CLAUDE.md's failure-patterns convention, a second occurrence
of anything should get a guard, not just a re-flag. No guard designed yet; surfaced to Saiful as
an open decision (e.g. making melehost's copy read-only, or a pre-run diff-against-git check)
rather than built unilaterally.

**Heads-up for the next run, not yet verified:** the physical device may still be sitting on the
stuck New Trade sheet from this corrupted run, since `noReset=True` doesn't restart the app
between driver sessions — the UAT team may need to back out of it (or `pm clear` for a fully
cold state) before re-running, or the fixed harness will hit the same stuck screen for an
unrelated reason.
