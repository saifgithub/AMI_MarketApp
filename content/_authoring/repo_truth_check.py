"""Repo-truth auditor for lesson content (CR060 Phase 6).

Concrete failing case: DEF097 — lesson 355 described a halal-flag mechanism the
code had deleted, and sourced a symbol (`DEFAULT_HALAL_DEMO_UNIVERSE`) the code
marks "gone". A lesson can pass every content check and still be false the moment
an unrelated code merge lands. This scanner is the detector for that class.

Two passes:

  1. Curated denylist — retired / phantom identifiers a lesson must not present as
     live product truth, each with the real replacement. High precision.
  2. Heuristic Mandate-field pass — pull the REAL Compliance/Mandate field names
     straight from backend/app/schemas/mandate.py, then flag any backtick-quoted
     `snake_case: value` token in a lesson that looks like a Mandate field but is
     not one. Catches new phantoms without a denylist entry.

Run as a report (does not fail a build): promote to a pytest in
backend/tests/unit/ once the P1 batch has cleared the current occurrences, per
docs/initial_specs/08_tech/failure_patterns.md (guard lands with the fix).

    python3 content/_authoring/repo_truth_check.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
LESSONS = ROOT / "content" / "lessons"
MANDATE = ROOT / "backend" / "app" / "schemas" / "mandate.py"

# Pass 1 — retired / phantom identifiers → the real thing to say instead.
# "phantom Mandate field" = a lesson tells the user to SET it in the Mandate/
# Settings editor, but no such field exists in schemas/mandate.py. Every one below
# is confirmed absent from backend/app/ (grep) or is a retired symbol.
_CAP = "not a Mandate field; the single-name cap is risk_tier_cap(risk_score) = {1:1.5,2:1.5,3:3.0,4:4.5,5:4.5}% (trading_math/sizing.py) — the user sets risk_score, not the cap"
_DD = "not a Mandate field; the real drawdown field is max_drawdown_pct (Literal[10,20,30,50,100])"
_SCOPE = "not a Mandate field today; only exists if the Mandate schema gains granular caps (product-scope decision, not a content fix)"
DENYLIST = {
    "max_position_pct": _CAP,
    "max_single_name_notional_pct": _CAP,
    "max_risk_per_trade_pct": "not a Mandate field; risk appetite is risk_score (1-5), the cap derives from it",
    "max_per_trade_risk_pct": "not a Mandate field; risk appetite is risk_score (1-5)",
    "pause_at_drawdown_pct": _DD,
    "region_allowlist": "not a Mandate field; the real constraints are ticker_allowlist/ticker_blocklist + locale",
    "max_single_factor_exposure_pct": _SCOPE,
    "max_sector_exposure_pct": _SCOPE,
    "total_open_risk_pct": _SCOPE,
    "max_open_positions": _SCOPE,
    "max_trades_per_week": _SCOPE,
    "cooldown_after_stop_minutes": _SCOPE,
    "DEFAULT_HALAL_DEMO_UNIVERSE": "RETIRED by CR069 (sim_engine.py:74 marks it 'gone'); the halal flag now enforces a sourced S&P Sharia universe (sharia_universe.py)",
    "purification_amount": "no user-reachable code path computes this (DEF084 class)",
}

# Real Mandate/Compliance field names, pulled from the schema so this stays in sync.
KNOWN_OK_EXTRA = {
    # nested/adjacent real identifiers a lesson may legitimately name
    "risk_tier_cap", "risk_components", "SINGLE_NAME_ABSOLUTE_CAP_PCT",
    "time_local", "voice_id",
}


def real_mandate_fields() -> set[str]:
    text = MANDATE.read_text()
    # every `field_name: Type` at class-body indentation
    names = set(re.findall(r"^\s{4}([a-z][a-z0-9_]+)\s*:", text, re.M))
    names -= {"model_config"}
    return names | KNOWN_OK_EXTRA


# A token that LOOKS like a Mandate field being asserted as config:
#   `max_position_pct: 5`   or   `max_position_pct`   near "mandate"/"field"
FIELDISH = re.compile(r"`([a-z][a-z0-9_]{3,}_pct|[a-z][a-z0-9_]*_(?:pct|score|drawdown|only|blocklist|allowlist))`")


def scan() -> int:
    ok = real_mandate_fields()
    deny_hits: list[tuple[str, int, str, str]] = []
    phantom_hits: list[tuple[str, int, str]] = []

    for f in sorted(LESSONS.glob("*.en.mdx")):
        lid = f.name.replace(".en.mdx", "")
        for i, line in enumerate(f.read_text().splitlines(), 1):
            for bad, why in DENYLIST.items():
                if bad in line:
                    deny_hits.append((lid, i, bad, why))
            for m in FIELDISH.finditer(line):
                tok = m.group(1)
                if tok not in ok and tok not in DENYLIST:
                    phantom_hits.append((lid, i, tok))

    print(f"# Repo-truth audit — {len(list(LESSONS.glob('*.en.mdx')))} lessons\n")
    print(f"## Pass 1 — retired/phantom identifiers ({len(deny_hits)} hits)\n")
    by_lesson: dict[str, list] = {}
    for lid, i, bad, why in deny_hits:
        by_lesson.setdefault(lid, []).append((i, bad, why))
    for lid in sorted(by_lesson):
        for i, bad, why in by_lesson[lid]:
            print(f"  {lid}:{i}  `{bad}`  → {why}")
    print(f"\n  lessons affected: {len(by_lesson)}")

    print(f"\n## Pass 2 — field-ish tokens not in the real Mandate schema ({len(phantom_hits)} hits)\n")
    seen = set()
    for lid, i, tok in phantom_hits:
        key = (lid, tok)
        if key in seen:
            continue
        seen.add(key)
        print(f"  {lid}:{i}  `{tok}`  (not a Mandate field)")

    return len(deny_hits)


if __name__ == "__main__":
    sys.exit(1 if scan() else 0)
