"""DEF366 — the iOS walk's escape detector must distinguish "cannot tell" from "fine".

**Why this lives in the backend suite rather than in `qa/appium/tests/`.** The
appium suite needs a booted simulator and an Appium server, so it runs rarely
and is currently red (DEF362) — a guard that only runs there is a guard that
does not run. This suite is what the promotion gate executes. The resolver was
extracted into `qa/appium/helpers/foreground.py`, which imports nothing, so it
loads here by file path with no selenium in the venv.

**The bug being guarded.** `_is_app_foreground` was `try: … except: return True`,
which made an unanswerable query indistinguishable from a healthy app. DEF362
burned two diagnosis rounds on a walk that sat at the iOS home screen for its
full 480s budget while the detector reported fine — and then blamed the app.
`CLAUDE.md`: *if this fires constantly and silently, what does the user end up
believing?*
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parents[3] / "qa" / "appium" / "helpers" / "foreground.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("_def366_foreground", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_M = _load()


def test_the_module_needs_no_appium_to_load():
    """The whole point of the extraction. If this file ever grows an import of
    selenium or the Appium client, this suite stops being able to run it and
    the guard silently leaves the gate."""
    import ast

    tree = ast.parse(_MODULE_PATH.read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    # Prose may name Appium — the docstring explains the bug. Only real
    # imports matter, so this walks the AST rather than grepping the text.
    assert imported <= {"__future__"}, imported


def test_the_app_in_front_reads_as_foreground():
    assert _M.resolve(lambda: 4) == _M.FOREGROUND


def test_any_other_state_reads_as_not_foreground():
    for state in (0, 1, 2, 3, 5):
        assert _M.resolve(lambda s=state: s) == _M.NOT_FOREGROUND, state


def test_a_failing_query_is_unknown_and_not_foreground():
    """THE regression. The old code returned True — 'we are fine' — from
    exactly this branch, and that is what let a walk report on an app it could
    not see."""
    def boom():
        raise RuntimeError("WDA session died")

    assert _M.resolve(boom) == _M.UNKNOWN
    assert _M.resolve(boom) != _M.FOREGROUND


def test_a_none_answer_is_unknown_not_a_measurement():
    """A driver that answers 'I don't know' in band. `None == 4` is False, so a
    naive implementation calls this NOT_FOREGROUND and manufactures an escape
    from an absent measurement — the DEF059 shape pointing the other way."""
    assert _M.resolve(lambda: None) == _M.UNKNOWN


def test_the_three_states_are_distinct():
    assert len({_M.FOREGROUND, _M.NOT_FOREGROUND, _M.UNKNOWN}) == 3


def test_the_caller_handles_unknown_separately_from_both_others():
    """The resolver being three-state buys nothing if the caller collapses it
    again. Asserted against the walk's source, because the loop itself needs a
    live driver to execute."""
    walk = (_MODULE_PATH.parent / "onboarding.py").read_text()
    assert "state == UNKNOWN" in walk
    assert "state == NOT_FOREGROUND" in walk
    # An UNKNOWN must not be counted as an escape: we have not established one.
    unknown_block = walk.split("if state == UNKNOWN:")[1].split("if state == NOT_FOREGROUND:")[0]
    assert "escapes += 1" not in unknown_block
    assert "blind += 1" in unknown_block
    # And it must fail with its own message rather than the app-blaming one.
    assert "could not observe whether the app under test" in unknown_block


def test_a_blind_walk_never_reports_on_onboarding():
    """The sentence that misled two rounds of diagnosis was 'onboarding did not
    reach Floor'. A walk that could not see the app must not produce it."""
    walk = (_MODULE_PATH.parent / "onboarding.py").read_text()
    unknown_block = walk.split("if state == UNKNOWN:")[1].split("if state == NOT_FOREGROUND:")[0]
    assert "did not reach Floor" not in unknown_block


def test_the_ios_escape_diagnostic_names_something():
    """`_foreground_package` was `driver.current_package`, Android-only by its
    own docstring, so every iOS escape could only report 'an unidentified app'
    — detection and explanation both shaped for the platform that was not
    failing."""
    walk = (_MODULE_PATH.parent / "onboarding.py").read_text()
    block = walk.split("def _foreground_package(")[1].split("\ndef ")[0]
    assert "is_ios(driver)" in block


def test_the_ios_keyboard_failure_is_no_longer_swallowed():
    """`POST /wda/keyboard/dismiss` returning 400 is the leading candidate for
    the backgrounding, and it was invisible because the except branch printed
    nothing."""
    gestures = (_MODULE_PATH.parent / "gestures.py").read_text()
    block = gestures.split("def hide_keyboard_if_shown(")[1].split("\ndef ")[0]
    assert "keyboard dismissal failed" in block
