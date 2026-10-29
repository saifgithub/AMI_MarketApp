#!/usr/bin/env python3
"""CR266 — V2 records the persisted verdict, not the pre-stamp stream event."""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from library.runner import Arm, _convene_arm


class _Verdict:
    def __init__(self, payload):
        self.payload = payload

    def model_dump(self):
        return self.payload


class _Event:
    kind = "verdict"

    def __init__(self, verdict):
        self.verdict = verdict


class _StoredRun:
    def __init__(self, verdict):
        self.verdict = verdict


class _Runner:
    def __init__(self, streamed, stored):
        self.streamed = streamed
        self.stored = stored
        self.run_id = None

    async def run(self, *, run_id, user_id, ticker, mandate, agent_timeout_s):
        self.run_id = run_id
        yield _Event(_Verdict(self.streamed))

    def get_run(self, run_id):
        if run_id != self.run_id:
            raise AssertionError("stored lookup used a different run id")
        return _StoredRun(_Verdict(self.stored))


class PersistedVerdictTests(unittest.TestCase):
    def test_completed_stored_verdict_supersedes_stream_event(self) -> None:
        runner = _Runner(
            {"action": "APPROVE", "sheet_state": None},
            {"action": "APPROVE", "sheet_state": {"pe": "live"}},
        )
        _, verdict, _, _ = asyncio.run(_convene_arm(
            Arm(key="AAPL-r4-rep1", ticker="AAPL", mandate={}),
            runner=runner, mandate=object(), user_id=uuid4(),
            agent_timeout_s=1.0,
        ))
        self.assertEqual(verdict["sheet_state"], {"pe": "live"})

    def test_runner_without_persistence_lookup_keeps_stream_fallback(self) -> None:
        class StreamOnlyRunner:
            async def run(self, **kwargs):
                yield _Event(_Verdict({"action": "PASS", "sheet_state": None}))

        _, verdict, _, _ = asyncio.run(_convene_arm(
            Arm(key="AAPL-r4-rep1", ticker="AAPL", mandate={}),
            runner=StreamOnlyRunner(), mandate=object(), user_id=uuid4(),
            agent_timeout_s=1.0,
        ))
        self.assertEqual(verdict["action"], "PASS")


if __name__ == "__main__":
    unittest.main()
