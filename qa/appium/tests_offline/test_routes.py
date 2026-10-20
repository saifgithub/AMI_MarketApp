"""Offline guards for route-driving (CR264 phase C): the catalogue graph, path
planning, replay-step matching, seeding I/O and the spend gate. No device."""

from __future__ import annotations

import plistlib
import subprocess

import pytest

from config.semantics_ids import SCREEN_IDS
from crawler import controls as C
from crawler import routes as R
from crawler import seed
from crawler.exhaustive import _match, _OPTIONAL_STEPS
from crawler.intents import Catalogue, Intent, load_dir


def _it(screen, name, target, expect="navigate", when="", ident="", kind="button"):
    return Intent(screen, "" if ident else name, ident, kind, expect, target, "", when, 1, "x.dart")


def _node(label="", ident="", y=300):
    return C.Node("XCUIElementTypeButton", ident, label, "", 10, y, 100, 40, interactive=True)


@pytest.fixture(scope="module")
def real_graph():
    return R.build_graph(load_dir())


# -- graph over the real catalogue --------------------------------------------

def test_every_host_is_a_known_screen_or_dotted_surface():
    cat = load_dir()
    for widget, hosts in R.HOSTS.items():
        for h in hosts:
            assert h in SCREEN_IDS or h in cat.by_screen, f"{widget} -> unknown host {h}"


def test_every_nav_root_is_a_known_screen():
    for nav, screens in R.NAV_TO_ROOTS.items():
        assert all(s in SCREEN_IDS for s in screens), nav


def test_entry_notes_only_name_real_screens():
    for s in R.ENTRY_NOTES:
        assert s in SCREEN_IDS, s


def test_floor_children_are_reachable_from_the_floor_tab(real_graph):
    nav, edges = R.plan(real_graph, "ami.screen.inbox")
    assert nav == "ami.nav.floor" and len(edges) == 1
    nav, edges = R.plan(real_graph, "ami.screen.company_review")
    assert nav == "ami.nav.floor"


def test_journal_is_reached_through_the_you_segment(real_graph):
    nav, edges = R.plan(real_graph, "ami.screen.journal_detail")
    assert nav == "ami.nav.you"
    assert [e.dst for e in edges] == ["ami.screen.you.journal", "ami.screen.journal_detail"]
    assert edges[0].ident == "ami.you.journal"


def test_lesson_reader_goes_lessons_track_reader(real_graph):
    nav, edges = R.plan(real_graph, "ami.screen.lesson_reader")
    assert edges[-1].dst == "ami.screen.lesson_reader"
    first = R.plan(real_graph, "ami.screen.track_lessons")
    assert first[0] == "ami.nav.lessons" and [e.dst for e in first[1]] == ["ami.screen.track_lessons"]


def test_most_known_screens_have_a_route(real_graph):
    reach = R.reachable(real_graph)
    missing = [s for s in SCREEN_IDS if s not in reach and s not in R.ENTRY_NOTES
               and not s.startswith("ami.screen.games_")]
    # Anything here has neither a catalogue edge nor a stated reason: add one.
    assert missing == [] or all(R.explain_unreachable(real_graph, m) for m in missing)


# -- planning ---------------------------------------------------------------

def _tiny():
    cat = Catalogue([
        _it("ami.screen.floor", "A", "ami.screen.a"),
        _it("ami.screen.a", "B", "ami.screen.b", when="needs a holding"),
        _it("ami.screen.portfolio", "C", "ami.screen.b"),
        _it("ami.screen.b", "D", "ami.screen.c"),
        _it("ami.screen.x", "E", "ami.screen.d"),
    ])
    return R.build_graph(cat)


def test_unconditional_route_beats_shorter_conditional_one():
    nav, edges = R.plan(_tiny(), "ami.screen.b")
    assert nav == "ami.nav.portfolio" and [e.control for e in edges] == ["C"]


def test_banning_an_edge_replans_or_gives_up():
    g = _tiny()
    first = R.plan(g, "ami.screen.b")[1][0]
    nav, edges = R.plan(g, "ami.screen.b", banned=frozenset({first.key}))
    assert nav == "ami.nav.floor" and [e.control for e in edges] == ["A", "B"]
    both = frozenset({first.key, edges[1].key})
    assert R.plan(g, "ami.screen.b", banned=both) is None


def test_path_steps_start_with_the_tab_and_carry_wait_targets():
    nav, edges = R.plan(_tiny(), "ami.screen.c")
    steps = R.path_steps(nav, edges)
    assert steps[0] == {"nav": nav}
    assert all(s["strict"] and s["to"].startswith("ami.screen.") for s in steps[1:])


def test_unreachable_reasons_are_concrete():
    g = _tiny()
    assert "no control in the catalogue" in R.explain_unreachable(g, "ami.screen.nowhere")
    assert "themselves unreachable" in R.explain_unreachable(g, "ami.screen.d")
    assert "first-run" in R.explain_unreachable(g, "ami.screen.onboarding")
    assert "AMI_GAMES" in R.explain_unreachable(g, "ami.screen.games_run")
    e = R.plan(g, "ami.screen.b")[1][0]
    assert "route replay failed" in R.explain_unreachable(g, "ami.screen.b", failed={e.key: "step 'C' not found"})


def test_only_conditional_routes_name_the_precondition():
    cat = Catalogue([_it("ami.screen.floor", "A", "ami.screen.a", when="a holding exists")])
    assert "a holding exists" in R.explain_unreachable(R.build_graph(cat), "ami.screen.a")


# -- replay matching --------------------------------------------------------

def test_match_by_id_then_label_then_pattern():
    nodes = [_node("Something", "ami.x"), _node("Convene the room · AAPL"), _node("OK")]
    assert _match(nodes, {"ident": "ami.x"}).ident == "ami.x"
    assert _match(nodes, {"label": "OK", "type": "XCUIElementTypeButton"}).label == "OK"
    assert _match(nodes, {"pat": "convene the room"}) is None  # pattern is anchored
    assert _match(nodes, {"pat": "convene the room · <t>"}).label.startswith("Convene")


def test_match_follows_the_catalogue_entry_when_the_label_drifts():
    cat = Catalogue([_it("ami.screen.floor", "CONVENE THE ROOM", "ami.screen.convene_sheet")])
    nodes = [_node("CONVENE THE ROOM")]
    step = {"label": "CONVENE AGAIN", "screen": "ami.screen.floor", "intent": "CONVENE THE ROOM"}
    assert _match(nodes, step, cat).label == "CONVENE THE ROOM"


def test_placeholder_row_picks_first_unexplained_control_not_chrome():
    cat = Catalogue([_it("ami.screen.lessons", "Back", "ami.screen.floor", expect="back")])
    nodes = [_node("Back", y=60), _node("Foundations track", y=300), _node("Other", y=400)]
    step = {"row": True, "screen": "ami.screen.lessons"}
    assert _match(nodes, step, cat).label == "Foundations track"


def test_nav_step_never_falls_back_to_labels():
    assert _match([_node("ami.nav.floor")], {"nav": "ami.nav.floor"}) is None  # no ident set
    assert "not now" in _OPTIONAL_STEPS


# -- seeding ----------------------------------------------------------------

def test_read_device_user_id_from_plist(tmp_path, monkeypatch):
    prefs = tmp_path / "Library" / "Preferences"
    prefs.mkdir(parents=True)
    uid = "e448392a-61b2-4699-b782-4f866cf0d7d2"
    (prefs / "b.id.plist").write_bytes(plistlib.dumps({seed.DEVICE_USER_KEY: uid}))
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, str(tmp_path) + "\n", ""))
    assert seed.read_device_user_id("UDID", "b.id") == uid


def test_malformed_device_user_id_is_an_error_not_a_guess(tmp_path, monkeypatch):
    prefs = tmp_path / "Library" / "Preferences"
    prefs.mkdir(parents=True)
    (prefs / "b.id.plist").write_bytes(plistlib.dumps({seed.DEVICE_USER_KEY: "nope"}))
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, str(tmp_path), ""))
    with pytest.raises(RuntimeError):
        seed.read_device_user_id("UDID", "b.id")


class _FakeAdmin:
    def __init__(self, fail=()):
        self.calls, self.fail = [], fail

    def call(self, method, path, body=None, params=None):
        self.calls.append((method, path, body))
        if any(f in path for f in self.fail):
            raise RuntimeError("boom")
        return {}


def test_seed_user_sets_plan_credits_and_message_and_isolates_failures():
    a = _FakeAdmin()
    r = seed.seed_user(a, "u1")
    assert [c[1] for c in a.calls] == ["/v1/admin/users/u1/plan", "/v1/admin/users/u1/credits", "/v1/admin/messages"]
    assert a.calls[2][2]["audience"] == {"mode": "user", "user_ids": ["u1"]}  # one user, never a blast
    assert len(r.unlocked) == 3 and not r.notes
    b = _FakeAdmin(fail=("credits",))
    r = seed.seed_user(b, "u1")
    assert len(b.calls) == 3 and len(r.unlocked) == 2 and "credits failed" in r.notes[0]


def test_seeding_is_a_logged_noop_on_android():
    class P:
        platform = "android"
    r = seed.seed_for_crawl(P())
    assert r.unlocked == [] and "Android" in r.notes[0]


# -- spend gate -------------------------------------------------------------

def test_second_room_convene_is_budget_exempt():
    limits = C.load_spend_limits()
    n = _node("CONVENE THE ROOM")
    assert C.spend_group(limits, "ami.screen.floor", n, "destructive") == "room"
    assert C.spend_group(limits, "ami.screen.settings", _node("Notifications"), "navigate") is None
