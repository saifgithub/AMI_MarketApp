# Lessons — re-translation needed (DEF423, lane B of CR160's rename → i18n / language manager)

CR160's original content sweep (`64f0739e`, 2026-08-20) renamed six agent roles across EN lesson
prose but missed the bare **`PM`** abbreviation (only the pre-CR160 role's full spelled-out name
was swept) plus two shorthand spots ("Neutral" as the third Risk Officer's name, "Market"/"Social
Media" as agent shorthand in one lesson). Saiful, 2026-09-25: *"We have been mixing the term PM
and CIO in the app, and in the lesson."* This manifest closes that EN gap; AR/MS siblings are
untouched (no CR160 transcreation target exists for PM→CIO the way Bull/Bear→Long-Side/Short-Side
does), so every lesson below needs full retranslation of the touched sentences, not a term swap.

**Guard note (same shape as `cr172_lessons_retranslate.md`):** `locale_staleness_check.py`
mechanism 2 (anchor divergence) will **NOT** catch these edits — `PM`→`CIO` and `Neutral`→
`Balanced` are prose-word substitutions with no change to tickers, numbers, URLs, or component
ids, so the anchor multiset is unchanged. Confirmed by running the script after this edit: 0 of
the 52 files below appear in its STALE list. This is DEF105's exact shape again. The standing fix
is CR060 Phase 6's per-`id` `source_sha` stamp (still not built into the translation pipeline as
of this writing). Hand-written manifest is the correct fallback per existing convention.

Keyed by `id`. See [[feedback_content_change_flags_translation]].

## What changed (EN only)

- Standalone **`PM`** (the abbreviation, mid-sentence — e.g. "the PM enforces", "1-on-1 with the
  PM") → **`CIO`**, in body prose and in the `title:` frontmatter field where present. `agent_id`
  keys (`portfolio_manager` in `agent_callouts`, `<ChatWith agent="portfolio_manager" />`), the
  lesson `id`/filename, and `tags: ["pm", ...]` / `topic: "pm_independence"` values were **not**
  touched — those are keys/ids, not rendered text, and are explicitly out of CR160's scope.
- One exclusion: `348_the_business_activity_screen.en.mdx` mentions **"Philip Morris International
  (PM)"** — a stock ticker, not the agent. Left untouched; not in this manifest.
- `290_position_sizing_basics.en.mdx`: the Risk Officer table's third row, **"Neutral"** →
  **"Balanced"** (the pre-CR160 third stance name → Risk Officer — Balanced, per CR160's table).
- `268_why_twelve_agents_not_one.en.mdx`: "...Conservative wants 2%; **Neutral** lands at 3%" →
  "...**Balanced** lands at 3%."
- `269_analysts_gather_researchers_debate.en.mdx`: one sentence used bare "Market" / "Social
  Media" as agent shorthand ("**Market** reads $215... **Social Media** reports neutral retail
  sentiment") — updated to "**The Technical Strategist** reads $215... **Flow & Positioning**
  reports neutral retail sentiment" to match the renamed labels used everywhere else in the same
  lesson.

## Files (52), all `ar` + `ms` stale

| id | PM→CIO occurrences | other changes |
|---|---|---|
| `011_long_term_wealth_building` | 1 | — |
| `012_why_most_traders_fail` | 3 | — |
| `013_why_risk_matters_more_than_profit` | 1 | — |
| `014_position_sizing_basics` | 1 | — |
| `017_portfolio_exposure_and_correlation` | 2 | — |
| `018_drawdown_management` | 1 | — |
| `019_survival_mindset` | 1 | — |
| `046_fear_and_capitulation` | 2 | — |
| `047_revenge_trading` | 2 | — |
| `049_overconfidence` | 1 | — |
| `051_discipline_vs_excitement` | 3 | — |
| `060_bear_markets` | 1 | — |
| `066_telegram_whatsapp_pump_groups` | 1 | — |
| `072_what_ami_can_do_for_you` | 4 | — |
| `073_what_ami_cannot_do` | 1 | — |
| `074_ai_hallucinations_and_amis_safety_floor` | 21 | — |
| `075_the_risk_of_overreliance` | 5 | — |
| `076_human_oversight_is_the_product` | 9 | — |
| `108_regime_dependent_correlation` | 4 | — |
| `109_risk_budgeting_across_positions` | 1 | — |
| `111_gamblers_ruin_and_the_one_percent_rule` | 1 | — |
| `142_atr_position_sizing_and_stops` | 1 | — |
| `202_bottom_tick_capitulation` | 1 | — |
| `203_portfolio_wide_panic_selling` | 17 | — |
| `208_size_creep_on_winning_streaks` | 3 | — |
| `209_system_delusion_lucky_vs_skilled` | 1 | — |
| `211_journal_review_as_discipline` | 2 | — |
| `213_explain_to_a_six_year_old` | 3 | — |
| `253_mandate_adjustments_by_regime` | 8 | — |
| `268_why_twelve_agents_not_one` | 1 | "Neutral" → "Balanced" (the third Risk Officer's name, per CR160's table) |
| `269_analysts_gather_researchers_debate` | 10 | "Market"/"Social Media" shorthand → "Technical Strategist"/"Flow & Positioning" |
| `270_why_the_pm_is_structurally_separate` | 27 | title field: "Why the PM is..." → "Why the CIO is..." |
| `271_inside_the_deterministic_compliance_check` | 5 | — |
| `272_the_mandate_is_your_contract` | 16 | — |
| `273_uncoachable_means_no_prompt` | 8 | — |
| `274_the_safety_floors_audit_trail` | 17 | — |
| `276_spotting_hallucinated_numbers` | 6 | — |
| `277_pass_is_not_buy` | 20 | — |
| `278_coaching_changes_style_not_floor` | 12 | — |
| `279_you_are_the_ceo` | 2 | — |
| `283_market_order_vs_limit` | 1 | — |
| `290_position_sizing_basics` | 4 | "Neutral" → "Balanced" (Risk Officer table row) |
| `291_the_pm_and_your_mandate` | 20 | title field: "The PM and Your Mandate" → "The CIO and Your Mandate" |
| `292_research_manager_synthesis` | 3 | — |
| `293_market_integrity_why` | 2 | — |
| `298_fiduciary_duty` | 1 | — |
| `299_conflicts_of_interest` | 1 | — |
| `300_suitability_kyc` | 2 | — |
| `355_how_amis_halal_flag_maps_to_real_screening` | 4 | — |
| `356_capstone_screen_a_company_end_to_end` | 5 | — |
| `359_keeping_a_decision_journal` | 1 | — |
| `364_capstone_evaluate_a_room_verdict` | 3 | — |

**Total: 273 `PM`→`CIO` substitutions across 52 lessons, plus the 2 Risk Officer table/shorthand
fixes and 1 shorthand-prose fix above.**

**Safe to translate now: YES for all 52.** These are label-only substitutions — no teaching claim,
number, or source changed (BOK quality rule holds). The `id`, quiz `answer={n}` indices, quiz
option counts, and all figures are byte-identical to what a translator already has; only the
word "PM" (and in three lessons, "Neutral"/"Market"/"Social Media" as agent shorthand) changed to
its CR160 replacement.

## Ambiguous / left alone (not in scope, listed for the record)

- `content/lessons/348_the_business_activity_screen.en.mdx` — "Philip Morris International (PM)"
  is a stock ticker, not the agent. Left untouched.
- 16 EN lessons use **"Trader A" / "Trader B" / "Trader C"** as hypothetical exercise personas in
  quiz scenarios (013, 015, 016, 018, 019, 100, 101, 103, 104, 106, 107, 110, 111, 202-adjacent,
  296, 390, 392) — these are pedagogical stand-ins for a generic human trader, not AMI's Execution
  Desk agent. Confirmed against CR160's own text: *"Pricing-tier 'Trader', 'Day Trader' preset and
  Trader A/B/C exercise personas deliberately kept."* Left untouched; already covered by the
  existing `test_cr160_agent_rename.py` exclusion, which explicitly carves "Trader" out for this
  reason.
- MS/AR siblings still spell out the pre-CR160 role name in full (the "PM" abbreviation plus its
  expansion, and the Arabic gloss for it) and the pre-CR160 Risk Officer sub-names, throughout —
  not touched. No CR160 transcreation target exists for PM→CIO the way it does for
  Bull→Long-Side/Bear→Short-Side (checked `content/i18n/style_guide_ar_ms.md`: the only
  transcreation note on file is Bull/Bear), so per DEF423's brief this is full retranslation, not
  a term swap I can safely make without inventing target-language wording.
