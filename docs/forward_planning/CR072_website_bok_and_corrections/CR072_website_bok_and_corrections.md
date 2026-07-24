# CR072 — Website update: market the Body of Knowledge, correct the Sharia claim

**Status:** done · **Opened:** 2026-07-23 · **Track:** R64
**Owner split:** Claude ships all copy + code + deploy; Saiful decides DEF084, supplies the
Play opt-in / TestFlight links and the Lessons screenshot.

---

## Why

The site was last touched at CR049, when the product was 270 lessons across 7 visible
tracks and "iOS first". The product moved; the site did not.

| | What the site says | What is true (verified in repo, 2026-07-22) |
|---|---|---|
| Lessons | "Core lessons library" — one pricing bullet | **342** (`content/lessons/*.en.mdx`) |
| Tracks | not mentioned | **13**, incl. net-new Asset Classes (20), Economics (12), Quant Methods (12), Ethics (10), Islamic Finance (10), Decision Evaluation (8) |
| Glossary | not mentioned | **208** terms (`content/glossary/terms.en.json`) |
| Sourcing | not mentioned | CR054/CR060 — the BOK batch cites the CFA/CMT/FRM canon + primary sources, behind a dual-pass accuracy gate |
| Lessons UI | not shown | 13-facet honeycomb (DEF082) — *the same 4/5/4 comb the marketing site already uses for the 13 agents* |
| Android | "iOS & Android" | Play internal-testing track live, Play App Signing enrolled, Google Sign-In fixed (DEF076) |

Saiful (2026-07-22): lead with **all three** — the Body of Knowledge, Android/Play, and
the 13-facet comb.

## The correction that forced this CR

Two places on the live site sell **"Halal / Sharia screening mode"** as a shipped feature:
the compare table (`index.html:468`) and the Floor Manager pricing card (`index.html:595`).
**DEF084** established the `halal` flag was a hardcoded 7-ticker allowlist while the real
`sharia_screen()` in `backend/app/trading_math/screening.py` was called nowhere — a public
page making a **religious-observance assurance the product did not compute**.

**The app has since been fixed and the website is now the only place still making the
claim.** DEF084 was resolved Option 2 (AT:R64, `bd5c74d`+`cef212f`+`e344b27`, shipped in
mobile `+51` via `alpha-2026-07-22-4`): the set is relabelled `DEFAULT_HALAL_DEMO_UNIVERSE`
(`backend/app/api/mandate.py:34,274`) and the rejection copy now says *"outside AMI's
curated demonstration universe"*. Saiful, filing **CR069**: *"We have had to drop the
'Halal' filter because we currently do not have an indicator to say if a ticker/counter is
halal/shariah compliant"* — none of our five market-data feeds carries one.

So the website copy is not being softened ahead of a fix; it is **catching up to a product
decision already made**. The roadmap line points at CR069, not at a vague "coming soon".
The same pricing card also sells "GCC & Bursa market coverage" against the locked
US-equities-at-MVP decision — removed in the same pass.

## Scope

| WS | What | Commit |
|---|---|---|
| 1 | Corrections — pull Sharia + GCC claims, `Coach Your Agent` → `Brief Your Agent` | first, standalone |
| 2 | New `#curriculum` section + 13-track comb (HTML + CSS) | second |
| 3 | Android/Play + app-preview framing | third |
| 4 | Concierge KB (`faq.md`) + Sharia escalation | third |
| 5 | Cache-bust sweep → `?v=cr072` on all four pages | fourth |

## Two rules this CR is built on

**1. The comb mirrors the app; it is not re-designed on the web.** Slot order, colour and
label come verbatim from `mobile/lib/screens/lessons/honeycomb_layout.dart`
(`honeycombTrackOrder` / `honeycombTrackColor` / `honeycombTrackLabel`), resolving through
`mobile/lib/theme/ami_theme.dart:32-53`. That palette was solved to maximise the *minimum*
OKLab ΔE over the comb's 26 adjacent pairs (weakest seam 0.3278 vs 0.1807 for the shipped
palette's own closest pair). Re-ordering or re-colouring on the web alone throws the solve
away and de-syncs the two surfaces.

**2. Claim the process, never the result.** CR060's sweep measured a high defect rate in
our own corpus, and DEF078 (19 content fixes) + DEF083 are still open. The site says
*"every sourced lesson goes through a dual-pass accuracy gate"* — true — and never
*"every lesson is verified"* — not true today.

## Corpus figures — regenerate, don't trust this file

```bash
ls content/lessons/*.en.mdx | wc -l                                    # 342
grep -h '^track:' content/lessons/*.en.mdx | sort | uniq -c | sort -rn # 13 tracks
python3 -c "import json;print(len(json.load(open('content/glossary/terms.en.json'))))"  # 208
```

Track table as of 2026-07-22 (slot order = the app's `honeycombTrackOrder`):

| Slot | Track | Label | Lessons | Colour |
|---|---|---|---|---|
| 1 | `technical_analysis` | TECHNICAL | 45 | `#8B5CF6` |
| 2 | `sentiment_behaviour` | SENTIMENT | 10 | `#EC4899` |
| 3 | `news_macro` | NEWS & MACRO | 19 | `#F59E0B` |
| 4 | `ethics_integrity` | ETHICS | 10 | `#4F46E5` |
| 5 | `risk_portfolio` | RISK | 16 | `#EF4444` |
| 6 | `economics_macro` | ECONOMICS | 12 | `#A3E635` |
| 7 | `foundations` | FOUNDATIONS | 16 | `#3B82F6` |
| 8 | `islamic_finance` | ISLAMIC FINANCE | 10 | `#D946EF` |
| 9 | `quant_methods` | QUANT | 12 | `#4ADE80` |
| 10 | `fundamentals_analysis` | FUNDAMENTALS | 66 | `#06B6D4` |
| 11 | `asset_classes` | ASSET CLASSES | 20 | `#F97316` |
| 12 | `edge_process` | EDGE | 98 | `#10B981` |
| 13 | `decision_evaluation` | EVALUATION | 8 | `#FB7185` |

## Reuse (not rebuilt)

- `.honey-abs` / `.honey-hex` comb geometry — `website/assets/css/site.css` (CR049's
  interlocking-hex work). The curriculum comb uses the identical container and slot
  coordinates as the agent comb.
- `.card.top-*` pattern for the three supporting cards.
- `.honey-mobile` flex fallback under 560px.
- `website_api/app/services/faq_answer.py::classify_escalation` — the deterministic
  escalation floor; Sharia/halal questions route into it rather than being auto-answered.

## Acceptance

1. No live page claims Sharia screening, GCC/Bursa coverage, or "Coach Your Agent".
2. `#curriculum` renders 13 hexes at 4/5/4 with app-parity colours; degrades to
   `.honey-mobile` under 560px.
3. Copy asserts only regenerated corpus figures; no clean-bill-of-health claim.
4. Android framing states internal-testing/TestFlight, not a public store download.
5. `faq.md` agrees with the page; a halal/Sharia question escalates rather than being
   auto-answered.
6. `website_api` tests green; all four pages on `?v=cr072`; live curl checks pass.

## Out of scope (flagged, not fixed here)

- **`legal/policies/privacy_policy.md:148-150` §14 and its transcription at
  `website/privacy/index.html:302-303` (v2.0, live) still read "If you enable
  Halal/Shariah screening…"** — stale after DEF084's Option-2 relabel. The clause is about
  *data handling of the preference*, not a claim the screen computes, so it is not
  urgent — but the feature it names no longer exists under that name. Belongs to the
  legal track (`AT:legal`, CR068), which owns the canonical markdown; the website HTML is
  a manual transcription of it per `legal/VERSIONING.md`. **Not edited here** — I don't
  unilaterally rewrite a published legal document. Raised with Saiful.
- **CR069** — sourcing a real Sharia-compliance indicator. Blocked on a data feed that
  carries one; none of our five does.
- **10 SHARIA lessons** still carry the citation-integrity failures DEF084 catalogued
  (0 verified / 8 findings / 2 escalations), and DEF082's fix means they are reachable
  in-app again. Education lane + SME, not the website.
- Play internal-testing opt-in URL + TestFlight link (CTAs stay on `#waitlist` until sent).
- Lessons-comb device screenshot for a fourth preview frame.
- Designed og-image (PIL temp still live), Turnstile SECRET, CF purge of stale `Archive.zip`.

---

## Outcome (2026-07-23) — shipped and verified live

| WS | Commit | Result |
|---|---|---|
| 1 Corrections | `c976785` | Sharia + GCC claims removed; `Coach Your Agent` -> `Brief Your Agent`; roadmap line added |
| 2 Curriculum | `d43241e` | `#curriculum` section + 13-track comb; nav entry |
| 3/4/5 | `ddf82f9` | Android/Play framing; KB refresh; `_COMPLIANCE_RE` escalation; cache-bust sweep |
| Leak fix | `81778dd` | `website/` reduced to deployable content only |

**Live verification:**

```
curl .../ | grep -c 'honey-hex t-'                  -> 13
curl .../ | grep -c 'Halal / Sharia|Coach Your Agent' -> 0
site.css?v=cr072, cf-cache-status: MISS, 26 .t- rules served
Archive.zip / WEBSITE.md / deploy_ftp.py            -> 404, 404, 404
api-website /health                                  -> {"ok":true}
"Is AAPL halal?"          -> compliance escalation, "does not run a Sharia compliance screen"
"Is Tesla a good halal buy?" -> compliance wins over advice, as ordered
"Should I buy NVDA?"      -> advice escalation intact
"How many lessons?"       -> "342 lessons across 13 tracks ... 208 glossary terms ... CFA, CMT, FRM"
```

`website_api` tests 23 -> 25.

## What this CR found that it was not looking for

**The CR049 leak fix was never durable.** The rsync dry-run before deploy showed
`website/` still contained `Archive.zip`, `WEBSITE.md` and `deploy_ftp.py` — the three
files CR049 deleted from the live docroot after finding them publicly served. CR049
removed them from the *server* and not from the *source*, so this deploy would have
re-published all three. Fixed by relocating them out of `website/` (`81778dd`) rather
than by adding excludes, so the property holds by construction.

The same dry-run showed `--delete` would have removed the server's `.well-known/` and
`.ftpquota`. Same class as DEF081. Both now excluded and documented in `docs/WEBSITE.md`.

**Generalisable rule, now in `docs/WEBSITE.md`:** deleting a file from a server is not
the same as fixing the thing that put it there. And always dry-run an rsync with
`--delete` against a host whose contents you did not author.

---

## Follow-on (2026-07-24) — "How the room works" analyst-team blurb

Saiful, after the curriculum ship: *"Read `docs/initial_specs/02_agents/agent_data_blueprint.md`
and write a web blurb on how the analyst team works — keep the current tone, keep it
concise, keep it true to the file. Don't credit the agents with data the blueprint marks
unavailable, but don't say that it isn't available either."*

Added a two-paragraph **"How the room works"** block inside `#agents` (below the comb),
grounded strictly in the blueprint:

- **Names only available inputs.** Fundamentals → the full §1 fundamentals set + next-earnings;
  Market → 20/50-day trend, RSI, volume-vs-20-day, support, breakout; News → headlines by
  publisher/recency + per-headline sentiment; Social → all six fields (mention volume + trend,
  communities, buzz, bull/bear split). The deliberation chain (Bull/Bear on the shared read +
  their per-ticker journal → Research Manager synthesis → Trader's entry/stop/target with
  **computed** R:R and drawdown → three risk debators red-teaming the mandate → PM's final call
  behind the uncoachable compliance floor) matches the §2 phase gate exactly.
- **Honest-degradation rule (§7) respected.** Never names an unavailable source and never
  flags the gap: no MACD / Bollinger / intraday / MA-crossover (Technicals), no macro calendar
  or 8-K/S-1 (News), no Twitter/StockTwits/Google Trends/Discord (Social), no forward guidance
  or peer-basket P/E (Fundamentals). "Reward-to-risk and drawdown **computed, not asserted**"
  encodes the blueprint's insistence (§3 Trader note) that the figure be real, not narrated.
- **Also corrected the News comb sub-label** `Filings & events` → `Headlines & events`: the
  blueprint marks regulatory filings (8-K/S-1) as *not available* to the News Analyst, so the
  old label over-claimed.

No `cr_list.md` edit (row already exists; avoids the raced register). Ships on the CR072 tag.

### Revised (2026-07-24) — made it interactive instead of text

Saiful: *"that was a boring text-filled section. a web is a multimedia environment. how about,
when the visitor passes over the agent hexagon … instead of just highlighting, we show what
the agent is supposed to do and data it gets."*

Replaced the two-paragraph blurb with an **interactive agent brief**. Each of the 13 comb
hexes (and the 13 mobile cards) now carries `data-agent` / `data-job` / `data-reads` /
`data-accent`; hovering, focusing (keyboard) or tapping a hex feeds a single shared
`#agent-brief` panel below the comb — icon, name, one-line job, and the agent's data feed as
chips, tinted to that agent's accent. Defaults to the Concierge so it never renders empty.

- **Why one shared panel, not per-hex tooltips:** `.honey-hex` uses `clip-path`, which clips
  its own children — a tooltip *inside* a hex is impossible. One JS-updated panel is the
  robust pattern (noted in the CSS).
- **Same blueprint grounding, now per-agent.** Every `data-reads` chip is a field
  `agent_data_blueprint.md` marks *available* for that agent (Social gets all six §1 fields;
  Trader's chips include the computed R:R + drawdown; PM's include the uncoachable compliance
  floor). Honest-degradation §7 still holds: no unavailable source is named (no MACD/Bollinger,
  no macro calendar/filings, no Twitter/StockTwits), and no gap is flagged.
- **Accessible:** hexes/cards are `tabindex="0"` with `:focus-visible` outlines; the panel is
  `aria-live="polite"`; honours `prefers-reduced-motion`.
- **CSS change → cache-bust bumped `cr072` → `cr072b` on all seven pages that link
  `site.css`** (index, privacy, terms + terms/v2 + terms/v3, competition-rules,
  sad-to-see-you-go). Verified locally with Playwright: default Concierge → hover Trader
  renders the 5 trade-math chips + amber accent → Social renders all 6 → keyboard focus works;
  no JS errors (the localhost Turnstile 400 is the domain-locked bot widget, not this feature).
