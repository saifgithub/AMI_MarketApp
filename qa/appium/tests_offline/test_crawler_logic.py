"""Offline guards for the crawler's pure logic (CR163). No device, no Appium.

These cover the parts where being wrong is dangerous rather than merely broken:

- the destructive-control filter, which is all that stands between an autonomous
  crawler and tapping "delete" on a real Alpha account;
- fingerprint stability, which is what stops every run re-reporting every
  finding until nobody reads the report;
- the error-sink parse, which is the crawler's main source of findings and had
  its first implementation invalidated by measurement.
"""

from __future__ import annotations

import json

import pytest

from crawler.errorsink import SinkUnavailable, parse_sink, read_sink
from crawler.explorer import is_safe_to_tap, screen_fingerprint
from crawler.ledger import FALSE_POSITIVE, FILED, NEW, Ledger, fingerprint


# -- the destructive-control filter ---------------------------------------

@pytest.mark.parametrize("label", [
    "Delete account", "DELETE", "Sign out", "Log Out", "Reset progress",
    "Restart onboarding", "Buy 10 shares", "Subscribe", "Confirm trade",
    "Place order", "Sell all", "Close position", "Cancel subscription",
])
def test_destructive_controls_are_never_tapped(label):
    """The crawler drives a REAL Alpha account. This list is the only thing
    between it and destroying its own session or writing junk to a shared
    system, so it is asserted rather than trusted."""
    assert not is_safe_to_tap(label), f"{label!r} would be tapped by the crawler"


@pytest.mark.parametrize("label", [
    "Privacy policy", "Terms", "Contact support", "Open in browser",
])
def test_controls_that_leave_the_app_are_not_tapped(label):
    """Tapping these strands the crawler in Safari with no way back, silently
    ending the run's usefulness while it still burns budget."""
    assert not is_safe_to_tap(label)


@pytest.mark.parametrize("label", [
    "CONVENE THE ROOM", "PORTFOLIO", "Save for retirement", "Journal",
])
def test_ordinary_controls_are_tappable(label):
    assert is_safe_to_tap(label)


def test_unlabelled_controls_are_skipped_not_tapped():
    """An unlabelled control cannot be proven not to be 'delete'. The oracles
    report them separately, so this is a visible coverage gap, not a silent one."""
    assert not is_safe_to_tap("<unlabeled>")
    assert not is_safe_to_tap("   ")


def test_the_filter_is_case_and_substring_insensitive():
    assert not is_safe_to_tap("  dELeTe This Journal Entry  ")


# -- screen fingerprints ---------------------------------------------------

def test_screen_fingerprint_ignores_order_and_duplicates():
    """Two reads of the same screen must agree, or every screen looks new and
    the crawl never terminates."""
    a = screen_fingerprint(["Floor", "Portfolio", "Journal"])
    b = screen_fingerprint(["Journal", "Floor", "Portfolio", "Floor"])
    assert a == b


def test_different_controls_are_different_screens():
    assert screen_fingerprint(["Floor"]) != screen_fingerprint(["Settings"])


# -- the ledger ------------------------------------------------------------

def _finding(**kw):
    base = {"check": "render_overflow", "screen": "abc123", "detail": "42 pixels"}
    base.update(kw)
    return base


def test_fingerprint_is_stable_across_runs():
    assert fingerprint(_finding()) == fingerprint(_finding())


def test_fingerprint_distinguishes_rule_screen_and_detail():
    base = fingerprint(_finding())
    assert fingerprint(_finding(check="sparse_screen")) != base
    assert fingerprint(_finding(screen="other")) != base
    assert fingerprint(_finding(detail="8 pixels")) != base


def test_only_triaged_findings_are_suppressed(tmp_path):
    """A finding that was merely SEEN must keep being reported — it is still an
    open defect. Only an explicit triage decision silences it."""
    ledger = Ledger(tmp_path / "l.json")
    f = _finding()

    ledger.record(f, status=NEW)
    assert not ledger.is_suppressed(f), "seen-but-untriaged must still be reported"

    ledger.record(f, status=FILED, note="stub")
    assert ledger.is_suppressed(f)


def test_rejected_findings_never_come_back(tmp_path):
    """Without this, a false positive is rediscovered every night and the
    report degrades into noise."""
    ledger = Ledger(tmp_path / "l.json")
    f = _finding()
    ledger.record(f, status=FALSE_POSITIVE)
    fresh, known = ledger.split([f])
    assert fresh == [] and len(known) == 1


def test_ledger_round_trips_through_disk(tmp_path):
    path = tmp_path / "l.json"
    Ledger(path).record(_finding(), status=FILED) or Ledger(path)
    ledger = Ledger(path)
    ledger.record(_finding(), status=FILED)
    ledger.save()
    assert Ledger(path).is_suppressed(_finding())


# -- the error sink --------------------------------------------------------

def _record(message: str) -> str:
    return json.dumps({"kind": "flutter_error", "library": "rendering library",
                       "message": message, "full": message, "stack": "#0 foo"})


@pytest.mark.parametrize("message,rule,severity", [
    ("A RenderFlex overflowed by 42 pixels on the bottom.", "render_overflow", "high"),
    ("setState() called after dispose()", "setstate_after_dispose", "high"),
    ("Null check operator used on a null value", "null_check_operator", "high"),
    ("LateInitializationError: Field '_x' has not been initialized.", "late_not_initialized", "high"),
    ("Unable to load asset: assets/missing.png", "missing_asset", "medium"),
    ("RenderBox was not laid out", "layout_error", "high"),
])
def test_known_error_shapes_are_classified(message, rule, severity):
    findings = parse_sink(_record(message))
    assert len(findings) == 1
    assert findings[0]["rule"] == rule
    assert findings[0]["severity"] == severity


def test_unknown_errors_are_still_reported():
    """An unfamiliar error is more interesting than a familiar one, not less.
    Dropping what we do not recognise would hide exactly the novel defects the
    crawler exists to find."""
    findings = parse_sink(_record("Some entirely novel failure nobody has seen"))
    assert len(findings) == 1
    assert findings[0]["rule"] == "flutter_error"
    assert "novel failure" in findings[0]["detail"]


def test_a_truncated_final_line_does_not_lose_the_run():
    """The app can be killed mid-write. Losing one record beats losing the
    whole run's findings to a JSONDecodeError."""
    text = _record("A RenderFlex overflowed by 8 pixels on the right.") + "\n{ trunc"
    assert len(parse_sink(text)) == 1


def test_a_missing_sink_is_an_error_not_an_empty_result(tmp_path):
    """The critical one. If a missing sink read as 'no errors', every crawl
    against a mis-built app would report a clean bill of health — the silent
    degradation this project's conventions forbid."""
    with pytest.raises(SinkUnavailable, match="AMI_QA_SEMANTICS"):
        read_sink(tmp_path / "does_not_exist.jsonl")
