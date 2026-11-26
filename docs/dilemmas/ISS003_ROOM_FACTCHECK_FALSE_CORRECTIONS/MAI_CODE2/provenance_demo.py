"""Demonstrate fail-closed rendering for provenance-linked Room numbers."""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


class PublishRejected(ValueError):
    """The proposed Room output contract cannot publish this turn."""


@dataclass(frozen=True)
class NumericAtom:
    """One server-owned number or number-bearing phrase."""

    atom_id: str
    label: str
    rendered_value: str
    source: str
    resolves_to: str | None = None

    def render(self) -> str:
        return f"{self.label}: {self.rendered_value}"


@dataclass(frozen=True)
class TextPart:
    """Model prose which is not permitted to contain a numeric expression."""

    text: str


@dataclass(frozen=True)
class AtomPart:
    """A model-selected reference; the model never supplies the number."""

    atom_id: str


@dataclass(frozen=True)
class ProvenanceSpan:
    """Rendered position of one atom in the published text."""

    atom_id: str
    start: int
    end: int
    source: str


@dataclass(frozen=True)
class RenderedTurn:
    """Published text plus the spans owned by the server renderer."""

    text: str
    spans: tuple[ProvenanceSpan, ...]


_ENGLISH_NUMBER_WORD_RE = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|"
    r"twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
    r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|"
    r"thousand|million|billion|trillion|first|second|third|fourth|fifth|"
    r"sixth|seventh|eighth|ninth|tenth|half|quarter|dozen|twice|double|"
    r"triple)\b",
    re.IGNORECASE,
)


def example_registry() -> dict[str, NumericAtom]:
    """Return the four provenance classes needed by the ISS003 examples."""
    base = {
        "sheet.fcf_ttm": NumericAtom(
            "sheet.fcf_ttm",
            "TTM FCF",
            "-RM15,433M",
            "profile.free_cash_flow",
        ),
        "sheet.fcf_yield": NumericAtom(
            "sheet.fcf_yield",
            "FCF yield",
            "-12.6%",
            "profile.fcf_yield",
        ),
        "sheet.fcf_history_mean_4y": NumericAtom(
            "sheet.fcf_history_mean_4y",
            "4-year average FCF",
            "RM5,273M",
            "computed:mean(profile.fcf_history)",
        ),
        "mandate.single_name_cap": NumericAtom(
            "mandate.single_name_cap",
            "single-name cap",
            "1.0%",
            "mandate.single_name_cap_pct",
        ),
        "derived.atr_stop": NumericAtom(
            "derived.atr_stop",
            "ATR stop distance",
            "1.0x ATR(14), RM0.145",
            "computed:stop.atr_multiple*profile.atr14",
        ),
    }
    base["debate.bear.cap_quote"] = NumericAtom(
        "debate.bear.cap_quote",
        "quoted single-name cap",
        base["mandate.single_name_cap"].rendered_value,
        "message:bear.turn:mandate.single_name_cap",
        resolves_to="mandate.single_name_cap",
    )
    return base


def _raw_numeric_reason(text: str) -> str | None:
    if any(unicodedata.category(char) in {"Nd", "Nl", "No"} for char in text):
        return "Unicode numeric character in prose"
    if _ENGLISH_NUMBER_WORD_RE.search(text):
        return "English numeric word in prose"
    if any(symbol in text for symbol in ("%", "‰", "‱")):
        return "numeric unit in prose"
    return None


def _resolve(atom_id: str, registry: dict[str, NumericAtom]) -> NumericAtom:
    seen: set[str] = set()
    current_id = atom_id
    while True:
        if current_id in seen:
            raise PublishRejected(f"cyclic atom alias: {atom_id}")
        seen.add(current_id)
        atom = registry.get(current_id)
        if atom is None:
            raise PublishRejected(f"atom is not available: {atom_id}")
        if atom.resolves_to is None:
            return atom
        current_id = atom.resolves_to


def publish(
    parts: list[TextPart | AtomPart],
    registry: dict[str, NumericAtom],
) -> RenderedTurn:
    """Resolve a turn or reject it before any text is sent to a user."""
    output: list[str] = []
    spans: list[ProvenanceSpan] = []
    offset = 0
    for part in parts:
        if isinstance(part, TextPart):
            reason = _raw_numeric_reason(part.text)
            if reason is not None:
                raise PublishRejected(reason)
            rendered = part.text
        elif isinstance(part, AtomPart):
            atom = _resolve(part.atom_id, registry)
            rendered = atom.render()
            spans.append(
                ProvenanceSpan(
                    atom_id=part.atom_id,
                    start=offset,
                    end=offset + len(rendered),
                    source=atom.source,
                )
            )
        else:
            raise PublishRejected(f"unsupported part: {type(part).__name__}")
        output.append(rendered)
        offset += len(rendered)
    return RenderedTurn("".join(output), tuple(spans))

