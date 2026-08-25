"""DEF374 — what the onboarding walk is allowed to tap.

The walk picks the bottom-most labelled control as "the chip for the current
turn" (`onboarding._live_chip`). When the iOS software keyboard is up, its keys
ARE labelled controls and they ARE the bottom-most ones, so the walk taps a
keyboard key instead of the answer chip. Measured on 2026-08-25: **186 clicks
on one element whose label reads `Next keyboard`** — the globe key — across
three 480-second wedges.

DEF348 found this and fixed it by calling `driver.hide_keyboard()` first. That
call cannot work here: WebDriverAgent answers
`400 Did not know how to dismiss the keyboard` for a keyboard raised by a
Flutter text field — 57 times in a single run — and until DEF366 stopped
swallowing the exception, nothing said so. A fix that depends on a driver
capability the driver does not have is not a fix; it is a wish.

**The rule is a floor, not a bounding box, and that distinction was measured.**
The first cut of this file excluded candidates whose centre fell inside
`XCUIElementTypeKeyboard`'s own rect. It dropped 3 keys per iteration and the
walk still wedged 171 taps on the globe key, because on iOS 26 the globe and
dictation controls sit in a row BELOW that rect — they are keyboard chrome that
the keyboard element does not contain. So the test is now "is the candidate
centred at or below the keyboard's top edge", which needs no theory about which
controls the keyboard claims as its own: while the keyboard is up it owns the
bottom of the screen, and anything down there is either its chrome or occluded
by it. An occluded control is not tappable either way.

**The composer is not a chip either, and that was the second wedge.** With the
keyboard keys filtered out, the bottom-most labelled control became the text
field itself (`Type your answer…`) — tapped 180 times in one run. The walk had
a guard for that, `is_text_input`, but it was applied only in the fallback
branch; the primary branch filters `labelled_only=True`, and the composer
carries a label, so it sailed through. Same shape as the `labelled_only`
asymmetry `locators.interactive_elements` already documents for Android: a
guard that reads as present in the source and is absent on the path actually
taken. Both rules now live here, applied to one pool, on every branch.

The walk never types — it answers with chips — so excluding text inputs
outright is not a narrowing.

Imports nothing, for the same reason `foreground.py` imports nothing: the walk's
modules pull in Appium and selenium, so a guard over them would need a booted
simulator — and the appium suite is exactly what is broken here. Every branch
below is reachable from a plain tuple.
"""

from __future__ import annotations

Rect = tuple[float, float, float, float]  # x, y, width, height


def center(rect: Rect) -> tuple[float, float]:
    x, y, w, h = rect
    return x + w / 2.0, y + h / 2.0


def is_occluded(candidate: Rect, keyboard: Rect | None) -> bool:
    """Is the candidate at or below the keyboard's top edge?

    Centre rather than top edge: a chip row commonly sits flush against the
    keyboard, and judging by the candidate's own top would discard the very
    control the walk is looking for. Centre-below-the-floor discards a key and
    keeps its neighbour above.

    `keyboard is None` means no keyboard was found, which must exclude NOTHING —
    the caller cannot distinguish "no keyboard" from "could not read one", and
    silently dropping every candidate would turn a missing keyboard into an
    empty screen (the DEF366 shape, one file over).
    """
    if keyboard is None:
        return False
    _, ky, _, kh = keyboard
    if kh <= 0:
        # A keyboard mid-dismissal reports a collapsed rect. Treating its top
        # edge as a floor would exclude by an accident of timing.
        return False
    _, cy = center(candidate)
    return cy >= ky


def outside_keyboard(candidates: list[Rect], keyboard: Rect | None) -> list[int]:
    """Indices of the candidates the keyboard does not cover.

    Returns indices rather than rects so the caller can map straight back to
    its own WebElement list without re-reading a rect per candidate — those
    reads are what dominate the walk's runtime.
    """
    return [i for i, rect in enumerate(candidates) if not is_occluded(rect, keyboard)]


# Appium's names for a text-entry control, per platform. The walk answers the
# interview with chips and never calls `send_keys`, so a text input is never a
# thing it wants to tap — it only raises the keyboard that then hides the chips.
TEXT_INPUT_TYPES = frozenset(
    {"XCUIElementTypeTextField", "XCUIElementTypeSecureTextField"}
)


def is_text_input_kind(kind: str | None) -> bool:
    """iOS reports the control's `type`; Android reports a `class` containing
    `EditText`. `None` is not a text input — an unreadable attribute must not
    silently remove a candidate the walk needs (DEF366's shape)."""
    if not kind:
        return False
    return kind in TEXT_INPUT_TYPES or "EditText" in kind


def selectable(kinds, rects, keyboard):
    """Indices of the candidates `_live_chip` may choose from.

    One pool, both rules, no branch where only one of them applies.
    """
    return [
        i
        for i, (kind, rect) in enumerate(zip(kinds, rects))
        if not is_text_input_kind(kind) and not is_occluded(rect, keyboard)
    ]
