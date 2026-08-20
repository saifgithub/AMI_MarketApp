"""DEF350 — every agent id referenced by content must be a real AgentId.

The ai_coach corpus carried `technical_analyst` and `sentiment_analyst` in
`related_agents` for months — ids no AgentId ever had. Nothing noticed because
every consumer prettified ids with a tolerant `.title()`; the moment CR160's
display-name registry resolved them strictly, prompt-building crashed at
runtime. The data is fixed; this guard makes the class impossible to reintroduce:
an id that fails AgentId() is caught here, at test time, not in a live request.
"""
import glob
import json
from pathlib import Path

from app.schemas.agents import AgentId

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_VALID = {a.value for a in AgentId}


def _related_agent_ids():
    for f in glob.glob(str(_ROOT / "content" / "ai_coach" / "**" / "*.json"), recursive=True):
        doc = json.loads(Path(f).read_text())
        items = doc if isinstance(doc, list) else doc.get("items") or doc.get("entries") or []
        if not isinstance(items, list):
            continue
        for item in items:
            for agent_id in item.get("related_agents") or []:
                yield f, agent_id


def test_every_content_agent_id_is_a_real_agent_id():
    bad = sorted({(Path(f).relative_to(_ROOT).as_posix(), a)
                  for f, a in _related_agent_ids() if a not in _VALID})
    assert not bad, (
        f"content references agent id(s) no AgentId defines: {bad} — "
        "fix the content; do not loosen agent_display_name()."
    )


def test_the_guard_sees_the_corpus():
    assert sum(1 for _ in _related_agent_ids()) > 50, (
        "guard walked almost nothing — the ai_coach layout moved and this test "
        "needs re-pointing, not deleting"
    )
