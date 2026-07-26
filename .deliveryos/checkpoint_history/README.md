# Checkpoint archives — the durable cold-start anchor

Each `YYYYMMDDTHHMMSSZ_<session-id>.md` here is one `/sm-checkpoint` memo, archived on
RESTORE. **The newest file is the freshest committed state of the project** — read it first
on a cold start (`ls -t . | head -1`), then cross-check `git log --oneline` + the registers
(a stamped memo can predate commits that landed after it).

CR097 (2026-07-27) retired the `/handover` + `/start-fresh` docs; these committed archives
replaced them. The commit convention lives in the repo `CLAUDE.md` ("Autonomy + continuity
rules") — the **global** `~/.claude/commands/sm-checkpoint.md` skill is deliberately not
modified, so pathspec-commit the archived `.md` yourself after each RESTORE.

Only `*.md` here is tracked (`.gitignore` negation); `memory.sqlite` + host-side tooling
state stay uncommitted.
