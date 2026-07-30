# Claim register — what marketing may say, and on whose authority

Every number and capability claim in `marketing/` traces to a row here. A figure without a row
is either sourced or deleted. This exists because the repo already learned the lesson twice in
code — DEF059 (a confident fake APPROVE when the LLM was down) and DEF084/DEF094 (a two-state
answer to a four-state question) — and marketing copy can re-break either one without touching
a line of code.

**Measured:** 2026-07-29 / 2026-07-30, against Alpha (`melehost`) and `main` @ `51c24018`.
Numbers move. Re-measure before any external use more than ~30 days after that date, or label
the figure with its measurement date in the asset itself.

## Status vocabulary

| Status | Meaning | Usable in external copy? |
|---|---|---|
| `VERIFIED` | Measured, source named, date named | Yes, with the date if it's a moving number |
| `NEWLY CLAIMABLE` | Shipped and client-visible, but our own public copy currently denies or omits it | Yes — and the site needs correcting |
| `PROJECTED` | A model, not a measurement. From the spec's own illustrative math | Only when labelled as a projection |
| `FORBIDDEN` | Must not be claimed | No |

Two house rules from `CLAUDE.md` apply to everything below:

- **User-facing copy says "AMI", never "the AI".** Internal docs may say LLM.
- **No extrapolated numbers.** Measured and cited, or explicitly labelled.

---

## VERIFIED — build substance

| # | Claim | Value | Source |
|---|---|---|---|
| V1 | Commits on `main` | 1,406 | `git rev-list --count main`, 2026-07-29 |
| V2 | Current build | `0.1.0+59`, on TestFlight **and** Play internal testing | `mobile/pubspec.yaml`; commit `73a25c7f` |
| V3 | Lessons | **342 lessons**, each in EN + AR + MS (1,026 `.mdx` files) | `content/lessons/`, file count 2026-07-29 |
| V4 | Agents | **13** — 12 analyst-team agents + the Concierge | `docs/initial_specs/02_agents/twelve_agents.md` |
| V5 | Agent roster (exact display names) | Fundamentals Analyst, Market Analyst, News Analyst, Social Media Analyst, Bull Researcher, Bear Researcher, Research Manager, Trader, Aggressive Debator, Conservative Debator, Neutral Debator, Portfolio Manager, + AI Concierge | same |
| V6 | Room debates run | 960 total, **938 completed** | `ami_trade.room_runs`, 2026-07-29 |
| V7 | Room completion rate | **97.7%** (938/960) | derived from V6 |
| V8 | Backend unit tests | 1,269 passing | `DEF094.row.md` re-verify note, AT:R65 |
| V9 | Languages shipped | EN, AR (full RTL), MS — 311/311 and 310/311 ARB keys | `mobile/lib/l10n/`, AT:R35 |
| V10 | Market data | Real Yahoo prices via `yfinance`, **15-minute delayed** | `USE_REAL_MARKET_DATA=true` on Alpha |
| V11 | Glossary + coach content | 188 glossary terms, 280 AI-Coach Q&A, 183 daily challenges | `project_plan.md` snapshot |

**V6/V7 carry a mandatory caveat wherever used:** 750 of the 960 runs are the CR035 benchmark
(5 synthetic accounts × 150 tickers). Real usage is **~210 runs across ~37 accounts**, and
nearly all of those accounts are Saiful's own devices plus the Hermes UAT rig. V7's completion
rate is a *reliability* claim and is sound — the benchmark exercised the same code path. It is
**not** a usage or traction claim, and must never be presented as one.

---

## VERIFIED — traction, stated honestly

The whole point of this block is that it is the part a reader will check.

| # | Claim | Value | Source |
|---|---|---|---|
| T1 | Revenue to date | **USD 0. No payment has ever processed.** | `ami_trade.revenuecat_events` = 0 rows |
| T2 | Waitlist signups | **0**, all time, on a live public site | `ami_website.waitlist` |
| T3 | User rows | 119 (10 with an email, 109 anonymous) | `ami_trade.users` |
| T4 | Real external users | **Effectively zero.** Cannot be stated more precisely — see below | derived |
| T5 | Store status | Closed testing only: TestFlight + Play internal. No public listing. | `docs/WEBSITE.md` open items |
| T6 | Other measured activity | 1,171 journal entries · 24 sim trades · 71 one-on-one messages · 178 lesson-progress rows · 13 mandates · 82 bug reports | `ami_trade`, 2026-07-29 |

**On T4.** We cannot produce a real-user count, and no asset may imply one. `users` rows are
created anonymously on first launch, so the 119 conflates Saiful's devices, the Appium/Hermes
UAT rig, the CR035 benchmark accounts, and any genuine tester. The honest external phrasing is
**"closed alpha; no public launch yet"** — nothing numeric.

**On T1.** State it plainly in investor material rather than omitting it. Omission is the
version that costs trust when diligence finds it, and it will.

---

## NEWLY CLAIMABLE — shipped, and our own copy is behind

| # | Claim | Value | Source |
|---|---|---|---|
| N1 | **Halal / Sharia screening is live and reaches the client** | `SHARIA_SCREEN_ENABLED=true` on Alpha. **AAOIFI** standard. **216 compliant of a 503-name parent index** (S&P 500), as-of **2026-07-28**. Sources: SP Funds SPUS holdings + the S&P 500 constituents list. | Alpha env; `ami_trade.sharia_universe_snapshots` |
| N2 | Per-ticker verdict carries its own as-of date | Yes — shown per verdict, deliberately not in the Settings subtitle | `DEF094.row.md` |
| N3 | Ethical-exclusion mandate flags are live | `no_fossil_fuels`, `no_tobacco_alcohol`, + one more — DEF112 fixed the same never-serialized gap | `DEF112.row.md` |
| N4 | Social Media Analyst runs on real social sentiment | Adanos source configured, 162 rows cached | Alpha env; `social_sentiment_cache` |
| N5 | Leagues and reputation are live with real data | 6 leagues, 25 members, 215 reputation events | `ami_trade` |
| N6 | Portfolio Manager vetoes trades against the user's own mandate | Compliance pre-check on trade submit, verdict now serialized to the client | `DEF094.row.md`; `sim.py` |

### N1 has a hard guardrail — read this before writing any halal copy

`www.agenticmarketintel.ai` currently says Sharia screening is *"on the roadmap, not shipped."*
That is **stale** and understates the product's most defensible differentiator. Correcting it is
tracked in `users/assets/landing_page_changes.md`.

**But the screen has four states, not two, and `unknown` is a real state.** DEF094 exists
because a successful trade response carried nothing distinguishing a screened PASS from an
unscreened UNKNOWN — the user got silent permission on a ticker no scholar body has ruled on.
Marketing copy can recreate that defect in one sentence.

Permitted:

> "Screen your universe against an AAOIFI-based compliant list — 216 of the S&P 500 as of
> 28 July 2026 — with the as-of date on every verdict."

Forbidden:

- "All stocks screened for Sharia compliance" — the universe is the S&P 500, not all stocks.
- "AMI tells you if a stock is halal" — it reports a screen against a published list; it does
  not issue a religious ruling, and `legal_plan_ami_trade.md` escalates Sharia rulings to
  qualified scholars.
- Anything that lets `unknown` read as approval.
- Any AR/MS halal copy that has not been reviewed by a human. Observance-sensitive strings are
  explicitly excluded from machine translation (see `DEF094.row.md`) and this rule extends to
  marketing.

---

## PROJECTED — the spec's own model, never a measurement

All of this comes from [`docs/initial_specs/06_monetization/unit_economics.md`](../../docs/initial_specs/06_monetization/unit_economics.md),
which says of itself: *"These are illustrative — real numbers tighten post-launch with usage
data."* Usable only when labelled as a projection, and never in user-facing copy.

| # | Projection | Value |
|---|---|---|
| P1 | Trader-tier gross margin | ~$5.30/MAU (~46%) at 60% credit utilisation |
| P2 | Floor Manager gross margin | ~-$6.65/MAU year 1 — deliberately tight |
| P3 | Aggregate at 10,000 MAU | ~$40,400/mo revenue, ~45% gross margin, ~$485K/yr |
| P4 | Pricing | Floor Pass free (ads) · Trader $14.99/mo or $129/yr · Floor Manager $34.99/mo or $299/yr · credit packs $4.99 / $19.99 / $49.99 |
| P5 | Affordability | $14.99 is ~0.3% of average monthly post-tax income in the US, ~0.5% in Saudi Arabia, ~1.2% in Malaysia |

**P1–P3 are stale in our favour, and the correction must be given in both directions.** The
model prices Haiku/Sonnet/Opus through OpenRouter. Production runs **on-prem vLLM**
(`192.168.20.74:8000`, `ami-llm`) on hardware Saiful already owns, so today's marginal
inference cost is electricity — real gross margin is *better* than P1–P3 imply. It **inverts**
on the planned GCP Beta migration, which the backer agreement's own Schedule B puts at
**USD 750–2,550/month** and discloses as a live contingency. Any asset citing the cost advantage
cites the contingency in the same breath.

**P4 carries a live inconsistency:** the spec locks $14.99 / $34.99; the website says pricing is
"TBD, revealed at launch"; and the site's free-tier feature list (3 analysts per session, 5
Convene sessions/week) does not match the spec's (13 credits, 1 Room, 5 one-on-ones). No asset
may state a price until Saiful confirms which is current. Flagged in the user plan §11.

---

## FORBIDDEN — not claimable, at any volume of enthusiasm

### Not built

| # | Thing | Why not |
|---|---|---|
| F1 | **Morning / daily briefing** | A17 — never started, and **deliberately dropped** via CR115 on 2026-07-29. No scheduler, no sender, no TTS. `marketing/user_poc/so_what.md` describes it ("your analyst team has already done the work" when you open the app); that sentence must not reach a customer. |
| F2 | Voice / TTS briefings | A13/A14 blocked on a provider account |
| F3 | Push notifications | A15/A16 — no OneSignal/FCM anywhere in `mobile/lib` |
| F4 | Shareable P&L cards / any referral mechanic | `share_plus` is a dependency; no share feature is built |
| F5 | Badges | Table exists, **0 rows** |
| F6 | Credit-pack purchase | No purchase of any kind has ever completed (T1) |
| F7 | Real-time market data | 15-minute delayed (V10). Floor Manager real-time is v1.1+ |
| F8 | Huawei AppGallery | v1.1 |
| F9 | GCC / Tadawul / Bursa coverage | US equities only at MVP |
| F10 | Second news source | `ALPHA_VANTAGE_API_KEY` unset on Alpha — CR023's Yahoo half works, the second source is dark |
| F11 | Reasoning-quality leaderboard, public Room replays | Phase 2/3 |
| F12 | Crash reporting actually reporting | `sentry_flutter` is installed but `SENTRY_DSN` is empty on Alpha |

### Never claimable, regardless of what ships

Straight from `docs/initial_specs/09_compliance/` and the locked decisions in `CLAUDE.md`:

| # | Forbidden claim | Why |
|---|---|---|
| F13 | Any return, gain, performance or "beat the market" figure | Apple 3.2.2; `store_compliance.md` App Review tip 5 explicitly says no claims of returns in marketing materials |
| F14 | "Investment advice", "recommendations", "signals", "picks" | AMI is not licensed to give investment advice. Locked decision, permanent |
| F15 | Real money, brokerage, execution, or "start trading" | Simulation-only, forever. No brokerage integration ever |
| F16 | Guarantees of any kind | — |
| F17 | "The AI" / "our AI" in user-facing copy | `CLAUDE.md`: it is **AMI** by name anywhere a user reads |
| F18 | Any user, download or growth number | T4 — we do not have one |
| F19 | Comparative claims about a competitor's *quality* | Feature-comparison against Finelo is fine and sourced (`vs_finelo.md`); disparagement is not |

**Framing rule that outranks all of the above.** Every store listing, ad and page leads with
**education** and **simulation**. `store_compliance.md` is unambiguous that Apple review is
prickly about trading claims, and that the mitigation is to lead with education/simulation in
the name, subtitle, description, screenshots and metadata, with the disclaimer visible in at
least one screenshot. This is a review-survival requirement, not a tone preference.

---

## Where each block may be used

| Block | Investor assets | User assets | Public website |
|---|---|---|---|
| VERIFIED build substance | Yes | Yes | Yes |
| VERIFIED traction | **Yes — required** | No (T4: nothing numeric) | No |
| NEWLY CLAIMABLE | Yes | Yes, within N1's guardrail | Yes — and it needs correcting |
| PROJECTED | Yes, labelled | No | No |
| FORBIDDEN | No | No | No |

## Re-measurement commands

```bash
cd "/Volumes/Extreme Pro/AMI_MarketApp"
git rev-list --count main
find content/lessons -type f | wc -l          # ÷3 for lessons

ssh melehost "docker exec ami_postgres sh -lc 'psql -U \$POSTGRES_USER -d ami_trade -c \
  \"select (select count(*) from room_runs) runs, \
           (select count(*) from revenuecat_events) payments, \
           (select jsonb_array_length(compliant) from sharia_universe_snapshots \
             order by fetched_at desc limit 1) sharia_compliant;\"'"

ssh melehost "docker exec ami_postgres sh -lc 'psql -U \$POSTGRES_USER -d ami_website -tAc \
  \"select count(*) from waitlist;\"'"
```
