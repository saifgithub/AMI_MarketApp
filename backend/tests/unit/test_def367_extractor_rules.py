"""DEF367 — the three Dart read patterns the wire-contract extractor learned (AT:B1).

`/v1/games/cadences`, `/v1/games/runs/{id}/trade/quote` and `/v1/games/record/prs`
sat in the unverified baseline because driving them turned each into a false hard
FAIL: the extractor read a Dart fallback as a hard requirement. Each rule here is
tested with a synthetic Dart snippet (the extractor is lexical, so the snippet IS
the spec) and each has a negative case — none of the alternatives sent must still
FAIL, or the rule has become a way to wave a real disagreement through.

  1. nested-or-flat:  `x is Map ? X.fromJson(x) : X.fromJson(j)`
  2. alternative keys: `j['a'] ?? j['b']`, and a nullable static helper that
     returns the first non-null of several keys
  3. client adapter:  `gamesRecordPrs` reshapes a category-keyed object before
     `fromJson`

Pure unit tests: no server, no capture.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_WC = Path(__file__).resolve().parents[2] / "scripts" / "wire_contract"
sys.path.insert(0, str(_WC))

import adapters  # noqa: E402
import compare  # noqa: E402
import dart_keys  # noqa: E402

# Keys no server code emits, so a missing one classifies as unemittable (FAIL), not
# branch-conditional (UNVERIFIED). Same device as the other comparator tests.
_NOPE_A = "zzz_no_such_key_a"
_NOPE_B = "zzz_no_such_key_b"


def _index_for(tmp_path, monkeypatch, dart: str) -> dict:
    (tmp_path / "m.dart").write_text(dart)
    monkeypatch.setattr(dart_keys, "MODELS_DIR", tmp_path)
    return dart_keys._build_index()


def _pair(cls="Thing"):
    return {"dart_method": "m", "verb": "GET", "url_template": "/v1/thing",
            "url_regex": r"^/v1/thing$", "dart_class": cls, "is_list": False,
            "envelope_key": None}


def _check(idx, body, cls="Thing"):
    cap = [{"method": "GET", "path": "/v1/thing", "status": 200, "body": body}]
    return compare.check_pair(_pair(cls), cap, idx)


# --------------------------------------------------------------------------
# 1. nested-or-flat
# --------------------------------------------------------------------------

_NESTED_OR_FLAT = f"""
class Thing {{
  factory Thing.fromJson(Map<String, dynamic> j) {{
    final nested = j['{_NOPE_A}'];
    return Thing(
      id: j['id'] as String,
      inner: nested is Map<String, dynamic>
          ? Inner.fromJson(nested)
          : (j['{_NOPE_B}'] != null ? Inner.fromJson(j) : null),
    );
  }}
}}
class Inner {{
  factory Inner.fromJson(Map<String, dynamic> j) => Inner(
        a: j['inner_a'] as int?,
        b: j['inner_b'] as int?,
      );
}}
"""


def test_nested_or_flat_is_extracted(tmp_path, monkeypatch):
    c = _index_for(tmp_path, monkeypatch, _NESTED_OR_FLAT)["Thing"]
    assert c.required_keys == {"id"}, "the nested key and the flat guard are not hard requirements"
    (ff,) = c.flat_fallbacks
    assert (ff.nested_key, ff.flat_class, ff.guard_keys) == (_NOPE_A, "Inner", {_NOPE_B})


def test_nested_or_flat_inline_form_is_extracted(tmp_path, monkeypatch):
    c = _index_for(tmp_path, monkeypatch, f"""
class Thing {{
  factory Thing.fromJson(Map<String, dynamic> j) => Thing(
        inner: j['{_NOPE_A}'] is Map<String, dynamic>
            ? Inner.fromJson(j['{_NOPE_A}'] as Map<String, dynamic>)
            : Inner.fromJson(j),
      );
}}
class Inner {{
  factory Inner.fromJson(Map<String, dynamic> j) => Inner(a: j['inner_a']);
}}
""")["Thing"]
    (ff,) = c.flat_fallbacks
    assert (ff.nested_key, ff.flat_class) == (_NOPE_A, "Inner")
    assert c.required_keys == set()


def test_nested_or_flat_satisfied_by_the_nested_key(tmp_path, monkeypatch):
    idx = _index_for(tmp_path, monkeypatch, _NESTED_OR_FLAT)
    assert _check(idx, {"id": "x", _NOPE_A: {"inner_a": 1}})["status"] == "PASS"


def test_nested_or_flat_satisfied_by_the_flat_keys(tmp_path, monkeypatch):
    idx = _index_for(tmp_path, monkeypatch, _NESTED_OR_FLAT)
    r = _check(idx, {"id": "x", _NOPE_B: "f", "inner_a": 1, "inner_b": 2})
    assert r["status"] == "PASS"


def test_nested_or_flat_fails_when_neither_shape_is_sent(tmp_path, monkeypatch):
    """The negative case. Only `id` arrived: no nested key, and the flat keys are
    missing too — the client would build a cadence with no field at all."""
    idx = _index_for(tmp_path, monkeypatch, _NESTED_OR_FLAT)
    r = _check(idx, {"id": "x"})
    assert r["status"] == "FAIL"
    (u,) = r["unsatisfied_flat_fallbacks"]
    assert u["nested_key"] == _NOPE_A


def test_nested_or_flat_is_not_satisfied_by_a_partial_flat_shape(tmp_path, monkeypatch):
    """Some flat keys but not all is the half-migrated server: the flat parse
    would read nulls for the rest. Not a pass."""
    idx = _index_for(tmp_path, monkeypatch, _NESTED_OR_FLAT)
    r = _check(idx, {"id": "x", _NOPE_B: "f", "inner_a": 1})
    assert r["status"] != "PASS"


# --------------------------------------------------------------------------
# 2. alternative keys
# --------------------------------------------------------------------------

_ALT_CHAIN = f"""
class Thing {{
  factory Thing.fromJson(Map<String, dynamic> j) => Thing(
        a: (j['{_NOPE_A}'] ?? j['{_NOPE_B}'] ?? j['third_alt']) as num?,
        id: j['id'] as String,
      );
}}
"""


@pytest.mark.parametrize("sent", [_NOPE_A, _NOPE_B, "third_alt"])
def test_an_alternation_chain_is_satisfied_by_any_one_spelling(tmp_path, monkeypatch, sent):
    idx = _index_for(tmp_path, monkeypatch, _ALT_CHAIN)
    assert _check(idx, {"id": "x", sent: 1})["status"] == "PASS"


def test_an_alternation_chain_fails_when_no_spelling_is_sent(tmp_path, monkeypatch):
    idx = _index_for(tmp_path, monkeypatch, _ALT_CHAIN)
    r = _check(idx, {"id": "x"})
    assert r["status"] == "FAIL"
    assert sorted(r["unsatisfied_alt_groups"][0]) == sorted([_NOPE_A, _NOPE_B, "third_alt"])


_ALT_HELPER = f"""
class Thing {{
  factory Thing.fromJson(Map<String, dynamic> j) => Thing(
        id: j['id'] as String,
        flag: _flag(j),
      );

  /// A doc comment that mentions `j['{_NOPE_A}']` is documentation, not a read.
  static bool? _flag(Map<String, dynamic> j) {{
    final explicit = j['{_NOPE_A}'] as bool?;
    if (explicit != null) return explicit;
    final inverse = j['{_NOPE_B}'] as bool?;
    return inverse == null ? null : !inverse;
  }}
}}
"""


@pytest.mark.parametrize("sent", [_NOPE_A, _NOPE_B])
def test_a_fallback_helper_is_satisfied_by_any_one_key(tmp_path, monkeypatch, sent):
    idx = _index_for(tmp_path, monkeypatch, _ALT_HELPER)
    assert idx["Thing"].required_keys == {"id"}
    assert _check(idx, {"id": "x", sent: True})["status"] == "PASS"


def test_a_fallback_helper_fails_when_no_key_is_sent(tmp_path, monkeypatch):
    idx = _index_for(tmp_path, monkeypatch, _ALT_HELPER)
    r = _check(idx, {"id": "x"})
    assert r["status"] == "FAIL"
    assert r["unsatisfied_alt_groups"] == [[_NOPE_A, _NOPE_B]]


def test_a_helper_with_no_early_return_keeps_every_key_required(tmp_path, monkeypatch):
    """The early `!= null` return is what makes the keys alternatives. A helper
    that reads two keys and needs both must not be relaxed into an either/or."""
    idx = _index_for(tmp_path, monkeypatch, f"""
class Thing {{
  factory Thing.fromJson(Map<String, dynamic> j) => Thing(v: _both(j));
  static int? _both(Map<String, dynamic> j) {{
    final a = j['{_NOPE_A}'] as int?;
    final b = j['{_NOPE_B}'] as int?;
    return a == null || b == null ? null : a + b;
  }}
}}
""")
    assert idx["Thing"].alt_groups == []
    assert idx["Thing"].required_keys == {_NOPE_A, _NOPE_B}
    assert _check(idx, {_NOPE_A: 1})["status"] == "FAIL"


def test_a_key_named_only_in_a_comment_is_not_a_requirement(tmp_path, monkeypatch):
    """The slice for one factory runs to the next, so it swallowed the next
    class's doc comment — `GameTradeResult`'s "This read `j['status']`..." made
    `GameTradeQuote` require `status`."""
    idx = _index_for(tmp_path, monkeypatch, f"""
class Thing {{
  factory Thing.fromJson(Map<String, dynamic> j) => Thing(id: j['id'] as String);
}}
/// This read `j['{_NOPE_A}']` and defaulted to 'filled'.
class Other {{
  factory Other.fromJson(Map<String, dynamic> j) => Other();
}}
""")
    assert idx["Thing"].required_keys == {"id"}


# --------------------------------------------------------------------------
# 3. the client adapter (`gamesRecordPrs`)
# --------------------------------------------------------------------------

_PRS_PAIR = {
    "dart_method": "gamesRecordPrs", "verb": "GET",
    "url_template": "/v1/games/record/prs", "url_regex": r"^/v1/games/record/prs$",
    "dart_class": "Rec", "is_list": False, "envelope_key": None,
}


def _prs_idx():
    from dart_keys import ClassContract
    return {"Rec": ClassContract(
        class_name="Rec", file="r.dart",
        required_keys={"kind", "entry_id", "value", "cadence"},
    )}


def _prs(body):
    cap = [{"method": "GET", "path": "/v1/games/record/prs", "status": 200, "body": body}]
    return compare.check_pair(_PRS_PAIR, cap, _prs_idx())


def test_the_adapter_mapping_covers_the_five_categories():
    assert adapters.PR_CATEGORY_VALUE_KEYS == {
        "best_weekly_twr": "final_twr_pct", "best_alpha": "alpha_scored_pct",
        "best_drawdown_control": "max_drawdown_pct", "longest_hold_days": "days",
        "longest_finish_streak": "count",
    }


def test_a_category_keyed_board_is_checked_through_the_adapter():
    """`cadence` is read by `fromJson` but never put in the synthesised object —
    the adapter's own reads are the contract, so it is not a missing key."""
    r = _prs({
        "has_any_finished_runs": True,
        "best_weekly_twr": {"entry_id": "e1", "final_twr_pct": 1.5},
        "longest_hold_days": {"entry_id": "e1", "days": 4},
        "best_alpha": None,
    })
    assert r["status"] == "PASS"
    assert r["observations"] == 2


def test_a_category_without_its_value_key_fails():
    """The negative case, and the reason the adapter objects are checked one by
    one: `longest_hold_days` has its `entry_id` but not `days`, and a sibling
    category's `value` must not paper over it."""
    r = _prs({
        "best_weekly_twr": {"entry_id": "e1", "final_twr_pct": 1.5},
        "longest_hold_days": {"entry_id": "e1", "days_held": 4},
    })
    assert r["status"] != "PASS"
    assert "value" in (r["missing_and_unemittable"] + r["missing_but_branch_conditional"])


def test_a_category_without_entry_id_is_not_a_pass():
    r = _prs({"best_weekly_twr": {"final_twr_pct": 1.5}})
    assert r["status"] != "PASS"


def test_an_all_null_board_is_unverified_not_passed():
    """No record means no object was ever handed to `fromJson`: nothing observed."""
    r = _prs({"has_any_finished_runs": False, "best_weekly_twr": None, "best_alpha": None})
    assert r["status"] == "UNVERIFIED"
    assert r["observations"] == 0


def test_a_flat_prs_list_is_passed_through_to_the_class_contract():
    """The client reads `data['prs']` FIRST. When the server does send it the
    elements go to `fromJson` untouched, so they answer to the class's own keys."""
    ok = _prs({"prs": [{"kind": "k", "entry_id": "e", "value": 1, "cadence": "week"}]})
    assert ok["status"] == "PASS"
    short = _prs({"prs": [{"kind": "k"}]})
    assert short["status"] != "PASS"


def test_only_the_named_route_is_adapted():
    """Any other method keeps the plain `fromJson`-keys check."""
    assert set(adapters.ADAPTERS) == {"gamesRecordPrs"}


def test_the_adapter_table_still_matches_the_dart_source():
    """The mapping is declared by hand, so pin it to `api_client.dart`: if the app
    renames a category or its value key this fails instead of silently verifying a
    shape the client no longer reads."""
    import re

    src = (Path(__file__).resolve().parents[3] / "mobile" / "lib" / "services" / "api"
           / "api_client.dart").read_text()
    block = src[src.index("_prCategoryValueKeys"):]
    block = block[: block.index("};")]
    assert dict(re.findall(r"'(\w+)':\s*'(\w+)'", block)) == adapters.PR_CATEGORY_VALUE_KEYS
    method = src[src.index("Future<List<GamePersonalRecord>> gamesRecordPrs"):]
    method = method[: method.index("\n  }\n")]
    assert "raw['entry_id']" in method
    assert "data['prs']" in method
    for forbidden in ("raw['cadence']", "raw['achieved_at']"):
        assert forbidden not in method, (
            f"the adapter now reads {forbidden}: add it to the adapted contract"
        )
