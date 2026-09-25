"""DEF429 — raw snake_case agent ids shown to users in daily challenges.

DEF423 (2026-09-25, lane C) closed the PM/CIO abbreviation-mixing residue in
`content/**` but explicitly flagged one thing it found and left alone as
out-of-scope: "those quiz items render raw snake_case ids as user-facing
answer text, which is a pre-existing display bug independent of PM/CIO
naming — out of DEF423's scope, flagged here only so it isn't mistaken for
something this sweep should have caught." (see
`docs/defect/DEF423_lane_C_content.md`, "Ambiguous occurrences left alone".)

DEF429 is that flagged bug. `content/daily_challenges/2026_07.json` had
~23 occurrences of raw ids like `market_analyst`, `conservative_debator`,
`portfolio_manager` sitting directly in `question`/`scenario`/`options`/
`explanation` strings — a user reading "What does the conservative_debator
say?" or picking between multiple-choice options that are literally
`["portfolio_manager", "trader", "bear_researcher", "conservative_debator"]`
sees the internal wire key, not the CR160 display title a user is supposed
to see everywhere else in the app.

This is the same failure class CLAUDE.md's failure_patterns.md calls P37 (a
rename's own guard scans one corpus; a structurally identical sibling corpus
has none) one layer down: CR160's corpus guard
(`test_cr160_agent_rename.py`) checks for the *retired English labels*
reappearing, and DEF423's residue guard
(`test_def423_agent_rename_residue.py`) checks `mobile/lib` + `agent.dart` +
`content/agents/*.md` for the same retired-label class — but nothing checked
for the *wire id itself* leaking into user-visible prose. A snake_case id
was never a retired label to begin with, so neither existing guard's
`RETIRED_LABELS` tuple could have caught it.

The canonical agent-id list is imported from `app.schemas.agents` (never
hard-coded here) so this guard tracks the roster automatically if it ever
changes. Scope is the `TWELVE_AGENT_IDS` trading-team ids MINUS `trader`,
for the same reason `test_cr160_agent_rename.py` already excludes the
English word "Trader" from its label scan: "trader" (lowercase, no
underscore collision possible since it IS the bare id) is core app
vocabulary — the word for the *user* becoming one, the pricing tier, the
Day Trader risk preset — and appears legitimately dozens of times per file
(measured: every `content/ai_coach/*.json` and `content/glossary/terms.en.json`
file in this corpus uses it as an ordinary noun). A whole-corpus scan for
bare `trader` has no signal-to-noise ratio here; the two real DEF429
`trader`-as-agent-id leaks (2026_07.json entries 12/25, both fixed in this
same change) only ever appeared *alongside* other unambiguous snake_case ids
in a parenthetical list or an options array — ambiguity that does not
recur once those two sibling ids are also fixed, so this guard scans the
other 11 unambiguous ids and relies on the DEF423-style human sweep for the
rare case where "trader" alone leaks in a snake_case context. `concierge` is
excluded for a different reason: unlike the snake_case, multi-word
trading-team ids, "Concierge" (capitalised) IS the correct display name and
is meant to appear verbatim in user copy throughout the app
(`AGENT_DISPLAY_NAMES[AgentId.CONCIERGE] == "AMI Concierge"`), so a bare
"concierge" is not the same defect class. `risk_officer` is excluded because
it is a CR201 internal-compute-only identity, deliberately outside
`TWELVE_AGENT_IDS`/`AGENT_DISPLAY_NAMES` and never rendered to a user by
design (see `app/schemas/agents.py`'s own comment on `RISK_OFFICER`).

Every string value in the EN content JSON families this Defect covers
(`content/daily_challenges/*.json`, `content/ai_coach/*.json`,
`content/glossary/terms.en.json`) is walked, skipping known code-key fields
(`id`, `related_agent`, `related_agents`, `see_also`, `tags`, `category`,
`type`, `locale`, `related_lesson`, `related_lessons`, `answer`,
`difficulty`) where a raw id is the *correct* value, not a leak. AR/MS
sibling files and `content/_authoring/`/`content/i18n/` tooling are excluded
per this Defect's brief — the i18n lane owns retranslation and these ids are
frozen wire keys, not something a rename ever touches there.

Lesson prose (`content/lessons/*.en.mdx`) is separately checked: the only
places a raw id may legitimately appear are the YAML frontmatter block
(`tags`, `agent_callouts`, `prerequisites`, etc. — code metadata, not
rendered prose, same as a JSON `tags` array) and `<ChatWith agent="...">` /
similar component props — both code-facing, not prose a user reads as a
sentence. Fenced code blocks are excluded from the prose scan for the same
reason `test_cr160_agent_rename.py` already carves out `content/_authoring/`
— a lesson could legitimately show a JSON wire payload as a teaching
example (e.g. explaining what an API response looks like) without meaning
it as a UI label.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.schemas.agents import TWELVE_AGENT_IDS

REPO = Path(__file__).resolve().parents[3]

# "trader" is deliberately excluded — see module docstring. It is ordinary
# English vocabulary throughout this corpus (the user becoming a trader, the
# pricing tier, the Day Trader preset), the same ambiguity
# `test_cr160_agent_rename.py` already documents for the retired "Trader"
# agent label.
AGENT_ID_VALUES: tuple[str, ...] = tuple(
    a.value for a in TWELVE_AGENT_IDS if a.value != "trader"
)
_ID_PATTERN = re.compile(r"\b(" + "|".join(re.escape(v) for v in AGENT_ID_VALUES) + r")\b")

# Fields where a raw agent id is the CORRECT value (a wire-key reference),
# never a leak into user-visible prose.
_CODE_KEYS = {
    "id",
    "related_agent",
    "related_agents",
    "see_also",
    "tags",
    "category",
    "type",
    "locale",
    "related_lesson",
    "related_lessons",
    "answer",
    "difficulty",
}

_CONTENT_DIRS = (
    REPO / "content" / "daily_challenges",
    REPO / "content" / "ai_coach",
)
_GLOSSARY_EN = REPO / "content" / "glossary" / "terms.en.json"


def _en_json_files() -> list[Path]:
    files: list[Path] = []
    for d in _CONTENT_DIRS:
        for path in sorted(d.glob("*.json")):
            # Skip locale subdirectories reached via glob accidentally and
            # any non-EN sibling — content/daily_challenges/ar|ms/*.json and
            # content/ai_coach/ar|ms/*.json live in subdirectories, so a flat
            # glob("*.json") on the EN dir never touches them, but this stays
            # explicit in case layout changes.
            if "/ar/" in str(path) or "/ms/" in str(path):
                continue
            files.append(path)
    files.append(_GLOSSARY_EN)
    return files


def _walk_strings(obj, path, hits, skip_keys):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in skip_keys:
                continue
            _walk_strings(v, path + [str(k)], hits, skip_keys)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _walk_strings(v, path + [str(i)], hits, skip_keys)
    elif isinstance(obj, str):
        m = _ID_PATTERN.search(obj)
        if m:
            hits.append((".".join(path), m.group(1), obj))


def test_no_raw_agent_ids_in_user_visible_content_json():
    all_hits: list[str] = []
    for f in _en_json_files():
        data = json.loads(f.read_text(encoding="utf-8"))
        hits: list[tuple[str, str, str]] = []
        _walk_strings(data, [], hits, _CODE_KEYS)
        for field_path, agent_id, value in hits:
            all_hits.append(f"{f.relative_to(REPO)}::{field_path} -> {agent_id!r} in {value!r}")
    assert not all_hits, (
        "raw snake_case agent ids found in user-visible content JSON fields "
        "(expected the CR160 display title instead):\n" + "\n".join(all_hits)
    )


# ---------------------------------------------------------------------------
# Lesson prose — the only legitimate raw-id surfaces are agent_callouts
# frontmatter and agent="..." component props.
# ---------------------------------------------------------------------------

_AGENT_PROP = re.compile(r'agent="[a-z_]+"')
_FRONTMATTER_BLOCK = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_FENCED_CODE_BLOCK = re.compile(r"```.*?```", re.DOTALL)


def _strip_legitimate_id_surfaces(text: str) -> str:
    text = _FRONTMATTER_BLOCK.sub("", text, count=1)
    text = _FENCED_CODE_BLOCK.sub("", text)
    text = _AGENT_PROP.sub("", text)
    return text


def test_no_raw_agent_ids_in_lesson_prose_outside_known_surfaces():
    lessons_dir = REPO / "content" / "lessons"
    offenders: list[str] = []
    for path in sorted(lessons_dir.glob("*.en.mdx")):
        text = path.read_text(encoding="utf-8")
        stripped = _strip_legitimate_id_surfaces(text)
        m = _ID_PATTERN.search(stripped)
        if m:
            offenders.append(f"{path.name}: {m.group(1)!r}")
    assert not offenders, (
        "raw snake_case agent ids found in lesson prose outside agent_callouts/"
        "agent=\"...\" props/fenced code:\n" + "\n".join(offenders)
    )
