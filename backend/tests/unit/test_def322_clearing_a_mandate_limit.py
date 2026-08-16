"""DEF322 — "cannot remove mandate", and the two different things that means.

Three identical user reports inside one minute on `0.1.0+68` (2026-08-06),
categorised `2× ui_glitch + 1× other`. Three in a minute is one person tapping
the same control repeatedly because nothing happened.

Traced end to end, there are two separate questions behind that sentence and
only one of them is a defect:

**1. Removing a LIMIT — works, and was untested.** Setting a risk limit back to
"follow your risk profile" is a PATCH of an explicit `null`, and every layer has
to preserve it: `_deep_merge` replaces the scalar rather than skipping a falsy
value, `Mandate.model_validate` accepts `None` for each of these fields, and the
client keeps the key in `_pendingRiskLimits` so `updates` carries `{"key": null}`
rather than omitting it. Verified by probe before this file existed — set four
limits, clear all four, read them back as `None`. Nothing pinned it, which for a
user-facing "turn this off" control is the gap worth closing here.

The null is load-bearing in a way a truthy check silently breaks: `None` means
*unenforced / follow the preset* and `0` means *hard zero*, so a merge that
treated `None` as "no change" would leave a limit the user believes they removed
still enforcing. That is the DEF197 shape one layer down.

**2. Removing the MANDATE ITSELF — genuinely impossible, and not a code defect.**
There is no `DELETE /v1/mandate/{user_id}`, no reset control anywhere in
`mobile/lib`, and restarting onboarding does not clear it. DEF152/DEF158 traced
exactly this from the other side: the restart dialog used to promise it *"clears
the mandate your interview produced"*, and that claim was false **specifically for
the users who had a mandate to lose** — `reset()` clears a SharedPreferences flag
and in-memory state with no API call, `_bind_onboarding_session` skips when a
mandate row already exists, and the readback preview is never PATCHed. `+68` is
the era of that copy. A user who read it, restarted, and found the mandate
unchanged would report precisely this, three times in a minute.

DEF158 fixed the copy and said the rest was a product question, not a copy
question. It still is: whether a mandate should be removable at all is Saiful's
call, and a defect ticket is the wrong container for it.

So this file pins the half that is behaviour. The other half is a decision.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.services.mandate_store import get_mandate_store


_CLEARABLE = (
    ("single_name_cap_pct", 12.5),
    ("sector_cap_pct", 30.0),
    ("max_open_positions", 4),
    ("max_trades_per_day", 3),
    ("max_trades_per_week", 9),
    ("max_open_risk_pct", 25.0),
    ("post_loss_cooldown_hours", 6.0),
)


def test_every_clearable_limit_goes_back_to_following_the_profile():
    """Set them all, clear them all, read them back.

    One test over the whole set rather than seven: they share a merge path, and
    a regression here would be in `_deep_merge` or in re-validation, not in one
    field. A per-field test would report the same fault seven times.
    """
    store = get_mandate_store()
    user_id = uuid4()

    store.patch(user_id, {k: v for k, v in _CLEARABLE})
    was = store.get(user_id)
    assert [getattr(was, k) for k, _ in _CLEARABLE] == [v for _, v in _CLEARABLE], (
        "precondition: the limits must be set before clearing means anything"
    )

    store.patch(user_id, {k: None for k, _ in _CLEARABLE})
    now = store.get(user_id)

    still_set = [k for k, _ in _CLEARABLE if getattr(now, k) is not None]
    assert not still_set, f"the user turned these off and they stayed on: {still_set}"


@pytest.mark.parametrize("field", ["single_name_cap_pct", "max_open_positions"])
def test_zero_is_not_the_same_as_off(field):
    """The distinction a truthy merge would erase, and the reason clearing has
    to travel as an explicit `null`.

    `None` means *unenforced — follow the risk-profile preset*. `0` means *a hard
    zero*: no position in one name, or no open positions at all. A merge written
    as `if updates.get(k):` would treat both as "no change" and leave a limit the
    user believes they removed still enforcing — silently, which is the failure
    mode this project files as degrade-loudly (CR040).
    """
    store = get_mandate_store()
    user_id = uuid4()

    store.patch(user_id, {field: 0})
    assert getattr(store.get(user_id), field) == 0, "0 was swallowed as falsy"

    store.patch(user_id, {field: None})
    assert getattr(store.get(user_id), field) is None, "None did not clear"


def test_there_is_still_no_way_to_remove_the_mandate_itself():
    """Pinned as a KNOWN GAP, not as an assertion that the gap is correct.

    `get_or_default` returns a default without persisting, so "no mandate" and
    "a default mandate" are indistinguishable to every reader — which is why
    there is nothing to delete and why the restart dialog could claim to clear
    something it never touched (DEF152/DEF158). If a future CR adds a reset, this
    test is the one that should go red and be rewritten, rather than the gap
    being discovered again from a bug report.
    """
    from app.api import mandate as mandate_api

    routes = {
        (r.path, m)
        for r in mandate_api.router.routes
        for m in getattr(r, "methods", set())
    }
    assert not [p for p, m in routes if m == "DELETE"], (
        "a DELETE route appeared — the product gap this pins has been closed, "
        "so rewrite this test around the new behaviour"
    )
