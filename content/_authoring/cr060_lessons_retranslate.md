# Lessons — re-translation needed (→ i18n / language manager)

EN lesson bodies edited after their AR/MS siblings were translated. The siblings now teach something the EN
no longer says (the DEF105 silent-divergence class). `locale_staleness_check.py` flags these automatically;
this manifest is the human-readable hand-off. See [[feedback_content_change_flags_translation]].

| lesson | locales stale | defect | why | safe to translate now? |
|---|---|---|---|---|
| 349_the_three_financial_ratio_screens | ar, ms | DEF118 | EN reframed so the halal flag no longer claims to compute the ratios live — it defers to a sourced AAOIFI index (CR069). Added two `<Lesson 355>` refs; changed intro / Example / Quiz-1 explanation / Try-it / Takeaway prose | **YES** — EN is final |

## Coordinate before translating the DEF105 cohort

The DEF105 cohort (`017, 047, 050, 051, 109, 204, 205`) was rewritten to *remove* phantom-Mandate-cap claims
(strip). **Saiful has since decided to BUILD those caps (CR101)** — so those EN lessons will likely be reverted
to teach the caps once the fields ship. **Do not re-translate the stripped versions yet** — they will change
again. Translate 349 now (it is independent of CR101); hold the DEF105 seven until CR101 lands and their EN is
re-settled.

**Guard:** `python3 content/_authoring/locale_staleness_check.py` lists every stale `.ar`/`.ms` sibling.

## CR174 pilot — beat re-authoring, lessons 013–018 (2026-08-20)

The six interactive-pilot EN bodies were re-cut to **≤60 words per paragraph** (CR174 acceptance #2:
each paragraph is one card in interactive mode). Every worked figure, ticker, cap and quiz block is
unchanged — quizzes are byte-identical — but paragraph boundaries and connective prose moved in every
section, so each AR/MS sibling is stale per-`id`. **`locale_staleness_check.py`'s anchor heuristic
will NOT flag these** (the anchors were deliberately preserved); this manifest is the flag.

| lesson | locales stale | change ref | why | safe to translate now? |
|---|---|---|---|---|
| `013_why_risk_matters_more_than_profit` | ar, ms | CR174 | intro/example/trap/try-it re-cut to ≤60w paragraphs; Trader A/B figures unchanged | **YES** — EN is final |
| `014_position_sizing_basics` | ar, ms | CR174 | same re-cut; "Notice three things" split into four cards | **YES** |
| `015_stop_loss_basics` | ar, ms | CR174 | same re-cut; intro reworded, TSLA ticket figures unchanged | **YES** |
| `016_risk_reward_ratio` | ar, ms | CR174 | same re-cut; Example split into four near-verbatim paragraphs | **YES** |
| `017_portfolio_exposure_and_correlation` | ar, ms | CR174 | same re-cut; AMI-enforcement framing moved from intro to end of section 0 | **YES** — the DEF105-cohort hold above is over for this id: CR101 landed and this EN is re-settled |
| `018_drawdown_management` | ar, ms | CR174 | same re-cut; recovery math unchanged | **YES** |

**Translator constraints (CR174 Amendment B + authoring-prompt v4):** keep the `## ` section COUNT
identical to EN (all six have exactly 5) — interactions anchor by section index and
`cr174_models_test.dart` fails the mobile build on a mismatch. Keep paragraph boundaries aligned
with EN and each paragraph ≤60 words in the target language's own count: every paragraph is one
interactive card in that locale.
