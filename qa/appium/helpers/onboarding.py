"""One-time Concierge-onboarding walkthrough.

The interview itself (backend/app/services/concierge_engine.py) is an
11-turn, backend-driven script — WELCOME, 8 questions, a READBACK
confirmation, then a claim-your-team screen — before the app ever reaches
Floor. Its question/chip prose is server-owned V0 Python string literals,
not `mobile/lib/l10n/app_en.arb` keys, so it can change without a mobile
release; hardcoding all 11 turns' exact text here would be fragile by
design. This walks through generically instead: tap whichever clickable,
non-text-input element appears first, with explicit preference given to the
handful of points that DO have a stable ARB-sourced string, so the walk
doesn't wander into the wrong branch:

  - "SKIP FOR NOW" over "SAVE MY TEAM" at the final claim-your-team screen —
    SAVE MY TEAM kicks off an actual sign-in sub-flow, which needs real
    credentials this harness must never fabricate (Phase 2 territory).
  - "LOOKS RIGHT — CONTINUE" at READBACK over any "Edit ..." chip — every
    Edit option except "Looks right" is unimplemented server-side (HTTP 501,
    backend/app/api/onboarding.py), so blindly tapping first-clickable there
    would intermittently hit a real error.
  - "TRY AGAIN" on the documented backend-unreachable error screen, capped
    at 2 retries — past that this is a real connectivity failure, not a
    locator problem, and should raise loudly rather than spin forever.

Runs once per fresh install: `noReset=True` means every later driver session
in this run (and future runs, until `pm_clear`) reads the persisted
`ami_onboarding_done` SharedPreferences flag and lands straight on Floor, so
after the very first call this is just a ~5s "already there" check.
"""

from __future__ import annotations

import time

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)

from config.locales import LOCALES
from helpers.gestures import hide_keyboard_if_shown, tap_element
from helpers.locators import (
    exists_id,
    exists_text,
    interactive_elements,
    is_text_input,
    wait_visible_text,
)
from helpers.platform import is_ios
from helpers.shell import recover_to_shell, shell_is_up, wait_for_shell

_SKIP_FOR_NOW = "SKIP FOR NOW"
_LOOKS_RIGHT_CONTINUE = "LOOKS RIGHT — CONTINUE"
_BACKEND_ERROR_TITLE = "CAN'T REACH THE BACKEND"
_TRY_AGAIN = "TRY AGAIN"
_MAX_BACKEND_RETRIES = 2
_MAX_ESCAPES = 3

# DEF366 — how many consecutive unanswerable foreground queries before the
# walk gives up and says so. Higher than _MAX_ESCAPES because a transient
# WDA hiccup is survivable and common, while a sustained one means the
# harness is blind and every later observation is worthless.
_MAX_BLIND = 10

# How long to let the shell appear before concluding the app needs onboarding.
# Generous on purpose: a cold start on the Android rig renders blank for several
# seconds, and deciding "not onboarded" too early is what set the walk loose on
# a working app and convened three Rooms. Waiting is cheap — this only elapses
# in full on a device that genuinely needs the interview, which happens once per
# install.
_SHELL_BUDGET_S = 30.0


# Controls the walk must never tap, matched case-insensitively as a substring
# of the element's label.
#
# The walk taps things it has not identified — unavoidable for an interview
# whose chips are generated — so the only defence against it doing something
# expensive is to name what expensive looks like. CONVENE runs the full
# 12-agent Room: real credits, minutes of on-prem LLM, and a row in
# `room_runs`. It got tapped repeatedly across two incidents because it is the
# bottom-most labelled control on Floor and on the Convene sheet, which is
# exactly what `_live_chip` reaches for.
#
# Nothing in the Concierge interview is named this, so the filter costs the
# walk nothing on the path it is actually for. Keep this list short and keep it
# about *spending or destroying account state*, not about tidiness — a long
# denylist would quietly become a way to make the walk pass by hiding what it
# cannot handle.
#
# RESTART ONBOARDING is the Settings row (`floorRestartOnboarding`) that erases
# `ami_onboarding_done` and re-runs the whole interview against a REAL account.
# The walk did exactly that on iOS smoke attempt 3 (DEF348): it wandered into
# Settings, the flag was gone afterwards, and a new onboarding_session_id
# existed on the backend. All three rendered locales are listed because the
# label is what the walk sees, and matching is against `.upper()` — Arabic has
# no case, so its entry is verbatim.
_NEVER_TAP = (
    "CONVENE",
    "RESTART ONBOARDING",
    "إعادة تشغيل الجولة التعريفية",
    "MULAKAN SEMULA ORIENTASI",
)


def _is_expensive(driver, element) -> bool:
    """Does this element's label name something the walk must never tap?

    The label attribute is platform-dispatched, and that dispatch is
    load-bearing: asking XCUITest for `content-desc` is not "empty string", it
    is HTTP 500 from WebDriverAgent (it validates against a fixed attribute
    list — see locators.element_description). Read that way, the except-arm
    swallowed the 500 and answered False for EVERY element, so the guard was
    structurally dead on iOS while its offline tests — which mocked
    `content-desc` as answerable — stayed green (DEF348, CR040 class).
    """
    attribute = "label" if is_ios(driver) else "content-desc"
    try:
        label = element.get_attribute(attribute) or element.text or ""
    except WebDriverException:
        return False  # stale node; it will not be tapped successfully anyway
    return any(marker in label.upper() for marker in _NEVER_TAP)


# Appium's application state enum; 4 is RUNNING_IN_FOREGROUND.
_FOREGROUND = 4


def _app_id(driver) -> str | None:
    """The package/bundle under test, from the live session's own capabilities
    rather than a constant — the harness drives two platforms whose ids differ
    (`…ami_trade` vs `…amiTrade`), and a hardcoded one would silently never
    match on the other."""
    caps = driver.capabilities
    for key in ("appPackage", "bundleId", "appium:appPackage", "appium:bundleId"):
        if caps.get(key):
            return caps[key]
    return None


# DEF366 — three states, not two. `UNKNOWN` exists because the previous
# version returned `True` from its except branch, which made "cannot tell"
# and "we are fine" the same answer. That is how DEF362 burned two rounds of
# diagnosis: the simulator sat on the iOS home screen for the full 480s
# budget, the detector could not see it, reported fine, and the walk blamed
# the app. `CLAUDE.md`: *if this fires constantly and silently, what does the
# user end up believing?* Here the operator believed the app could not start,
# and DEF347 and DEF348 were both aimed at that belief.
from helpers.foreground import FOREGROUND, NOT_FOREGROUND, UNKNOWN, resolve
from helpers.candidate_pool import selectable


def app_foreground_state(driver, app_id: str) -> str:
    """Is the app under test in front? `UNKNOWN` when the query itself fails.

    The old signature returned `bool` and could not express the third answer.
    Callers must handle `UNKNOWN` explicitly — it is neither safe to treat as
    an escape (a false escape relaunches mid-interview and discards real
    progress, which is what the original comment was right about) nor safe to
    treat as fine (which is what it actually did).
    """
    return resolve(lambda: driver.query_app_state(app_id))


def _foreground_package(driver) -> str | None:
    """Only for the diagnostic message. Knowing it was the dialer rather than
    'not our app' is the difference between a five-minute diagnosis and an
    hour of one.

    DEF366 — used to be `driver.current_package` unconditionally, which is
    Android-only by its own admission, so on iOS it raised and every escape
    could only ever be reported as "an unidentified app". Both the detection
    and its explanation were shaped for the platform that was not failing.
    iOS has no equivalent query, so say *that* rather than nothing: naming the
    limitation is more useful to the next reader than a bare null.
    """
    try:
        if is_ios(driver):
            return "another app (iOS exposes no foreground-app query)"
        return driver.current_package
    except Exception:
        return None


def _keyboard_frame(driver):
    """The software keyboard's own rect, or None when there isn't one.

    None on Android deliberately: `hide_keyboard()` works there, and this
    exists only because it does not work on iOS. None is also the answer when
    the query fails — see `keyboard_zone.is_inside` for why that must exclude
    nothing rather than everything.
    """
    if not is_ios(driver):
        return None
    try:
        keyboards = driver.find_elements(
            AppiumBy.IOS_PREDICATE, 'type == "XCUIElementTypeKeyboard"'
        )
    except Exception:
        return None
    for keyboard in keyboards:
        try:
            rect = keyboard.rect
        except Exception:
            continue
        return (rect["x"], rect["y"], rect["width"], rect["height"])
    return None


def _selectable(driver, candidates):
    """Narrow the pool to controls the walk may actually tap.

    DEF374, in two measured halves. `_live_chip` picks the bottom-most labelled
    control; with the keyboard up that was the globe key (186 taps in one wedged
    run), and once the keyboard was excluded it became the composer text field
    (180 taps in the next). Filtering here rather than inside `_live_chip` keeps
    the "bottom-most wins" rule intact and simply stops feeding it controls that
    are not answers.
    """
    frame = _keyboard_frame(driver)
    kinds, rects, live = [], [], []
    for element in candidates:
        try:
            rect = element.rect
            kind = element.get_attribute("type") or element.get_attribute("class") or ""
        except Exception:
            continue
        rects.append((rect["x"], rect["y"], rect["width"], rect["height"]))
        kinds.append(kind)
        live.append(element)
    kept = selectable(kinds, rects, frame)
    dropped = len(live) - len(kept)
    if dropped:
        print(f"    [onboarding] ignoring {dropped} non-answer control(s)")
    return [live[i] for i in kept]


def _live_chip(driver, candidates):
    """Pick the chip belonging to the CURRENT turn.

    The interview is a chat transcript: answered turns stay on screen and
    scroll up, and their chips stay in the accessibility tree. "First
    interactive element" therefore means "a chip from a turn already answered",
    which submits nothing — the walk taps it forever and times out with the app
    visibly parked on the same question. That is exactly how the first iOS run
    failed, twice, at 120s and then at 300s.

    Two signals identify the live chips, and both are structural rather than
    string-matched (the interview's prose is backend-owned and must not be
    hardcoded here):

    - They carry a label. The send-arrow button beside the text field has none,
      and tapping it with an empty field does nothing.
    - They are the bottom-most such control, because the transcript grows
      downward and the active chip row sits directly above the input.

    Each `rect` read is a driver round trip against a node that may no longer
    exist — the system keyboard's keys vanish the moment it dismisses, and a
    StaleElementReferenceException out of the bare `max()` key killed iOS smoke
    attempt 5 on the keyboard's Return key (DEF348). Stale candidates are
    skipped; if EVERY candidate went stale the screen is mid-transition, and
    that raises the same "nothing to tap here" the caller already retries on.
    """
    if not candidates:
        raise NoSuchElementException("no tappable candidate on this screen")
    readable = []
    for element in candidates:
        try:
            readable.append((element.rect["y"], element))
        except WebDriverException:
            continue
    if not readable:
        raise NoSuchElementException(
            "every tappable candidate went stale mid-read — the screen is transitioning"
        )
    return max(readable, key=lambda pair: pair[0])[1]


def ensure_onboarded(
    driver, *, floor_label: str | None = None, timeout_s: float | None = None
) -> None:
    """Walk the Concierge interview until the app lands on the shell.

    CR162 fixed two things here:

    - `floor_label` defaulted to the literal `"Floor"`, which is the harness's
      locale-independent *key*, not the rendered string. The tab renders
      `l.floorTabUpper` — "FLOOR" — so the exact-text probe could never match
      and this function could only ever fall through to the walk. It now takes
      the string from the same locale table everything else uses.
    - The budget is platform-aware. WebDriverAgent element queries are markedly
      slower than UiAutomator2's, and each miss in this loop pays the locator
      retry backoff (~5.4s), so an 11-turn interview does not fit in the
      Android-sized 120s. Measured, not guessed: the walk completed the full
      11-turn interview and reached Floor at just over 300s, so 480s is the
      budget with headroom. This is a one-time cost per fresh install —
      `noReset=True` means every later session takes the ~5s early return.

    The Android budget went 120s -> 300s, and that number is **not measured** —
    say so rather than let a round figure read as one. What is measured is iOS:
    just over 300s for the same 11 turns. Most of that is not query overhead,
    it is eleven round-trips to the LLM answering as the Concierge, and that
    cost is identical on both platforms. So the platform difference is the
    *overhead on top of* a floor both share, and 120s sat below the floor
    itself. The error directions are not symmetric either: too small
    manufactures a failure that reads exactly like a broken app (this loop's
    timeout surfaces as "never reached Floor"), while too large only costs
    wall-clock on a run that was going to fail anyway. Replace this with a real
    Android measurement when a device is next on the cable.
    """
    if floor_label is None:
        floor_label = LOCALES["en"].tab_labels["Floor"]
    if timeout_s is None:
        timeout_s = 480.0 if is_ios(driver) else 300.0

    # Is the shell already up? This is the common case by a wide margin —
    # `noReset=True` means a device onboards once and every later session lands
    # straight on Floor — and getting it wrong is the most expensive mistake
    # this module can make, so it is worth a real budget and an exact question.
    #
    # It asks for the bottom nav's IDENTIFIER, not the word "FLOOR". The nav
    # exists only once onboarding has handed over to the shell, so the
    # identifier is a precise discriminator; the text is not. Text races the
    # first paint, and it is also a *label on a control the walk might tap*.
    #
    # What that cost, measured: a 5s text probe fired during a cold start on the
    # rig (the app renders blank for several seconds), concluded "not
    # onboarded", and set the walk loose on a perfectly healthy, fully
    # onboarded app. `_live_chip` takes the bottom-most labelled control, and on
    # Floor that is CONVENE THE ROOM — so the walk typed noise into the omnibox
    # and convened the Room. Three real 12-agent runs against the on-prem LLM
    # (`BY`, `ANDG`, `BY` — `ANDG` is not a ticker), one of them 199s long, and
    # the Room is a full-screen route with no bottom nav, so the probe could
    # never re-match and the walk kept tapping inside it until the budget died.
    #
    # The containment check below did not catch that, and correctly so: we never
    # left the app. We left the *shell*, which is a different question and is
    # this probe's job to answer.
    if wait_for_shell(driver, floor_label, timeout_s=_SHELL_BUDGET_S):
        return

    # Covered, or absent? A modal sheet or a pushed route left behind by an
    # earlier test hides the bottom nav just as thoroughly as unfinished
    # onboarding does, and the right answer to each is the opposite of the
    # other. Try backing out before assuming the interview is unfinished.
    if recover_to_shell(driver, floor_label):
        return

    print("    [onboarding] shell not up — walking the Concierge interview")
    deadline = time.monotonic() + timeout_s
    backend_error_retries = 0
    escapes = 0
    blind = 0
    app_id = _app_id(driver)

    while time.monotonic() < deadline:
        # Are we even still in the app? The walk taps whatever the accessibility
        # tree offers, and the tree is the *foreground app's*, not ours — so one
        # stray tap that fires an external intent, or a probe that runs before
        # our first frame paints, hands the rest of the budget to somebody
        # else's UI. Measured: a run left AMI Trade and spent the full 300s
        # tapping the Samsung dialer's keypad, then reported "onboarding did not
        # reach Floor", which reads exactly like the app failing to start.
        #
        # Recover rather than fail on the first escape — the walk is exploratory
        # and a single bounce is survivable — but say so every time, and give up
        # naming the intruder once it is clearly not converging. Silently
        # re-entering forever would hide an app that really does launch
        # something external.
        state = app_foreground_state(driver, app_id) if app_id else FOREGROUND

        # DEF366 — an unanswerable query is its own outcome and is reported
        # every single time. It is NOT counted as an escape (we have not
        # established one) and NOT treated as fine (which is the bug). If it
        # never resolves, the walk fails saying it could not see the app —
        # never "onboarding did not reach Floor", which blames the app for
        # something the harness could not observe.
        if state == UNKNOWN:
            blind += 1
            print(
                f"    [onboarding] cannot determine whether {app_id} is in "
                f"front — query_app_state failed (blind {blind}/{_MAX_BLIND})."
            )
            if blind > _MAX_BLIND:
                raise TimeoutError(
                    f"onboarding could not observe whether the app under test "
                    f"({app_id}) was in the foreground: query_app_state failed "
                    f"{blind} times. This says NOTHING about whether onboarding "
                    f"works — the harness went blind, and a walk that cannot "
                    f"see the app must not report on the app. Check the Appium "
                    f"session and the bundle id in the session capabilities."
                )
            time.sleep(1.0)
            continue

        if state == NOT_FOREGROUND:
            escapes += 1
            intruder = _foreground_package(driver) or "an unidentified app"
            print(
                f"    [onboarding] the walk left {app_id} — {intruder} is in "
                f"front (escape {escapes}/{_MAX_ESCAPES}). Re-entering."
            )
            if escapes > _MAX_ESCAPES:
                raise TimeoutError(
                    f"onboarding kept leaving the app under test ({app_id}); "
                    f"last seen in front: {intruder}. The walk taps what the "
                    f"foreground app exposes, so it cannot recover on its own. "
                    f"This is NOT 'the app failed to start' — check whether a "
                    f"tapped element fires an external intent."
                )
            driver.activate_app(app_id)
            time.sleep(2.0)
            continue

        if shell_is_up(driver, floor_label):
            print("    [onboarding] landed on Floor")
            return

        if exists_text(driver, _BACKEND_ERROR_TITLE, retry=False):
            backend_error_retries += 1
            if backend_error_retries > _MAX_BACKEND_RETRIES:
                raise TimeoutError(
                    f"onboarding hit {_BACKEND_ERROR_TITLE!r} {backend_error_retries} times — "
                    "this is a real backend-connectivity failure, not a locator problem"
                )
            wait_visible_text(driver, _TRY_AGAIN, timeout_s=5).click()
            time.sleep(2)
            continue

        if exists_text(driver, _SKIP_FOR_NOW, retry=False):
            wait_visible_text(driver, _SKIP_FOR_NOW, timeout_s=3).click()
            time.sleep(1.5)
            continue

        if exists_text(driver, _LOOKS_RIGHT_CONTINUE, retry=False):
            wait_visible_text(driver, _LOOKS_RIGHT_CONTINUE, timeout_s=3).click()
            time.sleep(1.5)
            continue

        # The system keyboard's keys are ordinary labelled buttons at the
        # bottom of the screen — exactly what `_live_chip` reaches for. Once a
        # tap focused the composer TextField, the Dictate/globe keys became the
        # bottom-most candidates and got tapped forever: three 480s wedges on
        # iOS (DEF348). Same dismissal, same reason, as crawler/explorer.py's
        # `_labels`.
        hide_keyboard_if_shown(driver)

        # labelled_only filters server-side: the send-arrow button has no
        # label, and this avoids one WebDriverAgent attribute read per candidate.
        candidates = interactive_elements(driver, labelled_only=True)
        if not candidates:
            candidates = [
                element
                for element in interactive_elements(driver)
                if not is_text_input(driver, element)
            ]
        candidates = [c for c in candidates if not _is_expensive(driver, c)]
        candidates = _selectable(driver, candidates)
        if not candidates:
            time.sleep(1.0)
            continue
        try:
            chip = _live_chip(driver, candidates)
        except NoSuchElementException:
            # Every candidate went stale mid-read — screen transition; re-observe.
            time.sleep(1.0)
            continue
        try:
            tap_element(driver, chip)
        except StaleElementReferenceException:
            print("    [onboarding] the chosen chip went stale before the tap — re-observing")
            continue
        time.sleep(1.5)

    raise TimeoutError(f"onboarding did not reach Floor within {timeout_s}s")
