# Run report — 2026-08-07_run-03

Item: CR124. SHA: `6ea166a6`. Verdict: AWAITING_FIXES (round 1). 3 MAJOR, 0 BLOCKER, 2 MINOR.
Full findings in `orchestration/audit/cr/CR124.auditor.md`.

## Setup

```text
cd "/Volumes/Extreme Pro/AMI_MarketApp"
git worktree add .claude/worktrees/audit-CR124 6ea166a6
```

## Regression suite (independent, scratch worktree, absolute interpreter)

```text
cd .claude/worktrees/audit-CR124/backend
"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest tests/unit/ -q
2365 passed, 13 warnings in 309.54s (0:05:09)
```

Matches submission exactly. Scoped rerun of the 20 CR124/parity tests: `20 passed in 0.99s`.

## Live verification attempted, environment-blocked (matches submission's §5 claim)

- SSH to melehost: down (DEF224), not independently re-attempted (already documented, no
  controllable path here either).
- Docker daemon on Mac: none. `docker info` shows client-only (`Docker version 29.5.3`,
  `Context: desktop-linux`, no server block, no daemon running).

## Verification that WAS available and used (beyond what the submission attempted)

- `docker compose config` — the Docker **client** binary (29.5.3 / Compose v5.1.4) is present on
  the Mac even with no daemon, and pure config-rendering doesn't need one. Ran with no env vars
  (correctly fails on first missing `:?`) and with all 3 dummy credentials + `AMI_ENV` +
  `SECRET_KEY` set (renders cleanly, `mem_limit`/`ports`/`networks`/`profiles` all correct). This
  contradicts the submission's "I could not even `docker compose config`" and is materially
  stronger evidence of compose validity than `yaml.safe_load`.
- Docker Hub registry API (anonymous token flow) to verify all 4 declared image digests resolve
  to their claimed tags — 4/4 exact match.
- Shell-quoting test harness (fake `ssh` echoing argv) to empirically verify the runbook's 3
  trickiest heredoc/embedded-quote constructs — all 3 correct.
- `uv lock --check` (Homebrew `uv 0.10.7`) — `Resolved 123 packages`, matches submission.
- Own mutation tests: removed `REDISCLI_AUTH` from redis's environment (0/20 tests catch it);
  removed `REVOKE CONNECT` from `01_website_role.sql` (0/17 tests catch it); reproduced 3 of the
  submission's 5 claimed mutations independently (loopback bind, `POSTGRES_PASSWORD:?`→`:-`,
  unpinned redis digest — all correctly kill their named test). Tree diffed clean after every
  mutation (`git status --short` empty, `diff` against pre-mutation backup empty).

## Findings summary

1. MAJOR — `backend/Dockerfile:1` base image not digest-pinned; "all five" claim is false;
   guard test structurally can't catch Dockerfile `FROM` lines (only checks compose `image:`).
2. MAJOR — runbook step 3's "additive and safe" framing is wrong: old `api-alpha`'s DSN has the
   password hardcoded (confirmed via `git show 6ea166a6^`), SQLAlchemy pool has no
   `pool_pre_ping`/`pool_recycle` (`app/db/session.py:62`), so overflow connections opened
   between step 3 and step 4 fail auth against the live host.
3. MAJOR — non-root (N7) silently breaks yfinance's on-disk SQLite cache (`~/.cache/py-yfinance`,
   resolves to non-existent, non-writable `/home/ami`); traced the actual installed package
   (`yfinance==1.3.0`) to confirm the failure is caught (not a crash) but retries on every call
   and logs to a stream separate from the app's structured JSON log pipeline. Unflagged by the
   submission, which named only the `bug_attachments` write path.
4. MINOR — `REDISCLI_AUTH` wiring (correct as shipped, reasoned through and confirmed) has zero
   regression coverage; failure mode if dropped is loud (whole stack fails to start) not silent.
5. MINOR — `01_website_role.sql` content (correct as shipped) has zero regression coverage;
   failure mode if a statement is dropped is quiet (only bites on a future fresh-volume deploy).

Plus the central judgment call: even absent the above, live acceptance evidence is categorically
unavailable this round (SSH down, no daemon), and the C3 exposure remains live on melehost per
the submission's own admission — independently, that alone would warrant AWAITING_FIXES on a
security-hardening CR, per the reasoning in the lane file.

## Worktree cleanup

```text
git worktree remove .claude/worktrees/audit-CR124
```
