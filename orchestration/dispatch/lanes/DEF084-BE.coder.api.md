<!-- coder lane — coder.api-owned. DEF084-BE. -->
# DEF084-BE — coder.api

STATUS: READY_FOR_AUDIT (round 1)

SHA: bd5c74d — `fix(mandate): DEF084 Option 2 … (AT:coder.api DEF084)`
AUDIT-LANE: orchestration/audit/cr/DEF084-BE.architect.md (SUBMITTED: round 1)
SELF-TEST: `pytest backend/tests/unit/ -q` → 941 passed (guard verified RED against main first).

ACCEPTANCE: docs/defect/DEF084_halal_flag_is_an_allowlist_not_a_screen/ — **Option 2 only**
(relabel the 7-ticker set as a curated demonstration universe; do NOT wire sharia_screen();
do NOT withdraw the flag).

DEPENDS-ON: none
HOT-FILES: backend/app/services/sim_engine.py, backend/app/agents/safety_floor.py (frozen
signatures — kept stable), backend/app/api/mandate.py
