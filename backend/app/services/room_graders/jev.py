"""CR267 WP-22: the Jev (TypeSafe System One) grader.

Answers the six q1 questions about a finished Room in one typed call, the shape
`docs/tools/room_investigation_V2/tools/jev_v1_pilot.py` established. Why a class
of its own: the model version is part of the policy key (WP-23), so it is pinned
at construction and "latest" is refused, and the response's own model id is
recorded so a silent vendor change is visible. The API key is read from the
environment at call time and never logged or placed in a result.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable

from app.core.logging import logger
from app.services.room_grader_contract import (
    Answer,
    GraderResult,
    QuestionAnswer,
    QuestionId,
    RoomTranscript,
    QUESTION_SET_VERSION,
)
from app.services.room_graders.questions import load_question_set, render_transcript

JEV_URL = "https://api.typesafe.ai/v1/systemone"
JEV_KEY_ENV = "JEV_API_KEY"

Transport = Callable[[str, dict[str, str], bytes, float], dict[str, Any]]


def _urllib_transport(
    url: str, headers: dict[str, str], body: bytes, timeout: float
) -> dict[str, Any]:
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


class JevGrader:
    name = "jev"

    def __init__(
        self,
        version: str,
        *,
        api_key: str | None = None,
        url: str = JEV_URL,
        close_band: float = 0.2,
        phrasing: int | None = None,
        timeout_s: float = 60.0,
        retries: int = 3,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not version or not version.strip() or version.strip().lower().endswith("latest"):
            raise ValueError(
                "JevGrader needs a pinned model version (e.g. 'jev-1.13.0'), never 'latest'"
            )
        self.version = version.strip()
        self._api_key = api_key
        self._url = url
        self._close_band = close_band
        self._phrasing = phrasing
        self._timeout_s = timeout_s
        self._retries = max(1, retries)
        self._transport = transport or _urllib_transport
        self._sleep = sleep

    def _key(self) -> str | None:
        return self._api_key or os.environ.get(JEV_KEY_ENV) or None

    def _questions_payload(self) -> dict[str, Any]:
        qs = load_question_set()
        return {
            q.id.value: {
                "type": "choice",
                "instructions": (
                    "A finished multi-desk investment debate about one ticker is "
                    "shown in `input`. Answer this question about it, using only "
                    f"what the debate says: {q.text_for(self._phrasing)}"
                ),
                "criteria": {"yes": q.yes, "no": q.no},
            }
            for q in qs.questions
        }

    def _state(self, transcript: RoomTranscript) -> dict[str, Any]:
        return {
            "input": {
                "task_context": render_transcript(transcript),
                "data_and_transcript": [
                    {"role": t.get("agent_id", "unknown"), "content": t.get("content", "")}
                    for t in transcript.turns
                ],
            },
            "output": json.dumps(transcript.proposed_trade, sort_keys=True)
            if transcript.proposed_trade
            else "",
        }

    def _post(self, key: str, body: bytes) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        delay = 2.0
        for attempt in range(self._retries):
            try:
                return self._transport(self._url, headers, body, self._timeout_s)
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 529) and attempt < self._retries - 1:
                    self._sleep(delay)
                    delay *= 2
                    continue
                raise
        raise RuntimeError("unreachable")

    def _failed(self, started: float, message: str) -> GraderResult:
        return GraderResult(
            grader=self.name,
            grader_version=self.version,
            question_set_version=QUESTION_SET_VERSION,
            answers=(),
            latency_ms=int((time.perf_counter() - started) * 1000),
            error=message,
        )

    def grade(self, transcript: RoomTranscript) -> GraderResult:
        started = time.perf_counter()
        try:
            key = self._key()
            if not key:
                return self._failed(started, f"{JEV_KEY_ENV} is not set")
            body = json.dumps(
                {
                    "state": self._state(transcript),
                    "model": self.version,
                    "questions": self._questions_payload(),
                }
            ).encode()
            result = self._post(key, body)
            latency_ms = int((time.perf_counter() - started) * 1000)
            raw_answers = result.get("answers")
            if not isinstance(raw_answers, dict):
                return self._failed(started, "Jev response carried no answers object")
            answers = tuple(self._parse(q, raw_answers.get(q.value)) for q in QuestionId)
            response_model = result.get("model")
            if response_model != self.version:
                logger.warning(
                    "room_grader_jev_model_mismatch",
                    pinned=self.version,
                    reported=response_model,
                )
            return GraderResult(
                grader=self.name,
                grader_version=self.version,
                question_set_version=QUESTION_SET_VERSION,
                answers=answers,
                latency_ms=latency_ms,
                extra={
                    "response_model": response_model,
                    "model_matches_pin": response_model == self.version,
                    "usage": result.get("usage"),
                },
            )
        except Exception as exc:  # noqa: BLE001 — a grader never raises out
            return self._failed(started, f"{type(exc).__name__}: {str(exc)[:300]}")

    def _parse(self, qid: QuestionId, raw: Any) -> QuestionAnswer:
        if not isinstance(raw, dict):
            return QuestionAnswer(qid, Answer.NOT_COMPUTABLE, rationale="Jev returned no answer")
        choice = str(raw.get("choice", "")).strip().lower()
        if choice not in ("yes", "no"):
            return QuestionAnswer(
                qid, Answer.NOT_COMPUTABLE, rationale=f"unrecognised choice {choice!r}"
            )
        probs = raw.get("probabilities") or {}
        p_yes = _prob(probs.get("yes"))
        p_no = _prob(probs.get("no"))
        if p_yes is None and p_no is not None:
            p_yes = 1.0 - p_no
        if p_yes is not None:
            confidence = p_yes if choice == "yes" else 1.0 - p_yes
            close = abs(p_yes - 0.5) <= self._close_band
        else:
            confidence = _prob(raw.get("confidence"))
            close = False
        return QuestionAnswer(
            question=qid,
            answer=Answer.YES if choice == "yes" else Answer.NO,
            confidence=confidence,
            close=close,
        )


def _prob(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if 0.0 <= float(value) <= 1.0 else None
