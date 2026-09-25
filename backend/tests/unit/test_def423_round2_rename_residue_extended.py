"""DEF423 round 2 — MAJOR-1 companion guard.

The auditor (U66, round 1) reintroduced one retired agent label into each of
four areas this Defect's three lanes actually touched, ran
`test_def423_agent_rename_residue.py` + `test_cr160_agent_rename.py`, and
three of the four mutations passed clean:

    M1 room_prompts.py: "Execution Desk's size" -> "Trader's size"   NOT CAUGHT
    M2 lesson 283: first "CIO" -> "PM"                               NOT CAUGHT
    M3 app_en.arb: "Technical Strategist" -> "Market Analyst"        caught
    M4 content/ai_coach/ai_meta.json: "CIO" -> "PM"                  NOT CAUGHT

`test_def423_agent_rename_residue.py` only ever scanned `app_en.arb`, the
Flutter registry, and `content/agents/*.md` — the same P37 shape one layer
down: a rename's guard scans one corpus (or three), a structurally identical
sibling corpus (backend prompt-building modules, lesson prose, content JSON)
has none. This module is that guard, covering exactly the three areas the
auditor's mutation matrix found uncovered, plus the website chatbot FAQ named
in the DEF423 architect doc's attack surface item 2.

Scope, one function per area:

1. **Backend string constants that reach prompts or users** — an AST scan of
   every string literal in `backend/app/**/*.py`, excluding docstrings (the
   first statement of a module/class/function body), comments (invisible to
   the AST), and the first positional argument of a `logger.<level>(...)`
   call (a log key, not user copy). A small, named allowlist covers real
   exceptions the scan would otherwise flag — see `_BACKEND_ALLOWLIST` for
   the reasoning on each entry.
2. **Lesson prose** (`content/lessons/*.en.mdx`) — reuses
   `test_cr160_agent_rename.py`'s own `RETIRED_LABELS` tuple and mirrors its
   allowlist rules (a fenced code block is not prose; "PM" survives as a
   time-of-day inside a digits-then-PM pattern, the Philip Morris ticker
   `(PM)`, and the `Trader A/B/C` exercise-persona convention that
   `test_cr160_agent_rename.py`'s own docstring documents for "Trader").
3. **Content JSON user-visible fields** — reuses `test_def429_no_raw_agent_ids_in_content.py`'s
   `_walk_strings` walker and `_CODE_KEYS` skip-set, swapping the raw-id
   pattern for the retired-label pattern, over the same three EN families
   (`content/daily_challenges/*.json`, `content/ai_coach/*.json`,
   `content/glossary/terms.en.json`).
4. **The website chatbot FAQ** (`website_api/app/knowledge/faq.md`) — a
   direct label scan; the FAQ is small enough that no code-key/prose
   distinction is needed.

`test_def423_agent_rename_residue.py` keeps its own five tests (ARB, Flutter
registry, agent prompt markdown) — this module does not duplicate that
coverage, only what fell in the gap between it, `test_cr160_agent_rename.py`,
and `test_def429_no_raw_agent_ids_in_content.py`.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from app.schemas.agents import TWELVE_AGENT_IDS  # noqa: F401  (import-path sanity)

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

# Bare "PM" as the retired Portfolio Manager abbreviation, possessive
# included ("PM's", "PM’s": the form the residue actually took). Excludes a
# time-of-day ("4 PM ET"), the Philip Morris ticker "(PM)", and anything
# already caught by the label scan above.
_BARE_PM = re.compile(r"(?<![A-Za-z])PM(?![A-Za-z])")
_PM_TIME_CONTEXT = re.compile(r"\b\d{1,2}\s*PM\b", re.IGNORECASE)
_PM_TICKER_CONTEXT = re.compile(r"\(PM\)")

# Bare "Trader" as the retired agent label. "Trader A/B/C" and "Trader 1/2/3/…"
# (numbered exercise personas, e.g. the herding-cascade lesson), "Day Trader"
# (the CR129 risk preset), and the $14.99/mo pricing tier (named "Trader" —
# CLAUDE.md's Pricing decision row) are excluded — the same ambiguity
# `test_cr160_agent_rename.py`'s own docstring documents for why it drops
# "Trader" from its whole-corpus scan.
_BARE_TRADER = re.compile(r"\bTrader\b")
_TRADER_ALLOWED_CONTEXT = re.compile(
    r"Day Trader"
    r"|Trader\s*[\*_]*\s*[A-C0-9]+\b"
    r"|Trader['’]s \$14\.99"
    r"|\$14\.99.{0,20}Trader"
    r"|Floor Pass|Floor Manager"
    r"|paid tiers"
)


def _has_bare_pm(text: str) -> list[str]:
    hits = []
    for m in _BARE_PM.finditer(text):
        window = text[max(0, m.start() - 12): m.end() + 4]
        if _PM_TIME_CONTEXT.search(window) or _PM_TICKER_CONTEXT.search(window):
            continue
        hits.append(window)
    return hits


def _has_bare_trader(text: str) -> list[str]:
    hits = []
    for m in _BARE_TRADER.finditer(text):
        window = text[max(0, m.start() - 60): m.end() + 60]
        if _TRADER_ALLOWED_CONTEXT.search(window):
            continue
        hits.append(text[max(0, m.start() - 20): m.end() + 20])
    return hits


def _has_retired_label(text: str) -> list[str]:
    return [label for label in RETIRED_LABELS if label in text]


# ---------------------------------------------------------------------------
# Area 1 — backend string constants (AST scan)
# ---------------------------------------------------------------------------

_LOG_CALL_NAMES = {"debug", "info", "warning", "error", "critical", "exception"}

# Every entry here is a real, reasoned exception — not a growing escape
# hatch. Format: (relative file path, line, why).
_BACKEND_ALLOWLIST = {
    # Legacy sentinel kept byte-identical on purpose so a verdict row banked
    # before this round is still recognised by `is_llm_outage_verdict`
    # (DEF423 round 2, MAJOR-2). Never used to mint a new verdict.
    ("app/services/room_runner.py", "_PM_LLM_UNAVAILABLE_REASON_LEGACY"): (
        "pre-rename sentinel kept verbatim for stored-row equality matching"
    ),
    # Internal numeric-provenance audit rows (CR104) — developer-facing
    # explanations of where a number came from, never rendered to a user or
    # fed to an LLM prompt. Round-1 audit already ruled the line 204 entry a
    # non-finding on the same grounds; 257/273 are the same row family.
    ("app/services/numeric_provenance.py", None): (
        "internal provenance rows, not user- or agent-facing copy"
    ),
    # DEF423 round-1-approved ticker-collision guard: "PM" as a time-of-day/
    # abbreviation entry in a blocklist of caps words that collide with
    # ticker-looking tokens. Not an agent title anywhere near it.
    ("app/services/fundamentals.py", "_TICKER_BLOCKLIST"): (
        "PM listed as a time-of-day/abbreviation collision, not an agent title"
    ),
    # "Trader" as the *user's own* default display name in dev/test-mode
    # Mandate constructors (1-on-1 pre-auth flows) — not the retired agent
    # label. Three call sites, one per module that hydrates a dev Mandate.
    ("app/services/brief_engine.py", "hydrate_brief_mandate"): (
        "default value for the USER's display_name in a dev-mode Mandate, not an agent title"
    ),
    ("app/services/agent_runner.py", "hydrate_mandate"): (
        "default value for the USER's display_name in a dev-mode Mandate, not an agent title"
    ),
    ("app/services/concierge_engine.py", "session_to_mandate_dict"): (
        "default value for the USER's display_name from onboarding, not an agent title"
    ),
}


def _is_docstring_node(node) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and _is_docstring_node(body[0]):
            ids.add(id(body[0].value))
    return ids


def _is_log_call_arg(node: ast.Constant, ancestors: list[ast.AST]) -> bool:
    """True for any positional or keyword argument (log keys AND context
    values like `note=`/`key=`) to a `logger.<level>(...)` call — none of
    that is copy a user or an LLM prompt ever sees."""
    for anc in reversed(ancestors):
        if isinstance(anc, ast.Call):
            func = anc.func
            fname = func.attr if isinstance(func, ast.Attribute) else (
                func.id if isinstance(func, ast.Name) else None
            )
            if fname not in _LOG_CALL_NAMES:
                return False
            if any(a is node for a in anc.args):
                return True
            return any(kw.value is node for kw in anc.keywords)
    return False


def _is_dunder_all_element(node: ast.Constant, ancestors: list[ast.AST]) -> bool:
    """True for a string literal that is an element of an `__all__` list/tuple
    — those name Python identifiers (re-exports), not user- or agent-facing
    copy, even when the identifier itself contains a retired word like
    "Debator" (`DebatorSizes`, a `NamedTuple` type name)."""
    for anc in ancestors:
        if isinstance(anc, ast.Assign):
            targets = anc.targets
            if any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets):
                return True
    return False


def _file_is_fully_allowlisted(rel: str) -> bool:
    for (fkey, marker), _why in _BACKEND_ALLOWLIST.items():
        if marker is None and rel.endswith(fkey):
            return True
    return False


def _name_is_allowlisted(rel: str, names_in_scope: set[str]) -> bool:
    for (fkey, marker), _why in _BACKEND_ALLOWLIST.items():
        if marker is not None and rel.endswith(fkey) and marker in names_in_scope:
            return True
    return False


def _enclosing_names(ancestors: list[ast.AST]) -> set[str]:
    """Names of the assignment target(s), function, or class that directly
    or transitively contain the current node — e.g. for
    `_TICKER_BLOCKLIST: frozenset[str] = frozenset({"PM", ...})`, the string
    "PM" is inside an `AnnAssign`/`Assign` whose target is
    `_TICKER_BLOCKLIST`."""
    names: set[str] = set()
    for anc in ancestors:
        if isinstance(anc, ast.Assign):
            for t in anc.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(anc, ast.AnnAssign) and isinstance(anc.target, ast.Name):
            names.add(anc.target.id)
        elif isinstance(anc, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(anc.name)
    return names


def _scan_backend_file(path: Path) -> list[tuple[int, str, str]]:
    """Returns (lineno, kind, text) for retired-title hits in one file."""
    try:
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(path))
    except SyntaxError:
        return []

    try:
        rel = path.relative_to(REPO).as_posix()
    except ValueError:
        rel = str(path)

    if _file_is_fully_allowlisted(rel):
        return []

    doc_ids = _docstring_ids(tree)
    hits: list[tuple[int, str, str]] = []
    stack: list[ast.AST] = []

    class Visitor(ast.NodeVisitor):
        def generic_visit(self, node):
            stack.append(node)
            super().generic_visit(node)
            stack.pop()

        def visit_Constant(self, node: ast.Constant):
            if isinstance(node.value, str) and id(node) not in doc_ids:
                text = node.value
                if (
                    not _is_log_call_arg(node, stack)
                    and not _is_dunder_all_element(node, stack)
                    and not _name_is_allowlisted(rel, _enclosing_names(stack))
                ):
                    for label in RETIRED_LABELS:
                        if label in text:
                            hits.append((node.lineno, "TITLE", text[:160]))
                    for _ in _has_bare_pm(text):
                        hits.append((node.lineno, "BARE_PM", text[:160]))
                    for _ in _has_bare_trader(text):
                        hits.append((node.lineno, "BARE_TRADER", text[:160]))
            self.generic_visit(node)

    Visitor().visit(tree)
    return hits


def test_no_retired_agent_labels_in_backend_string_constants():
    backend_app = REPO / "backend" / "app"
    all_hits: list[str] = []
    for py in sorted(backend_app.rglob("*.py")):
        for lineno, kind, text in _scan_backend_file(py):
            rel = py.relative_to(REPO).as_posix()
            all_hits.append(f"{rel}:{lineno} [{kind}] {text!r}")
    assert not all_hits, (
        "retired agent titles found in backend/app string constants "
        "(prompts and/or user-visible strings):\n" + "\n".join(all_hits)
    )


def test_backend_ast_scan_finds_the_known_positive():
    """Validates the scanner itself: it must find the two pre-fix "Trader"
    role-header/INPUTS-list occurrences this Defect's round 2 actually
    removed from `overlay_generator.py`. Run against a synthetic module with
    the pre-fix text (not by reverting the real file), so this test cannot
    regress by the real fix simply staying in place."""
    import tempfile

    sample = (
        "def _trader_block():\n"
        "    parts = [\n"
        '        "## Role guidance — Trader",\n'
        '        "INPUTS:",\n'
        '        "- Trader\'s proposal",\n'
        "    ]\n"
        "    return parts\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(sample)
        tmp_path = Path(f.name)
    try:
        hits = _scan_backend_file(tmp_path)
        assert hits, "scanner failed to find the known-positive 'Trader' role text"
    finally:
        tmp_path.unlink(missing_ok=True)

    # DEF423 round 2 MAJOR-1: both of that round's own "PM's" fixes could be
    # reverted with the guard green, because the lookahead excluded "'".
    for possessive in ("PM's", "PM\u2019s"):
        sample = f'NOTE = "You can shape the {possessive} own view."\n'
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(sample)
            tmp_path = Path(f.name)
        try:
            assert _scan_backend_file(tmp_path), (
                f"scanner failed to find the possessive {possessive!r}"
            )
        finally:
            tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Area 2 — lesson prose
# ---------------------------------------------------------------------------

_FRONTMATTER_BLOCK = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_FENCED_CODE_BLOCK = re.compile(r"```.*?```", re.DOTALL)


def _strip_non_prose(text: str) -> str:
    text = _FRONTMATTER_BLOCK.sub("", text, count=1)
    text = _FENCED_CODE_BLOCK.sub("", text)
    return text


def test_no_retired_agent_labels_in_lesson_prose():
    lessons_dir = REPO / "content" / "lessons"
    offenders: list[str] = []
    for path in sorted(lessons_dir.glob("*.en.mdx")):
        prose = _strip_non_prose(path.read_text(encoding="utf-8"))
        for label in _has_retired_label(prose):
            offenders.append(f"{path.name}: label {label!r}")
        for hit in _has_bare_pm(prose):
            offenders.append(f"{path.name}: bare PM near {hit!r}")
        for hit in _has_bare_trader(prose):
            offenders.append(f"{path.name}: bare Trader near {hit!r}")
    assert not offenders, (
        "retired agent labels found in content/lessons/*.en.mdx prose:\n"
        + "\n".join(offenders)
    )


# ---------------------------------------------------------------------------
# Area 3 — content JSON user-visible fields (reuses DEF429's walker shape)
# ---------------------------------------------------------------------------

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

_CONTENT_JSON_DIRS = (
    REPO / "content" / "daily_challenges",
    REPO / "content" / "ai_coach",
)
_GLOSSARY_EN = REPO / "content" / "glossary" / "terms.en.json"


def _en_json_files() -> list[Path]:
    files: list[Path] = []
    for d in _CONTENT_JSON_DIRS:
        for path in sorted(d.glob("*.json")):
            if "/ar/" in str(path) or "/ms/" in str(path):
                continue
            files.append(path)
    if _GLOSSARY_EN.exists():
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
        for label in _has_retired_label(obj):
            hits.append((".".join(path), "TITLE", label, obj))
        for hit in _has_bare_pm(obj):
            hits.append((".".join(path), "BARE_PM", hit, obj))


def test_no_retired_agent_labels_in_content_json():
    all_hits: list[str] = []
    for f in _en_json_files():
        data = json.loads(f.read_text(encoding="utf-8"))
        hits: list[tuple[str, str, str, str]] = []
        _walk_strings(data, [], hits, _CODE_KEYS)
        for field_path, kind, needle, value in hits:
            all_hits.append(
                f"{f.relative_to(REPO)}::{field_path} [{kind}] {needle!r} in {value!r}"
            )
    assert not all_hits, (
        "retired agent labels found in user-visible content JSON fields:\n"
        + "\n".join(all_hits)
    )


# ---------------------------------------------------------------------------
# Area 4 — website chatbot FAQ
# ---------------------------------------------------------------------------


def test_no_retired_agent_labels_in_website_faq():
    faq = REPO / "website_api" / "app" / "knowledge" / "faq.md"
    if not faq.exists():
        return
    text = faq.read_text(encoding="utf-8")
    offenders: list[str] = []
    for label in _has_retired_label(text):
        offenders.append(f"label {label!r}")
    for hit in _has_bare_pm(text):
        offenders.append(f"bare PM near {hit!r}")
    for hit in _has_bare_trader(text):
        offenders.append(f"bare Trader near {hit!r}")
    assert not offenders, (
        "retired agent labels found in website_api/app/knowledge/faq.md:\n"
        + "\n".join(offenders)
    )
