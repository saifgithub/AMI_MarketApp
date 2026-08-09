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

from selenium.common.exceptions import NoSuchElementException

from config.locales import LOCALES
from helpers.gestures import tap_element
from helpers.locators import (
    element_description,
    exists_text,
    interactive_elements,
    is_text_input,
    wait_visible_text,
)
from helpers.platform import is_ios

_SKIP_FOR_NOW = "SKIP FOR NOW"
_LOOKS_RIGHT_CONTINUE = "LOOKS RIGHT — CONTINUE"
_BACKEND_ERROR_TITLE = "CAN'T REACH THE BACKEND"
_TRY_AGAIN = "TRY AGAIN"
_MAX_BACKEND_RETRIES = 2


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
    """
    labelled = [
        element
        for element in candidates
        if element_description(driver, element) != "<unlabeled>"
    ]
    if not labelled:
        return candidates[0]
    return max(labelled, key=lambda element: element.rect["y"])


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
    """
    if floor_label is None:
        floor_label = LOCALES["en"].tab_labels["Floor"]
    if timeout_s is None:
        timeout_s = 480.0 if is_ios(driver) else 120.0

    try:
        wait_visible_text(driver, floor_label, timeout_s=5)
        return  # already onboarded from a previous noReset session — the common case
    except NoSuchElementException:
        pass

    print("    [onboarding] Floor not reached yet — walking the Concierge interview")
    deadline = time.monotonic() + timeout_s
    backend_error_retries = 0

    while time.monotonic() < deadline:
        try:
            wait_visible_text(driver, floor_label, timeout_s=2)
            print("    [onboarding] landed on Floor")
            return
        except NoSuchElementException:
            pass

        if exists_text(driver, _BACKEND_ERROR_TITLE):
            backend_error_retries += 1
            if backend_error_retries > _MAX_BACKEND_RETRIES:
                raise TimeoutError(
                    f"onboarding hit {_BACKEND_ERROR_TITLE!r} {backend_error_retries} times — "
                    "this is a real backend-connectivity failure, not a locator problem"
                )
            wait_visible_text(driver, _TRY_AGAIN, timeout_s=5).click()
            time.sleep(2)
            continue

        if exists_text(driver, _SKIP_FOR_NOW):
            wait_visible_text(driver, _SKIP_FOR_NOW, timeout_s=3).click()
            time.sleep(1.5)
            continue

        if exists_text(driver, _LOOKS_RIGHT_CONTINUE):
            wait_visible_text(driver, _LOOKS_RIGHT_CONTINUE, timeout_s=3).click()
            time.sleep(1.5)
            continue

        candidates = [
            element
            for element in interactive_elements(driver)
            if not is_text_input(driver, element)
        ]
        if not candidates:
            time.sleep(1.0)
            continue
        tap_element(driver, _live_chip(driver, candidates))
        time.sleep(1.5)

    raise TimeoutError(f"onboarding did not reach Floor within {timeout_s}s")
