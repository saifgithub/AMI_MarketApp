"""DEF551: read the Execution Desk's stated trade horizon out of its turn.

Why it exists. The runner's `trader_horizon_weeks` is a constant (6) that nothing ever replaced
with what the desk said, so every consumer of "the trade's horizon" read 42 days while the desks'
own plans said 57 to 210 days. The desk states it on a `Time horizon:` line of its money block
(`room_prompts.trader_block_regex` allows up to 24 free-text characters there: "8 weeks",
"6-8 weeks", "3 months", "90 days", "until the Q3 print"). This module turns that line into days
or says it cannot; it never guesses. Pure, no I/O.

A range reads as its upper end: the trade is allowed to run that long, and the one consumer that
needs a horizon for a decision (the `debt_default` materiality check) takes the larger of this and
the mandate's own horizon, so a longer reading is the conservative one.
"""

from __future__ import annotations

import re

MIN_DAYS = 1
MAX_DAYS = 5 * 365

_LINE = re.compile(r"(?im)^[ \t*_>-]*Time horizon:[ \t*_]*([^\n]{1,80})")
_NUM = r"(\d+(?:\.\d+)?)\+?"
_UNIT = (
    r"(?P<unit>days?|d|weeks?|wks?|w|months?|mos?|mths?|quarters?|qtrs?|years?|yrs?|y)\b"
)
_RANGE = re.compile(
    rf"{_NUM}\s*(?:-|–|—|to)\s*{_NUM}\s*{_UNIT}", re.IGNORECASE,
)
_SINGLE = re.compile(rf"{_NUM}\s*{_UNIT}", re.IGNORECASE)

_DAYS_PER_UNIT = {"d": 1.0, "w": 7.0, "m": 365.0 / 12.0, "q": 365.0 / 4.0, "y": 365.0}


def _unit_days(unit: str) -> float:
    u = unit.lower()
    if u.startswith("d"):
        return _DAYS_PER_UNIT["d"]
    if u.startswith("w"):
        return _DAYS_PER_UNIT["w"]
    if u.startswith("m"):
        return _DAYS_PER_UNIT["m"]
    if u.startswith("q"):
        return _DAYS_PER_UNIT["q"]
    return _DAYS_PER_UNIT["y"]


def parse_stated_horizon_days(text: str | None) -> int | None:
    """The horizon a phrase states, in whole days, or None when it states none the code can read
    ("until the Q3 print", "TBD", empty) or one outside 1 day to 5 years. A range reads as its
    upper end."""
    if not text:
        return None
    found: list[float] = [
        max(float(m.group(1)), float(m.group(2))) * _unit_days(m.group("unit"))
        for m in _RANGE.finditer(text)
    ]
    found += [float(m.group(1)) * _unit_days(m.group("unit")) for m in _SINGLE.finditer(text)]
    if not found:
        return None
    days = int(round(max(found)))
    return days if MIN_DAYS <= days <= MAX_DAYS else None


def stated_horizon_line(turn_text: str | None) -> str | None:
    """The text after the last `Time horizon:` label in a desk turn, or None when it has none."""
    found = _LINE.findall(turn_text or "")
    return found[-1].strip() if found else None


def desk_horizon_days(turn_text: str | None) -> tuple[int | None, str | None]:
    """(days, the phrase read). Days is None when the turn has no line or the line is unreadable;
    the phrase is returned either way so the caller can record what was there."""
    phrase = stated_horizon_line(turn_text)
    return parse_stated_horizon_days(phrase), phrase
