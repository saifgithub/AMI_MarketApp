# Zone Wireframe — Holding Detail Screen

## Vertical scroll order (top to bottom)

The holding detail screen is a single `ListView` with these zones stacking vertically:

1. **Chart zone** (placeholder while in-dev, Tier 1)
   - Candlestick + SMA/EMA + volume bars
   - Height: ~180–220 px (responsive to screen width)
   - Status: in development in production
   - Collapsing: if chart data missing → zone hidden

2. **Position card** (already exists)
   - Ticker, position size, avg cost, unrealised P&L, % return
   - Status: shipped
   - No change

3. **Quick-actions row** (already exists)
   - Trade, Ask Analyst, Convene Room, Close Position
   - Status: shipped
   - No change

4. **News strip** (Tier 1, section 09)
   - Up to 5 headlines with publisher + timestamp
   - Headline tap → system browser
   - Height: ~120 px (3–5 items, variable)
   - Collapsing: if no news available → "No recent news" empty state, or zone hidden

5. **Earnings & Dividend chip** (Tier 2, section 11)
   - Inline chip: "Earnings: Jun 12" | "Ex-div: Jul 3"
   - Collapsing: if both dates are None → zone hidden

6. **Stop & Target chip** (Tier 3, section 15)
   - Inline: "Stop: $120" | "Target: $160" | "Trailing stop: 5%"
   - Collapsing: if no stop/target → zone hidden

7. **Trade history list** (already exists)
   - Open + closed trades with entry/exit prices, P&L
   - Status: shipped
   - No change

---

## Zone toggle logic

Each zone is independently toggleable: if data is missing (null/empty), the zone is hidden, not stubbed. The screen reflows automatically via `ListView` layout.

Example state table:

| State | Chart | News | Earnings | Stop | Rendered |
|---|---|---|---|---|---|
| Full data | ✓ | ✓ | ✓ | ✓ | All zones visible, full scroll |
| No news | ✓ | ✗ | ✓ | ✓ | Chart, earnings, stop, history (news zone hidden) |
| No chart | ✗ | ✓ | ✓ | ✓ | News, earnings, stop, history (chart zone hidden) |
| Only position | ✗ | ✗ | ✗ | ✗ | Position card + quick-actions + history only |

---

## Scroll behavior

- Zones are not independently scrollable — the entire holding detail screen is one scrollable `ListView`.
- Pull-to-refresh re-fetches: live quote (position card), news (if available), stops (mandate evaluation).
- Sticky quick-actions row is deferred (not in Tier 1).

---

## Rendering responsibility

| Zone | Folder | File | Widget |
|---|---|---|---|
| Chart | (production) | `holding_detail_screen.dart` | `_ChartZone()` (in-dev) |
| Position | (shipped) | `holding_detail_screen.dart` | `_PositionCard()` |
| Quick-actions | (shipped) | `holding_detail_screen.dart` | `_QuickActions()` |
| News | section 09 | `09_per_ticker_news/` | `NewsStrip()` — added to holding_detail_screen.dart |
| Earnings | section 11 | `11_earnings_dividends/` | `EarningChip()` — added to holding_detail_screen.dart |
| Stop/Target | section 15 | `15_trailing_stop/` | `StopTargetChip()` — added to holding_detail_screen.dart |
| Trade history | (shipped) | `holding_detail_screen.dart` | `_TradeHistory()` |

Each Tier feature track (09, 11, 15) produces:
- A re-usable Flutter widget (`NewsStrip()`, `EarningChip()`, `StopTargetChip()`) with full theme support
- An import statement and list item in the holding detail `ListView.builder()`

---

## No hard sizing

Heights for news and earnings are variable (1–5 items, responsive to content). The `ListView` handles reflow. Do not hardcode zone heights.

---

## Empty states

- **No news:** "No recent news available" text in neutral gray, centered in the news zone space, ~30 px height
- **No earnings date:** earnings zone is hidden (not rendered)
- **No stop/target:** stop/target zone is hidden (not rendered)

---

## Animation / transitions

None at Tier 1. Zones appear/disappear based on data availability. Tap actions (news link, trade button) navigate normally. Tier 2+ can add transitions if UX testing supports it.
