# /daily-cr-def-review

Go through every **untouched** CR and Defect — `proposed` CRs, `open` Defects — and ask
Saiful one by one what to do with each, via `AskUserQuestion`. This is the daily sibling
of `/fix-bugs`'s triage step, but for the CR/Defect registers instead of `bug_reports`:
poll, surface, log the decision, **never act on it**. Filed as CR085.

Runs daily at 13:00 Asia/Riyadh (UTC+3, Saiful's timezone) via a `/schedule` cloud routine — can also be run
manually any time.

---

## Hard rules

1. **Never flip a CR/Defect's status, and never touch code.** This command only reads
   the registers and writes to one ledger file. A status change only happens through the
   normal governance flow (the item's domain owner edits its row file + regenerates) —
   see `CLAUDE.md`'s "Change governance" section.
2. **Read status from the row files, not the generated tables.** Always
   `docs/forward_planning/_registry/CR*.row.md` / `docs/defect/_registry/DEF*.row.md` —
   the generated `cr_list.md`/`def_list.md` can silently drift (CR085's own filing found
   `cr_list.md` missing CR084). Self-heal first (step 2 below) so the generated tables
   never lag anyway, but don't depend on them for the source data.
3. **One item, one `AskUserQuestion` call, in sequence.** Don't batch unrelated items
   into one multi-question call — Saiful's answers need to log against distinct items
   cleanly, and "one by one" is the literal ask.
4. **Log every answer immediately**, right after it comes back — not batched at the end.
   A mid-run interruption should never lose an already-collected answer.
5. **Commit only the ledger file**, pathspec-only, never bare/`-am`/`add -A`:
   `chore(governance): daily CR/Def review log YYYY-MM-DD (AT:R<N>)` — docs-only, exempt
   from needing its own CR/DEF tag (CLAUDE.md's Exempt rule). Push directly to `main`; no
   worktree needed — unlike `/fix-bugs`, this never touches code, so there's nothing to
   isolate.
6. **No cap.** Every `proposed` CR + `open` Defect gets asked, every run.

---

## Step-by-step

### 1. Sync

```bash
git pull
```

### 2. Self-heal register drift

```bash
python scripts/registers/gen_registers.py verify all
```

If it reports drift, fix it in the same run:

```bash
python scripts/registers/gen_registers.py gen all
git add docs/forward_planning/cr_list.md docs/defect/def_list.md
git commit -m "chore(governance): regenerate registers — drift fix (AT:R<N>)" \
  -- docs/forward_planning/cr_list.md docs/defect/def_list.md
```

### 3. Build today's list

Parse directly from the row files (never the generated tables):

- **CRs:** every `docs/forward_planning/_registry/CR*.row.md` whose Status column
  (5th `|`-delimited field) is exactly `proposed`.
- **Defects:** every `docs/defect/_registry/DEF*.row.md` whose Status column (7th
  `|`-delimited field) starts with `open` — tolerate `**open**` and `open — <note>`
  variants (seen in practice on DEF089/DEF097).

### 4. Pull prior context per item

```bash
grep -B1 '\*\*<ID>\*\*' docs/governance/daily_cr_def_review_log.md | tail -20
```

For each item in today's list, find its most recent entry (if any) in
`docs/governance/daily_cr_def_review_log.md`.

### 5. Check whether yesterday's stated action happened

For every item with a prior entry:

```bash
git log --all --oneline --grep="<ID>" --since="<date of that log entry>"
```

Combine with whether the row file's Status has actually changed since. Build one short
context line either way — e.g. *"you said 'start it' on 07-24; still `proposed`, no
commit tagged CR014 since"* or *"you said 'drop it' on 07-24; still `proposed`, no
`dropped`/`wont_fix` flip yet — same call, or has this changed?"*. If the action clearly
did happen (status changed and/or a matching commit landed), skip re-asking — log it as
closed instead of asking again.

### 6. Ask, one item at a time

For every item still open after step 5 (prior-context ones first, then brand-new ones),
call `AskUserQuestion` — title/summary of the item, any follow-up context from step 5,
and options tailored to that item (e.g. "Start now", "Keep deferring", "Drop it") plus
the tool's built-in free-form "Other". No forced "(Recommended)" option — Saiful is
prioritizing, not accepting a proposed fix, so there's no honest default to push.

### 7. Log immediately

After each answer, append one line to **today's** `## YYYY-MM-DD` section of
`docs/governance/daily_cr_def_review_log.md` (create the section if this is the first
item asked today):

```
- **<ID>** (<status> since <date>) — asked: "<question gist>" → Saiful: "<raw answer>"
```

### 8. Commit + push

```bash
git add docs/governance/daily_cr_def_review_log.md
git commit -m "chore(governance): daily CR/Def review log $(date +%Y-%m-%d) (AT:R<N>)" \
  -- docs/governance/daily_cr_def_review_log.md
git push
```

### 9. Summarize

Print a one-line-per-item recap: how many asked, how many closed via the step-5
follow-up check without re-asking, and the raw text of each new answer.

---

## What NOT to do

- Don't flip any row file's Status, don't edit `cr_list.md`/`def_list.md` content by
  hand (only via `gen_registers.py`), don't touch application code.
- Don't skip items to keep the list short — no cap, ever (Saiful's call, see CR085).
- Don't batch multiple items into one `AskUserQuestion` call.
- Don't bare-commit or `git add -A` — pathspec only, so this never sweeps up whatever
  unrelated work-in-progress is sitting in the checkout from other tracks.
- Don't `--force` push, ever.
