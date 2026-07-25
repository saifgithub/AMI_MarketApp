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

from helpers.gestures import tap_element
from helpers.locators import exists_text, interactive_elements, wait_visible_text

_SKIP_FOR_NOW = "SKIP FOR NOW"
_LOOKS_RIGHT_CONTINUE = "LOOKS RIGHT — CONTINUE"
_BACKEND_ERROR_TITLE = "CAN'T REACH THE BACKEND"
_TRY_AGAIN = "TRY AGAIN"
_MAX_BACKEND_RETRIES = 2


def ensure_onboarded(driver, *, floor_label: str = "Floor", timeout_s: float = 120.0) -> None:
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
            if "EditText" not in (element.get_attribute("class") or "")
        ]
        if not candidates:
            time.sleep(1.0)
            continue
        tap_element(driver, candidates[0])
        time.sleep(1.5)

    raise TimeoutError(f"onboarding did not reach Floor within {timeout_s}s")
