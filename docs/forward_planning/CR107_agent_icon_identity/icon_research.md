# CR107 icon research — 13 agent identity marks

Design research input for Saiful's decision on CR107. **Not an implementation spec** — no SVG
code, no changes to `agent.dart` or `hex_avatar.dart`, no change to CR107's row status. One section
per role: current abbreviation, 2–3 candidate concepts with a one-line rationale each, an honest
small-size legibility call, and a recommended pick.

Roles are researched **by function**, not by current or renamed label, per the brief — CR160
(proposed, not yet approved) would rename 6 of the 13 roles. Both names are given wherever CR160
touches a role.

---

## 0. DEF154 status — CR107's hold condition, checked against the actual code

**Short answer: not actually clear, and the state is more interesting than "still open."**

CR107 was RULED HELD (Saiful, 2026-07-29) on this condition: *"you cannot honestly judge whether
icons beat letters while the letters are drawn at 3.2px."* Tracing the DEF chain against
`mobile/lib/widgets/hex/hex_avatar.dart` at the current commit (`a8d868b3`, 2026-07-31, clean
working tree):

1. **DEF154 itself is `dropped`** — closed as a duplicate of **DEF142** (commit `23d7729f`,
   AT:R65, 2026-07-29). Same two findings (unfloored `size * 0.16` font ratio, white ink failing
   contrast on family fills), filed a day apart from opposite directions; DEF154's size census and
   its "CR107 can't be decided before this lands" argument were folded into DEF142 rather than lost.
2. **DEF142 shipped fixed** (commit `2c7a1121`, AT:R65, 2026-07-29/30) — `HexAvatar` adopted the
   CR106 comb's canvas-interior treatment (`slate900` interior, family-coloured border, label in
   the family colour) plus a census-derived **4.0px font floor**, with the label suppressed below
   it rather than rendered as a smudge.
3. **DEF206 then reverted it** (commit `a8d868b3`, 2026-07-31, `AT:architect`) — Saiful, on seeing
   the first build carrying DEF142: *"This is what it was looking like before. Revert to this
   design."* The canvas-interior fill read washed out against the dark canvas and made the lock
   glyph collide with the label (`F🔒D`, `M🔒T`). Scope was `hex_avatar.dart` only — the Verdict
   Board's own comb keeps DEF142's treatment. **The revert removed both changes together**: the
   fill/ink went back to solid family colour + white label, *and* the 4.0px font floor was deleted
   in the same commit — `fontSize: widget.size * 0.16` with no floor, `color: Colors.white`, is what
   ships today. Confirmed by reading the current file, not the registers: lines 152–157 are
   byte-identical to the pre-DEF142 state.

**Net effect: the exact defect CR107 named as making the comparison dishonest is live again.**
`lesson_tile.dart:104` (`size: 20`) renders agent initials at **3.2px** today, and white-on-fill
still fails the 3:1 floor on the same three families DEF142/154 measured (`hexAmber` 2.15:1,
`hexCyan` 2.43:1, `hexGreen` 2.54:1). The DEF *IDs* are formally closed/fixed in the registers; the
*widget* is back to the state those IDs were filed against. This isn't an oversight — DEF206 is a
considered founder call for a different reason (brand identity of the solid hex, not contrast
performance) — but it means CR107's own control condition is not substantively satisfied by what's
in the app right now, whatever the register rows say. Worth flagging to Saiful explicitly before
treating "DEF154 landed" as license to compare icons against today's letters.

One separable fact for whoever revisits this: DEF206's commit message objects to the **canvas-interior
fill** specifically (washed out, collides with the lock glyph) — it does not object to the font-size
floor on its own terms. The floor and the fill/ink change were bundled in one revert but aren't
logically coupled; that's a fact for the record, not a recommendation here.

**Secondary note for whoever authors the SVGs:** if icons render on `HexAvatar`'s current solid
family fill (post-DEF206), the same three families that fail white-text contrast — amber, cyan,
green — will pose the same problem for a white/light icon stroke. WCAG's non-text/graphical-object
floor is 3:1, more lenient than text's 4.5:1, but amber (2.15:1) and cyan (2.43:1) still miss even
that with pure white. Check icon-stroke colour per family fill; don't assume white is safe because
DEF142 already measured that it isn't, on three of the six.

---

## 1. Fundamentals Analyst (FUND)

**Function:** financials, intrinsic value, balance sheet, red flags. **Family:** analyst (cyan).
CR160: unchanged.

1. **Ledger grid** — a small 2×2 or 2×3 bold-stroked cell grid, like a miniature spreadsheet/balance
   sheet. Depicts "financial statement" directly. *Precedent:* Material Symbols ships
   `table_chart` / `request_quote` for exactly this; QuickBooks/Xero-style accounting UIs use a
   ledger-grid glyph for "accounts"/"statements."
2. **Magnifying glass over a bar or coin stack** — "scrutinizing the numbers." *Precedent:*
   magnifying glass = analysis/screening, near-universal (Finviz-style screener icons).
3. **Column/pillar pictogram** (simplified temple column) — "fundamentals = the foundation."
   Weakest of the three: reads generically as "institution/bank," not specifically "analyst."

**Small-size risk:** LOW for the grid if capped at 4 cells with heavy dividers (more cells reads as
a hash/waffle at 26pt); MEDIUM for the magnifying glass — its thin circle-and-handle construction is
close to the kind of delicate line-work CR107 flagged as blobbing.

**Recommended: ledger grid.** Distinct blocky silhouette that survives compression, doesn't compete
with MKT's candlesticks or TRADE's ticket, and is the more specific referent (magnifying glass reads
as generic "search/analysis," used everywhere, not analyst-specific).

---

## 2. Market Analyst (MKT) — CR160: Technical Strategist (TECH)

**Function:** charts, indicators, patterns, levels. **Family:** analyst (cyan).

1. **Candlestick pair** — two candle bodies (solid filled rects), one tall one short, with short
   thick wick nubs (not full-height thin lines). *Precedent:* this is a **named glyph** —
   `candlestick_chart` in Material Symbols — and the default chart-mode icon across TradingView,
   Bloomberg, and most retail trading apps.
2. **Zigzag trend line with a breakout marker** — a jagged price line crossing a short horizontal
   level line. Depicts "levels/patterns" more specifically than candlesticks, but less
   instantly-recognizable as "market analysis" at a glance.
3. **Simple ascending line-chart with a peak** — closest to `show_chart`; very generic, risks
   reading as "any metric going up" rather than "technical analysis" specifically.

**Small-size risk:** LOW for candlesticks *if drawn as solid bars, not thin outlined rects with
separate wick strokes* — that distinction is exactly what makes Material Symbols' own
`candlestick-chart` glyph hold up at small sizes. MEDIUM-HIGH for the zigzag+level version — thin
crossing lines are a repeat of CR107's failure mode.

**Recommended: candlestick pair**, bodies as solid fills. Strongest real-world precedent for this
exact function, distinct silhouette from FUND's grid and TRADE's ticket, and survives the CR160
rename to "Technical Strategist" without needing to change (arguably reads *more* precisely under
that name than under "Market Analyst").

---

## 3. News Analyst (NEWS) — CR160: Macro & Events (MACRO)

**Function:** macro events, headlines, regulatory news. **Family:** analyst (cyan).

1. **Folded newspaper** — a rectangle with a folded top-corner triangle and **one** bold headline
   bar (not multiple thin text-lines). *Precedent:* newspaper is the standard "news" glyph across
   icon sets; most financial-news apps (and Bloomberg's own terminal branding) lean on
   newspaper/broadsheet imagery.
2. **Megaphone** — "macro events being announced." *Precedent:* Material Symbols `campaign`, common
   for announcements/alerts dashboards. Reserved here for SOC instead (see §4) to avoid an
   outbound-broadcast mark on an inbound-analysis role.
3. **Globe with a small alert dot** — "world events." More abstract, weaker at small size (globe
   line-work — meridians/parallels — is detail-heavy, a repeat failure mode).

**Small-size risk:** LOW for the newspaper *if reduced to 3 shapes max* (body rect, folded corner,
one bold headline bar) — the standard newspaper glyph's usual 3–4 body text-lines will vanish or mush
together well before 26pt.

**Recommended: folded newspaper**, simplified to 3 shapes. Most literal fit, clean under either
name (NEWS or "Macro & Events" both read as "the newspaper agent"), and doesn't compete with SOC's
speech-bubble.

---

## 4. Social Media Analyst (SOC) — CR160: Flow & Positioning (FLOW) / open decision "Sentiment & Flow"

**Function:** sentiment, crowd mood, retail positioning. **Family:** analyst (cyan).

1. **Speech bubble with a small pulse/wave mark inside** — "reading crowd sentiment."
   *Precedent:* sentiment-analysis dashboards (Vista Social, Brandwatch-style tools) tag
   conversations with a bubble-plus-sentiment-mark convention.
2. **Cluster of 3 small dots/circles of varying size** — "the crowd," abstracted.
   *Precedent:* close to Material Symbols `groups`. Reads as "many people" more than "sentiment,"
   a slightly less precise fit for a role that measures *mood*, not headcount.
3. **Megaphone** — freed up by giving NEWS the newspaper (see §3). Reads as *outbound* broadcast,
   which is a directional mismatch for a role that's *reading* the crowd, not addressing it.

**Small-size risk:** LOW. A bubble silhouette (rounded rect/oval + tail) stays legible even if the
inner mark degrades or drops entirely at the smallest sizes — the shape alone still reads as
"conversation," which is a good robustness property CR107's failed marks didn't have.

**Recommended: speech bubble with an internal pulse/wave.** Best functional fit, most robust
degradation curve. Flagged below (§ Cross-role confusion) against CNC, which also has a
speech-bubble candidate — pick different bubble silhouettes if both ship.

---

## 5. Bull Researcher (BULL)

**Function:** builds the long case. **Family:** researcher (purple). CR160: unchanged — Saiful,
2026-08-08: *"Keep bull and bears, they are market jargons."*

1. **Simplified bull-head silhouette** — rounded head wedge + two curved upward horn strokes, 2–3
   strokes total, no eye/nostril detail. *Precedent:* the dominant convention across finance
   iconography — the Wall Street Charging Bull, and every trading icon set surveyed (icons8, iStock
   "bull market icon" results) renders bull/bear as literal animal silhouettes, not abstractions.
2. **Upward diagonal wedge with horn-like flourishes** — a hybrid abstraction, less literal.
3. **Plain up-chevron/arrow** — rejected: too generic, risks blending with the up/down arrow motif
   the app likely already uses for P&L and price-change indicators elsewhere.

**Small-size risk:** MEDIUM — must hold to 2–3 strokes (rounded head + two horn curves) or it
repeats CR107's blob failure. This is the harder of the two animal marks to keep clean, since horns
read thin at small stroke weight.

**Recommended: simplified bull-head.** Matches the settled real-world convention, gives BULL/BEAR a
shared "animal pair" visual language that's mutually reinforcing rather than competing, and an
animal pictogram carries no text — CR160's finding that "bull/bear" doesn't transcreate to AR/MS
(reads as a literal animal, hence the label change to Long-Side/Short-Side) is explicitly a
*label* problem, not an icon one; the icon needs no re-translation.

---

## 6. Bear Researcher (BEAR)

**Function:** builds the short/avoid case. **Family:** researcher (purple). CR160: unchanged.

1. **Simplified bear-head silhouette** — rounded snout wedge + two small rounded ear bumps close to
   the head, matched stroke-count to BULL's mark for a deliberate visual pairing. Same precedent
   basis as BULL (§5).
2. **Three short parallel diagonal claw-slashes** — abstracted "bear claw," no literal head.
   Distinct from bull's rounded-horn silhouette, avoids drawing an animal at all.
3. **Plain down-chevron** — rejected for the same reason as BULL's arrow option.

**Small-size risk:** MEDIUM — same discipline as BULL: 2–3 strokes only, no fur/texture detail.

**Recommended: simplified bear-head**, matched to BULL. Rounded ears set close to the head vs.
pointed horns rising off it is a strong, well-established silhouette contrast (it's how virtually
every existing bull/bear icon pair differentiates them) — this is a solved design problem, not a
novel risk, **provided the pair gets deliberate hand-authoring attention** since it's the sharpest
test of CR107's "distinguishable as a set" acceptance criterion. Mitigating factor: per CR107's own
sizing rule, this pair never renders below 44pt in the current scope (26–32pt surfaces stay
letters), which meaningfully de-risks it versus a bare 26pt worst case.

---

## 7. Research Manager (RES-M)

**Function:** adjudicates Bull vs Bear, writes synthesis. **Family:** manager (purple). CR107's own
first draft failed here — *"a hook that means nothing."* Avoid anything hook/curve-shaped with no
clear referent.

1. **Scales of justice** — a bold T-shaped beam with two small solid discs (not hanging
   chains/pans with fine linework). Depicts "weighs both sides" directly — the literal function.
   *Precedent:* Material Symbols `balance`; scales are the standard "weigh two sides / compare"
   glyph in finance UX generally.
2. **Gavel** — "issues the ruling." Strong precedent (Material Symbols `gavel`) but reserved for PM
   instead (§8) — gavel implies *final* ruling, closer to PM's "approves or rejects" than to RES-M's
   *adjudicates-then-synthesizes* function. Using it here would also leave PM without its own
   distinct "judgment" mark.
3. **Two arrows converging into a checkmark** — "two cases merged into one verdict." More abstract;
   reads closer to a generic software "merge" icon than a finance-specific mark. Weaker precedent.

**Small-size risk:** HIGH if drawn literally (hanging pans + thin center post + chains is exactly
the multi-thin-line construction CR107 warned about — this is the direct redraw target for the
failed "hook"). LOW-MEDIUM if simplified to a bold T-beam + two solid discs.

**Recommended: simplified scales**, bold T-beam + two discs, no hanging linework. Precise functional
fit and clearly a *redraw*, not a repeat, of the failed hook. **Flagged below** against NEU's
"balances aggressive vs conservative" — the two functions are conceptually adjacent enough that a
scale-family glyph is tempting for both; keep RES-M's mark exclusively scale-shaped and steer NEU
toward a different silhouette (§10).

---

## 8. Portfolio Manager (PM) — CR160: Chief Investment Officer (CIO)

**Function:** final call, approves or rejects against the user's mandate. **Family:** manager
(purple). CR107's own first draft failed here — *"an arch that says nothing."* Avoid anything
architectural/arch-shaped with no clear referent.

1. **Shield with a checkmark** — the mandate as a boundary, the check as approval. *Precedent:*
   shield = protect/guard/compliance (Material Symbols `shield`, `verified_user`), and it ties
   directly into this app's own language for the role — "mandate enforcement," the "uncoachable"
   safety floor (`docs/initial_specs/…decision_log.md`). The concept depicts the *function*
   ("approve/reject against a boundary"), not the job title, so it survives the CR160 rename to CIO
   unchanged — arguably reads *more* precisely for a CIO ("guards capital within a mandate") than
   for "Portfolio Manager."
2. **Stamp/seal with a checkmark** — "final approval stamp." *Precedent:* Material Symbols
   `verified`/`task_alt`. Simpler at tiny sizes than a shield outline (a circle survives compression
   better than a 5-point shield silhouette) but less tied to the product's own mandate language.
3. **Gavel** — "final ruling." Strong standalone precedent but not recommended here because it
   duplicates the "judgment" vocabulary RES-M already owns via scales (§7); splitting "adjudicates"
   (scales) from "approves/rejects" (shield) keeps the two management roles visually and
   conceptually distinct rather than both reaching for "justice" imagery.

**Small-size risk:** LOW-MEDIUM. Shield-plus-check reduces well: at the smallest sizes, drop the
checkmark to a simple diagonal notch, or drop it entirely — the shield silhouette alone is still
distinct from every other mark in the set and still reads as "guard/approve." This directly avoids
repeating the "arch that says nothing" failure since a shield has a specific, near-universally
legible referent an arch does not.

**Recommended: shield with checkmark.**

---

## 9. Aggressive Debator (AGG) — CR160: Risk Officer — Aggressive

**Function:** argues for risk-on. **Family:** risk (amber). Part of the three-debator set flagged
by name in the brief as a confusion risk — see § Cross-role confusion for the design decision that
shapes all three.

1. **Jagged upward bolt/spike** — a sharp zigzag rising steeply, lightning-bolt-adjacent but
   distinctly "spiking price action" rather than a generic lightning glyph. Deliberately **not**
   sharing a base shape with CON/NEU (see below).
2. **Speedometer/gauge with the needle pinned hard over** — "risk dial maxed out." *Precedent:*
   gauge/risk-meter is the standard convention in robo-advisor risk-tolerance UX (Betterment/
   Wealthfront-style sliders, and the "risk spectrum" language used across Schwab/Saxo/Security Bank
   investor-profile pages). **Not recommended as the base for all three** — see confusion flag.
3. **Flame** — casual-app shorthand for "hot/aggressive," weaker institutional-finance precedent
   than the other two.

**Small-size risk:** LOW for the bolt (few strokes, high contrast, no fine detail) — the strongest
argument for it over the gauge.

**Recommended: jagged upward bolt.** Chosen specifically to avoid the shared-dial-plus-rotating-
needle pattern (see § Cross-role confusion) — trades some "risk spectrum" elegance for certain
distinctiveness from its two siblings, which matters more given CR107's own history of failed marks
at exactly this size class.

---

## 10. Conservative Debator (CON) — CR160: Risk Officer — Conservative

**Function:** argues for capital preservation. **Family:** risk (amber).

1. **Turtle silhouette** — the standard "slow and steady/careful investing" idiom in retail-investing
   UX. Gives CON an animal-family mark, echoing BULL/BEAR's visual language without colliding with
   them (different family colour, different context).
2. **Gauge with the needle pinned low** — shares the same shared-dial problem as AGG's option 2;
   not recommended as the set's base shape (see confusion flag).
3. **Padlock/vault door** — "locking in value." **Rejected outright, not just de-prioritized:** this
   app already uses a padlock (`Icons.lock`) as the universal *locked-agent* overlay badge on every
   `HexAvatar`. Giving CON its own padlock identity mark would visually stack with — and be
   confusable with — that existing chrome on CON's own hex whenever it's actually locked. Don't use
   a padlock for any agent's identity mark.

**Small-size risk:** LOW-MEDIUM for the turtle — a rounded shell dome + short leg nubs holds up well
if kept to 3–4 shapes; risk rises if shell-pattern detail (segments/hexagons on the shell) is added.

**Recommended: turtle.** Most legible and immediately recognizable of the three options, avoids the
shared-dial pattern, and sidesteps the padlock collision entirely. Same AR/MS caveat as bull/bear
applies in principle (an idiom may not transcreate as text) — but again, that's a *label* question;
CR160's finding is specifically about naming, not about pictograms.

---

## 11. Neutral Debator (NEU) — CR160: Risk Officer — Balanced (BAL)

**Function:** balances aggressive vs conservative. **Family:** risk (amber).

1. **Two arrows converging to a center point** (⇌-style, or a short "=" flanked by tick marks) —
   "balance point between two extremes." Deliberately **not** a literal scale, to avoid colliding
   with RES-M's mark (§7) despite the conceptual closeness of "balances two sides" and "adjudicates
   two sides."
2. **Gauge with the needle centered** — completes the shared-dial pattern with AGG/CON; not
   recommended as the base shape (see confusion flag).
3. **Minimalist single-fulcrum balance beam** (one bar, one center-triangle support, no hanging
   pans) — still balance-family, but visually closer to RES-M's scales than option 1; higher
   residual collision risk even with careful differentiation.

**Small-size risk:** LOW for the converging-arrows mark — two short diagonal strokes meeting a
center point is a simple, high-contrast shape.

**Recommended: converging arrows.** The clean silhouette-level differentiator from RES-M's scales;
recommended over the beam variant (option 3) specifically because option 3 keeps too much visual DNA
in common with §7's mark to trust at a glance.

---

## 12. Trader (TRADE) — CR160: Execution Desk (EXEC)

**Function:** translates synthesis into a trade idea. **Family:** execution (green). CR107 flagged
the first draft's plain right-arrow as generic (not a hard failure, but named as needing a redraw).

1. **Order-ticket glyph** — a small rectangle with a 2–3-dot perforated edge and one bold internal
   tick/arrow. "Order ticket" is literal trading-desk vocabulary — this is what a real trade ticket
   *is*. Visually unlike anything else in the set (nothing else uses a perforated-rectangle shape).
2. **Arrow through a target ring** — "execute / hit the target." *Precedent:* target+arrow is a
   common "achieve/execute" motif (Material Symbols `target`, `bolt` for instant-execution
   contexts). More components than the ticket, so more to compress at small size.
3. **Plain right-arrow** — explicitly the option CR107 already flagged as too generic; kept here
   only to name it as the one to avoid.

**Small-size risk:** LOW-MEDIUM for the ticket if the perforation is capped at 2–3 dots (a full
dashed line vanishes) and the internal mark is one bold stroke, not multiple.

**Recommended: order-ticket glyph.** More specific than a target+arrow, on-domain vocabulary, and it
survives — arguably improves under — the CR160 rename to "Execution Desk" (a desk processes
tickets). Even a silhouette-only read (rectangle + notch) still says "document/ticket," which
degrades more gracefully than an arrow does when compressed.

---

## 13. AMI Concierge (CNC)

**Function:** personal assistant — lessons, journal, scheduling. **Family:** concierge (pink). The
13th mark, outside the Room agent-graph proper.

1. **Crossed keys** — the actual, internationally recognized concierge emblem (Les Clefs d'Or, the
   worldwide hotel-concierge association, uses crossed golden keys as its literal badge).
   *Precedent:* this is a real-world, on-the-nose symbol for the specific word "Concierge" — stronger
   and more differentiated than generic AI-assistant iconography, which every chatbot app already
   uses and which would undercut the deliberately-chosen brand name by reading as "just a chatbot."
2. **Speech bubble with a sparkle/star inside** — generic AI-assistant convention. *Precedent:*
   Material Symbols `assistant`/`smart_toy`, and most consumer AI products use a sparkle-in-bubble
   motif. Flagged against SOC's speech-bubble candidate (§4) — if both ship, they need visibly
   different bubble silhouettes (e.g., rounded-rect chat bubble for CNC vs. oval tail-bubble for
   SOC) to avoid a same-family-shape collision, and CNC isn't even in the same colour family as SOC
   (pink vs. cyan), which helps but shouldn't be relied on alone.
3. **Hex/star badge with a sparkle** — generic "special/featured" badge; weakest option, risks
   reading as a rating/rank mark rather than an identity mark (the league screen likely already uses
   star/rank iconography elsewhere in the app).

**Small-size risk:** MEDIUM for crossed keys — thin bows (the round part) and shafts need to render
as bold single-line shapes with at most 1–2 tooth notches on the blades, or the pair collapses into
an ambiguous X/asterisk at 26pt. Genuine redraw discipline required, comparable to bull/bear.

**Recommended: crossed keys.** Strongest, least generic, and least confusable precedent of the
three — zero shape overlap with any of the other 12 marks (nothing else in the set uses key
shapes), and it's specific to the product's own chosen name rather than borrowed generic-assistant
vocabulary.

---

## Cross-role confusion flags

Ranked by severity, for whoever briefs the SVG author:

1. **Aggressive / Conservative / Balanced (Risk Officers) — highest risk in the set.** Same family
   colour (amber) on all three, and the textbook design move — one shared gauge/dial base with the
   needle rotated per role — is exactly the highest-collision pattern possible: three marks
   differing only by a small rotation, on identical colour, is a harder discrimination task at 44pt
   (let alone 26pt) than anything else proposed here. **This research recommends explicitly not
   doing that** — bolt (AGG) / turtle (CON) / converging-arrows (NEU) gives each a genuinely
   different silhouette family instead of a shared base. Even so, this trio has zero colour help
   (identical family fill) and should get the most scrutiny against CR107's Acceptance §1
   ("distinguishable as a set at 56pt, by someone who hasn't seen the legend") of anything in the
   roster — test this specific triple first if only one group gets user-tested before a full draw
   pass.
2. **Research Manager vs. Neutral/Balanced Debator — conceptual collision, not just visual.**
   "Adjudicates Bull vs Bear" (RES-M) and "balances aggressive vs conservative" (NEU) are close
   enough in wording that both naturally pull toward scale/balance imagery. Recommended split here
   (scales for RES-M, converging arrows for NEU) avoids a literal shape clash, but whoever briefs
   the SVG author should say this explicitly rather than leave it to be discovered mid-draw — a
   designer working from the function description alone, without seeing this note, could easily
   reach for a scale glyph on both.
3. **Bull vs. Bear — the expected, well-precedented pair.** Same family colour (purple), and this is
   the pairing the brief calls out by name. Lower actual risk than it looks: the horns-vs-ears
   silhouette contrast is the settled real-world convention for exactly this pair (every bull/bear
   icon pair surveyed uses it), and per CR107's own sizing rule this pair never has to work below
   44pt in the current scope. Still deserves careful hand-authoring since it's the most-precedented
   pair to get *lazy* about, drawing both from the same template with only the horns/ears swapped.
4. **Social Media Analyst vs. AMI Concierge — bubble-motif overlap, low-moderate.** Recommending
   crossed keys for CNC (§13) removes this collision outright. If crossed keys is rejected in favour
   of the generic assistant-bubble alternate, it must use a visibly different bubble silhouette than
   SOC's, not just a different inner glyph — different family colours (cyan vs. pink) help but the
   shape language would otherwise be the same "rounded box with a tail."
5. **Portfolio Manager vs. Conservative Debator — protection-imagery overlap, avoided by
   construction.** Both functions could reach for "protect/guard" imagery (shield, vault, padlock).
   Recommended picks keep shield exclusive to PM and steer CON to a turtle instead, specifically to
   avoid this. Separately and more importantly: **no agent identity mark should use a padlock at
   all** — the app already uses `Icons.lock` as the universal locked-agent overlay on every hex, so
   a padlock identity icon would collide with the app's own existing locked-state chrome, not just
   with another agent's mark.
6. **Fundamentals Analyst vs. Market Analyst — low risk, noted for completeness.** Both are the
   "quantitative-looking" pair in the analyst family (grid vs. candlesticks), same cyan fill, same
   size class. The two silhouettes are genuinely distinct (a cell grid vs. a pair of solid bars), so
   this is a light flag rather than a real risk — included because they're adjacent in every list
   this research produced and worth a side-by-side glance once drawn.

---

## Precedent sources consulted

General trend confirmation via web search (queried 2026-08-12; results are icon-marketplace listings
and named glyphs, not endorsements of any specific vendor or library — cited for the *convention*,
not for a component to import, consistent with the DS's no-icon-CDN rule):

- Bull/bear as literal animal silhouettes being the dominant finance-icon convention:
  [icons8 bull-and-bear-trading set](https://icons8.com/icons/set/bull-and-bear-trading),
  [iStock "bull bear icon"](https://www.istockphoto.com/illustrations/bull-bear-icon)
- Candlestick chart as a named, standard glyph:
  [Material Symbols `candlestick-chart` via Iconify](https://icon-sets.iconify.design/material-symbols/candlestick-chart/)
- Risk tolerance as a conservative→aggressive spectrum/dial, the standard framing in investor-risk
  UX: [Schwab, "A Guide to Risk Profiles"](https://www.schwab.com/learn/story/guide-to-risk-profiles),
  [Saxo, "Understanding risk tolerance"](https://www.home.saxo/learn/guides/start-investing/understanding-risk-tolerance),
  [Security Bank, "Mapping UITFs on the Risk Spectrum"](https://www.securitybank.com/blog/mapping-uitfs-on-the-risk-spectrum-conservative-to-aggressive/)
- AI-assistant iconography convention (sparkle-in-bubble, `smart_toy`, `support_agent`):
  [Material UI "Support agent" icon](https://materialui.co/icon/support-agent),
  [Material UI "Smart toy" icon](https://materialui.co/icon/smart-toy)
- Sentiment-tagged conversation bubbles as the standard "reading crowd mood" convention:
  [Vista Social, "Social Media Sentiment Analysis Dashboard"](https://vistasocial.com/insights/social-media-sentiment-analysis-dashboard/)

Design-system precedent (read directly, not searched):

- `/Volumes/Extreme Pro/AMI AI Design System/README.md:155-168` — the DS's own iconography rule:
  6 hand-authored SVGs first, emoji second, unicode glyphs third; **no icon CDN**; a genuinely new
  line icon should be "a minimal SVG path with `stroke: currentColor` and 2px stroke-width."
- `/Volumes/Extreme Pro/AMI AI Design System/assets/icon_ami.svg`, `icon_atm.svg`, `icon_credit.svg`,
  `icon_debit.svg` — the DS's existing product marks are hex-clipped badges with an **emoji**
  glyph centered inside, not hand-drawn vector icons. Useful negative precedent: the DS has never
  actually hand-authored a *set* of role-specific vector icons before; CR107 would be the first.
- Real-world concierge emblem (crossed keys, Les Clefs d'Or) — general knowledge, not a search
  result; flagged here as a claim to verify visually before drawing, not asserted as sourced from a
  cited page.

Standard associations used without a specific citation (gavel = ruling, shield = protection/
compliance, scales = weighing two sides, newspaper = news, magnifying glass = analysis, speech
bubble = conversation/sentiment, ticket = order/trade) are treated as common-knowledge iconographic
conventions, consistent with how Material Symbols names its own glyphs for the same concepts
(`gavel`, `shield`, `balance`, `newspaper`, `search`, `chat_bubble`, `receipt_long`) — cited above
where a specific glyph name was confirmed via search, otherwise noted as convention rather than
invented.
