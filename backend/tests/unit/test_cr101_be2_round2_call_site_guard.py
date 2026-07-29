"""CR101-BE2 round 2 — guard against a FIFTH `check_mandate_compliance` call site
reintroducing the round-1 BLOCKER (three of the four new limits silently off
because `room_runner.py` and `safety_floor.py`'s LLM-override wrapper never
supplied the context those limits need).

DERIVED, not hand-enumerated. `test_cr101_be1_settable_risk_caps.py`'s own
four-leg guard is a hand-listed checklist of Mandate FIELDS — DEF191 named that
gap explicitly: it did not "pick up" CR101-BE2's five new fields on its own, and
that same round-1 bridge recommended NOT hand-listing call sites the same way a
second time. This walks every `.py` file under `app/` with `ast`, finds every
CALL whose callee name is `check_mandate_compliance`, and asserts each one names
all four of CR101-BE2's context kwargs — regardless of what value is passed, only
that the caller did not simply forget to mention it. A sixth call site added
tomorrow is covered automatically; nothing here needs updating for it.
"""

from __future__ import annotations

import ast
import pathlib

import app as _app_pkg

_REQUIRED_CONTEXT_KWARGS = {
    "last_loss_closed_at",
    "trade_open_timestamps",
    "existing_open_risk_pct",
}
# `proposed_stop` is NOT required here. It only refines the open-risk cap with the
# proposed trade's OWN contribution; `existing_open_risk_pct` alone still fully
# evaluates the cap against already-open exposure. `sim_engine.preview()` omits it
# by a disclosed round-1 judgment call (no `stop` param on preview() at all,
# pre-CR101) — an ALREADY-breached cap still blocks in preview, only the
# proposal's own incremental contribution can't be priced there. Requiring it
# here would fail a call site that was never the round-1 BLOCKER's shape.


def _check_mandate_compliance_call_sites(root: pathlib.Path) -> list[tuple[pathlib.Path, ast.Call]]:
    sites: list[tuple[pathlib.Path, ast.Call]] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else (
                func.attr if isinstance(func, ast.Attribute) else None
            )
            if name == "check_mandate_compliance":
                sites.append((path, node))
    return sites


def test_every_check_mandate_compliance_call_site_supplies_the_full_context():
    app_root = pathlib.Path(_app_pkg.__file__).parent
    sites = _check_mandate_compliance_call_sites(app_root)

    # If this drops to zero, the AST walk itself broke — fail loud, not green
    # on an empty list (the exact silent-pass shape this guard exists to catch).
    assert len(sites) >= 3, (
        f"expected >=3 check_mandate_compliance call sites (sim_engine submit + "
        f"preview, room_runner scripted path, safety_floor's own LLM-override "
        f"forward), found {len(sites)} — the AST walk may be broken"
    )

    missing = []
    for path, node in sites:
        kw_names = {kw.arg for kw in node.keywords if kw.arg is not None}
        gap = _REQUIRED_CONTEXT_KWARGS - kw_names
        if gap:
            missing.append(f"{path.relative_to(app_root.parent.parent)}:{node.lineno} missing {sorted(gap)}")

    assert not missing, (
        "check_mandate_compliance call site(s) omit CR101-BE2 context kwargs — "
        "this is the round-1 BLOCKER shape (a set mandate field silently unenforced "
        "because a caller forgot the argument):\n" + "\n".join(missing)
    )
