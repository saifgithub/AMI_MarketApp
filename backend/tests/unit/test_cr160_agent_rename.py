"""CR160 — the six-agent rename holds, structurally and corpus-wide.

Three guarantees, each of which failed silently at least once in this
project's history class (P3 stale-copy):

1. **ID freeze** — `agent_id` values are wire/DB keys (five tables key on
   them). The rename must never touch them: every `content/agents/*.md`
   frontmatter `agent_id` still matches its filename and is a member of
   `AgentId`.
2. **Display-name lockstep** — the backend's `AGENT_DISPLAY_NAMES`, the
   `content/agents/*.md` frontmatter `display_name`, and the Flutter
   registry (`mobile/lib/models/agent.dart`) must agree per id, or two
   surfaces show the same agent under different names (T-TWICE).
3. **Corpus zero-occurrence** — the retired labels ("Aggressive/Conservative/
   Neutral Debator", "Portfolio Manager", "Market Analyst", "Social Media
   Analyst", "News Analyst" as agent labels) must not reappear in EN content
   or the agent prompt files. New content citing a dead label would teach a
   roster that no longer exists. ("Trader" is excluded here: it legitimately
   survives as the pricing tier, the Day Trader preset, and Trader A/B/C
   exercise personas — the label-specific greps above cover its agent uses
   via the Debator-era phrasing that always accompanied them.)

AR/MS siblings are exempt until the i18n lane retranslates them
(retranslate:[ar,ms] flagged on the CR160 content commit); the ARB files are
the arb-lane's this wave and carry their own DEF137/DEF295 guards.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.schemas.agents import AGENT_DISPLAY_NAMES, AgentId, agent_display_name

REPO = Path(__file__).resolve().parents[3]
AGENTS_DIR = REPO / "content" / "agents"

_FM_FIELD = re.compile(r"^(agent_id|display_name):\s*(.+?)\s*$", re.M)


def _frontmatter(path: Path) -> dict[str, str]:
    head = path.read_text(encoding="utf-8").split("---")[1]
    return {m.group(1): m.group(2) for m in _FM_FIELD.finditer(head)}


def test_agent_ids_are_frozen_and_match_filenames():
    files = sorted(p for p in AGENTS_DIR.glob("*.md") if p.name != "README.md")
    assert len(files) == 13, files
    for p in files:
        fm = _frontmatter(p)
        assert fm["agent_id"] == p.stem, (p.name, fm)
        AgentId(fm["agent_id"])  # raises if the id drifted


def test_display_names_lockstep_backend_vs_prompt_frontmatter():
    for p in sorted(AGENTS_DIR.glob("*.md")):
        if p.name == "README.md":
            continue
        fm = _frontmatter(p)
        assert fm["display_name"] == agent_display_name(fm["agent_id"]), (
            p.name, fm["display_name"], agent_display_name(fm["agent_id"]))


def test_display_names_lockstep_backend_vs_flutter_registry():
    dart = (REPO / "mobile" / "lib" / "models" / "agent.dart").read_text(
        encoding="utf-8")
    pairs = re.findall(
        r"id:\s*'([a-z_]+)',\s*\n\s*displayName:\s*'([^']+)',", dart)
    assert len(pairs) == 13, f"expected 13 registry entries, got {len(pairs)}"
    for agent_id, display in pairs:
        assert display == agent_display_name(agent_id), (
            agent_id, display, agent_display_name(agent_id))


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

# i18n-lane logs quote old strings verbatim; AR/MS awaits retranslation.
_EXEMPT = re.compile(
    r"(/ar/|/ms/|\.ar\.|\.ms\.|lesson_confidence_log|qa_spotcheck_log|"
    r"coverage_status|_authoring/cr060|_authoring/cr127|style_guide_ar_ms)")


def test_retired_labels_absent_from_en_content_corpus():
    offenders: list[str] = []
    for p in (REPO / "content").rglob("*"):
        if not p.is_file() or p.suffix not in {".md", ".mdx", ".json"}:
            continue
        rel = p.relative_to(REPO).as_posix()
        if _EXEMPT.search("/" + rel):
            continue
        text = p.read_text(encoding="utf-8")
        for label in RETIRED_LABELS:
            if label in text:
                offenders.append(f"{rel}: {label}")
    assert not offenders, "retired agent labels found:\n" + "\n".join(offenders)
