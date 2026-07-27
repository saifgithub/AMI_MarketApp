# Paywall Axes

The complete table of what's free, what's paid, and at which tier.

25 axes considered. Verdict and tier per axis.

## The full table

| # | Axis | Floor Pass | Trader | Floor Manager | Notes |
|---|---|---|---|---|---|
| 1 | **Smarter AI** | Cheap models | Mid models | Premium models | Biggest cost lever AND quality lever |
| 2 | **Agent unlock speed** | Earn Path | Skip Path | Skip Path | Dual-gating model |
| 3 | **Full Rooms / month** | 1 free + buy via credits | 10 included + credits | 20 included + credits | Rooms are most LLM-expensive |
| 4 | **1-on-1 chats / month** | 5 free + credits | Unlimited (via credit allowance) | Unlimited | |
| 5 | **Debate rounds in Room** | 1 | 1 | Up to 3 | Floor Manager differentiator |
| 6 | **Market data freshness** | 15-min delayed | 15-min delayed | Real-time (v1.1+) | Sim product — real-time isn't critical |
| 7 | **Sim capital & portfolios** | 1 / $10K / monthly reset | 2 / $100K / on-demand reset | 5 / $1M / on-demand reset | |
| 8 | **Decision Journal history** | 30 days | Unlimited + search + tag | Unlimited + search + tag + export | |
| 9 | **Brief Your Agent edits** | 3 per agent lifetime | Unlimited, 20-version history | Unlimited, infinite history, Raw Mode | |
| 10 | **Concierge basic** | Free unlimited | Free unlimited | Free unlimited | Navigation layer — never paywall |
| 10b | **Concierge assistant tools** | None | Schedule, reminders, summarise, mute | Same as Trader | Personal-assistant features |
| 11 | **Voice TTS briefings** | Text only | Text + voice | Text + premium voice + analyst commentary | TTS provider cost |
| 12 | **Mandate complexity** | Full (basic + advanced) | Full | Full | **Never gated** — mandate is identity |
| 13 | **Mandate edit history** | Last 5 versions | Last 20 | Unlimited | Edits free for all; deep history paid |
| 14 | **Languages** | All available | All available | All available | **Never gated** — equity / strategic |
| 15 | **Daily challenges + streaks** | Free unlimited | Free unlimited | Free unlimited | Retention loop — never gate |
| 16 | **Trading Fundamentals lessons** | All free | All free | All free | Education is the product's heart |
| 17 | **Agent Academy** | All free | All free | All free | Earn Path depends on it |
| 18 | **Mandate Drift Alerts** | Weekly digest (email) | Daily (push + email) | Real-time + tunable | |
| 19 | **Halal / Sharia screening** | Always free | Same | Same | **Never gate** — positioning + ethics |
| 20 | **Replay-as-case-study** (Phase 2) | View community replays | Convert past Rooms to replay challenges | Same as Trader | Phase 2 |
| 21 | **Reasoning-quality leaderboard** (Phase 2) | View | Eligible | Eligible + verified badge | Phase 2 |
| 22 | **Per-agent performance review** (Phase 2) | Aggregate only | Per-agent scorecards + mute/promote | Same as Trader + 1-on-1 reviews | Phase 2 |
| 23 | **Customer support** | Concierge | + standard email | + priority 24h human | Light touch |
| 24 | **Cosmetic themes** (Phase 2) | Default | Default + 2 alt | All palettes + custom | Phase 2 |
| 25 | **Live News/Social Analyst data feed** | Credit surcharge per live feed; else loud "paid feature" disclosure + honest synthetic fallback | Same surcharge | Same surcharge | CR090 — metered by **credits, not a tier lock** |

### Axis #25 — Live News/Social Analyst data feed (CR090)

The News Analyst's Alpha Vantage NEWS_SENTIMENT feed (CR023) and the Social Media
Analyst's Adanos Reddit feed (CR024) cost real money per call. CR090 meters them:

- **Surcharge, not a tier lock (decided live, Saiful 2026-07-25):** a Room turn that
  actually fires a live feed with real data adds **+2 credits per live feed**
  (`LIVE_DATA_SURCHARGE`, beside `ROOM_COST_BASIC`). Basic Room with both feeds live =
  8 + 2 + 2 = 12. The base Room price is untouched — the surcharge stacks.
- **Entitlement is the credit balance, not the plan.** Any plan can buy live feeds if
  the balance covers `base + surcharge`; short on credits ⇒ the feeds are withheld and
  the run proceeds on the honest synthetic fallback. No flat Floor-Pass block.
- **All-or-nothing on the live bundle** — a run buys both live feeds or neither, so the
  price never depends on an unpredictable per-feed tie-break.
- **Degrade loudly (CR040/DEF059).** Withheld ≠ unavailable. A `withheld_paid` feed
  emits a **structural** `live_data_notice` event (model out of the loop) so the client
  can say "this agent's live feed is a paid feature," never a silent synthetic
  substitution. `unavailable` (no data exists) keeps the CR023/CR024 illustrative
  fallback byte-for-byte. Only `live` costs credits.
- **Free-tier sanctity untouched:** the surcharge is a power-feature meter (operations
  volume), not a gate on mandate, halal screening, or education.

## Free-tier sanctity

Three things must remain free **forever**, regardless of how desperate we are for revenue:

1. **Mandate complexity** — Mandate is the user's identity in the product. Gating it would dilute the AI-first promise and feel mean.
2. **Halal/Sharia screening** — Charging Muslim users to invest halal in AR/MS markets would be a positioning disaster and arguably ethically dubious.
3. **Lessons + Daily Challenges + Agent Academy** — Education must be free. The Earn Path depends on it. Gating learning destroys the user-trust we're building.

If we ever consider charging for these, treat it as a brand emergency, not a pricing experiment.

## Free-tier honesty

A Floor Pass user — fully free, no card on file — must be able to:
- Learn anything in the curriculum
- Complete all 12 Agent Academy modules (Earn Path)
- Use all 12 agents (after Earn Path)
- Run at least 1 Room per month
- Run at least 5 1-on-1s per month
- Edit their mandate freely
- View their Decision Journal (last 30 days)
- Set up daily challenges and streaks

The friction is **operations volume** + **ads** + **caps on power features** (Coach, Journal history). Not access.

This honesty is brand-positive. Users who *could* fully use the free tier sometimes pay anyway, out of respect for the value. That's a healthier funnel than one that traps users with artificial scarcity.

## Cross-references

- Detailed per-tier feature table: [`tiers_and_pricing.md`](tiers_and_pricing.md)
- Credit economics behind operations volume: [`credits.md`](credits.md)
- Ads on Floor Pass: [`ads.md`](ads.md)
- Why education must be free (rationale): [`docs/initial_specs/04_education/dual_gating.md`](../04_education/dual_gating.md)
