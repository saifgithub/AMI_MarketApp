# Checkpoint archives — the cold-start anchor (selected at READ time)

Each `<YYYYMMDDTHHMMSSZ>_<session-id>.md` is one `/sm-checkpoint` memo, archived + committed on
RESTORE. The filename is unique to the writing session (a disjoint write-path), so any number of
sessions can archive concurrently without racing.

**Cold start: read the newest memo carrying YOUR role/instance marker — not the newest file.**
The archives interleave *every* track's sessions (15+ distinct session-ids, filenames keyed by
opaque session-id), so `ls -t | head -1` usually returns some other role's memo. Each memo opens
with an identity line `TRACK: <letter> · ROLE: <name> · INSTANCE: <id-or->`. Select by reading:

```bash
grep -l "ROLE: <your-role>" *.md | sort | tail -1     # timestamp-prefixed → lexical sort = newest
```

**There is deliberately no `LATEST_<track>.md` (or any single shared pointer).** A per-track file
overwritten by every same-role session is a *shared mutable flag*: two sessions committing it
concurrently race and the loser's pointer is swept — exactly what the CR052 protocol forbids
(disjoint write-paths, no shared mutable state, state derived by reading). Selection is therefore
done at read time, never by maintaining a shared file. If no memo carries your marker yet, fall
back to `git log` + the registers.

CR097 (2026-07-27) retired the `/handover` + `/start-fresh` docs; these committed archives replaced
them. The commit convention lives in the repo `CLAUDE.md` ("Autonomy + continuity rules"); the
**global** `~/.claude/commands/sm-checkpoint.md` skill is deliberately not modified.

Only `*.md` here is tracked (`.gitignore` negation); `memory.sqlite` + host-side tooling state stay
uncommitted.
