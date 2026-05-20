# Information Architecture

5-tab navigation, persistent header, persistent FAB, and the full screen map.

## Bottom navigation (5 tabs)

| Order | Tab | Hex icon | Purpose |
|---|---|---|---|
| 1 | **Floor** | ⬢ Hex avatar mesh | Home — today's briefing + 12-agent honeycomb |
| 2 | **Sim** | ⬢ Chart spark | Sim portfolio + trade ticket |
| 3 | **Convene** | ⬢ Two-hex collision | Recent Room sessions + quick-start |
| 4 | **Academy** | ⬢ Book + node | Trading Fundamentals + Agent Academy + Daily Challenge |
| 5 | **Journal** | ⬢ Timeline glyph | Decision Journal |

Active state: hex-clipped solid fill in hex-blue. Inactive: outlined slate-700.

## Persistent global UI

| Element | Position | Behaviour |
|---|---|---|
| **AMI Trade hex logo** | Top-left header (64px) | Tap → about / version / privacy. |
| **Concierge pill** "Ask anything…" | Top-center header | Always accessible. Tap → full-screen Concierge thread. Pink-accented when Concierge has a pending message. |
| **Mandate + credits badge** | Top-right header | Hex chip showing current drawdown vs cap (color-coded) + credit balance. Tap → My Mandate / Wallet menu. |
| **⬢ Convene FAB** | Bottom-right, floats above tab bar | One-tap start a Room. Long-press → 1-on-1 picker. Hex-blue glow. |

Header height: **64px fixed**, never scrolls. Glass-chrome background (`rgba(15,23,42,0.85)` + blur).

## Full screen inventory

```
APP
├── Onboarding (first-run only)
│   ├── 01_splash
│   └── 02_concierge_conversation        (~3 min)
│       └── 02b_account_claim
├── Floor (tab 1)
│   └── 03_floor_home_honeycomb
│       ├── (long-press hex) → 04_one_on_one_bottom_sheet
│       └── (tap hex) → 05_agent_profile
│           ├── overview tab
│           ├── past_calls tab
│           ├── performance tab           (Phase 2)
│           └── coach tab → 06_coach_session
├── Sim (tab 2)
│   ├── 07_sim_portfolio
│   │   └── (tap holding) → 08_position_detail
│   └── 09_trade_ticket
├── Convene (tab 3)
│   ├── 10_convene_quickstart
│   └── 11_convene_the_room              (the showpiece — live debate)
├── Academy (tab 4)
│   ├── 12_academy_hub                   (Fundamentals + Agent Academy + Daily Challenge tiles)
│   ├── 13_lesson_player
│   ├── 14_agent_academy_module
│   └── 15_daily_challenge
├── Journal (tab 5)
│   ├── 16_journal_index
│   └── 17_journal_transcript
├── Settings (accessed from header badge or Concierge)
│   ├── 18_my_mandate
│   ├── 19_wallet_and_plan
│   └── 20_about_and_legal
└── Modal: Concierge full-screen          (from header pill, any time)
```

That's the 20-screen MVP IA. Below are summaries — see [`screen_inventory.md`](screen_inventory.md) for the full per-screen spec.

## Tab-bar UX details

- **Bottom navigation height**: 80px (52px tab strip + 28px safe area on notched phones).
- **Tab icons** are SVG, rendered at 28×28 inside the tab cell.
- **Active label** appears below the icon in JetBrains Mono UPPERCASE 10pt; inactive label hidden to save space.
- **Tap on already-active tab**: scroll to top, then second tap navigates to root of that tab.
- **Long-press on a tab**: tab-specific quick actions (e.g., Floor long-press → "View all agents" / "Switch active mandate" Phase 2).

## Concierge persistence

Concierge is a **single persistent thread per user**, never session-scoped. When the user taps the header pill, they re-enter the same conversation they had yesterday.

- Local state: last 50 messages cached locally for instant open
- Server state: full thread persisted, paginated on scroll-up
- Concierge can refer to past conversations: *"Like we discussed last Tuesday..."*

## Modals & sheets

| Type | When to use |
|---|---|
| **Bottom sheet (50–80% height)** | Quick 1-on-1 chat (from Floor long-press), trade ticket inline review, mandate field edits |
| **Full-screen modal** | Concierge full thread, Brief Your Agent session, Convene the Room |
| **Toast (auto-dismiss 3s)** | Confirmations: "Saved", "Streak +1", "Credits added" |
| **Dialog (system-style)** | Destructive actions only: cancel subscription, delete mandate, etc. |

No "snackbars" with action buttons — they're awkward on mobile. Use toasts + sheets.

## Navigation transitions

Per AMI motion spec — minimal and functional:
- **Tab change**: instant (no animation; tabs are siblings)
- **Push onto a tab stack** (e.g., agent profile from Floor): slide from right (LTR) / left (RTL)
- **Modal up**: slide from bottom
- **Bottom sheet**: rise from bottom with spring damp
- **Back swipe**: edge-swipe on iOS; system back on Android

No parallax. No bouncy spring physics. AMI brand calls for "minimal and functional" motion.

## Header behaviour per tab

| Tab | Header content |
|---|---|
| Floor | Logo · Concierge pill · Mandate badge |
| Sim | Logo · "$10,234.50 +1.2%" stat · Mandate badge |
| Convene | Logo · "Last Room: 2h ago" · Mandate badge |
| Academy | Logo · "150 lessons · Day 12 🔥" · Mandate badge |
| Journal | Logo · "47 entries" · Mandate badge |

The mandate badge stays in the same place across tabs — predictable.

## Empty states

Every screen has a Concierge-narrated empty state:

| Screen | Empty state Concierge message |
|---|---|
| Floor (0 agents unlocked) | "Welcome to the floor. Complete an Academy module to meet your first analyst." |
| Sim (no positions) | "Empty portfolio. Want to convene the Room on a watchlist ticker, or paper-trade something?" |
| Convene (no past sessions) | "Your first Room session will appear here. Tap the FAB to start." |
| Academy | "Pick a track to begin." (always populated — never truly empty) |
| Journal | "Nothing logged yet. Every Room, 1-on-1, and trade lands here." |

## Cross-references

- The Floor home screen: [`floor_home_honeycomb.md`](floor_home_honeycomb.md)
- Every screen in detail: [`screen_inventory.md`](screen_inventory.md)
- Hex widget implementations: [`ami_hex_in_flutter.md`](ami_hex_in_flutter.md)
- RTL handling: [`colors_motion_rtl.md`](colors_motion_rtl.md)
