---
name: bug-monitor
description: Autonomous bug-report triage cycle (CR185). Polls melehost bug_reports for open rows, diagnoses each, files a DEF or CR, commits, then flips the report to investigating. Never asks a question, never touches code, never pushes.
---

> Kimi copy of `.claude/commands/bug-monitor.md` — keep both in sync when the runbook changes.


## Step 1 — Poll

```bash
ssh -o ConnectTimeout=10 melehost "docker exec ami_postgres psql -U postgres -d ami_trade -P pager=off -c \"SELECT id, category, title, app_version, created_at FROM bug_reports WHERE status='open' ORDER BY created_at ASC;\""
```

No rows → stop. Say "no open reports" and exit. Do not manufacture work.

For each open row, pull the detail (steps, route, platform, attachment_path) with the same
`psql` shape, and read any screenshot at `attachment_path` (they land under melehost's
uploads dir; `scp` it to the scratchpad and `Read` it — a screenshot usually IS the
diagnosis).

## Step 2 — Diagnose and collapse

- Read the code the report points at. Name the file and line that produces the behaviour.
- **Collapse duplicates.** Three reports with one root cause = one DEF covering all three.
- If a report is correct-by-design, do not file. Record that in the cycle's commit message
  and still flip it to `investigating`.

## Step 3 — Route by category

| `category` | Files as |
|---|---|
| `feature_request` | **CR**, status `proposed` |
| `ui_glitch` · `wrong_data` · `crash` · `performance` · `other` | **DEF**, status `open` |

If the defect's surface belongs to another active track's files, say so in the row
(`Routed to the <lane> lane`) and do not build it — lane discipline holds here too.

## Step 4 — File

Mint the next free ID by reading the highest in `docs/defect/_registry/` /
`docs/forward_planning/_registry/`. Write ONE row file, then:

```bash
python scripts/registers/gen_registers.py gen all
git commit -m "docs(bug-monitor): triage cycle — DEF### … (AT:R<N> DEF###)" -- \
  docs/defect/_registry/DEF###.row.md docs/defect/def_list.md
```

Row must carry: the reporter handle (`bug:<short-id>`), the build + platform, the
reproduction, the named file/line, the fix direction, and the lane it is routed to.

## Step 5 — Mark investigating (only after the commit succeeded)

```bash
ssh -o ConnectTimeout=10 melehost "docker exec ami_postgres psql -U postgres -d ami_trade -c \"UPDATE bug_reports SET status='investigating' WHERE id IN ('<id>', …) AND status='open';\""
```

The `AND status='open'` guard makes the flip idempotent and race-safe against `/fix-bugs`
running concurrently on another track.

## Step 6 — Report

One line per cycle: N reports read, M DEFs/CRs filed, K flipped, plus anything closed
by-design. Nothing else.
