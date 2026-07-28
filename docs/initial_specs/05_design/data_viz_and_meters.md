# Data visualisation, meters and stat tiles — AMI Hex

> Written in CR106. The AMI design system mount carries **no chart chapter** — the whole of its
> data-visualisation guidance is *"Blue (primary), green (positive), red (negative)"*
> (`reference/01_Hex_Reinforced_Design_System.md:236`) plus *"cyan + green + amber palette"* for
> illustrative imagery (`README.md:148`). Every chart the app has shipped so far
> (`ticker_chart.dart`, the sector donut in `portfolio_screen.dart`, the lesson painters) made its own
> local decisions. This file is where those decisions get reconciled, so the next one doesn't have to
> guess. The mount is read-only; this lives in our repo.

---

## 1. The rule that outranks everything

**Family colour is sacred.** Cyan = the four Analysts. Purple = Researchers and Managers (including the
PM). Amber = the three Risk debators. Green = the Trader, and positive P&L. Red = negative and mandate
violations. Pink = the Concierge and nothing else. See
[`colors_motion_rtl.md`](colors_motion_rtl.md).

The consequence for charts is specific and frequently inconvenient: **you may not encode a variable in the
hue of a mark that represents an agent.** If a chart needs to say "this analyst was bullish", it has to say
it with position, shape, fill-vs-outline, or a glyph — never by turning a cyan hex green.

Status colours (green positive / red negative / amber warning / slate unknown) *are* permitted
cross-family, because they describe an **outcome**, not an identity. A verdict tile may be green while the
PM who issued it is purple.

---

## 2. Encoding vocabulary — ranked

When a variable needs a visual channel, work down this list. Higher entries survive colour-blindness,
mirroring and missing data better.

| Rank | Channel | Carries | Notes |
|---|---|---|---|
| 1 | **Ordinal position** (banded lanes) | categorical / ordinal state | Fastest aggregate read — cluster shape is preattentive. Achromatic, so CVD-proof. Needs a separate gutter for "unknown", never a lane. |
| 2 | **Hex ring sweep** | a quantised magnitude | Arc length decodes well. Omit the ring *and* its track when the value is unknown. |
| 3 | **Mono label inside the mark** | identity | The only channel that separates members of one colour family. Text beats icons below ~16pt — see §4.4. |
| 4 | **Glyph** (`▲ ● ▼ ✓ ✗ —`) | small categorical sets | Per-item, not aggregate. Reads at row height. Precedented in the DS's own `KPITile`. |
| 5 | **Fill vs outline** (`⬢` / `⬡`) | a binary *kind* distinction | Reads as "different sort of thing", **not** as danger. This is how provenance and absence are marked. |
| 6 | **Length / extent** (bars, tracks) | quantised or continuous magnitude | Must be drawn to scale or not at all. The fallback when a ring's diameter is needed for a label. |
| 7 | **Stroke weight** | emphasis | Slow to decode; use for hierarchy, not data. |
| — | ~~Opacity / saturation ramp~~ | — | **Forbidden for data.** `hexCyan` on `slate900` clears the 4.2:1 floor only above ~70% alpha, so the bottom two-thirds of the range is illegible — and `Opacity(0.35)` already means "hasn't spoken yet" in `room_screen.dart`. A dimmed mark reads as *absent*, not *small*. |
| — | ~~Mark size~~ | — | Area decodes poorly, and "small" reads as *weak* rather than *unknown*. |

### Continuous vs ordinal

Prefer **ordinal bands over a continuous axis** whenever the underlying number is model-derived rather than
measured. Placing a mark at x = 0.63 asserts a precision an LLM-sampled score cannot support; three bands
assert only membership. This is CR038 (*prompt instructions are not controls — make it structural*) applied
to a chart: quantise **at the source**, in the schema, not in the renderer.

---

## 3. Honesty rules

These exist because a graphic states things more confidently than prose, and this codebase has a named
failure class for confident wrongness (DEF059: LLM down → fake APPROVE).

1. **Never draw a value you cannot attribute.** If a number was derived, defaulted or substituted
   somewhere upstream, the chart must carry that provenance or must not be drawn. A to-scale ladder of
   prices, two of which the system invented, is worse than a plain list of the same three numbers.
2. **Derived ≠ dangerous.** Mark provenance with fill-vs-outline and a dashed segment. Never amber, never
   `⚠` — those mean *risk*, and a system-supplied default is not a risk, it is a different kind of fact.
3. **Missing is a fourth state, not a middle value.** `null` goes to its own gutter or renders nothing.
   Never `0`, never "neutral", never 50%. Counts and totals are computed over known values only, and the
   caption says how many were known (`9 STATED A VIEW`, not a denominator that always matches the roster).
4. **Recompute, don't receive.** If a widget draws A, B and C, it computes any ratio of A, B and C itself
   from the same values. A ratio accepted from the wire can disagree with the geometry beside it, and then
   the screen contains a visible lie. Mirror the server's formula (`backend/app/trading_math/`) rather
   than trusting its output.
5. **No composite scores without a defensible weighting.** A "consensus 78%" over agents who do not have
   equal authority is a fabricated statistic. If one participant decides, exclude it from the tally and
   say so on the chart.
6. **An error state must not be shaped like a result.** A failed or empty run gets its own visual
   treatment, not the neutral variant of a successful one.

---

## 4. Components

### 4.0 Surface shape — where hexagons are allowed

**Hexagons are marks and controls. Content surfaces are rounded rects.**

This is the rule the app actually follows, and it differs from the design-system mount, which specs
`--clip-angle-panel` (20px cut corners) for "cards, modals, drawers". Nothing in `mobile/lib` does that.
What ships is:

| | Shape | Evidence |
|---|---|---|
| Cards, panels, sheets, inner blocks | **Rounded rect**, `AmiRadii.card` (8) — `AmiRadii.sheet` (12) for the verdict card | `_VerdictCard` `room_screen.dart:906`, `AccentCard` `accent_card.dart:43`, every `journal_detail_screen.dart` block |
| Agent avatars, chips, toasts, bottom nav, track button | **Hex clip** | `hex_avatar.dart`, `hex_chip.dart`, `hex_toast.dart`, `hex_bottom_nav.dart`, `track_hex_button.dart` |
| Segmented / period toggles | **Hex clip**, `FlatTopHexagonClipper(cornerCut: 8)` | `ticker_chart.dart:185` |
| Primary / secondary buttons | **Material 3 default** (stadium) — no `shape:` override anywhere in the Room | `room_screen.dart` |

**The app wins over the mount.** A new surface lives inside these screens, so matching them beats matching
a spec line that nothing implements. It is also the better rule on its own terms: cutting the corners off
every card spends the hexagon on chrome and leaves nothing to distinguish the marks that should carry it.

The standard card is `slate800` fill, 1px `slate700` border, 8px radius, optionally with a 2px accent top
stripe (`AccentCard` — 2px on mobile, 3px desktop). An outcome surface may instead take a 1.5px accent
border on all four sides at 12px radius, which is what `_VerdictCard` does.

*(Flagged: `ami_hex_in_flutter.md` should carry this rule too, so the divergence is recorded where the port
is documented rather than only here.)*

### 4.1 Stat tile (KPI)

The DS's `KPITile` / `MobKPI`, ported. `FlatTopHexagonClipper(cornerCut: 10)` panel, 3px top border in the
status colour, two internal rows:

- **Row 1** — a 56pt outcome hexagon carrying **one glyph**, plus a `labelMono` heading.
- **Row 2** — the number, full width, `AmiTypography.statBig`-class mono, with a dim `labelMono` unit line.

**Never set a multi-word label inside a hexagon.** A flat-top regular hexagon's usable width at the label
line is `0.724` of its bounding box (`hex_clipper.dart:85`, which records `ISLAMIC FINANCE` clipping at
1.15 text scale). The hexagon holds a glyph; the tile holds the words.

`FittedBox(scaleDown)` may wrap the **number** but never a mono label — scaling breaks the letter-spacing
rhythm that makes AMI labels read as labels.

A bare percentage always carries a unit line. `3.0%` beside an approval reads as expected return unless
`OF PORTFOLIO` sits next to it.

### 4.2 Banded comb

N hexagons distributed across 3–4 horizontal bands, one band per ordinal state, plus a gutter for unknown.

- Bands, not vertical lanes — lanes force deep stacks on a phone.
- Group marks by family with a wider seam (2pt intra, 6pt inter). The grouping is a **spatial identity
  cue independent of hue**, which is what actually rescues CVD readers: cyan/green and amber/green
  converge under deuteranopia.
- Width budget on a 390pt device (326pt of content): 26pt cells fit eleven marks with family seams
  (`11×26 + 6×2 + 4×6 = 322pt`). Anything larger overflows.
- Each mark needs a 44pt hit slug regardless of its drawn size.
- Caption the aggregate honestly: how many marks are placed, out of how many that stated a value.

### 4.3 Hex meter — ring or underline bar

**Pick by whether the mark's centre is contested.** A ring is the better meter, but it costs ~9pt of
diameter; if the hexagon also has to carry a label, spend that room on the label and move the magnitude
to an underline bar. Identity beats precision: an unidentifiable mark is not worth a finer read.

#### Underline bar (when the hex carries a label)

A `22×3pt` track beneath the hexagon, filled by length. Same quantisation and the same absence rule as the
ring: **unknown → no bar and no track**. Length is a weaker channel than arc, but it is still a magnitude
channel, and it leaves the whole cell for the label.

#### Ring (when nothing competes for the centre)

A conic sweep clipped to the **same flat-top hexagon** as the mark it surrounds, with a 2.5pt stroke and an
inset cut-out.

- **Hexagonal, not circular.** A circular ring around a hexagon at ≤30pt reads as a circle wearing a hat.
- Costs ~9pt of diameter. At the sizes a phone allows, that is the difference between a labelled and an
  unlabelled mark — see above.
- Sweep starts at 12 o'clock and runs clockwise.
- Track (the unfilled remainder) at ~14% of the accent; sweep at full strength.
- **Unknown → no ring and no track at all.** A ring at 0% is a claim.
- Quantise to three levels. Never print the underlying number beside the ring.
- `_DoughnutPainter` (`widgets/hex/track_hex_button.dart:107`) is the nearest shipped implementation and
  should be generalised rather than duplicated.

### 4.4 Labelling a mark

Colour identifies a **family**, never a member. Wherever several marks share a family colour — which in
this app is the normal case, since colour is assigned by agent family — the mark must carry its own label
or the group is unreadable.

- **Text beats icons at phone sizes.** Below ~16pt only the simplest glyphs (arrows, chevrons, equals,
  a zigzag) survive; ledgers, documents, bubbles and shields become mush, and every icon costs the reader
  a legend for something that already has a name. Reach for a bespoke icon set only when the label would
  not fit at all.
- **Cap the label length to the geometry, and derive it from the existing name.** A second naming scheme
  for the same entities is a divergence waiting to happen; a truncation is not.
- **Size per label length**, not one size for all — 4 characters at 7.5pt with tightened tracking, 2–3 at
  9pt, both scaling with the user's text scale. Let the row wrap rather than clipping.
- **Ink is `slate900` on any accent fill, never white.** Measured: white on `hexAmber` is **1.8:1**, on
  `hexGreen` **2.1:1** — below the 3:1 large-text floor. Dark ink clears 7:1 on all six family fills, and
  since fills are identical in light mode (§6) the same ink serves both themes.
- Centred text gets nearly the hexagon's full width. The `0.724` figure in `hex_clipper.dart:85` applies to
  a label placed **above** centre, where the diagonals cut in — do not apply it to a centred mark.

### 4.5 Magnitude ribbon

A to-scale horizontal track carrying two or three positioned marks (e.g. stop | entry | target).

- 8pt track, ends cut with `FlatTopHexagonClipper(cornerCut: 4)`.
- Segments in status colour at ~45% alpha; the pivot mark solid in `textHigh`, end caps smaller.
- **Split the labels across two rows** — pivot above the track, ends below. On one row they collide
  whenever the pivot falls within ~22% of either end, which is exactly what the interesting cases look
  like.
- Derived values get a **hollow cap and a dashed segment fill**, plus one 9pt mono footnote naming which
  values were derived and by whom.
- **Locked to `TextDirection.ltr`** — see §5.

### 4.6 Existing painters worth reusing

`_PricePainter` / `_VolumePainter` (`widgets/ticker_chart.dart`), `_DonutPainter`
(`screens/sim/portfolio_screen.dart:571`), `_DoughnutPainter` (`widgets/hex/track_hex_button.dart:107`),
`_HexPulsePainter`, `_HexBurstPainter`, `honeycombSlotOrigins()` (`screens/lessons/honeycomb_layout.dart`),
and the seven lesson painters in `widgets/lessons/anim/`. `fl_chart 0.69` is already a dependency —
it has no candlestick widget, which is why the price chart is hand-painted.

---

## 5. RTL

Layout mirrors: bands, rows, legends, axis labels, tile contents. Use `EdgeInsetsDirectional` and
`Row`, never `Stack` with hard-coded `Alignment(x, y)` — the latter fails silently under mirroring.

**A magnitude axis does not mirror.** A ribbon, number line or scale keeps its LTR orientation, because the
numbers on it are themselves LTR and mirroring would put the larger value on the left while its own digits
read left to right.

**Every mono numeric run needs `unicode-bidi: isolate` (CSS) / an LTR-locked span (Flutter).** Measured in
the CR106 prototype: without isolation, `2.8 : 1` renders as `1 : 2.8` under RTL. That is a wrong number,
not a layout nit — and ratios, ranges and `A → B` price pairs are all exposed to it.

Have a native Arabic reader confirm any numeric instrument before it ships. This section is reasoning about
bidi, not a substitute for reading it.

---

## 6. Colour in light mode

`DEVELOPER_PROMPT_LIGHT_MODE.md` is precise about this and it is easy to get backwards:

- **Accent fills keep their tone in both themes.** A cyan hexagon is `#06b6d4` on white as on slate.
- **Only accent *type* darkens** to clear 4.5:1 — `#0891b2` cyan, `#047857` green, `#b45309` amber,
  `#b91c1c` red, `#6d28d9` purple, `#2563eb` blue, `#be185d` pink.

So carry **two tokens per accent**, a fill and an ink, rather than swapping one wholesale. Swapping
wholesale turns every chart fill muddy in light mode — amber marks come out burnt orange — which is the
concrete bug this note exists to prevent.

Dark ground: contrast floor **4.2:1** (`amiCanvasContrastFloor`), with `readableOnCanvas()` applied to any
accent used as type. Fullscreen live charts stay dark in both themes per the DS.

---

## 7. Motion

`Cubic(0.4, 0, 0.2, 1)` at 150 / 200 / 300ms. No bounce, elastic, spring or parallax. **No motion on
text.**

A chart appears with one short opacity fade of the whole figure. Marks must not fly into position,
counters must not tick up, and a segmented control flips its fill rather than sliding a pill — an
orchestrated assembly implies live computation that is not happening. `prefers-reduced-motion` /
`MediaQuery.disableAnimations` removes the fade entirely.

---

## 8. Iconography

Per `README.md:155-168`: no Font Awesome, Heroicons, Lucide, or any icon CDN. The sanctioned vocabulary is
the six brand SVGs, emoji centred inside a hex-clipped frame, and Unicode geometric glyphs — `◆` for
bullets (tinted to the list's accent), `→ ⇒`, `⬢ ⬡`, `✓ ✗`. A line icon that genuinely has no equivalent
is inlined as minimal SVG with `stroke: currentColor` at 2px.

For hexagons, prefer the **clip-path** (`FlatTopRegularHexagon`) over the `⬢` glyph: it scales cleanly,
takes a fill and a ring, and does not depend on a font subset carrying `U+2B22`.

---

## 9. Voice on a chart

`README.md:69-80` applies to every label: declarative, UPPERCASE MONO for labels, badges and eyebrows,
en-dashes for ranges, **numbers over adjectives**. A caption states what the figure shows and what it does
not — `THE PM DECIDES — THIS IS NOT A VOTE` is a caption; *"strong consensus"* is not.
