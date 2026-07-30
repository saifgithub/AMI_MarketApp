# REL58 round 1 — audit run report (track U, 2026-07-29)

Lane: `orchestration/audit/cr/REL58.architect.md` (`SUBMITTED: round 1`, submission commit
`f559452c`). Audited SHA `83e8506a` on `main` in scratch worktree
`.claude/worktrees/audit-REL58/` (removed after the run). Post-ship review of the
`0.1.0+58` batch + CR106. Verdict: **AWAITING_FIXES (round 1)** — two MAJORs, see
`../cr/REL58.auditor.md`.

## Suite re-runs at 83e8506a

| Command | Lane claim | Measured | Verdict |
|---|---|---|---|
| `backend/.venv/bin/python -m pytest tests/unit/ -q` (from worktree `backend/`) | 1589 passed (256s) | **1588 passed, 1 failed** (260s) — `test_registers_no_drift` on CR121 | M1 |
| `flutter test -r compact` (worktree `mobile/`) | 299 passed (25s) | 299 passed (36s) | match |
| `flutter analyze --no-fatal-infos` | exit 0, 5 infos | exit 0, same 5 infos (`main.dart:69`×2, `floor_screen.dart:74,327`, `sign_in_email_disclosure_test.dart:27`) | match |
| `gen_registers.py verify all` | DEF 156 OK, CR 117 OK, no drift | DEF OK 156; **CR drift: CR121 in live, not in _registry** | M1 |

M1 detail: the CR121 row entered `cr_list.md` via the HEAD commit `83e8506a`
(`docs(governance): daily CR/Def review … AT:R65`) with no row file. At audit time a
`CR121.row.md` exists UNTRACKED in the shared working tree (architect remediation in
flight, not yet committed anywhere — `git log --all` for the path is empty).

## Probe 1 — DEF151 live on Alpha

```
GET /v1/sim/history/AAPL?period=1M      → 200, body opens {"ticker":"AAPL","period":"1m",...}
GET /v1/sim/history/AAPL?period=1m      → 200, identical echo
GET /v1/sim/history/AAPL?period=1month  → 422
GET /v1/sim/history/AAPL?period=        → 422
GET /v1/sim/history/AAPL?period=%201M%20 → 200  (strip works)
```

Client cache key: `TickerHistoryKey(ticker, _period.toLowerCase())` (`ticker_chart.dart:78`)
— the key is the client's own normalised token, which equals the server's canonical echo;
`SimHistory.period` (the echo) is parsed into the model but read by nothing. Harmless.

## Probe 2 — DEF129 real snapshot load (`def129_snapshot_probe.py`)

Old schema recovered via `git show d6932f15~1:backend/app/schemas/mandate.py`. Output:

```
OLD snapshot daily_briefing: {'enabled': True, 'time_local': '08:30', 'timezone': 'Asia/Kuala_Lumpur', 'voice_id': None, 'delivery_channels': ['push', 'in_app'], 'language': 'en'}
NEW load: OK
daily_briefing dropped on re-dump: True
preserved: Pre DEF129 Snapshot 3 20 1 active
```

The lane's "Pydantic ignores unknown fields" claim — previously reasoned from config —
is now measured on a snapshot serialized by the actual pre-change schema.

## Probe 3 — CR114 chip parser (`cr114_chip_probe.py`)

```
== shipped chips ==
['halal']                       <- 'ONLY halal / Sharia-compliant'
['esg_lite']                    <- 'ONLY ESG-leaning'
['liquid_only']                 <- 'ONLY liquid names (no microcaps)'
['long_only']                   <- 'ONLY long positions (no shorting)'
['no_tobacco_alcohol_gambling'] <- 'NEVER tobacco, alcohol or gambling'
['no_fossil_fuels']             <- 'NEVER fossil fuels'
[]                              <- 'No hard rules'

== adversarial ==
['no_fossil_fuels']  <- 'No hard rules, NEVER fossil fuels'        (union wins over "no rules"; multi-select quirk)
[]                   <- 'NEVER long positions'                     (hypothetical inverse chip: NO flag)
[]                   <- 'ONLY long positions'                      (chip minus parenthetical: NO flag — parse rides on "no short")
['no_tobacco_alcohol_gambling'] <- 'no alcohol'                    (single exclusion → triple flag; parser has no finer grain)
['halal']            <- 'sharia'
[]                   <- ''
['esg_lite','halal'] <- two-chip join                              (union, correct)
```

Every shipped chip → exactly its own flag; none → two flags. The fragility (parenthetical
dependency) is pinned by the lane's contract test for the shipped set. NOTE: the breadth
reader's hypothetical that "NEVER long positions" would still set `long_only` is WRONG —
measured: it sets nothing. The real exposure is the opposite direction (dropping the
parenthetical silently un-wires the flag).

## Probe 4 — DEF147 null rate on live llm_audit (`def147_null_rate.py` + `llm_audit_room_7d.jsonl`)

308 `flow='room'` prose-agent turns, 7 days to 2026-07-29 10:24Z, parsed with the shipped
`parse_stance_envelope` from the worktree:

```
2026-07-23:   11 turns,   11 no-parse (100%),    2 contain 'STANCE' ( 18%)
2026-07-25:   33 turns,   33 no-parse (100%),    8 contain 'STANCE' ( 24%)
2026-07-27:   44 turns,   44 no-parse (100%),   12 contain 'STANCE' ( 27%)
2026-07-28:  132 turns,  132 no-parse (100%),   23 contain 'STANCE' ( 17%)
2026-07-29:   88 turns,    2 no-parse (  2%),   88 contain 'STANCE' (100%)
```

Post-fix era = 2026-07-29: **2/88 = 2.3% null**. Both nulls are `research_manager`
(05:54:08Z, 09:38:34Z) with the envelope entirely ABSENT — full-length prose, no STANCE
line head or tail — i.e. model omission, not truncation, handled as designed
(null ≠ neutral). The pre-fix "27%" in the DEF147 row was measured with the old
end-anchored ruler; under one ruler the real pre-fix parseable rate was ~0% with only
~20% of turns even attempting the envelope. **CR112's blocking number: ~2% on live
traffic.** (The 10:50Z `ami_api_alpha` restart postdates the last room turn at 10:24Z;
DEF147 was already serving before it.)

## Breadth re-read (7 parallel readers, full static pass over all 20 items' diffs
## + final state at file:line)

Method note: 7 read-only sub-readers, one per item group, each instructed adversarially
(quote file:line for every claim, check final state vs diff intent, hunt dead code /
vacuous tests / dangling references). Every finding that made the verdict was
cross-checked against my own reads during the deep-attack pass. Raw reports:
`breadth_reports.txt`.

## Interaction read (attack #1) — summary

CR118 × CR120 × CR117 × DEF156 in `portfolio_screen.dart`: nested ListView has its own
`ScrollController` (:856 → `primary: false`), `NeverScrollableScrollPhysics` when content
fits, `ClampingScrollPhysics` when overflowing (a 99pt scroll-trap strip when it
overflows — the CR's chosen design); tab bar and value card sit outside all scroll views;
IndexedStack keeps `_SectorLegendState` alive across tab switches; only the two renamed
CR117 shapes referenced (:390, :498); `_JournalPointer` (:1450-1496) implements exactly
the post-DEF156 three retention states. File untouched by any later batch commit
(`git log 60efa05d..HEAD -- <file>` empty). Finger-on-glass: NEEDS-DEVICE-CHECK, as the
lane states.
