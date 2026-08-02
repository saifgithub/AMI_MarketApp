# CR136 — Screen designs (Portfolio Health)

**Status:** design, 2026-08-02 (AT:R65) · **Additive only.** This file adds the
screen layer CR136 never specified. It changes **no** existing spec — not the
math, sufficiency contract, estimator pins, uncertainty contract, rule engine,
prompt contract, or journal plan. Where it names a behaviour, it is restating a
decision already made in `CR136_portfolio_health_metrics.md`, not making a new
one.

Visual reference (mockups of every screen and state):
`https://claude.ai/code/artifact/fa495a04-980f-4928-9df5-7737af9b52be`

---

## Why this file exists

CR136 scope item 6 named a "Portfolio Health card" and listed which metrics it
carries. It specified no layout, no state matrix, no Finding screen, and no
journal rendering. The Finding spec (§F1–§F5) describes *content* and *register*
but not *surface*. A builder picking up CR136 today would have to invent the
screens, and the states most likely to be invented wrongly are exactly the ones
the CR spent two audit rounds protecting — insufficient, partial, and refusal.

## Sources this design obeys

| Source | What it fixes |
|---|---|
| `mobile/lib/theme/ami_theme.dart` | **Authoritative tokens.** `AmiColors`, `AmiTypography`, `AmiSpacing`, `AmiRadii`, `AmiMotion` |
| `docs/initial_specs/05_design/data_viz_and_meters.md` | Encoding vocabulary, honesty rules, surface shapes, chart voice |
| `mobile/lib/widgets/sharia_verdict_banner.dart:9-23` | The app's status-colour semantics |
| `CR136_portfolio_health_metrics.md` | Content, register split, hostile-reader standard, states |

**Two stale-doc corrections, recorded so the next reader does not re-derive them:**

1. `05_design/colors_motion_rtl.md` and `ami_hex_in_flutter.md` name **Inter /
   JetBrains Mono**. The app ships **IBM Plex Sans / IBM Plex Mono** via
   `google_fonts` (`ami_theme.dart:152-155`); Inter and JetBrains are bundled
   only as cold-launch fallbacks. Design against IBM Plex.
2. `ami_hex_in_flutter.md:12-98` lists several stale hex values (`slate800`,
   `hexPurple`, `textHigh`). `ami_theme.dart` wins.

---

## Surface inventory

| Id | Surface | Host | Status |
|---|---|---|---|
| **07a** | Portfolio Health card | Screen 07 Sim Portfolio, after `_SectorAllocationSection()` (`portfolio_screen.dart:680`) | new |
| **07b** | Card states — insufficient / partial / refusal / empty / loading | same | new |
| **21** | The Finding (full analysis) | new detail screen, pushed from 07a | new |
| **17+** | Stored Finding in the journal | `journal_detail_screen.dart` new branch | new branch on existing screen |

---

## 07a — Portfolio Health card

**Shape.** `AccentCard(accent: AmiColors.hexBlue)` (`accent_card.dart:16`) —
slate800 fill, 1px slate700 border, `AmiRadii.card` (8), 2px accent top stripe.
No shadow; shipped cards are flat. Content surfaces are rounded rects, never hex
(`data_viz §4.0`).

**Accent is `hexBlue`, deliberately not `hexAmber`.** Amber already means
mandate-violation / warning app-wide. A risk *measurement* is not a violation;
tinting it amber fires an existing signal falsely and devalues it. `hexBlue`
carries no agent-family identity, so it also cannot collide with the
family-colour rule (`data_viz §1`).

**Contents, top to bottom:**

1. Title `Portfolio Health` (`AmiTypography.h4`-class) + a `labelMono` subtitle
   carrying **window and basis** — `126 TRADING DAYS · HOLDINGS-BASED`.
2. A 2×2 tile grid: **Volatility** (with benchmark alongside), **Beta** (with
   R²), **Effective bets** (with raw holding count), **Max drawdown** (with its
   window). Each tile = `labelMono` label, mono value, and a **unit line** —
   never a bare percentage (`data_viz §4.1`).
3. **Risk vs money**, top 3 contributors — the signature visual, below.
4. Legend, then a mono caption stating what the figure is **not**.
5. `HexButton` CTA → the Finding. Rounded rect, not clipped (CR113).

### The signature visual — risk share vs money share

Two bars per holding, same scale, same origin, stacked:

- **Solid bar** = share of portfolio **risk**
- **Outlined bar** = share of portfolio **money** (weight)

The divergence between them is the insight. NVDA at 62% of risk on 30% of the
money is legible before a word is read, and it is the concept CR136 identified
as the feature's highest teaching value.

Why this encoding survives the design system:

- **Length** (rank 6) carries magnitude, drawn to scale — legal.
- **Fill-vs-outline** (rank 5) carries the risk/money *kind* distinction —
  the sanctioned channel for a binary kind difference.
- It uses **no opacity ramp and no size encoding** — both *forbidden for data*
  (`data_viz §2`).
- One hue, two treatments — so no holding is ever tinted with a family colour
  it does not own.

**No painter required.** Reuse either shipped pattern: `_ClosedTradeSummary`
(`portfolio_screen.dart:1483-1501`, `ClipRRect > SizedBox(height:6) > Row` of
`Expanded(flex:) > ColoredBox`) or the `FractionallySizedBox` underline bar
(`room_board.dart:997-1007`).

**Caption, mandatory:** "Shares of total portfolio risk, cash included. Not a
forecast and not a return." — a caption states what the figure shows *and what
it does not* (`data_viz §9`).

---

## 07b — The states that are not a result

`data_viz §3.6`: *an error state must not be shaped like a result.* Every
non-populated state therefore **drops the accent top-stripe, drops the tile
grid, and uses a dashed container** — structurally unmistakable, not a
greyed-out twin of the populated card.

`data_viz §3.3`: *missing is a fourth state, not a middle value.* No zero, no
50%, no placeholder dash inside a tile. The tile is **absent** and the reason is
named.

| State | Trigger | Treatment | Colour |
|---|---|---|---|
| **Insufficient** | Tier-1 block `sufficient: false` | Dashed container, `⬡` glyph, names the shortfall in real numbers ("needs 126 trading days; your oldest holding has 47") | **Neutral slate** |
| **Partial** | `partial: true` | Populated card **plus** an inline `Partial` chip, excluded tickers named, covered fraction of invested value stated | **Amber** |
| **Refusal** | `use_real_market_data = false` | Dashed container, states what AMI *will not* do | **Amber** |
| **Empty** | No holdings | `AmiEmptyState` (`empty_state.dart:11`) | **Neutral slate** |
| **Loading** | Request in flight | `HexPulseLoader` inside the half-alpha container from `_ChartNotice` (`ticker_chart.dart:238-301`) | `hexCyan` |

**Colour semantics are fixed by the app, not chosen here.**
`sharia_verdict_banner.dart:9-23`: neutral slate = *unknown / absence of a
ruling*; amber = *a real exclusion, or system unavailable*; red = *negative P&L
or mandate violation*.

- Insufficient history is an **absence**, so it must not borrow the warning
  colour → neutral slate.
- The mock-data refusal is **system unavailable** → amber.
  *Corrected during design: this panel was drawn red first, which would have
  fired the mandate-violation signal for an infrastructure condition.*
- Partial is a **real exclusion** of holdings → amber.

---

## 21 — The Finding

A new detail screen, `Navigator.push(MaterialPageRoute<void>(...))` from the
card CTA — the app has no named routes for detail screens (`app.dart:55-59`).
Structure follows `RoomBoard`: a plain `Column` of sections separated by
`AmiSpacing.m`, with the **host screen owning the scroll**.

Sections are labelled with the spec's own ids — `F1 · Headlines` …
`F5 · Recommendations` — so a reviewer's objection maps to a section without
translation. Section header token: `labelMono@10` in `hexBlue`
(`room_transcript_rows.dart:179-183`).

### The register split, made structural

CR136 requires plain language in F1/F2/F5 and a technical register in F3, and
that *"neither register leaks into the other."* Type alone will not hold that
line under editing pressure, so **F3 gets a different container**: a recessed
`slate900` ledger with a mono key/value grid, visually a different document
class from the prose cards around it. The user reads prose; the portfolio
manager reads a ledger; one scroll serves both.

**F3 uses a KV grid, not a markdown table.** The shared `agentMarkdownStyle()`
(`room_board.dart:1198`) defines no `tableHead`, `tableBody`, `blockquote` or
`h4` — those fall back to Material defaults, i.e. not IBM Plex and not AMI ink.
Build F3 rows from `BoardMetricRow` (`room_board.dart:497`, already public). If
markdown tables are ever wanted, the stylesheet must be extended first.

**Per-metric F3 block carries:** value, standard error, observations, window,
method + citation — the four things a professional checks before deciding
whether to keep reading.

**Disclosures** sit at the foot in mono, always present, never conditional:
simulation-only, gross-of-fees, shrinkage estimator, window + Gaussian SE
caveat. A reader cannot reach the end and discover an unstated limitation.

**Recommendations** show their trigger values inside the sentence and name their
`based_on` metric ids beneath — the answer to "where does this come from?" is on
the same line.

---

## 17+ — Journal rendering

The stored Finding renders with the **same section widget** as Screen 21 — one
component, two hosts — and renders the **stored** sections, never a live
recompute, so an archived report always reads as it did when filed.

**The trap, and it is already live.** `journal.dart:103-104` coerces an unknown
wire `entry_type` to `oneOnOne`. That branch reads `user_message` /
`assistant_reply`, both null for a Finding, so the payload renders as **nothing
at all** — a blank gap. The generic `else` fallback at
`journal_detail_screen.dart:358` is **unreachable** for a new type and cannot
save it. This is not hypothetical: the backend has nine entry types and Dart has
eight, so `daily_challenge` entries render blank in the journal today.

Required, in one change:

1. `journal.dart` — add the enum value **and** the `fromWire` case.
2. `journal_detail_screen.dart` — an `else if` before `:358` that
   early-returns a dedicated widget, following the `roomRun` precedent
   (`:339-357`).
3. Three exhaustive switches will fail to compile until updated —
   `journal.dart:16` (`wire`), `journal_screen.dart:429` (`_accent`), `:450`
   (`_label`). Take that compile error as the checklist.

Per `_RecordActions` (`journal_detail_screen.dart:454-500`) and its T-STALE
rule: a Finding is a **record**. No trade ticket from it, ever.

---

## Motion

`data_viz §7`: the card and the Finding appear with **one short opacity fade of
the whole figure** (`AmiMotion.fast`, `AmiMotion.easeOut`). Bars must not grow
from zero, numbers must not count up — an orchestrated assembly implies live
computation that is not happening. `MediaQuery.disableAnimations` removes the
fade entirely.

Note this differs from the existing `_ValueCard` count-up
(`portfolio_screen.dart:296-303`), which predates the rule. Do not copy it here.

## RTL

Every mono numeric run needs bidi isolation — `_isolateNumeric()`
(`portfolio_screen.dart:60`) wraps with `⁦…⁩`. Use
`EdgeInsetsDirectional` and `Row`, never `Stack` with hard-coded `Alignment`,
which fails silently under mirroring (`data_viz §5`). The risk/money bars are
locked `TextDirection.ltr` like the magnitude ribbon.

## Strings

All copy above is new UI text and **must be flagged for AR + MS translation**
before v1.0. Keys follow the app's existing convention
(`portfolioHealthTitle`, `portfolioHealthInsufficientTitle`,
`portfolioHealthInsufficientBody`, `portfolioHealthPartialChip`,
`portfolioHealthMockRefusalTitle`, `findingSectionF1`…`F5`, plus the five rule
templates). Numbers, tickers and window dates interpolate as **placeholders** —
never baked into a translated sentence. `mobile/test/l10n_key_parity_test.dart`
requires `app_en.arb` + `app_ar.arb` + `app_ms.arb` parity.

## Acceptance additions (screen layer only)

- Each of the five card states renders from a fixture and is golden-tested;
  the insufficient and refusal states assert **no numeric glyph** is present.
- The risk/money bars assert `width` proportional to the value, and that risk
  and money bars for the same holding share an origin and scale.
- A `sufficient: false` metric asserts **no tile** is rendered for it — not a
  tile containing a dash.
- A journal entry of the new type renders its five sections; a golden pins that
  it is **not** an empty block.
- `flutter analyze` clean; l10n parity green across en/ar/ms.

---

## Rev 2 (build-final) amendments — 2026-08-02, integrates Rev 4 of the CR

The sections above are kept as written (audit trail). The following
amendments **supersede** them where they conflict; they carry the measured
F9/F19/F20 fixes and the Rev 4 decisions. M09 builds from the base doc PLUS
this section.

1. **Bar-chart basis (supersedes the §07a caption).** Both bars are
   **invested-sleeve**: solid = Euler risk share, outlined = invested money
   share `wᵢ/(1−cash)`. Measured rationale: on the total basis the headline
   gap widens purely with cash (+29.3pp → +59.3pp across 0→60% cash for an
   identical sleeve) — a cash artefact read as a statement about the holding.
   On the invested basis the gap is exactly cash-invariant. Risk shares are
   numerically identical on either basis (verified to 3e-16), so no
   recomputation. **New mandatory caption:** "Shares of invested risk and
   invested money; cash is shown on its own line. Not a forecast and not a
   return." Cash gets its own line beneath the bars (weight only, no risk
   bar — its risk share is exactly 0).
2. **Bar-chart edge cases (new, must be defined before build):**
   - **Negative risk share** (a diversifier/hedge — measured −7.04% on a
     plausible long-only book): draw from the shared origin leftward into a
     reserved negative gutter, same solid treatment, caption note "a negative
     share means this holding offset risk over the window."
   - **Share > 100%** (measured 126.9% on a hedged two-name book): the axis
     extends to the max share; the axis end-label shows the actual maximum —
     never clamp or truncate a drawn-to-scale bar (`data_viz §2`).
   - **Invested value = 0** (100% cash): the bar block is absent entirely;
     the card shows the cash line + the empty state — never 0/0.
3. **Weight-concentration tile**: computed on the **invested sleeve** and
   labelled "INVESTED WEIGHT CONCENTRATION" (total-value HHI is non-monotone
   in cash — measured eff-N 2.63→3.53→3.37→2.38 across 0/20/40/60% cash).
   When `contains_etfs`, the tile carries the fixed ETF-overlap disclosure
   chip ("ETF overlap not counted").
4. **Disclosures move to the HEAD (supersedes §21's foot placement).** The
   Finding's disclosure block renders first, before §F1, and is stored in the
   journal payload: `disclaimerShort`, gross-of-fees + zero-cost sim,
   backcast line, window + estimator line, non-stationarity caveat. The foot
   may repeat them; the head placement is the requirement (F19 — "limitations
   are disclosed before the reader finds them").
5. **Estimator wording in any UI copy**: the window subtitle becomes
   "≈66-DAY EFFECTIVE WINDOW · HOLDINGS-BASED" (EWMA λ=0.97; the rectangular
   "126 TRADING DAYS" claim no longer describes the estimator). The 126
   figure remains only in sufficiency copy ("needs 126 trading days of
   history").
6. **§F5 rename + speech act**: section title is **"What the numbers point
   to"** (was "Actionable recommendations"). Templates are
   conditional-educational — no imperatives on the user's tickers, no
   severity bands. String keys change accordingly
   (`findingSectionF5` label text; rule templates per Rev 4's table —
   R0/R2b added, R1/R3/R4 reworded).
7. **Plain-language R²**: §F1/§F2/§F5 never show "R²" — the flag renders as
   "the market explains only {x}% of this book's day-to-day moves". "R²"
   appears only inside the §F3 ledger.
8. **Insufficient-state copy names OUR limit when that is the cause** (F20):
   "price history available to AMI's engine covers {n} days; 126 needed" —
   never "your oldest holding has {n} days" when the fetch depth is the
   binding constraint.
9. **Gate CTA states (new — Access gating, Rev 4)**: the card footer carries
   the Finding entry point in one of: generate (available) / trial chip
   ("{k} of {n} trial findings left" or "{d} days left") / daily-cap state /
   upgrade state (plan-gated). Tiles themselves are never gated. Shapes come
   from M07's gate-status payload.
10. **Golden-test note**: the base doc's golden-test acceptance stands, with
    the three new edge-case fixtures (negative share, >100% share, 100%
    cash) added to the five card states.
