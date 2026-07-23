"""Phase 2 — full cold-start onboarding: Concierge chat stream, interview
chips + free text, mandate readback, hand-off to Floor. Needs `pm clear` (a
destructive reset of the on-device app state) plus long LLM-stream waits, so
it's kept separate from the Phase 1 noReset-based tab sweep. Not implemented
yet — tracked in CR080's Phase 2 backlog, not silently dropped."""

import pytest

pytestmark = [pytest.mark.phase2, pytest.mark.skip(reason="Phase 2 — see CR080 coverage backlog, not yet implemented")]


def test_cold_start_onboarding_not_yet_implemented():
    """Placeholder so this Phase-2 gap is visible in report.html as SKIPPED,
    not silently absent from the run."""

