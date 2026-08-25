"""DEF374 — the walk must not tap the system keyboard.

Lives here, not in `qa/appium/`, for the reason DEF366's guard does: that suite
needs a booted simulator and is the thing under repair. `keyboard_zone` imports
nothing, so every branch is reachable from a plain tuple.

Every number below is measured, not invented. On 2026-08-25 a wedged run clicked
one element **186 times**; its label, read back from the Appium log, was
`Next keyboard` — the globe key. The rects are the iPhone 17 Pro simulator's own
(402x874pt portrait), read from the live accessibility tree.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_MODULE = (
    Path(__file__).resolve().parents[3] / "qa" / "appium" / "helpers" / "candidate_pool.py"
)
_spec = importlib.util.spec_from_file_location("candidate_pool", _MODULE)
candidate_pool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(candidate_pool)

# `XCUIElementTypeKeyboard`'s own rect: it stops at y=791 and does NOT contain
# the globe/dictation row beneath it. That gap is the whole reason this module
# uses a floor rather than a bounding box.
KEYBOARD = (0.0, 564.0, 402.0, 227.0)

# The interview's first-turn answer chip, from the live tree.
CHIP = (16.0, 369.0, 151.0, 48.0)
COMPOSER = (16.0, 425.0, 330.0, 52.0)
# Inside the keyboard's rect.
RETURN_KEY = (300.0, 700.0, 90.0, 44.0)
# BELOW the keyboard's rect — the element that was tapped 186 times.
GLOBE = (12.0, 812.0, 40.0, 40.0)
DICTATE = (350.0, 812.0, 40.0, 40.0)


def test_the_globe_key_is_excluded_even_though_it_is_below_the_keyboard_rect():
    """The regression that matters. The first cut of this module used a
    bounding box, dropped 3 keys an iteration, and still wedged 171 taps here."""
    assert candidate_pool.is_occluded(GLOBE, KEYBOARD) is True
    assert candidate_pool.is_occluded(DICTATE, KEYBOARD) is True


def test_a_key_inside_the_keyboard_rect_is_excluded():
    assert candidate_pool.is_occluded(RETURN_KEY, KEYBOARD) is True


def test_the_answer_chip_survives():
    """An over-eager filter turns a wedge into an empty screen, which is worse."""
    assert candidate_pool.is_occluded(CHIP, KEYBOARD) is False


def test_the_bottom_most_survivor_is_reachable_ui_not_a_key():
    """The property that actually matters. `_live_chip` picks the bottom-most
    labelled control; the guard is not 'something was dropped' but 'what that
    rule now lands on is a control the user could reach'."""
    pool = [CHIP, COMPOSER, RETURN_KEY, GLOBE, DICTATE]
    kept = candidate_pool.outside_keyboard(pool, KEYBOARD)
    bottom_most = max(kept, key=lambda i: pool[i][1])
    assert pool[bottom_most] == COMPOSER
    for key in (RETURN_KEY, GLOBE, DICTATE):
        assert key not in [pool[i] for i in kept]


def test_no_keyboard_excludes_nothing():
    """`None` means "no keyboard found", and the caller cannot tell that from
    "could not read one". Dropping every candidate would turn a missing
    keyboard into an empty screen — DEF366's shape, one file over."""
    pool = [CHIP, COMPOSER, GLOBE]
    assert candidate_pool.outside_keyboard(pool, None) == [0, 1, 2]


def test_a_collapsed_keyboard_excludes_nothing():
    """A keyboard mid-dismissal reports zero height. Without the explicit
    check its top edge is still a floor, and everything below it — the whole
    lower half of the screen — vanishes on an accident of timing."""
    collapsing = (0.0, 564.0, 402.0, 0.0)
    assert candidate_pool.is_occluded(GLOBE, collapsing) is False
    assert candidate_pool.outside_keyboard([CHIP, GLOBE], collapsing) == [0, 1]


def test_a_chip_overlapping_the_keyboard_top_survives_if_centred_above_it():
    """Centre, not top edge. This chip spans 530..578, so it crosses the
    keyboard's top at 564 — but its centre is at 554, above the floor, and a
    top-edge rule would discard the very control the walk is looking for."""
    overlapping = (16.0, 530.0, 151.0, 48.0)
    assert candidate_pool.center(overlapping)[1] == 554.0
    assert candidate_pool.is_occluded(overlapping, KEYBOARD) is False


def test_a_key_straddling_the_top_edge_is_judged_by_its_centre():
    """The mirror: starts above the floor (y=550 < 564), centred below it."""
    straddling = (12.0, 550.0, 36.0, 40.0)
    assert candidate_pool.center(straddling)[1] == 570.0
    assert candidate_pool.is_occluded(straddling, KEYBOARD) is True


@pytest.mark.parametrize("rect", [CHIP, COMPOSER])
def test_controls_above_the_floor_are_never_dropped(rect):
    assert candidate_pool.is_occluded(rect, KEYBOARD) is False


# ---------------------------------------------------------------------------
# The second half of DEF374: the composer is not a chip either.
# ---------------------------------------------------------------------------

COMPOSER_KIND = "XCUIElementTypeTextField"
BUTTON_KIND = "XCUIElementTypeButton"


def test_the_composer_is_not_a_candidate():
    """Tapped 180 times in the run after the keyboard keys were excluded: it
    carries a label, so `labelled_only=True` kept it, and it was then the
    bottom-most control left."""
    assert candidate_pool.is_text_input_kind(COMPOSER_KIND) is True
    assert candidate_pool.is_text_input_kind("XCUIElementTypeSecureTextField") is True
    assert candidate_pool.is_text_input_kind("android.widget.EditText") is True


def test_a_button_is_a_candidate():
    assert candidate_pool.is_text_input_kind(BUTTON_KIND) is False


def test_an_unreadable_kind_does_not_remove_a_candidate():
    """An attribute read that failed is not evidence the control is a text
    field. Dropping it would be DEF366's shape: 'cannot tell' collapsing into
    'exclude'."""
    assert candidate_pool.is_text_input_kind(None) is False
    assert candidate_pool.is_text_input_kind("") is False


def test_both_rules_apply_on_one_pool():
    """The bug was a guard present on one branch and absent on the other. This
    pins that a single call enforces both, and that what survives is the chip."""
    kinds = [BUTTON_KIND, COMPOSER_KIND, BUTTON_KIND, BUTTON_KIND]
    rects = [CHIP, COMPOSER, RETURN_KEY, GLOBE]
    kept = candidate_pool.selectable(kinds, rects, KEYBOARD)
    assert [rects[i] for i in kept] == [CHIP]


def test_the_bottom_most_survivor_is_the_chip():
    """The property `_live_chip` actually relies on."""
    kinds = [BUTTON_KIND, COMPOSER_KIND, BUTTON_KIND, BUTTON_KIND]
    rects = [CHIP, COMPOSER, RETURN_KEY, GLOBE]
    kept = candidate_pool.selectable(kinds, rects, KEYBOARD)
    assert rects[max(kept, key=lambda i: rects[i][1])] == CHIP
