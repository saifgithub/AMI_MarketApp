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

import sys
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

def _pair(is_list=False):
    return {
        "dart_method": "m", "verb": "GET", "url_template": "/v1/thing",
        "url_regex": r"^/v1/thing$", "dart_class": "Thing", "is_list": is_list,
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
