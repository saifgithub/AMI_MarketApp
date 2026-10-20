"""Offline guards for the exhaustive crawler's pure logic (CR264): snapshot
parsing, press verdicts, destructive classification, never_press and spend
budgets, coverage accounting, and the control-intent catalogue."""

from __future__ import annotations

import pytest

from crawler import controls as C
from crawler.intents import (
    Catalogue, IntentSchemaError, check_expectation, label_pattern, load_dir, validate_doc,
)


def _ios(*elements: str) -> str:
    return "<XCUIElementTypeApplication type='XCUIElementTypeApplication'>" + "".join(elements) + "</XCUIElementTypeApplication>"


def _el(typ="XCUIElementTypeButton", name="", label="", value="", x=10, y=100, w=100, h=40, **extra):
    attrs = "".join(f' {k}="{v}"' for k, v in extra.items())
    return (f'<{typ} type="{typ}" name="{name}" label="{label}" value="{value}" '
            f'x="{x}" y="{y}" width="{w}" height="{h}" visible="true" enabled="true"{attrs}/>')


def snap(*elements):
    return C.take(C.parse_snapshot(_ios(*elements), "ios"))


# -- snapshot / screen identity ---------------------------------------------

def test_screen_key_prefers_topmost_semantic_id_else_fingerprint():
    both = snap(_el("XCUIElementTypeOther", name="ami.screen.room"),
                _el("XCUIElementTypeOther", name="ami.screen.convene_sheet"),
                _el(label="CONVENE"))
    assert both.key == "ami.screen.convene_sheet"
    bare = snap(_el(label="A"), _el(label="B"))
    assert bare.key.startswith("fp:")
    assert bare.key == snap(_el(label="B", y=300), _el(label="A", y=10)).key  # order/position independent


def test_android_snapshot_parses_bounds_and_checkable():
    xml = ('<hierarchy><node class="android.widget.Switch" resource-id="ami.x" content-desc="Alerts" '
           'clickable="true" checkable="true" checked="false" bounds="[10,20][110,60]" enabled="true"/></hierarchy>')
    n = C.parse_snapshot(xml, "android")[0]
    assert (n.ident, n.label, n.cx, n.cy, n.interactive, n.is_toggle) == ("ami.x", "Alerts", 60, 40, True, True)


# -- press verdicts ------------------------------------------------------------

def test_dead_tap_when_nothing_changed():
    b = snap(_el(label="SAVE"))
    assert C.press_outcome(b, snap(_el(label="SAVE")), b.nodes[0]) == "dead"


def test_ticking_numbers_do_not_count_as_a_change():
    b = snap(_el("XCUIElementTypeStaticText", label="NVDA $912.40"), _el(label="SAVE"))
    a = snap(_el("XCUIElementTypeStaticText", label="NVDA $913.05"), _el(label="SAVE"))
    assert C.press_outcome(b, a, b.nodes[1]) == "dead"


def test_new_text_is_a_change_and_a_flipped_switch_is_a_toggle():
    b = snap(_el(label="MORE"))
    a = snap(_el(label="MORE"), _el("XCUIElementTypeStaticText", label="Expanded paragraph"))
    assert C.press_outcome(b, a, b.nodes[0]) == "changed"
    sw0 = snap(_el("XCUIElementTypeSwitch", label="Alerts", value="0"))
    sw1 = snap(_el("XCUIElementTypeSwitch", label="Alerts", value="1"))
    assert C.press_outcome(sw0, sw1, sw0.nodes[0]) == "toggled"


def test_navigation_and_sheet_outcomes():
    b = snap(_el("XCUIElementTypeOther", name="ami.screen.floor"), _el(label="GO"))
    n = snap(_el("XCUIElementTypeOther", name="ami.screen.room"))
    assert C.press_outcome(b, n, b.nodes[1]) == "navigated"
    s = snap(_el("XCUIElementTypeOther", name="ami.screen.floor"), _el("XCUIElementTypeOther", name="ami.sheet.convene"))
    assert C.press_outcome(b, s, b.nodes[1]) == "sheet"


def test_pressing_a_text_field_is_focus_not_a_dead_tap():
    b = snap(_el("XCUIElementTypeTextField", label="Ticker"))
    assert C.press_outcome(b, snap(_el("XCUIElementTypeTextField", label="Ticker")), b.nodes[0]) == "focused"


# -- classification / never_press / spend ---------------------------------------

@pytest.mark.parametrize("label,cls", [
    ("Delete account", "destructive"), ("Sign out", "destructive"), ("BUY", "destructive"),
    ("Privacy policy", "external"), ("JOURNAL", "safe"), ("", "unlabelled"),
])
def test_classification(label, cls):
    assert C.classify(C.Node("XCUIElementTypeButton", "", label, "", 0, 0, 10, 10, interactive=True)) == cls


def _n(label="", ident=""):
    return C.Node("XCUIElementTypeButton", ident, label, "", 0, 0, 10, 10, interactive=True)


def test_never_press_exact_scoped_and_substring():
    t = {"Send report": "r1", "ami.screen.upgrade_paywall#~buy": "r2", "~open settings": "r3"}
    assert C.never_press_reason("ami.screen.x", _n("send REPORT"), t) == "r1"
    assert C.never_press_reason("ami.screen.upgrade_paywall", _n("BUY (Trader)"), t) == "r2"
    assert C.never_press_reason("ami.screen.trade_ticket", _n("BUY"), t) is None  # scope respected
    assert C.never_press_reason("ami.screen.x", _n("Open Settings app"), t) == "r3"


def test_shipped_never_press_covers_paywall_and_bug_report():
    t = C.load_never_press()
    assert C.never_press_reason("ami.screen.upgrade_paywall", _n("BUY"), t)
    assert C.never_press_reason("ami.screen.upgrade_paywall", _n("Restore purchases"), t) is None
    assert C.never_press_reason("ami.screen.bug_report_sheet", _n("Send report"), t)


def test_spend_groups_room_budget_and_free_convene_sheet():
    lim = C.load_spend_limits()
    free = C.spend_group(lim, "ami.screen.floor", _n("CONVENE THE ROOM"), "sheet", "CONVENE THE ROOM", "ami.screen.convene_sheet")
    assert free is None  # opening the empty sheet spends nothing
    assert C.spend_group(lim, "ami.screen.convene_sheet", _n("CONVENE"), "destructive", "CONVENE") == "room"
    assert C.spend_group(lim, "ami.screen.room", _n("TRY AGAIN"), "destructive") == "room"
    assert C.spend_group(lim, "ami.screen.convene_sheet", _n("NVDA"), "navigate",
                         "<suggested ticker chip: AAPL / MSFT>", "ami.screen.room") == "room"
    assert C.spend_group(lim, "ami.screen.one_on_one", _n("send"), "destructive") == "one_on_one"
    assert C.spend_group(lim, "ami.screen.brief", _n("send"), "destructive") == "brief"
    assert C.spend_group(lim, "ami.screen.floor", _n("JOURNAL"), "navigate") is None


# -- coverage accounting ----------------------------------------------------------

def test_coverage_gate_lists_every_failure_kind():
    cov = C.Coverage(["ami.screen.a", "ami.screen.b"])
    cov.see_screen("ami.screen.a", path=["nav"])
    pressed, skipped, exempt, bad = (cov.discover("ami.screen.a", _n(l), "button") for l in "wxyz")
    cov.mark(pressed, "navigated")
    cov.exempt(exempt, "never_press: purchase")
    cov.mark(bad, "dead", finding="dead tap")
    fails = cov.gate_failures(["extra"])
    assert "screen not reached: ami.screen.b" in fails
    assert any(f.startswith("control not pressed") and "|x|" in f for f in fails)
    assert any("dead tap" in f for f in fails) and "extra" in fails
    assert not any("|w|" in f or "|y|" in f for f in fails)
    t = cov.totals()
    assert (t["controls_discovered"], t["controls_pressed"], t["controls_exempt"], t["controls_unpressed"]) == (4, 2, 1, 1)


def test_control_ids_are_stable_across_digit_and_newline_changes():
    a = C.control_id("s", _n("3 unread messages\n3"))
    b = C.control_id("s", _n("1 unread messages\n1"))
    assert a == b and "\n" not in a


def test_expected_screens_read_dynamically_from_a_module():
    import types
    m = types.SimpleNamespace(A="ami.screen.floor", B={"x": "ami.screen.room"}, C=("ami.nav.floor",), _p="ami.screen.hidden")
    assert C.expected_screens_from(m) == ["ami.screen.floor", "ami.screen.room"]


# -- intent catalogue -----------------------------------------------------------------

DOC = {
    "screen": "ami.screen.journal_detail", "source": "mobile/lib/x.dart",
    "controls": [
        {"label": "SEE CHART", "kind": "button", "expect": "navigate", "target": "ami.screen.chart_fullscreen", "when": "entry has a ticker"},
        {"id": "ami.journal.pending", "label": "PENDING", "kind": "chip", "expect": "state", "state": "PENDING chip selected"},
        {"label": "send (arrow_upward icon)", "kind": "icon", "expect": "destructive"},
        {"label": "Share", "kind": "icon", "expect": "external"},
        {"label": "back (arrow_back icon)", "kind": "icon", "expect": "back"},
    ],
}


def _cat():
    intents, errs = validate_doc(DOC, "t.yaml")
    assert not errs
    return Catalogue(intents)


def test_schema_reports_every_problem_at_once():
    bad = {"screen": "floor", "controls": [
        {"label": "A", "kind": "weird", "expect": "navigate"},
        {"kind": "button", "expect": "none"},
        {"label": "C", "kind": "chip", "expect": "state"},
    ]}
    _, errs = validate_doc(bad, "bad.yaml")
    joined = "\n".join(errs)
    for needle in ("`screen`", "`source`", "kind 'weird'", "needs `target`", "needs a `label` or an `id`", "needs a human-readable `state`"):
        assert needle in joined, needle


def test_load_dir_raises_on_malformed_and_tolerates_missing(tmp_path):
    assert len(load_dir(tmp_path / "nope")) == 0
    (tmp_path / "x.yaml").write_text("screen: nope\ncontrols: []\n")
    with pytest.raises(IntentSchemaError):
        load_dir(tmp_path)


def test_lookup_by_id_label_description_and_placeholder():
    c = _cat()
    s = "ami.screen.journal_detail"
    assert c.lookup(s, "ami.journal.pending", "whatever").expect == "state"
    assert c.lookup(s, "", "see chart").expect == "navigate"
    assert c.lookup(s, "", "send").expect == "destructive"          # "(arrow_upward icon)" stripped
    assert c.lookup("ami.screen.other", "", "SEE CHART") is not None  # widget entries render inside other screens
    assert c.lookup(s, "", "unheard of") is None
    assert label_pattern("CONVENE THE ROOM · <TICKER>").fullmatch("convene the room · nvda")
    assert not label_pattern("<AdMob native ad body>").fullmatch("anything")


def test_expectations_navigate_state_back_external_and_precondition():
    c = _cat()
    s = "ami.screen.journal_detail"
    before = snap(_el("XCUIElementTypeOther", name=s), _el(label="SEE CHART"))
    chart = snap(_el("XCUIElementTypeOther", name="ami.screen.chart_fullscreen"))
    room = snap(_el("XCUIElementTypeOther", name="ami.screen.room"))

    nav = c.lookup(s, "", "SEE CHART")
    assert check_expectation(nav, before, chart, left_app=False, prev_key=None).status == "ok"
    v = check_expectation(nav, before, room, left_app=False, prev_key=None)
    # `when:` set => an unmet expectation is a precondition problem, not a failure
    assert v.status == "precondition_not_met" and "ami.screen.chart_fullscreen" in v.detail and "ami.screen.room" in v.detail

    strict = c.lookup(s, "", "Share")
    assert check_expectation(strict, before, before, left_app=False, prev_key=None).status == "mismatch"
    assert check_expectation(strict, before, before, left_app=True, prev_key=None).status == "ok"

    back = c.lookup(s, "", "back")
    parent = snap(_el("XCUIElementTypeOther", name="ami.screen.journal"))
    assert check_expectation(back, before, parent, left_app=False, prev_key="ami.screen.journal").status == "ok"
    assert check_expectation(back, before, before, left_app=False, prev_key="ami.screen.journal").status == "mismatch"

    st = c.lookup(s, "ami.journal.pending", "")
    changed = snap(_el("XCUIElementTypeOther", name=s), _el(label="SEE CHART"), _el("XCUIElementTypeStaticText", label="PENDING selected"))
    assert check_expectation(st, before, changed, left_app=False, prev_key=None).status == "ok"
    assert check_expectation(st, before, before, left_app=False, prev_key=None).status == "mismatch"

    destructive = c.lookup(s, "", "send")
    assert check_expectation(destructive, before, before, left_app=False, prev_key=None).status == "ok"


def test_real_catalogue_on_main_validates_if_present():
    """The catalogue is written by other lanes; if it is on this branch it must
    load. Duplicates are warnings, not failures."""
    cat = load_dir()
    assert isinstance(cat.warnings, list)


def test_system_keyboard_keys_are_not_controls_and_do_not_change_the_screen():
    kb = _el("XCUIElementTypeKeyboard", y=500, h=300)
    key = _el(label="Next keyboard", y=760, h=40)
    base = snap(_el(label="GO"))
    with_kb = snap(_el(label="GO"), kb, key)
    assert [n.label for n in with_kb.nodes] == ["GO"]
    assert base.key == with_kb.key


def test_chip_placeholder_lists_literal_labels_and_counts_as_room_spend():
    assert label_pattern("<suggested ticker chip: AAPL / MSFT / NVDA>").fullmatch("msft")
    lim = C.load_spend_limits()
    assert C.spend_group(lim, "fp:x", _n("TSLA"), None) == "room"
