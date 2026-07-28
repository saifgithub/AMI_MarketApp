# DEF144 — the translation model leaks foreign scripts into AR/MS content

## What

The in-house model (Qwen3.6-35B-A3B-NVFP4, on-prem vLLM) occasionally code-switches
mid-generation: a Chinese, Cyrillic or Japanese word glued into otherwise-correct Arabic
or Malay text. Sometimes it cuts the target-language word in half to do it. This is worse
than a stray glyph — both instances Saiful caught by eye were inside quiz answer options,
i.e. user-facing content a learner reads and is graded against:

- `192_payout_ratio_on_fcf.ar.mdx:59` — `…ويدفع الانخفاض نفسه لدى الشركة ب نسبة التوزيع
  فوق 100٪ وي迫使 قرار خفض التوزيع` — `迫使` is Chinese for "forces/compels", dropped into
  the middle of an Arabic sentence.
- `176_trailing_vs_forward_pe.ar.mdx:54` — `…كلا مضاعفي الربحية المستقبليين موثوقان بنفس
  الق因为它们 تأتيان من نفس مصدر البيانات` — `因为它们` is Chinese for "because they", and
  it severed the Arabic word `القدر` ("equally") mid-way through to insert itself.

## How found

Saiful spotted both by eye while a DEF126 blind-retranslation job was running live and
asked directly: *"It's crazy to me, we need to put in so much guardrails to deliver the
language. I think some may have already slipped past. How do we correct this?"*

## Scope — measured across three surfaces, not estimated

**1. The job that was running.** Stopped it immediately (was at 257/296 AR lessons).
Scanned everything it had written so far: **11/288 (3.8%)** already contaminated —
`001_what_is_a_stock`, `015_stop_loss_basics`, `121_pullback_depth_fibonacci_zones`,
`176_trailing_vs_forward_pe`, `191_fixed_vs_floating_and_currency_mismatch`,
`192_payout_ratio_on_fcf`, `232_regime_segmented_backtests`, `248_vix_term_structure`,
`252_regime_change_realtime_vs_hindsight`, `311_expense_ratio_tracking_error`,
`328_capstone_reading_the_macro_machine`.

**2. Everything already committed (`HEAD`) — the "has this already shipped" question.**
Swept `content/lessons/*.{ar,ms}.mdx`, `content/ai_coach/{ar,ms}/*.json`,
`content/daily_challenges/{ar,ms}/*.json`, `content/glossary/terms.{ar,ms}.json`, and
`mobile/lib/l10n/app_{ar,ms}.arb`. **19 files already committed, contaminated:**

- 17 lessons: `015_stop_loss_basics.ar`, `020_candlesticks_anatomy_of_a_bar.ms`,
  `026_moving_averages.ar`, `031_indicator_limitations.ar`,
  `066_telegram_whatsapp_pump_groups.ar`, `106_asymmetric_rr_in_regimes.ar`,
  `117_dynamic_vs_static_support_resistance.ar`,
  `177_pe_in_cyclicals_peak_earnings_trap.ar`, `181_pb_for_banks_regulatory_book.ar`,
  `184_dupont_decomposition_deep.ar`, `196_organic_vs_acquired_growth.ar`,
  `239_strategy_rotation_by_regime.ar`, `252_regime_change_realtime_vs_hindsight.ar`,
  `257_pre_pump_accumulation_signals.ar`, `273_uncoachable_means_no_prompt.ar`,
  `311_expense_ratio_tracking_error.ar`, `347_the_four_prohibitions.ar`.
- 2 content files: `content/ai_coach/ar/platform.json` (`[19].short_answer`: "...لا يمس
  底线 السلامة" — 底线 is Chinese for "bottom line", glued onto "السلامة" with no space);
  `content/daily_challenges/ar/2026_06.json` (`[20].options[2]`: "...لا تملك ни البصيلة" —
  ни is Russian for "neither/nor").
- 0 in `content/glossary/terms.{ar,ms}.json` and 0 in the mobile ARBs.

Confirmed **genuinely new to this corpus**, not a stale scan artifact: `git show
HEAD:<path>` for both of Saiful's two examples returns zero CJK matches — the corruption
in those two specific files came from the run just stopped. But the 19 already-committed
hits prove the *pattern itself* is not new — it has been present since at least the
original CR083 pass and DEF109's partial retranslation, just never looked for.

**One piece of real good news, not by design:** all 17 already-committed lesson
instances were already sitting in DEF126's own "needs review" bucket — none was hiding
inside the 81 lessons marked "verified". The LLM verifier happened to flag something on
every one of them. That is luck, not a guarantee: nothing in the verification prompt
asks specifically "does this contain a foreign script", so a future lesson hitting this
failure mode while the LLM verifier judges everything *else* about it as fine was never
ruled out before this fix.

## Rate is stable across two independent passes

~3-4% whether measured against the from-scratch CR083 corpus pass (the 19 already-shipped
hits, against ~683 locale files = 2.8%) or this session's fresh retranslation pass
(11/288 = 3.8%). Re-running the same model again does not make this go away — it's a
property of the model's generation, most likely related to NVFP4 quantization (a known
class of degenerate-output risk at low precision), not a one-off sampling fluke.

## Fix

A new deterministic, LLM-free guard, since — per **DEF083**'s own framing, independently
re-derived here — *"this class needs no LLM, which is the argument for a guard over a
periodic audit."* `scripts/_i18n_script_guard.py::foreign_script_leak(text, locale)`:

- Flags CJK ideographs, hiragana/katakana, hangul, Cyrillic, Thai, Devanagari for **both**
  `ar` and `ms`.
- Additionally flags Arabic script for `ms` (Malay is Latin-script; Arabic has no
  legitimate reason to appear there).
- **Deliberately excludes Greek** (`σ`, `Σ`, `β`, `Δ`, `α`, `μ`...) — legitimate
  finance/statistics notation. Confirmed both flagged Greek instances
  (`110_tail_risk_and_fat_tails`, `335_expected_value_the_core_of_every_decision`) have
  the same symbols in the EN source, so an earlier draft of this scan that included Greek
  was over-flagging, not under-flagging.

Wired into every place a model output is accepted, across all three LAN translate
scripts:

- `translate_lessons_lan.py`: `_translate_prose` retries (same budget as the existing
  sentinel-mismatch retry); `_translate_quizzes` and `_translate_title` fall back to EN
  per-field — same shape as the placeholder/sentinel guards already there.
- `translate_content_lan.py`: `_apply_translations`, per text field and per list-field
  item, same EN-fallback shape, reported the same way as an existing "problem".
- `translate_arb_lan.py`: dropped like a placeholder-mismatch key (key stays unfilled
  rather than corrupted).

**Verified live**, not just unit-tested: re-ran the guarded script against the exact two
lessons Saiful flagged. `176_trailing_vs_forward_pe` logged `quiz q1 options:
foreign-script leak — keeping EN` and the option now renders in clean English rather than
the severed-Arabic-plus-Chinese string; both files scan clean (zero leaks) end to end
afterward.

## Not yet done — tracked here, not folded into DEF126

- **Fold the same deterministic check into `i18n_verify_lesson_translation.py` as a hard
  pre-check**, ahead of the LLM call. Right now a verifier pass "catching" this is still
  incidental — the LLM has to happen to notice and say so. A deterministic pre-check
  removes the reliance on luck entirely, and costs nothing (no LLM call).
- **Fix the 2 already-committed non-lesson files** (`platform.json`, `2026_06.json`) —
  outside DEF126's scope (lessons only). Needs a `translate_content_lan.py --overwrite`
  pass targeted at just those two records, now guarded.
- The 17 already-committed **lesson** instances don't need separate handling — they were
  already in DEF126's 600-flagged "needs review" list and ride that remediation, now
  running under this same guard.

## Related

**DEF126** (the corpus-wide quality gap this was found while remediating), **DEF083**
(the "this class needs no LLM" argument, independently re-derived here for a different
failure class).
