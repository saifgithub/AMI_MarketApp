"""Offline guards for the two questions that keep the walk from running wild:
"am I still in the app" (`helpers/onboarding.py`) and "is the shell reachable"
(`helpers/shell.py`).

The Concierge walk is the one part of this harness that taps things it has not
identified: it reads the accessibility tree, picks the bottom-most labelled
candidate, taps, repeats. That is the correct design for an interview whose
questions are generated and whose chips are therefore not known in advance —
but the tree it reads belongs to whatever app is in *front*, not to the app
under test.

Measured on the Android rig: a run left AMI Trade and spent its entire 300s
budget tapping the Samsung dialer's keypad, then failed with "onboarding did
not reach Floor". Every word of that message was true and all of it pointed at
the wrong thing — the app was healthy and sitting in the background the whole
time. A test that fails for a fake reason is worse than no test (see this
suite's other guards); a test that fails for a fake reason *while describing a
real one* is worse still.

These run with no device: the escape detection is pure decision logic, and the
part worth pinning is what it does when the answer is unknown.
"""

from __future__ import annotations

import pytest

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)

from config.semantics_ids import NAV_IDS
from helpers import onboarding, shell


class FakeDriver:
    def __init__(self, *, state=onboarding._FOREGROUND, caps=None, package="com.x"):
        self.capabilities = caps if caps is not None else {"appPackage": "ai.agenticmarketintel.ami_trade"}
        self._state = state
        self.current_package = package

    def query_app_state(self, app_id):
        if isinstance(self._state, Exception):
            raise self._state
        return self._state


def test_the_app_under_test_is_read_from_the_live_session():
    """Not a constant: the two platforms' ids differ by more than case
    (`ai.agenticmarketintel.ami_trade` vs `…amiTrade`), so a hardcoded one
    would never match on the other platform and the check would be dead."""
    android = FakeDriver(caps={"appPackage": "ai.agenticmarketintel.ami_trade"})
    ios = FakeDriver(caps={"bundleId": "ai.agenticmarketintel.amiTrade"})
    prefixed = FakeDriver(caps={"appium:appPackage": "ai.agenticmarketintel.ami_trade"})

    assert onboarding._app_id(android) == "ai.agenticmarketintel.ami_trade"
    assert onboarding._app_id(ios) == "ai.agenticmarketintel.amiTrade"
    assert onboarding._app_id(prefixed) == "ai.agenticmarketintel.ami_trade"
    assert onboarding._app_id(FakeDriver(caps={})) is None


@pytest.mark.parametrize(
    "state, foreground",
    [
        (4, True),   # RUNNING_IN_FOREGROUND
        (3, False),  # RUNNING_IN_BACKGROUND — the dialer case
        (2, False),  # RUNNING_IN_BACKGROUND_SUSPENDED
        (1, False),  # NOT_RUNNING
        (0, False),  # NOT_INSTALLED
    ],
)
def test_only_foreground_counts_as_still_in_the_app(state, foreground):
    """Background is exactly the state the dialer incident produced — the app
    was alive the whole time (`pidof` returned a pid), just not in front. An
    is-it-running check would have called that healthy."""
    driver = FakeDriver(state=state)
    assert onboarding._is_app_foreground(driver, "ai.agenticmarketintel.ami_trade") is foreground


def test_an_unanswerable_state_query_assumes_we_are_home():
    """The one place this must NOT degrade loudly.

    A false escape relaunches the app mid-interview and throws away every
    answer already given, turning a working run into a failing one. The cost is
    asymmetric: a missed escape wastes the budget of a run that was going to
    fail anyway, a false escape breaks a run that was going to pass. So an
    unknown answer means carry on."""
    driver = FakeDriver(state=RuntimeError("driver does not implement this"))
    assert onboarding._is_app_foreground(driver, "whatever") is True


class ShellDriver:
    """Answers locator queries from a fixed set of what is 'on screen'."""

    def __init__(self, *, ids=(), texts=()):
        self.capabilities = {"platformName": "Android", "appPackage": "x"}
        self.ids, self.texts = set(ids), set(texts)

    def find_elements(self, by, value):
        for present in (*self.ids, *self.texts):
            if f'"{present}"' in value:
                return [object()]
        return []


def test_the_shell_is_detected_by_identifier_not_by_the_word_floor():
    """The load-bearing distinction, and it cost three Room runs to learn.

    "FLOOR" is a *label on a control the walk can tap*, and it only appears
    once the app has painted. A 5s text probe fired during a cold start on the
    rig — where the app renders blank for seconds — concluded "not onboarded",
    and turned the walk loose on a healthy, fully-onboarded app. `_live_chip`
    takes the bottom-most labelled control, which on Floor is CONVENE THE ROOM,
    so it convened the Room: three real 12-agent runs against the on-prem LLM
    on tickers `BY`, `ANDG`, `BY` — `ANDG` is not a ticker, it is noise the walk
    typed into the omnibox.

    The bottom nav's identifier exists only once onboarding hands over to the
    shell, so it answers the actual question."""
    onboarded = ShellDriver(ids={NAV_IDS["Floor"]})
    assert shell.shell_is_up(onboarded, "FLOOR") is True

    mid_onboarding = ShellDriver(texts={"Tell me about your goals"})
    assert shell.shell_is_up(mid_onboarding, "FLOOR") is False


def test_a_pre_cr162_build_still_resolves_by_text():
    """Builds older than the identifiers are the only reason the text path
    survives. Weaker, but it is all such a build offers."""
    old_build = ShellDriver(texts={"FLOOR"})
    assert shell.shell_is_up(old_build, "FLOOR") is True


def test_the_shell_budget_outlasts_a_cold_start():
    """A number, not a vibe: the probe was 5s and the rig's cold start rendered
    blank past that, which is the whole defect. If someone tightens this back
    toward the paint time, the walk starts convening Rooms again."""
    assert onboarding._SHELL_BUDGET_S >= 20.0, (
        f"_SHELL_BUDGET_S is {onboarding._SHELL_BUDGET_S}s — too tight to "
        f"outlast a cold start on a low-end device. Deciding 'not onboarded' "
        f"early is what set the walk loose on a working app."
    )


class BackDriver(ShellDriver):
    """A shell hidden under `layers` dismissable layers."""

    def __init__(self, layers):
        super().__init__(ids={NAV_IDS["Floor"]})
        self.layers, self.backs = layers, 0

    def back(self):
        self.backs += 1
        self.layers = max(0, self.layers - 1)

    def find_elements(self, by, value):
        if self.layers:
            return []  # the modal covers the nav
        return super().find_elements(by, value)


def test_a_covered_shell_is_backed_out_of_not_walked():
    """"The nav is not visible" has two causes needing opposite responses:
    onboarding is unfinished (walk it), or a sheet from an earlier test is on
    top of a working app (press back). Conflating them is what convened Rooms:
    a Convene sheet left open hid the nav, the walk decided "not onboarded",
    tapped around inside the sheet, and hit CONVENE."""
    driver = BackDriver(layers=2)
    assert shell.recover_to_shell(driver, "FLOOR") is True
    assert driver.backs == 2, "should stop as soon as the shell is back"


def test_backing_out_gives_up_so_real_onboarding_still_gets_walked():
    """On the onboarding root there is nothing to dismiss. This must fall
    through rather than press back forever — a device that genuinely needs the
    interview has to reach the walk."""
    driver = BackDriver(layers=99)
    assert shell.recover_to_shell(driver, "FLOOR") is False
    assert driver.backs == shell.MAX_BACK_OUTS


def _android_driver():
    return FakeDriver(caps={"platformName": "Android", "appPackage": "x"})


def _ios_driver():
    return FakeDriver(caps={"platformName": "iOS", "bundleId": "x"})


class LabelledElement:
    """The UiAutomator2 contract: `content-desc` answers, anything else is None."""

    def __init__(self, desc="", text=""):
        self._desc, self.text = desc, text

    def get_attribute(self, name):
        return self._desc if name == "content-desc" else None


# What WebDriverAgent actually answers. Everything else is HTTP 500, not "" —
# it validates attribute names against a fixed list.
_WDA_ATTRIBUTES = ("label", "name", "value", "type", "visible", "enabled")


class WdaElement:
    """The XCUITest contract, modelled honestly: `label` carries the string and
    `content-desc` RAISES. The pre-DEF348 fakes mocked `content-desc` as
    answerable on iOS, which is exactly how a spend-guard that was structurally
    dead on the real platform stayed green offline."""

    def __init__(self, label="", text=""):
        self._label, self.text = label, text

    def get_attribute(self, name):
        if name not in _WDA_ATTRIBUTES:
            raise WebDriverException(f"HTTP 500: WDA has no attribute {name!r}")
        return self._label if name == "label" else None


@pytest.mark.parametrize(
    "label, expensive",
    [
        ("CONVENE", True),
        ("CONVENE THE ROOM", True),
        ("Convene the room", True),   # case-insensitive: labels change case
        ("Save for retirement", False),
        ("SKIP FOR NOW", False),
        ("LOOKS RIGHT — CONTINUE", False),
        ("", False),
    ],
)
def test_the_walk_refuses_to_tap_anything_that_spends_credits(label, expensive):
    """The walk taps controls it has not identified, so the only defence is
    naming what expensive looks like. CONVENE runs the full 12-agent Room —
    credits, minutes of on-prem LLM, a row in `room_runs` — and it is the
    bottom-most labelled control on both Floor and the Convene sheet, which is
    exactly what `_live_chip` reaches for. Nothing in the interview is named
    this, so the filter costs the real path nothing."""
    assert onboarding._is_expensive(_android_driver(), LabelledElement(label)) is expensive


def test_the_spend_guard_is_alive_on_ios():
    """The guard read `content-desc` unconditionally. On iOS that is not an
    empty answer, it is a WebDriverAgent 500, and the stale-node except-arm
    turned it into False for EVERY element — CONVENE included. A silent
    degrade (CR040 class), invisible to any fake whose `content-desc` answers.
    This element's does not, so a regression to the shared attribute fails
    here instead of on a live Simulator four smoke attempts in (DEF348)."""
    assert onboarding._is_expensive(_ios_driver(), WdaElement("CONVENE THE ROOM")) is True
    assert onboarding._is_expensive(_ios_driver(), WdaElement("Save for retirement")) is False


@pytest.mark.parametrize(
    "label",
    [
        "restart onboarding",           # EN Settings row (floorRestartOnboarding)
        "RESTART ONBOARDING?",          # EN confirm-dialog title
        "إعادة تشغيل الجولة التعريفية",   # AR row — Arabic has no case; matched verbatim
        "mulakan semula orientasi",     # MS row
    ],
)
def test_the_walk_refuses_the_settings_row_that_resets_a_real_account(label):
    """Settings carries a row that erases `ami_onboarding_done` and re-runs the
    interview against a REAL account. The walk tapped it on iOS smoke attempt 3
    (DEF348): the flag was gone afterwards and a new onboarding_session_id
    existed. Destroying account state is as walk-fatal as spending credits."""
    assert onboarding._is_expensive(_android_driver(), LabelledElement(label)) is True
    assert onboarding._is_expensive(_ios_driver(), WdaElement(label)) is True


def test_a_benign_settings_row_is_still_tappable():
    """The deny-list must stay about spending and destruction — a filter broad
    enough to swallow ordinary rows would make the walk pass by hiding what it
    cannot handle."""
    assert onboarding._is_expensive(_android_driver(), LabelledElement("Language")) is False


def test_an_unreadable_element_is_not_treated_as_expensive():
    """A stale node cannot be tapped successfully anyway; refusing it as
    'expensive' would be a silent, wrong reason for skipping it."""

    class Stale:
        text = ""

        def get_attribute(self, name):
            raise WebDriverException("stale")

    assert onboarding._is_expensive(_android_driver(), Stale()) is False
    assert onboarding._is_expensive(_ios_driver(), Stale()) is False


class RectChip:
    def __init__(self, y):
        self.rect = {"x": 0, "y": y, "width": 320, "height": 48}


class StaleRectChip:
    @property
    def rect(self):
        raise StaleElementReferenceException("the keyboard key vanished with the keyboard")


def test_the_chooser_skips_a_candidate_that_goes_stale_mid_read():
    """Each rect read is a round trip against a node that may already be gone —
    the system keyboard's keys vanish the moment it dismisses, and a stale
    Return key inside the bare max() killed iOS smoke attempt 5 (DEF348)."""
    live = RectChip(y=500)
    assert onboarding._live_chip(None, [RectChip(y=200), live, StaleRectChip()]) is live


def test_a_screen_where_every_candidate_went_stale_reads_as_nothing_to_tap():
    """Mid-transition is not a crash: 'nothing to tap' is what the walk loop
    already sleeps on and re-observes, and that is the right response to a
    screen that vanished under the read."""
    with pytest.raises(NoSuchElementException):
        onboarding._live_chip(None, [StaleRectChip(), StaleRectChip()])


def test_an_empty_candidate_list_still_raises():
    with pytest.raises(NoSuchElementException):
        onboarding._live_chip(None, [])


class WalkChip:
    """A tappable iOS element as the walk sees one: string via `label`,
    geometry via rect, WDA's 500 on anything else."""

    def __init__(self, label, y, on_click=None):
        self._label, self._y, self._on_click = label, y, on_click
        self.taps = 0
        self.text = ""

    @property
    def rect(self):
        return {"x": 0, "y": self._y, "width": 320, "height": 48}

    def get_attribute(self, name):
        if name not in _WDA_ATTRIBUTES:
            raise WebDriverException(f"HTTP 500: WDA has no attribute {name!r}")
        return self._label if name == "label" else None

    def click(self):
        self.taps += 1
        if self._on_click:
            self._on_click()


class KeyboardedInterviewDriver:
    """One interview turn with the system keyboard up — DEF348's wedge state.

    The keyboard's Dictate key is the bottom-most labelled control, the live
    chip sits above it, and the shell appears only once the CHIP is tapped. A
    walk that does not dismiss the keyboard taps Dictate until its budget dies."""

    def __init__(self):
        self.capabilities = {"platformName": "iOS", "bundleId": "ai.agenticmarketintel.amiTrade"}
        self.keyboard_shown = True
        self.keyboard_hides = 0
        self.shell_up = False
        self.chip = WalkChip("Growth investing", y=500, on_click=self._land)
        self.dictate = WalkChip("Dictate", y=800)

    def _land(self):
        self.shell_up = True

    def query_app_state(self, app_id):
        return onboarding._FOREGROUND

    def is_keyboard_shown(self):
        return self.keyboard_shown

    def hide_keyboard(self):
        self.keyboard_hides += 1
        self.keyboard_shown = False

    def back(self):
        pass

    def find_elements(self, by, value):
        if by == AppiumBy.ACCESSIBILITY_ID:
            return [object()] if (self.shell_up and value == NAV_IDS["Floor"]) else []
        if "XCUIElementType" in value:  # the interactive-elements predicate
            return [self.chip, self.dictate] if self.keyboard_shown else [self.chip]
        return []  # text probes: no SKIP FOR NOW / READBACK / error banner on this turn


def test_the_walk_dismisses_the_keyboard_instead_of_typing_on_it(monkeypatch):
    """Three real 480s wedges (DEF348): once a tap focused the composer
    TextField, the system keyboard's Dictate/globe keys became the bottom-most
    labelled controls and `_live_chip` tapped them forever. The walk loop must
    dismiss the keyboard before choosing what to tap — the same move, for the
    same reason, as crawler/explorer.py's `_labels`."""
    driver = KeyboardedInterviewDriver()
    monkeypatch.setattr(onboarding, "_SHELL_BUDGET_S", 0.0)
    monkeypatch.setattr(shell, "MAX_BACK_OUTS", 0)
    monkeypatch.setattr(onboarding.time, "sleep", lambda seconds: None)

    onboarding.ensure_onboarded(driver, timeout_s=5.0)

    assert driver.keyboard_hides >= 1, "the keyboard was never dismissed"
    assert driver.dictate.taps == 0, "the walk tapped the keyboard"
    assert driver.chip.taps == 1


def test_waiting_for_the_shell_gives_up_rather_than_hanging():
    driver = ShellDriver(texts={"nothing useful"})
    assert shell.wait_for_shell(driver, "FLOOR", timeout_s=0.0) is False


def test_the_diagnostic_names_the_intruder_and_survives_not_knowing_it():
    """`current_package` is Android-only. It is worth reporting where it works
    — "the dialer" is a diagnosis, "not our app" is a puzzle — and must not
    break the escape path where it does not."""
    assert onboarding._foreground_package(FakeDriver(package="com.android.dialer")) == "com.android.dialer"

    class NoPackage:
        @property
        def current_package(self):
            raise RuntimeError("unsupported on this platform")

    assert onboarding._foreground_package(NoPackage()) is None
