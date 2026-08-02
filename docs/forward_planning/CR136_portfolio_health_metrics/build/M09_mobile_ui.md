# CR136 build — M09: Mobile — Health card + Finding screen + gate states

> Conforms to CR136 Rev 4 + build/README.md. Where this doc and Rev 4 disagree, Rev 4 wins.

## 1. Purpose

The mobile surface layer: the Portfolio Health card on the Sim Portfolio screen
(SCREEN_DESIGNS 07a/07b), the signature risk-vs-money bars with Rev 4's F9
invested-sleeve basis + three pinned edge cases, the Finding detail screen
(SCREEN_DESIGNS 21), the API client for M07's frozen envelopes, and all new
l10n strings. Implements Rev 4 "Presentation surfaces" (§F1 tiles + entry
point) and the mobile row of "Access gating". SCREEN_DESIGNS' **Rev 2
(build-final) amendments are present** (SCREEN_DESIGNS.md:259-323) and govern
where the base doc conflicts. Colour semantics are the app's
(`sharia_verdict_banner.dart:9-23`): neutral slate = absence, amber = real
exclusion / system unavailable, red = negative P&L / mandate violation. Card
accent is `hexBlue`, **never amber** — amber = mandate violation app-wide.

## 2. Files

New (header one-liners stated):

| File | Header one-liner |
|---|---|
| `mobile/lib/models/portfolio_health.dart` | `/// CR136 M09 — wire models for GET /v1/portfolio/health (M04 envelope + M07 gate) and POST .../finding. Parses; never computes a metric.` |
| `mobile/lib/state/portfolio_health_providers.dart` | `/// CR136 M09 — providers for the Health card (free tiles GET) and Finding generation (gated POST; same-day POST is idempotent server-side).` |
| `mobile/lib/widgets/portfolio_health/health_card.dart` | `/// CR136 M09 — Portfolio Health card (SCREEN_DESIGNS 07a/07b): §F1 tiles, six states, gate CTA. hexBlue accent — a measurement is not a warning.` |
| `mobile/lib/widgets/portfolio_health/risk_money_bars.dart` | `/// CR136 M09 — risk vs money bars (solid = risk share, outlined = money share; both invested-sleeve, one scale, one origin). Pure geometry, painter-free.` |
| `mobile/lib/screens/sim/portfolio_health_finding_screen.dart` | `/// CR136 M09 — the Finding (SCREEN_DESIGNS 21): POSTs generation, renders the STORED head disclosure + §F1–§F5 via FindingSections. Never recomputes.` |
| `mobile/test/models/portfolio_health_test.dart` | `// CR136 M09 — envelope parsing: both nestings, gate keys, refusal shape.` |
| `mobile/test/widgets/portfolio_health_card_test.dart` | `// CR136 M09 — six card states, partial chip, tile absence, CTA states.` |
| `mobile/test/widgets/risk_money_bars_test.dart` | `// CR136 M09 — bar geometry + the three Rev 4 edge cases.` |
| `mobile/test/screens/portfolio_health_finding_screen_test.dart` | `// CR136 M09 — Finding order, section labels, F3 ledger, error panels.` |

Touched (anchors verified at HEAD 645de77c):

- `mobile/lib/services/api/api_client.dart` — two methods, `sectorAllocation`
  idiom (:929-934).
- `mobile/lib/screens/sim/portfolio_screen.dart` — one line: `const
  PortfolioHealthCard(),` directly after `const _SectorAllocationSection(),`
  (:680; the section class is at :747).
- `mobile/lib/widgets/journal/finding_sections.dart` (M08's widget —
  **additive only**, §3.6). M08's tests must stay green unmodified.
- `mobile/lib/l10n/app_en.arb` + `app_ar.arb` + `app_ms.arb` (§3.7;
  `mobile/test/l10n_key_parity_test.dart` fails on a missing locale).

## 3. Implementation spec

### 3.1 Wire models (`portfolio_health.dart`)

M07 §3.4/§3.5 are the frozen HTTP envelopes; inside them sits M04 §3.5's
engine payload (root `status` + accounting + `context` + `blocks`).

```dart
class HealthGateStatus {            // exactly M07 §3.2's 8 keys
  final String mode;                // "open" | "trial" | "plan"
  final bool trialActive, planHasAccess;
  final int trialFindingsUsed, trialFindingsBudget, trialDaysLeft,
      dailyUsed, dailyCap;
}

class HealthMetricBlock {           // README contract 1 + M04 extensions
  final String metric, basis, engineVersion;
  final double? value, standardError, tEff;   // null ⇔ insufficient / by-decision
  final int nObservations, windowDays;
  final bool sufficient, partial, containsEtfs, backcast;
  final List<Map<String, dynamic>> droppedHoldings;   // [{ticker, reason}]
  final bool? lowExplanatoryPower;  // non-null on `beta` only
  final String? insufficientCause;  // short_window|t_over_n|benchmark_misaligned|dropped_weight_exceeded
  final Map<String, dynamic> extensions;  // r_squared, per_holding, top, effective_n, holdings_count…
}

class PortfolioHealth {
  final String status;              // "ok" | "refused_mock_data" | "no_holdings"
  final String? asOf; final String generatedAt, engineVersion;
  final bool containsEtfs, partial;
  final List<Map<String, dynamic>> droppedHoldings;
  final int holdingsCount, riskyHoldingsCount;
  final double totalValue, investedValue, coveredInvestedValue, cashFraction;
  final double? benchmarkVolAnn;    // context.benchmark_vol_ann; null ⇒ no comparison line
  final Map<String, HealthMetricBlock> blocks;
  final HealthGateStatus gate;
}

class HealthFinding {               // POST response, M07 §3.5
  final String journalEntryId, asOf; final bool created;
  final Map<String, String> sections;   // head, f1..f5
  final HealthGateStatus gate;
}
```

`PortfolioHealth.fromJson`: engine envelope from `json['metrics']` when
present, else the root (`final m = (json['metrics'] as Map<String,dynamic>?)
?? json;`) — tolerates either nesting so a backend divergence is a
one-`fromJson` fix (§7). `gate` from root, falling back to `m['gate']`.
Non-`ok` statuses fill accounting with 0/empty; `asOf` nullable (the refusal
shape omits it). **Units pin:** Tier-1 block values are decimal fractions —
renderer ×100 (M04 §3.4); Tier-2 `realised_max_drawdown`/`realised_return`
values are **already percent** (M03 §3.5) — never ×100 them.

### 3.2 API client + providers

`api_client.dart`, after :934:

```dart
/// CR136 M09 — Portfolio Health tiles + gate status. Free, never gated (M07 §3.4).
Future<PortfolioHealth> portfolioHealth(String userId) async {
  final r = await _dio.get<Map<String, dynamic>>('/v1/portfolio/health/$userId');
  return PortfolioHealth.fromJson(r.data!);
}

/// CR136 M09 — generate (or replay today's) Finding. Same-day repeat returns the
/// stored entry with created:false and consumes no budget (M07 §3.5 step 6).
Future<HealthFinding> generateHealthFinding(String userId) async {
  final r = await _dio.post<Map<String, dynamic>>('/v1/portfolio/health/$userId/finding');
  return HealthFinding.fromJson(r.data!);
}
```

`portfolio_health_providers.dart`, mirroring `sectorAllocationProvider`
(`sim_providers.dart:153-158` — `apiClientProvider` +
`DeviceUser.getOrCreate()`):

```dart
final portfolioHealthProvider = FutureProvider.autoDispose<PortfolioHealth>(...);
final healthFindingProvider  = FutureProvider.autoDispose<HealthFinding>(...);  // the POST
```

A `FutureProvider` wrapping a POST is safe **only because** the endpoint is
idempotent same-day. Gate errors surface as `AsyncError` carrying the
`DioException` (5xx annotated per DEF073, `api_client.dart:70-93`).

### 3.3 The card (`health_card.dart`) — states first

`class PortfolioHealthCard extends ConsumerWidget`, watching
`portfolioHealthProvider` (+ `simNotifierProvider` for the cash dollar source
— accounting the screen already shows). State derivation, first match wins:

| State | Predicate | Treatment |
|---|---|---|
| **Loading** | provider loading | half-alpha slate800 container (`_ChartSkeleton` idiom, `ticker_chart.dart:243-251`) + `HexPulseLoader` (default `hexCyan`, `hex_pulse_loader.dart:13`) |
| **Transport error** | provider error | `_ChartNotice` pattern (`ticker_chart.dart:259-301`): dashed container, retry glyph, `portfolioHealthErrorBody`, tap → `ref.invalidate(portfolioHealthProvider)`. Slate — a failed fetch is not an engine refusal |
| **Refusal** | `status == "refused_mock_data"` | dashed container, **amber** glyph + title, `portfolioHealthMockRefusalTitle/Body` — states what AMI will not do (system-unavailable semantics) |
| **Empty** | `status == "no_holdings"` | `AmiEmptyState` (`empty_state.dart:11`), `portfolioHealthEmptyTitle`, **no CTA** (`_NewTraderHint` below owns the trade CTA). Never 0/0; no bar block on this path (amendment 2c) |
| **Insufficient** | `status == "ok"` AND all four of `portfolio_volatility`, `beta`, `effective_bets`, `risk_contribution` insufficient | dashed container, `⬡` glyph, **neutral slate** (absence, not warning); copy by `portfolio_volatility.insufficient_cause`: `short_window` → `portfolioHealthInsufficientBody(n_observations)`; `dropped_weight_exceeded` → `portfolioHealthInsufficientDroppedBody(covered)`. No accent stripe, no tiles, no metric value (07b: an error state must not be shaped like a result) |
| **Populated** | otherwise | `AccentCard(accent: AmiColors.hexBlue)` (`accent_card.dart:16`) — the only state with the accent stripe |

Non-populated states drop the stripe + tile grid and use a dashed rounded-rect
border — small `_DashedRectBorder` CustomPainter (precedent: CR098 dashed
hexes `room_board.dart:1037`; dashed levels
`lessons/anim/threshold_trigger_painter.dart:38`).

**Populated card, top to bottom** (07a + amendments 3/5/9):

1. `portfolioHealthTitle` (`AmiTypography.h4`) + `portfolioHealthWindowSubtitle`
   (`labelMono`, `textLow`) — amendment-5 verbatim `≈66-DAY EFFECTIVE WINDOW ·
   HOLDINGS-BASED`; "126" appears only in sufficiency copy.
2. **Partial chip** when root `partial`: amber `portfolioHealthPartialChip` +
   `portfolioHealthPartialNote(tickers, covered)`, `covered =
   round(coveredInvestedValue / investedValue × 100)` — invested basis (R5).
3. **Tile grid** — 2-column rows; each tile a rounded rect (`AmiRadii.card`,
   slate900 fill, slate700 border; data_viz §4.1) with `labelMono` label,
   mono `dataMd` value, `caption` unit line — never a bare percentage.
   **`sufficient: false` ⇒ NO tile — absent, not dashed** (data_viz §3.3):
   - **VOLATILITY** (`portfolio_volatility`): `{σₚ×100, 1dp}` + unit line;
     comparison `portfolioHealthTileVolatilityBenchmark(benchmarkVolAnn×100,
     1dp)` only when non-null.
   - **BETA** (`beta`): `{β, 2dp}` + unit line. `lowExplanatoryPower == true`
     adds `portfolioHealthBetaLowR2(r_squared×100, 0dp)` — the card is §F1
     register: the literal "R²" never renders here (amendment 7).
   - **EFFECTIVE BETS** (`effective_bets`): `{DR², 1dp}` +
     `portfolioHealthTileBetsUnit(holdingsCount)` — copy says effective
     independent bets, never a literal count claim.
   - **MAX DRAWDOWN** (`realised_max_drawdown`, Tier 2): renders **only when
     present in `blocks` AND sufficient** — `{value, 1dp}` (already percent)
     plus `portfolioHealthTileMddUnit(window_days)`; window always stated (F10).
     Present-but-insufficient → note `portfolioHealthMddNote(n_observations)`;
     absent from the wire → silent (§7).
4. **INVESTED WEIGHT CONCENTRATION** tile, full-width (`weight_concentration`
   — always sufficient): `{effective_n, 1dp}` +
   `portfolioHealthTileConcentrationUnit(holdings_count)`; block
   `containsEtfs` ⇒ inline chip `portfolioHealthEtfChip` (amendment 3).
5. **Tile-absence notes** (`caption`, only when applicable): `t_over_n` on
   `effective_bets` → `portfolioHealthTnNote(n_observations,
   riskyHoldingsCount)`; `benchmark_misaligned` on `beta` →
   `portfolioHealthBenchmarkNote`. Copy names AMI's limit, never the user's
   book (F20).
6. **Risk vs money bars** (§3.4) — only when `risk_contribution.sufficient`.
7. Legend (solid `portfolioHealthLegendRisk` / outlined
   `portfolioHealthLegendMoney` swatches) + mandatory
   `portfolioHealthBarsCaption` (amendment-1 verbatim) +
   `portfolioHealthBarsNegativeNote` only when a negative share is drawn.
8. **Cash line** `portfolioHealthCashLine(cashFraction×100, 0dp)` — text
   only, **no bar**: a total-book bar beside invested-sleeve bars would mix
   bases (SHARE/LEVEL rule).
9. **Gate CTA footer** (§3.5).

**Motion:** one opacity fade of the whole card (`AmiMotion.fast`,
`AmiMotion.easeOut`); `Duration.zero` when
`MediaQuery.of(context).disableAnimations` (data_viz §7 — first use of the
flag in the app; the spec is the pin). Bars never grow; numbers are stamped.
Do **not** copy the `_ValueCard` count-up (`portfolio_screen.dart:294-303` —
predates the rule).

**RTL:** `EdgeInsetsDirectional` + `Row`; never `Stack` with hard-coded
`Alignment`. Every interpolated numeric string is wrapped `'⁦$s⁩'` before
entering an l10n placeholder — same shape as `_isolateNumeric`
(`portfolio_screen.dart:60`; file-private, so `health_card.dart` carries its
own two-line copy with a pointer comment). The bar block is wrapped in
`Directionality(textDirection: TextDirection.ltr)` — a magnitude axis does
not mirror (data_viz §5).

### 3.4 Signature bars (`risk_money_bars.dart`)

Rows: top **3** by `risk_share` desc from
`risk_contribution.extensions['per_holding']`; `moneyShare = invested_weight`
(both invested-sleeve — amendment 1; risk shares identical on either basis,
verified 3e-16, no recompute). Per row: ticker (`labelMono`) + mono text
`{risk×100, 0dp}% / {money×100, 0dp}%` (the mark is labelled, data_viz §4.4;
the text is also the a11y surface — painted bars sit in `ExcludeSemantics`),
then two 6px bars (`ClipRRect` radius 3 — the `_ClosedTradeSummary` pattern,
`portfolio_screen.dart:1484-1501`): **solid** `hexBlue` = risk share,
**outlined** (transparent fill, 1px `hexBlue` border) = money share. One hue,
two treatments; length to scale (rank 6) + fill-vs-outline for kind (rank 5);
no opacity ramp, no size encoding (data_viz §2).

Geometry is pure and shared — both bars of every row use the SAME instance
(shared scale + origin is structural):

```dart
@immutable
class RiskMoneyBarGeometry {
  const RiskMoneyBarGeometry({required this.axisMin, required this.axisMax});
  final double axisMin;                  // min(0.0, smallest risk share)
  final double axisMax;                  // max(1.0, largest risk or money share)
  double get span => axisMax - axisMin;
  double get originX => -axisMin / span; // track-width fraction where 0 sits
  double widthOf(double share) => share.abs() / span;
  double leftOf(double share) => share >= 0 ? originX : originX - widthOf(share);
  static RiskMoneyBarGeometry fromRows(List<({double risk, double money})> rows);
}
```

Rendering: `LayoutBuilder` → per bar `Padding(left: leftOf(v)*w)` +
`SizedBox(width: widthOf(v)*w)` inside the LTR block. Pinned edge cases
(amendment 2 — all defined, all tested):

- **Negative risk share** (diversifier): `axisMin < 0` reserves the negative
  gutter; bar draws leftward from the shared origin, same solid treatment;
  `portfolioHealthBarsNegativeNote` appears; a 1px slate600 origin tick
  renders at `originX`.
- **Share > 100%**: `axisMax` extends to the max share; the axis end-label
  (`caption` mono under the track) shows the actual maximum
  `{axisMax×100, 0dp}%` — never clamp a drawn-to-scale bar. End-label + `0`
  origin label always render.
- **Invested value == 0**: card-level guard `coveredInvestedValue <= 0` ⇒ bar
  block absent entirely (in practice the `no_holdings` path; defence in
  depth). Never 0/0.

### 3.5 Gate CTA footer

Pure derivation from M07's 8-key gate dict, unit-tested at every boundary:

```dart
enum HealthCtaState { generate, trial, dailyCap, upgrade }

HealthCtaState deriveHealthCta(HealthGateStatus g) {
  final hasAccess = g.mode == 'open' || g.planHasAccess ||
      (g.mode == 'trial' && g.trialActive);
  if (!hasAccess) return HealthCtaState.upgrade;
  if (g.dailyUsed >= g.dailyCap) return HealthCtaState.dailyCap;
  if (g.mode == 'trial' && g.trialActive && !g.planHasAccess) return HealthCtaState.trial;
  return HealthCtaState.generate;
}
```

Tiles are NEVER gated (Rev 4). Renderings:

- **generate**: `HexButton(label: l.portfolioHealthCtaFinding, color:
  AmiColors.hexBlue)` (`hex_button.dart:29`; rounded rect per CR113) →
  `await Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) =>
  const PortfolioHealthFindingScreen()))` (no named detail routes —
  `app.dart:55-59`), then `ref.invalidate(portfolioHealthProvider)`.
- **trial**: same button + slate chip `portfolioHealthTrialChip(k, n, d)`,
  `k = trialFindingsBudget − trialFindingsUsed`, `n = trialFindingsBudget`,
  `d = trialDaysLeft`. (Amendment 9 offers findings-left OR days-left; both
  numbers avoids an unpinned selection rule — recorded deviation.)
- **dailyCap**: disabled `HexButton` (onPressed null) +
  `portfolioHealthDailyCapNote(dailyUsed, dailyCap)`.
- **upgrade**: `portfolioHealthUpgradeBody` + outlined `HexButton` →
  `showUpgradeSheet(context, resetDateLabel: …, onPurchased: () =>
  ref.invalidate(portfolioHealthProvider))` (`upgrade_paywall.dart:351`;
  `resetDateLabel` per `_resetDateStr`, `room_screen.dart:695-700` /
  `settings_screen.dart:681-687`, `'the 1st'` fallback).

The server stays the authority: a stale card racing the gate gets 402/429
from the POST and the Finding screen shows the matching panel — the client
never invents access.

### 3.6 Finding screen + FindingSections extension

`PortfolioHealthFindingScreen` — `ConsumerWidget`; `Scaffold` + `AppBar`
(`findingScreenTitle`); body = `ref.watch(healthFindingProvider).when`:

- **loading** → centred `HexPulseLoader`.
- **data** → `SingleChildScrollView(padding: EdgeInsets.all(AmiSpacing.m))` →
  `FindingSections(payload: {'disclosure': f.sections['head'], 'sections':
  {f1..f5 from f.sections}})` — the adapter from M07's POST envelope to
  M08's widget contract. One component, two hosts: the journal branch (M08
  §3.8) is the other host, so a Finding is reachable from the card AND from
  its journal entry with identical rendering. STORED content only.
- **error** → `_FindingErrorPanel` on the `DioException` detail `code` (M07
  §7): 409 `portfolio_health_unavailable` → amber dashed panel,
  `findingUnavailableBody`; 402 `portfolio_health_gate_closed` → slate +
  `portfolioHealthUpgradeBody` + SEE PLANS; 429
  `portfolio_health_daily_cap_reached` → slate +
  `portfolioHealthDailyCapNote` from the error's own `gate` dict; else →
  transport panel with retry (`ref.invalidate(healthFindingProvider)`).
  Whole-screen single fade, same reduced-motion rule.

`finding_sections.dart` (M08's file — **additive**): (a) before each section
body a header `Text(label, style: AmiTypography.labelMono.copyWith(fontSize:
10, color: AmiColors.hexBlue))` — the Room section-header token
(`room_transcript_rows.dart:179-183`); labels `findingSectionF1…F5` (F5 =
amendment-6 rename, never "Recommendations"); the head disclosure gets no
label. (b) the `f3` body's container becomes the **ledger**: `slate900` fill
(recessed against the slate800 card), 1px `slate700` border, `AmiRadii.card`,
`AmiSpacing.s` padding, same `agentMarkdownStyle(AmiColors.textMed)`
stylesheet (`room_board.dart:1198`) — the register split carried by a
different document class (SCREEN_DESIGNS 21). The stored §F3 is markdown; the
base doc's `BoardMetricRow` KV grid would mean parsing numbers out of stored
prose, violating "render the STORED sections, never regenerate" (README
contract 5) — recorded deviation. `MarkdownBody` count and order unchanged,
so M08's tests hold.

### 3.7 l10n

Every key is NEW EN copy → `@` description ends `retranslate:[ar,ms]`; ar/ms
carry the EN value verbatim as placeholders (M08 §3.7 / DEF210 convention).
Numbers/tickers/windows interpolate as placeholders — never baked into a
sentence. AMI by name; numbers over adjectives. Pinned values:

| Key | EN value |
|---|---|
| `portfolioHealthTitle` | `PORTFOLIO HEALTH` |
| `portfolioHealthWindowSubtitle` | `≈66-DAY EFFECTIVE WINDOW · HOLDINGS-BASED` |
| `portfolioHealthTileVolatility` / `…Unit` / `…Benchmark` | `VOLATILITY` / `% ANNUALISED · TOTAL BOOK` / `S&P 500 {pct}%` |
| `portfolioHealthTileBeta` / `…Unit` | `BETA` / `× THE S&P 500 · MEASURED WINDOW` |
| `portfolioHealthBetaLowR2` | `Market explains {pct}% of daily moves` |
| `portfolioHealthTileBets` / `…Unit` | `EFFECTIVE BETS` / `INDEPENDENT BETS · OF {n} HOLDINGS` |
| `portfolioHealthTileMdd` / `…Unit` | `MAX DRAWDOWN` / `TRAILING {n}-DAY WINDOW · REALISED` |
| `portfolioHealthTileConcentration` / `…Unit` | `INVESTED WEIGHT CONCENTRATION` / `EFFECTIVE HOLDINGS BY WEIGHT · OF {n} HELD` |
| `portfolioHealthEtfChip` | `ETF OVERLAP NOT COUNTED` |
| `portfolioHealthBarsHeading` | `RISK VS MONEY` |
| `portfolioHealthBarsCaption` | `Shares of invested risk and invested money; cash is shown on its own line. Not a forecast and not a return.` |
| `portfolioHealthBarsNegativeNote` | `A negative share means this holding offset risk over the window.` |
| `portfolioHealthLegendRisk` / `…Money` | `RISK` / `MONEY` |
| `portfolioHealthCashLine` | `CASH · {pct}% OF TOTAL BOOK` |
| `portfolioHealthPartialChip` / `…Note` | `PARTIAL` / `Excludes {tickers}. Numbers describe {covered}% of invested value.` |
| `portfolioHealthInsufficientTitle` | `NOT ENOUGH HISTORY YET` |
| `portfolioHealthInsufficientBody` | `Price history available to AMI's engine covers {n} trading days; 126 needed.` |
| `portfolioHealthInsufficientDroppedBody` | `Usable price history covers {covered}% of invested value; AMI needs at least 80%.` |
| `portfolioHealthTnNote` | `{t} aligned trading days across {n} holdings — too few for AMI to attribute risk reliably.` |
| `portfolioHealthBenchmarkNote` | `S&P 500 history did not align with this book's window; beta is not measured.` |
| `portfolioHealthMddNote` | `{n} daily snapshots so far; realised drawdown needs 21.` |
| `portfolioHealthMockRefusalTitle` / `…Body` | `LIVE MARKET DATA IS OFF` / `AMI measures portfolio risk from real price history only. It will not compute these numbers from simulated prices.` |
| `portfolioHealthEmptyTitle` | `NO HOLDINGS TO MEASURE` |
| `portfolioHealthErrorBody` | `AMI's engine did not respond. Tap to retry.` |
| `portfolioHealthCtaFinding` | `FULL FINDING` |
| `portfolioHealthTrialChip` | `{k} of {n} trial Findings left · {d} days` |
| `portfolioHealthDailyCapNote` | `{used} of {cap} Findings used today. Available again tomorrow.` |
| `portfolioHealthUpgradeBody` / `…Cta` | `Findings are included in Trader and Floor Manager plans.` / `SEE PLANS` |
| `findingScreenTitle` | `Portfolio Health` |
| `findingSectionF1…F5` | `F1 · HEADLINES` / `F2 · EXECUTIVE SUMMARY` / `F3 · DETAILED ANALYSIS` / `F4 · CONCLUSION` / `F5 · WHAT THE NUMBERS POINT TO` |
| `findingUnavailableBody` | `AMI cannot generate a Finding right now — live market data is off.` |

The literals 126 / 80 / 21 mirror `T_MIN` / `DROPPED_WEIGHT_MAX` /
`TIER2_MIN_SNAPSHOTS` (cr136.v1); each `@` description names its constant so
a threshold change flags the string. Client dp pins (mirror M06): shares /
cash / covered / R² 0dp; vol / benchmark / MDD 1dp; beta 2dp; DR² /
effective-N 1dp.

## 4. Out of scope for this module

- **Metric math and Finding copy** — M02/M04 compute, M06 renders; the client
  formats and displays only (its sole derivations are geometry fractions and
  the CTA enum).
- **Journal enum, wire mapping, list badge, detail branch** — M08 (landed
  precondition; M09 only extends `FindingSections` additively).
- **Gate semantics/enforcement** — M07; the client renders the gate dict and
  obeys the server's 402/429/409.
- **Journal filter chip** — deliberately not added (`journal_screen.dart`
  `filtersFor` untouched); M08's badge suffices at alpha.
- **Equity curve, scenario panel, bad-month, TE, MCR tiles** — not card
  surfaces; they reach users inside the Finding's stored markdown (M06).
- **Backfill (M10), promotion/E2E + device pass (M11), CR137 Room.**

## 5. Tests

No goldens — verified: zero `matchesGoldenFile` in the repo; SCREEN_DESIGNS'
golden acceptance is translated to widget assertions (deviation recorded).
Host idiom: `MaterialApp` + `AppLocalizations` delegates
(`journal_replay_chrome_test.dart:46-50`); provider overrides per
`test/screens/sim/portfolio_screen_test.dart`
(`sectorAllocationProvider.overrideWith`, ~:95).

**`portfolio_health_test.dart`** — nested (`metrics`) and flat envelopes parse
identically; gate 8 keys; refusal shape (no blocks, null `asOf`);
insufficient block has null value+SE; extensions pass through.

**`risk_money_bars_test.dart`** — geometry: all-positive → axis [0,1],
`originX == 0`, widths ∝ shares; negative −0.0704 → `axisMin == -0.0704`,
`leftOf < originX`, solid treatment kept; share 1.269 → `axisMax == 1.269`,
end label `127%`; widget: solid + outlined bars of one row share origin and
scale (RenderBox widths within 0.5px of computed fractions); negative note
renders only when a negative share is drawn.

**`portfolio_health_card_test.dart`** — one fixture per state:

1. **Populated**: hexBlue `AccentCard`; VOLATILITY/BETA/BETS tiles; caption ==
   the amendment-1 string; cash line; CTA button.
2. **Insufficient** (short_window, n=47): no `AccentCard`, no tile, copy
   `covers 47 trading days; 126 needed`, no `hexAmber` in the state's
   decorations, **no metric value rendered** (no `%`-suffixed mono value —
   the 47/126 shortfall numbers live in the reason copy and are the permitted
   exception; deviation note).
3. **Refusal**: amber title + body; no tiles, no metric values.
4. **Partial**: populated + PARTIAL chip + excluded ticker + covered %.
5. **Empty**: `AmiEmptyState`, no CTA.
6. **Loading**: `HexPulseLoader`.
7. **t_over_n** (σₚ+β sufficient, bets/shares not): vol+beta tiles present,
   bets tile absent, bar block absent, `portfolioHealthTnNote` shown.
8. **MDD**: absent block → no tile, no note; present-insufficient (n=9) →
   `9 daily snapshots…`; sufficient → tile with window in unit line.
9. **CTA boundaries** (pure + widget): dailyUsed 1/2 → generate, 2/2 →
   dailyCap (disabled + note); mode=plan, `plan_has_access:false` → upgrade
   (tap → `upgradeSheetTitle` appears); trial k=5,n=7,d=9 → chip `5 of 7
   trial Findings left · 9 days`; mode=open + trial exhausted → generate.
10. **Motion**: `MediaQuery(disableAnimations: true)` → full opacity on first
    pump; default → one fade at `AmiMotion.fast`; no number animates.
11. **RTL**: pump under `Directionality.rtl` — bar block sits under an LTR
    `Directionality`; interpolated values carry `⁦`
    (`lesson_locale_rtl_test.dart` idiom).
12. **Invested value == 0** fixture → no bar block (never 0/0).

**`portfolio_health_finding_screen_test.dart`** — override
`healthFindingProvider`: data → 6 `MarkdownBody` in order disclosure, f1…f5
(M08's guarantee holds after §3.6); labels `F1 · HEADLINES` … `F5 · WHAT THE
NUMBERS POINT TO`; f3's ancestor container has `slate900` fill; 409 → amber
`findingUnavailableBody`; 402 → SEE PLANS; 429 cap → note using the error
payload's own gate numbers.

Plus: `l10n_key_parity_test.dart` green (ar/ms placeholders exist); M08's
`finding_sections_test.dart` green unmodified.

## 6. Acceptance

- [ ] `cd mobile && flutter analyze` → clean.
- [ ] `cd mobile && flutter test` → green: four new files +
      `l10n_key_parity_test.dart` + M08's tests untouched.
- [ ] `grep -n "PortfolioHealthCard" mobile/lib/screens/sim/portfolio_screen.dart`
      → one insertion, adjacent to `_SectorAllocationSection()`.
- [ ] Every §3.7 key present in en+ar+ms; every EN `@` description carries
      `retranslate:[ar,ms]`.
- [ ] `grep -n "hexAmber" mobile/lib/widgets/portfolio_health/health_card.dart`
      → hits only in refusal + partial-chip paths (never the accent or the
      insufficient state).
- [ ] `grep -rn "matchesGoldenFile" mobile/test/` → no matches.
- [ ] No count-up animation on any number in `widgets/portfolio_health/`.
- [ ] No new pubspec dependencies (`flutter_markdown_plus` ^1.0.3 already at
      pubspec.yaml:74).
- [ ] Commit tagged `(AT:R<N> CR136)`, pathspec-commit only §2's files.

## 7. Hand-off

**M10/M11 may assume:** the card is live behind `portfolioHealthProvider`;
all six presentation states + four CTA states are fixture-drivable for M11's
device pass (iPhone 13/17 release builds: five card states, Finding render,
journal markdown branch, trial/upgrade states); the Finding renders
identically from card (POST envelope) and journal (stored payload) via the
one shared `FindingSections`; all new EN strings flagged `retranslate:[ar,ms]`
for the i18n lane.

**Seams asserted** (reconcile at wire-up; the landed backend doc wins):

- GET parsed as M07 §3.4 (`metrics` wrapping M04 §3.5's root, which nests
  `blocks`); the parser tolerates the flat alternative — divergence is a
  one-`fromJson` fix.
- Tier-2 `realised_max_drawdown` is not named in M07's GET spec; M03 says M07
  owns response shaping. The MDD tile keys on block **presence** — it lights
  up when M07/M03 wire Tier 2 through; until then its absence is a silent
  absent tile, never a dash (Rev 4 §F1: "Tier 2, when sufficient").
- M06 §3.7 stores the journal disclosure as `head_disclosure`; M08 §3.2 pins
  `disclosure`. M09 is insulated — the Finding screen consumes only M07's
  POST `sections.head`; the journal host consumes M08's widget contract. That
  key reconciliation belongs to M06/M08's build, not M09's.
