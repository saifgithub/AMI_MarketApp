<!-- coder lane — coder.api. CR052. -->
# CR090-BE — coder.api

STATUS: READY_FOR_AUDIT (round 1)

Built in `.claude/worktrees/coder.api-CR090-BE/` on branch
`lane/CR090-BE.coder.api` (based on `main` @ `16af15a`). coder.api core only —
no room cluster, no Flutter, per the fixed scope in
`orchestration/dispatch/lanes/CR090-BE.assign.md`.

## What landed (3 files + 1 test file)

1. **`backend/app/services/credit_service.py`** — the surcharge, beside
   `room_cost_for_plan`:
   - `LIVE_DATA_SURCHARGE = 2` (documented constant, per live-data analyst turn).
   - `live_data_surcharge(n_live_analysts: int) -> int` → `n * 2`, clamped to 0
     for `n <= 0`.
   - `ALLOWANCE`, `ROOM_COST_BASIC` (8), `ROOM_COST_PREMIUM` (25),
     `_ROOM_COST_BY_PLAN` — **untouched** (asserted byte-unchanged in tests).
   - **Nothing is spent here.** The `spend()` of the surcharge is CR090-ROOM's
     job (`room_runner.py`). This lane only exposes the figure + accessor.

2. **`backend/app/services/news_context.py`** — the 3-state marker + resolver:
   - `class LiveDataState(Enum)` — the SINGLE shared marker (owned here;
     social_context re-imports it). Values: `LIVE`, `WITHHELD_PAID`,
     `UNAVAILABLE`. Structural enum, not a prompt string (CR038).
   - `live_data_state(*, available: bool, entitled: bool) -> LiveDataState` —
     pure/total classifier. The DEF059 inversion is impossible by construction:
     `available and not entitled` maps ONLY to `WITHHELD_PAID`.
   - `class NewsFeed(NamedTuple)` = `(state, headlines)`; `headlines` populated
     only for `LIVE`.
   - `resolve_news_feed(ticker, *, entitled, limit=3) -> NewsFeed` — additive
     entry point; `fetch_live_news` and all existing binary callers untouched.

3. **`backend/app/services/social_context.py`** — mirror for Social:
   - imports the shared `LiveDataState` + `live_data_state` from news_context.
   - `class SocialFeed(NamedTuple)` = `(state, sentiment)`; `sentiment` set only
     for `LIVE`.
   - `resolve_social_feed(ticker, *, entitled) -> SocialFeed` — additive;
     `fetch_live_sentiment` untouched.

4. **`backend/tests/unit/test_cr090_live_data_surcharge.py`** — 18 tests:
   surcharge math (0/1/2 → 0/2/4), pricing byte-unchanged, classifier truth
   table incl. the WITHHELD_PAID-is-not-UNAVAILABLE guard, the shared-type
   identity, and both resolvers (LIVE/WITHHELD_PAID/UNAVAILABLE + back-compat).

## Evidence

- `cd backend && uv sync --frozen --extra dev` then `.venv/bin/pytest tests/unit/ -q`
  → **1260 passed, exit 0** (146s). New file alone: 18 passed.

## CONTRACT for CR090-ROOM (wire charging + disclosure off this — no guessing)

Shared marker (import from `app.services.news_context`, or re-exported from
`social_context`):

```python
from app.services.news_context import LiveDataState, live_data_state
# LiveDataState.LIVE / .WITHHELD_PAID / .UNAVAILABLE
```

Feed resolvers (entitlement-aware; return the marker + payload-only-when-LIVE):

```python
from app.services.news_context import resolve_news_feed, NewsFeed
from app.services.social_context import resolve_social_feed, SocialFeed

news:   NewsFeed   = resolve_news_feed(ticker, entitled=<bool>)   # .state, .headlines
social: SocialFeed = resolve_social_feed(ticker, entitled=<bool>) # .state, .sentiment
```

Surcharge:

```python
from app.services.credit_service import live_data_surcharge, LIVE_DATA_SURCHARGE
# live_data_surcharge(n) == n * 2   # n = number of analysts whose .state is LIVE
```

**Room-side wiring rule (CR090-ROOM):**
- Count `n_live = number of feeds whose .state is LiveDataState.LIVE`.
- Charge `live_data_surcharge(n_live)` ON TOP of the flat Room/1-on-1 base — the
  surcharge fires ONLY for `LIVE`, never for `WITHHELD_PAID`/`UNAVAILABLE`.
- On `WITHHELD_PAID`: render the loud "this agent's live feed is a paid feature"
  disclosure (the third disclosure-header state). The payload is already empty
  by contract — do NOT substitute the synthetic block as business-as-usual
  (DEF059). Charge nothing for it.
- On `UNAVAILABLE`: the existing honest synthetic-illustrative fallback
  (CR023/CR024), unchanged. Charge nothing.

**Quota note (design choice, non-blocking):** `resolve_*` probe the (cache-first)
live feed even for a non-entitled turn, to distinguish WITHHELD_PAID from
UNAVAILABLE. If protecting the Alpha Vantage / Adanos 250-call/month budget
against non-entitled probes matters, CR090-ROOM can gate the resolver call to
entitled turns and compose WITHHELD_PAID directly via the exposed
`live_data_state(available=..., entitled=False)` classifier without a live fetch.

Audit lane: `orchestration/audit/cr/CR090-BE.architect.md`, SUBMITTED: round 1.
