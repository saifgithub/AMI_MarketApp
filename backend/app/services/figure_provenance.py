"""CR288 (ISS003) — figure provenance by value, run in SHADOW.

The Room's fact-check used to ask "which sheet field did the desk mean, and is it
wrong?" and was wrong about 99% of the time (DEF547, three rounds; FABLE's replay of
369 Rooms: 625 firings, 2 real misquotes). This module asks the question that needs no
reading of meaning: "is this number one the desk was shown?". It is FABLE's
`grounding.py` prototype, productionised.

Per figure in a desk's prose, three outcomes:
  record   - equals, at the prose figure's own precision (rounding or truncation, sign
             ignored, a percentage never matching an amount), a figure in the LEDGER:
             the text the desk's own prompt carried, minus the static instructions.
  derived  - not in the ledger, but a one-step calculation (ratio, premium, difference,
             percentage-of) from two grounded figures in the same sentence.
  own      - neither: the desk's own calculation, estimate, level or invention.
Plus `conditional` (an `own` figure inside an explicit "if ..." clause: a threshold or
falsifier, not a claim - ISS003 verdict 4.4) and `decision` (Entry/Stop/Target lines).

The ledger is built from the assembled prompt (`build_ledger`): everything the builder
put in except the static instructions, so a block added to the prompt tomorrow is in the
ledger tomorrow. Earlier turns are in it too, as source `debate`; a figure found only
there is counted apart (`record_debate_only`) because it was said by a desk, not shown
by the code.

SHADOW ONLY. Nothing here writes into a turn, a verdict, the stream or the bank. The one
output is the `room_figure_provenance` log event, one per desk turn. This module has no
function that produces user-visible text, on purpose (`test_cr288_figure_provenance.py`
pins it). A failure inside `log_turn_provenance` is logged loudly as
`room_figure_provenance_error` and never reaches the Room.

Known limits, accepted (ISS003 verdict 6): a dropped or flipped sign is not caught; a
right number under the wrong label passes; about 21% of altered figures land on another
ledger figure.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Sequence

import structlog

logger = structlog.get_logger(__name__)

#: More `own` figures than this in one turn is the extractor or the ledger failing, not
#: a desk doing arithmetic (FABLE 5.2.3: the worst whole Room listed 11 across all turns).
BREAKER_MAX_OWN_FIGURES = 6

#: The event lists at most this many `own` figures, each cut to `_FIG_MAX_CHARS`.
_OWN_LISTED_MAX = 12
_FIG_MAX_CHARS = 24

_MAG = {
    "k": 1e3, "thousand": 1e3, "ribu": 1e3,
    "m": 1e6, "mn": 1e6, "mil": 1e6, "million": 1e6, "juta": 1e6,
    "b": 1e9, "bn": 1e9, "bil": 1e9, "billion": 1e9, "bilion": 1e9,
    "t": 1e12, "trillion": 1e12, "trilion": 1e12,
}

_NUM = re.compile(
    r"(?:(?<![\w.,])[-−+])?(?P<cur>US\$|S\$|RM|MYR|[$£€])?\s?(?:(?<![\w.,])[-−+])?"
    r"(?P<int>\d{1,3}(?:,\d{3})+|\d+)(?:\.(?P<frac>\d+))?"
    r"(?:\s?(?P<mag>trillion|trilion|billion|bilion|million|thousand|juta|ribu|bil|mil|bn|mn|[kKmMbBtT])(?![A-Za-z]))?"
    r"(?P<unit>\s?%|\s?(?:x|×)(?![A-Za-z])|\s?pp\b|\s?bps\b|\s?pts?\b|:1\b)?",
    re.IGNORECASE,
)

_PARAM_AFTER = re.compile(
    r"^[\s-]*(?:day|week|wk|month|year|yr|quarter|session|bar|period|share|trading|hour|minute)s?\b",
    re.IGNORECASE,
)
_PERIOD_BEFORE = re.compile(r"(?:FY|CY|Q|H)'?\s?$", re.IGNORECASE)
_NAME_BEFORE = re.compile(r"(?:S&P|Item|Rule|Form|top|Russell|Nasdaq|KLCI)[\s-]?$", re.IGNORECASE)
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b")
_DECISION_LINE = re.compile(
    r"^\s*[-*•]?\s*\**\s*(?:entry|target|stop|r:r|size|time horizon)\b[^:\n]{0,24}:", re.IGNORECASE
)
#: An explicit conditional opens a clause that runs to the end of its sentence.
_CONDITIONAL = re.compile(r"\b(?:if|unless|provided that|in case)\b", re.IGNORECASE)
#: AMI's own annotations inside a turn (geometry, truncation, fact-check notes) are not
#: the desk's words and carry figures AMI computed.
_AMI_MARK = re.compile(r"\[AMI[^\]]*\]")


@dataclass(frozen=True)
class Fig:
    raw: str
    value: float        # absolute value, magnitude applied
    mult: float         # the magnitude the text itself used (1.0 if none)
    dec: int            # decimals the text stated, in its own unit
    cls: str            # "pct" | "bps" | "amount" | "mult" | "ratio" | "plain"
    kind: str           # "figure" | "year" | "period" | "param" | "name" | "wordpart" | "smallint"
    start: int
    end: int


def _cls(cur: bool, mag: str, unit: str) -> str:
    if unit in ("%", "pp"):
        return "pct"
    if unit == "bps":
        return "bps"
    if unit == "x":
        return "mult"
    if unit == ":1":
        return "ratio"
    if cur or mag:
        return "amount"
    return "plain"


def extract(text: str) -> list[Fig]:
    """Every numeral in `text`. Used on BOTH sides (ledger text and desk prose), so a
    quirk in this function affects both sides the same way and cancels."""
    out: list[Fig] = []
    dates = [(d.start(), d.end()) for d in _DATE.finditer(text)]
    for m in _NUM.finditer(text):
        s, e = m.start("int"), m.end()
        if any(lo <= s < hi for lo, hi in dates):
            continue
        ip = m.group("int").replace(",", "")
        fr = m.group("frac") or ""
        mag = (m.group("mag") or "").lower()
        unit = (m.group("unit") or "").strip().lower().replace("×", "x")
        cur = bool(m.group("cur"))
        mult = _MAG.get(mag, 1.0)
        base = float(f"{ip}.{fr or '0'}")
        before, after = text[max(0, s - 10):s], text[e:e + 16]
        kind = "figure"
        bare = not (fr or cur or mag or unit)
        if s > 0 and text[s - 1].isalpha() and not cur:
            kind = "period" if _PERIOD_BEFORE.search(before) else "wordpart"
        elif after[:1].isalpha() and not mag and not unit:
            kind = "wordpart"
        elif not (cur or mag or unit) and _NAME_BEFORE.search(before):
            kind = "name"
        elif bare and len(ip) == 4 and 1900 <= base <= 2100:
            kind = "year"
        elif bare and (_PARAM_AFTER.match(after) or (before.endswith("(") and after[:1] == ")")):
            kind = "param"
        elif bare and base < 13:
            kind = "smallint"
        out.append(Fig(m.group(0).strip(), base * mult, mult, len(fr), _cls(cur, mag, unit), kind, m.start(), e))
    return out


def _compatible(claim_cls: str, entry_cls: str) -> bool:
    """A percentage is never an amount. Everything else may be written loosely
    ("P/E of 38.2" for the sheet's "38.2x")."""
    a, b = claim_cls, entry_cls
    if "any" in (a, b) or a == b or "plain" in (a, b):
        return True
    return {a, b} in ({"mult", "ratio"}, {"pct", "bps"})


def _same(claim: Fig, v: float) -> bool:
    """`v` equals the claim at the claim's own precision in the claim's own unit, by
    rounding OR truncation (desks truncate: 59,957M is written "$59.9B")."""
    unit = 10.0 ** -min(claim.dec, 6)
    delta = abs(v) / claim.mult - claim.value / claim.mult
    return -0.5 * unit - 1e-9 <= delta < unit - 1e-9


@dataclass(frozen=True)
class Entry:
    value: float
    cls: str
    source: str   # "sheet" | "prompt" | "debate" | "decision"


@dataclass
class Ledger:
    entries: list[Entry] = field(default_factory=list)

    def add_text(self, source: str, text: str) -> None:
        for f in extract(text):
            self.entries.append(Entry(f.value, f.cls, source))

    def add_value(self, source: str, value: float, cls: str = "any") -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return
        self.entries.append(Entry(abs(float(value)), cls, source))

    def find(self, claim: Fig) -> list[Entry]:
        return [
            en for en in self.entries
            if _compatible(claim.cls, en.cls) and _same(claim, en.value)
        ]

    def __len__(self) -> int:
        return len(self.entries)


def build_ledger(
    prompt: str,
    *,
    static: Sequence[str] = (),
    sheet: str = "",
    debate: str = "",
) -> Ledger:
    """The ledger of one desk's turn: every numeral in the assembled `prompt` except
    those in the `static` instruction segments. `sheet` and `debate` are the segments of
    the prompt that are the fact sheet and the earlier turns; they are carried under their
    own source names. Whatever else the prompt holds (mandate, portfolio, feed, coded
    lines, ladders, scoreboards, a Brief overlay) lands in source `prompt`, so a block
    nobody remembered to list is still in the ledger. A segment the prompt does not
    contain (a localisation differed) removes nothing and leaves the ledger wider, which
    errs toward fewer listed figures, never toward a false one."""
    rest = prompt
    for seg in (*static, sheet, debate):
        if seg:
            rest = rest.replace(seg, "\n")
    ledger = Ledger()
    ledger.add_text("prompt", rest)
    if sheet:
        ledger.add_text("sheet", sheet)
    if debate:
        ledger.add_text("debate", debate)
    return ledger


_SENT = re.compile(r"(?<=[.;!?])\s+|\n+")


def _sentence_span(text: str, pos: int) -> tuple[int, int]:
    lo = 0
    for m in _SENT.finditer(text):
        if m.end() <= pos:
            lo = m.end()
        else:
            return lo, m.start()
    return lo, len(text)


def _derived_from(claim: Fig, others: list[float]) -> str | None:
    """One-step calculations only, exact at the claim's precision. Deliberately small:
    each extra operation raises the chance a made-up figure matches."""
    vals = others[:8]
    for i, a in enumerate(vals):
        for j, b in enumerate(vals):
            if i == j or not a or not b:
                continue
            cands: list[tuple[str, float]] = [("difference", abs(a - b))]
            if claim.cls in ("pct", "plain"):
                cands += [("premium/discount", abs(a / b - 1) * 100), ("percentage of", a / b * 100)]
            if claim.cls == "bps":
                cands += [("difference in bps", abs(a - b) * 100)]
            if claim.cls in ("mult", "plain", "ratio"):
                cands += [("ratio", a / b)]
            for name, v in cands:
                if _same(claim, v):
                    return name
    return None


@dataclass(frozen=True)
class Provenance:
    fig: Fig
    status: str             # "record" | "derived" | "decision" | "conditional" | "own" | "not_a_figure"
    sources: tuple[str, ...] = ()
    how: str | None = None


def _in_conditional(text: str, pos: int) -> bool:
    lo, _hi = _sentence_span(text, pos)
    return _CONDITIONAL.search(text, lo, pos) is not None


def classify(text: str, ledger: Ledger) -> list[Provenance]:
    """Every numeral of the desk's own prose, classified. AMI's own `[AMI ...]` marks are
    removed first: they are not the desk's words and carry figures AMI computed."""
    text = _AMI_MARK.sub(" ", text or "")
    figs = extract(text)
    out: list[Provenance] = []
    grounded_vals: dict[int, float] = {}
    pending: list[tuple[int, Fig]] = []
    for idx, f in enumerate(figs):
        if f.kind != "figure":
            out.append(Provenance(f, "not_a_figure"))
            continue
        line_lo = text.rfind("\n", 0, f.start) + 1
        if _DECISION_LINE.match(text[line_lo:f.start + 1]):
            out.append(Provenance(f, "decision"))
            grounded_vals[idx] = f.value
            continue
        hits = ledger.find(f)
        if hits:
            out.append(Provenance(f, "record", tuple(sorted({h.source for h in hits}))))
            grounded_vals[idx] = f.value
        else:
            out.append(Provenance(f, "own"))
            pending.append((len(out) - 1, f))
    for out_idx, f in pending:
        lo, hi = _sentence_span(text, f.start)
        near = [
            (abs(figs[i].start - f.start), v) for i, v in grounded_vals.items()
            if lo <= figs[i].start < hi
        ]
        how = _derived_from(f, [v for _d, v in sorted(near)])
        if how:
            out[out_idx] = Provenance(f, "derived", how=how)
        elif _in_conditional(text, f.start):
            out[out_idx] = Provenance(f, "conditional")
    return out


def own_figures(text: str, ledger: Ledger) -> list[str]:
    """The desk's own figures, once each, as the desk wrote them."""
    seen: dict[str, None] = {}
    for p in classify(text, ledger):
        if p.status == "own":
            seen.setdefault(p.fig.raw, None)
    return list(seen)


@dataclass(frozen=True)
class TurnProvenance:
    counts: dict[str, int]
    own: list[str]              # distinct, as written, capped for the log
    own_total: int              # distinct, uncapped
    record_debate_only: int     # `record` figures found nowhere but earlier turns
    ledger_size: int
    breaker: bool


def assess_turn(text: str, ledger: Ledger) -> TurnProvenance:
    """Classify one desk turn."""
    provs = classify(text, ledger)
    counts = {"record": 0, "derived": 0, "own": 0, "conditional": 0, "decision": 0}
    debate_only = 0
    for p in provs:
        if p.status in counts:
            counts[p.status] += 1
        if p.status == "record" and set(p.sources) == {"debate"}:
            debate_only += 1
    own = list(dict.fromkeys(p.fig.raw for p in provs if p.status == "own"))
    return TurnProvenance(
        counts=counts,
        own=[o[:_FIG_MAX_CHARS] for o in own[:_OWN_LISTED_MAX]],
        own_total=len(own),
        record_debate_only=debate_only,
        ledger_size=len(ledger),
        breaker=len(own) > BREAKER_MAX_OWN_FIGURES,
    )


@dataclass
class PromptCapture:
    """What a prompt builder hands back so the shadow can build its ledger. The builder
    calls `fill` with the prompt it assembled; the runner reads the fields afterwards.
    Created only when the shadow switch is on, so with it off nothing is captured."""

    prompt: str = ""
    static: list[str] = field(default_factory=list)
    sheet: str = ""
    debate: str = ""
    filled: bool = False

    def fill(self, prompt: str, *, static: Sequence[str], sheet: str, debate: str) -> None:
        """Never raises: a capture failure must not break the prompt it observes."""
        try:
            self.prompt = prompt
            self.static = [s for s in static if s]
            self.sheet = sheet
            self.debate = debate
            self.filled = True
        except Exception:  # noqa: BLE001 - shadow only; see module docstring
            logger.error("room_figure_provenance_error", stage="capture", exc_info=True)


def log_turn_provenance(
    *,
    capture: PromptCapture | None,
    text: str,
    run_id: Any = None,
    agent_id: Any = None,
    market: Any = None,
    ticker: str | None = None,
    surface: str = "agent_text",
) -> TurnProvenance | None:
    """Emit the one `room_figure_provenance` event for a desk turn. Returns the
    assessment (tests read it), or None when there was nothing to assess or the shadow
    failed. NEVER raises: any failure is `room_figure_provenance_error` at error level
    and the Room carries on."""
    try:
        if capture is None or not capture.filled:
            logger.error(
                "room_figure_provenance_error",
                stage="no_prompt_capture",
                run_id=str(run_id) if run_id is not None else None,
                agent_id=getattr(agent_id, "value", agent_id),
            )
            return None
        ledger = build_ledger(
            capture.prompt, static=capture.static, sheet=capture.sheet, debate=capture.debate
        )
        result = assess_turn(text, ledger)
        emit = logger.warning if result.breaker else logger.info
        emit(
            "room_figure_provenance",
            run_id=str(run_id) if run_id is not None else None,
            agent_id=getattr(agent_id, "value", agent_id),
            market=getattr(market, "value", market),
            ticker=ticker,
            surface=surface,
            counts=result.counts,
            record_debate_only=result.record_debate_only,
            own_figures=result.own,
            own_total=result.own_total,
            ledger_size=result.ledger_size,
            breaker=result.breaker,
        )
        return result
    except Exception as exc:  # noqa: BLE001 - shadow only; must never reach the Room
        try:
            logger.error(
                "room_figure_provenance_error",
                stage="assess",
                run_id=str(run_id) if run_id is not None else None,
                agent_id=getattr(agent_id, "value", agent_id),
                error=(str(exc) or repr(exc))[:200],
            )
        except Exception:  # noqa: BLE001 - a broken logger is not the Room's problem either
            pass
        return None
