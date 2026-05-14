# Floor Home — the Honeycomb

The signature home screen. Concierge at the centre, the 12 agents tessellated around her in a hexagonal flower pattern.

This is the screen that defines AMI Trade's visual identity. No other app looks like this.

## Why this design

Standard mobile apps put a briefing card on top and a grid of icons below. That's fine — but it wastes the hex motif by treating hexagons as decorative.

Our design **uses the hexagon as the layout primitive**. The user opens the app and sees a hexagonal honeycomb where each cell is a member of their team. The AI (Concierge) is at the centre, narrating. The agents orbit her.

This communicates AI-first **structurally**, not just visually. The user reads the floor as a *room with people in it*, not a *dashboard with options*.

## Layout

The honeycomb is a "flower" pattern: central hex + 6 surrounding hexes = 7 cells in the inner pattern. We extend this:

```
                ┌────────────────────────────────┐
                │  HEADER (64px fixed)           │
                │  ⬢ Logo  [Ask…]  ⬢ -4%/30%     │
                ├────────────────────────────────┤
                │                                │
                │       ⬢ FUND      ⬢ MKT        │   ← Analyst row (cyan)
                │                                │
                │   ⬢ NEWS    ⬢⬢⬢⬢   ⬢ SOC     │
                │             ⬢CNC ⬢             │   ← Concierge at centre (pink, 2× scale)
                │   ⬢ BULL    ⬢⬢⬢⬢   ⬢ BEAR    │   ← Researchers (purple)
                │                                │
                │       ⬢ AGG       ⬢ CON        │   ← Risk row (amber)
                │             ⬢ NEU              │
                │  ⬢ RES-M   ⬢ TRADE    ⬢ PM     │   ← Managers + Trader
                │                                │
                ├────────────────────────────────┤
                │ MANDATE HEALTH                 │
                │ Drawdown:  4% / 30%  ⬢ ✓       │
                │ Halal:     ✓                   │
                │ Agents active: 4 / 12          │
                ├────────────────────────────────┤
                │ STREAK     🔥  12 days         │
                ├────────────────────────────────┤
                │ TODAY'S BRIEFING               │   ← (collapsed by default;
                │ "NVDA up 3.2% overnight..."    │     center hex streams when expanded)
                │ [▶ Play 90s]   [Read]          │
                ├────────────────────────────────┤
                │ WATCHLIST SIGNAL                   │
                │ AAPL  +1.2%   ⬢⬢⬢ 3 flagged    │
                │ NVDA  +3.2%   ⬢ Bull excited   │
                └────────────────────────────────┘
                              [⬢ CONVENE]
                ├────────────────────────────────┤
                │  Floor | Sim | Convene | Acad | Jrn │
                ├────────────────────────────────┤
                │[CLOSED] AAPL $192.34 ↑1.2% · NVDA…│  ← TICKER TAPE (28px, scrolling)
                └────────────────────────────────┘
                ════════ home indicator inset ═══════
```

## The Concierge centre

The central hex is the **Concierge** — pink, 2× scale, and **alive**.

| State | Visual |
|---|---|
| **Idle** (no new content) | Flat pink hex with Concierge glyph |
| **Briefing ready** | Hex pulses softly; tap opens streamed briefing text inside the hex (Matrix Console aesthetic) |
| **Speaking** (briefing playing) | Hex shows a sound-wave visualisation; text streams character-by-character |
| **Has a message for you** | Pink glow + a small numeric badge ("3 new" — could be reminders, scheduled briefings, drift alerts) |

Tapping Concierge → opens her full-screen thread (the same thread reachable from the header pill).

## The 12 agent orbits

| Position | Family | Members |
|---|---|---|
| **Top row** | Analysts | Fundamentals, Market |
| **Upper sides** | Analysts | News (left), Social (right) |
| **Mid row** | Researchers | Bull (left), Bear (right) |
| **Lower upper** | Risk | Aggressive, Conservative |
| **Lower middle** | Risk | Neutral |
| **Bottom row** | Manager/Execution | Research Mgr, Trader, Portfolio Mgr |

Hex avatar size: **~96px wide** on a standard phone. Concierge: ~160px. Fits ~4 hexes per row with breathing room.

### Agent hex states

| State | Visual |
|---|---|
| **Locked** (not yet unlocked via Earn or Skip Path) | Dimmed slate fill, lock glyph top-right, no role color |
| **Idle** (unlocked, no recent activity) | Solid role color, no glow |
| **Recent call** (contributed to a Room in the last 24h) | Solid role color + soft glow (10–15% intensity) |
| **Signal** (this agent flagged something noteworthy today) | Solid role color + pulsing glow (animated, 0.5Hz) |
| **Attention** (agent wants to talk — e.g., Coach prompt, drift alert) | Solid role color + amber outline + small `!` badge |

### Interactions per hex

| Gesture | Effect |
|---|---|
| Tap | Open agent profile (full screen) |
| Long-press | Quick 1-on-1 chat opens as bottom sheet |
| Tap on locked hex | Open Agent Academy module for that agent (or upgrade prompt if Skip Path is preferred) |

## Below-the-fold sections (scroll-revealed)

The honeycomb occupies the top ~50% of the viewport. Below the fold:

### Mandate Health

A live status strip. Three quick metrics:

| Metric | Display |
|---|---|
| **Drawdown vs cap** | Hex-clipped progress bar: `4% / 30%`. Color-coded: green (≤50% of cap) → amber (50–80%) → red (>80%). |
| **Halal compliance** | ✓ or ⚠ — if user's halal flag is on and portfolio has violations |
| **Agents active** | "4 / 12" — counts how many of the 12 are activated |

Tap any → drill down (drawdown → Sim, halal → audit screen, agents → Academy).

### Streak

A single hex with the day count and 🔥 emoji. Tap → daily challenge if not done yet today; else streak history.

### Today's Briefing card (collapsible)

By default **collapsed** to a one-line summary: *"NVDA up 3.2% overnight, your team has 2 takes — tap to read."*

Tap to expand:
- Full text briefing (text always free)
- ▶ Play 90s audio (paid tier; TTS in user's mandate language)
- Tap each ticker mentioned → drill down

The center hex (Concierge) can also display the briefing if user prefers — tapping the hex expands the briefing *inside* the hex with Matrix Console streaming.

### Watchlist Signal

Top 3 tickers from user's watchlist where at least one agent has a signal today.

```
AAPL  +1.2%  ⬢⬢⬢  3 agents flagged
NVDA  +3.2%  ⬢      Bull Researcher excited
MSFT  -0.8%  ⬢      Bear Researcher cautious
```

Tap a row → ticker sub-page with full agent takes, "Convene the Room" CTA.

## First-run variant (0 agents unlocked)

Before the user completes their first Agent Academy module:

```
                ⬢       ⬢
                                          ← all 12 locked, dimmed
              ⬢      ⬢⬢⬢⬢     ⬢
                     ⬢CNC ⬢                ← Concierge HUGE, pulsing
              ⬢      ⬢⬢⬢⬢     ⬢
                                          
                ⬢       ⬢
                   ⬢
              ⬢       ⬢       [⬢ FUND]   ← Fundamentals Analyst PULSING
                                              ← (the recommended first unlock)

           ┌─────────────────────────────────────┐
           │ Complete Module 1 to meet your      │
           │ first analyst — or upgrade to       │
           │ meet the whole team.                │
           │                                     │
           │ [Start Module 1]  [Upgrade]         │
           └─────────────────────────────────────┘
```

This single screen embodies the dual-gating choice (Earn or Skip), in the user's first interaction post-onboarding.

## Variant: Trader tier, all 12 unlocked

For a paying user with all 12 unlocked, the honeycomb is fully lit. The animation tilts toward "live trading floor" — different agents move into the "active" state during the day:

- 7am-9am (pre-market): News Analyst pulses (digesting overnight)
- 9:30am open: Market Analyst pulses (chart action)
- After market close: Trader and PM pulse (digesting trades)

The board feels alive without being noisy. (Animation is v1.0; alpha is static.)

## Pinch-to-zoom (accessibility)

For users who prefer larger touch targets, pinch-spread on the honeycomb zooms to 3-per-row instead of 4. Concierge stays centre, agents reflow.

---

## Ticker Tape (below the bottom nav bar)

A slim scrolling strip anchored **below the 5-tab nav bar**, above the system home indicator. Sourced directly from Yahoo Finance — no AMI backend hop.

### Behaviour

| Property | Value |
|---|---|
| Height | 28 px content + system bottom inset |
| Scroll direction | Right-to-left (LTR locales) / Left-to-right (RTL locales — AR, MS) |
| Scroll speed | ~60 px/s |
| Refresh rate | 120 s silent background refresh (no shimmer flash between cycles) |
| Tap | Pauses tape 2 s → opens watchlist action sheet for that ticker |
| Tabs | Visible on all 5 tabs |

### Content per item (fixed 160 px wide)

```
AAPL  $192.34  ↑1.2%  ·
```

- **Symbol** — `labelMono`, `textMed`
- **Price** — `labelMono`, `textHigh`, 2 dp
- **Arrow + %** — `↑` `hexGreen` / `↓` `hexRed` / `–` `textLow`, vs previous close, 1 dp
- **Separator** — `·` `textLow`

### Ticker source

User's watchlist tickers lead; bourse defaults fill the tail to a minimum of 10 symbols. Bourse is `us` at alpha (Tadawul `sa` and Bursa `my` default lists are defined ready for Phase 2).

### Status pill (pinned at leading edge)

| `marketState` | Pill |
|---|---|
| `REGULAR` | — (hidden) |
| `PRE` | amber `PRE-MKT` |
| `POST` | amber `AFTER-HRS` |
| `CLOSED` | slate `CLOSED` |
| network failure | red `STALE` (last known prices kept) |

### Visual

```
─────────────────────────────────────────────────────── ← slate700 border
[CLOSED]  AAPL $192.34 ↑1.2% · MSFT $415.20 ↓0.3% · NVDA $875.00 ↑2.1% · ···  ← scrolling
                                                         ← slate900 bg
──────── home indicator inset ──────────────────────────
```

### Implementation

- `mobile/lib/services/yahoo_finance_service.dart` — `YahooFinanceService`, `TickerQuote`, `Bourse` enum
- `mobile/lib/state/ticker_tape_provider.dart` — `tickerTapeProvider`, `TickerTapeData`, `activeBourseProvider`
- `mobile/lib/widgets/ticker_tape.dart` — `TickerTape`, `_ScrollingTape`, `_TapeItem`, `_StatusPill`
- `mobile/lib/screens/home_shell.dart` — tape added below `BottomNavigationBar` inside `Column`

Accessibility: VoiceOver / TalkBack reads each hex as "[Agent name], [status], double-tap to open profile, two-finger-tap for chat."

## RTL handling

The honeycomb is radially symmetric. RTL flips the surrounding labels and tab bar but the honeycomb itself reads identically. **No layout change needed.**

The mandate badge moves to top-left, logo to top-right.

## Performance notes

- Each hex avatar is ~3KB (clipped Container with Text). 12 hexes + Concierge = ~50KB total render footprint.
- Pulse animations use `AnimationController` shared per family (single timer for all 4 cyan analysts).
- No images. No video. The honeycomb is 60fps on any device from 2020+.
- Briefing audio streams from CDN (not embedded).

## Cross-references

- Implementation specifics: [`ami_hex_in_flutter.md`](ami_hex_in_flutter.md)
- Agent role colours: [`colors_motion_rtl.md`](colors_motion_rtl.md)
- Concierge content (briefing): [`docs/02_agents/concierge.md`](../02_agents/concierge.md)
- Daily Challenge interaction: [`docs/04_education/daily_and_streaks.md`](../04_education/daily_and_streaks.md)
