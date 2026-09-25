"""DEF423 — CR160's rename held for `content/` but not for the surfaces this
guard covers: `mobile/lib`'s EN ARB values, `mobile/lib/models/agent.dart`
display names, and `content/agents/*.md` prompt text.

`test_cr160_agent_rename.py::test_retired_labels_absent_from_en_content_corpus`
only walks `content/`. It never looked at `mobile/lib/l10n/app_en.arb`, so
CR160's own shipped sweep still left twelve ARB values saying "PM" and three
more spelling out "Portfolio Manager" / "Market Analyst" / "Trader" as agent
labels (DEF423, 2026-09-25 — Saiful: *"We have been mixing the term PM and
CIO in the app, and in the lesson."*). This is a second occurrence of the
incomplete-rename class, so per CLAUDE.md's failure-patterns house rule it
gets a guard, not just a fix.

Scope is deliberately narrower than the CR160 test's `content/` walk: it
covers exactly the three surfaces this Defect's lane owns (mobile app +
agent prompt files). Backend user-facing strings and website/website_api
copy were swept by hand for this Defect but have no dedicated corpus here to
scan structurally without also flagging legitimate code comments/docstrings
(CLAUDE.md: internal identifiers and comments are fine) — see
docs/defect/DEF423_cr160_rename_residue.md for that reasoning.

The allowlist below is deliberately small and documented, not a growing
escape hatch: every entry is a real ambiguous case reasoned about in the
Defect doc, not a shortcut around a fix.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

RETIRED_LABELS = (
    "Aggressive Debator",
    "Conservative Debator",
    "Neutral Debator",
    "Risk Debator",
    "Debator",
    "Portfolio Manager",
    "Market Analyst",
    "Social Media Analyst",
    "News Analyst",
)

# Case-insensitive variants of the same labels, for ALL-CAPS UI strings
# ("ASK THE MARKET ANALYST", "PORTFOLIO MANAGER" card headers) that the
# case-sensitive tuple above would miss.
_RETIRED_LABELS_CI = tuple(label.lower() for label in RETIRED_LABELS)

# Bare "PM" as an abbreviation for the retired "Portfolio Manager" label.
# Excludes "4 PM ET"-style times and anything already caught by the label
# scan above.
_BARE_PM = re.compile(r"(?<![A-Za-z])PM(?![A-Za-z'])")
_PM_TIME_CONTEXT = re.compile(r"\b\d{1,2}\s*PM\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Allowlist — every entry is a real, reasoned exception, not a growing hole.
# ---------------------------------------------------------------------------

# ARB keys where "Trader" is the $14.99/mo pricing-tier product name (CR084),
# the Day Trader risk preset (CR129), or a competition-ladder rank — none of
# which are the retired "Trader" AGENT label CR160 renamed to Execution Desk.
_ARB_ALLOWED_TRADER_KEYS = {
    "upgradePlanTrader",
    "portfolioHealthUpgradeBody",
    "houseAdOneOnOneHeadline",
    "houseAdRoomHeadline",
    "houseAdRoomBody",
    "houseAdGenericHeadline",
    "houseAdGenericBody",
    "houseAdCtaTrader",
    "settingsRiskPresetDayTrader",
    "settingsRiskPresetDayTraderActive",
    "settingsDayTraderConfirm",
}

# ARB `@key` metadata blocks are dev-facing descriptions (like a code
# comment), not rendered strings — CLAUDE.md exempts internal comments.
# Only VALUES are scanned; this constant documents that choice for readers
# of this file, not an allowlist of specific keys.


def _en_arb() -> dict[str, str]:
    path = REPO / "mobile" / "lib" / "l10n" / "app_en.arb"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("@") and isinstance(v, str)}


def test_no_retired_agent_label_in_en_arb_values():
    strings = _en_arb()
    offenders: list[str] = []
    for key, value in strings.items():
        low = value.lower()
        for label in _RETIRED_LABELS_CI:
            if label in low:
                offenders.append(f"{key}: contains {label!r} -> {value!r}")
    assert not offenders, "retired agent labels found in app_en.arb values:\n" + "\n".join(offenders)


def test_no_bare_pm_agent_abbreviation_in_en_arb_values():
    strings = _en_arb()
    offenders: list[str] = []
    for key, value in strings.items():
        if not _BARE_PM.search(value):
            continue
        if _PM_TIME_CONTEXT.search(value):
            continue
        offenders.append(f"{key}: {value!r}")
    assert not offenders, (
        "bare 'PM' (the retired Portfolio Manager abbreviation) found in "
        "app_en.arb values — use 'CIO':\n" + "\n".join(offenders)
    )


def test_no_retired_trader_agent_label_in_en_arb_values():
    """"Trader" survives as a pricing tier / Day Trader preset / competition
    rank (see `_ARB_ALLOWED_TRADER_KEYS`) but not as the agent CR160 renamed
    to Execution Desk."""
    strings = _en_arb()
    offenders: list[str] = []
    for key, value in strings.items():
        if key in _ARB_ALLOWED_TRADER_KEYS:
            continue
        if re.search(r"\bTrader\b", value) and "Day Trader" not in value:
            offenders.append(f"{key}: {value!r}")
    assert not offenders, (
        "retired 'Trader' agent label found in app_en.arb values (expected "
        "'Execution Desk'):\n" + "\n".join(offenders)
    )


def test_no_retired_agent_label_in_flutter_agent_registry_display_names():
    dart = (REPO / "mobile" / "lib" / "models" / "agent.dart").read_text(encoding="utf-8")
    display_names = re.findall(r"displayName:\s*'([^']+)',", dart)
    assert display_names, "expected to find displayName entries in agent.dart"
    offenders: list[str] = []
    for name in display_names:
        low = name.lower()
        for label in _RETIRED_LABELS_CI:
            if label in low:
                offenders.append(name)
    assert not offenders, f"retired agent labels found in agent.dart displayName values: {offenders}"


def test_no_retired_agent_label_in_agent_prompt_markdown():
    agents_dir = REPO / "content" / "agents"
    offenders: list[str] = []
    for path in sorted(agents_dir.glob("*.md")):
        if path.name == "README.md":
            continue
        text = path.read_text(encoding="utf-8")
        for label in RETIRED_LABELS:
            if label in text:
                offenders.append(f"{path.name}: {label}")
    assert not offenders, "retired agent labels found in content/agents/*.md:\n" + "\n".join(offenders)
