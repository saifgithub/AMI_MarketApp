"""DEF147 live null-rate measure — llm_audit room turns through the SHIPPED parser.

Data: llm_audit_room_7d.jsonl in this directory (308 rows, dumped via:
  psql -At -c "select row_to_json(t) from (select created_at, agent_id,
  coalesce(response_text,'') rt from llm_audit where flow='room'
  and created_at > now() - interval '7 days' order by created_at) t")
Run from .claude/worktrees/audit-REL58/backend/ with the backend venv python.
"""
import json, sys
from collections import defaultdict

sys.path.insert(0, ".")
from app.services.room_runner import parse_stance_envelope

days = defaultdict(lambda: [0, 0, 0])  # day -> [total, no-parse, contains 'STANCE']
for line in open("llm_audit_room_7d.jsonl"):
    r = json.loads(line)
    d = r["created_at"][:10]
    days[d][0] += 1
    if "STANCE" in r["rt"].upper():
        days[d][2] += 1
    try:
        _, env = parse_stance_envelope(r["rt"])
        if env.stance is None:
            days[d][1] += 1
    except Exception:
        days[d][1] += 1

for d in sorted(days):
    t, n, s = days[d]
    print(f"{d}: {t:4d} turns, {n:4d} no-parse ({100*n/t:4.0f}%), {s:4d} contain 'STANCE' ({100*s/t:4.0f}%)")
