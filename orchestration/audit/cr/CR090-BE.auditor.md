<!--
CR090-BE.auditor.md — auditor lane file (track U owns). State derives from round
numbers here vs CR090-BE.architect.md (see PROTOCOL.md).
-->

# CR090-BE — audit lane (auditor)

**Item:** CR090 — meter the live News/Social Analyst data feeds via a credit
surcharge; fail LOUDLY (a distinct "paid feature withheld" state) instead of silently
degrading to synthetic. Surcharge model (Saiful 2026-07-26): Room/1-on-1 keep their
flat price; live-data turns add an additive surcharge only when they actually fire
with real data. This lane is the contract only — the surcharge cost + accessor, and
the 3-state liveness marker on the News/Social degrade path.

**Gate:** independent — real credit-spend/entitlement contract, same risk class as
CR084 (money/entitlements, D-5).

**Audited SHA:** `cd292d3`, tip of `lane/CR090-BE.coder.api` (base `main` @ `16af15a`).
Audited in an isolated worktree `.claude/worktrees/audit-CR090-BE/`.

## Round 1

### Reproduced independently

| Check | Result |
|---|---|
| Scope | `git diff 16af15a...cd292d3 --stat` — 6 files, **+545/−0**, purely additive. Matches the architect's claim exactly. |
| Full suite | `.venv/bin/pytest tests/unit/ -q` — **1260 passed**, exit 0 (165s). Matches both the coder's and architect's reported count. |
| `credit_service.py` | `LIVE_DATA_SURCHARGE = 2` + `live_data_surcharge(n)` — pure multiply, `n<=0 → 0`. `ALLOWANCE`/`ROOM_COST_BASIC`/`ROOM_COST_PREMIUM`/`_ROOM_COST_BY_PLAN`/`room_cost_for_plan` untouched (confirmed via diff — the new block is appended after `room_cost_for_plan`, zero lines changed above it). `spend()` not touched here, as claimed — deferred to CR090-ROOM. |
| `news_context.py` | `LiveDataState` enum (LIVE/WITHHELD_PAID/UNAVAILABLE) + pure/total classifier `live_data_state(*, available, entitled)` + `NewsFeed` + `resolve_news_feed`. Existing `fetch_live_news`/`build_news_context_block` byte-unchanged (confirmed via diff — both additions land after existing code, no edits to it). |
| `social_context.py` | Imports the shared `LiveDataState`/`live_data_state` from `news_context` (one-way — confirmed via grep: `news_context.py` has no reference to `social_context`, `social_context.py` imports `news_context`). Adds `SocialFeed` + `resolve_social_feed`, mirroring the news resolver. `fetch_live_sentiment` untouched. |
| Compose parity | No new env-driven setting introduced (grepped the diff — no new `settings.*`/`os.environ` reads) → `test_config_compose_parity` correctly needs no change; it's in the 1260 green. CR040 N/A here, confirmed rather than assumed. |

### Three mutation-tested claims, all caught cleanly

1. **DEF059 inversion guard** — inverted `live_data_state`'s `available and not
   entitled` branch to return `UNAVAILABLE` instead of `WITHHELD_PAID`. Caught by 3
   tests simultaneously: the classifier's own test plus both `resolve_*_feed`
   withheld-path tests (which assert `state is not UNAVAILABLE` independently of the
   classifier test — a genuine second line of defense, not a duplicate assertion).
2. **Payload-leak guard** — changed `resolve_news_feed`'s headline-gating from
   `if state is LIVE` to `if state is not UNAVAILABLE` (i.e. leak the real headlines
   on a WITHHELD_PAID/gated turn). Caught immediately —
   `test_resolve_news_feed_withheld_when_available_but_not_entitled` failed on the
   `feed.headlines == ()` assertion with the real headline object showing through.
   This is the single most safety-critical claim in the lane (a paid payload must
   never leak to a non-entitled turn) and it has a dedicated, independent guard.
3. **Surcharge scaling** — changed `live_data_surcharge` to return a flat
   `LIVE_DATA_SURCHARGE` regardless of `n` (instead of `n * LIVE_DATA_SURCHARGE`).
   Caught by all 3 tests that pin the scaling/constant/illustration.

All three reverted; `git status --short` confirmed clean before moving on.

### Findings

None. Zero BLOCKER, MAJOR, or MINOR. The lane is scoped exactly as claimed — a pure,
additive contract with no spend/room wiring — and every claim in the architect's
adversarial-angles list held under mutation.

### Verdict

**VERDICT: COMPLETE (round 1)**

Run report: [`../runs/2026-07-26_run-51/run_report.md`](../runs/2026-07-26_run-51/run_report.md)
