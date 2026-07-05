# Colors, Motion & RTL

Role-color palette mapping, motion principles, and RTL (Arabic) handling.

## Role-color palette

All AMI Trade UI colors derive from the AMI design system's 6-color palette. AMI Trade extends with a 7th — pink for Concierge — distinct from the trading agents.

| Color | Token | Used for |
|---|---|---|
| **Hex-blue** `#3b82f6` | `--hex-blue` | Primary brand. Trader tier badge. Primary CTAs. Floor active-tab indicator. |
| **Cyan** `#06b6d4` | `--hex-cyan` | **Analysts family** — Fundamentals, Market, News, Social Media |
| **Purple** `#a855f7` | `--hex-purple` | **Researchers + Managers family** — Bull, Bear, Research Mgr, Portfolio Mgr; Floor Manager tier badge |
| **Amber** `#f59e0b` | `--hex-amber` | **Risk family** — Aggressive, Conservative, Neutral; mandate-violation warning state |
| **Green** `#10b981` | `--hex-green` | Trader agent; positive P&L; passing compliance checks |
| **Red** `#ef4444` | `--hex-red` | Negative P&L; mandate violations (rejected trades) |
| **Pink** `#ec4899` | `--hex-pink` | **Concierge** — exclusive to the 13th agent; never used for trading agents |

### Color use rules

**Family color is sacred.** Always use the family color for that agent's:
- Hex avatar
- Chat bubble accent
- Status indicators
- Section headers when discussing that agent

**Cross-family color use:**
- Use **hex-blue** for primary CTAs (regardless of context)
- Use **green** for positive P&L numbers regardless of which agent surfaced them
- Use **red** for mandate violations regardless of which agent flagged them
- Use **amber** for "needs attention" UI elements regardless of family

**Combinations to avoid:**
- Cyan text on cyan background (analyst-on-analyst — illegible)
- Red text in the Trader agent's bubble (mixes role-color with status-color confusingly)
- Pink anywhere outside Concierge (dilutes her signature)

## Status colors

Beyond role-colors, system status uses:

| State | Color | Use |
|---|---|---|
| **Success** | Green (`--hex-green`) | Confirmations, positive metrics, passing checks |
| **Warning** | Amber (`--hex-amber`) | Cautions, drift alerts, threshold approaches |
| **Error** | Red (`--hex-red`) | Failed actions, mandate violations, errors |
| **Info** | Cyan (`--hex-cyan`) | Neutral information, tips, lesson references |

## Backgrounds (per AMI spec)

Never flat. Always one of:

| Surface | Spec |
|---|---|
| **Canvas** | `#0f172a` slate + 3% hex-mesh overlay SVG |
| **Hero / above-the-fold** | Canvas + top-centred radial blue glow (`hex-blue` at 15% opacity, 400px diameter) |
| **Glass panel** | `rgba(17,24,39,0.7)` + `backdrop-filter: blur(8px) saturate(180%)` |
| **Chrome (header)** | `rgba(15,23,42,0.85)` + `backdrop-filter: blur(12px) saturate(180%)` |
| **Accent card** | Glass panel + 3px top border in role color |

## Type ramp (per AMI spec)

| Style | Family | Size / weight | Use |
|---|---|---|---|
| H1 | Inter | 32 / 700 | Page hero |
| H2 | Inter | 24 / 700 | Section heading |
| H3 | Inter | 18 / 600 | Card title |
| H4 | Inter | 16 / 600 | Subtitle |
| Body | Inter | 14 / 400 | Default text, 1.5 line-height |
| Caption | Inter | 13 / 400 | Secondary |
| Label Mono | JetBrains Mono | 13 / 500 | UPPERCASE labels, button text, tags, badges, 0.1em letter-spacing |
| Stat Big | JetBrains Mono | 42 / 700 | Big numbers — portfolio value, P&L |
| Stat Mid | JetBrains Mono | 24 / 600 | Medium numbers — drawdown %, agent counts |
| Stat Small | JetBrains Mono | 16 / 500 | Inline numbers, prices, percentages |
| Stream | JetBrains Mono | 13 / 400 | Matrix Console agent logs |

## Motion principles (per AMI spec)

> Minimal and functional. No spring, no bounce, no parallax.

| Property | Value |
|---|---|
| **Default transition** | `transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1)` (ease-out) |
| **Hover lift on cards** | `translateY(-2px)` + soft shadow (30px) |
| **Hover scale on hex buttons** | None — `clip-path` makes scale look broken |
| **Hover fill flip on hex buttons** | Tint → solid color, text → white |
| **Active period toggle** | Solid `--hex-blue` background, faint glow |
| **Focus** | `outline: 2px solid hex-blue, offset 4px` |
| **Press** | Slight darken of fill, no shrink |
| **Pulse animation** (active agent) | 0.5Hz, opacity 0.6 → 1.0 → 0.6, `--hex-{family}` glow |
| **Streaming text** | Typewriter at 40 char/sec |

### Animation timing

| Duration | Used for |
|---|---|
| 150ms | Quick reactions (button press, tap feedback) |
| 200ms | Default — view changes, color transitions, hover |
| 350ms | Modal entries, page transitions |
| 1–2s | Hex pulse cycles (long-form attention pulses) |

### What NOT to do

- No bouncy spring physics (iOS-default look — too playful)
- No parallax scroll
- No CSS keyframe `@keyframes` for things easily done with transitions
- No motion on text (no fade-in-text, no animated word counters)
- No video backgrounds
- No Lottie animations except for the briefing audio waveform

## RTL (Right-to-Left) handling for Arabic

The Arabic locale (`ar-SA`, `ar-AE`, etc.) flips the entire layout.

### What flips automatically

| Element | Behaviour |
|---|---|
| **Layout direction** | `Directionality(textDirection: TextDirection.rtl)` wraps the app at the root |
| **Padding/margin** | Use `padding-inline-start` / `padding-inline-end` (Flutter `EdgeInsetsDirectional`) — flips automatically |
| **Text alignment** | Default left-align becomes right-align |
| **Row arrangement** | `Row` widgets reverse |
| **Tab bar** | Floor / Sim / Convene / Academy / Journal reads right-to-left |
| **Header layout** | Logo right, mandate badge left |

### What stays the same

| Element | Behaviour |
|---|---|
| **Hexagons** | Radially symmetric — no flip needed |
| **Numbers** | Stay LTR even inside RTL paragraphs (ICU default — `$152.43` reads correctly) |
| **Tickers** | Stay LTR (`NVDA`, `AAPL`) |
| **Logo** | The AMI hex logo doesn't flip (it's not directional) |
| **Charts** | Chart libraries (ECharts, fl_chart) configured with `direction: rtl` — x-axis flips, but the visualisation reads correctly |

### Icons that DO mirror in RTL

- Arrow icons (`→` becomes `←`)
- Back navigation chevron
- Sliders / progress bars (left-to-right becomes right-to-left)
- Time-axis progressions (older-on-left becomes older-on-right)

### Icons that DON'T mirror

- Hex logo
- Hex avatars
- Brand glyphs
- Charts (already handled via library config)

### Typography in Arabic

Use **IBM Plex Sans Arabic** for body text. Inter remains for English/Latin mixed-runs (it has good Arabic support via Inter Arabic for v1.0, but Plex looks better at body-text size).

JetBrains Mono has Arabic numerals support — keep using it for numbers. For Arabic *text* labels, switch to IBM Plex Sans Arabic with `letter-spacing: 0` (no Latin tracking — Arabic doesn't need it).

### Testing RTL

Manual test pass at v1.0:

1. Switch device locale to `ar-SA`
2. Walk through every screen
3. Check:
   - All text labels readable (right-aligned, in IBM Plex Sans Arabic)
   - All padding/margin reads correctly
   - All icons mirror appropriately
   - All numbers stay LTR
   - Hexagons visible and properly tessellated
4. Check chart libraries — fl_chart and ECharts both need `--rtl` flags

### RTL gotchas to watch

- Third-party chart libraries that don't fully support RTL
- Animations that move "left-to-right" — must mirror in RTL
- Decision Journal transcripts: agent role labels (`[BEAR]`) should stay LTR (they're code-like); narrative content should be RTL

## Cross-references

- AMI design system source: `/Volumes/Extreme Pro/AMI AI Design System/`
- Implementation: [`ami_hex_in_flutter.md`](ami_hex_in_flutter.md)
- i18n architecture: [`docs/initial_specs/07_localization/i18n_architecture.md`](../07_localization/i18n_architecture.md)
