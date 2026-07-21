<!--
trail.md — the ACTIVE dispatch ledger (DISPATCH_PROTOCOL.md §8.6). Architect appends one TERSE row
per assignment and per closure; newest at the bottom. Owner: Architect.
RETENTION: keep bounded — open lanes + the current period only. When a period turns or this file
grows large, roll older closed rows into ../history/trail/<period>.md. Query with grep/tail, never
slurp. Per-item detail lives in ../history/lanes/<ITEM>.md, not here.
-->

# Dispatch ledger (active)

| When (KL) | Item | Instance | Round | Event | Headline |
|---|---|---|---|---|---|
| 2026-07-21 22:30 | CR052 | architect | 1 | PROTOCOL | Orchestration protocol scaffolded; 9-instance roster seeded; first wave assigned |
| 2026-07-21 23:00 | CR052 | architect | 1 | CONSOLIDATE | Unified under orchestration/ (dispatch/ + audit/ [was audit/handshake] + history/); paths rewired; retention/rotation + rotate_trail.py added |
