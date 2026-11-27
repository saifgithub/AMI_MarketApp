# ISS003 state

- 2026-11-25: convened (AT:B1) after DEF547 round 3 (device run AMI-DL-35). Saiful: "Dilemma + log-only meanwhile".
- Interim control: `ROOM_FACTCHECK_NOTES=log` on Alpha from deploy #36 (notes computed and logged, not shown in Room text).
- Contributors: none yet. Saiful invites each in a fresh session with INVITE_PROMPT.md.
- Next: collect at least two independent SOLUTION.md files, then judge and write VERDICT.md.
- 2026-11-26: first two contributors (LUNA, MAI_CODE2) ran in the repo root on `main`, which has neither this brief nor the DEF547 fact-check code; one reported the brief missing. Their SOLUTION.md files (untracked, in the root checkout's copy of this folder) were written without the evidence. INVITE_PROMPT now names the worktree (`f2c5221d`); each is asked to revise from the brief before judging.
- 2026-11-26: three submissions in, all committed on `beta/cr267`: FABLE (`342968f3`; figure provenance by value, measured on 369 stored Rooms), MAI_CODE2 (numeric atoms by ID; read the brief from `6a98972a`; its demo has 1 failing test of 6), LUNA (revised after reading the brief on `beta/cr267`; claim ledger with typed sources). The two root-checkout folders were moved here as written. Next: judge, write VERDICT.md.
- 2026-11-27: format-compliance measurement merged (`c80722ed`). VERDICT.md written: FABLE > LUNA > MAI_CODE2; recommendation is FABLE's provenance-by-value, shadow-first with a per-market gate, plus LUNA's Risk Officer log-mode gap closed first. Decision owed: Saiful.
- 2026-11-27: Saiful: "Ok. Let's do ISS003 as you recommended" (narrowed: Risk Officer fix + FABLE's check in shadow only, measure noise on real prompts, then decide visibility). Implementation CR288 (`4695e7e7`), build running.
