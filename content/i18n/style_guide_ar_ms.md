# AR / MS terminology + tone style guide

Consolidated from the translate scripts' own prompt rules (`scripts/translate_arb_lan.py`,
`translate_content_lan.py`, `translate_lessons_lan.py`) so it's one reference instead of
three copies embedded in prompt strings. If you change a script's prompt rules, update
this file too — it's documentation, the scripts remain the source of behavior.

## Never translate / transliterate only

- **"AMI"** — the brand name. Never translated, never transliterated differently.
- **Ticker symbols** — uppercase Latin (AAPL, MSFT, MAYBANK, NVDA). Stay LTR even inside
  an Arabic RTL sentence (Flutter's bidi algorithm handles this for plain `Text` widgets).
- **Agent role names** (CR160 set) — Bull Researcher, Bear Researcher, Fundamentals Analyst,
  Chief Investment Officer, Technical Strategist, Macro & Events, Execution Desk,
  Risk Officer — Conservative, Risk Officer — Aggressive, Risk Officer — Balanced,
  Research Manager, Flow & Positioning, Concierge. Keep the English label.
  The pre-CR160 labels (Portfolio Manager, Market Analyst, News Analyst, Trader, the three
  Debators, Social Media Analyst) are retired — a source string still carrying one is stale EN,
  not a term to preserve.
- **Bull / Bear — TRANSCREATE, do not translate (CR160).** Bull/Bear survive in EN because
  they are market jargon. Rendered literally into Arabic (ثور / دب) or Malay (lembu jantan /
  beruang) they produce an animal, not a market stance. The AR/MS strings therefore use the
  **Long-Side / Short-Side** concept instead: Bull Researcher → Long-Side Analyst,
  Bear Researcher → Short-Side Analyst (in the target language's own words for long/short
  exposure, consistent with the glossary's long/short terms). This is a DELIBERATE divergence
  from the EN source — do NOT "correct" it back to the literal animal, and carry this comment
  into every string file that touches Bull/Bear so the next translator sees it.
- **Currency + numerics** — `$`, `RM`, `SAR`, digits, percent signs, dates. Stay LTR inside
  Arabic sentences (see `mobile/lib/l10n/README.md`'s RTL notes).
- **`{placeholder}` tokens** — preserved exactly, including braces.
- **Islamic-finance proper nouns** — AAOIFI, DJIM, FTSE, MSCI, S&P (standards bodies /
  index families) — transliterate, never translate or expand.

## Islamic-finance / Sharia-observance content (see `sensitive_keys.json`)

- **`exclude` list**: never sent to the LLM at all. Held to EN, routed to Saiful/SME.
- **`strict_review` list**: auto-translated normally, but only counts as verified once
  the stricter Tier-3 confidence bar is met (see `README.md`).
- Ruling-adjacent vocabulary must never flip polarity in translation: "unscreened" must
  never become "not permitted" / "haram" / "non-compliant" — it means the standard never
  examined the company, which is not a ruling either way. This is the single most
  important rule in this style guide; CR069's ARB translator notes spell out why in detail.
- Arabic-loanword glossary terms (riba, gharar, maysir, sukuk, ijarah, murabahah,
  musharakah, mudarabah, takaful, tazkiyah) are proper terms of art — transliterate
  consistently across lessons/glossary/coach rather than each surface picking its own
  rendering.

## Tone

Confident, analyst-to-analyst, terse. No filler, no marketing puffery, no editorializing —
matches `CLAUDE.md`'s brand-voice rule for the whole project, not just EN copy.

## RTL specifics (Arabic)

See `mobile/lib/l10n/README.md`'s existing notes — ticker symbols, currency, and inline
numerics stay LTR inside RTL sentences; prefer a placeholder over a hand-built substring
concatenation for anything with a manual `${prefix}${value}`-style pattern.
