"""Phase 2 — agent unlock celebration, 1-on-1 chat, Brief Your Agent
propose/diff/accept, brief history/rollback. Needs seeded agent-progression
state (celebration.dart) and longer LLM-stream waits than Phase 1 budgeted
for. Not implemented yet — tracked in CR080's Phase 2 backlog, not silently
dropped."""

import pytest

pytestmark = [pytest.mark.phase2, pytest.mark.skip(reason="Phase 2 — see CR080 coverage backlog, not yet implemented")]


def test_agent_unlock_brief_and_history_not_yet_implemented():
    """Placeholder so this Phase-2 gap is visible in report.html as SKIPPED,
    not silently absent from the run."""

