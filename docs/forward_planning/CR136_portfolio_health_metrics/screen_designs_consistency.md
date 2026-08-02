<!-- CR136 M11 §3.8b — SCREEN_DESIGNS Rev-2 amendments 1–10 walked against the shipped M09 code; yes/no per amendment, with the file:line that settles each. -->

# CR136 — SCREEN_DESIGNS Rev-2 consistency walk

Amendments 1–10 (`SCREEN_DESIGNS.md:259-323`) checked against M09 as shipped at
`1942ee22` + `0762f02d`. Each row cites the code or test that settles it, so a
re-reader can re-run the walk rather than trust it.

**Result: 8 conform, 2 amended (one design change with a measurement behind it,
one doc line that was never buildable as written). No DEF minted — no code is
wrong against Rev 4.**

| # | Amendment | Verdict | Evidence |
|---|---|---|---|
| 1 | Both bars invested-sleeve; mandatory caption verbatim; cash on its own line, no bar | **YES** | `risk_money_bars.dart` takes `risk_share` + `invested_weight` from `risk_contribution.extensions.per_holding`, both invested-sleeve. Caption asserted verbatim in `portfolio_health_card_test.dart` ("the amendment-1 caption is mandatory and verbatim"). Cash renders as `portfolioHealthCashLine`, text only. |
| 2 | Three edge cases defined and built | **YES** | Negative share: `RiskMoneyBarGeometry.axisMin = min(0, …)`, origin tick, `portfolioHealthBarsNegativeNote`; tested at −0.0704. >100%: `axisMax` extends, end-label prints the real maximum; tested at 1.269 → `127%`. Invested = 0: card-level `coveredInvestedValue > 0` guard drops the whole block; tested. |
| 3 | Concentration tile on the invested sleeve, so labelled, ETF chip when `contains_etfs` | **YES** | `_ConcentrationTile` reads `weight_concentration.extensions.effective_n`; label `INVESTED WEIGHT CONCENTRATION`; chip `ETF OVERLAP NOT COUNTED` gated on the block's `containsEtfs`. Both sides tested (M09 audit finding 8.12). |
| 4 | Disclosures at the HEAD, before §F1, stored in the payload | **YES** | `FindingSections` renders `sections['head']` first in its own recessed container, then `f1…f5`; `isRenderable` refuses to render a Finding at all without a non-empty disclosure. M08's write-time validator raises on an empty `head`, so a disclosure-less artefact cannot reach storage either. |
| 5 | Window subtitle "≈66-DAY EFFECTIVE WINDOW · HOLDINGS-BASED"; 126 only in sufficiency copy | **YES** | `portfolioHealthWindowSubtitle` is that string verbatim. `126` appears in exactly one ARB value in the whole app, `portfolioHealthInsufficientBody` — the sufficiency copy. |
| 6 | §F5 titled "What the numbers point to"; conditional-educational templates | **YES** | `findingSectionF5` = `F5 · WHAT THE NUMBERS POINT TO`; a test asserts `find.textContaining('Recommendations')` finds nothing. Rule templates R0/R2b present, R1/R3/R4 reworded (`portfolio_rules.py:76`). |
| 7 | Plain-language R² — the literal never renders on the card | **YES** | `portfolioHealthBetaLowR2` = "Market explains {pct}% of daily moves". A test joins every `Text` on the card and asserts `R²` appears nowhere (added by the M09 audit). |
| 8 | Insufficient copy names AMI's own limit when that is the cause (F20) | **YES** | `portfolioHealthInsufficientBody`: "Price history available to AMI's engine covers {n} trading days; 126 needed." Never phrased as the user's holding being young. |
| 9 | Gate CTA states; tiles never gated | **YES** | `deriveHealthCta` → generate / trial / dailyCap / upgrade, unit-tested at every boundary. A test pumps a closed gate and asserts the tiles and the bars block still render. |
| 10 | Golden tests over five card states + three edge fixtures | **AMENDED** | See below. |

## The two amendments

### 10 — goldens do not exist in this repo, and did not before CR136

`grep -rn "matchesGoldenFile" mobile/test/` returns nothing. There is no golden
infrastructure, no reference PNGs, and no CI step that would compare them; the
base doc's golden acceptance was written against a testing setup this project
never adopted.

M09 translated it into widget assertions instead, which is recorded as a
deviation in M09 §5 and re-recorded here. Every state and every edge fixture the
amendment named **is** covered — six card states plus a seventh added by the M09
audit (unknown status), and all three edge cases — they are asserted on the
widget tree rather than on pixels.

Honest limit, stated rather than papered over: a widget assertion cannot catch a
purely visual regression (a colour token drifting, a bar rendering at the wrong
height when the assertion only checks its `RenderBox` width). The bar geometry
test does measure real `RenderBox` rects, which is the closest thing to a
pixel check available here. Adopting goldens is a repo-wide decision with a
maintenance cost, so it stays out of CR136.

### 1/2 — the bars ship COLLAPSED, which the amendment did not anticipate

Amendment 1 and 2 describe the bar block as always present on a populated card.
It is present, correct in every detail above, and **collapsed behind a
tap-to-expand row** by default.

The reason is measured, not stylistic: fully expanded the card is **803pt** at
390×844, which added a whole screen to the Positions tab — a tab CR120 §9
budgets at ≤ 3.0 screens and which already measured 2.99. Collapsed the card is
**563pt** and the tab measures 3.71. Saiful's call, 2026-08-03, given those
numbers.

The mandatory caption ships **inside the same expanded block as the bars**, so
there is no state in which a bar is drawn without the sentence naming its basis
— which is what amendment 1 was actually protecting. CR120's acceptance number
was re-pinned 3.0 → 3.75 in its own test, with the measurement and the reason
recorded there.

**SCREEN_DESIGNS.md is left as written.** It is an audit-trail document by its
own opening line ("The sections above are kept as written"), and this file is
the amendment record. A future reader comparing the doc to the app will find
this walk from the CR folder's index.
