"""The check itself: for every auto-discovered (endpoint, Dart class) pair,
union the REAL captured JSON bodies observed on that endpoint during a normal
test run, recurse one level into nested list classes (DEF365's shape), and
report any key a Dart factory reads that never once appeared on the real
wire.

This is the mechanism proposed in SOLUTION.md, runnable end to end:

    python3 discover_pairs.py        # (re)build discovered_pairs.json
    # run the real backend suite with wire_capture_plugin.py loaded
    python3 compare.py               # this file

No endpoint/class pair is hand-declared anywhere in this pipeline.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from dart_keys import index as dart_index

HERE = Path(__file__).parent
PAIRS_JSON = HERE / "discovered_pairs.json"
CAPTURED = HERE / "captured_responses.jsonl"


def _load_pairs():
    return json.loads(PAIRS_JSON.read_text())["pairs"]


def _load_captured():
    rows = []
    if not CAPTURED.exists():
        return rows
    for line in CAPTURED.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _bodies_for(pair, captured):
    rx = re.compile(pair["url_regex"])
    out = []
    for r in captured:
        if r["method"] != pair["verb"]:
            continue
        if r["status"] >= 400:
            continue
        if not rx.match(r["path"]):
            continue
        if r["body"] is None:
            continue
        out.append(r["body"])
    return out


def _flatten_objects(body, is_list: bool):
    """The objects actually handed to `.fromJson` for this endpoint."""
    if is_list:
        if isinstance(body, list):
            return [o for o in body if isinstance(o, dict)]
        return []
    return [body] if isinstance(body, dict) else []


def check_pair(pair, captured, idx, seen_never_verified):
    cls = pair["dart_class"]
    contract = idx.get(cls)
    if contract is None:
        return {
            "class": cls, "endpoint": pair["url_template"], "status": "SKIP",
            "reason": "class has no fromJson factory found by dart_keys.py "
                      "(constructor-only class, or extractor miss)",
        }
    bodies = _bodies_for(pair, captured)
    objs = []
    for b in bodies:
        objs.extend(_flatten_objects(b, pair["is_list"]))

    if not objs:
        # DEGRADE LOUDLY: a pair with zero real observations cannot be
        # evaluated and must not silently pass. This is exactly the state a
        # brand-new field/endpoint is in until a test exercises it — the
        # inventory's item 6.
        seen_never_verified.append(pair)
        return {
            "class": cls, "endpoint": pair["url_template"], "status": "UNVERIFIED",
            "reason": "endpoint never observed with a 2xx JSON body during "
                      "this run — cannot confirm or deny wire agreement",
        }

    observed_keys: set[str] = set()
    for o in objs:
        observed_keys |= set(o.keys())

    missing_required = sorted(contract.required_keys - observed_keys)
    missing_alt = []
    for group in contract.alt_groups:
        if not (group & observed_keys):
            missing_alt.append(sorted(group))

    result = {
        "class": cls,
        "endpoint": pair["url_template"],
        "status": "FAIL" if (missing_required or missing_alt) else "PASS",
        "observations": len(objs),
        "missing_required_keys": missing_required,
        "unsatisfied_alt_groups": missing_alt,
    }

    # Recurse one level into nested list classes (DEF365's exact shape).
    nested_results = []
    for wire_key, nested_cls in contract.nested_lists.items():
        nested_contract = idx.get(nested_cls)
        if nested_contract is None:
            continue
        nested_objs = []
        for o in objs:
            v = o.get(wire_key)
            if isinstance(v, list):
                nested_objs.extend(x for x in v if isinstance(x, dict))
        if not nested_objs:
            nested_results.append({
                "class": nested_cls, "via": f"{cls}.{wire_key}",
                "status": "UNVERIFIED",
                "reason": f"'{wire_key}' was always empty in {len(objs)} "
                          f"observation(s) — the nested class was never "
                          f"actually populated on the wire",
            })
            continue
        nested_observed: set[str] = set()
        for no in nested_objs:
            nested_observed |= set(no.keys())
        nmiss = sorted(nested_contract.required_keys - nested_observed)
        nested_results.append({
            "class": nested_cls, "via": f"{cls}.{wire_key}",
            "status": "FAIL" if nmiss else "PASS",
            "observations": len(nested_objs),
            "missing_required_keys": nmiss,
        })
    result["nested"] = nested_results
    return result


def main():
    pairs = _load_pairs()
    captured = _load_captured()
    idx = dart_index()
    never_verified: list[dict] = []
    results = [check_pair(p, captured, idx, never_verified) for p in pairs]

    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    n_unverified = sum(1 for r in results if r["status"] == "UNVERIFIED")
    n_skip = sum(1 for r in results if r["status"] == "SKIP")

    print(f"{len(results)} discovered pairs | "
          f"{n_pass} PASS  {n_fail} FAIL  {n_unverified} UNVERIFIED  {n_skip} SKIP\n")

    for r in results:
        if r["status"] in ("FAIL",):
            print(f"FAIL  {r['class']:28s} <- {r['endpoint']}")
            if r.get("missing_required_keys"):
                print(f"      missing (server never emits): {r['missing_required_keys']}")
            if r.get("unsatisfied_alt_groups"):
                print(f"      no alt satisfied: {r['unsatisfied_alt_groups']}")
            for n in r.get("nested", []):
                if n["status"] == "FAIL":
                    print(f"      NESTED FAIL {n['class']} via {n['via']}: "
                          f"missing {n['missing_required_keys']}")

    print()
    for r in results:
        for n in r.get("nested", []):
            if n["status"] != "PASS":
                print(f"{n['status']:10s} {n['class']:24s} via {n['via']:30s} "
                      f"{n.get('reason', '')}")

    Path(HERE / "compare_report.json").write_text(json.dumps(results, indent=2))
    print(f"\nFull report -> {HERE / 'compare_report.json'}")


if __name__ == "__main__":
    main()
