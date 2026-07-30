<!-- Design-conformance review of CR109's mobile surfaces, written by AT:UI Designer under
     CR134. This is a NEW file so it is a disjoint write path: CR109.md, implementation_plan.md,
     ARCHITECT_BRIEF.md and the lane drafts belong to AT:Gamer on a shared checkout and are not
     touched here (CR081). Findings are for the Gamer track to fold in and for the build lanes
     to satisfy. -->

# CR109 — design-conformance review

**Reviewer:** `AT:UI Designer` · **CR134** · 2026-07-30
**Reviewed:** the CR109 package (13 documents, 5,297 lines) and the AT:Gamer design artifact
`b47a68ca-8a2c-4dc6-84af-c99f26867ed2` — 20 mocked screens, `00 The Floor card` → `19 The Record`.
**Against:** [`ami_hex_in_flutter.md`](../../initial_specs/05_design/ami_hex_in_flutter.md),
[`data_viz_and_meters.md`](../../initial_specs/05_design/data_viz_and_meters.md),
[`colors_motion_rtl.md`](../../initial_specs/05_design/colors_motion_rtl.md), and
`mobile/lib/theme/ami_theme.dart`.

Saiful's ask, verbatim: *"look at CR109 and look at the UI designs. make sure they adhere to the
rest of the application designs."*

---

## 0. The structural finding — why there are twenty-seven of these

**The CR109 package references the design system exactly once.** Not once per document — once in
total, across 5,297 lines:

```
$ grep -rn "05_design\|ami_hex_in_flutter\|data_viz_and_meters\|colors_motion_rtl\|ami_theme" .
lane_drafts/CR109-1-MOBILE.assign.draft.md:30
```

That one line is also the one that hands a coder a forbidden encoding channel (**D01**). And §19's
~60 acceptance criteria — exhaustive on scoring, integrity, restart, fees, thin fields and feature
cross-products — contain **no design criterion of any kind**: no token check, no shape check, no
family-colour check, no motion, contrast, provenance or bidi check.

**This is the second occurrence of a named class**, which by `failure_patterns.md`'s own rule means
it gets a guard rather than a fix. CR106 §4.0 records the first: the hex rule lived only in a
decision record, `HexButton` kept clipping unconditionally for months, and the eventual write-up
notes *"a rule filed where its audience does not read is not a control."* The rule was duly moved
into `ami_hex_in_flutter.md` — and nothing structural couples a CR to it, so twenty screens have now
been drawn without it. The guard is §3 of this document: design acceptance, phrased as assertions.

**None of this is a criticism of the artifact's care.** See §1. It is a criticism of a pipeline in
which a 20-screen design can reach lane-ready without the design system entering the room.

---

## 1. What is right, and must not be re-done

Recorded first because a findings list reads as a verdict on the whole, and this one is not.

| | Evidence |
|---|---|
| **Tokens are verbatim** from `ami_theme.dart`, with a comment saying so | `--slate900:#0F172A`, `--cardBg:#152845`, `--cyan:#06B6D4` … all correct |
| **The type ramp is the app's**, correctly scaled to the 310px frame | `.big` 33px = `statBig` 42 × 0.79 · `.mid` 19px = `statMid` 24 × 0.79 |
| **`tabular-nums` on every numeric run** | `.big`, `.mid`, `.m`, `.kv .v`, `.board-row .tw`, `.taxrow` |
| **Dark-only observed** — no light variant invented | D-062, correctly cited in the lane draft |
| **The heat gauge is a bar, not a ring** | Correct: `data_viz` §4.3 forbids printing the number beside a ring, and this design is number-forward |
| **Screen 18 is a model of CR040** | Red notice, per-day `LIVE`/`MOCK` table, unofficial return shown, no points, "why did this happen?" |
| **`prefers-reduced-motion` honoured** in the artifact's own CSS | `* { animation: none !important }` |

Screen 18 is the strongest screen in the set and is quoted back in §3 as the standard the others
should meet.

---

## 2. Findings

**Severity:** 🔴 blocking a lane that is drafted · 🟠 wrong as drawn · 🟡 absent rather than wrong.

### 2.1 Provenance and derived values

#### 🔴 D01 — The equity-curve lane offers an encoding the system forbids

`lane_drafts/CR109-1-MOBILE.assign.draft.md:34` — *"A point whose `price_source` is not `live` must
be visibly marked — a dashed segment, **a muted colour**, or a flagged tick, **your call**."*

`data_viz_and_meters.md:44` puts opacity/saturation ramps in the forbidden row outright: *"A dimmed
mark reads as **absent**, not **small**."* `:64` pins provenance to one vocabulary: *"Mark provenance
with fill-vs-outline and a dashed segment. **Never amber, never ⚠**."*

Two of the three options offered are the sanctioned one; the middle one is forbidden, and *"your
call"* makes it a coin-flip. **This is the only finding with a clock on it** — the lane is written
and waiting for the Architect to lift.

> **Fix.** Replace lines 34–36 with: *"A point whose `price_source` is not `live` renders as a
> **dashed segment with a hollow cap**; the legend names the treatment. Never a muted or lower-opacity
> colour (`data_viz_and_meters.md:44`), never amber (`:64`) — a system-supplied default is a different
> kind of fact, not a risk."*

#### 🟠 D02 — The equity curve has no provenance channel at all

`sparkline()` draws one solid `<path stroke-width="1.75">` plus a gradient area and an endpoint dot.
`price_source` is on the wire — that is the entire reason it is on the wire — and appears nowhere in
the drawing. Screens 09, 10, 11, 15, 17.

> **Fix.** Split the path at every provenance boundary; non-`live` spans dashed with hollow caps.
> Follow `ticker_chart.dart`'s `_PricePainter` rather than inventing a second charting idiom — the
> lane draft asks for this at `:26` and the artifact does not do it.

#### 🟠 D03 — The modeled trading cost is drawn in the risk colour

Screen 07: `Est. trading cost` → `1.56 modeled` in `var(--amber)`.

`data_viz_and_meters.md:64` — *"Derived ≠ dangerous. … **Never amber, never ⚠** — those mean risk, and
a system-supplied default is not a risk, it is a different kind of fact."* The word `modeled` beside
it is correct and should stay; the colour contradicts it.

> **Fix.** `textMed` ink, `modeled` in `textLow`. Reserve amber for the book-percentage line if that
> line keeps it at all — see D04.

#### 🟠 D04 — Two different ambers on one card

Screen 07's confirm card carries `1.56 modeled` **and** `42% of your book`, both amber, meaning two
unrelated things.

[`room_board.dart:53`](../../../mobile/lib/widgets/room/room_board.dart#L53) carries a shipped comment
forbidding exactly this: *"amber stays reserved for the violations list and the safety-floor pill.
**Two different amber things on one card is one too many.**"*

> **Fix.** D03 removes one of them. The concentration line keeps amber only if concentration is being
> called out as risk — and §10.4 says it is not (see D11).

#### 🟠 D05 — `MOCK` days marked amber

Screen 18's affected-days table renders `MOCK` in `var(--amber)`. Same rule as D03. The severity is
already carried, correctly and loudly, by the red notice above it; the per-day marks are carrying
*provenance*, and provenance is fill-vs-outline.

> **Fix.** `MOCK` as an outlined chip in `slate500`, `LIVE` filled in green. The row then reads as two
> kinds of fact, and the red notice stays the only thing shouting.

#### 🟠 D06 — The counterfactual is a simulation drawn as a measurement

Screen 15, beat 2, in full: *"If you'd just held the S&P — **+0.61%**"* on a green-bordered card, with
no marking whatsoever. It is the most prominent single number on the app's highest-attention screen,
and it is a value the system computed from a hypothetical, not one it observed.

`data_viz_and_meters.md:62` — *"Never draw a value you cannot attribute … the chart must carry that
provenance or must not be drawn."*

> **Fix.** Both counterfactual lines get a hollow cap / dashed rule and one 9pt mono footnote naming
> what was held constant (`PRICE-ONLY · NO DIVIDENDS · YOUR ENTRY DATES` — §6.6.3 already decided
> price-only, so the footnote is stating a decision, not adding one). §19 asserts the free Close
> *contains* both lines; it should also assert they are marked.

#### 🟠 D07 — The wildness index is a composite with no defensible weighting

§10.4: *"A per-run width score from stored data — concentration, effective position count, turnover,
book volatility."* Four unlike quantities, one number, no weighting stated anywhere in the package.

`data_viz_and_meters.md:73` — *"**No composite scores without a defensible weighting.** A 'consensus
78%' over agents who do not have equal authority is a fabricated statistic."* And `:49` — *"Prefer
ordinal bands over a continuous axis whenever the underlying number is model-derived … quantise **at
the source**, in the schema, not in the renderer."*

> **Fix.** Three ordinal bands — `DISCIPLINED · MIXED · WILD` — quantised in `games_scoring.py` and
> stored as an enum on `game_entries`. The weighting is written into the pure function and tested. The
> number is never printed. This also makes tag-versus-index (§10.4's best coaching moment) a
> comparison of two enums rather than a tag against a float.

#### 🟠 D08 — Returns-by-style has no small-n floor

Screen 19: *"Wild runs — 1 of 7 positive"*, *"Disciplined runs — 5 of 8 positive"*. Correct here.
At `n = 1` the same row reads `1 of 1`, and a reader takes 100% from it.

`data_viz_and_meters.md:66` — *"Counts and totals are computed over known values only, and the
caption says how many were known."*

> **Fix.** A per-style minimum (`n ≥ 3`) below which the row is omitted rather than shown degenerate,
> and the caption states `n`. Identical to the per-card thresholds CR133 §4.1 adopted for INSIGHTS.

### 2.2 The mirrors render as verdicts

#### 🟠 D09 — The whole class

§10.4 is emphatic and says it three times: *"measurement instead of guardrails"* · *"Not a rule, not
a warning, no gate — a mirror held up at the moment width is being decided"* · *"The counterfactual
never scolds."* §1.1's lab framing exists so that going wild is **sanctioned and measured**, not
prevented — and §10.4 says naming wild as sanctioned *"removes the shame that suppresses
experimentation."*

Three mirrors ship in judgment colours:

| Mirror | Screen | Drawn as | Reads as |
|---|---|---|---|
| Book heat | 10 | amber bar + amber `High` chip | a warning |
| Returns by style | 19 | `.down` red on *wild*, `.up` green on *disciplined* | a verdict on the player |
| Est. trading cost | 07 | amber (D03) | a risk |

Amber is the app's *"needs attention"* status (`colors_motion_rtl.md:31`). Rendering the mirror in
the warning colour makes it a warning, whatever the copy says. **Colour is what turns a mirror into
a scold** — and the design spent three documents arguing that it must not be one.

> **Fix.** Mirrors take neutral ink: a `slate700` track with a `textMed` fill, and the ordinal band as
> a `tinted` `HexChip` in `slate500`. Status colour is reserved for outcomes — the run's P&L, the
> verdict, the void. The number stays; only the judgment goes.
>
> `returns by style` in particular: `1 of 7` and `5 of 8` in `textHigh`, no red, no green. The
> player draws the conclusion; that is the entire point of a mirror.

### 2.3 Shape — the app's identity is absent

#### 🟠 D10 — Zero hexagons in twenty screens

```
$ grep -c "clip-path" artifact.html   → 0
$ grep -c "polygon("  artifact.html   → 0
```

Every chip, tab, size-chip, nav cell and button in the artifact is a rounded rectangle.

`ami_hex_in_flutter.md:189` — *"**Hex geometry is for marks and controls.** Surfaces and large CTAs
are rounded rects."* The boundary is pinned in `mobile/test/widgets/cta_shape_test.dart`, *"so a
later 'AMI moved off hex clipping' tidy-up trips rather than lands."* The design system is named
Hex-Reinforced Precision; the game as drawn contains none of it.

> **Fix**, by element, all against shipped precedent:
>
> | Element | Correct treatment | Precedent |
> |---|---|---|
> | Status/tier/tag chips | `HexChip`, `CutCornerOctagonClipper(cornerCut: 6)` | `hex_chip.dart:76` |
> | Size / preset / period chips | `CutCornerOctagonClipper(cornerCut: 8)` | `ticker_chart.dart:185` |
> | Segmented bars (board filters, Record tabs) | `FlatTopHexagonBarClipper(endInset: 8)`, one clip around the whole bar | CR117 / DEF146 |
> | Bottom-nav active cell | flat-top hexagon, purple→blue gradient, `hexBlue` border, glow | `hex_bottom_nav.dart` `_ActiveHexPainter` |
> | Cards, notices, sheets | rounded rect — **already correct**, wrong radius (D11) | `data_viz_and_meters.md:93` |
> | Full-width CTAs | rounded rect, **no clip** | CR113 |

#### 🟠 D11 — Card radius is 4px; the app is 8

`border-radius` census across the artifact: `4px` ×17, `3px` ×9, `2px` ×9. The app has four radii and
uses two: `AmiRadii.card = 8` for cards, panels, sheets, list rows and large CTAs; `AmiRadii.sheet =
12` for an outcome surface (`_VerdictCard`). `4` is `AmiRadii.sm`, which nothing in `mobile/lib` uses
for a card.

> **Fix.** Cards, notices and CTAs to `8`. The Close's result card is an outcome surface — `12` with a
> 1.5px accent border on all four sides, which is what `_VerdictCard` (`room_screen.dart:906`) does and
> what beat 1 wants anyway.

#### 🟡 D12 — `StatTile` has no agreed shape, and CR109 is the change that forces the question

§13.3: *"`StatTile` / `MetricRow` — reimplemented privately 4× today (`_AlpacaStat`, `_MetricRow`,
`_StatRow`, `_ReadOnlyRow`) — extract once."* Correct and overdue. But the target shape is
contradictory:

- `data_viz_and_meters.md:117` (§4.1) specs the KPI tile as a `CutCornerOctagonClipper(cornerCut: 10)`
  panel with a 3px top border and a 56pt outcome hexagon.
- `:85` (§4.0) says content surfaces are rounded rects.
- **All four shipped implementations are rounded-rect or unclipped.** `_AlpacaStat`
  (`portfolio_screen.dart:1627`) is a caption + `labelMono` in a `glassChrome` container at radius 8;
  `_MetricRow` (`room_screen.dart:1571`) is a 72pt `labelMono` label + `statSmall` value, no container.

§4.1 describes a component nothing implements, and CR109 is the first change that has to build it.

> **Fix.** Resolved in favour of §4.0 and the shipped code — the tile is a **surface**: rounded rect at
> `AmiRadii.card`, optional 2px accent top stripe (`AccentCard`), and the hexagon reserved for the
> *mark inside* it where an outcome glyph is warranted. §4.1 amended accordingly under CR134 so the
> next reader is not sent back into the same contradiction.

#### 🟡 D13 — The Close invents a surface token

Screen 15: `linear-gradient(180deg,#12233D 0%,#0F172A 58%)`. `#12233D` is not in `ami_theme.dart`.

`colors_motion_rtl.md:56` specs the hero treatment: *"Canvas + top-centred **radial** blue glow
(`hex-blue` at 15% opacity, 400px diameter)."*

> **Fix.** `slate900` canvas + the specified radial glow. Same intent, an existing token, and it reads
> as the app's hero rather than as a new gradient.

### 2.4 Colour — family hues spent on non-agent concepts

#### 🟠 D14 — Every primary CTA is cyan

`.btn { background: var(--cyan); color: var(--slate900) }` — 9 filled and 6 ghost instances.

`colors_motion_rtl.md:28` — *"Use **hex-blue** for primary CTAs (regardless of context)."* Cyan is the
four Analysts (`data_viz_and_meters.md:15`, `agentFamilyColor()`).

> **Fix.** `hexBlue` fill, white ink, `AmiRadii.card`. `HexButton(variant: filled)` already is this.
> `HexButtonVariant.glow` is the right variant for the Close's re-entry CTA — it is the app's biggest
> earned moment and `glow` exists for exactly that.

#### 🟠 D15 — The career title `Analyst` renders in two different family colours

Screen 00: `<span class="chip pu">Analyst</span>` — purple. Screen 19: the same rung
`<span class="chip cy">×1.4</span>` with `Analyst` in cyan.

Inconsistent with itself, and both are family hues: purple is Researchers + Managers, cyan is the
four Analysts. A player title literally named **Analyst**, rendered cyan, cannot be distinguished
from an Analyst family mark.

#### 🟠 D16 — The title ladder has no colour scheme, and the one it inherits is being deleted

Screen 19's ladder is slate → green → cyan → slate → slate. §13.3 says to reuse `league_common.dart`,
whose `leagueTierColor()` maps five tiers onto `hexBlue / hexCyan / hexPurple / hexAmber / slate500` —
four family hues. And it is **orphaned by CR109 itself**: its only two importers, `league_card.dart`
and `league_screen.dart`, are both on §13.4's deletion list.

> **Fix for D15 + D16.** Titles are a **progression ramp**, not an identity, so they must not borrow
> identity hues. Use a single-hue value ramp on `hexBlue` — the brand colour, which is already
> non-family and already means "the app itself" — with rung state carried by fill-vs-outline
> (`data_viz_and_meters.md:41`, rank 5, *"reads as a different sort of thing"*): locked rungs outlined
> in `slate600`, reached rungs filled, current rung filled + `glowBlue`. Strike `league_common.dart`
> from §13.3's reuse list and add it to §13.4's removal scope.

#### 🟠 D17 — The champion skin recolours agent frames amber

§8.3: *"A champion's Room renders its agent cards in **amber hex frames** instead of slate."*

Amber is not free. It is the **Risk family's** colour — three of the twelve agents in that very Room
— and it is the app's attention state: `HexAvatarStatus.attention` is *"stronger amber-tinted pulse +
'!' badge"*, and `room_screen.dart:712` and `:793` are both amber warning cards. **A champion's Room
in all-amber frames reads as twelve agents flagging a problem.**

The idea is right and its economics are right (zero art, programmatic, on-brand). Only the channel is
wrong.

> **Fix.** Champion status is **hierarchy**, and `data_viz_and_meters.md:43` assigns hierarchy to
> **stroke weight** — rank 7, *"use for hierarchy, not data"*, which is exactly this. A champion's Room
> draws each agent frame at 2px instead of 1px **in the agent's own family colour**, plus §8.3's own
> **Room plaque** (already the section's second idea, and the safest one — an added mark, not a
> recoloured one). Every family hue survives, the Room still reads instantly as different, cost is
> still zero.

#### 🟡 D18 — Info notices are blue; the status table says cyan

`.notice.info` uses `--blue`. `colors_motion_rtl.md:47` assigns **cyan** to *Info — neutral
information, tips, lesson references*, and blue to primary CTAs. Minor, but it is the token that
collides with D14's fix: once CTAs are blue, a blue notice beside a blue button flattens the
hierarchy.

> **Fix.** Info notices to `hexCyan`. This is the one place cyan is correct and non-family, because it
> is a *status*, which `data_viz_and_meters.md:25` sanctions cross-family.

### 2.5 Motion

#### 🟠 D19 — Beat 1 animates two things, one of which is never permitted

§10.2: *"**1 — The result.** Rank, career-point delta, **the curve replayed**."*

`data_viz_and_meters.md:257` — *"Marks must not fly into position, **counters must not tick up**."*
`colors_motion_rtl.md:107` — *"**No motion on text** (no fade-in-text, no animated word counters)."*

**Saiful's ruling, 2026-07-30: the curve draws on once, briefly.** The two halves separate cleanly:

> **Permitted, and now written down.** A **single left-to-right draw-on of the already-final curve**,
> **≤600ms**, `AmiMotion.easeOut`, on the Close and the season Wind-Up only, removed entirely under
> `MediaQuery.disableAnimations`. 600ms is not a new number — it is what `HexBurstOverlay`
> (`celebration.dart:154`) already ships, so this documents an exception the app has rather than
> inventing one. `data_viz_and_meters.md` §7 is amended under CR134 to name it, bound it and say where
> it does **not** apply, so it is a rule and not a precedent.
>
> **Not permitted, unchanged.** The `+112 pts` delta is **stamped**. It never counts up. *No motion on
> text* stands unamended — it is a separate rule with a separate reason, and the ruling was about the
> curve.

#### 🟡 D20 — `Celebrate.major` cannot be generalised as §13.3 asks

§13.3: *"The Close / ceremony — Full-screen sequence (§10); **generalise `Celebrate.major`**."*

`celebration.dart:44` is `static void major(BuildContext context, {required Agent agent})`, whose body
pushes `AgentUnlockedScreen(agent: agent)`, and whose file docstring says *"major — full-screen
`AgentUnlockedScreen` takeover. **Agent unlock only.**"* Generalising it widens the app's biggest
earned moment to cover a weekly result, which is a demotion of the unlock, not a promotion of the
Close.

> **Fix.** Leave `Celebrate` alone. The Close is its own full-screen route (`GameCloseScreen`,
> `fullscreenDialog: true`) that plays a heavy haptic on push. The tier taxonomy stays true —
> micro/meso/major describe *overlays over the calling widget*, and the Close is a destination.

### 2.6 RTL and bidi

#### 🟠 D21 — RTL appears in the package only as a string concern

The package's entire RTL content is *"Arabic is RTL"* beside the ARB instruction, in both lane
drafts. The game is wall-to-wall numeric pairs and ratios: `3rd of 26` · `+4.90% TWR · +112 pts` ·
`82% in 2 names` · `31 / 28 / 3` · `1 of 7 positive` · `−4.2%` · `548 to Trader` · `2D 14H`.

`data_viz_and_meters.md:225` — *"**Every mono numeric run needs `unicode-bidi: isolate` (CSS) / an
LTR-locked span (Flutter).** **Measured** in the CR106 prototype: without isolation, `2.8 : 1` renders
as `1 : 2.8`."* That is a wrong number, not a layout nit. `room_board.dart:39-42` hides `intl`'s
`TextDirection` specifically so this lock cannot silently bind to the wrong type.

> **Fix.** Every mono numeric run in the game LTR-locked, no exceptions. The board's rank column, the
> ladder's thresholds and the `entered / finished / forfeited` triple are the highest-risk three.

#### 🟡 D22 — The curve's axis behaviour under RTL is unstated, and the two docs differ

`colors_motion_rtl.md:141` mirrors time-axis progressions (*older-on-left becomes older-on-right*) and
`:134` says `fl_chart` is configured `direction: rtl`. `data_viz_and_meters.md:222` says a **magnitude
axis does not mirror**. An equity curve has one of each, and slice 1 ships the app's first line chart.

> **Fix.** State it in the lane: **the time axis mirrors, the NAV axis does not**, and the draw-on
> (D19) runs in reading order — left-to-right in EN, right-to-left in AR. One sentence, and without it
> the first chart the app ever draws is a coin-flip in Arabic.

### 2.7 Iconography and reuse

#### 🟡 D23 — Nav icons and beat markers are codepoints the bundled faces do not carry

Nav: `▦ ◪ ◆ ▭ ◈` (U+25A6, U+25EA, U+25C6, U+25AD, U+25C8). Close beats: `① ② ③` (U+2460–2462).

These are absent from the prototype's font subset **and** from Inter, so they fall back or vanish
silently. This exact class turned a caret into a full stop in the CR120 prototype. The shipped nav
passes Material icons (`Icons.grid_view_rounded`, …) to `HexNavItem`.

> **Fix.** In any prototype: inline SVG paths. In Flutter: Material icons as today, or
> `FlatTopRegularHexagon` — `data_viz_and_meters.md:270` says to prefer the clip-path over the `⬢`
> glyph precisely because it *"does not depend on a font subset carrying U+2B22."*

#### 🟡 D24 — The settlement freeze re-invents a shipped pattern

§13.3's *"Settlement freeze — positions locked, results withheld ~1h"* is the same act the Room
already performs. `room_screen.dart:969` carries both the widget and the rule:

> *"`withheld_tenure` gets its own accent (**purple, not amber**) so the card never LOOKS like the
> credits-withheld state even before reading it."*

The app has a considered visual language for *deliberately withheld*, and CR109 does not reference it.

> **Fix.** Reuse the card. Take an accent that is neither amber (credits-withheld) nor purple
> (tenure-withheld): `slate500` with fill-vs-outline, which is what `accentForOutcome` gives `PASS` and
> `NO_VERDICT` and for the same reason — *"amber here would read as 'this trade was risky'."*

#### 🟡 D25 — The reuse list names four widgets, one of them dead, and omits the one CR109 needs most

§13.3:1814 — *"Reuse `AccentCard`, `HexChip`, `HexButton`, `league_common.dart`."* `league_common.dart`
is D16's orphan. Not named, and all directly needed:

| Widget | Why CR109 needs it |
|---|---|
| **`AmiEmptyState`** (`widgets/empty_state.dart`) | ≥6 empty states, including *"the empty book — must not be a blank list"*, which is §13.3's own highest-anxiety screen |
| `HexToast` | queued-order confirmations, cancel-before-fill |
| `GlassPanel` | the chrome the app uses for headers and overlays |
| `AmiMotion` | the 150/200/300 ramp and `easeOut`, including D19's bound |
| `readableOnCanvas()` | any accent used as type must clear 4.2:1 |
| `agentFamilyColor()` | the post-mortem names an agent — D17's fix depends on this |
| `_PricePainter` (`ticker_chart.dart`) | the charting idiom the lane draft asks the coder to follow |

#### 🟡 D26 — Twenty new surfaces, none in the screen inventory

`docs/initial_specs/05_design/screen_inventory.md` lists 20 screens and is the app's index of what
exists. CR109 adds 20 more and joins none of them.

> **Fix.** The Gamer track appends its surfaces at build time, one row each. Not a blocker; it is how
> the next designer finds out these exist.

#### 🟡 D27 — The artifact's bottom nav is stale against a decided CR

Screens render `FLOOR · PORT · GAME · JRNL · LEARN` — five tabs, Journal still a tab, no `YOU`, and
Settings absent entirely. **CR133 is decided** (Saiful, 2026-07-30): `FLOOR · PORTFOLIO · GAME ·
LESSONS · YOU`, with the Journal moved inside `YOU` and Settings behind its gear. Labels are also
abbreviated; CR133 measured that the full words fit — 5 cells give 77.6pt each and `PORTFOLIO`
renders at 52.4pt.

The nav is drawn at `opacity:.5`, so it is plainly context rather than a proposal. It is listed only
because a build lane reading this artifact would take the wrong nav from it.

---

## 3. Design acceptance — the guard

§0's finding is that nothing couples a CR to the design system. A checklist would not fix that:
CLAUDE.md's own rule is that **prompt instructions are not controls** (CR038 — agents ignore even
emphatic instructions ~70% of the time). So these are written as assertions, for the Architect to
fold into CR109 §19 and for the lanes to satisfy.

**Shape**
- Every chip, size-chip, preset-chip and segmented control in `screens/games/` is clip-path'd. The
  boundary test `mobile/test/widgets/cta_shape_test.dart` gains the game widgets, asserting in both
  directions: controls **have** a clip, full-width CTAs **do not**.
- No card, notice or sheet in `screens/games/` uses a radius other than `AmiRadii.card` or
  `AmiRadii.sheet`.

**Colour**
- No colour literal appears in `screens/games/`; every colour resolves through `AmiColors`,
  `agentFamilyColor()` or `accentForOutcome()`. Greppable, and it is what catches the `#12233D` class.
- **No family hue encodes a non-agent concept.** Titles, tiers and career points do not use
  `hexCyan`, `hexPurple`, `hexAmber` or `hexPink` as identity.
- **No agent mark changes hue for any reason** — champion, cosmetic, tier or otherwise. Asserted at
  the widget: the champion Room renders each agent in `agentFamilyColor(agent.family)` regardless of
  champion state.
- **No card carries two ambers meaning two things.**

**Honesty**
- A curve point whose `price_source` is not `live` renders dashed with a hollow cap, and never with a
  muted colour, a lower opacity or amber.
- Both counterfactual lines render with a derived-value marking and a footnote naming what was held
  constant.
- The wildness index is stored as an ordinal enum and its numeric value never reaches the client.
- A returns-by-style row with `n < 3` is omitted, not shown; every such caption states `n`.
- Screen 18 is the standard: an unranked run says which days, in what state, and shows its return
  marked unofficial. **No figure the game cannot derive renders as `0`** (CR040).

**Mirrors**
- Book heat, returns-by-style and the wildness band render in neutral ink. A test asserts no
  `hexAmber` or `hexRed` in the heat gauge and no `hexRed` on a "wild" row — §10.4's *"never scolds"*,
  made structural.

**Motion**
- The Close's curve draw-on is ≤600ms, runs once, and is absent when `MediaQuery.disableAnimations`
  is true.
- **No numeric value in `screens/games/` animates.** No count-up, anywhere, ever.

**Bidi**
- Every mono numeric run in `screens/games/` is inside an LTR-locked span. Golden test at `ar` locale
  asserting `3 / 26` does not render `26 / 3` — the CR106 measurement, applied to the game.

---

## 4. What this review did not touch

`CR109.md`, `implementation_plan.md`, `ARCHITECT_BRIEF.md` and both lane drafts are AT:Gamer's files
on a shared checkout; CR081's sweep risk makes editing them the wrong move even when the edit is one
sentence. **D01's fix is written out verbatim above so the Gamer track can paste it** — it is one
line, and it is the only finding that has to land before a lane opens.

Design-system amendments arising from this review land under CR134, in
`docs/initial_specs/05_design/`: `data_viz_and_meters.md` §7 (D19's bounded exception) and §4.1
(D12's shape resolution).

Prototype showing the corrected screens beside the current ones lives under CR134, not here:
[`CR134_cr109_design_conformance/prototype/`](../CR134_cr109_design_conformance/prototype/).
