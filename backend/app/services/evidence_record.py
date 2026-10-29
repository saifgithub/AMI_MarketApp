"""CR266 — typed Room evidence record and the PM evidence gate.

The four evidence desks file CLAIMS/OBJECTIONS cards in-turn (CR256). This
module converts those parsed cards into one deterministic, typed record:
per-item data presence read off the fact-sheet's own `field_state` registry
(never the LLM's self-reported `data=` flag), net support from
direction x grade, and unresolved objections at adequate severity. The record
feeds the PM gate: a per-provider, per-risk-level calibrated threshold picks
the allowed action set and a continuous size from 25% of the mandate cap at
the threshold to 100% at score 1.0.

Pure functions only — no I/O, no settings, no runner imports — so both
`room_runner` and `core.config` can depend on it without a cycle, and the
whole gate is unit-testable in isolation.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

# The five-item CFA registry — the same ids `room_prompts._CLAIMS_REGISTRY`
# hands the desks and `room_runner._CARD_ITEM_IDS` parses against.
ITEM_IDS: tuple[str, ...] = ("eq", "vc", "vh", "bs", "moat")

# The four evidence desks, by AgentId value — the set `room_prompts._CARD_DESKS`
# names. The gate requires every one of them to have filed a parseable card.
REQUIRED_DESKS: tuple[str, ...] = (
    "fundamentals_analyst",
    "bull_researcher",
    "bear_researcher",
    "research_manager",
)

# Card item -> fact-sheet fields whose liveness means the desk actually had
# payload to grade. `data_present` is decided ONLY by this registry against
# the run's `field_state` — the card's own `data=yes|no` self-report is a
# claim, not a measurement (CR266: compute from the registry, not LLM report).
ITEM_FIELD_REGISTRY: dict[str, tuple[str, ...]] = {
    "eq": ("free_cash_flow", "sbc", "net_cash"),
    "vc": ("roic", "wacc"),
    "vh": ("pe", "forward_pe", "ev_to_ebitda", "peg_ratio", "price_to_sales"),
    "bs": (
        "total_debt", "net_cash", "interest_coverage", "debt_maturity",
        "current_ratio", "quick_ratio", "debt_to_equity",
    ),
    "moat": ("gross_margin", "operating_margin", "rev_growth", "profit_margin"),
}

_DIRECTION_WEIGHT: dict[str, float] = {"support": 1.0, "oppose": -1.0, "neutral": 0.0}
_GRADE_WEIGHT: dict[str, float] = {"well": 1.0, "partial": 0.5, "unsupported": 0.0}

# An objection only binds at high or medium severity; a low-severity note is
# telemetry, never a score penalty.
ADEQUATE_SEVERITIES: frozenset[str] = frozenset({"high", "medium"})

# score = net_support - 0.1 per unresolved objection.
UNRESOLVED_PENALTY = 0.1

# Continuous size: 25% of the mandate cap at the threshold, 100% at score 1.0.
SIZE_FLOOR_FRACTION = 0.25

# The calibrated-threshold config's risk-level keys. Monotone descending:
# a conservative mandate (R1) must clear MORE evidence than an aggressive
# one (R5).
RISK_LEVELS: tuple[str, ...] = ("R1", "R2", "R3", "R4", "R5")


class ThresholdConfigError(ValueError):
    """`ROOM_EVIDENCE_GATE_THRESHOLDS_JSON` is malformed, incomplete, out of
    range or non-monotone — fail boot loudly (CR040), never clamp silently."""


@dataclass(frozen=True)
class EvidenceItem:
    """One desk's card on one registry item, with the registry's verdict on
    whether the fact sheet actually carried the payload."""

    item: str
    desk: str
    direction: str
    grade: str
    data_present: bool
    contribution: float  # direction x grade weight; 0.0 when data is absent


@dataclass(frozen=True)
class EvidenceObjection:
    """One desk's objection, resolved or not by OTHER desks' evidenced cards."""

    id: str
    desk: str
    target: str
    severity: str
    adequate: bool
    resolved: bool


@dataclass(frozen=True)
class EvidenceRecord:
    """The typed record the gate scores. `evidence_available` is False when a
    required desk filed nothing parseable or an item has no card at all — the
    gate fails closed on that, never scores a half-empty room."""

    items: tuple[EvidenceItem, ...]
    objections: tuple[EvidenceObjection, ...]
    data_present: dict[str, bool]
    net_support: float
    unresolved_objections: tuple[str, ...]  # ids, in filing order
    score: float
    evidence_available: bool
    missing: tuple[str, ...] = ()

    @property
    def unresolved_objection_count(self) -> int:
        return len(self.unresolved_objections)


@dataclass(frozen=True)
class EvidenceGateDecision:
    """The gate built once before the PM call. `fail_closed_reason` set means
    the convene gets a code-built PASS with that reason and no PM call at all
    — an uncalibrated provider or incomplete evidence can never silently skip
    or fabricate a decision."""

    record: EvidenceRecord
    provider: str | None
    threshold: float | None
    allowed_actions: tuple[str, ...]
    computed_size_pct: float | None
    fail_closed_reason: str | None = None
    reasons: tuple[str, ...] = ()


def _live(field_state: Mapping[str, str], names: tuple[str, ...]) -> bool:
    return any(str(field_state.get(n, "")).lower() == "live" for n in names)


def build_evidence_record(
    cards_by_desk: Mapping[str, Any],
    field_state: Mapping[str, str] | None,
) -> EvidenceRecord:
    """Convert parsed desk cards into the typed record.

    `cards_by_desk` maps desk (AgentId value) to a parsed card channel object
    (duck-typed: `.cards` / `.objections` tuples of frozen dataclasses, exactly
    what `room_runner.parse_claim_cards` returns). Missing desks or a missing
    `field_state` simply yield absent evidence — availability is reported, the
    caller decides.
    """
    state = field_state or {}
    data_present = {item: _live(state, ITEM_FIELD_REGISTRY[item]) for item in ITEM_IDS}

    items: list[EvidenceItem] = []
    objections: list[EvidenceObjection] = []
    missing: list[str] = []
    cards_per_item: dict[str, list[EvidenceItem]] = {item: [] for item in ITEM_IDS}

    for desk in REQUIRED_DESKS:
        channel = cards_by_desk.get(desk)
        cards = tuple(getattr(channel, "cards", ()) or ())
        if not cards:
            missing.append(f"cards:{desk}")
            continue
        for card in cards:
            item = str(getattr(card, "item", "")).lower()
            if item not in cards_per_item:
                continue
            direction = str(getattr(card, "direction", "")).lower()
            grade = str(getattr(card, "grade", "")).lower()
            present = data_present[item]
            contribution = (
                _DIRECTION_WEIGHT.get(direction, 0.0) * _GRADE_WEIGHT.get(grade, 0.0)
                if present
                else 0.0
            )
            # Missing data neutral/unsupported, never silently bearish: a card
            # the fact sheet cannot back contributes nothing, in EITHER
            # direction — an unsupported "oppose" is not negative evidence.
            ev = EvidenceItem(
                item=item, desk=desk, direction=direction, grade=grade,
                data_present=present, contribution=contribution,
            )
            items.append(ev)
            cards_per_item[item].append(ev)
    for item in ITEM_IDS:
        if not cards_per_item[item]:
            missing.append(f"item:{item}")

    net_support = round(sum(ev.contribution for ev in items), 6)

    # An adequate objection is resolved only by ANOTHER desk's evidenced card
    # on the same item pointing the other way — a desk's own card cannot
    # answer its own challenge, and an unevidenced card answers nothing.
    by_desk_dir = {
        (ev.desk, ev.item): ev.direction for ev in items if ev.data_present
    }
    unresolved: list[str] = []
    seen: dict[tuple[str, str], int] = {}
    for desk in REQUIRED_DESKS:
        channel = cards_by_desk.get(desk)
        for obj in tuple(getattr(channel, "objections", ()) or ()):
            target = str(getattr(obj, "target", "")).lower()
            if target not in cards_per_item:
                continue
            severity = str(getattr(obj, "severity", "")).lower()
            seen[(desk, target)] = seen.get((desk, target), 0) + 1
            oid = f"{desk}:{target}:{seen[(desk, target)] - 1}"
            adequate = severity in ADEQUATE_SEVERITIES
            own_dir = by_desk_dir.get((desk, target))
            resolved = False
            if adequate:
                for ev in cards_per_item[target]:
                    if ev.desk == desk or not ev.data_present:
                        continue
                    if _GRADE_WEIGHT.get(ev.grade, 0.0) <= 0:
                        continue
                    if own_dir is None or ev.direction != own_dir:
                        resolved = True
                        break
            if adequate and not resolved:
                unresolved.append(oid)
            objections.append(EvidenceObjection(
                id=oid, desk=desk, target=target, severity=severity,
                adequate=adequate, resolved=resolved,
            ))

    score = round(net_support - UNRESOLVED_PENALTY * len(unresolved), 6)
    return EvidenceRecord(
        items=tuple(items),
        objections=tuple(objections),
        data_present=data_present,
        net_support=net_support,
        unresolved_objections=tuple(unresolved),
        score=score,
        evidence_available=not missing,
        missing=tuple(missing),
    )


def parse_gate_thresholds(raw: str) -> dict[str, dict[str, float]]:
    """Parse and loudly validate `ROOM_EVIDENCE_GATE_THRESHOLDS_JSON`.

    Shape: {"<provider>": {"R1": t1, ..., "R5": t5}} with every level in
    [0, 1] and t1 >= t2 >= t3 >= t4 >= t5 (a conservative mandate clears more
    evidence than an aggressive one). Anything else — bad JSON, a missing or
    extra level, a non-number, an out-of-range or non-monotone run — raises
    ThresholdConfigError: a miscalibrated gate must fail at boot, not guess.
    """
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise ThresholdConfigError(f"not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ThresholdConfigError("top level must be an object keyed by provider")
    out: dict[str, dict[str, float]] = {}
    for provider, levels in parsed.items():
        if not isinstance(provider, str) or not provider.strip():
            raise ThresholdConfigError("provider names must be non-empty strings")
        if not isinstance(levels, dict):
            raise ThresholdConfigError(f"{provider!r}: levels must be an object")
        keys = set(levels)
        if keys != set(RISK_LEVELS):
            raise ThresholdConfigError(
                f"{provider!r}: need exactly {list(RISK_LEVELS)}, got {sorted(keys)}"
            )
        run: dict[str, float] = {}
        for level in RISK_LEVELS:
            value = levels[level]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ThresholdConfigError(f"{provider!r}/{level}: not a number")
            if not 0.0 <= float(value) <= 1.0:
                raise ThresholdConfigError(
                    f"{provider!r}/{level}: {value} outside [0, 1]"
                )
            run[level] = float(value)
        vals = [run[level] for level in RISK_LEVELS]
        if any(a < b for a, b in zip(vals, vals[1:], strict=False)):
            raise ThresholdConfigError(
                f"{provider!r}: thresholds must be monotone {'>='.join(RISK_LEVELS)}, "
                f"got {vals}"
            )
        out[provider.strip()] = run
    return out


def threshold_for_risk(
    thresholds: Mapping[str, Mapping[str, float]],
    provider: str | None,
    risk_score: int,
) -> float | None:
    """The calibrated threshold for this provider and mandate risk level.
    None means uncalibrated — the gate fails closed, never free-passes."""
    if not provider:
        return None
    levels = thresholds.get(provider)
    if not levels:
        return None
    level = f"R{max(1, min(5, int(risk_score)))}"
    value = levels.get(level)
    return float(value) if value is not None else None


def allowed_actions(score: float, threshold: float) -> tuple[str, ...]:
    """PASS only below the threshold; APPROVE+PASS at or above it."""
    if score < threshold:
        return ("PASS",)
    return ("APPROVE", "PASS")


def computed_size_pct(score: float, threshold: float, cap_pct: float) -> float | None:
    """Continuous, monotone: 25% of the mandate cap at the threshold, 100% at
    score 1.0, linear in between, capped. None below the threshold — a PASS
    carries no size, and inventing one would be fabrication."""
    if score < threshold:
        return None
    span = 1.0 - threshold
    frac = 1.0 if span <= 0 else (score - threshold) / span
    frac = min(1.0, max(0.0, frac))
    return round(cap_pct * (SIZE_FLOOR_FRACTION + (1.0 - SIZE_FLOOR_FRACTION) * frac), 4)


def gate_contested(
    *,
    split_vote: bool,
    score: float,
    threshold: float,
    margin: float,
    bar_blocked: bool,
    scripted_turns: int,
) -> bool:
    """A gated decision is contested when the team split, the score sits within
    `margin` of the threshold, the bar or floor blocked an approval the reads
    wanted, or any desk ran scripted (the evidence is thinner than it looks)."""
    return (
        split_vote
        or abs(score - threshold) < margin
        or bar_blocked
        or scripted_turns > 0
    )


def build_gate_decision(
    *,
    cards_by_desk: Mapping[str, Any],
    field_state: Mapping[str, str] | None,
    thresholds: Mapping[str, Mapping[str, float]],
    provider: str | None,
    risk_score: int,
    cap_pct: float,
) -> EvidenceGateDecision:
    """Build the gate once, before the PM call. Fails closed — with the reason
    named — when the provider is uncalibrated or the evidence is incomplete."""
    record = build_evidence_record(cards_by_desk, field_state)
    reasons: list[str] = []

    if not record.evidence_available:
        reason = (
            "typed evidence incomplete: missing "
            + ", ".join(record.missing)
        )
        return EvidenceGateDecision(
            record=record, provider=provider, threshold=None,
            allowed_actions=("PASS",), computed_size_pct=None,
            fail_closed_reason=reason, reasons=(reason,),
        )

    threshold = threshold_for_risk(thresholds, provider, risk_score)
    if threshold is None:
        reason = f"no calibrated evidence thresholds for provider '{provider}'"
        return EvidenceGateDecision(
            record=record, provider=provider, threshold=None,
            allowed_actions=("PASS",), computed_size_pct=None,
            fail_closed_reason=reason, reasons=(reason,),
        )

    actions = allowed_actions(record.score, threshold)
    size = computed_size_pct(record.score, threshold, cap_pct)
    reasons.append(f"evidence score {record.score:.2f} vs threshold {threshold:.2f}")
    if record.unresolved_objection_count:
        reasons.append(
            f"{record.unresolved_objection_count} unresolved objection(s): "
            + ", ".join(record.unresolved_objections)
        )
    if "APPROVE" in actions and size is not None:
        reasons.append(f"computed size {size:.2f}% of the {cap_pct:.2f}% cap")
    return EvidenceGateDecision(
        record=record, provider=provider, threshold=threshold,
        allowed_actions=actions, computed_size_pct=size, reasons=tuple(reasons),
    )
