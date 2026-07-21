# CR058 — Sharia-compliant investing: a first-class Islamic-finance strand

**Status:** planned — **dispatch-ready single-module CR** (architect / education lane implements) · **Session:** AT:R63 · **Filed:** 2026-07-21

> Origin: spun out of **CR054** (the BOK master plan), gap **G8** / module **M25**. Saiful:
> *"The architects are still busy with CR054, so either fold it into the next CR if it's related,
> otherwise create a new CR."* CR055 (room holdings) and CR056 (no-assumed-data) are unrelated, so
> this is a **new, self-contained CR** the education lane can pick up independently — without
> re-opening the in-flight CR054 umbrella.

---

## 1. Why this exists (the gap, precisely)

AMI **gates trades on a `halal` mandate flag but never teaches Islamic finance.** Verified state
of the corpus (2026-07-21):

- **Zero** dedicated lessons on Sharia-compliant investing.
- The `halal` flag appears only as an **app-feature mention** in ~11 lessons (the PM's
  deterministic compliance check — `271`, `272`, `273`, `291`, `253`, …). Those teach *that the
  toggle exists*, not *what it screens for*.
- **Two incidental asides** inside the in-flight fixed-income batch: `303_why_bonds_exist` frames
  **sukuk** as "the Islamic-finance-compliant version of a bond … structured to avoid interest
  (riba)"; `307_credit_spreads_and_ratings` notes sukuk pricing over Malaysian Government
  Securities. Both are one-liners inside bond lessons.
- **Zero** glossary terms, **zero** daily challenges, **one** platform Q&A ("Is there a halal
  filter?" — about the toggle).

So the mandate promises a halal screen the user is never taught to understand or verify. For a
product whose target markets are **US + Bursa Malaysia + GCC/Tadawul**, where a large share of
listed equities are Shariah-screened and Islamic finance is a primary framework, this is a
first-class gap — not a niche. This CR makes it a taught subject.

## 2. Relationship to work already in flight

CR054 is being actively built. The untracked batch in the tree (lesson IDs **300–322**) already
uses the exact scheme CR054 proposed — `track: "asset_classes"`, `code: "ASST n"`, `level: 9`,
`sources: []`, module 13/14/15 for fixed income / funds / options. This CR **depends on and builds
on** that batch:

- Lesson *"Sukuk vs conventional bonds"* extends `303–309` (bonds/rates). **Do not restate bond
  basics** — reference them (and, once CR053 lands, deep-link them).
- Lesson *"Islamic indices, ETFs & funds"* extends `310–315` (funds/vehicles).
- The *"halal mandate flag"* lesson extends `271`/`272`/`273` (the deterministic compliance check).

**Sequencing:** land after the `300–322` batch is committed, so its prerequisites exist and IDs
don't collide with active WIP (see §6).

## 3. What "best-in-class" Islamic-finance content covers

Benchmarked to the recognized standards — **AAOIFI Shariah Standards**, **Bursa Malaysia Shariah
Advisory Council (SAC)** methodology, the **Dow Jones Islamic Market / S&P Shariah / MSCI Islamic /
FTSE Shariah** index rulebooks — and the standard literature (Usmani, *An Introduction to Islamic
Finance*; El-Gamal, *Islamic Finance: Law, Economics, and Practice*). Taught in AMI's voice:
analyst-to-analyst, numbers over adjectives, falsifiable, simulation-framed.

### 3.1 Proposed module — M25 "Sharia-compliant investing"

Foundation lessons (IDs assigned at build time per §6; codes per §5). Counts are shape, not a hard
target.

| # | Lesson | Teaches | Builds on / ties to |
|---|---|---|---|
| 1 | **The four prohibitions** | *riba* (interest), *gharar* (excessive uncertainty), *maysir* (gambling), *haram* business activity — and the underlying **risk-sharing over risk-transfer** principle | foundation |
| 2 | **The business-activity screen** | qualitative sector exclusions (alcohol, tobacco, pork, gambling, conventional banking/insurance, weapons, adult content, non-halal food) with real tickers that fail | lesson 1 |
| 3 | **The financial-ratio screens** | the quantitative thresholds — **debt / market cap < ~33%**, **cash + interest-bearing securities / market cap < ~33%**, **non-compliant (interest) income < ~5% of revenue**; worked on a real ticker (e.g. does AAPL's cash pile pass?) | ratios (FUND track), **CR046 math** |
| 4 | **Standards differ — why the same stock flips** | AAOIFI vs SAC (Malaysia) vs Dow Jones Islamic vs S&P/MSCI/FTSE; trailing-vs-market-cap denominators; why Malaysia is more lenient than the GCC; **compliance drift** as debt rises | lesson 3 |
| 5 | **Purification (*tazkiyah*)** | cleansing the impermissible income fraction of dividends; how to compute the purification amount; where it goes | lessons 1, 3, **CR046 math** |
| 6 | **Sukuk vs conventional bonds** | asset-based/asset-backed structures; how return is generated without riba; the *"is it really asset-backed?"* critique | **extends `303–309`** |
| 7 | **Islamic contracts & instruments** | *murabahah* (cost-plus), *ijarah* (leasing), *musharakah* (partnership), *mudarabah* (profit-share), *takaful* (Islamic insurance) — and their conventional analogues | lesson 6 |
| 8 | **Islamic indices, ETFs & funds** | Sharia-compliant ETFs (e.g. SPUS, HLAL, iShares MSCI Islamic), index methodology, tracking/expense, Bursa Malaysia-i | **extends `310–315`** |
| 9 | **How AMI's `halal` flag maps to real screening** | what the PM's deterministic `is_halal_compliant` check *represents* (the two-stage screen), why a ticker can flip compliant→non-compliant, reading the Verdict's halal PASS/BLOCK | **extends `271`/`272`/`273`** |
| 10 | **Capstone — screen a company end to end** | synthesis: pick a real ticker, run the business screen + the three ratios + name the standard + decide; synthesis quiz | all of the above |

Woven-in misconceptions (not separate lessons): *"it's just no-alcohol-stocks"* (the ratios do
most of the work); compliance is **not permanent**; crypto/DeFi halal debate as an edge case; the
gap between screening a stock and endorsing it.

### 3.2 Mirror across the other three corpora (mandatory — or the Concierge stays blind)

- **Glossary** — new category **`islamic_finance`** (~20 terms): riba, gharar, maysir, halal,
  haram, sukuk, ijarah, murabahah, musharakah, mudarabah, takaful, tazkiyah/purification, AAOIFI,
  Shariah Advisory Council, Dow Jones Islamic Market Index, Sharia screening, business screen,
  financial screen, Sharia-compliant, Islamic ETF. (Today: **0** Islamic terms in 188.)
- **AI-coach Q&A** (~15): *"Is [ticker] halal?"*, *"What does AMI's halal filter actually check?"*,
  *"Why did a stock stop being halal?"*, *"Is a sukuk the same as a bond?"*, *"Which Sharia standard
  does AMI use?"*, *"Do I need to purify my dividends?"*, *"Is crypto halal?"*
- **Daily challenges** (~10): spot-the-non-compliant-stock, screen-this-balance-sheet, sukuk-vs-
  bond, which-standard-applies. Reuse existing types (`spot_the_violation`, `whats_missing`) or add
  a `screen_the_stock` type (with its own guards if added).

## 4. Track decision (architect confirms, consistent with CR054 §4.2)

Islamic-finance screening is a **values/rules discipline tied to a Mandate flag** — the same shape
as **ESG** (CR054 M26, which also maps to a mandate flag). Recommendation:

- **Preferred:** a dedicated **`mandate_compliance`** track housing M25 (Islamic) + M26 (ESG),
  speakable CR044 prefix (proposal: **`SCRN`** — "screen"; architect finalises the one-dict prefix
  per CR044 rules). Rationale: both teach *"screen a universe against your stated values"*, which
  is exactly what the Mandate is; keeping them in `fundamentals_analysis` would blur the track
  facet the way CR054 warns against.
- **Fallback (low-friction):** fold into **`fundamentals_analysis`** (screening is ratio work) —
  lessons carry `FUND` codes. Acceptable if Saiful doesn't want a new track yet.

Wiring touch-points if the new track is chosen (same list as CR054 §4.2): `track` enum
(`backend/app/schemas/lessons.py`), display-name + prefix maps (`lessons_service.py:69-90`), mobile
`_trackShortLabel` (`track_lessons_screen.dart:20-28`), glossary category enum, corpus-integrity
test. Additive — no existing CR044 code changes, so DEF068/DEF071 stay safe. **Agent gateways stay
fixed at 5**; these lessons may be `agent_callouts` for `fundamentals_analyst` / `portfolio_manager`
but do not alter any gateway set.

## 5. Frozen-code + numbering rules (CR044)

- New lessons take the **next free number in the chosen track** (`SCRN 1…` or the next free `FUND
  n`). Never reuse or reassign a code.
- The in-flight batch shows the convention to match (`ASST 1`, `ASST 14`, `sources: []`,
  `level`/`module` populated). New lessons follow it verbatim.

## 6. ID assignment (avoid collision with active WIP)

Highest lesson id in the tree is **322**, and the `303–322` batch is **untracked WIP** that may
extend further as CR054's later waves (macro, portfolio, quant, discerning-CEO) are authored.
Therefore: **do not hard-code IDs in this CR.** At build time, assign the **next free contiguous
block after the CR054 asset-class/funds/options batch is committed**, so sukuk/ETF prerequisites
exist and no id collides with in-flight authoring.

## 7. Constraints honoured (non-negotiable)

- **Not a religious ruling.** AMI teaches the **published screening methodology** and reflects the
  named standards (AAOIFI / SAC / index rulebooks); it does **not issue fatwa or Sharia rulings**
  and defers to qualified scholars and the user's own Sharia authority. Every lesson carries this
  the way other lessons carry "not investment advice" — a load-bearing frame, structural not
  decorative. Where standards disagree, present the disagreement; never adjudicate it.
- **Simulation-only, forever.** Screening is taught as **literacy**; the app's `halal` flag is a
  **training constraint the PM enforces on simulated Verdicts**, never a real-money halal
  certification and never "act on this."
- **AMI by name** in user-facing copy; **LLM** only in code.
- **CR046 computational rigor.** The ratio screens (debt/market-cap, cash/market-cap, interest-
  income %) and the purification amount are **computed via `trading_math/`**, not hand-authored —
  a wrong screening number is worse than none. Open the CR046 ledger entries with guard tests.
- **CR044 codes frozen / contiguous**; **gateways fixed at 5**; **DEF064/DEF065 quiz invariants**
  (multiple-choice only, options required, no numeric option references, answer position varied);
  **degrade loudly** (new track/category fails a corpus test, not a user's screen).
- **Authoring prompt.** Extend `content/_authoring/lesson_authoring_prompt.md` with the Islamic-
  finance domain, the "not a Sharia ruling" frame, the new glossary category, and the standards to
  cite — so any AI tool generating a batch stays on-spec.

## 8. Guards (land with the content — house rule)

Extend `backend/tests/unit/test_lesson_corpus_integrity.py`:
- new prefix (if `SCRN`) present/unique/prefix-matches-track/contiguous 1..N;
- every Islamic-finance lesson resolves its prerequisites (esp. the bond/fund lessons it builds
  on) — fail loudly if built before the `300–322` batch is committed;
- glossary `islamic_finance` category is in the enum; every `related_lessons` id resolves;
- the CR046 screening/purification calcs have their own math guard tests (shown == computed).

## 9. Registers

- Row added to `docs/forward_planning/cr_list.md` (CR058, `planned`).
- **Parent:** CR054 (G8 / M25) — this CR *is* M25, lifted out for independent dispatch; CR054's
  M26 (ESG) remains in the umbrella and could be spun out the same way if wanted.
- **Depends on:** the CR054 `300–322` asset-class/funds/options batch (prerequisites); pairs with
  **CR053** (deep-linkable references) and **CR046** (the screening math).
- Commit tag for filing this plan: `(AT:R63 CR058)`. Build commits: `(AT:R<N> CR058)`.

---

### One-paragraph brief for the education lane

Build a first-class **Sharia-compliant investing** module (~10 lessons + ~20 glossary terms + ~15
coach Q&A + ~10 daily challenges) that finally *teaches* the halal screen the app already gates on:
the four prohibitions, the business + three-ratio screens (numbers computed via CR046), why
standards (AAOIFI vs Bursa SAC vs the index rulebooks) disagree, purification, sukuk vs bonds
(extends the in-flight `303–309`), Islamic contracts, Sharia ETFs (extends `310–315`), and how
AMI's `halal` mandate flag maps to the real two-stage screen (extends `271`/`273`), closing on an
end-to-end screening capstone. House it in a `mandate_compliance` track (shared with ESG) or fold
into `fundamentals_analysis`; assign IDs after the `300–322` batch commits; and hold the line on
**"methodology, not a Sharia ruling"** as firmly as "not investment advice," plus every locked
constraint (simulation-only, AMI naming, frozen codes, curated 5-lesson gateways, DEF064/065).
