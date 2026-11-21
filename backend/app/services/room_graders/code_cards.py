"""CR267 WP-22: the plain-code grader over CR266 typed claim cards.

No model call: it reads the four evidence desks' cards (and the fact sheet's
`field_state`) through `evidence_record.build_evidence_record` and answers only
what those cells can carry. A missing cell makes a question `NOT_COMPUTABLE`
for that room and is never imputed, so the bake-off can report completeness as
its own column. `trade_proposed` reads `proposed_trade` alone, so this grader
can own that question even in rooms that ran with cards off.

`transcript.cards` shape this grader expects:
`{"cards_by_desk": {desk: {"cards": [{item, direction, grade, data, claim,
nums}], "objections": [{target, severity, objection}]}}, "field_state": {...}}`.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any

from app.services.evidence_record import (
    ADEQUATE_SEVERITIES,
    REQUIRED_DESKS,
    EvidenceRecord,
    build_evidence_record,
)
from app.services.room_grader_contract import (
    QUESTION_SET_VERSION,
    Answer,
    GraderResult,
    QuestionAnswer,
    QuestionId,
    RoomTranscript,
)

NO_TRADE_ACTIONS = frozenset(
    {"", "hold", "pass", "none", "no_trade", "no trade", "wait", "skip"}
)
_SEVERITY_RANK = {"high": 2, "medium": 1}
_GRADE_BINDS = frozenset({"well", "partial"})


def _nc(q: QuestionId, why: str) -> QuestionAnswer:
    return QuestionAnswer(q, Answer.NOT_COMPUTABLE, rationale=why)


def _desk_channels(cards: dict) -> dict[str, SimpleNamespace]:
    by_desk = cards.get("cards_by_desk")
    if not isinstance(by_desk, dict):
        raise ValueError("cards must carry a cards_by_desk object")
    out: dict[str, SimpleNamespace] = {}
    for desk, channel in by_desk.items():
        if not isinstance(channel, dict):
            raise ValueError(f"cards_by_desk[{desk!r}] must be an object")
        out[str(desk)] = SimpleNamespace(
            cards=tuple(SimpleNamespace(**c) for c in channel.get("cards") or ()),
            objections=tuple(SimpleNamespace(**o) for o in channel.get("objections") or ()),
        )
    return out


class CodeCardsGrader:
    name = "code_cards"
    version = "cards-1"

    def __init__(self, *, material_cutoff: float = 0.2, close_band: float = 0.05) -> None:
        self._cutoff = material_cutoff
        self._close_band = close_band

    def grade(self, transcript: RoomTranscript) -> GraderResult:
        started = time.perf_counter()
        try:
            answers = self._answers(transcript)
        except Exception as exc:  # noqa: BLE001 — a grader never raises out
            return GraderResult(
                grader=self.name,
                grader_version=self.version,
                question_set_version=QUESTION_SET_VERSION,
                answers=(),
                latency_ms=int((time.perf_counter() - started) * 1000),
                error=f"{type(exc).__name__}: {str(exc)[:300]}",
            )
        return GraderResult(
            grader=self.name,
            grader_version=self.version,
            question_set_version=QUESTION_SET_VERSION,
            answers=answers,
            latency_ms=int((time.perf_counter() - started) * 1000),
            cost_usd=0.0,
            extra={
                "computable": sum(a.answer is not Answer.NOT_COMPUTABLE for a in answers),
                "questions": len(answers),
            },
        )

    def _answers(self, transcript: RoomTranscript) -> tuple[QuestionAnswer, ...]:
        channels: dict[str, SimpleNamespace] | None = None
        record: EvidenceRecord | None = None
        field_state: dict | None = None
        if transcript.cards is not None:
            channels = _desk_channels(transcript.cards)
            field_state = transcript.cards.get("field_state") or None
            record = build_evidence_record(channels, field_state)
        out = []
        for q in QuestionId:
            if q is QuestionId.TRADE_PROPOSED:
                out.append(self._trade_proposed(transcript.proposed_trade))
            elif q is QuestionId.THESIS_MATERIAL_DIRECTIONAL:
                out.append(self._thesis(record))
            elif q is QuestionId.TERMINAL_VULNERABILITY:
                out.append(self._terminal(record))
            elif q is QuestionId.BEAR_OBJECTION_ANSWERED:
                out.append(self._bear(channels, record))
            else:
                out.append(_nc(q, "no card item carries this question"))
        return tuple(out)

    def _trade_proposed(self, trade: dict | None) -> QuestionAnswer:
        q = QuestionId.TRADE_PROPOSED
        if not trade:
            return QuestionAnswer(q, Answer.NO, rationale="no proposed trade")
        action = trade.get("action", trade.get("side"))
        if action is None:
            return _nc(q, "proposed_trade carries no action or side")
        proposed = str(action).strip().lower() not in NO_TRADE_ACTIONS
        return QuestionAnswer(
            q, Answer.YES if proposed else Answer.NO, rationale=f"action={action}"
        )

    def _thesis(self, record: EvidenceRecord | None) -> QuestionAnswer:
        q = QuestionId.THESIS_MATERIAL_DIRECTIONAL
        if record is None:
            return _nc(q, "room ran without cards")
        if not record.evidence_available:
            return _nc(q, "evidence incomplete: " + ", ".join(record.missing[:6]))
        weight = abs(record.net_support)
        return QuestionAnswer(
            question=q,
            answer=Answer.YES if weight >= self._cutoff else Answer.NO,
            close=abs(weight - self._cutoff) <= self._close_band,
            rationale=f"net_support={record.net_support}",
        )

    def _terminal(self, record: EvidenceRecord | None) -> QuestionAnswer:
        q = QuestionId.TERMINAL_VULNERABILITY
        if record is None:
            return _nc(q, "room ran without cards")
        if "registry:field_state" in record.missing:
            return _nc(q, "fact-sheet field_state registry missing")
        filed = {i.desk for i in record.items if i.item == "bs"}
        absent = [d for d in REQUIRED_DESKS if d not in filed]
        if absent:
            return _nc(q, "balance-sheet card missing from: " + ", ".join(absent))
        open_high = [
            o
            for o in record.unresolved_objections
            if o.target == "bs" and o.severity == "high"
        ]
        return QuestionAnswer(
            q,
            Answer.YES if open_high else Answer.NO,
            rationale=open_high[0].objection if open_high else "",
        )

    def _bear(
        self,
        channels: dict[str, SimpleNamespace] | None,
        record: EvidenceRecord | None,
    ) -> QuestionAnswer:
        q = QuestionId.BEAR_OBJECTION_ANSWERED
        if channels is None or record is None:
            return _nc(q, "room ran without cards")
        if not record.evidence_available:
            return _nc(q, "evidence incomplete: " + ", ".join(record.missing[:6]))
        bear = channels.get("bear_researcher")
        if bear is None or not bear.cards:
            return _nc(q, "bear desk filed no cards")
        adequate = [
            o
            for o in bear.objections
            if str(getattr(o, "severity", "")).lower() in ADEQUATE_SEVERITIES
            and str(getattr(o, "target", "")).lower() in record.data_present
        ]
        if not adequate:
            return _nc(q, "no adequate bear objection filed (the channel is optional)")
        strongest = max(
            adequate,
            key=lambda o: _SEVERITY_RANK.get(str(o.severity).lower(), 0),
        )
        target = str(strongest.target).lower()
        own_dir = next(
            (
                str(c.direction).lower()
                for c in bear.cards
                if str(c.item).lower() == target
            ),
            None,
        )
        for desk, channel in channels.items():
            if desk == "bear_researcher" or not record.data_present.get(target):
                continue
            for card in channel.cards:
                if (
                    str(card.item).lower() == target
                    and str(card.grade).lower() in _GRADE_BINDS
                    and (own_dir is None or str(card.direction).lower() != own_dir)
                    and str(getattr(card, "nums", "") or "").strip()
                ):
                    return QuestionAnswer(
                        q,
                        Answer.YES,
                        rationale=f"{desk} answers {target} with {card.nums}",
                    )
        return QuestionAnswer(
            q, Answer.NO, rationale=f"no desk answers the {target} objection with numbers"
        )
