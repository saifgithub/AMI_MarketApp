# CR100 — Render the three dark BE contracts on the portfolio surface

**Status:** proposed → in_progress · **Filed:** 2026-07-27 (AT:R65)
**Umbrella for:** the mobile halves of **CR026** (sector allocation donut), **CR029**
(per-lot cost basis), **CR030** (dividend sub-chip).

## Why one CR instead of three sub-lanes

Three separately-approved features whose backends all landed and whose UI never did.
They share one instance (`coder.mobile`), one pair of screens
(`portfolio_screen.dart`, `ticker_detail_screen.dart`), and one failure mode (the
hand-mirrored `fromJson`). Three concurrent lanes would contend on the same Flutter
files for no benefit; three sequential lanes triple the audit round-trips for what is
one coherent unit of delivery. The parent CRs' mobile halves close when this lands.

## The problem, measured

Every one of these endpoints is live and serving. Nothing on the client reads them:

```
$ grep -rn "sector_allocation\|sectorAllocation\|ex_dividend\|exDividend\|dividend_rate\|lots" \
    mobile/lib --include="*.dart"
(no hits)
```

The clearest single illustration is `mobile/lib/models/sim.dart:313-321`.
`SimEarnings.fromJson` reads `earnings_date`, `quarter`, `eps_estimate` — and stops.
The backend has been sending `ex_dividend_date` and `dividend_rate` on the same
response since CR030 (`backend/app/api/sim.py:599-601`). The client silently discards
them. Nothing failed, nothing logged, no test went red. **That is the whole class of
defect this CR exists to close** — the same shape as DEF038 and DEF063, each of which
sat dark for months for want of one wiring line, and the reason CLAUDE.md's
degrade-loudly rule exists.

## The three contracts (exact, read from the source 2026-07-27)

### 1. CR026 — sector allocation donut
`GET /v1/portfolio/sector-allocation/{user_id}` (`backend/app/api/portfolio.py:47`)

```json
{
  "allocation": {"Technology": 0.4212, "Other": 0.1},
  "total_value": 12345.67,
  "compliance": {
    "max_sector": 0.4212,
    "max_sector_name": "Technology",
    "max_allowed": 0.40,
    "compliant": false
  }
}
```

- `allocation` weights are normalised over invested market value, 4 dp.
- `max_allowed` comes from the user's mandate `concentration_tolerance`, **never
  hard-code 0.40** — a user can change it.
- `max_sector_name` is `null` when the portfolio holds only unclassified tickers.
- **The `"Other"` bucket is disclosed but never counts as a breach** — that is the
  DEF059 inversion guard, deliberate. The UI must not render "Other" as a violation.

### 2. CR029 — per-lot cost basis
`GET /v1/sim/lots/{user_id}/{ticker}` (`backend/app/api/sim.py:441`)

```json
{
  "ticker": "AAPL", "current_price": 231.4, "price_source": "yfinance_live",
  "lots": [{
    "entry_trade_id": "...", "entry_date": "2026-05-02T13:00:00Z",
    "entry_price": 180.0, "quantity": 10.0, "quantity_open": 4.0,
    "quantity_closed": 6.0, "realised_pnl": 300.0,
    "unrealised_pnl": 205.6, "status": "partially_closed"
  }],
  "totals": {"realised_pnl": 300.0, "unrealised_pnl": 205.6, "quantity_open": 4.0}
}
```

- `status` ∈ `"open" | "partially_closed" | "closed"` (source: `Lot`,
  `backend/app/services/cost_basis_lots.py:60-71`).
- `unrealised_pnl` is **nullable** — `None` when the price is unknown. A closed lot's
  unrealised P&L is not zero, it is absent; render it as such, don't coerce to 0.
- Draw-down is FIFO. Self-closed buys (stop / target / manual) become fully-closed
  lots carrying their recorded P&L.

### 3. CR030 — dividend sub-chip
`GET /v1/sim/earnings/{ticker}` (`backend/app/api/sim.py:581`) — same response the
earnings pill already consumes, two extra keys:

- `ex_dividend_date` (`"YYYY-MM-DD"` or null)
- `dividend_rate` (float or null)

`null` on both means non-payer or no window ⇒ **chip hidden**, per CR030's own design.

## Scope

- `mobile/lib/models/sim.dart` — extend `SimEarnings`; add `HoldingLots` / `Lot`.
- New model for the sector-allocation response.
- `mobile/lib/services/api/api_client.dart` — the two new GETs.
- `mobile/lib/screens/sim/portfolio_screen.dart` — the allocation donut + the
  concentration marker.
- `mobile/lib/screens/sim/ticker_detail_screen.dart` — the dividend sub-chip beside
  the existing earnings pill; entry point to the per-lot cards.
- i18n strings with context comments (EN authored; AR/MS are Saiful's external
  arrangement and are **not** blocking).

## Out of scope

- Any backend change. All three contracts are already live and audited; if one looks
  wrong, file a defect, don't edit `backend/`.
- CR090's live-data disclosure (that is CR090-MOBILE, gated on CR090-ROOM's event shape).
- New screens. All three attach to existing surfaces.

## Acceptance

- `flutter analyze` clean; `flutter test` green with the new tests.
- **A contract test per endpoint that parses a real captured response body**, not a
  hand-written fixture that mirrors the model. The hand-mirror is the defect; a fixture
  written from the model reproduces the bug instead of catching it.
- No `?? <default>` that can mask an absent or renamed key on a required field. Where a
  key is genuinely nullable (`unrealised_pnl`, `max_sector_name`, both dividend fields),
  null must be *rendered as absent*, never as zero or as a breach.
- The donut reads `max_allowed` from the response; a mandate with
  `concentration_tolerance` ≠ 0.40 moves the marker.
- `"Other"` never renders as a compliance breach.
- Dividend chip hidden when both fields are null; shown when either is present.

## Risk class

Read-only UI over already-audited backends — no money, no schema, no safety floor.
`GATE: spawned` is sufficient; this does not need Saiful's independent track-U slot.
