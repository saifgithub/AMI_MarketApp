# AR / MS terminology + tone style guide

Consolidated from the translate scripts' own prompt rules (`scripts/translate_arb_lan.py`,
`translate_content_lan.py`, `translate_lessons_lan.py`) so it's one reference instead of
three copies embedded in prompt strings. If you change a script's prompt rules, update
this file too — it's documentation, the scripts remain the source of behavior.

## Never translate / transliterate only

- **"AMI"** — the brand name. Never translated, never transliterated differently.
- **Ticker symbols** — uppercase Latin (AAPL, MSFT, MAYBANK, NVDA). Stay LTR even inside
  an Arabic RTL sentence (Flutter's bidi algorithm handles this for plain `Text` widgets).
- **Agent role names** — Bull Researcher, Bear Researcher, Fundamentals Analyst, Portfolio
  Manager, Market Analyst, News Analyst, Trader, Conservative Debator, Aggressive Debator,
  Neutral Debator, Research Manager, Social Media Analyst, Concierge. Keep the English label.
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
