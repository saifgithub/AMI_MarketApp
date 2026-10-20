"""Pure logic for the exhaustive crawl (CR264): no driver, no Appium, all offline-testable.

The exhaustive crawler wants three things the CR163 explorer never needed, and
each is decided here, away from the device, so a wrong decision shows up in
`tests_offline` rather than as a mysterious night of device time:

1. **A snapshot per observation.** One `page_source` parse yields every node's
   type, id, label, value, bounds and state. The CR163 explorer made a
   WebDriverAgent round trip per attribute per element; an exhaustive crawl
   observes after EVERY press, so that cost had to go.
2. **A verdict on each press.** "Dead tap" = nothing observable changed. What
   counts as observable is a deliberate choice (see `signature`): digits are
   masked so the ticker tape and live prices cannot make every tap look alive.
3. **Coverage accounting.** Every discovered control ends in exactly one
   state: pressed with an outcome, exempt with a reason, or unpressed (which
   is a gate failure). Nothing is silently dropped.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

SCREEN_PREFIX = "ami.screen."
SHEET_PREFIX = "ami.sheet."
NEVER_PRESS_PATH = Path(__file__).resolve().parent / "never_press.json"
SPEND_LIMITS_PATH = Path(__file__).resolve().parent / "spend_limits.json"

# Same words as explorer.FORBIDDEN / EXITS. Imported rather than copied so the
# two crawlers can never disagree about what "destructive" means.
from crawler.explorer import EXITS, FORBIDDEN  # noqa: E402

_IOS_INTERACTIVE = {
    "XCUIElementTypeButton", "XCUIElementTypeLink", "XCUIElementTypeTextField",
    "XCUIElementTypeSecureTextField", "XCUIElementTypeSwitch",
}
_IOS_INPUT = {"XCUIElementTypeTextField", "XCUIElementTypeSecureTextField"}
_BOUNDS = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


@dataclass(frozen=True)
class Node:
    type: str
    ident: str
    label: str
    value: str
    x: int
    y: int
    w: int
    h: int
    visible: bool = True
    enabled: bool = True
    interactive: bool = False
    state: str = ""  # selected/checked flags, folded into the signature

    @property
    def cx(self) -> int:
        return self.x + self.w // 2

    @property
    def cy(self) -> int:
        return self.y + self.h // 2

    @property
    def is_input(self) -> bool:
        return self.type in _IOS_INPUT or "EditText" in self.type

    @property
    def is_toggle(self) -> bool:
        return self.type == "XCUIElementTypeSwitch" or "Switch" in self.type or "CheckBox" in self.type \
            or "Toggle" in self.type or self.state.startswith("checkable")


def _clean_ident(raw: str) -> str:
    return raw if raw.startswith("ami.") else ""


def parse_snapshot(xml: str, platform: str) -> list[Node]:
    """Flatten a `page_source` dump into nodes, document order preserved (so the
    LAST `ami.screen.*` node is the topmost surface)."""
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        return []
    nodes: list[Node] = []
    for el in root.iter():
        a = el.attrib
        if platform == "ios":
            typ = a.get("type") or el.tag
            if typ == "XCUIElementTypeApplication":
                continue
            try:
                x, y, w, h = (int(float(a.get(k, "0"))) for k in ("x", "y", "width", "height"))
            except ValueError:
                continue
            nodes.append(Node(
                type=typ,
                ident=_clean_ident(a.get("name", "")),
                label=(a.get("label") or "").strip(),
                value=(a.get("value") or "").strip(),
                x=x, y=y, w=w, h=h,
                visible=a.get("visible", "true") != "false",
                enabled=a.get("enabled", "true") != "false",
                interactive=typ in _IOS_INTERACTIVE,
                state="sel" if a.get("selected") == "true" else "",
            ))
        else:
            m = _BOUNDS.search(a.get("bounds", ""))
            if not m:
                continue
            x1, y1, x2, y2 = (int(g) for g in m.groups())
            checkable = a.get("checkable") == "true"
            state = ("checkable:" if checkable else "") + (
                "checked " if a.get("checked") == "true" else "") + (
                "sel" if a.get("selected") == "true" else "")
            nodes.append(Node(
                type=a.get("class", el.tag),
                ident=_clean_ident(a.get("resource-id", "")),
                label=(a.get("content-desc") or a.get("text") or "").strip(),
                value="",
                x=x1, y=y1, w=x2 - x1, h=y2 - y1,
                visible=True,
                enabled=a.get("enabled", "true") != "false",
                interactive=a.get("clickable") == "true",
                state=state.strip(),
            ))
    return _without_keyboard(nodes)


def _without_keyboard(nodes: list[Node]) -> list[Node]:
    """The iOS system keyboard is app-external furniture: its keys read as
    controls ("Next keyboard", emoji, Arabic glyphs) and focusing a field would
    otherwise look like navigation to a new screen. Remember where it is, drop
    everything inside it."""
    kbs = [n for n in nodes if n.type == "XCUIElementTypeKeyboard"]
    if not kbs:
        return nodes
    top = min(k.y for k in kbs)
    return [n for n in nodes if n.type != "XCUIElementTypeKeyboard" and n.cy < top]


def screen_key(nodes: list[Node]) -> str:
    """`ami.screen.<name>` of the topmost surface, else a label fingerprint.

    The fingerprint fallback is `fp:` prefixed so the coverage file never
    confuses a semantic id with a guess."""
    ids = [n.ident for n in nodes if n.ident.startswith(SCREEN_PREFIX) and n.visible]
    if ids:
        return ids[-1]
    labels = sorted({n.label for n in nodes if n.interactive and n.visible and n.label})
    return "fp:" + hashlib.sha256("|".join(labels).encode()).hexdigest()[:10]


def sheet_ids(nodes: list[Node]) -> frozenset[str]:
    return frozenset(n.ident for n in nodes if n.ident.startswith(SHEET_PREFIX) and n.visible)


_DIGITS = re.compile(r"\d")


def signature(nodes: list[Node]) -> str:
    """What a user could notice changing, minus live-data noise.

    Includes every visible label/value with digits masked to `#` (so "$10,000"
    -> "$##,###" and a ticking price is invisible, while a new toast, an
    expanded paragraph, a toggled switch or a selected chip is not), plus the
    interactive nodes' selected/checked state and the screen/sheet ids."""
    parts: set[str] = set()
    for n in nodes:
        if not n.visible:
            continue
        text = _DIGITS.sub("#", n.label)
        val = _DIGITS.sub("#", n.value)
        if text or val or n.ident:
            parts.add(f"{n.type[-12:]}|{n.ident}|{text}|{val}|{n.state}")
    return hashlib.sha256("\n".join(sorted(parts)).encode()).hexdigest()[:16]


def value_signature(nodes: list[Node]) -> str:
    """Unmasked values/states of interactive nodes only — a toggle flipping
    from "0" to "1" or a stepper going 3 -> 4 is a real change even though the
    masked signature cannot see it."""
    parts = sorted(f"{n.ident}|{n.label}|{n.value}|{n.state}" for n in nodes if n.interactive and n.visible)
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]


@dataclass(frozen=True)
class Snapshot:
    key: str
    sheets: frozenset[str]
    sig: str
    vsig: str
    nodes: tuple[Node, ...] = field(default=(), compare=False)


def take(nodes: list[Node]) -> Snapshot:
    return Snapshot(screen_key(nodes), sheet_ids(nodes), signature(nodes), value_signature(nodes), tuple(nodes))


def press_outcome(before: Snapshot, after: Snapshot, node: Node) -> str:
    """Classify one press. Order matters: the strongest evidence first."""
    if after.key != before.key:
        return "navigated"
    if after.sheets != before.sheets:
        return "sheet"
    if node.is_input:
        return "focused"
    if node.is_toggle and after.vsig != before.vsig:
        return "toggled"
    if after.sig != before.sig or after.vsig != before.vsig:
        return "changed"
    return "dead"


# -- control identity & classification -------------------------------------

def _id_label(label: str) -> str:
    """First line, digits masked: "1 unread message" and "3 unread message" are
    one control across visits, and a newline must not break the report."""
    first = (label.splitlines() or [""])[0].strip()
    return _DIGITS.sub("#", first)[:80]


def control_id(screen: str, node: Node) -> str:
    name = node.ident or _id_label(node.label) or "<unlabelled@%d,%d>" % (node.cx // 10, node.cy // 10)
    return f"{screen}|{name}|{node.type[-14:]}"


def load_never_press(path: Path = NEVER_PRESS_PATH) -> dict[str, str]:
    data = json.loads(path.read_text()) if path.exists() else {}
    return {k: v for k, v in data.items() if not k.startswith("_")}


def never_press_reason(screen: str, node: Node, table: dict[str, str]) -> str | None:
    """Exact (case-insensitive) match on id or label, optionally scoped as
    `<screen>#<id or label>`; a key starting with `~` is a label substring."""
    names = [s.lower() for s in (node.ident, node.label) if s]
    for key, reason in table.items():
        k = key.lower()
        scope, _, target = k.partition("#") if "#" in k else ("", "", k)
        if scope and scope != screen.lower():
            continue
        if target.startswith("~"):
            if any(target[1:] in n for n in names):
                return reason
        elif target in names:
            return reason
    return None


def load_spend_limits(path: Path = SPEND_LIMITS_PATH) -> dict[str, dict]:
    data = json.loads(path.read_text()) if path.exists() else {}
    return {k: v for k, v in data.items() if not k.startswith("_")}


def spend_group(limits: dict[str, dict], screen: str, node: Node,
                intent_expect: str | None, intent_label: str = "", intent_target: str = "") -> str | None:
    """Which spend group (if any) pressing `node` would draw from. Only a
    destructive-intent control, or one the catalogue does not know, spends."""
    if node.is_input:
        return None
    label = " ".join((node.label or "").lower().split())
    for name, g in limits.items():
        if intent_target and intent_target in g.get("intent_targets", []):
            return name  # entering the Room is itself the spend, whatever the control is
        if intent_label and any(t in intent_label.lower() for t in g.get("intent_label_contains", [])):
            return name
        if intent_expect not in (None, "destructive"):
            continue
        if g.get("screens") and screen not in g["screens"]:
            continue
        if g.get("label_regex") and re.search(g["label_regex"], label):
            return name
    return None


def classify(node: Node) -> str:
    """`unlabelled` | `destructive` | `external` | `safe`.

    Destructive controls are not skipped — they are pressed LAST. An
    unlabelled control is the same class: it cannot be proven not to be
    "delete", so it waits at the back with the ones that can."""
    low = (node.label or "").lower()
    if not low and not node.ident:
        return "unlabelled"
    if any(w in low for w in FORBIDDEN):
        return "destructive"
    if any(w in low for w in EXITS):
        return "external"
    return "safe"


def is_chrome(node: Node, nav_ids: set[str]) -> bool:
    """Bottom-nav tabs are the crawl's own navigation, pressed as roots."""
    return node.ident in nav_ids


# -- coverage accounting ---------------------------------------------------

@dataclass
class Control:
    id: str
    screen: str
    label: str
    ident: str
    type: str
    kind: str                # button | toggle | input | nav | destructive | external | unlabelled
    pressed: bool = False
    outcome: str = ""
    exempt: str = ""         # reason; non-empty => not counted against the gate
    finding: list[str] = field(default_factory=list)
    leads_to: str = ""
    expect: str = ""         # from the intent catalogue
    intent: str = ""         # ok | mismatch | unexplained | precondition_not_met | ""


class Coverage:
    def __init__(self, expected_screens: list[str] | None = None):
        self.controls: dict[str, Control] = {}
        self.screens: dict[str, dict] = {}
        self.expected = sorted(expected_screens or [])

    def see_screen(self, key: str, *, path: list[str], screenshot: str = "") -> bool:
        if key in self.screens:
            return False
        self.screens[key] = {"path": path, "screenshot": screenshot}
        return True

    def discover(self, screen: str, node: Node, kind: str) -> Control:
        cid = control_id(screen, node)
        if cid not in self.controls:
            self.controls[cid] = Control(cid, screen, node.label, node.ident, node.type, kind)
        return self.controls[cid]

    def mark(self, ctl: Control, outcome: str, *, finding: str = "", leads_to: str = "") -> None:
        ctl.pressed = True
        ctl.outcome = outcome
        if leads_to:
            ctl.leads_to = leads_to
        if finding:
            ctl.finding.append(finding)

    def exempt(self, ctl: Control, reason: str) -> None:
        ctl.exempt = reason
        ctl.outcome = ctl.outcome or "exempt"

    def unreached_screens(self) -> list[str]:
        return [s for s in self.expected if s not in self.screens]

    def unpressed(self) -> list[Control]:
        return [c for c in self.controls.values() if not c.pressed and not c.exempt]

    def with_findings(self) -> list[Control]:
        return [c for c in self.controls.values() if c.finding]

    def totals(self) -> dict:
        cs = list(self.controls.values())
        return {
            "screens_reached": len(self.screens),
            "screens_expected": len(self.expected),
            "screens_unreached": len(self.unreached_screens()),
            "controls_discovered": len(cs),
            "controls_pressed": sum(c.pressed for c in cs),
            "controls_exempt": sum(bool(c.exempt) and not c.pressed for c in cs),
            "controls_unpressed": len(self.unpressed()),
            "controls_with_findings": len(self.with_findings()),
            "controls_unexplained": sum(c.intent == "unexplained" for c in cs),
            "intent_mismatches": sum(c.intent == "mismatch" for c in cs),
            "preconditions_not_met": sum(c.intent == "precondition_not_met" for c in cs),
        }

    def gate_failures(self, extra_findings: list[str] | None = None) -> list[str]:
        """Everything that must make UAT-CTRL-001 fail, as human lines."""
        out = [f"screen not reached: {s}" for s in self.unreached_screens()]
        out += [f"control not pressed: {c.id} ({c.outcome or 'never reached'})" for c in self.unpressed()]
        for c in self.with_findings():
            out += [f"finding on {c.id}: {f}" for f in c.finding]
        out += extra_findings or []
        return out

    def to_json(self) -> dict:
        return {
            "totals": self.totals(),
            "screens": self.screens,
            "unreached_screens": self.unreached_screens(),
            "controls": [c.__dict__ for c in self.controls.values()],
        }

    def to_markdown(self, *, runtime_s: float = 0.0, notes: list[str] | None = None) -> str:
        t = self.totals()
        lines = [
            "# Control coverage", "",
            f"1. screens reached: **{t['screens_reached']}** of {t['screens_expected']} expected",
            f"2. controls discovered: **{t['controls_discovered']}**, pressed **{t['controls_pressed']}**, "
            f"exempt **{t['controls_exempt']}**, unpressed **{t['controls_unpressed']}**",
            f"3. controls with findings: **{t['controls_with_findings']}** "
            f"(unexplained {t['controls_unexplained']}, intent mismatches {t['intent_mismatches']}, "
            f"preconditions not met {t['preconditions_not_met']})",
            f"4. runtime: {runtime_s / 60:.1f} min", "",
        ]
        if notes:
            lines += ["## Notes", ""] + [f"{i}. {n}" for i, n in enumerate(notes, 1)] + [""]
        if self.unreached_screens():
            lines += ["## Unreached known screens", ""]
            lines += [f"{i}. `{s}`" for i, s in enumerate(self.unreached_screens(), 1)] + [""]
        if self.unpressed():
            lines += ["## Unpressed controls", ""]
            lines += [f"{i}. `{c.id}` — {c.outcome or 'never reached'}" for i, c in enumerate(self.unpressed(), 1)] + [""]
        exempt = [c for c in self.controls.values() if c.exempt and not c.pressed]
        if exempt:
            lines += ["## Exempt controls", ""]
            lines += [f"{i}. `{c.id}` — {c.exempt}" for i, c in enumerate(exempt, 1)] + [""]
        if self.with_findings():
            lines += ["## Findings", ""]
            n = 0
            for c in self.with_findings():
                for f in c.finding:
                    n += 1
                    lines.append(f"{n}. `{c.id}` — {f}")
            lines.append("")
        lines += ["## Screens reached", ""]
        lines += [f"{i}. `{k}` via {' > '.join(v['path']) or '(root)'}" for i, (k, v) in enumerate(sorted(self.screens.items()), 1)]
        return "\n".join(lines) + "\n"

    def write(self, out: Path, *, runtime_s: float = 0.0, notes: list[str] | None = None) -> None:
        out.mkdir(parents=True, exist_ok=True)
        (out / "control_coverage.json").write_text(json.dumps(self.to_json(), indent=2) + "\n")
        (out / "coverage.md").write_text(self.to_markdown(runtime_s=runtime_s, notes=notes))


def expected_screens_from(module) -> list[str]:
    """Every `ami.screen.*` string anywhere in a config module — read
    dynamically so Phase A adding a screen id is enough to put it on the gate."""
    found: set[str] = set()

    def walk(v):
        if isinstance(v, str):
            if v.startswith(SCREEN_PREFIX):
                found.add(v)
        elif isinstance(v, dict):
            for x in list(v.keys()) + list(v.values()):
                walk(x)
        elif isinstance(v, (list, tuple, set, frozenset)):
            for x in v:
                walk(x)

    for name, value in vars(module).items():
        if not name.startswith("_"):
            walk(value)
    return sorted(found)
