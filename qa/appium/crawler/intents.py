"""Control-intent catalogue: what every control is SUPPOSED to do (CR264).

"Pressed" is not "works". Saiful (2026-10-20): *"tapping on each button also
means you need to know what each button is supposed to do."* The catalogue under
`qa/uat/controls/<area>.yaml` states, per control, the expected effect; the
exhaustive crawler asserts it after every press.

    screen: ami.screen.journal_detail
    source: mobile/lib/screens/journal/journal_detail_screen.dart
    controls:
      - label: "SEE CHART"          # or id: ami.journal.see_chart (or both)
        kind: button
        expect: navigate            # navigate|sheet|dialog|state|external|back|destructive|none
        target: ami.screen.chart_fullscreen
        when: "entry has a ticker"  # optional; an unmet precondition is NOT a failure
        line: 412

This module is pure (no driver). The loader validates the schema strictly and
reports every problem at once: a catalogue silently skipping a malformed entry
would turn "this control is unexplained" into "this control is fine".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

KINDS = {"button", "icon", "chip", "toggle", "tab", "menu_item", "list_row", "link", "field"}
EXPECTS = {"navigate", "sheet", "dialog", "state", "external", "back", "destructive", "none"}
NEEDS_TARGET = {"navigate", "sheet", "dialog"}
DEFAULT_DIR = Path(__file__).resolve().parents[2] / "uat" / "controls"


class IntentSchemaError(ValueError):
    """Every schema problem in the catalogue, one per line."""


@dataclass(frozen=True)
class Intent:
    screen: str
    label: str
    ident: str
    kind: str
    expect: str
    target: str = ""
    state: str = ""
    when: str = ""
    line: int = 0
    source: str = ""

    @property
    def name(self) -> str:
        return self.ident or self.label


def validate_doc(doc, origin: str, warns: list[str] | None = None) -> tuple[list[Intent], list[str]]:
    errs: list[str] = []
    warns = warns if warns is not None else []
    if not isinstance(doc, dict):
        return [], [f"{origin}: top level must be a mapping"]
    screen = doc.get("screen")
    if not isinstance(screen, str) or not screen.startswith("ami.screen."):
        errs.append(f"{origin}: `screen` must be a string starting with 'ami.screen.' (got {screen!r})")
    source = doc.get("source")
    if not isinstance(source, str) or not source:
        errs.append(f"{origin}: `source` is required")
    controls = doc.get("controls")
    if not isinstance(controls, list):
        return [], errs + [f"{origin}: `controls` must be a list"]
    out: list[Intent] = []
    seen: set[str] = set()
    for i, c in enumerate(controls):
        where = f"{origin}: controls[{i}]"
        if not isinstance(c, dict):
            errs.append(f"{where}: must be a mapping")
            continue
        label, ident = c.get("label") or "", c.get("id") or ""
        if not (isinstance(label, str) and isinstance(ident, str)) or not (label or ident):
            errs.append(f"{where}: needs a `label` or an `id`")
            continue
        where = f"{origin}: control {ident or label!r}"
        kind, expect = c.get("kind"), c.get("expect")
        if kind not in KINDS:
            errs.append(f"{where}: kind {kind!r} not in {sorted(KINDS)}")
        if expect not in EXPECTS:
            errs.append(f"{where}: expect {expect!r} not in {sorted(EXPECTS)}")
        target = c.get("target") or ""
        if expect in NEEDS_TARGET and not (isinstance(target, str) and target.startswith("ami.")):
            errs.append(f"{where}: expect={expect} needs `target` (an ami.* id)")
        state = c.get("state") or ""
        if expect == "state" and not (isinstance(state, str) and state):
            errs.append(f"{where}: expect=state needs a human-readable `state`")
        if c.get("when") is not None and not isinstance(c["when"], str):
            errs.append(f"{where}: `when` must be a string")
        if c.get("line") is not None and not isinstance(c["line"], int):
            errs.append(f"{where}: `line` must be an integer")
        dup = (ident or label).lower()
        if dup in seen:
            warns.append(f"{where}: duplicate entry on this screen (first one wins)")
            continue
        seen.add(dup)
        if kind in KINDS and expect in EXPECTS and isinstance(screen, str):
            out.append(Intent(screen, label, ident, kind, expect, target, state,
                              c.get("when") or "", c.get("line") or 0, source or ""))
    return out, errs


_PAREN = re.compile(r"\s*\([^)]*\)\s*$")
_PLACEHOLDER = re.compile(r"<[^>]*>")


def label_pattern(label: str) -> re.Pattern:
    """Catalogue labels are descriptions, not always the rendered string:
    `send (arrow_upward icon)` describes a control whose label is `send`;
    `CONVENE THE ROOM · <TICKER>` has a placeholder. Strip a trailing
    parenthetical, turn each <...> into a wildcard, anchor the rest."""
    base = _PAREN.sub("", label.strip())
    alts = _PLACEHOLDER.findall(base)
    if len(alts) == 1 and ":" in alts[0] and "/" in alts[0] and base.strip() == alts[0]:
        # `<suggested ticker chip: AAPL / MSFT / NVDA>` lists the literal labels.
        options = [a.strip().lower() for a in alts[0][1:-1].split(":", 1)[1].split("/") if a.strip()]
        return re.compile("|".join(re.escape(o) for o in options)) if options else re.compile(r"(?!)")
    parts = _PLACEHOLDER.split(base)
    if sum(len(p.strip()) for p in parts) < 3:
        return re.compile(r"(?!)")  # a pure placeholder describes nothing matchable
    return re.compile(".+".join(re.escape(p.strip().lower()) if p.strip() else "" for p in parts) if len(parts) > 1
                      else re.escape(base.lower()), re.S)


def _norm(label: str) -> str:
    return " ".join((label or "").lower().split())


def _find(entries: list[Intent], ident: str, label: str) -> Intent | None:
    if ident:
        for e in entries:
            if e.ident == ident:
                return e
    low = _norm(label)
    if not low:
        return None
    for e in entries:
        if e.label and _norm(e.label) == low:
            return e
    for e in entries:
        if e.label and label_pattern(_norm(e.label)).fullmatch(low):
            return e
    return None


class Catalogue:
    def __init__(self, intents: list[Intent] | None = None, warnings: list[str] | None = None):
        self.warnings = warnings or []
        self.by_screen: dict[str, list[Intent]] = {}
        for it in intents or []:
            self.by_screen.setdefault(it.screen, []).append(it)

    def __len__(self) -> int:
        return sum(len(v) for v in self.by_screen.values())

    def screens(self) -> list[str]:
        return sorted(self.by_screen)

    def lookup(self, screen: str, ident: str, label: str) -> Intent | None:
        """Find the entry for a control. This screen's entries first, then the
        whole catalogue: a widget file (floor_omnibox, hex_bottom_nav) has its
        own catalogue `screen:` but renders inside another screen's root id.
        Within a scope: id, then exact label, then label pattern."""
        for entries in (self.by_screen.get(screen, []), self._all()):
            hit = _find(entries, ident, label)
            if hit:
                return hit
        return None

    def _all(self) -> list[Intent]:
        return [e for es in self.by_screen.values() for e in es]

    def unseen(self, seen_names: set[tuple[str, str]]) -> list[Intent]:
        """Catalogue entries on reached screens that the crawl never met."""
        return [e for es in self.by_screen.values() for e in es
                if (e.screen, e.name.lower()) not in seen_names]


def load_dir(path: Path = DEFAULT_DIR) -> Catalogue:
    """Read every `*.yaml` under `path`. Missing directory => empty catalogue
    (the caller decides whether that is fatal; the UAT test makes it so)."""
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PyYAML is required for the control catalogue (pip install PyYAML)") from exc
    intents: list[Intent] = []
    errs: list[str] = []
    warns: list[str] = []
    for f in sorted(path.glob("*.yaml")) if path.exists() else []:
        try:
            doc = yaml.safe_load(f.read_text())
        except yaml.YAMLError as exc:
            errs.append(f"{f.name}: invalid YAML: {exc}")
            continue
        got, e = validate_doc(doc, f.name, warns)
        intents += got
        errs += e
    if errs:
        raise IntentSchemaError("\n".join(errs))
    return Catalogue(intents, warns)


# -- the post-press assertion ----------------------------------------------

@dataclass
class Verdict:
    status: str          # ok | mismatch | precondition_not_met | deferred
    detail: str = ""


def _screen_ids(snap) -> set[str]:
    return {n.ident for n in snap.nodes if n.ident and n.visible
            and (n.ident.startswith("ami.screen.") or n.ident.startswith("ami.sheet.")
                 or n.ident.startswith("ami.dialog."))}


def _actual(before, after, left_app: bool) -> str:
    if left_app:
        return "left the app"
    if after.key != before.key:
        return f"opened {after.key}"
    if after.sheets != before.sheets:
        return f"opened {sorted(after.sheets - before.sheets) or sorted(after.sheets)}"
    if after.sig != before.sig or after.vsig != before.vsig:
        return "changed state only"
    return "did nothing visible"


def check_expectation(intent: Intent, before, after, *, left_app: bool, prev_key: str | None) -> Verdict:
    """Assert `intent.expect` against what the press did.

    `destructive` is a scheduling instruction (press last), not an effect to
    assert, so it always passes here; likewise `none`, which also means a dead
    tap is the correct outcome (handled by the caller)."""
    e = intent.expect
    ok = True
    if e in ("navigate", "sheet", "dialog"):
        ids = _screen_ids(after)
        ok = intent.target in ids or after.key == intent.target
        want = f"to open {intent.target}"
    elif e == "back":
        ok = (after.key == prev_key) if prev_key else (after.key != before.key)
        want = f"to go back to {prev_key or 'the previous screen'}"
    elif e == "state":
        ok = (not left_app and after.key == before.key
              and (after.sig != before.sig or after.vsig != before.vsig))
        want = f"to change state ({intent.state})"
    elif e == "external":
        ok = left_app
        want = "to leave the app"
    else:
        return Verdict("ok")
    if ok:
        return Verdict("ok")
    detail = f"control {intent.name!r} expected {want}, but {_actual(before, after, left_app)}"
    if intent.when:
        return Verdict("precondition_not_met", f"{detail} (when: {intent.when})")
    return Verdict("mismatch", detail)
