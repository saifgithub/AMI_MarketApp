"""CR208 / ISS002 — the wire-contract machinery, guarded without a suite run.

The live check (`backend/scripts/wire_contract/verify.py`) needs a full backend
run to produce its capture, so it cannot be a unit test. Its *logic* can be, and
must be: the machinery decides whether a client/server disagreement is reported
at all, and a comparator that quietly returns PASS is indistinguishable from a
codebase with no problems.

These exercise the four states, the mandatory branch-conditional correction, and
the ratchet — each against fixtures, so they run in milliseconds and fail for
one reason each.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pytest

_WC = Path(__file__).resolve().parents[2] / "scripts" / "wire_contract"
sys.path.insert(0, str(_WC))

import branch_scan  # noqa: E402
import compare  # noqa: E402
import unreachable  # noqa: E402
from dart_keys import ClassContract  # noqa: E402


# --------------------------------------------------------------------------
# The mandatory correction: a branch-conditional key is not a missing one.
# --------------------------------------------------------------------------

def test_a_key_the_server_can_emit_is_not_reported_absent():
    """`order` is THE case this correction exists for. `sim.py` emits it on the
    `resting: True` branch only; 21 captured submissions never rested, and the
    prototype called that a FAIL. It is not one — both sides are correct."""
    absent, conditional = branch_scan.classify_missing(["order"])
    assert conditional == ["order"]
    assert absent == []


def test_a_key_nothing_emits_is_reported_absent():
    absent, conditional = branch_scan.classify_missing(["zzz_no_such_key_anywhere"])
    assert absent == ["zzz_no_such_key_anywhere"]
    assert conditional == []


def test_the_scan_does_not_wave_everything_through():
    """If `server_may_emit` returned True for anything, the correction would
    downgrade every real failure and the guard would be decorative."""
    assert branch_scan.server_may_emit("qqq_definitely_not_a_field") is False
    assert branch_scan.server_may_emit("") is False


# --------------------------------------------------------------------------
# The comparator's four states.
# --------------------------------------------------------------------------

def _pair(is_list=False, envelope_key=None):
    return {
        "dart_method": "m", "verb": "GET", "url_template": "/v1/thing",
        "url_regex": r"^/v1/thing$", "dart_class": "Thing", "is_list": is_list,
        "envelope_key": envelope_key,
    }


def _cap(body, status=200, path="/v1/thing", method="GET"):
    return [{"method": method, "path": path, "status": status, "body": body}]


def _idx(required=(), alts=(), nested=None):
    return {"Thing": ClassContract(
        class_name="Thing", file="thing.dart",
        required_keys=set(required), alt_groups=[set(a) for a in alts],
        nested_lists=nested or {},
    )}


def test_every_key_observed_is_a_pass():
    r = compare.check_pair(_pair(), _cap({"a": 1, "b": 2}), _idx(required=["a", "b"]))
    assert r["status"] == "PASS"


def test_an_unobservable_endpoint_is_unverified_not_pass():
    """DEF169/DEF190: an unevaluable check must not silently pass."""
    r = compare.check_pair(_pair(), [], _idx(required=["a"]))
    assert r["status"] == "UNVERIFIED"
    assert r["observations"] == 0


def test_an_error_response_is_not_an_observation():
    """A 500 body proves nothing about the success shape the client parses.

    The required key here is one nothing can emit, deliberately: if error
    bodies were counted as observations this would read FAIL (the key is
    genuinely absent from `{"detail": "boom"}`), and with them excluded it
    reads UNVERIFIED. A key the server *can* emit lands on UNVERIFIED either
    way and would let the bug through — which is exactly what the first
    version of this test did."""
    r = compare.check_pair(
        _pair(),
        _cap({"detail": "boom"}, status=500),
        _idx(required=["zzz_no_such_key_anywhere"]),
    )
    assert r["status"] == "UNVERIFIED"
    assert r["observations"] == 0


def test_a_key_nothing_can_emit_is_a_fail():
    r = compare.check_pair(
        _pair(), _cap({"a": 1}), _idx(required=["a", "zzz_no_such_key_anywhere"])
    )
    assert r["status"] == "FAIL"
    assert r["missing_and_unemittable"] == ["zzz_no_such_key_anywhere"]


def test_a_branch_conditional_key_downgrades_to_unverified():
    """The whole point of the correction, at comparator level rather than in
    isolation: the surface must not read FAIL."""
    r = compare.check_pair(_pair(), _cap({"a": 1}), _idx(required=["a", "order"]))
    assert r["status"] == "UNVERIFIED"
    assert r["missing_but_branch_conditional"] == ["order"]
    assert r["missing_and_unemittable"] == []


def test_an_alt_group_needs_only_one_spelling():
    """`j['a'] ?? j['b']` means either satisfies the client."""
    r = compare.check_pair(_pair(), _cap({"b": 2}), _idx(alts=[["a", "b"]]))
    assert r["status"] == "PASS"


def test_a_list_endpoint_is_read_element_wise():
    r = compare.check_pair(_pair(is_list=True), _cap([{"a": 1}, {"a": 2}]), _idx(required=["a"]))
    assert r["status"] == "PASS"
    assert r["observations"] == 2


def test_a_nested_list_class_is_checked_one_level_down():
    """DEF365's exact shape: SimPortfolio -> `options` -> SimOptionLeg."""
    idx = _idx(required=["legs"], nested={"legs": "Leg"})
    idx["Leg"] = ClassContract(class_name="Leg", file="thing.dart",
                               required_keys={"zzz_no_such_key_anywhere"})
    r = compare.check_pair(_pair(), _cap({"legs": [{"other": 1}]}), idx)
    assert any(n["status"] == "FAIL" for n in r["nested"])


def test_an_always_empty_nested_list_is_unverified():
    """An empty list proves nothing about the shape of its elements."""
    idx = _idx(required=["legs"], nested={"legs": "Leg"})
    idx["Leg"] = ClassContract(class_name="Leg", file="thing.dart", required_keys={"x"})
    r = compare.check_pair(_pair(), _cap({"legs": []}), idx)
    assert all(n["status"] == "UNVERIFIED" for n in r["nested"])


def test_a_class_with_no_factory_is_skipped_not_passed():
    r = compare.check_pair(_pair(), _cap({"a": 1}), {})
    assert r["status"] == "SKIP"


# --------------------------------------------------------------------------
# Discovery and Layer 3, against the real repo.
# --------------------------------------------------------------------------

def test_discovery_finds_the_real_surfaces_without_anything_declared():
    """The bar ISS002 set: no human declares a pair. If this collapses, the
    gate silently checks nothing — the P21 shape."""
    from discover_pairs import discover
    pairs = discover()
    assert len(pairs) >= 60, (
        f"only {len(pairs)} (endpoint -> Dart class) pairs discovered from "
        "api_client.dart; 85 were found on 2026-08-25. A collapse means the "
        "extractor stopped matching, not that the app shrank."
    )


def test_every_dart_wire_model_is_parsed_by_something():
    """Layer 3. Currently finds zero — recorded so a future zero is a
    measurement rather than an assumption."""
    assert unreachable.find_unreachable() == []


def test_layer_three_counts_a_tear_off_as_a_caller():
    """`.map(GameBoardRow.fromJson)` has no parentheses. Requiring them
    reported GameBoardRow as dead while `games.dart` parsed with it on every
    board fetch — a false positive found by hand before it was believed."""
    sources = {Path("x.dart"): "factory Foo.fromJson(j) => Foo();",
               Path("y.dart"): "rows.map(Foo.fromJson).toList();"}
    assert unreachable.callers("Foo", sources) == 1


@pytest.mark.parametrize("key", ["order", "total_value"])
def test_known_real_keys_are_emittable(key):
    """Sanity on the scan's own corpus: if it could not see the server at all,
    every key would look unemittable and every surface would read FAIL."""
    assert branch_scan.server_may_emit(key) is True


# --------------------------------------------------------------------------
# DEF367 — two instrument defects found while working the unverified baseline.
# Both made the count mean something other than "outstanding coverage debt".
# --------------------------------------------------------------------------

def test_an_envelope_wrapped_list_is_read_through_the_key_the_client_reads():
    """Five surfaces sat in the unverified baseline while the suite exercised
    their routes 1-9 times each. The client reads `r.data['items']`; the
    comparator dereferenced the BODY as a list, and `{"items": [...]}` is not a
    list, so it saw zero objects and reported "endpoint never observed". They
    were unverifiable, not uncovered — a baseline entry no test could close,
    which is worse than an uncovered surface because it stops the next reader
    looking."""
    r = compare.check_pair(
        _pair(is_list=True, envelope_key="items"),
        _cap({"items": [{"a": 1}, {"a": 2}], "total": 2}),
        _idx(required=["a"]),
    )
    assert r["status"] == "PASS"
    assert r["observations"] == 2


def test_a_missing_envelope_key_is_unverified_not_passed():
    """The key is the client's own navigation, so its absence is a real
    disagreement — the client would have taken `?? const []` and rendered an
    empty list. Falling back to "read the body as a list" here would turn a
    server that stopped emitting `items` into a silent pass."""
    r = compare.check_pair(
        _pair(is_list=True, envelope_key="items"),
        _cap({"renamed": [{"a": 1}], "total": 1}),
        _idx(required=["a"]),
    )
    assert r["status"] == "UNVERIFIED"
    assert r["observations"] == 0


def test_a_bare_list_body_still_works_without_an_envelope_key():
    """The envelope path is additive. A route that answers a bare JSON array
    must keep verifying exactly as before."""
    r = compare.check_pair(
        _pair(is_list=True), _cap([{"a": 1}]), _idx(required=["a"]),
    )
    assert r["status"] == "PASS"
    assert r["observations"] == 1


def test_the_ratchet_counts_duplicate_surface_ids_separately():
    """`api_client.dart::gamesRecordPrs` parses `GamePersonalRecord` twice from
    `GET /v1/games/record/prs` — once as a list, once as a scalar. Same
    `surface_id`, two different checks. Loaded as a SET, one could become
    verified while the other stayed unverified and neither the NEW nor the
    RECOVERED comparison would fire, because the id is present on both sides.
    """
    import verify  # noqa: PLC0415 — imported here so the _WC path insert applies

    sid = "GET /v1/games/record/prs -> GamePersonalRecord"
    baseline = Counter({sid: 2})
    # Exactly one of the two got a real response this run.
    unverified = [sid]
    recovered = sorted((baseline - Counter(unverified)).elements())
    assert recovered == [sid], (
        "half a duplicated surface recovered and the ratchet did not notice — "
        "the baseline would keep claiming two outstanding where one remains"
    )
    # And the loader really does hand back a multiset — asserting the
    # annotation would pass over a function that still returns a set.
    loaded = verify._load_baseline()
    assert isinstance(loaded, Counter)
    assert loaded[sid] == 2, (
        "the live baseline has lost the duplicate; if that was intentional the "
        "count changed and this guard should be updated deliberately"
    )


def test_the_baseline_holds_the_duplicate_twice():
    """The measured shape this guards. If discovery ever collapses the two call
    sites into one, this reds and the baseline should lose an entry — which is
    a real change to what the gate covers, not a formatting detail."""
    import json as _json
    from pathlib import Path as _Path

    baseline = _json.loads(
        (_WC / "unverified_baseline.json").read_text()
    )["unverified"]
    assert baseline.count("GET /v1/games/record/prs -> GamePersonalRecord") == 2
    assert len(baseline) == _json.loads(
        (_WC / "unverified_baseline.json").read_text()
    )["count"], "the stated count must be the multiset size, not the unique count"
    assert _Path(_WC / "unverified_baseline.json").exists()


def test_an_empty_capture_is_refused_not_read_as_82_blind_spots(tmp_path, monkeypatch, capsys):
    """`conftest.py` truncates and rewrites the capture on every pytest session,
    so running one test file leaves a present, near-empty capture behind. The
    existing guard checked that the file EXISTS, which is not how it breaks.
    Measured: a 0-row capture reported every one of the 82 surfaces as
    UNVERIFIED — exactly the wrong-reason failure the missing-file branch is
    written to prevent."""
    import verify  # noqa: PLC0415

    empty = tmp_path / "_wire_capture.jsonl"
    empty.write_text("")
    monkeypatch.setattr(verify, "CAPTURE", empty)
    monkeypatch.setattr(sys, "argv", ["verify.py"])
    assert verify.main() == 1
    out = capsys.readouterr().out
    assert "EMPTY" in out
    assert "UNVERIFIED" not in out, (
        "an empty capture must not produce a surface tally at all — printing "
        "one invites reading it as a measurement"
    )


def test_update_baseline_refuses_to_add(tmp_path, monkeypatch, capsys):
    """The baseline file's own comment says 'do not add an entry to get a build
    past the gate'. That was a request. One `--update-baseline` run against a
    truncated capture turned a 40-entry ratchet into an 82-entry rubber stamp in
    a single command, and printed a success message. A ratchet only shrinks."""
    import verify  # noqa: PLC0415

    baseline = tmp_path / "unverified_baseline.json"
    baseline.write_text(json.dumps({"count": 1, "unverified": ["GET /a -> A"]}))
    capture = tmp_path / "_wire_capture.jsonl"
    capture.write_text(json.dumps(
        {"method": "GET", "path": "/nope", "status": 200, "body": {}}) + "\n")
    monkeypatch.setattr(verify, "BASELINE", baseline)
    monkeypatch.setattr(verify, "CAPTURE", capture)
    monkeypatch.setattr(verify, "run", lambda _p: [
        {"class": "A", "endpoint": "/a", "verb": "GET", "status": "UNVERIFIED"},
        {"class": "B", "endpoint": "/b", "verb": "GET", "status": "UNVERIFIED"},
    ])
    monkeypatch.setattr(verify, "find_unreachable", lambda: [])
    monkeypatch.setattr(sys, "argv", ["verify.py", "--update-baseline"])

    before = baseline.read_text()
    assert verify.main() == 1
    assert baseline.read_text() == before, "the baseline was written despite the refusal"
    assert "REFUSED" in capsys.readouterr().out


def test_update_baseline_still_allows_a_shrink(tmp_path, monkeypatch):
    """The refusal must not wedge the gate shut. Removing a recovered surface is
    the whole point of the mechanism and has to stay a one-command operation —
    a guard whose failing state is its normal state is the thing this project
    has paid for three times."""
    import verify  # noqa: PLC0415

    baseline = tmp_path / "unverified_baseline.json"
    baseline.write_text(json.dumps({"count": 2, "unverified": ["GET /a -> A", "GET /b -> B"]}))
    capture = tmp_path / "_wire_capture.jsonl"
    capture.write_text(json.dumps(
        {"method": "GET", "path": "/a", "status": 200, "body": {}}) + "\n")
    monkeypatch.setattr(verify, "BASELINE", baseline)
    monkeypatch.setattr(verify, "CAPTURE", capture)
    monkeypatch.setattr(verify, "run", lambda _p: [
        {"class": "A", "endpoint": "/a", "verb": "GET", "status": "UNVERIFIED"},
        {"class": "B", "endpoint": "/b", "verb": "GET", "status": "PASS"},
    ])
    monkeypatch.setattr(verify, "find_unreachable", lambda: [])
    monkeypatch.setattr(sys, "argv", ["verify.py", "--update-baseline"])

    assert verify.main() == 0
    after = json.loads(baseline.read_text())
    assert after["unverified"] == ["GET /a -> A"]
    assert after["count"] == 1
