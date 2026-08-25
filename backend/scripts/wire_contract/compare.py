"""ISS002/CR208 — the check itself.

For every auto-discovered (endpoint, Dart class) pair, union the REAL captured
JSON bodies observed on that endpoint during a normal backend suite run, recurse
one level into nested list classes (DEF365's exact shape), and report any key a
Dart factory reads that never once appeared on the wire.

Nothing is hand-declared. The pairs come from parsing `api_client.dart`, the
bodies come from the suite that already runs. That is the whole point: manual
declaration is the mechanism that failed three times (DEF357, DEF363, DEF365).

**Four states, and the third is the one that took a Dilemma to get right.**

  PASS        every key the client reads was observed at least once
  FAIL        a key was never observed AND no server branch can emit it
  UNVERIFIED  either the endpoint was never observed, or the key is absent but
              the server DOES have a branch that emits it
  SKIP        the class has no `fromJson` the extractor could find

`UNVERIFIED` is never a silent pass — see `verify.py`, which ratchets it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from branch_scan import classify_missing
from dart_keys import index as dart_index
from discover_pairs import _url_to_regex, discover

HERE = Path(__file__).parent


def load_captured(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _bodies_for(pair: dict, captured: list[dict]) -> list:
    rx = re.compile(pair["url_regex"])
    out = []
    for r in captured:
        if r["method"] != pair["verb"] or r["status"] >= 400 or r["body"] is None:
            continue
        if rx.match(r["path"]):
            out.append(r["body"])
    return out


def _objects(body, is_list: bool) -> list[dict]:
    """The objects actually handed to `.fromJson` for this endpoint."""
    if is_list:
        return [o for o in body if isinstance(o, dict)] if isinstance(body, list) else []
    return [body] if isinstance(body, dict) else []


def check_pair(pair: dict, captured: list[dict], idx) -> dict:
    cls = pair["dart_class"]
    contract = idx.get(cls)
    base = {"class": cls, "endpoint": pair["url_template"], "verb": pair["verb"]}
    if contract is None:
        return {**base, "status": "SKIP",
                "reason": "no fromJson factory found for this class"}

    objs: list[dict] = []
    for b in _bodies_for(pair, captured):
        objs.extend(_objects(b, pair["is_list"]))

    if not objs:
        # Degrade loudly: a pair with zero observations cannot be evaluated and
        # must not silently pass. This is the state every brand-new endpoint is
        # in until a test exercises it.
        return {**base, "status": "UNVERIFIED", "observations": 0,
                "reason": "endpoint never observed with a 2xx JSON body"}

    observed: set[str] = set()
    for o in objs:
        observed |= set(o.keys())

    missing = sorted(contract.required_keys - observed)
    unsatisfied_alts = [sorted(g) for g in contract.alt_groups if not (g & observed)]

    # THE MANDATORY CORRECTION. Observation proves presence, never absence, so a
    # key nobody saw is only a FAIL when the server has no branch that emits it.
    absent, conditional = classify_missing(missing)
    alt_absent = []
    for group in unsatisfied_alts:
        group_absent, _ = classify_missing(group)
        if len(group_absent) == len(group):
            alt_absent.append(group)

    status = "FAIL" if (absent or alt_absent) else (
        "UNVERIFIED" if (conditional or unsatisfied_alts) else "PASS"
    )
    result = {
        **base,
        "status": status,
        "observations": len(objs),
        "missing_and_unemittable": absent,
        "missing_but_branch_conditional": conditional,
        "unsatisfied_alt_groups": alt_absent,
    }

    nested = []
    for wire_key, nested_cls in contract.nested_lists.items():
        ncontract = idx.get(nested_cls)
        if ncontract is None:
            continue
        nobjs: list[dict] = []
        for o in objs:
            v = o.get(wire_key)
            if isinstance(v, list):
                nobjs.extend(x for x in v if isinstance(x, dict))
        if not nobjs:
            nested.append({"class": nested_cls, "via": f"{cls}.{wire_key}",
                           "status": "UNVERIFIED",
                           "reason": f"'{wire_key}' was empty in every observation"})
            continue
        nobserved: set[str] = set()
        for no in nobjs:
            nobserved |= set(no.keys())
        nmissing = sorted(ncontract.required_keys - nobserved)
        nabsent, nconditional = classify_missing(nmissing)
        nested.append({
            "class": nested_cls, "via": f"{cls}.{wire_key}",
            "status": "FAIL" if nabsent else ("UNVERIFIED" if nconditional else "PASS"),
            "observations": len(nobjs),
            "missing_and_unemittable": nabsent,
            "missing_but_branch_conditional": nconditional,
        })
    result["nested"] = nested
    return result


def run(capture_path: Path) -> list[dict]:
    pairs = [
        {
            "dart_method": p.dart_method, "verb": p.verb,
            "url_template": p.url_template, "url_regex": _url_to_regex(p.url_template),
            "dart_class": p.dart_class, "is_list": p.is_list,
        }
        for p in discover()
    ]
    captured = load_captured(capture_path)
    idx = dart_index()
    return [check_pair(p, captured, idx) for p in pairs]


def surface_id(result: dict) -> str:
    """Stable identity for a surface, for the UNVERIFIED baseline."""
    return f"{result['verb']} {result['endpoint']} -> {result['class']}"
