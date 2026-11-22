"""CR159 — the backend's AGENT_DESKS and the Flutter `Agent.desk` field agree.

The Your Firm bands are derived from `desk`, never list position (T-SLICE).
Two registries of one fact must not drift (T-TWICE): every AgentId has a desk,
and the Dart registry seats each agent on the same desk.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.schemas.agents import AGENT_DESKS, AgentId

REPO = Path(__file__).resolve().parents[3]
DART = REPO / "mobile" / "lib" / "models" / "agent.dart"

_ENUM = re.compile(r"enum AgentDesk \{([^}]*)\}")


def test_every_wire_agent_has_a_desk_except_the_internal_risk_officer():
    assert set(AGENT_DESKS) == set(AgentId) - {AgentId.RISK_OFFICER}


def test_desk_names_match_the_dart_enum():
    dart = DART.read_text(encoding="utf-8")
    declared = {n.strip() for n in _ENUM.search(dart).group(1).split(",")
                if n.strip()}
    assert set(AGENT_DESKS.values()) == declared


def test_desks_lockstep_backend_vs_flutter_registry():
    dart = DART.read_text(encoding="utf-8")
    pairs = re.findall(
        r"id:\s*'([a-z_]+)',.*?desk:\s*AgentDesk\.(\w+),", dart, re.S)
    assert len(pairs) == 13, f"expected 13 registry entries, got {len(pairs)}"
    for agent_id, desk in pairs:
        assert AGENT_DESKS[AgentId(agent_id)] == desk, (agent_id, desk)
