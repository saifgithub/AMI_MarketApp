"""Phase 2 — full 12-agent "Convene the Room" run-to-verdict, kill-mid-run/
reconnect, trade submission from a verdict. Needs a full Room run's worth of
LLM-stream wait time, well beyond Phase 1's scope. Not implemented yet —
tracked in CR080's Phase 2 backlog, not silently dropped."""

import pytest

pytestmark = [pytest.mark.phase2, pytest.mark.skip(reason="Phase 2 — see CR080 coverage backlog, not yet implemented")]


def test_convene_room_to_verdict_not_yet_implemented():
    """Placeholder so this Phase-2 gap is visible in report.html as SKIPPED,
    not silently absent from the run."""

