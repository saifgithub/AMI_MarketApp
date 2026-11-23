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

from adapters import ADAPTERS
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


def _objects(body, is_list: bool, envelope_key: str | None = None) -> list[dict]:
    """The objects actually handed to `.fromJson` for this endpoint.

    DEF367 — `envelope_key` is how the CLIENT reaches the list, lifted from its
    own navigation by `discover_pairs`. Without it this function dereferenced
    the response body as a JSON array, so every list endpoint that answers
    `{"items": [...], "total": n}` produced zero objects and stayed UNVERIFIED
    no matter how often it was called. Five surfaces sat in the baseline that
    way while the suite exercised their routes 1-9 times each: they read as
    coverage debt someone could pay off, and no test could ever have closed
    them. That is worse than an uncovered surface, because the entry stops the
    next reader looking.

    An envelope key that is absent from the body, or does not hold a list, is
    NOT silently ignored — it falls through to zero objects and the surface
    stays UNVERIFIED. The client would have read `?? const []` there and
    rendered an empty list, so "the key is gone" is a real disagreement and
    must not read as a pass.
    """
    if is_list:
        if isinstance(body, list):
            return [o for o in body if isinstance(o, dict)]
        if envelope_key and isinstance(body, dict):
            inner = body.get(envelope_key)
            if isinstance(inner, list):
                return [o for o in inner if isinstance(o, dict)]
        return []
    # DEF367 — a scalar parsed through an envelope key (`SimTrade.fromJson(
    # r.data!['trade'])`) is read through that key, never from the body. A body
    # that lacks the key, or holds something other than an object there, is zero
    # observations — the client would have thrown or defaulted, which is a real
    # disagreement and must stay UNVERIFIED, not fall back to reading the
    # envelope as if it were the model.
    if envelope_key:
        inner = body.get(envelope_key) if isinstance(body, dict) else None
        return [inner] if isinstance(inner, dict) else []
    return [body] if isinstance(body, dict) else []


def _evaluate(base: dict, contract, objs: list[dict], idx, per_object: bool = False) -> dict:
    """Compare the objects handed to `fromJson` against `contract`.

    `per_object` (adapter-synthesised objects only): each object must carry every
    required key on its own, rather than the union across objects satisfying it.
    A synthesised record that lacks its `value` is a broken record even if a
    different category's record had one.
    """
    cls = contract.class_name
    if not objs:
        # Degrade loudly: a pair with zero observations cannot be evaluated and
        # must not silently pass. This is the state every brand-new endpoint is
        # in until a test exercises it.
        return {**base, "status": "UNVERIFIED", "observations": 0,
                "reason": "endpoint never observed with a 2xx JSON body"}

    observed: set[str] = set()
    for o in objs:
        observed |= set(o.keys())

    if per_object:
        missing = sorted({k for o in objs for k in contract.required_keys - set(o.keys())})
    else:
        missing = sorted(contract.required_keys - observed)
    unsatisfied_alts = [sorted(g) for g in contract.alt_groups if not (g & observed)]

    # DEF367 - nested-or-flat reads: satisfied by the nested key, or by the keys the
    # flat parse of the same object reads. Unsatisfied only if the nested key was not
    # sent AND some flat key was not either.
    unsatisfied_flat = []
    for ff in contract.flat_fallbacks:
        if ff.nested_key in observed:
            continue
        flat = idx.get(ff.flat_class)
        need = set(ff.guard_keys)
        flat_alts: list[set[str]] = []
        if flat is not None:
            need |= flat.required_keys
            flat_alts = flat.alt_groups
        flat_missing = [[k] for k in sorted(need - observed)] + [
            sorted(g) for g in flat_alts if not (g & observed)
        ]
        if flat_missing:
            unsatisfied_flat.append({"nested_key": ff.nested_key,
                                     "flat_class": ff.flat_class,
                                     "flat_missing": flat_missing})

    # THE MANDATORY CORRECTION. Observation proves presence, never absence, so a
    # key nobody saw is only a FAIL when the server has no branch that emits it.
    absent, conditional = classify_missing(missing)
    alt_absent = []
    for group in unsatisfied_alts:
        group_absent, _ = classify_missing(group)
        if len(group_absent) == len(group):
            alt_absent.append(group)
    flat_absent = []
    for u in unsatisfied_flat:
        nested_absent, _ = classify_missing([u["nested_key"]])
        # A spelling group is only unemittable when every spelling is.
        unemittable = [g for g in u["flat_missing"]
                       if len(classify_missing(g)[0]) == len(g)]
        if nested_absent and unemittable:
            flat_absent.append({**u, "flat_missing": unemittable})

    status = "FAIL" if (absent or alt_absent or flat_absent) else (
        "UNVERIFIED" if (conditional or unsatisfied_alts or unsatisfied_flat) else "PASS"
    )
    result = {
        **base,
        "status": status,
        "observations": len(objs),
        "missing_and_unemittable": absent,
        "missing_but_branch_conditional": conditional,
        "unsatisfied_alt_groups": alt_absent,
        "unsatisfied_flat_fallbacks": flat_absent,
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


def check_pair(pair: dict, captured: list[dict], idx) -> dict:
    cls = pair["dart_class"]
    contract = idx.get(cls)
    base = {"class": cls, "endpoint": pair["url_template"], "verb": pair["verb"]}
    if contract is None:
        return {**base, "status": "SKIP",
                "reason": "no fromJson factory found for this class"}

    adapter = ADAPTERS.get(pair.get("dart_method", ""))
    if adapter is not None:
        return _check_adapted(base, adapter, contract, pair, captured, idx)

    objs: list[dict] = []
    for b in _bodies_for(pair, captured):
        objs.extend(_objects(b, pair["is_list"], pair.get("envelope_key")))
    return _evaluate(base, contract, objs, idx)


def _check_adapted(base, adapter, contract, pair, captured, idx) -> dict:
    """DEF367 - a route the client reshapes before `fromJson` (see `adapters.py`).

    Each branch the wire actually took is checked against its own contract. The
    client's `prs`-list branch and its category branch are alternatives, so a
    branch that never fired is not a missing observation - but a route where NO
    branch produced an object is still UNVERIFIED.
    """
    by_branch: dict[str, list[dict]] = {"adapted": [], "passthrough": []}
    for b in _bodies_for(pair, captured):
        for branch, obj in adapter.transform(b):
            by_branch[branch].append(obj)
    results = []
    if by_branch["adapted"]:
        results.append(_evaluate(base, adapter.adapted_contract, by_branch["adapted"],
                                 idx, per_object=True))
    if by_branch["passthrough"]:
        results.append(_evaluate(base, contract, by_branch["passthrough"], idx))
    if not results:
        return _evaluate(base, contract, [], idx)
    rank = {"PASS": 0, "UNVERIFIED": 1, "FAIL": 2}
    worst = max(results, key=lambda r: rank[r["status"]])
    return {**worst, "observations": sum(r["observations"] for r in results)}


def run(capture_path: Path) -> list[dict]:
    pairs = [
        {
            "dart_method": p.dart_method, "verb": p.verb,
            "url_template": p.url_template, "url_regex": _url_to_regex(p.url_template),
            "dart_class": p.dart_class, "is_list": p.is_list,
            "envelope_key": p.envelope_key,
        }
        for p in discover()
    ]
    captured = load_captured(capture_path)
    idx = dart_index()
    return [check_pair(p, captured, idx) for p in pairs]


def surface_id(result: dict) -> str:
    """Stable identity for a surface, for the UNVERIFIED baseline."""
    return f"{result['verb']} {result['endpoint']} -> {result['class']}"
