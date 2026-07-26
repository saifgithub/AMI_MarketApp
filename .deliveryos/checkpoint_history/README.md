# Checkpoint archives — the per-track cold-start anchor

Two kinds of file live here:

- **`LATEST_<track>.md`** — the rolling **cold-start anchor** for one track (`LATEST_G.md` =
  Governance, `LATEST_R.md` = Development, …). **Read `LATEST_<your-track>.md` first** on a cold
  start — it's this track's freshest committed state. It's a copy of that track's most recent
  `/sm-checkpoint` memo, refreshed on each RESTORE. This is what `HANDOVER_<track>.md` used to be,
  minus the rewrite tax (it's a `cp`, not a re-authored doc).
- **`<YYYYMMDDTHHMMSSZ>_<session-id>.md`** — the immutable timestamped history, one per RESTORE.

**Do NOT pick the newest file by timestamp.** The timestamped archives interleave *every* track's
sessions (15+ distinct session-ids, filenames keyed by opaque session-id), so `ls -t | head -1`
usually returns some other track's memo. Select by track via `LATEST_<track>.md`. If your track has
no `LATEST_` file yet, fall back to `git log` + the registers — authoritative and track-unambiguous.

CR097 (2026-07-27) retired the `/handover` + `/start-fresh` docs; these committed archives replaced
them. The commit + `LATEST_<track>.md` conventions live in the repo `CLAUDE.md` ("Autonomy +
continuity rules"). The **global** `~/.claude/commands/sm-checkpoint.md` skill is deliberately not
modified — the session does the commit + copy itself after each RESTORE.

Only `*.md` here is tracked (`.gitignore` negation); `memory.sqlite` + host-side tooling state stay
uncommitted.
