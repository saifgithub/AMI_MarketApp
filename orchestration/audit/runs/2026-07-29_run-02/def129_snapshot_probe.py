"""DEF129 probe — load a REAL pre-change Mandate snapshot under the post-change schema.

Builds a Mandate with the schema from d6932f15~1 (daily_briefing populated),
serializes it exactly as mandate_store would have persisted it, then validates
that JSON under the post-change schema from the worktree. Run from
.claude/worktrees/audit-REL58/backend/ with the backend venv python.
Requires /tmp/rel58_old_mandate.py = `git show d6932f15~1:backend/app/schemas/mandate.py`.
"""
import importlib.util, json, sys, uuid
from datetime import datetime, timezone

spec = importlib.util.spec_from_file_location("old_mandate", "/tmp/rel58_old_mandate.py")
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)

now = datetime.now(timezone.utc)
m = old.Mandate(
    user_id=uuid.uuid4(),
    display_name="Pre DEF129 Snapshot",
    primary_goal="long_term_wealth",
    horizon="long",
    path="active",
    risk_score=3,
    risk_components=old.RiskComponents(drawdown_response=3, regret_asymmetry=0, concentration_tolerance=3),
    max_drawdown_pct=20,
    daily_briefing=old.DailyBriefing(enabled=True, time_local="08:30", timezone="Asia/Kuala_Lumpur", delivery_channels=["push", "in_app"]),
    created_at=now, updated_at=now,
)
snap = json.loads(m.model_dump_json())
assert "daily_briefing" in snap
print("OLD snapshot daily_briefing:", snap["daily_briefing"])

sys.path.insert(0, ".")
from app.schemas.mandate import Mandate as NewMandate

new = NewMandate.model_validate(snap)
redump = new.model_dump()
print("NEW load: OK")
print("daily_briefing dropped on re-dump:", "daily_briefing" not in redump)
print("preserved:", new.display_name, new.risk_score, new.max_drawdown_pct, new.version, new.path)
