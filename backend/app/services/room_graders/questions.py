"""CR267 WP-22: loader for the versioned question set and the shared rendering of
a finished Room for the model-backed graders.

One file (`room_questions_q1.json`) owns the six question texts, their yes/no
semantics and the five alternative phrasings the wording test swaps in. Graders
read it here so the text a person checks and the text a grader is asked can never
drift apart.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.services.room_grader_contract import (
    QUESTION_SET_VERSION,
    QuestionId,
    RoomTranscript,
)

QUESTIONS_PATH = Path(__file__).resolve().parent.parent / "room_questions_q1.json"


@dataclass(frozen=True)
class Question:
    id: QuestionId
    text: str
    yes: str
    no: str
    read_from: tuple[str, ...]
    phrasings: tuple[str, ...]

    def text_for(self, phrasing: int | None) -> str:
        return self.text if phrasing is None else self.phrasings[phrasing]


@dataclass(frozen=True)
class QuestionSet:
    version: str
    questions: tuple[Question, ...]

    def get(self, qid: QuestionId) -> Question:
        for q in self.questions:
            if q.id == qid:
                return q
        raise KeyError(qid)


@lru_cache(maxsize=1)
def load_question_set() -> QuestionSet:
    raw = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    questions = tuple(
        Question(
            id=QuestionId(q["id"]),
            text=q["text"],
            yes=q["answer_semantics"]["yes"],
            no=q["answer_semantics"]["no"],
            read_from=tuple(q["read_from"]),
            phrasings=tuple(q["phrasings"]),
        )
        for q in raw["questions"]
    )
    version = raw["version"]
    if version != QUESTION_SET_VERSION:
        raise ValueError(
            f"question file version {version!r} != contract {QUESTION_SET_VERSION!r}"
        )
    if {q.id for q in questions} != set(QuestionId):
        raise ValueError("question file must carry exactly the contract's QuestionId set")
    return QuestionSet(version=version, questions=questions)


def render_transcript(transcript: RoomTranscript) -> str:
    header = (
        f"Ticker: {transcript.ticker}\n"
        f"Mandate risk score: {transcript.risk_score}\n"
        f"Mandate horizon: {transcript.horizon or 'not stated'}\n"
    )
    turns = "\n\n".join(
        f"[{t.get('agent_id', 'unknown')}]\n{t.get('content', '')}"
        for t in transcript.turns
    )
    trade = (
        f"\n\nProposed trade: {json.dumps(transcript.proposed_trade, sort_keys=True)}"
        if transcript.proposed_trade
        else "\n\nProposed trade: none"
    )
    return f"{header}\n{turns}{trade}"
