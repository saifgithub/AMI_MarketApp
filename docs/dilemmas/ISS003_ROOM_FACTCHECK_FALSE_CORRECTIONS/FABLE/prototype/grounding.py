"""ISS003 / FABLE prototype — figure provenance by value, not correction by label.

Stdlib only. Not wired into the app; it exists so every claim in SOLUTION.md can
be re-run (see replay.py and test_brief_cases.py next to this file).

The question this module answers for each figure in a desk's prose is
"is this number one the desk was shown?", never "which field did the desk mean,
and is it wrong?". The first needs no inference about meaning; the second is the
inference that failed in DEF547 rounds 1-3.

Three outcomes per figure:
  RECORD  - equals a figure in the ledger (text the code itself wrote: the rendered
            fact sheet, the mandate block, coded sizing lines, coded notes).
  DERIVED - not in the ledger, but equals a one-step calculation from two figures
            in the same sentence (ratio, premium, difference, percentage of).
  OWN     - neither. The desk's own calculation, estimate, level, or invention.

Sign is deliberately not part of the comparison (see SOLUTION.md section 6 for
what that costs).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

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
    """Every numeral in `text`. Used on BOTH sides (ledger text and desk prose), so
    a quirk in this function affects both sides the same way."""
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
        elif not (cur or mag or unit) and _NAME_BEFORE.search(before):
            kind = "name"
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
    """`v` equals the claim at the claim's own precision in the claim's own unit,
    by rounding OR truncation (desks truncate: 59,957M is written "$59.9B")."""
    unit = 10.0 ** -min(claim.dec, 6)
    delta = abs(v) / claim.mult - claim.value / claim.mult
    return -0.5 * unit - 1e-9 <= delta < unit - 1e-9


@dataclass(frozen=True)
class Entry:
    value: float
    cls: str
    source: str   # "sheet" | "mandate" | "coded" | "decision" | "debate"
    label: str    # the text just before the figure where the code wrote it


@dataclass
class Ledger:
    entries: list[Entry] = field(default_factory=list)

    def add_text(self, source: str, text: str) -> None:
        for f in extract(text):
            label = re.sub(r"\s+", " ", text[max(0, f.start - 48):f.start]).strip()
            self.entries.append(Entry(f.value, f.cls, source, label))

    def add_value(self, source: str, value: float, label: str = "", cls: str = "any") -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return
        self.entries.append(Entry(abs(float(value)), cls, source, label))

    def find(self, claim: Fig, sources: tuple[str, ...] | None = None) -> list[Entry]:
        return [
            en for en in self.entries
            if (sources is None or en.source in sources)
            and _compatible(claim.cls, en.cls)
            and _same(claim, en.value)
        ]


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
    """One-step calculations only, exact at the claim's precision. Deliberately
    small: each extra operation raises the chance a made-up figure matches."""
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
    status: str             # "record" | "derived" | "decision" | "own" | "not_a_figure"
    sources: tuple[str, ...] = ()
    labels: tuple[str, ...] = ()
    how: str | None = None


def classify(text: str, ledger: Ledger) -> list[Provenance]:
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
            out.append(Provenance(
                f, "record",
                tuple(sorted({h.source for h in hits})),
                tuple(dict.fromkeys(h.label for h in hits))[:3],
            ))
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
    return out


def own_figures(text: str, ledger: Ledger) -> list[str]:
    seen: dict[str, None] = {}
    for p in classify(text, ledger):
        if p.status == "own":
            seen.setdefault(p.fig.raw, None)
    return list(seen)


NOTE_MAX_FIGURES = 6


def provenance_note(text: str, ledger: Ledger) -> str | None:
    """The only user-visible sentence this design emits. It never says a figure is
    wrong and never names what the sheet 'really' says. Returns None when there is
    nothing to say, and None (with the caller logging loudly) when the turn looks
    like a broken normaliser rather than a desk doing arithmetic."""
    own = own_figures(text, ledger)
    if not own or len(own) > NOTE_MAX_FIGURES:
        return None
    listed = ", ".join(own)
    return (
        f"[AMI: not on the fact sheet — {listed}. "
        "These are this desk's own calculation or estimate, not figures of record.]"
    )
